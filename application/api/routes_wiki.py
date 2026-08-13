"""Serve Wiki knowledge graph from per-user ``.session_storage/{user}/wiki``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from application.api.routes_auth import require_user_id
from application.graph_query import query_user_graph
from application.wiki_jobs import (
    ensure_wiki_graph_html_current,
    ensure_wiki_sync,
    get_wiki_job_status,
    republish_wiki_graph_html,
)
from application import utils

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


def wiki_graph_html_path(user_id: str) -> Path:
    return Path(utils.wiki_graph_html_path(user_id))


def wiki_graph_json_path(user_id: str) -> Path:
    return Path(utils.wiki_graph_json_path(user_id))


class WikiQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    mode: Literal["bfs", "dfs"] = "bfs"
    budget: int = Field(2000, ge=200, le=8000)


class WikiPatternPatch(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=32)


class WikiSourcesPut(BaseModel):
    folders: list[str] = Field(default_factory=list, max_length=3)


class WikiUrlIngest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


@router.get("/status")
def wiki_status(request: Request) -> dict:
    user_id = require_user_id(request)
    json_path = wiki_graph_json_path(user_id)
    path = wiki_graph_html_path(user_id)
    job = get_wiki_job_status(user_id)
    exists = json_path.is_file()
    status = job.get("status") or "idle"
    if status in ("idle", "unchanged") and exists:
        status = "ready"
    sources = utils.get_wiki_source_folders(user_id)
    urls = utils.get_wiki_source_urls(user_id)
    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "sources": sources,
        "urls": urls,
        "max_sources": utils.MAX_WIKI_SOURCE_FOLDERS,
        "exists": exists,
        "path": path.name if path.is_file() else None,
        "storage": str(path.parent),
        "status": status,
        "pattern": utils.get_wiki_graph_pattern(user_id),
        "error": job.get("error"),
        "message": job.get("message"),
        "last_success_at": job.get("last_success_at"),
    }


@router.get("/sources")
def get_wiki_sources(request: Request) -> dict:
    user_id = require_user_id(request)
    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "folders": utils.get_wiki_source_folders(user_id),
        "urls": utils.get_wiki_source_urls(user_id),
        "max_sources": utils.MAX_WIKI_SOURCE_FOLDERS,
    }


@router.put("/sources")
def put_wiki_sources(body: WikiSourcesPut, request: Request) -> dict:
    """Save up to 3 Wiki Sync source folders (URL history is preserved)."""
    user_id = require_user_id(request)
    try:
        saved = utils.set_wiki_sources(
            folders=list(body.folders or []), user_id=user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Wiki 소스 저장 실패: {exc}",
        ) from exc
    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "folders": saved["folders"],
        "urls": saved["urls"],
        "max_sources": utils.MAX_WIKI_SOURCE_FOLDERS,
    }


@router.get("/browse")
def browse_wiki_sources(
    request: Request,
    path: str | None = Query(None),
) -> dict:
    """List directories for the Configure source picker menu."""
    user_id = require_user_id(request)
    try:
        return utils.browse_wiki_source_dirs(path, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"폴더 목록 조회 실패: {exc}",
        ) from exc


@router.post("/urls")
def ingest_wiki_url(body: WikiUrlIngest, request: Request) -> dict:
    """Fetch one URL into the user's ``{wiki}/raw`` and append URL history."""
    user_id = require_user_id(request)
    try:
        result = utils.ingest_wiki_url(body.url, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"URL 수집 실패: {exc}",
        ) from exc
    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "url": result["url"],
        "path": result["path"],
        "urls": result["urls"],
        "folders": utils.get_wiki_source_folders(user_id),
        "max_sources": utils.MAX_WIKI_SOURCE_FOLDERS,
    }


@router.post("/sync")
def sync_wiki(request: Request, full: bool = Query(False)) -> dict:
    """Enqueue graphify sync for the user's wiki directory."""
    user_id = require_user_id(request)
    utils.ensure_user_wiki_dir(user_id)
    job = ensure_wiki_sync(user_id, full=full)
    path = wiki_graph_html_path(user_id)
    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "exists": wiki_graph_json_path(user_id).is_file(),
        "path": path.name if path.is_file() else None,
        "storage": str(path.parent),
        "pattern": utils.get_wiki_graph_pattern(user_id),
        **job,
    }


@router.patch("/pattern")
def patch_wiki_pattern(body: WikiPatternPatch, request: Request) -> dict:
    """Switch Wiki Graph view pattern (Force Atlas / Neo4j Explore / Holistic)."""
    user_id = require_user_id(request)
    if not wiki_graph_json_path(user_id).is_file():
        raise HTTPException(
            status_code=404,
            detail="Wiki 그래프가 아직 없습니다. Settings → Wiki → Sync를 실행하세요.",
        )
    pid = utils.set_wiki_graph_pattern(body.pattern, user_id=user_id)
    try:
        ok = republish_wiki_graph_html(user_id, pattern=pid)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Wiki 그래프 패턴 전환 실패: {exc}",
        ) from exc
    if not ok:
        raise HTTPException(
            status_code=500,
            detail="Wiki 그래프 HTML을 생성하지 못했습니다.",
        )
    path = wiki_graph_html_path(user_id)
    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "exists": True,
        "path": path.name if path.is_file() else None,
        "pattern": pid,
        "status": "ready",
    }


@router.get("/graph")
def get_wiki_graph(request: Request):
    """Open Wiki knowledge graph with pattern UI (search + 3 view types)."""
    user_id = require_user_id(request)
    json_path = wiki_graph_json_path(user_id)
    if not json_path.is_file():
        job = get_wiki_job_status(user_id)
        status = job.get("status") or "idle"
        if status in ("queued", "running"):
            detail = "Wiki 그래프를 동기화하는 중입니다. 잠시 후 다시 열어 주세요."
        elif status == "error":
            detail = f"Wiki 동기화에 실패했습니다: {job.get('error') or 'unknown error'}"
        else:
            detail = (
                "Wiki 그래프가 아직 없습니다. Settings → Wiki → Sync로 "
                "먼저 동기화하세요."
            )
        return HTMLResponse(
            "<!doctype html><html lang='ko'><head><meta charset='UTF-8' />"
            "<title>Wiki Graph</title></head><body style='"
            "font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;"
            "padding:48px;max-width:640px;margin:0 auto;'>"
            "<h1>Wiki Graph 없음</h1>"
            f"<p>{detail}</p>"
            f"<p style='color:#8b949e;font-size:13px;'>경로: "
            f"{utils.get_user_wiki_dir(user_id)}</p>"
            "</body></html>",
            status_code=404,
        )

    path = ensure_wiki_graph_html_current(user_id)
    if path is None or not path.is_file():
        try:
            republish_wiki_graph_html(user_id)
            path = wiki_graph_html_path(user_id)
        except Exception as exc:
            return HTMLResponse(
                "<!doctype html><html lang='ko'><head><meta charset='UTF-8' />"
                "<title>Wiki Graph</title></head><body style='"
                "font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;"
                "padding:48px;max-width:640px;margin:0 auto;'>"
                "<h1>Wiki Graph 렌더 실패</h1>"
                f"<p>{exc}</p>"
                "</body></html>",
                status_code=500,
            )

    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
        },
    )


@router.post("/query")
def query_wiki_graph(body: WikiQueryRequest, request: Request) -> dict:
    """BFS/DFS traversal over the user's wiki graph.json."""
    user_id = require_user_id(request)
    graph_json = wiki_graph_json_path(user_id)
    if not graph_json.is_file():
        raise HTTPException(
            status_code=404,
            detail="Wiki 그래프가 아직 없습니다. Settings → Wiki → Sync를 실행하세요.",
        )
    wiki_root = Path(utils.get_user_wiki_dir(user_id))
    allowed = [wiki_root, wiki_root / "raw", wiki_root / "graphify-out"]
    for src in utils.get_wiki_source_folders(user_id):
        allowed.append(Path(src))
    try:
        return query_user_graph(
            graph_json,
            body.question,
            mode=body.mode,
            budget=body.budget,
            allowed_roots=allowed,
            use_embeddings=utils.is_hybrid_graph_search_enabled(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"wiki query failed: {exc}",
        ) from exc
