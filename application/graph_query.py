"""Graphify-style BFS/DFS query over a user's graph.json + source text excerpts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from networkx.readwrite import json_graph

_MAX_FILE_BYTES = 500_000
_MAX_SOURCES = 6
_MAX_EXCERPT_CHARS = 1800
_MAX_TOTAL_EXCERPT_CHARS = 8000


def _load_graph(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        return json_graph.node_link_graph(data, edges="links")
    except TypeError:
        return json_graph.node_link_graph(data)


def _query_terms(question: str) -> list[str]:
    """Tokenize question for label matching.

    English tokens shorter than 3 chars are skipped (a, of, …).
    CJK tokens keep length >= 2 so queries like \"여행\" still match.
    """
    raw_parts = [t for t in re.split(r"\s+", question.strip()) if t]
    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        low = part.lower()
        # Keep whole token if CJK-ish or long enough
        has_cjk = bool(re.search(r"[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF\u4E00-\u9FFF]", part))
        candidates = [low]
        # Also split on punctuation for mixed tokens (서울-제주)
        candidates.extend(
            p.lower()
            for p in re.split(r"[^\w\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF\u4E00-\u9FFF]+", part)
            if p
        )
        for t in candidates:
            if not t or t in seen:
                continue
            if has_cjk or re.search(r"[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF\u4E00-\u9FFF]", t):
                if len(t) < 2:
                    continue
            elif len(t) <= 2:
                continue
            seen.add(t)
            out.append(t)
    return out


def _score_label(label: str, terms: list[str]) -> int:
    low = (label or "").lower()
    return sum(1 for t in terms if t in low)


def _text_term_score(text: str, terms: list[str]) -> int:
    if not text or not terms:
        return 0
    low = text.lower()
    return sum(1 for t in terms if t in low)


def _find_nodes_by_source_content(
    G,
    terms: list[str],
    roots: list[Path],
    *,
    limit: int = 24,
) -> list[tuple[int, str]]:
    """Score nodes by whether their source_file body contains query terms."""
    by_file: dict[str, list[str]] = {}
    for nid, data in G.nodes(data=True):
        src = str(data.get("source_file") or "").strip()
        if src:
            by_file.setdefault(src, []).append(nid)

    scored: list[tuple[int, str]] = []
    checked = 0
    for src, nids in by_file.items():
        if checked >= 80:
            break
        allowed = _allowed_source(Path(src), roots)
        if allowed is None:
            continue
        checked += 1
        try:
            raw = allowed.read_bytes()
            if len(raw) > _MAX_FILE_BYTES:
                raw = raw[:_MAX_FILE_BYTES]
            text = raw.decode("utf-8", errors="replace")
        except OSError:
            continue
        score = _text_term_score(text, terms)
        if score <= 0:
            continue
        for nid in nids:
            # Prefer higher-degree hubs slightly so BFS starts somewhere useful.
            boost = min(3, int(G.degree(nid) or 0) // 3)
            scored.append((score * 10 + boost, nid))

    scored.sort(reverse=True)
    # unique node ids preserving rank
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    for score, nid in scored:
        if nid in seen:
            continue
        seen.add(nid)
        out.append((score, nid))
        if len(out) >= limit:
            break
    return out


def _allowed_source(path: Path, roots: list[Path]) -> Path | None:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return None
    if not resolved.is_file():
        return None
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    return None


def _paragraphs(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n+", text)
    out: list[str] = []
    for chunk in chunks:
        cleaned = re.sub(r"[ \t]+\n", "\n", chunk).strip()
        if len(cleaned) >= 40:
            out.append(cleaned)
    if out:
        return out
    # Fallback: sliding windows of lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    joined = "\n".join(lines)
    return [joined[i : i + 600] for i in range(0, min(len(joined), 3000), 500)]


def _extract_excerpts(
    text: str,
    *,
    terms: list[str],
    labels: list[str],
    source_location: str | None,
) -> list[str]:
    paras = _paragraphs(text)
    if not paras:
        return []

    loc = (source_location or "").strip()
    if loc and loc.lower() not in ("none", "null"):
        loc_hits = [p for p in paras if loc.lower() in p.lower()]
        if loc_hits:
            paras = loc_hits + [p for p in paras if p not in loc_hits]

    label_terms = []
    for lab in labels:
        for token in re.split(r"[\s/()\[\]|,:-]+", lab):
            tok = token.lower().strip()
            if len(tok) > 2:
                label_terms.append(tok)
    score_terms = list(dict.fromkeys(terms + label_terms))

    ranked: list[tuple[int, str]] = []
    for p in paras:
        low = p.lower()
        score = sum(1 for t in score_terms if t in low)
        if score > 0:
            ranked.append((score, p))
    ranked.sort(key=lambda x: (-x[0], -len(x[1])))

    excerpts: list[str] = []
    used = 0
    for _, p in ranked[:4]:
        snippet = p if len(p) <= _MAX_EXCERPT_CHARS else p[: _MAX_EXCERPT_CHARS - 1] + "…"
        if used + len(snippet) > _MAX_EXCERPT_CHARS:
            remain = _MAX_EXCERPT_CHARS - used
            if remain < 80:
                break
            snippet = snippet[: remain - 1] + "…"
        excerpts.append(snippet)
        used += len(snippet)
        if used >= _MAX_EXCERPT_CHARS:
            break

    if excerpts:
        return excerpts
    # No keyword hit: return a short head preview
    head = text.strip()
    if not head:
        return []
    return [head[: min(700, _MAX_EXCERPT_CHARS)] + ("…" if len(head) > 700 else "")]


def query_user_graph(
    graph_json: Path,
    question: str,
    *,
    mode: str = "bfs",
    budget: int = 2000,
    allowed_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Run graphify-style traversal and attach source text excerpts."""
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required")
    if not graph_json.is_file():
        raise FileNotFoundError(f"graph not found: {graph_json}")

    mode = "dfs" if str(mode).lower() == "dfs" else "bfs"
    budget = max(200, min(int(budget), 8000))
    terms = _query_terms(question)
    if not terms:
        terms = [question.lower()]

    G = _load_graph(graph_json)
    roots = allowed_roots or [graph_json.parent.parent]

    scored: list[tuple[int, str]] = []
    for nid, ndata in G.nodes(data=True):
        score = _score_label(str(ndata.get("label") or ""), terms)
        if score > 0:
            scored.append((score, nid))
    scored.sort(reverse=True)
    start_nodes = [nid for _, nid in scored[:3]]
    match_via = "label"

    # Document search: also match corpus/source body text.
    # Needed when labels are English ("Weather…") but the query is Korean ("날씨").
    content_scored = _find_nodes_by_source_content(G, terms, roots)
    if not start_nodes:
        start_nodes = [nid for _, nid in content_scored[:3]]
        match_via = "source"
    elif content_scored:
        # Augment starts with strong content matches not already selected.
        chosen = set(start_nodes)
        for _, nid in content_scored:
            if nid in chosen:
                continue
            start_nodes.append(nid)
            chosen.add(nid)
            if len(start_nodes) >= 3:
                break
        match_via = "label+source"

    if not start_nodes:
        return {
            "question": question,
            "mode": mode,
            "start_nodes": [],
            "nodes": [],
            "edges": [],
            "sources": [],
            "message": f"No matching nodes found for: {', '.join(terms)}",
        }

    content_score_by_id = {nid: score for score, nid in content_scored}

    subgraph_nodes: set[str] = set()
    subgraph_edges: list[tuple[str, str]] = []

    if mode == "dfs":
        visited: set[str] = set()
        stack = [(n, 0) for n in reversed(start_nodes)]
        while stack:
            node, depth = stack.pop()
            if node in visited or depth > 6:
                continue
            visited.add(node)
            subgraph_nodes.add(node)
            for neighbor in G.neighbors(node):
                if neighbor not in visited:
                    stack.append((neighbor, depth + 1))
                    subgraph_edges.append((node, neighbor))
    else:
        frontier = set(start_nodes)
        subgraph_nodes = set(start_nodes)
        for _ in range(3):
            next_frontier: set[str] = set()
            for n in frontier:
                for neighbor in G.neighbors(n):
                    if neighbor not in subgraph_nodes:
                        next_frontier.add(neighbor)
                        subgraph_edges.append((n, neighbor))
            subgraph_nodes.update(next_frontier)
            frontier = next_frontier

    def relevance(nid: str) -> int:
        return (
            _score_label(str(G.nodes[nid].get("label") or ""), terms) * 10
            + int(content_score_by_id.get(nid, 0))
        )

    ranked_nodes = sorted(subgraph_nodes, key=relevance, reverse=True)

    nodes_out: list[dict[str, Any]] = []
    for nid in ranked_nodes:
        d = G.nodes[nid]
        nodes_out.append(
            {
                "id": nid,
                "label": d.get("label") or nid,
                "source_file": d.get("source_file") or "",
                "source_location": d.get("source_location"),
                "community": d.get("community"),
                "file_type": d.get("file_type"),
            }
        )

    edges_out: list[dict[str, Any]] = []
    seen_e: set[tuple[str, str, str]] = set()
    for u, v in subgraph_edges:
        if u not in subgraph_nodes or v not in subgraph_nodes:
            continue
        ed = G.edges[u, v]
        key = (u, v, str(ed.get("relation") or ""))
        if key in seen_e:
            continue
        seen_e.add(key)
        edges_out.append(
            {
                "source": u,
                "target": v,
                "source_label": G.nodes[u].get("label") or u,
                "target_label": G.nodes[v].get("label") or v,
                "relation": ed.get("relation") or "",
                "confidence": ed.get("confidence") or "",
            }
        )

    # Group nodes by source file for excerpt extraction
    by_file: dict[str, list[dict[str, Any]]] = {}
    for n in nodes_out:
        src = str(n.get("source_file") or "").strip()
        if not src:
            continue
        by_file.setdefault(src, []).append(n)

    sources_out: list[dict[str, Any]] = []
    total_chars = 0
    for src, file_nodes in sorted(
        by_file.items(),
        key=lambda kv: -max(relevance(n["id"]) for n in kv[1]),
    ):
        if len(sources_out) >= _MAX_SOURCES or total_chars >= _MAX_TOTAL_EXCERPT_CHARS:
            break
        allowed = _allowed_source(Path(src), roots)
        if allowed is None:
            sources_out.append(
                {
                    "path": src,
                    "name": Path(src).name,
                    "readable": False,
                    "matched_labels": [n["label"] for n in file_nodes[:8]],
                    "excerpts": [],
                    "error": "source file not readable or outside allowed roots",
                }
            )
            continue
        try:
            raw = allowed.read_bytes()
            if len(raw) > _MAX_FILE_BYTES:
                raw = raw[:_MAX_FILE_BYTES]
            text = raw.decode("utf-8", errors="replace")
        except OSError as exc:
            sources_out.append(
                {
                    "path": str(allowed),
                    "name": allowed.name,
                    "readable": False,
                    "matched_labels": [n["label"] for n in file_nodes[:8]],
                    "excerpts": [],
                    "error": str(exc),
                }
            )
            continue

        loc = next(
            (
                str(n.get("source_location"))
                for n in file_nodes
                if n.get("source_location") not in (None, "", "None")
            ),
            None,
        )
        excerpts = _extract_excerpts(
            text,
            terms=terms,
            labels=[str(n["label"]) for n in file_nodes],
            source_location=loc,
        )
        # Trim to remaining budget
        kept: list[str] = []
        for ex in excerpts:
            if total_chars + len(ex) > _MAX_TOTAL_EXCERPT_CHARS:
                remain = _MAX_TOTAL_EXCERPT_CHARS - total_chars
                if remain >= 80:
                    kept.append(ex[: remain - 1] + "…")
                    total_chars += remain
                break
            kept.append(ex)
            total_chars += len(ex)

        sources_out.append(
            {
                "path": str(allowed),
                "name": allowed.name,
                "readable": True,
                "matched_labels": [n["label"] for n in file_nodes[:8]],
                "excerpts": kept,
            }
        )

    # Soft token budget on node/edge listing (for parity with graphify CLI)
    char_budget = budget * 4
    approx = json.dumps(
        {"nodes": nodes_out, "edges": edges_out},
        ensure_ascii=False,
    )
    truncated = False
    if len(approx) > char_budget:
        # Keep highest-relevance nodes first
        keep_n = max(8, min(len(nodes_out), char_budget // 120))
        keep_ids = {n["id"] for n in nodes_out[:keep_n]}
        nodes_out = nodes_out[:keep_n]
        edges_out = [
            e
            for e in edges_out
            if e["source"] in keep_ids and e["target"] in keep_ids
        ]
        truncated = True

    return {
        "question": question,
        "mode": mode,
        "match_via": match_via,
        "start_nodes": [
            {"id": nid, "label": G.nodes[nid].get("label") or nid}
            for nid in start_nodes
        ],
        "nodes": nodes_out,
        "edges": edges_out,
        "sources": sources_out,
        "truncated": truncated,
        "message": None,
    }
