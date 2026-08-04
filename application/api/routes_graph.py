"""Serve per-user knowledge graph HTML from session storage."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from application.api.routes_auth import require_user_id
from application.graph_jobs import ensure_graph_job, get_job_status
from application import utils

router = APIRouter(prefix="/api/graph", tags=["graph"])


def user_graph_html_path(user_id: str) -> Path:
    """Session storage only: …/{user}/graph/out/graph.html"""
    return Path(utils.user_graph_html_path(user_id))


@router.get("/status")
def graph_status(request: Request) -> dict:
    user_id = require_user_id(request)
    enabled = utils.is_knowledge_graph_enabled(user_id)
    path = user_graph_html_path(user_id)
    job = get_job_status(user_id)
    exists = path.is_file()
    status = job.get("status") or "idle"
    if not enabled:
        status = "disabled"
    elif status in ("idle", "skipped_cooldown", "skipped_unchanged") and exists:
        status = "ready" if status in ("idle", "skipped_unchanged") else status
    return {
        "user_id": user_id,
        "exists": exists,
        "path": path.name if exists else None,
        "storage": str(path.parent),
        "status": status,
        "enabled": enabled,
        "error": job.get("error"),
        "last_success_at": job.get("last_success_at"),
        "cooldown_seconds": job.get("cooldown_seconds"),
        "next_eligible_at": job.get("next_eligible_at"),
    }


@router.post("/rebuild")
def rebuild_graph(request: Request, force: bool = Query(False)) -> dict:
    """Enqueue a background pipeline (respects cooldown unless force=true)."""
    user_id = require_user_id(request)
    if not utils.is_knowledge_graph_enabled(user_id):
        raise HTTPException(
            status_code=403,
            detail="Knowledge Graph is disabled in Settings",
        )
    job = ensure_graph_job(user_id, force=force)
    path = user_graph_html_path(user_id)
    return {
        "user_id": user_id,
        "exists": path.is_file(),
        "path": path.name if path.is_file() else None,
        "storage": str(path.parent),
        "enabled": True,
        **job,
    }


@router.get("")
def get_user_graph(request: Request):
    """Open the logged-in user's knowledge graph from session storage."""
    user_id = require_user_id(request)
    path = user_graph_html_path(user_id)
    if not path.is_file():
        job = get_job_status(user_id)
        status = job.get("status") or "idle"
        if status in ("queued", "running"):
            detail = "지식 그래프를 백그라운드에서 생성 중입니다. 잠시 후 다시 열어 주세요."
        elif status == "error":
            detail = f"그래프 생성에 실패했습니다: {job.get('error') or 'unknown error'}"
        else:
            detail = "사용자 그래프 정보가 아직 없습니다. 잠시후 다시 시도하세요"
        return HTMLResponse(
            "<!doctype html><html lang='ko'><head><meta charset='UTF-8' />"
            f"<title>Knowledge Graph — {user_id}</title></head><body style='"
            "font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;"
            "padding:48px;max-width:640px;margin:0 auto;'>"
            f"<h1>Knowledge Graph 없음</h1>"
            f"<p>{detail}</p>"
            "</body></html>",
            status_code=404,
        )
    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
        },
    )
