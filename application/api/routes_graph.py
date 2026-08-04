"""Serve per-user knowledge graph HTML from graph/out/."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from application.api.routes_auth import require_user_id

router = APIRouter(prefix="/api/graph", tags=["graph"])

_APPLICATION_DIR = Path(__file__).resolve().parents[1]
_GRAPH_OUT_DIR = _APPLICATION_DIR.parent / "graph" / "out"


def safe_slug(raw: str, *, max_len: int = 48) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw or "user")[:max_len].strip("_")
    if cleaned:
        return cleaned
    digest = hashlib.sha1((raw or "user").encode("utf-8")).hexdigest()[:12]
    return f"user_{digest}"


def user_graph_html_path(user_id: str) -> Path:
    return _GRAPH_OUT_DIR / f"graph_{safe_slug(user_id)}.html"


@router.get("/status")
def graph_status(request: Request) -> dict:
    user_id = require_user_id(request)
    path = user_graph_html_path(user_id)
    return {
        "user_id": user_id,
        "exists": path.is_file(),
        "path": path.name if path.is_file() else None,
    }


@router.get("")
def get_user_graph(request: Request):
    """Open the logged-in user's knowledge graph (graph/out/graph_{user}.html)."""
    user_id = require_user_id(request)
    path = user_graph_html_path(user_id)
    if not path.is_file():
        return HTMLResponse(
            "<!doctype html><html lang='ko'><head><meta charset='UTF-8' />"
            f"<title>Knowledge Graph — {user_id}</title></head><body style='"
            "font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;"
            "padding:48px;max-width:640px;margin:0 auto;'>"
            f"<h1>Knowledge Graph 없음</h1>"
            f"<p>사용자 <b>{user_id}</b> 용 그래프 파일이 아직 없습니다.</p>"
            "<p><code>cd graph && python run_pipeline.py --user "
            f"{user_id}</code> 로 생성한 뒤 다시 열어 주세요.</p>"
            "</body></html>",
            status_code=404,
        )
    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            # filename= 을 주면 attachment로 내려받아짐 → 브라우저에서 바로 표시
            "Content-Disposition": "inline",
        },
    )
