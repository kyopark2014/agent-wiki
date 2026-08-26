"""Serve Wiki knowledge graph from per-user ``.session_storage/{user}/wiki``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
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

# Multipart /api/wiki/raw still caps at ~ALB body size; prefer /raw/presign for large files.
_MAX_RAW_UPLOAD_BYTES = 80 * 1024 * 1024  # 80 MiB per file (multipart only)
_MAX_RAW_PRESIGN_BYTES = 5 * 1024 * 1024 * 1024  # 5 GiB (S3 single PUT)
_MAX_RAW_UPLOAD_FILES = 30


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
    foundation_model_parser_enabled: bool | None = None


class WikiUrlIngest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class WikiRawPresignRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    size: int | None = Field(default=None, ge=0)
    content_type: str | None = None


class WikiRawCompleteRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    s3_key: str = Field(..., min_length=1)
    size: int | None = Field(default=None, ge=0)


def _assert_wiki_presign_size(size: int | None) -> None:
    if size is None:
        return
    if size < 0:
        raise HTTPException(status_code=400, detail="Invalid file size")
    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size > _MAX_RAW_PRESIGN_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File exceeds the 5 GiB upload limit",
        )


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
        "foundation_model_parser_enabled": utils.is_foundation_model_parser_enabled(
            user_id
        ),
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
        "foundation_model_parser_enabled": utils.is_foundation_model_parser_enabled(
            user_id
        ),
    }


@router.put("/sources")
def put_wiki_sources(body: WikiSourcesPut, request: Request) -> dict:
    """Save up to 3 Wiki Sync source folders (URL history is preserved)."""
    user_id = require_user_id(request)
    try:
        saved = utils.set_wiki_sources(
            folders=list(body.folders or []), user_id=user_id
        )
        if body.foundation_model_parser_enabled is not None:
            utils.set_foundation_model_parser_enabled(
                bool(body.foundation_model_parser_enabled),
                user_id=user_id,
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
        "foundation_model_parser_enabled": utils.is_foundation_model_parser_enabled(
            user_id
        ),
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


@router.post("/raw/presign")
def wiki_raw_presign(request: Request, body: WikiRawPresignRequest) -> dict:
    """Return a short-lived S3 PUT URL so the browser can upload past ECS body limits."""
    user_id = require_user_id(request)
    _assert_wiki_presign_size(body.size)
    name = (body.file_name or "").strip() or "upload.bin"
    try:
        presign = utils.generate_wiki_raw_presigned_put(name, user_id=user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"업로드 URL 생성 실패: {exc}",
        ) from exc
    if not presign or not presign.get("upload_url"):
        raise HTTPException(status_code=500, detail="업로드 URL 생성 실패")
    return {
        "ok": True,
        "file_name": presign["file_name"],
        "s3_key": presign["s3_key"],
        "content_type": presign.get("content_type"),
        "upload_url": presign["upload_url"],
        "headers": presign.get("headers") or {},
        "expires_in": presign.get("expires_in"),
    }


@router.post("/raw/complete")
def wiki_raw_complete(request: Request, body: WikiRawCompleteRequest) -> dict:
    """Confirm a presigned PUT and copy the object into local ``{wiki}/raw``."""
    user_id = require_user_id(request)
    _assert_wiki_presign_size(body.size)
    try:
        result = utils.save_wiki_raw_from_s3(
            file_name=body.file_name,
            s3_key=body.s3_key,
            user_id=user_id,
            expected_size=body.size,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"문서 저장 실패: {exc}",
        ) from exc

    return {
        "wiki_dir": result["wiki_dir"],
        "raw_dir": result["raw_dir"],
        "saved": result["saved"],
        "count": result["count"],
        "files": result.get("files") or utils.get_wiki_source_files(user_id),
    }


@router.post("/raw")
async def upload_wiki_raw_files(
    request: Request,
    files: list[UploadFile] = File(...),
) -> dict:
    """Copy uploaded documents into the user's ``{wiki}/raw`` for later Sync.

    Prefer ``/raw/presign`` + browser PUT for large files (>~80MB) so the body
    does not traverse ECS/ALB.
    """
    user_id = require_user_id(request)
    if not files:
        raise HTTPException(status_code=400, detail="업로드할 파일이 없습니다.")
    if len(files) > _MAX_RAW_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"한 번에 최대 {_MAX_RAW_UPLOAD_FILES}개까지 업로드할 수 있습니다.",
        )

    payloads: list[tuple[str, bytes]] = []
    try:
        for upload in files:
            name = (upload.filename or "").strip() or "upload.bin"
            data = await upload.read()
            if not data:
                continue
            if len(data) > _MAX_RAW_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"파일이 너무 큽니다: {name} "
                        f"(최대 {_MAX_RAW_UPLOAD_BYTES // (1024 * 1024)}MB). "
                        "대용량은 presigned 업로드를 사용하세요."
                    ),
                )
            payloads.append((name, data))
    finally:
        for upload in files:
            try:
                await upload.close()
            except Exception:
                pass

    try:
        result = utils.save_wiki_raw_uploads(payloads, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"문서 저장 실패: {exc}",
        ) from exc

    return {
        "wiki_dir": utils.get_user_wiki_dir(user_id),
        "raw_dir": result["raw_dir"],
        "saved": result["saved"],
        "count": result["count"],
        "files": result.get("files") or utils.get_wiki_source_files(user_id),
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
    allowed = [wiki_root, wiki_root / "raw", wiki_root / "graphify-out", wiki_root / "graphify-out" / "converted"]
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
