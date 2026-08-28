#!/usr/bin/env python3
"""Sync per-user wiki knowledge graph (graphify SKILL.md pipeline).

Working directory is ``.session_storage/{user}/wiki`` (raw + graphify-out),
NOT a shared global AGENT_WIKI_DIR. Implements detect → AST → semantic →
build → HTML/JSON, with LiteLLM/Bedrock semantic extraction via agent-wiki
graph/lib.

Usage:
    python graph/sync_wiki.py --user alice
    python graph/sync_wiki.py --user alice --full
    python graph/sync_wiki.py --user alice --input /path/to/docs
"""

from __future__ import annotations

import argparse
import json
import os
import shutil


def _copy_file(src, dst) -> None:
    """Content-only copy for S3 Files / NFS mounts (no xattr).

    ``shutil.copy2`` calls ``copystat`` → ``os.setxattr``, which fails with
    Errno 524 (EREMOTEIO) on ``/mnt/app-data`` and similar mounts.
    """
    shutil.copy(src, dst)
import sys
from pathlib import Path
from typing import Any

_GRAPH_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _GRAPH_DIR.parent
_APPLICATION_DIR = _REPO_ROOT / "application"

if str(_GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(_GRAPH_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_APPLICATION_DIR) not in sys.path:
    sys.path.insert(0, str(_APPLICATION_DIR))

_CODE_EXTS = {
    ".py", ".ts", ".js", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c",
    ".rb", ".swift", ".kt", ".cs", ".scala", ".php", ".cc", ".cxx", ".hpp",
    ".h", ".kts", ".lua", ".toc",
}


def _wiki_root(user_id: str | None = None) -> Path:
    from application import utils

    return Path(utils.ensure_user_wiki_dir(user_id))


def _resolve_python(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / ".graphify_python").write_text(sys.executable, encoding="utf-8")


def _ensure_graphify() -> None:
    try:
        import graphify  # noqa: F401
    except ImportError:
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "graphifyy", "-q"],
        )


def _default_input(wiki: Path) -> Path:
    raw = wiki / "raw"
    return raw if raw.is_dir() else wiki


def _resolve_one_input(wiki: Path, input_path: str | Path) -> Path:
    target = Path(input_path).expanduser()
    if not target.is_absolute():
        target = (wiki / target).resolve()
    else:
        target = target.resolve()
    return target


def _resolve_inputs(
    wiki: Path,
    *,
    user_id: str | None = None,
    input_path: str | None = None,
    input_paths: list[str] | None = None,
) -> list[Path]:
    """Resolve Sync corpus folders.

    Priority:
    1. Explicit CLI ``--input`` values
    2. Per-user ``wiki_sources.json`` ``AGENT_WIKI_SOURCES``
    3. Always also ``{wiki}/raw`` when it contains files
    4. If nothing else: ``{wiki}/raw`` if present, else wiki root
    """
    from application import utils

    explicit: list[str] = []
    if input_paths:
        explicit.extend(str(p) for p in input_paths if str(p).strip())
    if input_path and str(input_path).strip():
        explicit.append(str(input_path).strip())

    resolved: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path)
        if key in seen:
            return
        if not path.is_dir():
            print(f"[wiki sync] skip missing folder: {path}")
            return
        seen.add(key)
        resolved.append(path)

    if explicit:
        for raw in explicit:
            _add(_resolve_one_input(wiki, raw))
    else:
        for raw in utils.get_wiki_source_folders(user_id):
            _add(Path(raw))
        # Always include inbox uploads when present (Configure → 문서 추가).
        raw_dir = wiki / "raw"
        if raw_dir.is_dir() and any(raw_dir.iterdir()):
            _add(raw_dir)
        if not resolved:
            _add(_default_input(wiki))

    if not resolved:
        raise SystemExit("No valid Wiki source folders to sync.")
    return resolved


def _merge_file_maps(*maps: dict[str, list]) -> dict[str, list]:
    out: dict[str, list] = {}
    for m in maps:
        for key, values in (m or {}).items():
            bucket = out.setdefault(str(key), [])
            for item in values or []:
                if item not in bucket:
                    bucket.append(item)
    return out


def _merge_detections(parts: list[dict[str, Any]]) -> dict[str, Any]:
    if not parts:
        return {
            "total_files": 0,
            "total_words": 0,
            "files": {},
            "new_total": 0,
            "new_files": {},
            "deleted_files": [],
        }
    files = _merge_file_maps(*[p.get("files") or {} for p in parts])
    new_files = _merge_file_maps(*[p.get("new_files") or {} for p in parts])
    deleted: list[str] = []
    for p in parts:
        for item in p.get("deleted_files") or []:
            if item not in deleted:
                deleted.append(item)
    total_files = sum(int(p.get("total_files") or 0) for p in parts)
    if total_files == 0:
        total_files = sum(len(v) for v in files.values())
    new_total = sum(int(p.get("new_total") or 0) for p in parts)
    if new_total == 0 and new_files:
        new_total = sum(len(v) for v in new_files.values())
    return {
        "total_files": total_files,
        "total_words": sum(int(p.get("total_words") or 0) for p in parts),
        "files": files,
        "new_total": new_total,
        "new_files": new_files,
        "deleted_files": deleted,
    }


def _wiki_manifest_path(out: Path) -> Path:
    return out / "manifest.json"


def _manifest_mtime(entry: Any) -> float | None:
    """Normalize manifest entry to an mtime float.

    Older graphify saved ``{path: float}``. Newer graphify (and some pipeline
    runs) save ``{path: {"mtime": float, "seen": ..., "ast_hash": ...}}``.
    Comparing a float to a dict raises TypeError — coerce here.
    """
    if entry is None:
        return None
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict):
        raw = entry.get("mtime", entry.get("seen"))
        if isinstance(raw, (int, float)):
            return float(raw)
        return None
    try:
        return float(entry)
    except (TypeError, ValueError):
        return None

def _detect_incremental_targets(
    targets: list[Path], *, manifest_path: Path
) -> dict[str, Any]:
    """Incremental detect across one or more source folders with a shared manifest.

    Upstream ``detect_incremental(root)`` treats every file outside *root* as
    deleted when the manifest is shared. We detect each target, merge corpora,
    then diff against the wiki-level manifest once.
    """
    from graphify.detect import detect, load_manifest

    parts: list[dict[str, Any]] = []
    for target in targets:
        print(f"[wiki sync] incremental detect on {target}", flush=True)
        part = detect(target)
        parts.append(part)
        print(
            f"  → {int(part.get('total_files') or 0)} files · "
            f"~{part.get('total_words', 0)} words",
            flush=True,
        )

    merged = _merge_detections(parts)
    manifest = load_manifest(str(manifest_path))

    file_map = merged.get("files") or {}
    if not manifest:
        merged["incremental"] = True
        merged["new_files"] = {k: list(v) for k, v in file_map.items()}
        merged["unchanged_files"] = {k: [] for k in file_map}
        merged["new_total"] = int(merged.get("total_files") or 0)
        merged["deleted_files"] = []
        return merged

    new_files: dict[str, list[str]] = {k: [] for k in file_map}
    unchanged_files: dict[str, list[str]] = {k: [] for k in file_map}
    for ftype, file_list in file_map.items():
        for f in file_list or []:
            stored_mtime = _manifest_mtime(manifest.get(f))
            try:
                current_mtime = Path(f).stat().st_mtime
            except OSError:
                current_mtime = 0.0
            if stored_mtime is None or current_mtime > stored_mtime:
                new_files[ftype].append(f)
            else:
                unchanged_files[ftype].append(f)

    current_files = {f for flist in file_map.values() for f in (flist or [])}
    deleted_files = [f for f in manifest if f not in current_files]
    new_total = sum(len(v) for v in new_files.values())

    merged["incremental"] = True
    merged["new_files"] = new_files
    merged["unchanged_files"] = unchanged_files
    merged["new_total"] = new_total
    merged["deleted_files"] = deleted_files
    return merged


def _save_wiki_manifest(out: Path, files: dict[str, list] | None) -> None:
    """Persist mtimes for all corpus files under the wiki graphify-out manifest."""
    from graphify.detect import save_manifest

    payload = files or {}
    try:
        save_manifest(payload, str(_wiki_manifest_path(out)))
    except TypeError:
        # Older graphifyy: save_manifest(files) only → cwd-relative default path.
        os.chdir(out.parent)
        save_manifest(payload)
    except Exception as exc:
        print(f"[wiki sync] WARNING: could not save manifest: {exc}", flush=True)


def _empty_extract() -> dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _wiki_converted_dir(out: Path) -> Path:
    """Canonical converted markdown dir: ``{user}/wiki/graphify-out/converted``."""
    return out / "converted"


def _unique_dest(dest_dir: Path, name: str, used: set[str]) -> Path:
    if name not in used and not (dest_dir / name).exists():
        used.add(name)
        return dest_dir / name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 2
    while True:
        candidate = f"{stem}_{n}{suffix}"
        if candidate not in used and not (dest_dir / candidate).exists():
            used.add(candidate)
            return dest_dir / candidate
        n += 1


def _relocate_detect_converted(
    detection: dict[str, Any],
    *,
    targets: list[Path],
    wiki_converted: Path,
) -> dict[str, Any]:
    """Move office sidecars from ``{source}/graphify-out/converted`` → wiki converted.

    Upstream graphify ``detect()`` writes Office→markdown under the *scan root*
    (e.g. ``~/Documents/docs/graphify-out/converted``). Wiki Sync keeps a single
    output tree under ``.session_storage/{user}/wiki/graphify-out/``.
    """
    wiki_converted.mkdir(parents=True, exist_ok=True)
    used: set[str] = {p.name for p in wiki_converted.glob("*") if p.is_file()}
    path_map: dict[str, str] = {}

    source_converted_roots: list[Path] = []
    for target in targets:
        cand = (target / "graphify-out" / "converted").resolve()
        if cand.is_dir():
            source_converted_roots.append(cand)
        # Also catch parent ``docs/graphify-out`` when target is a subfolder
        parent_cand = (target.parent / "graphify-out" / "converted").resolve()
        if parent_cand.is_dir() and parent_cand not in source_converted_roots:
            # Only relocate files that belong to this run (listed in detection)
            source_converted_roots.append(parent_cand)

    def _under_source_converted(path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(
            resolved == root or root in resolved.parents
            for root in source_converted_roots
        )

    def _remap_one(raw: str) -> str:
        if raw in path_map:
            return path_map[raw]
        src = Path(raw)
        if not _under_source_converted(src) or not src.is_file():
            return raw
        dest = _unique_dest(wiki_converted, src.name, used)
        try:
            _copy_file(src, dest)
        except OSError as exc:
            print(f"  WARNING: could not copy converted {src} → {dest}: {exc}")
            return raw
        new_path = str(dest.resolve())
        path_map[raw] = new_path
        try:
            path_map[str(src.resolve())] = new_path
        except OSError:
            pass
        return new_path

    files = detection.get("files") or {}
    new_files = detection.get("new_files") or {}
    moved = 0
    for bucket in (files, new_files):
        if not isinstance(bucket, dict):
            continue
        for key, values in list(bucket.items()):
            if not isinstance(values, list):
                continue
            remapped: list[str] = []
            for item in values:
                before = str(item)
                after = _remap_one(before)
                if after != before:
                    moved += 1
                remapped.append(after)
            bucket[key] = remapped

    if moved:
        print(
            f"[wiki sync] relocated {moved} converted file(s) → {wiki_converted}",
            flush=True,
        )
        # Best-effort cleanup of source-adjacent graphify-out/converted leftovers
        for root in source_converted_roots:
            try:
                # Only remove files we successfully copied
                for old, new in path_map.items():
                    old_p = Path(old)
                    if old_p.parent.resolve() == root and old_p.is_file():
                        old_p.unlink(missing_ok=True)
                # Drop empty converted + graphify-out dirs
                if root.is_dir() and not any(root.iterdir()):
                    root.rmdir()
                    gout = root.parent
                    if (
                        gout.name == "graphify-out"
                        and gout.is_dir()
                        and not any(gout.iterdir())
                    ):
                        gout.rmdir()
            except OSError:
                pass
    return detection


def _clear_wiki_converted(wiki_converted: Path) -> None:
    """Refresh wiki converted/ at the start of a semantic staging run."""
    if wiki_converted.exists():
        shutil.rmtree(wiki_converted, ignore_errors=True)
    wiki_converted.mkdir(parents=True, exist_ok=True)


def _pdf_to_text(
    path: Path,
    *,
    use_foundation_model: bool = False,
    work_dir: Path | None = None,
    parallel_pages: bool = True,
    file_i: int | None = None,
    file_n: int | None = None,
) -> str:
    """Extract text from a PDF for semantic staging (see ``pdf2text.py``)."""
    from pdf2text import pdf_to_text

    return pdf_to_text(
        path,
        use_foundation_model=use_foundation_model,
        work_dir=work_dir,
        parallel_pages=parallel_pages,
        file_i=file_i,
        file_n=file_n,
    )


def _doc_to_markdown_body(
    src: Path,
    *,
    use_foundation_model: bool = False,
    pdf_work_dir: Path | None = None,
    parallel_pages: bool = True,
    file_i: int | None = None,
    file_n: int | None = None,
) -> str | None:
    """Return markdown/plain text body for semantic extraction, or None if unsupported."""
    suffix = src.suffix.lower()
    if suffix == ".md":
        return src.read_text(encoding="utf-8", errors="replace")
    if suffix in {".txt", ".text", ".rst", ".markdown"}:
        return src.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        body = _pdf_to_text(
            src,
            use_foundation_model=use_foundation_model,
            work_dir=pdf_work_dir,
            parallel_pages=parallel_pages,
            file_i=file_i,
            file_n=file_n,
        ).strip()
        if not body:
            raise ValueError(f"PDF에서 텍스트를 추출하지 못했습니다: {src}")
        return f"# {src.stem}\n\nSource: `{src}`\n\n{body}"
    return None


def _chunk_text(text: str, *, max_chars: int = 10000) -> list[str]:
    """Split long documents so each LLM chunk stays within extract_chunk limits."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    overlap = 200
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            # Prefer breaking on a paragraph boundary.
            cut = text.rfind("\n\n", start + max_chars // 2, end)
            if cut > start:
                end = cut
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def _stage_docs_as_markdown(
    files: list[Path],
    stage: Path,
    *,
    use_foundation_model: bool = False,
    parallel_pages: bool = True,
) -> dict[str, str]:
    """Copy/convert docs into ``stage`` as ``.md`` files.

    Returns mapping of staged markdown absolute path → original source path.
    """
    path_map: dict[str, str] = {}
    used_names: set[str] = set()
    pdf_pages_root = stage / ".pdf_pages"
    if use_foundation_model:
        pdf_pages_root.mkdir(parents=True, exist_ok=True)

    def _unique(name: str) -> str:
        if name not in used_names:
            used_names.add(name)
            return name
        stem = Path(name).stem
        suffix = Path(name).suffix
        n = 2
        while True:
            candidate = f"{stem}_{n}{suffix}"
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate
            n += 1

    for idx, src in enumerate(files, 1):
        suffix = src.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            print(f"  skip image (vision not in wiki sync): {src}")
            continue

        print(
            f'[wiki progress] name="{src.name}" fi={idx} fn={len(files)} '
            f"pct={int(round(100.0 * (idx - 1) / max(len(files), 1)))} "
            f"| {src.name} · 파일 {idx}/{len(files)} · 변환 시작",
            flush=True,
        )

        original = str(src.resolve())
        # Already under wiki graphify-out/converted (e.g. relocated Office sidecars)
        try:
            if src.resolve().parent == stage.resolve() and suffix == ".md":
                path_map[str(src.resolve())] = original
                continue
        except OSError:
            pass

        pdf_work: Path | None = None
        if use_foundation_model and suffix == ".pdf":
            # Keep page PNGs + progressive extracted.md under converted/.pdf_pages
            import hashlib

            digest = hashlib.sha256(original.encode()).hexdigest()[:8]
            pdf_work = pdf_pages_root / f"{src.stem}_{digest}"
            pdf_work.mkdir(parents=True, exist_ok=True)
            (pdf_work / "source_path.txt").write_text(original + "\n", encoding="utf-8")

        try:
            body = _doc_to_markdown_body(
                src,
                use_foundation_model=use_foundation_model,
                pdf_work_dir=pdf_work,
                parallel_pages=parallel_pages,
                file_i=idx,
                file_n=len(files),
            )
        except Exception as exc:
            print(f"  WARNING: failed to convert {src}: {exc}")
            continue
        if body is None:
            print(f"  skip unsupported for semantic staging: {src}")
            continue

        if src.suffix.lower() == ".md" and len(body) <= 12000:
            name = _unique(src.name if src.name.endswith(".md") else f"{src.stem}.md")
            dest = stage / name
            dest.write_text(body, encoding="utf-8")
            path_map[str(dest.resolve())] = original
            print(
                f'[wiki progress] name="{src.name}" fi={idx} fn={len(files)} pct='
                f"{int(round(100.0 * idx / max(len(files), 1)))} "
                f"| {src.name} · 파일 {idx}/{len(files)} · 완료",
                flush=True,
            )
            continue

        parts = _chunk_text(body, max_chars=10000)
        if not parts:
            print(f"  skip empty after convert: {src}")
            continue
        print(
            f"  stage {src.name} → {len(parts)} markdown chunk(s) "
            f"({sum(len(p) for p in parts)} chars)",
            flush=True,
        )
        for i, part in enumerate(parts, 1):
            if len(parts) == 1:
                name = _unique(f"{src.stem}.md")
            else:
                name = _unique(f"{src.stem}_part{i:02d}.md")
            dest = stage / name
            header = (
                f"---\nsource_file: \"{original}\"\n"
                f"chunk: {i}\nchunks: {len(parts)}\n---\n\n"
            )
            dest.write_text(header + part, encoding="utf-8")
            path_map[str(dest.resolve())] = original

        print(
            f'[wiki progress] name="{src.name}" fi={idx} fn={len(files)} pct='
            f"{int(round(100.0 * idx / max(len(files), 1)))} "
            f"| {src.name} · 파일 {idx}/{len(files)} · 완료",
            flush=True,
        )

    return path_map


def _incomplete_foundation_pdfs(
    stage: Path, *, candidates: list[Path] | None = None
) -> list[Path]:
    """PDFs with partial ``.pdf_pages/.../extracted.md`` that should be resumed."""
    import hashlib

    from pdf2text import _EXTRACTED_NAME, _collect_done_pages

    root = stage / ".pdf_pages"
    if not root.is_dir():
        return []

    cand_by_key: dict[str, Path] = {}
    for c in candidates or []:
        p = Path(c)
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        try:
            resolved = p.resolve()
        except OSError:
            continue
        digest = hashlib.sha256(str(resolved).encode()).hexdigest()[:8]
        cand_by_key[f"{resolved.stem}_{digest}"] = resolved

    found: list[Path] = []
    seen: set[str] = set()
    for work in sorted(root.iterdir()):
        if not work.is_dir():
            continue
        marker = work / "source_path.txt"
        src: Path | None = None
        if marker.is_file():
            raw = marker.read_text(encoding="utf-8", errors="replace").strip()
            if raw:
                src = Path(raw)
        if src is None or not src.is_file():
            src = cand_by_key.get(work.name)
            if src is not None:
                marker.write_text(str(src.resolve()) + "\n", encoding="utf-8")
        if src is None or not src.is_file():
            continue
        try:
            key = str(src.resolve())
        except OSError:
            key = str(src)
        if key in seen:
            continue
        pages_dir = work / "pages"
        pngs = (
            sorted(pages_dir.glob("page_*.png")) if pages_dir.is_dir() else []
        )
        total = len(pngs) if pngs else 0
        done = _collect_done_pages(
            work / _EXTRACTED_NAME,
            pages_dir if pages_dir.is_dir() else work / "pages",
            total,
        )
        if not pngs and not done:
            continue
        if not done or (pngs and len(done) < len(pngs)):
            seen.add(key)
            found.append(src)
            print(
                f"  [foundation model] resume pending: {src.name} "
                f"({len(done)}/{len(pngs) or '?'} pages in extracted.md)",
                flush=True,
            )
    return found


def _merge_doc_files_with_resumes(
    doc_files: list[str],
    *,
    out: Path,
    use_foundation_model: bool,
    candidates: list[str] | None = None,
) -> list[str]:
    if not use_foundation_model:
        return doc_files
    stage = _wiki_converted_dir(out)
    cand_paths = [Path(p) for p in (candidates or [])] + [
        Path(p) for p in doc_files
    ]
    pending = _incomplete_foundation_pdfs(stage, candidates=cand_paths)
    if not pending:
        return doc_files
    merged = list(doc_files)
    have = {str(Path(p).resolve()) for p in doc_files if Path(p).is_file()}
    for src in pending:
        key = str(src.resolve())
        if key not in have:
            merged.append(str(src))
            have.add(key)
    return merged


def _rewrite_extract_sources(
    extraction: dict[str, Any], path_map: dict[str, str]
) -> dict[str, Any]:
    """Point extract nodes/edges back at original corpus paths (not stage/*.md)."""
    if not path_map:
        return extraction

    def _map_src(value: object) -> object:
        if not value:
            return value
        key = str(value)
        if key in path_map:
            return path_map[key]
        try:
            resolved = str(Path(key).resolve())
        except OSError:
            return value
        return path_map.get(resolved, value)

    for collection in ("nodes", "edges", "hyperedges"):
        for item in extraction.get(collection) or []:
            if isinstance(item, dict) and "source_file" in item:
                item["source_file"] = _map_src(item.get("source_file"))
    return extraction


def _merge_extracts(ast: dict[str, Any], sem: dict[str, Any]) -> dict[str, Any]:
    seen: set[str] = set()
    nodes: list[dict] = []
    for n in (ast.get("nodes") or []) + (sem.get("nodes") or []):
        nid = n.get("id")
        if not nid or nid in seen:
            continue
        seen.add(nid)
        nodes.append(n)
    return {
        "nodes": nodes,
        "edges": (ast.get("edges") or []) + (sem.get("edges") or []),
        "hyperedges": (sem.get("hyperedges") or []) + (ast.get("hyperedges") or []),
        "input_tokens": int(sem.get("input_tokens") or 0)
        + int(ast.get("input_tokens") or 0),
        "output_tokens": int(sem.get("output_tokens") or 0)
        + int(ast.get("output_tokens") or 0),
    }


def _files_from_detect(detect: dict[str, Any], *keys: str) -> list[str]:
    files = detect.get("files") or {}
    out: list[str] = []
    for key in keys:
        out.extend(files.get(key) or [])
    return out


def _run_ast(code_files: list[str], out: Path) -> dict[str, Any]:
    from graphify.extract import collect_files, extract

    paths: list[Path] = []
    for f in code_files:
        p = Path(f)
        if p.is_dir():
            paths.extend(collect_files(p))
        elif p.is_file():
            paths.append(p)
    if not paths:
        result = _empty_extract()
        (out / ".graphify_ast.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print("No code files - skipping AST extraction")
        return result
    result = extract(paths)
    (out / ".graphify_ast.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        f"AST: {len(result.get('nodes', []))} nodes, "
        f"{len(result.get('edges', []))} edges"
    )
    return result


def _run_semantic(
    doc_files: list[str],
    *,
    out: Path,
    deep: bool,
    use_foundation_model: bool = False,
    parallel_pages: bool = True,
) -> dict[str, Any]:
    from lib.semantic import extract_corpus  # type: ignore

    files = [Path(f) for f in doc_files if Path(f).is_file()]
    if not files:
        result = _empty_extract()
        (out / ".graphify_semantic.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print("No doc/paper/image files - skipping semantic extraction")
        return result

    stage = _wiki_converted_dir(out)
    stage.mkdir(parents=True, exist_ok=True)
    try:
        mode = "foundation-model" if use_foundation_model else "pdfplumber/pypdf"
        print(
            f"[wiki sync] staging {len(files)} doc/paper file(s) as markdown → {stage} "
            f"(pdf parser: {mode})",
            flush=True,
        )
        path_map = _stage_docs_as_markdown(
            files,
            stage,
            use_foundation_model=use_foundation_model,
            parallel_pages=parallel_pages,
        )
        staged_mds = list(path_map.keys())
        if not staged_mds:
            result = _empty_extract()
            print(
                "No convertible docs for semantic extraction "
                "(need .md/.txt/.pdf; images need vision)"
            )
            (out / ".graphify_semantic.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            return result

        print(
            f"[wiki sync] semantic extract on {len(staged_mds)} markdown chunk(s) "
            f"in {stage}",
            flush=True,
        )
        result = extract_corpus(stage, out, deep=deep, chunk_size=8)
        result = _rewrite_extract_sources(result, path_map)
    except Exception:
        # Keep converted/ for debugging on failure.
        raise

    (out / ".graphify_semantic.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        f"Semantic: {len(result.get('nodes', []))} nodes, "
        f"{len(result.get('edges', []))} edges · converted kept at {stage}",
        flush=True,
    )
    return result


def _write_outputs(
    G: Any,
    communities: dict,
    detection: dict[str, Any],
    *,
    out: Path,
    input_label: str,
    tokens: dict[str, int],
) -> None:
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.cluster import score_all
    from graphify.export import to_html, to_json
    from graphify.report import generate

    cohesion = score_all(G, communities)
    labels = {cid: f"Community {cid}" for cid in communities}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    questions = suggest_questions(G, communities, labels)
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        tokens,
        input_label,
        suggested_questions=questions,
    )
    (out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(out / "graph.json"))
    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in cohesion.items()},
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
    }
    (out / ".graphify_analysis.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )
    (out / ".graphify_labels.json").write_text(
        json.dumps({str(k): v for k, v in labels.items()}, indent=2),
        encoding="utf-8",
    )
    if G.number_of_nodes() > 5000:
        print(
            f"Graph has {G.number_of_nodes()} nodes - too large for HTML viz. "
            "Skipping graph.html."
        )
    else:
        to_html(G, communities, str(out / "graph.html"), community_labels=labels)
        print(f"graph.html written → {out / 'graph.html'}")
    print(
        f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"{len(communities)} communities"
    )


def _build_from_extract(
    extraction: dict[str, Any],
    detection: dict[str, Any],
    *,
    out: Path,
    input_label: str,
) -> None:
    from graphify.build import build_from_json
    from graphify.cluster import cluster

    G = build_from_json(extraction)
    if G.number_of_nodes() == 0:
        raise SystemExit("ERROR: Graph is empty - extraction produced no nodes.")
    communities = cluster(G)
    _write_outputs(
        G,
        communities,
        detection,
        out=out,
        input_label=input_label,
        tokens={
            "input": int(extraction.get("input_tokens") or 0),
            "output": int(extraction.get("output_tokens") or 0),
        },
    )


def _try_save_manifest(target: Path, detection: dict[str, Any]) -> None:
    """Deprecated helper — prefer ``_save_wiki_manifest``."""
    _ = target
    files = detection.get("files") if isinstance(detection, dict) else None
    if isinstance(files, dict):
        # Best-effort: write beside wiki after chdir in run_sync.
        from graphify.detect import save_manifest

        try:
            save_manifest(files)
        except Exception:
            return


def run_sync(
    *,
    user_id: str | None = None,
    full: bool = False,
    input_path: str | None = None,
    input_paths: list[str] | None = None,
    deep: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    """Run graphify sync for a user's wiki folder. Returns a status summary."""
    model_name = (model or "").strip()
    if model_name:
        os.environ["WIKI_VISION_MODEL"] = model_name
        print(f"[wiki sync] vision model (UI): {model_name}", flush=True)
    else:
        print(
            "[wiki sync] WARNING: no vision model from UI — "
            "Foundation Model Parser will use default (Claude 5.0 Sonnet)",
            flush=True,
        )

    wiki = _wiki_root(user_id)
    os.chdir(wiki)
    out = wiki / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    _ensure_graphify()
    _resolve_python(out)

    print(f"[wiki sync] user={user_id or 'default'} wiki={wiki}", flush=True)
    targets = _resolve_inputs(
        wiki,
        user_id=user_id,
        input_path=input_path,
        input_paths=input_paths,
    )
    input_label = ", ".join(str(t) for t in targets)
    print(f"[wiki sync] sources ({len(targets)}): {input_label}", flush=True)

    from graphify.build import build_from_json
    from graphify.cluster import cluster
    from graphify.detect import detect
    from networkx.readwrite import json_graph

    graph_json = out / "graph.json"
    wiki_converted = _wiki_converted_dir(out)
    manifest_path = _wiki_manifest_path(out)
    use_incremental = (
        not full and graph_json.is_file() and manifest_path.is_file()
    )

    if use_incremental:
        print(
            f"[wiki sync] incremental update on {len(targets)} source(s)",
            flush=True,
        )
        detection = _detect_incremental_targets(
            targets, manifest_path=manifest_path
        )
        (out / ".graphify_incremental.json").write_text(
            json.dumps(detection, indent=2), encoding="utf-8"
        )
        new_total = int(detection.get("new_total") or 0)
        deleted = detection.get("deleted_files") or []
        if new_total == 0 and not deleted:
            print("No files changed since last run. Nothing to update.")
            return {
                "status": "unchanged",
                "wiki": str(wiki),
                "input": input_label,
                "inputs": [str(t) for t in targets],
                "exists": graph_json.is_file(),
            }
        print(f"{new_total} new/changed file(s) to re-extract.", flush=True)
        # Refresh converted only for files we will re-stage this run.
        detection = _relocate_detect_converted(
            detection, targets=targets, wiki_converted=wiki_converted
        )
        (out / ".graphify_incremental.json").write_text(
            json.dumps(detection, indent=2), encoding="utf-8"
        )
        new_files = detection.get("new_files") or {}
        code_files = list(new_files.get("code") or [])
        doc_files = _files_from_detect(
            {"files": new_files},
            "document",
            "docs",
            "paper",
            "papers",
            "image",
            "images",
        )
    else:
        if full:
            print("[wiki sync] full re-detect/extract requested", flush=True)
        elif not graph_json.is_file() or not manifest_path.is_file():
            print(
                "[wiki sync] no prior graph/manifest — running full detect/extract",
                flush=True,
            )
        parts: list[dict[str, Any]] = []
        for target in targets:
            print(f"[wiki sync] full detect on {target}", flush=True)
            part = detect(target)
            parts.append(part)
            print(
                f"  → {int(part.get('total_files') or 0)} files · "
                f"~{part.get('total_words', 0)} words",
                flush=True,
            )
        detection = _merge_detections(parts)
        # One canonical converted/ under the user's wiki (not beside Sources).
        _clear_wiki_converted(wiki_converted)
        detection = _relocate_detect_converted(
            detection, targets=targets, wiki_converted=wiki_converted
        )
        (out / ".graphify_detect.json").write_text(
            json.dumps(detection, indent=2), encoding="utf-8"
        )
        total = int(detection.get("total_files") or 0)
        if total == 0:
            raise SystemExit(f"No supported files found in: {input_label}")
        print(f"Corpus: {total} files · ~{detection.get('total_words', 0)} words", flush=True)
        code_files = _files_from_detect(detection, "code")
        doc_files = _files_from_detect(
            detection, "document", "docs", "paper", "papers", "image", "images"
        )

    old_backup = out / ".graphify_old.json"
    if use_incremental and graph_json.is_file():
        _copy_file(graph_json, old_backup)

    all_changed = code_files + doc_files
    code_only = bool(all_changed) and all(
        Path(f).suffix.lower() in _CODE_EXTS for f in all_changed
    )

    print("[wiki sync] AST extract…", flush=True)
    ast = _run_ast(code_files, out)
    from application import utils as app_utils

    use_foundation_model = app_utils.is_foundation_model_parser_enabled(user_id)
    use_parallel = app_utils.is_wiki_parallel_processing_enabled(user_id)
    if use_foundation_model:
        print(
            "[wiki sync] Foundation Model Parser enabled — PDF→images→LLM",
            flush=True,
        )
    if use_parallel and use_foundation_model:
        print(
            "[wiki sync] Parallel page processing enabled "
            f"(page_workers={os.environ.get('WIKI_SYNC_PAGE_WORKERS', '4')}, "
            f"llm_concurrency={os.environ.get('WIKI_SYNC_LLM_CONCURRENCY', '4')})",
            flush=True,
        )
    elif use_foundation_model:
        print(
            "[wiki sync] Parallel page processing disabled — sequential pages",
            flush=True,
        )
    if use_foundation_model:
        doc_files = _merge_doc_files_with_resumes(
            doc_files,
            out=out,
            use_foundation_model=True,
            candidates=_files_from_detect(
                detection, "paper", "papers", "document", "docs"
            ),
        )
    if code_only and use_incremental and not doc_files:
        print("[graphify update] Code-only changes - skipping semantic extraction", flush=True)
        sem = _empty_extract()
    else:
        print("[wiki sync] semantic extract…", flush=True)
        sem = _run_semantic(
            doc_files,
            out=out,
            deep=deep,
            use_foundation_model=use_foundation_model,
            parallel_pages=use_parallel and use_foundation_model,
        )

    merged = _merge_extracts(ast, sem)
    (out / ".graphify_extract.json").write_text(
        json.dumps(merged, indent=2), encoding="utf-8"
    )
    print(
        f"Merged: {len(merged['nodes'])} nodes, {len(merged['edges'])} edges "
        f"({len(ast.get('nodes', []))} AST + {len(sem.get('nodes', []))} semantic)",
        flush=True,
    )

    if use_incremental and old_backup.is_file():
        print("[wiki sync] incremental merge + cluster…", flush=True)
        existing_data = json.loads(old_backup.read_text(encoding="utf-8"))
        try:
            G_existing = json_graph.node_link_graph(existing_data, edges="links")
        except TypeError:
            G_existing = json_graph.node_link_graph(existing_data)
        G_new = build_from_json(merged)
        deleted = set(
            json.loads((out / ".graphify_incremental.json").read_text()).get(
                "deleted_files", []
            )
        )
        if deleted:
            to_remove = [
                n
                for n, d in G_existing.nodes(data=True)
                if d.get("source_file") in deleted
            ]
            G_existing.remove_nodes_from(to_remove)
            print(
                f"Pruned {len(to_remove)} ghost nodes from "
                f"{len(deleted)} deleted file(s)"
            )
        G_existing.update(G_new)
        communities = cluster(G_existing)
        _write_outputs(
            G_existing,
            communities,
            detection,
            out=out,
            input_label=input_label,
            tokens={
                "input": int(merged.get("input_tokens") or 0),
                "output": int(merged.get("output_tokens") or 0),
            },
        )
        old_backup.unlink(missing_ok=True)
    else:
        print("[wiki sync] build graph + cluster + export…", flush=True)
        _build_from_extract(merged, detection, out=out, input_label=input_label)

    _save_wiki_manifest(out, detection.get("files") if isinstance(detection, dict) else None)

    return {
        "status": "ready",
        "wiki": str(wiki),
        "input": input_label,
        "inputs": [str(t) for t in targets],
        "exists": (out / "graph.html").is_file() or (out / "app-graph.html").is_file(),
        "graph_json": str(out / "graph.json"),
        "graph_html": str(out / "app-graph.html"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user",
        required=True,
        help="User id (wiki root = .session_storage/{user}/wiki)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full re-detect/extract instead of incremental --update",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=None,
        help="Corpus path (repeatable). Default: user wiki_sources or wiki/raw",
    )
    parser.add_argument("--deep", action="store_true", help="Aggressive INFERRED edges")
    parser.add_argument(
        "--model",
        default=None,
        help="UI display name for Foundation Model Parser vision model",
    )
    args = parser.parse_args()
    print(
        f"[wiki sync] start user={args.user} full={args.full} deep={args.deep}",
        flush=True,
    )
    summary = run_sync(
        user_id=args.user,
        full=args.full,
        input_paths=args.input,
        deep=args.deep,
        model=args.model,
    )
    print(
        f"[wiki sync] done status={summary.get('status')} "
        f"graph={summary.get('graph_json')}",
        flush=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
