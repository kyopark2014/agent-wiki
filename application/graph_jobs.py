"""Background knowledge-graph pipeline jobs triggered after session confirm."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("graph_jobs")

_APPLICATION_DIR = Path(__file__).resolve().parent
_GRAPH_DIR = _APPLICATION_DIR.parent / "graph"
_DEFAULT_COOLDOWN = 600

_lock = threading.Lock()
_pipeline_lock = threading.Lock()
_running_users: set[str] = set()
_states: dict[str, "GraphJobState"] = {}


def _cooldown_seconds() -> int:
    raw = os.environ.get("GRAPH_JOB_COOLDOWN_SECONDS", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return _DEFAULT_COOLDOWN


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GraphJobState:
    user_id: str
    status: str = "idle"  # idle|queued|running|ready|error|skipped_cooldown
    error: str | None = None
    last_success_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        cooldown = _cooldown_seconds()
        next_eligible: str | None = None
        if self.last_success_at is not None and cooldown > 0:
            next_eligible = (
                self.last_success_at + timedelta(seconds=cooldown)
            ).isoformat()
        return {
            "user_id": self.user_id,
            "status": self.status,
            "error": self.error,
            "last_success_at": (
                self.last_success_at.isoformat() if self.last_success_at else None
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "cooldown_seconds": cooldown,
            "next_eligible_at": next_eligible,
        }


def _get_or_create(user_id: str) -> GraphJobState:
    state = _states.get(user_id)
    if state is None:
        state = GraphJobState(user_id=user_id)
        _states[user_id] = state
    return state


def get_job_status(user_id: str) -> dict[str, Any]:
    with _lock:
        return _get_or_create(user_id).to_dict()


def _in_cooldown(state: GraphJobState) -> bool:
    cooldown = _cooldown_seconds()
    if cooldown <= 0 or state.last_success_at is None:
        return False
    return (_now() - state.last_success_at) < timedelta(seconds=cooldown)


def ensure_graph_job(user_id: str, *, force: bool = False) -> dict[str, Any]:
    """Start a background pipeline for user_id unless running or in cooldown.

    Returns the current job status dict. Never blocks on the pipeline itself.
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return {"status": "idle", "error": "missing user_id"}

    with _lock:
        state = _get_or_create(user_id)
        if user_id in _running_users or state.status in ("running", "queued"):
            logger.info("Graph job already running for %s — skip", user_id)
            return state.to_dict()

        if not force and _in_cooldown(state):
            state.status = "skipped_cooldown"
            state.updated_at = _now()
            logger.info(
                "Graph job cooldown active for %s (last_success=%s, cooldown=%ss) — skip",
                user_id,
                state.last_success_at.isoformat() if state.last_success_at else None,
                _cooldown_seconds(),
            )
            return state.to_dict()

        state.status = "queued"
        state.error = None
        state.started_at = _now()
        state.finished_at = None
        state.updated_at = state.started_at
        _running_users.add(user_id)

    thread = threading.Thread(
        target=_run_pipeline,
        args=(user_id,),
        name=f"graph-job-{user_id[:32]}",
        daemon=True,
    )
    thread.start()
    return get_job_status(user_id)


def _run_pipeline(user_id: str) -> None:
    with _lock:
        state = _get_or_create(user_id)
        state.status = "running"
        state.updated_at = _now()

    logger.info("Graph pipeline starting for user=%s", user_id)
    try:
        # Ensure session-storage workspace exists before the CLI configures env dirs.
        try:
            from application import utils

            utils.ensure_user_graph_dir(user_id)
        except Exception:
            logger.exception("Could not ensure user graph dir for %s", user_id)

        with _pipeline_lock:
            cmd = [
                sys.executable,
                "run_pipeline.py",
                "--user",
                user_id,
            ]
            logger.info("+ %s (cwd=%s)", " ".join(cmd), _GRAPH_DIR)
            subprocess.check_call(cmd, cwd=str(_GRAPH_DIR))
        with _lock:
            state = _get_or_create(user_id)
            now = _now()
            state.status = "ready"
            state.error = None
            state.last_success_at = now
            state.finished_at = now
            state.updated_at = now
            _running_users.discard(user_id)
        logger.info("Graph pipeline ready for user=%s", user_id)
    except Exception as exc:
        with _lock:
            state = _get_or_create(user_id)
            now = _now()
            state.status = "error"
            state.error = str(exc)[:500]
            state.finished_at = now
            state.updated_at = now
            # Failures do not set last_success_at — retries allowed immediately.
            _running_users.discard(user_id)
        logger.exception("Graph pipeline failed for user=%s", user_id)
