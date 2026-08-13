import logging
import sys
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import mcp_wiki

from typing import Dict, Literal, Optional
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("wiki")

try:
    mcp = FastMCP(
        name="wiki",
        instructions=(
            "Search the user's Wiki Graph (uploaded documents / Sources corpus) "
            "with the same document-search path as the Wiki Graph UI. "
            "Use when the answer depends on wiki documents, PDFs, or synced "
            "source folders — not past chat history (use graph memory for that)."
        ),
    )
    logger.info("MCP server initialized successfully")
except Exception as e:
    err_msg = f"Error: {str(e)}"
    logger.info(f"{err_msg}")


######################################
# wiki graph search
######################################
@mcp.tool()
def recall_wiki(
    question: str,
    mode: Optional[Literal["bfs", "dfs"]] = "bfs",
    budget: Optional[int] = 2000,
) -> Dict:
    """
    Search the user's Wiki Graph for document corpus text related to the question.

    Same behavior as the Wiki Graph screen document search (POST /api/wiki/query):
    finds matching nodes (label / source text / optional embedding hybrid),
    traverses neighbors (BFS or DFS), and returns source-text excerpts from
    wiki documents (topic/relation metadata is omitted).

    Call this when the user asks about content from uploaded wiki documents,
    synced folders, or converted PDFs (Korean: 위키, 문서, 업로드한 파일, Sync).

    Args:
        question: Natural-language search query (required), e.g. "Ontology on AWS", "RAG 아키텍처"
        mode: Traversal mode — "bfs" (default) or "dfs"
        budget: Soft size budget for node/edge listing (200–8000, default 2000)

    Returns:
        On success (same shape as memory retrieve):
            {"text": [
                {"type": "excerpt", "source": "...", "related_topics": [...], "text": "..."},
                ...
            ]}
        On error:
            {"status": "error", "content": [{"text": "..."}]}
    """
    logger.info("###### recall_wiki ######")
    logger.info(f"question: {question}, mode: {mode}, budget: {budget}")

    return mcp_wiki.recall_wiki(question, mode=mode, budget=budget)


if __name__ == "__main__":
    mcp.run(transport="stdio")
