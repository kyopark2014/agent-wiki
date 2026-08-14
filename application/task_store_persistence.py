"""Persist global + per-user task DBs via S3 Files mount, S3 API, or local session_storage.

Global ``tasks.db`` holds ``login_events`` (and legacy tasks/messages for migrate).
Per-user ``{user}.db`` holds tasks/messages; durable copy lives under session_storage.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import threading
from typing import Iterable

from application import app_data_backend as backend

logger = logging.getLogger("task_store_persistence")

_PERSIST_DEBOUNCE_SECONDS = 20.0

_persist_lock = threading.Lock()
_persist_timer: threading.Timer | None = None
_global_dirty = False
_dirty_users: set[str] = set()


def mount_dir() -> str:
    return backend.mount_dir()


def persistence_enabled() -> bool:
    """True when durable storage is available (mount or S3)."""
    return backend.backend_mode() in {"mount", "s3"}


def working_db_path() -> str:
    """Global/legacy working DB path."""
    return backend.working_tasks_db_path()


def persistent_db_path() -> str:
    """Mount path for ECS; for S3 mode returns the logical s3:// URI for logs."""
    mode = backend.backend_mode()
    if mode == "s3":
        bucket, _ = backend.s3_bucket_and_region()
        return f"s3://{bucket}/{backend.tasks_db_s3_key()}"
    return backend.persistent_tasks_db_path()


def _user_segment(user_id: str) -> str:
    from application.utils import sanitize_user_path_segment

    segment = sanitize_user_path_segment(user_id)
    if not segment:
        raise ValueError(f"Invalid user_id for DB path: {user_id!r}")
    return segment


def working_user_db_path(user_id: str) -> str:
    return backend.working_user_db_path(_user_segment(user_id))


def durable_user_db_path(user_id: str) -> str:
    """Canonical durable path under SESSION_STORAGE_DIR/{user}/{user}.db."""
    from application.utils import get_user_db_path

    return get_user_db_path(user_id)


def persistent_user_db_path(user_id: str) -> str:
    """Log-friendly durable location (mount path or s3:// URI)."""
    segment = _user_segment(user_id)
    mode = backend.backend_mode()
    if mode == "s3":
        bucket, _ = backend.s3_bucket_and_region()
        return f"s3://{bucket}/{backend.user_db_s3_key(segment)}"
    return durable_user_db_path(user_id)


def _db_ready(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0


def _copy_db_files(source: str, destination: str) -> None:
    """Copy DB bytes only (no metadata/xattrs).

    S3 Files / NFS rejects os.setxattr with Errno 524 (EREMOTEIO). shutil.copy2
    calls copystat → setxattr after a successful content copy, so persist always
    failed even though the file body was written. Use shutil.copy instead.
    """
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy(source, destination)
    for suffix in ("-wal", "-shm"):
        src = source + suffix
        dst = destination + suffix
        if os.path.isfile(src):
            shutil.copy(src, dst)
        elif os.path.isfile(dst):
            os.remove(dst)


def _checkpoint_sqlite(db_path: str) -> None:
    if not os.path.isfile(db_path):
        return
    conn = sqlite3.connect(db_path, timeout=5)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


def _remove_db_files(path: str) -> None:
    for candidate in (path, path + "-wal", path + "-shm"):
        try:
            if os.path.isfile(candidate):
                os.remove(candidate)
        except OSError as exc:
            logger.warning("Could not remove %s: %s", candidate, exc)


def _restore_from_mount(working: str, persistent: str) -> None:
    os.makedirs(os.path.dirname(working), exist_ok=True)

    if _db_ready(persistent):
        _remove_db_files(working)
        _copy_db_files(persistent, working)
        logger.info("Restored task DB from S3 Files mount: %s -> %s", persistent, working)
        return

    if os.path.isfile(persistent):
        logger.warning(
            "Persistent task DB empty, starting fresh: %s (size=%s)",
            persistent,
            os.path.getsize(persistent),
        )
    else:
        logger.info("No persistent task DB yet at %s; creating fresh working DB", persistent)

    if any(os.path.isfile(working + suffix) for suffix in ("", "-wal", "-shm")):
        logger.info(
            "Removing pre-existing working task DB (e.g. image-baked test data): %s",
            working,
        )
        _remove_db_files(working)


def _restore_from_s3(working: str, *, s3_key: str) -> None:
    bucket, region = backend.s3_bucket_and_region()
    if not bucket:
        return
    os.makedirs(os.path.dirname(working), exist_ok=True)

    tmp = working + ".s3download"
    try:
        if backend.download_s3_file(bucket, s3_key, tmp, region) and _db_ready(tmp):
            _remove_db_files(working)
            os.replace(tmp, working)
            for suffix in ("-wal", "-shm"):
                side = working + suffix
                if os.path.isfile(side):
                    os.remove(side)
            logger.info("Restored task DB from S3: s3://%s/%s -> %s", bucket, s3_key, working)
            return
        logger.info(
            "No S3 task DB at s3://%s/%s; using local working DB %s",
            bucket,
            s3_key,
            working,
        )
    except Exception:
        logger.exception(
            "S3 restore failed for s3://%s/%s; falling back to local/migrate",
            bucket,
            s3_key,
        )
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def restore_tasks_db() -> None:
    """Prepare working global tasks.db from mount or S3 when durable storage is available."""
    working = working_db_path()
    mode = backend.backend_mode()

    if mode == "mount":
        _restore_from_mount(working, backend.persistent_tasks_db_path())
        return

    if mode == "s3":
        _restore_from_s3(working, s3_key=backend.tasks_db_s3_key())
        return

    logger.info(
        "Task DB persistence disabled (no mount at %s and no s3_bucket); local only",
        mount_dir(),
    )


def restore_user_db(user_id: str) -> bool:
    """Copy durable per-user DB into the working path if available. Returns True if restored."""
    working = working_user_db_path(user_id)
    mode = backend.backend_mode()
    segment = _user_segment(user_id)

    if mode == "mount" or mode == "local":
        durable = durable_user_db_path(user_id)
        if _db_ready(durable):
            os.makedirs(os.path.dirname(working), exist_ok=True)
            _remove_db_files(working)
            _copy_db_files(durable, working)
            logger.info("Restored user DB from durable path: %s -> %s", durable, working)
            return True
        return False

    if mode == "s3":
        try:
            _restore_from_s3(working, s3_key=backend.user_db_s3_key(segment))
        except Exception:
            logger.exception("S3 user DB restore raised for %s", user_id)
        if _db_ready(working):
            return True
        durable = durable_user_db_path(user_id)
        if _db_ready(durable):
            os.makedirs(os.path.dirname(working), exist_ok=True)
            _copy_db_files(durable, working)
            logger.info("Restored user DB from local durable: %s -> %s", durable, working)
            return True
        return False

    return False


def _persist_to_mount(working: str, persistent: str) -> None:
    _checkpoint_sqlite(working)
    _copy_db_files(working, persistent)
    logger.info("Persisted task DB to durable path: %s -> %s", working, persistent)


def _persist_to_s3(working: str, *, s3_key: str) -> None:
    bucket, region = backend.s3_bucket_and_region()
    if not bucket:
        return
    _checkpoint_sqlite(working)
    backend.upload_s3_file(bucket, s3_key, working, region)


def _persist_global(*, force: bool = False) -> None:
    global _global_dirty

    mode = backend.backend_mode()
    if mode == "local":
        _global_dirty = False
        return

    working = working_db_path()
    if not force and not _global_dirty:
        return
    if not _db_ready(working):
        logger.warning("Working global task DB missing, skip persist: %s", working)
        _global_dirty = False
        return

    try:
        if mode == "mount":
            _persist_to_mount(working, backend.persistent_tasks_db_path())
        elif mode == "s3":
            _persist_to_s3(working, s3_key=backend.tasks_db_s3_key())
        _global_dirty = False
    except Exception:
        logger.exception("Failed to persist global task DB (%s)", mode)


def _persist_user(user_id: str) -> None:
    working = working_user_db_path(user_id)
    if not _db_ready(working):
        logger.warning("Working user DB missing, skip persist: %s", working)
        return

    mode = backend.backend_mode()
    segment = _user_segment(user_id)
    try:
        # Always mirror to session_storage durable path (local disk or mount).
        _persist_to_mount(working, durable_user_db_path(user_id))
        if mode == "s3":
            _persist_to_s3(working, s3_key=backend.user_db_s3_key(segment))
    except Exception:
        logger.exception("Failed to persist user DB for %s (%s)", user_id, mode)


def persist_tasks_db(*, force: bool = False, user_id: str | None = None) -> None:
    """Flush working SQLite DB(s) to durable storage.

    - ``user_id`` set: persist that user DB only.
    - ``user_id`` None and force: persist global + all dirty users.
    """
    with _persist_lock:
        users: Iterable[str]
        if user_id is not None:
            users = (user_id,)
            do_global = False
        else:
            users = list(_dirty_users)
            do_global = force or _global_dirty

        if do_global:
            _persist_global(force=True)

        for uid in users:
            _persist_user(uid)
            _dirty_users.discard(uid)


def _start_persist_timer_locked() -> None:
    """Caller must hold ``_persist_lock``."""
    global _persist_timer

    def _run() -> None:
        persist_tasks_db(force=True)

    if _persist_timer is not None:
        _persist_timer.cancel()
    _persist_timer = threading.Timer(_PERSIST_DEBOUNCE_SECONDS, _run)
    _persist_timer.daemon = True
    _persist_timer.start()


def schedule_persist(user_id: str | None = None) -> None:
    """Debounced persist after mutations. ``user_id=None`` marks global DB dirty."""
    global _global_dirty

    with _persist_lock:
        if user_id is None:
            if backend.backend_mode() != "local":
                _global_dirty = True
            elif not _dirty_users:
                return
        else:
            _dirty_users.add(user_id)

        if not _global_dirty and not _dirty_users:
            return
        _start_persist_timer_locked()


def flush_persist(user_id: str | None = None) -> None:
    """Cancel pending debounce and persist immediately.

    - ``user_id`` set: flush that user immediately; reschedule if others remain dirty.
    - ``user_id`` None: flush global and all dirty users.
    """
    global _persist_timer

    with _persist_lock:
        if _persist_timer is not None:
            _persist_timer.cancel()
            _persist_timer = None

    if user_id is not None:
        persist_tasks_db(force=True, user_id=user_id)
        with _persist_lock:
            if _global_dirty or _dirty_users:
                _start_persist_timer_locked()
        return

    persist_tasks_db(force=True)
