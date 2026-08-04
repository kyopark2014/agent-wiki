"""agentcore_knowledge_graph.html 스타일의 상세 관계 그래프 HTML 생성."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import networkx as nx

# agentcore_knowledge_graph.html 과 같은 팔레트
GROUP_COLORS = [
    "#FF6B35",
    "#4ECDC4",
    "#45B7D1",
    "#96CEB4",
    "#DDA0DD",
    "#FFD93D",
    "#F7B2B7",
    "#C8E6C9",
    "#B0BEC5",
    "#81D4FA",
    "#FFAB91",
    "#CE93D8",
    "#A5D6A7",
    "#FFF59D",
    "#90CAF9",
]


def _wrap_label(text: str, width: int = 16) -> str:
    text = (text or "").strip() or "(unnamed)"
    if len(text) <= width:
        return text
    parts: list[str] = []
    buf = ""
    for token in re.split(r"(\s+)", text):
        if len(buf) + len(token) > width and buf:
            parts.append(buf.strip())
            buf = token.lstrip()
        else:
            buf += token
    if buf.strip():
        parts.append(buf.strip())
    if not parts:
        parts = [text[:width]]
    return "\n".join(parts[:4])


def _infer_community_labels(
    G: nx.Graph,
    communities: dict[int, list[str]],
) -> dict[int, str]:
    labels: dict[int, str] = {}
    degree = dict(G.degree())
    for cid, members in communities.items():
        ranked = sorted(members, key=lambda n: degree.get(n, 0), reverse=True)
        top = []
        for nid in ranked[:3]:
            lab = str(G.nodes[nid].get("label") or nid)
            lab = re.sub(r"\s+", " ", lab).strip()
            if lab and lab not in top:
                top.append(lab[:28])
        labels[cid] = " · ".join(top) if top else f"그룹 {cid}"
    return labels


def _node_description(G: nx.Graph, node_id: str) -> str:
    data = G.nodes[node_id]
    lines: list[str] = []
    src = data.get("source_file") or ""
    if src:
        lines.append(f"출처: {Path(str(src)).name}")
    captured = data.get("captured_at") or ""
    if captured:
        lines.append(f"시각: {captured}")
    author = data.get("author") or ""
    if author:
        lines.append(f"사용자: {author}")

    rels: list[str] = []
    for _, nbr, edata in G.edges(node_id, data=True):
        rel = edata.get("relation") or "related"
        conf = edata.get("confidence") or ""
        nbr_label = G.nodes[nbr].get("label") or nbr
        tag = f"{rel}"
        if conf and conf != "EXTRACTED":
            tag += f" [{conf}]"
        rels.append(f"→ {tag} → {nbr_label}")
    # undirected: also show incoming-style via neighbors already covered
    if rels:
        lines.append("관계:")
        lines.extend(rels[:8])
        if len(rels) > 8:
            lines.append(f"… 외 {len(rels) - 8}개")
    return "\n".join(lines) if lines else "관련 설명이 없습니다."


def to_rich_html(
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_path: str | Path,
    *,
    title: str,
    subtitle: str | None = None,
    community_labels: dict[int, str] | None = None,
) -> None:
    """Write an agentcore-style interactive knowledge graph HTML."""
    community_labels = community_labels or _infer_community_labels(G, communities)
    node_community = {
        nid: cid for cid, members in communities.items() for nid in members
    }
    degree = dict(G.degree())
    max_deg = max(degree.values()) if degree else 1

    raw_nodes: list[dict[str, Any]] = []
    descriptions: dict[str, str] = {}
    for nid, data in G.nodes(data=True):
        cid = int(node_community.get(nid, 0))
        color = GROUP_COLORS[cid % len(GROUP_COLORS)]
        deg = degree.get(nid, 1)
        size = 14 + 28 * (deg / max_deg)
        label = str(data.get("label") or nid)
        raw_nodes.append(
            {
                "id": nid,
                "label": _wrap_label(label),
                "group": str(cid),
                "size": round(size, 1),
                "color": color,
                "degree": deg,
            }
        )
        descriptions[nid] = _node_description(G, nid)

    # hub = highest degree for initial focus
    hub = max(G.nodes, key=lambda n: degree.get(n, 0)) if G.number_of_nodes() else None

    raw_edges: list[dict[str, Any]] = []
    for u, v, data in G.edges(data=True):
        src = data.get("_src") or u
        tgt = data.get("_tgt") or v
        # keep endpoints inside graph
        if src not in G or tgt not in G:
            src, tgt = u, v
        cid = int(node_community.get(src, node_community.get(u, 0)))
        color = GROUP_COLORS[cid % len(GROUP_COLORS)]
        conf = data.get("confidence") or "EXTRACTED"
        raw_edges.append(
            {
                "from": src,
                "to": tgt,
                "label": data.get("relation") or "",
                "color": color,
                "dashed": conf != "EXTRACTED",
                "confidence": conf,
            }
        )

    legend_items = []
    for cid in sorted(communities.keys()):
        legend_items.append(
            {
                "id": str(cid),
                "label": community_labels.get(cid, f"그룹 {cid}"),
                "color": GROUP_COLORS[cid % len(GROUP_COLORS)],
                "count": len(communities[cid]),
            }
        )

    subtitle = subtitle or (
        "graphify로 추출된 지식 그래프 · 노드를 클릭하면 상세 정보와 관계를 확인할 수 있습니다"
    )

    payload = {
        "title": title,
        "subtitle": subtitle,
        "nodes": len(raw_nodes),
        "edges": len(raw_edges),
        "groups": len(communities),
        "hub": hub,
        "rawNodes": raw_nodes,
        "rawEdges": raw_edges,
        "descriptions": descriptions,
        "legend": legend_items,
    }

    html_doc = _render_template(payload)
    Path(output_path).write_text(html_doc, encoding="utf-8")


def _render_template(payload: dict[str, Any]) -> str:
    title = html.escape(payload["title"])
    subtitle = html.escape(payload["subtitle"])
    data_json = json.dumps(
        {
            "hub": payload["hub"],
            "rawNodes": payload["rawNodes"],
            "rawEdges": payload["rawEdges"],
            "descriptions": payload["descriptions"],
            "legend": payload["legend"],
        },
        ensure_ascii=False,
    )
    # Prevent </script> breakout
    data_json = data_json.replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html {{
    color-scheme: dark;
    height: 100%;
    background: #0d1117;
  }}
  body {{
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: #0d1117;
    font-family: 'Segoe UI', sans-serif;
    color: #e6edf3;
  }}

  #header {{
    flex-shrink: 0;
    background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
    border-bottom: 1px solid #30363d;
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  #header h1 {{ font-size: 20px; font-weight: 700; color: #FF6B35; }}
  #header p {{ font-size: 13px; color: #8b949e; margin-top: 4px; }}

  #main {{
    flex: 1;
    min-height: 0;
    display: flex;
  }}

  #network-container {{
    flex: 1;
    min-width: 0;
    position: relative;
    overflow: hidden;
    outline: none;
    border: none;
    background: radial-gradient(ellipse at center, #161b22 0%, #0d1117 100%);
  }}
  #mynetwork {{
    width: 100%;
    height: 100%;
    overflow: hidden;
    outline: none;
    border: none;
  }}
  #mynetwork:focus,
  #mynetwork:focus-visible,
  #network-container:focus,
  #network-container:focus-visible {{
    outline: none;
  }}
  #mynetwork .vis-network,
  #mynetwork canvas {{
    outline: none !important;
    border: none !important;
  }}

  #sidebar {{
    width: 300px;
    flex-shrink: 0;
    background: #161b22;
    border-left: 1px solid #30363d;
    overflow-x: hidden;
    overflow-y: auto;
    padding: 16px;
    scrollbar-width: thin;
    scrollbar-color: rgba(255, 255, 255, 0.22) #161b22;
  }}
  #sidebar::-webkit-scrollbar {{
    width: 8px;
  }}
  #sidebar::-webkit-scrollbar-track {{
    background: #161b22;
  }}
  #sidebar::-webkit-scrollbar-thumb {{
    background: rgba(255, 255, 255, 0.22);
    border-radius: 999px;
    border: 2px solid #161b22;
    background-clip: padding-box;
  }}
  #sidebar::-webkit-scrollbar-thumb:hover {{
    background: rgba(255, 255, 255, 0.35);
    background-clip: padding-box;
  }}
  #sidebar::-webkit-scrollbar-corner {{
    background: #161b22;
  }}
  #sidebar::-webkit-scrollbar-button {{
    display: none;
    width: 0;
    height: 0;
  }}

  .legend-title {{
    font-size: 13px;
    font-weight: 700;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
    margin-top: 16px;
  }}
  .legend-title:first-child {{ margin-top: 0; }}

  .legend-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border-radius: 6px;
    margin-bottom: 4px;
    cursor: pointer;
    transition: background 0.2s;
  }}
  .legend-item:hover {{ background: #21262d; }}
  .legend-dot {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .legend-label {{ font-size: 13px; color: #e6edf3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .legend-count {{
    margin-left: auto;
    font-size: 11px;
    color: #6e7681;
    background: #21262d;
    padding: 1px 6px;
    border-radius: 10px;
  }}

  #search {{
    width: 100%;
    background: #0d1117;
    border: 1px solid #30363d;
    color: #e6edf3;
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 13px;
    outline: none;
    margin-bottom: 8px;
  }}
  #search:focus {{ border-color: #FF6B35; }}

  #node-detail {{
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px;
    margin-top: 16px;
    display: none;
  }}
  #node-detail h3 {{ font-size: 14px; font-weight: 600; color: #FF6B35; margin-bottom: 8px; }}
  #node-detail p {{ font-size: 12px; color: #8b949e; line-height: 1.55; white-space: pre-wrap; }}
  #node-detail .node-type {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    margin-bottom: 6px;
  }}

  .controls {{
    position: absolute;
    bottom: 20px;
    left: 20px;
    display: flex;
    gap: 8px;
    z-index: 2;
  }}
  .ctrl-btn {{
    background: #21262d;
    border: 1px solid #30363d;
    color: #e6edf3;
    padding: 8px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
  }}
  .ctrl-btn:hover {{ background: #30363d; border-color: #FF6B35; }}

  .stats-bar {{
    position: absolute;
    top: 16px;
    left: 16px;
    display: flex;
    gap: 12px;
    z-index: 2;
  }}
  .stat-chip {{
    background: rgba(33,38,45,0.9);
    border: 1px solid #30363d;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    color: #8b949e;
  }}
  .stat-chip span {{ color: #FF6B35; font-weight: 700; }}
</style>
</head>
<body>

<div id="header">
  <div>
    <h1>{title}</h1>
    <p>{subtitle}</p>
  </div>
</div>

<div id="main">
  <div id="network-container">
    <div class="stats-bar">
      <div class="stat-chip">노드 <span>{payload["nodes"]}</span></div>
      <div class="stat-chip">엣지 <span>{payload["edges"]}</span></div>
      <div class="stat-chip">그룹 <span>{payload["groups"]}</span></div>
    </div>
    <div id="mynetwork"></div>
    <div class="controls">
      <button class="ctrl-btn" onclick="network.fit()">전체 보기</button>
      <button class="ctrl-btn" onclick="stabilize()">레이아웃 재정렬</button>
      <button class="ctrl-btn" onclick="filterGroup(null)">필터 해제</button>
    </div>
  </div>

  <div id="sidebar">
    <div class="legend-title">검색</div>
    <input id="search" type="search" placeholder="노드 이름 검색…" autocomplete="off">

    <div class="legend-title">그룹 범례</div>
    <div id="legend"></div>

    <div id="node-detail">
      <div class="node-type" id="detail-type"></div>
      <h3 id="detail-title"></h3>
      <p id="detail-desc"></p>
    </div>
  </div>
</div>

<script>
const DATA = {data_json};
const rawNodes = DATA.rawNodes;
const rawEdges = DATA.rawEdges;
const nodeDescriptions = DATA.descriptions;
const legend = DATA.legend;

function darkenColor(hex, factor) {{
  const r = Math.floor(parseInt(hex.slice(1,3), 16) * (1-factor));
  const g = Math.floor(parseInt(hex.slice(3,5), 16) * (1-factor));
  const b = Math.floor(parseInt(hex.slice(5,7), 16) * (1-factor));
  return `rgb(${{r}},${{g}},${{b}})`;
}}
function lightenColor(hex, factor) {{
  const r = Math.min(255, Math.floor(parseInt(hex.slice(1,3), 16) + 255 * factor));
  const g = Math.min(255, Math.floor(parseInt(hex.slice(3,5), 16) + 255 * factor));
  const b = Math.min(255, Math.floor(parseInt(hex.slice(5,7), 16) + 255 * factor));
  return `rgb(${{r}},${{g}},${{b}})`;
}}

const legendEl = document.getElementById('legend');
legend.forEach(item => {{
  const div = document.createElement('div');
  div.className = 'legend-item';
  div.onclick = () => filterGroup(item.id);
  div.innerHTML = `<div class="legend-dot" style="background:${{item.color}}"></div>` +
    `<span class="legend-label" title="${{item.label}}">${{item.label}}</span>` +
    `<span class="legend-count">${{item.count}}</span>`;
  legendEl.appendChild(div);
}});
const allItem = document.createElement('div');
allItem.className = 'legend-item';
allItem.onclick = () => filterGroup(null);
allItem.innerHTML = `<div class="legend-dot" style="background:#555"></div><span class="legend-label">전체 보기</span>`;
legendEl.appendChild(allItem);

const maxDeg = Math.max(...rawNodes.map(n => n.degree || 1), 1);
const visNodes = rawNodes.map(n => ({{
  id: n.id,
  label: n.label,
  group: n.group,
  size: n.size,
  color: {{
    background: n.color,
    border: darkenColor(n.color, 0.3),
    highlight: {{ background: lightenColor(n.color, 0.2), border: "#ffffff" }},
    hover: {{ background: lightenColor(n.color, 0.1), border: "#ffffff" }}
  }},
  font: {{
    color: '#fff',
    size: (n.degree || 1) >= maxDeg * 0.35 ? 12 : 0,
    face: 'Segoe UI',
    multi: true
  }},
  shadow: {{ enabled: true, color: n.color + '66', size: 8, x: 0, y: 0 }},
  borderWidth: 1.5,
  shape: 'dot',
  title: n.label.replace(/\\n/g, ' ')
}}));

const visEdges = rawEdges.map((e, i) => ({{
  id: i,
  from: e.from,
  to: e.to,
  label: e.label,
  color: {{
    color: e.color + '99',
    highlight: e.color,
    hover: e.color
  }},
  dashes: e.dashed || false,
  arrows: {{ to: {{ enabled: true, scaleFactor: 0.55 }} }},
  font: {{ size: 9, color: '#6e7681', align: 'middle', background: '#161b22', strokeWidth: 0 }},
  width: e.dashed ? 1 : 1.5,
  smooth: {{ type: 'curvedCCW', roundness: 0.18 }},
  title: e.label + (e.confidence ? ` [${{e.confidence}}]` : '')
}}));

const container = document.getElementById('mynetwork');
const networkData = {{
  nodes: new vis.DataSet(visNodes),
  edges: new vis.DataSet(visEdges)
}};

const options = {{
  physics: {{
    enabled: true,
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {{
      gravitationalConstant: -90,
      centralGravity: 0.012,
      springLength: 140,
      springConstant: 0.06,
      damping: 0.5,
      avoidOverlap: 0.7
    }},
    stabilization: {{ enabled: true, iterations: 180, updateInterval: 25 }}
  }},
  interaction: {{
    hover: true,
    tooltipDelay: 120,
    zoomView: true,
    dragView: true,
    keyboard: {{ enabled: true, bindToWindow: false }}
  }},
  layout: {{ improvedLayout: true }}
}};

const network = new vis.Network(container, networkData, options);
container.style.outline = 'none';
container.setAttribute('tabindex', '0');
container.addEventListener('mousedown', () => {{ container.style.outline = 'none'; }});

network.on("click", function(params) {{
  if (params.nodes.length === 0) return;
  const nodeId = params.nodes[0];
  const node = rawNodes.find(n => n.id === nodeId);
  const leg = legend.find(l => l.id === node.group);
  const detail = document.getElementById('node-detail');
  const typeEl = document.getElementById('detail-type');
  const titleEl = document.getElementById('detail-title');
  const descEl = document.getElementById('detail-desc');

  typeEl.textContent = leg ? leg.label : (`그룹 ${{node.group}}`);
  typeEl.style.background = node.color + '33';
  typeEl.style.color = node.color;
  typeEl.style.border = `1px solid ${{node.color}}66`;
  titleEl.textContent = node.label.replace(/\\n/g, ' ');
  descEl.textContent = nodeDescriptions[nodeId] || '관련 설명이 없습니다.';
  detail.style.display = 'block';
}});

network.on("hoverNode", () => {{ container.style.cursor = 'pointer'; }});
network.on("blurNode", () => {{ container.style.cursor = 'default'; }});

network.once("stabilizationIterationsDone", function() {{
  if (DATA.hub) {{
    network.focus(DATA.hub, {{ scale: 0.85, animation: {{ duration: 800 }} }});
  }} else {{
    network.fit();
  }}
}});

function filterGroup(group) {{
  if (!group) {{
    networkData.nodes.update(rawNodes.map(n => ({{ id: n.id, hidden: false, opacity: 1 }})));
    return;
  }}
  networkData.nodes.update(rawNodes.map(n => ({{
    id: n.id,
    hidden: n.group !== group,
    opacity: n.group === group ? 1 : 0.12
  }})));
}}

function stabilize() {{
  network.startSimulation();
  setTimeout(() => {{ network.stopSimulation(); network.fit(); }}, 2000);
}}

document.getElementById('search').addEventListener('input', (ev) => {{
  const q = (ev.target.value || '').trim().toLowerCase();
  if (!q) {{
    networkData.nodes.update(rawNodes.map(n => ({{ id: n.id, hidden: false }})));
    return;
  }}
  const hits = [];
  networkData.nodes.update(rawNodes.map(n => {{
    const hit = (n.label || '').toLowerCase().includes(q) || String(n.id).toLowerCase().includes(q);
    if (hit) hits.push(n.id);
    return {{ id: n.id, hidden: !hit }};
  }}));
  if (hits.length === 1) network.focus(hits[0], {{ scale: 1.1, animation: true }});
}});
</script>
</body>
</html>
"""
