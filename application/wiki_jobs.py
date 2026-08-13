"""Background wiki graph sync jobs (per-user under .session_storage/{user}/wiki).

Sync runs in a detached subprocess so closing the Wiki Graph modal (or the
browser tab) does not cancel the job. Status is also persisted to disk.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("wiki_jobs")

_APPLICATION_DIR = Path(__file__).resolve().parent
_GRAPH_DIR = _APPLICATION_DIR.parent / "graph"
_SYNC_SCRIPT = (
    _APPLICATION_DIR / "skills" / "graphify" / "scripts" / "sync_wiki.py"
)

_lock = threading.Lock()
_running_users: set[str] = set()
_states: dict[str, "WikiJobState"] = {}
_active_procs: dict[str, subprocess.Popen[str]] = {}

_GRAPH_HTML_CURRENT_MARKER = 'data-doc-search="1"'
_STATUS_NAME = ".wiki_sync_status.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status_path(user_id: str) -> Path:
    from application import utils

    return Path(utils.wiki_graphify_out_dir(user_id)) / _STATUS_NAME


def _persist_state(user_id: str, state: "WikiJobState") -> None:
    try:
        path = _status_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        logger.exception("Failed to persist wiki sync status user=%s", user_id)


def _load_persisted_state(user_id: str) -> dict[str, Any] | None:
    path = _status_path(user_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class WikiJobState:
    user_id: str
    status: str = "idle"  # idle|queued|running|ready|error|unchanged
    error: str | None = None
    last_success_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=_now)
    message: str | None = None
    pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "status": self.status,
            "error": self.error,
            "message": self.message,
            "pid": self.pid,
            "last_success_at": (
                self.last_success_at.isoformat() if self.last_success_at else None
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_or_create(user_id: str) -> WikiJobState:
    state = _states.get(user_id)
    if state is None:
        state = WikiJobState(user_id=user_id)
        persisted = _load_persisted_state(user_id)
        if persisted:
            state.status = str(persisted.get("status") or "idle")
            state.error = persisted.get("error")  # type: ignore[assignment]
            state.message = persisted.get("message")  # type: ignore[assignment]
            state.pid = persisted.get("pid")  # type: ignore[assignment]
            state.last_success_at = _parse_iso(persisted.get("last_success_at"))
            state.started_at = _parse_iso(persisted.get("started_at"))
            state.finished_at = _parse_iso(persisted.get("finished_at"))
            if state.status in ("queued", "running") and state.pid:
                if not _pid_alive(int(state.pid)):
                    state.status = "error"
                    state.error = (
                        "Wiki sync process ended unexpectedly (server restart)."
                    )
                    state.finished_at = _now()
                    state.pid = None
            elif state.status in ("queued", "running"):
                state.status = "idle"
                state.pid = None
        _states[user_id] = state
    return state


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def get_wiki_job_status(user_id: str) -> dict[str, Any]:
    with _lock:
        state = _get_or_create(user_id)
        if (
            state.status in ("queued", "running")
            and state.pid
            and user_id not in _running_users
        ):
            if not _pid_alive(int(state.pid)):
                state.status = "error"
                state.error = state.error or "Wiki sync process ended unexpectedly."
                state.finished_at = _now()
                state.updated_at = state.finished_at
                state.pid = None
                _persist_state(user_id, state)
        return state.to_dict()


def ensure_wiki_sync(user_id: str, *, full: bool = False) -> dict[str, Any]:
    """Enqueue a background wiki sync for ``user_id`` unless already running."""
    with _lock:
        state = _get_or_create(user_id)
        if user_id in _running_users or state.status in ("queued", "running"):
            if state.pid and _pid_alive(int(state.pid)):
                logger.info(
                    "Wiki sync already running user=%s pid=%s — skip",
                    user_id,
                    state.pid,
                )
                return state.to_dict()
            _running_users.discard(user_id)
            state.status = "idle"
            state.pid = None

        state.status = "queued"
        state.error = None
        state.message = "Wiki 동기화를 백그라운드에서 시작합니다."
        state.started_at = _now()
        state.finished_at = None
        state.updated_at = state.started_at
        state.pid = None
        _running_users.add(user_id)
        _persist_state(user_id, state)

    thread = threading.Thread(
        target=_run_sync,
        args=(user_id, full),
        name=f"wiki-sync-{user_id}",
        daemon=True,
    )
    thread.start()
    return get_wiki_job_status(user_id)


def _is_sync_progress_line(text: str) -> bool:
    """Skip noisy library warnings; keep brief sync milestones for logs/UI."""
    if not text:
        return False
    noisy_prefixes = (
        "Ignoring wrong pointing object",
        "Multiple definitions in dictionary",
        "Advanced encoding",
        "Wrong pointing object",
    )
    if any(text.startswith(p) or p in text for p in noisy_prefixes):
        return False
    if text.startswith("{") or text.startswith("}") or text.startswith('"'):
        return False
    return True


def _sync_error_tail(stdout: str, returncode: int) -> str:
    """Prefer the last meaningful sync lines over PDF library noise."""
    if not stdout:
        return f"sync failed (exit {returncode})"
    lines = [
        ln.strip()
        for ln in stdout.splitlines()
        if ln.strip() and _is_sync_progress_line(ln.strip())
    ]
    if lines:
        return "\n".join(lines[-12:])[-500:]
    return stdout[-500:]


def _run_sync(user_id: str, full: bool) -> None:
    with _lock:
        state = _get_or_create(user_id)
        state.status = "running"
        state.updated_at = _now()
        state.message = "Wiki 동기화 실행 중…"
        _persist_state(user_id, state)

    logger.info(
        "Wiki sync starting user=%s full=%s script=%s",
        user_id,
        full,
        _SYNC_SCRIPT,
    )
    proc: subprocess.Popen[str] | None = None
    try:
        from application import utils

        utils.ensure_user_wiki_dir(user_id)
        if not _SYNC_SCRIPT.is_file():
            raise FileNotFoundError(f"sync script not found: {_SYNC_SCRIPT}")
        cmd = [sys.executable, "-u", str(_SYNC_SCRIPT), "--user", user_id]
        if full:
            cmd.append("--full")
        logger.info("+ %s (detached)", " ".join(cmd))

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        popen_kwargs: dict[str, Any] = {
            "cwd": str(_APPLICATION_DIR.parent),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "start_new_session": True,
            "env": env,
            "bufsize": 1,
        }
        proc = subprocess.Popen(cmd, **popen_kwargs)
        with _lock:
            _active_procs[user_id] = proc
            state = _get_or_create(user_id)
            state.pid = proc.pid
            state.updated_at = _now()
            _persist_state(user_id, state)
        logger.info("Wiki sync subprocess user=%s pid=%s", user_id, proc.pid)

        assert proc.stdout is not None
        chunks: list[str] = []
        for line in proc.stdout:
            chunks.append(line)
            if len(chunks) > 200:
                chunks = chunks[-100:]
            text = line.strip()
            if text and _is_sync_progress_line(text):
                logger.info("[wiki sync][%s] %s", user_id, text[:300])
                with _lock:
                    state = _get_or_create(user_id)
                    state.message = text[:240]
                    state.updated_at = _now()
                    _persist_state(user_id, state)
        returncode = proc.wait()
        stdout = "".join(chunks).strip()

        if returncode != 0:
            err = _sync_error_tail(stdout, returncode)
            raise RuntimeError(err)

        unchanged = "Nothing to update" in stdout or '"status": "unchanged"' in stdout
        try:
            logger.info("Wiki sync republishing app-graph.html user=%s…", user_id)
            republish_wiki_graph_html(user_id)
        except Exception:
            logger.exception(
                "Wiki pattern HTML republish after sync failed user=%s", user_id
            )
        with _lock:
            state = _get_or_create(user_id)
            now = _now()
            state.status = "unchanged" if unchanged else "ready"
            state.error = None
            state.message = (
                "변경된 파일이 없습니다."
                if unchanged
                else "Wiki 동기화가 완료되었습니다."
            )
            if stdout:
                state.message = (state.message + " " + stdout[-300:]).strip()
            state.last_success_at = now
            state.finished_at = now
            state.updated_at = now
            state.pid = None
            _running_users.discard(user_id)
            _active_procs.pop(user_id, None)
            _persist_state(user_id, state)
        logger.info("Wiki sync finished user=%s status=%s", user_id, state.status)
    except Exception as exc:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.terminate()
                except Exception:
                    pass
        with _lock:
            state = _get_or_create(user_id)
            now = _now()
            state.status = "error"
            state.error = str(exc)[:500]
            state.message = state.error
            state.finished_at = now
            state.updated_at = now
            state.pid = None
            _running_users.discard(user_id)
            _active_procs.pop(user_id, None)
            _persist_state(user_id, state)
        logger.exception("Wiki sync failed user=%s", user_id)


def republish_wiki_graph_html(
    user_id: str, *, pattern: str | None = None
) -> bool:
    """Render pattern UI HTML (app-graph.html) from the user's wiki graph.json."""
    from application import utils

    out_dir = Path(utils.wiki_graphify_out_dir(user_id))
    graph_root = str(_GRAPH_DIR)
    if graph_root not in sys.path:
        sys.path.insert(0, graph_root)

    from lib.out_graphs import republish_html_from_json

    pid = pattern or utils.get_wiki_graph_pattern(user_id)
    if pattern:
        utils.set_wiki_graph_pattern(pid, user_id=user_id)

    written = republish_html_from_json(
        out_dir,
        pattern=pid,
        html_name="app-graph.html",
        title="Wiki Graph",
        subtitle=(
            "Wiki 지식 그래프 · 노드 클릭 시 출처·관계 상세를 볼 수 있습니다."
        ),
        query_url="/api/wiki/query",
    )
    if written is None:
        logger.info(
            "No wiki graph.json to republish user=%s pattern=%s", user_id, pid
        )
        return False
    logger.info(
        "Republished wiki graph HTML user=%s pattern=%s → %s",
        user_id,
        pid,
        written,
    )
    return True


def ensure_wiki_graph_html_current(user_id: str) -> Path | None:
    """Ensure app-graph.html exists with search UI for the current pattern."""
    from application import utils

    json_path = Path(utils.wiki_graph_json_path(user_id))
    if not json_path.is_file():
        return None
    html_path = Path(utils.wiki_graph_html_path(user_id))
    pid = utils.get_wiki_graph_pattern(user_id)
    need = True
    if html_path.is_file():
        try:
            sample = html_path.read_text(encoding="utf-8", errors="ignore")
            has_search = _GRAPH_HTML_CURRENT_MARKER in sample
            active_ok = (
                f'class="ctrl-btn pattern-btn active" data-pattern="{pid}"' in sample
            )
            stale_json = html_path.stat().st_mtime < json_path.stat().st_mtime
            need = (not has_search) or (not active_ok) or stale_json
        except OSError:
            need = True
    if need:
        try:
            republish_wiki_graph_html(user_id, pattern=pid)
        except Exception:
            logger.exception("Failed to ensure wiki graph HTML user=%s", user_id)
            return html_path if html_path.is_file() else None
    return html_path if html_path.is_file() else None
