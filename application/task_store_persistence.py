"""Persist tasks.db via S3 Files using the working-copy + restore/persist pattern."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading

logger = logging.getLogger("task_store_persistence")

_APPLICATION_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORKING_DIR = os.path.join(_APPLICATION_DIR, "data")
_DEFAULT_MOUNT = "/mnt/app-data"
_APP_DATABASE_SEGMENT = "application-database"
_PERSIST_DEBOUNCE_SECONDS = 20.0

_persist_lock = threading.Lock()
_persist_timer: threading.Timer | None = None
_persist_dirty = False


def _load_project_name() -> str:
    env_name = os.environ.get("TASK_DB_PROJECT", "").strip()
    if env_name:
        return env_name

    config_json = os.environ.get("APP_CONFIG_JSON", "").strip()
    if config_json:
        try:
            project = json.loads(config_json).get("projectName")
            if isinstance(project, str) and project.strip():
                return project.strip()
        except json.JSONDecodeError:
            pass

    config_path = os.path.join(_APPLICATION_DIR, "config.json")
    try:
        with open(config_path, encoding="utf-8") as handle:
            project = json.load(handle).get("projectName")
            if isinstance(project, str) and project.strip():
                return project.strip()
    except (OSError, json.JSONDecodeError):
        pass

    return "agentic-work"


def mount_dir() -> str:
    return os.environ.get("TASK_DB_MOUNT", _DEFAULT_MOUNT).strip() or _DEFAULT_MOUNT


def persistence_enabled() -> bool:
    path = mount_dir()
    return os.path.isdir(path) and os.access(path, os.W_OK)


def working_db_path() -> str:
    custom = os.environ.get("TASK_DB_WORKING_PATH", "").strip()
    if custom:
        return custom
    return os.path.join(_DEFAULT_WORKING_DIR, "tasks.db")


def persistent_db_path() -> str:
    project_name = _load_project_name()
    return os.path.join(
        mount_dir(),
        _APP_DATABASE_SEGMENT,
        project_name,
        "tasks.db",
    )


def _db_ready(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0


def _copy_db_files(source: str, destination: str) -> None:
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source, destination)
    for suffix in ("-wal", "-shm"):
        src = source + suffix
        dst = destination + suffix
        if os.path.isfile(src):
            shutil.copy2(src, dst)
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


def restore_tasks_db() -> None:
    """Prepare working tasks.db from S3 Files or start fresh when persistence is enabled."""
    working = working_db_path()
    persistent = persistent_db_path()
    if not persistence_enabled():
        logger.info("Task DB persistence disabled (no writable mount at %s)", mount_dir())
        return

    os.makedirs(os.path.dirname(working), exist_ok=True)

    if _db_ready(persistent):
        _remove_db_files(working)
        _copy_db_files(persistent, working)
        logger.info("Restored task DB from S3 Files: %s -> %s", persistent, working)
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


def persist_tasks_db(*, force: bool = False) -> None:
    """Flush the working SQLite DB to the S3 Files mount."""
    global _persist_dirty

    if not persistence_enabled():
        return

    working = working_db_path()
    persistent = persistent_db_path()

    with _persist_lock:
        if not force and not _persist_dirty:
            return
        if not _db_ready(working):
            logger.warning("Working task DB missing, skip persist: %s", working)
            _persist_dirty = False
            return

        try:
            _checkpoint_sqlite(working)
            _copy_db_files(working, persistent)
            _persist_dirty = False
            logger.info("Persisted task DB to S3 Files: %s -> %s", working, persistent)
        except Exception:
            logger.exception("Failed to persist task DB to %s", persistent)


def schedule_persist() -> None:
    """Debounced persist after task/message mutations."""
    global _persist_timer, _persist_dirty

    if not persistence_enabled():
        return

    _persist_dirty = True

    def _run() -> None:
        persist_tasks_db(force=True)

    with _persist_lock:
        if _persist_timer is not None:
            _persist_timer.cancel()
        _persist_timer = threading.Timer(_PERSIST_DEBOUNCE_SECONDS, _run)
        _persist_timer.daemon = True
        _persist_timer.start()


def flush_persist() -> None:
    """Cancel pending debounce and persist immediately."""
    global _persist_timer

    with _persist_lock:
        if _persist_timer is not None:
            _persist_timer.cancel()
            _persist_timer = None
    persist_tasks_db(force=True)
