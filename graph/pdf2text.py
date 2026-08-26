#!/usr/bin/env python3
"""PDF → text for Wiki Sync semantic staging.

Two backends:
  - classical (default): pdfplumber → pypdf page text
  - foundation model: PDF → per-page PNG (PyMuPDF) → Bedrock multimodal Markdown
    (same pipeline as rag-multimodal pdf2img + img2text)

Foundation-model progress is appended page-by-page to ``work_dir/extracted.md``
so an interrupted Sync can resume without redoing finished pages.

Usage:
    from pdf2text import pdf_to_text
    text = pdf_to_text(path, use_foundation_model=False)
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

_GRAPH_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _GRAPH_DIR.parent
_APPLICATION_DIR = _REPO_ROOT / "application"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_APPLICATION_DIR) not in sys.path:
    sys.path.insert(0, str(_APPLICATION_DIR))
if str(_GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(_GRAPH_DIR))

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}

LLM_PROMPT = (
    "페이지 내용을 Markdown 형식으로 변환합니다. 평문이 아니라 제목(#·##)·목록·강조·코드 블록 등 "
    "Markdown 문법을 적절히 써서 구조화해 주세요. 문장 단위로 읽기 쉽게 구분합니다. "
    "상단의 header와 하단의 footer는 출력에서 제외합니다. 상단 header는 주로 현재 페이지 제목이고, "
    "footer에는 페이지 번호 등이 있는데, 변환 결과에는 포함하지 않습니다.\n\n"
    "중요: 원문의 언어를 그대로 유지합니다. 영어 페이지는 영어로, 한국어 페이지는 한국어로 추출하고, "
    "번역·의역·언어 전환·다른 언어로의 요약을 하지 않습니다. 그림·도표 설명도 본문과 같은 언어로 작성합니다.\n\n"
    "페이지에 그림·도표·사진·스크린샷·다이어그램·캡처 등 시각적 요소가 있으면, 그 이미지가 무엇을 보여주는지·"
    "본문과 어떤 관계인지·어떤 정보를 전달하는지를 빠짐없이 상세히 풀어서 서술합니다."
)

_PAGE_HEADING_RE = re.compile(r"^## Page (\d+)\s*$", re.MULTILINE)
_EXTRACTED_NAME = "extracted.md"


def pdf_to_images(pdf_path: str | Path, output_dir: str | Path, dpi: int = 150) -> list[str]:
    """Convert every page of *pdf_path* to PNG (rag-multimodal pdf2img).

    Existing ``page_XXX.png`` files are reused (resume-friendly).
    """
    try:
        import pymupdf
    except ImportError:
        import subprocess

        print("PyMuPDF is not installed. Installing pymupdf …", file=sys.stderr)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pymupdf", "-q"],
            stdout=subprocess.DEVNULL,
        )
        import pymupdf

    pdf_path = Path(os.path.expanduser(str(pdf_path))).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(str(pdf_path))
    total = len(doc)
    saved: list[str] = []
    zoom = dpi / 72
    mat = pymupdf.Matrix(zoom, zoom)

    try:
        for i, page in enumerate(doc, start=1):
            out_path = output_dir / f"page_{i:03d}.png"
            if out_path.is_file() and out_path.stat().st_size > 0:
                saved.append(str(out_path.resolve()))
                print(f"  [{i}/{total}] cached → {out_path}", flush=True)
                continue
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(str(out_path))
            saved.append(str(out_path.resolve()))
            print(f"  [{i}/{total}] Saved → {out_path}", flush=True)
    finally:
        doc.close()

    return saved


def _natural_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def list_image_files(folder: Path) -> list[Path]:
    out = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    out.sort(key=_natural_key)
    return out


def _extract_image_markdown(image_path: Path) -> str:
    """One page image → Markdown via Bedrock multimodal (img2text / MCP path)."""
    import mcp_server_text_extraction as tex

    with open(image_path, "rb") as f:
        raw = f.read()
    b64 = tex._prepare_image_base64(raw)
    raw_text = tex._extract_text_with_llm(b64, LLM_PROMPT)
    return tex._parse_result(raw_text).strip()


def pdf_to_text_classical(path: Path) -> str:
    """Extract plain text with pdfplumber, falling back to pypdf."""
    try:
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = (page.extract_text() or "").strip()
                if text:
                    parts.append(f"## Page {i}\n\n{text}")
        if parts:
            return "\n\n".join(parts)
    except Exception as exc:
        print(f"  pdfplumber failed for {path.name}: {exc}; trying pypdf", flush=True)

    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            parts.append(f"## Page {i}\n\n{text}")
    return "\n\n".join(parts)


_FAILED_PAGE_MARKERS = (
    "텍스트를 추출하지 못하였습니다.",
    "> (추출 오류:",
    "> (빈 페이지)",
)


def _pages_done_in_md(md_path: Path) -> set[int]:
    """Pages that already have *successful* extraction (skip on resume)."""
    if not md_path.is_file():
        return set()
    text = md_path.read_text(encoding="utf-8", errors="replace")
    done: set[int] = set()
    parts = _PAGE_HEADING_RE.split(text)
    # parts: [preamble, num1, body1, num2, body2, ...]
    i = 1
    while i + 1 < len(parts):
        try:
            page_num = int(parts[i])
        except ValueError:
            i += 2
            continue
        body = (parts[i + 1] or "").strip()
        if body and not any(m in body for m in _FAILED_PAGE_MARKERS):
            done.add(page_num)
        i += 2
    return done


def _append_page_md(md_path: Path, page_num: int, body: str) -> None:
    """Write/replace one ``## Page N`` section and fsync (resume-safe)."""
    section = f"## Page {page_num}\n\n{body.strip()}\n"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if not md_path.is_file() or md_path.stat().st_size == 0:
        md_path.write_text(section, encoding="utf-8")
        return
    text = md_path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(
        rf"(^## Page {page_num}\s*\n)(.*?)(?=^## Page \d+\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(text):
        new_text = pattern.sub(section.rstrip() + "\n", text, count=1)
        md_path.write_text(new_text, encoding="utf-8")
    else:
        with open(md_path, "a", encoding="utf-8") as f:
            f.write("\n" + section)
            f.flush()
            os.fsync(f.fileno())
        return
    with open(md_path, "a", encoding="utf-8") as f:
        f.flush()
        os.fsync(f.fileno())


def pdf_to_text_foundation_model(
    path: Path,
    *,
    work_dir: Path | None = None,
    dpi: int = 150,
    keep_images: bool = False,
) -> str:
    """PDF → page images → multimodal LLM Markdown (Foundation Model Parser).

    Progress is written to ``work_dir/extracted.md`` after each page. Re-runs
    skip pages already present in that file (and reuse existing PNGs).
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    cleanup = False
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix=f"pdf2text_{path.stem}_"))
        cleanup = not keep_images
    else:
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    img_dir = work_dir / "pages"
    extracted_md = work_dir / _EXTRACTED_NAME
    print(
        f"  [foundation model] rendering PDF pages → {img_dir}",
        flush=True,
    )
    try:
        images = pdf_to_images(path, img_dir, dpi=dpi)
        if not images:
            raise ValueError(f"PDF에서 페이지 이미지를 만들지 못했습니다: {path}")

        done = _pages_done_in_md(extracted_md)
        if done:
            print(
                f"  [foundation model] resume: {len(done)}/{len(images)} page(s) "
                f"already in {extracted_md.name}",
                flush=True,
            )

        for i, img in enumerate(images, 1):
            if i in done:
                print(
                    f"  [foundation model] [{i}/{len(images)}] skip (already in md)",
                    flush=True,
                )
                continue
            img_path = Path(img)
            print(
                f"  [foundation model] [{i}/{len(images)}] LLM extract {img_path.name}",
                flush=True,
            )
            try:
                body = _extract_image_markdown(img_path)
            except Exception as exc:
                body = f"> (추출 오류: {exc})"
            if not body:
                body = "> (빈 페이지)"
            _append_page_md(extracted_md, i, body)
            done.add(i)

        if not extracted_md.is_file() or extracted_md.stat().st_size == 0:
            raise ValueError(f"Foundation Model Parser가 텍스트를 추출하지 못했습니다: {path}")

        print(
            f"  [foundation model] complete → {extracted_md} "
            f"({len(done)} page(s))",
            flush=True,
        )
        return extracted_md.read_text(encoding="utf-8", errors="replace").strip()
    finally:
        if cleanup:
            import shutil

            shutil.rmtree(work_dir, ignore_errors=True)


def pdf_to_text(
    path: str | Path,
    *,
    use_foundation_model: bool = False,
    work_dir: Path | None = None,
    dpi: int = 150,
) -> str:
    """Return page-sectioned Markdown/plain text for a PDF.

    When *use_foundation_model* is True, run PDF→images→Bedrock multimodal.
    Otherwise use pdfplumber/pypdf text extraction.

    For foundation model, do **not** fall back to classical on interrupt-style
    failures when partial ``extracted.md`` already exists — re-raise so the
    next Sync can resume. Classical fallback is only for hard startup failures.
    """
    src = Path(path).expanduser().resolve()
    if use_foundation_model:
        work = Path(work_dir) if work_dir else None
        partial = (
            work / _EXTRACTED_NAME
            if work is not None and (work / _EXTRACTED_NAME).is_file()
            else None
        )
        try:
            return pdf_to_text_foundation_model(src, work_dir=work_dir, dpi=dpi)
        except Exception as exc:
            if partial and partial.stat().st_size > 0:
                print(
                    f"  WARNING: foundation model parser interrupted for {src.name}: {exc}; "
                    f"keeping partial {partial} for resume (no classical fallback)",
                    flush=True,
                )
                raise
            print(
                f"  WARNING: foundation model parser failed for {src.name}: {exc}; "
                f"falling back to pdfplumber/pypdf",
                flush=True,
            )
            return pdf_to_text_classical(src)
    return pdf_to_text_classical(src)
