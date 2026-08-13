"""
Wiki Graph search tool for MCP.

Wraps application.graph_query.query_user_graph — the same BFS/DFS + excerpt
path used by POST /api/wiki/query (Wiki Graph UI document search) — so the
agent can search the user's wiki corpus (raw / Sources / converted docs).

Return shape mirrors mcp_graph_memory.recall_graph_memory:
  success → {"text": [<content items LLM can cite>]}
  error   → {"status": "error", "content": [{"text": "..."}]}
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("wiki")

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

_MAX_EXCERPTS = 12


def _current_user_id() -> str:
    """User id injected into the MCP process env by chat.create_agent()."""
    return (os.environ.get("AGENTCORE_USER_ID") or "").strip()


def _error(message: str) -> Dict[str, Any]:
    return {"status": "error", "content": [{"text": message}]}


def _extract_contents(result: dict[str, Any]) -> List[Any]:
    """
    Flatten graph query output into LLM-ready excerpt items.

    Topic labels and relations are omitted: they add tokens without
    citable source text. Related entity names stay on each excerpt as
    ``related_topics``.
    """
    contents: List[Any] = []

    if result.get("message") and not result.get("nodes") and not result.get("sources"):
        logger.info("wiki empty: %s", result.get("message"))
        return contents

    excerpt_count = 0
    for source in result.get("sources") or []:
        if not source.get("readable", True):
            continue
        name = source.get("name") or Path(str(source.get("path") or "")).name or "unknown"
        labels = [str(lb) for lb in (source.get("matched_labels") or []) if lb][:8]
        for excerpt in source.get("excerpts") or []:
            text = str(excerpt).strip()
            if not text:
                continue
            item: Dict[str, Any] = {
                "type": "excerpt",
                "source": name,
                "text": text,
            }
            if labels:
                item["related_topics"] = labels
            contents.append(item)
            excerpt_count += 1
            if excerpt_count >= _MAX_EXCERPTS:
                break
        if excerpt_count >= _MAX_EXCERPTS:
            break

    logger.info("extracted contents: excerpts=%s", excerpt_count)
    return contents


def recall_wiki(
    question: str,
    mode: Optional[Literal["bfs", "dfs"]] = "bfs",
    budget: Optional[int] = 2000,
) -> Dict[str, Any]:
    """
    Search the current user's Wiki Graph for corpus text related to ``question``.

    Same semantics as the Wiki Graph UI document search (POST /api/wiki/query).
    On success returns ``{"text": [...]}`` like memory retrieve.
    """
    try:
        import utils
        from graph_query import query_user_graph
    except ImportError as e:
        logger.error(f"Failed to import graph modules: {e}")
        return _error(f"Wiki search unavailable: {e}")

    user_id = _current_user_id()
    if not user_id:
        user_id = "default"
        logger.info("AGENTCORE_USER_ID was empty, using default: %s", user_id)

    logger.info(
        "###### recall_wiki ###### user_id=%s question=%r mode=%s budget=%s",
        user_id,
        question,
        mode,
        budget,
    )

    question = (question or "").strip()
    if not question:
        return _error("question is required")

    graph_json = Path(utils.wiki_graph_json_path(user_id))
    if not graph_json.is_file():
        return _error(
            "Wiki 그래프가 아직 없습니다. Settings → Wiki → Sync를 실행한 뒤 다시 검색하세요."
        )

    wiki_root = Path(utils.get_user_wiki_dir(user_id))
    allowed = [wiki_root, wiki_root / "raw", wiki_root / "graphify-out"]
    for src in utils.get_wiki_source_folders(user_id):
        allowed.append(Path(src))

    try:
        result = query_user_graph(
            graph_json,
            question,
            mode=mode or "bfs",
            budget=int(budget or 2000),
            allowed_roots=allowed,
            use_embeddings=utils.is_hybrid_graph_search_enabled(),
        )
    except ValueError as e:
        return _error(str(e))
    except FileNotFoundError as e:
        return _error(str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("wiki search failed")
        return _error(f"query failed: {e}")

    contents = _extract_contents(result)
    return {"text": contents}
