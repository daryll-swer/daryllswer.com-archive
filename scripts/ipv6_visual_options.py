#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Build alternate IPv6 subnetting visualisation prototypes from CSV data."""

from __future__ import annotations

import html
import json
import math
from collections import defaultdict
from pathlib import Path

from font_assets import FONT_BODY_STACK, FONT_HEADING_STACK, font_face_css
from ipv6_hierarchy import (
    artefact_info,
    attach_children,
    count_nodes,
    max_depth,
    prune_empty_children,
    read_prefix_rows,
)


OPTION_IDS = [
    "branch-cards",
    "collapsible-dendrogram",
    "purpose-cluster-graph",
]

OPTION_TITLES = {
    "branch-cards": "Branch cards",
    "collapsible-dendrogram": "Collapsible dendrogram",
    "purpose-cluster-graph": "Purpose cluster graph",
}

OPTION_SUMMARIES = {
    "branch-cards": "Operational branches with ancestry, child allocations, and notes grouped together.",
    "collapsible-dendrogram": "Expandable left-to-right hierarchy so readers can reveal only the branch they are inspecting.",
    "purpose-cluster-graph": "Interactive node-link graph clustered by operational purpose rather than pure prefix depth.",
}

BRANCH_VISIBLE_CHILDREN = 12

CATEGORY_ORDER = [
    "Loopback",
    "OOB and management",
    "Interconnect",
    "Content and CDN",
    "Service and routed pools",
    "Network device roles",
    "Geography and sites",
    "Reserved",
    "Other planning",
]


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def node_key(node: dict) -> str:
    return str(node.get("prefix") or "")


def flatten_tree(tree: dict) -> list[dict]:
    rows: list[dict] = []

    def visit(node: dict, parent: dict | None, depth: int, path: list[dict]) -> None:
        current_path = path + [node]
        row = dict(node)
        children = row.pop("children", [])
        row["parent"] = node_key(parent) if parent else ""
        row["depth"] = depth
        row["child_count"] = len(children)
        row["path"] = current_path
        rows.append(row)
        for child in children:
            visit(child, node, depth + 1, current_path)

    visit(tree, None, 0, [])
    return rows


def label_for(node: dict) -> str:
    return str(node.get("label") or node.get("source_sheet") or node.get("notes") or "").strip()


def notes_for(node: dict) -> str:
    return str(node.get("notes") or "").strip()


def category_for(node: dict) -> str:
    text = " ".join(str(node.get(key) or "") for key in ["label", "notes", "source_sheet"]).lower()
    if "reserved" in text:
        return "Reserved"
    if "loopback" in text:
        return "Loopback"
    if "oob" in text or "mgmt" in text or "management" in text:
        return "OOB and management"
    if "ptp" in text or "interconnect" in text or "interconnection" in text or "peer" in text or "pni" in text:
        return "Interconnect"
    if "cache" in text or "caching" in text or "akamai" in text or "cloudflare" in text or "netflix" in text or "google" in text or "meta" in text or "amazon" in text or "cdn" in text:
        return "Content and CDN"
    if "docker" in text or "vpn" in text or "cloud" in text or "routed" in text or "customer" in text or "employee" in text:
        return "Service and routed pools"
    if "edge" in text or "bng" in text or "router" in text or "switch" in text or "transport" in text or "pe " in text or " p " in text:
        return "Network device roles"
    if "india" in text or "delhi" in text or "chandigarh" in text or "site" in text or "zone" in text:
        return "Geography and sites"
    return "Other planning"


def category_slug(category: str) -> str:
    return category.lower().replace(" and ", "-").replace(" ", "-")


def prefix_chip(node: dict, *, small: bool = False) -> str:
    label = label_for(node)
    cat = category_slug(category_for(node))
    size_class = " chip-small" if small else ""
    label_html = f'<span class="chip-label">{html_escape(label)}</span>' if label else ""
    child_html = f'<span class="chip-count">{int(node.get("child_count") or 0)} children</span>' if node.get("child_count") else ""
    return (
        f'<span class="prefix-chip {cat}{size_class}">'
        f'<code>{html_escape(node.get("prefix", ""))}</code>'
        f"{label_html}{child_html}"
        "</span>"
    )


def path_summary(node: dict) -> str:
    parts = [item for item in node.get("path", []) if item.get("prefix")]
    return '<div class="path-summary">' + "".join(prefix_chip(item, small=True) for item in parts) + "</div>"


def notes_html(node: dict, class_name: str) -> str:
    notes = notes_for(node)
    return f'<p class="{class_name}">{html_escape(notes)}</p>' if notes else ""


def child_summary(node: dict) -> str:
    return (
        '<div class="child-item">'
        f"{prefix_chip(node, small=True)}"
        f"{notes_html(node, 'child-note')}"
        "</div>"
    )


def child_disclosure(children: list[dict]) -> str:
    visible = "".join(child_summary(child) for child in children[:BRANCH_VISIBLE_CHILDREN])
    hidden_children = children[BRANCH_VISIBLE_CHILDREN:]
    more = ""
    if hidden_children:
        hidden = "".join(child_summary(child) for child in hidden_children)
        more = (
            '<details class="branch-more">'
            '<summary>'
            '<span class="more-count">'
            f'<span class="more-open-label">+{len(hidden_children)} more</span>'
            '<span class="more-close-label">Show fewer</span>'
            '</span>'
            '</summary>'
            f'<div class="child-preview branch-more-items">{hidden}</div>'
            '</details>'
        )
    return f'<div class="branch-children"><div class="child-preview">{visible}</div>{more}</div>'


def terminal_nodes(nodes: list[dict]) -> list[dict]:
    return [node for node in nodes if int(node.get("child_count") or 0) == 0]


def direct_children(parent: dict, nodes: list[dict]) -> list[dict]:
    parent_prefix = node_key(parent)
    return [node for node in nodes if node.get("parent") == parent_prefix]


def sort_nodes(nodes: list[dict]) -> list[dict]:
    return sorted(nodes, key=lambda node: (int(node.get("depth") or 0), node_key(node)))


def short_prefix(prefix: object) -> str:
    text = str(prefix or "")
    if len(text) <= 24:
        return text
    if "/" in text:
        base, length = text.rsplit("/", 1)
        return f"{base[:18]}.../{length}"
    return text[:21] + "..."


def json_payload(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def graph_data(nodes: list[dict]) -> dict:
    payload_nodes = []
    for node in sort_nodes(nodes):
        prefix = node_key(node)
        payload_nodes.append(
            {
                "id": prefix,
                "prefix": prefix,
                "shortPrefix": short_prefix(prefix),
                "label": label_for(node),
                "notes": notes_for(node),
                "category": category_for(node),
                "categorySlug": category_slug(category_for(node)),
                "depth": int(node.get("depth") or 0),
                "prefixLength": int(node.get("prefix_length") or 0),
                "parent": node.get("parent") or "",
                "childCount": int(node.get("child_count") or 0),
                "path": [node_key(item) for item in node.get("path", []) if node_key(item)],
            }
        )
    return {"nodes": payload_nodes}


def node_lookup(nodes: list[dict]) -> dict[str, dict]:
    return {node_key(node): node for node in nodes if node_key(node)}


def graph_json_script(section_id: str, nodes: list[dict]) -> str:
    return (
        f'<script type="application/json" data-graph-data="{html_escape(section_id)}">'
        f"{json_payload(graph_data(nodes))}</script>"
    )


def graph_detail_panel() -> str:
    return (
        '<aside class="node-detail" data-node-detail>'
        "<h3>Select a prefix</h3>"
        "<p>Click a node to highlight its ancestry, immediate children, and metadata.</p>"
        "</aside>"
    )


def graph_mark_attrs(node: dict) -> str:
    path = " ".join(node_key(item) for item in node.get("path", []) if node_key(item))
    return (
        f'data-id="{html_escape(node_key(node))}" '
        f'data-parent="{html_escape(node.get("parent") or "")}" '
        f'data-path="{html_escape(path)}" '
        f'data-category="{html_escape(category_for(node))}"'
    )


def base_css(font_asset_prefix: str) -> str:
    return f"""{font_face_css(font_asset_prefix)}
* {{ box-sizing: border-box; }}
:root {{
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-alt: #edf2f7;
  --surface-strong: #e3ebf2;
  --text: #17202a;
  --muted: #5f6c78;
  --border: #d5dde6;
  --grid: #c7d1dc;
  --accent: #0b6f8a;
  --loopback: #1d6f42;
  --oob: #315ea8;
  --interconnect: #8a5a00;
  --cdn: #7c4d9e;
  --service: #b84b5a;
  --role: #0b6f8a;
  --geo: #626d1f;
  --reserved: #7b8290;
  --other: #50616f;
  --font-body: {FONT_BODY_STACK};
  --font-heading: {FONT_HEADING_STACK};
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #101418;
    --surface: #171d23;
    --surface-alt: #222b35;
    --surface-strong: #2a3440;
    --text: #edf2f7;
    --muted: #aab5c1;
    --border: #34404d;
    --grid: #445363;
    --accent: #6cc7df;
    --loopback: #87d19a;
    --oob: #9bbcff;
    --interconnect: #e4bd65;
    --cdn: #cfaae6;
    --service: #f39aa6;
    --role: #6cc7df;
    --geo: #c9d36c;
    --reserved: #b1bac5;
    --other: #b8c6d3;
  }}
}}
body {{
  margin: 0;
  min-width: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.55;
}}
a {{ color: var(--accent); text-underline-offset: .18em; }}
.page-header, main, footer {{
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: clamp(.85rem, 1.8vw, 1.35rem);
}}
.page-header {{
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  border-bottom: 1px solid var(--border);
}}
.eyebrow {{
  margin: 0 0 .45rem;
  color: var(--muted);
  font-size: .82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}}
h1 {{
  margin: 0;
  max-width: 900px;
  font-family: var(--font-heading);
  font-size: clamp(1.8rem, 4vw, 3.1rem);
  line-height: 1.12;
  letter-spacing: 0;
}}
h2, h3 {{
  font-family: var(--font-heading);
  line-height: 1.2;
  letter-spacing: 0;
}}
.summary {{ max-width: 780px; color: var(--muted); }}
.actions, .option-nav {{
  display: flex;
  gap: .55rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}}
.actions a, .option-nav a, .open-option {{
  display: inline-flex;
  align-items: center;
  min-height: 2.25rem;
  padding: .4rem .7rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  text-decoration: none;
  font-weight: 700;
}}
.option-nav {{
  justify-content: flex-start;
  margin: 1rem 0;
}}
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
  gap: .75rem;
  margin: 1rem 0;
  min-width: 0;
}}
.metric {{
  min-width: 0;
  padding: .8rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
.metric strong {{
  display: block;
  min-width: 0;
  font-size: 1.35rem;
  overflow-wrap: anywhere;
  word-break: break-word;
}}
.option-section {{
  margin: 1.25rem 0 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  min-width: 0;
}}
.visual-frame {{
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow: auto;
  overscroll-behavior-inline: contain;
  -webkit-overflow-scrolling: touch;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
.prefix-chip {{
  display: inline-flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: .35rem;
  min-height: 1.75rem;
  min-width: 0;
  max-width: 100%;
  padding: .22rem .5rem;
  border: 1px solid var(--border);
  border-left: .32rem solid var(--other);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  overflow-wrap: anywhere;
  white-space: normal;
}}
.prefix-chip code {{
  min-width: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .86rem;
  overflow-wrap: anywhere;
  word-break: break-word;
}}
.chip-small {{ min-height: 1.45rem; padding: .12rem .36rem; font-size: .82rem; }}
.chip-label, .chip-count {{
  min-width: 0;
  color: var(--muted);
  font-size: .82rem;
  overflow-wrap: anywhere;
}}
.reserved {{ border-left-color: var(--reserved); opacity: .78; }}
.loopback {{ border-left-color: var(--loopback); }}
.oob-management {{ border-left-color: var(--oob); }}
.interconnect {{ border-left-color: var(--interconnect); }}
.content-cdn {{ border-left-color: var(--cdn); }}
.service-routed-pools {{ border-left-color: var(--service); }}
.network-device-roles {{ border-left-color: var(--role); }}
.geography-sites {{ border-left-color: var(--geo); }}
.other-planning {{ border-left-color: var(--other); }}
.path-summary {{
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
  min-width: 0;
}}
footer {{ color: var(--muted); font-size: .92rem; }}
@media (max-width: 760px) {{
  .page-header {{ flex-direction: column; }}
  .actions {{ justify-content: flex-start; }}
  .visual-frame {{ padding: .75rem; }}
}}
"""


def branch_cards(nodes: list[dict]) -> str:
    candidates = [
        node for node in nodes
        if node.get("prefix_length") in {44, 48, 52, 56}
        and (node.get("child_count") or 0) > 0
        and category_for(node) != "Reserved"
    ]
    cards = []
    for node in candidates[:36]:
        children = direct_children(node, nodes)
        cards.append(
            '<article class="branch-card">'
            f'<h3>{html_escape(label_for(node) or node.get("prefix", ""))}</h3>'
            f'{path_summary(node)}'
            f"{notes_html(node, 'branch-note')}"
            f"{child_disclosure(children)}"
            "</article>"
        )
    return f"""
<section class="option-section" id="branch-cards">
  <h2>Option 1: Branch cards</h2>
  <p class="summary">This favours operator readability over total density: each meaningful branch keeps its lineage, intent, notes, and immediate children together.</p>
  <div class="visual-frame"><div class="branch-grid">{"".join(cards)}</div></div>
</section>
"""


def purpose_cluster_positions(nodes: list[dict]) -> tuple[dict[str, tuple[float, float]], int, int]:
    width = 1060
    height = 820
    positions: dict[str, tuple[float, float]] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        grouped[category_for(node)].append(node)
    centers: dict[str, tuple[float, float]] = {}
    for index, category in enumerate(CATEGORY_ORDER):
        col = index % 3
        row = index // 3
        centers[category] = (180 + col * 350, 150 + row * 245)
    golden_angle = math.pi * (3 - math.sqrt(5))
    for category in CATEGORY_ORDER:
        items = sorted(grouped.get(category, []), key=lambda node: (int(node.get("depth") or 0), node_key(node)))
        center_x, center_y = centers[category]
        for index, node in enumerate(items):
            if index == 0:
                positions[node_key(node)] = (center_x, center_y)
                continue
            radius = 15 + 13 * math.sqrt(index)
            angle = index * golden_angle
            positions[node_key(node)] = (
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius,
            )
    return positions, width, height


def graph_svg(nodes: list[dict], positions: dict[str, tuple[float, float]], width: int, height: int, *, show_node_labels: bool = False, label_depth: int = 1) -> str:
    node_map = node_lookup(nodes)
    edges = []
    marks = []
    for node in sort_nodes(nodes):
        prefix = node_key(node)
        parent = node.get("parent") or ""
        if parent in positions and prefix in positions:
            x1, y1 = positions[parent]
            x2, y2 = positions[prefix]
            edges.append(
                f'<line class="graph-edge" data-parent="{html_escape(parent)}" data-child="{html_escape(prefix)}" '
                f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"></line>'
            )
    for node in sort_nodes(nodes):
        prefix = node_key(node)
        if prefix not in positions:
            continue
        x, y = positions[prefix]
        depth = int(node.get("depth") or 0)
        child_count = int(node.get("child_count") or 0)
        radius = max(4.6, min(12.5, 10 - depth + math.sqrt(child_count + 1) * 0.9))
        cat = category_slug(category_for(node))
        label = ""
        if show_node_labels and (depth <= label_depth or child_count >= 8):
            label = f'<text class="graph-node-label" x="{x + radius + 4:.1f}" y="{y + 4:.1f}">{html_escape(short_prefix(prefix))}</text>'
        initial = ' data-initial="true"' if depth == 0 else ""
        marks.append(
            f'<g class="graph-mark {cat}" {graph_mark_attrs(node_map[prefix])}{initial} tabindex="0" role="button">'
            f'<title>{html_escape(prefix)} - {html_escape(label_for(node) or category_for(node))}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}"></circle>'
            f"{label}</g>"
        )
    return (
        f'<svg class="graph-canvas" viewBox="0 0 {width} {height}" role="img" aria-label="IPv6 prefix graph">'
        f'{"".join(edges)}{"".join(marks)}</svg>'
    )


def collapsible_dendrogram(tree: dict) -> str:
    def render_node(node: dict, depth: int) -> str:
        children = node.get("children", [])
        cat = category_slug(category_for(node))
        node_with_count = {**node, "child_count": len(children)}
        open_attr = " open" if depth <= 1 else ""
        leaf_class = " leaf" if not children else ""
        children_html = "".join(render_node(child, depth + 1) for child in children)
        return (
            f'<details class="tree-node {cat}{leaf_class}"{open_attr}>'
            f'<summary>{prefix_chip(node_with_count, small=True)}{notes_html(node, "tree-note")}</summary>'
            f"{children_html}</details>"
        )

    return f"""
<section class="option-section" id="collapsible-dendrogram" data-dendrogram-section>
  <h2>Option 2: Collapsible dendrogram</h2>
  <p class="summary">This is still a tree, but the reader controls complexity by expanding only the branch they care about.</p>
  <div class="visual-frame">
    <div class="tree-toolbar">
      <button type="button" data-tree-expand>Expand all</button>
      <button type="button" data-tree-collapse>Collapse all</button>
    </div>
    <div class="dendrogram-tree">{render_node(tree, 0)}</div>
  </div>
</section>
"""


def purpose_cluster_graph(nodes: list[dict]) -> str:
    positions, width, height = purpose_cluster_positions(nodes)
    labels = []
    for category in CATEGORY_ORDER:
        grouped_nodes = [node for node in nodes if category_for(node) == category]
        if not grouped_nodes:
            continue
        xs = [positions[node_key(node)][0] for node in grouped_nodes if node_key(node) in positions]
        ys = [positions[node_key(node)][1] for node in grouped_nodes if node_key(node) in positions]
        if not xs or not ys:
            continue
        labels.append(
            f'<text class="graph-category-label" x="{sum(xs) / len(xs):.1f}" y="{min(ys) - 34:.1f}" text-anchor="middle">{html_escape(category)}</text>'
        )
    section_id = "purpose-cluster-graph"
    return f"""
<section class="option-section" id="{section_id}" data-graph-section>
  <h2>Option 3: Purpose cluster graph</h2>
  <p class="summary">This keeps node links, but clusters prefixes by operational purpose so the design intent is visible before the exact hierarchy.</p>
  <div class="visual-frame">
    <div class="interactive-grid">
      <div>
        {graph_svg(nodes, positions, width, height, show_node_labels=False).replace("</svg>", "".join(labels) + "</svg>")}
      </div>
      {graph_detail_panel()}
    </div>
  </div>
  {graph_json_script(section_id, nodes)}
</section>
"""


def option_css() -> str:
    return """
.branch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));
  gap: .85rem;
}
.branch-card {
  display: grid;
  gap: .65rem;
  align-content: start;
  min-width: 0;
  overflow: hidden;
  padding: .85rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
}
.branch-card h3 { margin: 0; font-size: 1.05rem; }
.branch-card p { margin: 0; color: var(--muted); overflow-wrap: anywhere; }
.branch-children {
  display: grid;
  gap: .55rem;
  min-width: 0;
}
.child-preview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
  gap: .5rem;
  min-width: 0;
  align-items: start;
}
.child-item {
  display: grid;
  gap: .28rem;
  min-width: 0;
  padding: .42rem;
  border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface) 72%, transparent);
}
.child-item .prefix-chip {
  display: grid;
  grid-template-columns: 1fr;
  justify-items: start;
  width: 100%;
}
.branch-note,
.child-note,
.tree-note {
  color: var(--muted);
  font-size: .84rem;
  line-height: 1.38;
  overflow-wrap: anywhere;
}
.child-note {
  padding-left: .2rem;
}
.branch-more {
  min-width: 0;
}
.branch-more summary {
  display: inline-flex;
  max-width: 100%;
  cursor: pointer;
  list-style: none;
}
.branch-more summary::-webkit-details-marker {
  display: none;
}
.branch-more summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  border-radius: 6px;
}
.branch-more-items {
  margin-top: .55rem;
}
.more-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 1.45rem;
  padding: .12rem .45rem;
  border: 1px dashed var(--grid);
  border-radius: 6px;
  color: var(--muted);
  font-size: .82rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.branch-more[open] .more-count {
  border-style: solid;
  color: var(--text);
  background: var(--surface);
}
.more-close-label {
  display: none;
}
.branch-more[open] .more-open-label {
  display: none;
}
.branch-more[open] .more-close-label {
  display: inline;
}
.option-picker {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: .85rem;
  margin: 1rem 0 1.5rem;
}
.option-card {
  display: grid;
  gap: .65rem;
  padding: .9rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.option-card h2 { margin: 0; font-size: 1.15rem; }
.option-card p { margin: 0; color: var(--muted); }
.interactive-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(min(100%, 18rem), 24rem);
  gap: 1rem;
  align-items: start;
  min-width: 0;
}
.graph-canvas {
  display: block;
  min-width: 48rem;
  width: 100%;
  height: auto;
  border-radius: 8px;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--grid) 28%, transparent) 1px, transparent 1px),
    linear-gradient(0deg, color-mix(in srgb, var(--grid) 28%, transparent) 1px, transparent 1px),
    var(--surface-alt);
  background-size: 4rem 4rem;
}
.graph-canvas text {
  fill: var(--text);
  font-family: var(--font-body);
  font-size: .74rem;
  pointer-events: none;
}
.graph-category-label {
  font-weight: 800;
  paint-order: stroke;
  stroke: var(--surface-alt);
  stroke-width: 5px;
  stroke-linejoin: round;
}
.graph-edge {
  stroke: color-mix(in srgb, var(--grid) 72%, transparent);
  stroke-width: 1.2;
}
.graph-mark {
  cursor: pointer;
  outline: none;
}
.graph-mark circle,
.graph-mark path,
.graph-mark rect {
  transition: opacity .18s ease, stroke-width .18s ease, transform .18s ease;
}
.graph-mark circle {
  fill: var(--other);
  stroke: var(--surface);
  stroke-width: 1.4;
}
.graph-mark path,
.graph-mark rect {
  fill: var(--other);
  stroke: var(--surface);
  stroke-width: .7;
}
.graph-mark.loopback circle,
.graph-mark.loopback path,
.graph-mark.loopback rect { fill: var(--loopback); }
.graph-mark.oob-management circle,
.graph-mark.oob-management path,
.graph-mark.oob-management rect { fill: var(--oob); }
.graph-mark.interconnect circle,
.graph-mark.interconnect path,
.graph-mark.interconnect rect { fill: var(--interconnect); }
.graph-mark.content-cdn circle,
.graph-mark.content-cdn path,
.graph-mark.content-cdn rect { fill: var(--cdn); }
.graph-mark.service-routed-pools circle,
.graph-mark.service-routed-pools path,
.graph-mark.service-routed-pools rect { fill: var(--service); }
.graph-mark.network-device-roles circle,
.graph-mark.network-device-roles path,
.graph-mark.network-device-roles rect { fill: var(--role); }
.graph-mark.geography-sites circle,
.graph-mark.geography-sites path,
.graph-mark.geography-sites rect { fill: var(--geo); }
.graph-mark.reserved circle,
.graph-mark.reserved path,
.graph-mark.reserved rect { fill: var(--reserved); }
.graph-canvas.has-selection .graph-mark:not(.is-selected):not(.is-path):not(.is-child),
.graph-canvas.has-selection .graph-edge:not(.is-path) {
  opacity: .18;
}
.graph-mark.is-selected circle,
.graph-mark.is-selected path,
.graph-mark.is-selected rect {
  stroke: var(--text);
  stroke-width: 3;
}
.graph-mark.is-path circle,
.graph-mark.is-path path,
.graph-mark.is-path rect {
  stroke: var(--accent);
  stroke-width: 2.4;
}
.graph-mark.is-child circle,
.graph-mark.is-child path,
.graph-mark.is-child rect {
  stroke: var(--text);
  stroke-width: 2;
}
.graph-edge.is-path {
  stroke: var(--accent);
  stroke-width: 2.5;
  opacity: 1;
}
.node-detail,
.interaction-panel {
  display: grid;
  gap: .6rem;
  padding: .9rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
}
.node-detail h3,
.interaction-panel h3 {
  margin: 0;
  font-size: 1.05rem;
}
.node-detail p,
.interaction-panel p { margin: 0; color: var(--muted); }
.detail-grid {
  display: grid;
  gap: .35rem;
  font-size: .9rem;
}
.detail-grid div {
  display: grid;
  grid-template-columns: minmax(6.5rem, max-content) minmax(0, 1fr);
  gap: .8rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: .25rem;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { min-width: 0; margin: 0; text-align: right; overflow-wrap: anywhere; }
.detail-grid code { overflow-wrap: anywhere; word-break: break-word; }
.detail-grid .detail-notes {
  grid-template-columns: 1fr;
}
.detail-grid .detail-notes dd {
  text-align: left;
}
.tree-toolbar {
  display: flex;
  align-items: center;
  gap: .55rem;
  flex-wrap: wrap;
  margin: 0 0 .85rem;
}
.tree-toolbar button {
  min-height: 2rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.dendrogram-tree {
  min-width: min(42rem, 100%);
  display: grid;
  gap: .35rem;
}
.tree-node {
  margin-left: 1rem;
  padding-left: .75rem;
  border-left: 1px solid var(--grid);
}
.tree-node summary {
  display: flex;
  align-items: flex-start;
  gap: .5rem;
  min-height: 2rem;
  cursor: pointer;
  list-style: none;
  flex-wrap: wrap;
}
.tree-node summary::-webkit-details-marker { display: none; }
.tree-node summary::before {
  content: "+";
  display: inline-grid;
  place-items: center;
  width: 1.3rem;
  height: 1.3rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  flex: 0 0 auto;
  margin-top: .08rem;
}
.tree-node[open] > summary::before { content: "-"; }
.tree-node.leaf summary::before { content: ""; border-style: dashed; }
.tree-note {
  flex: 1 1 18rem;
  margin: .12rem 0 0;
}
@media (max-width: 980px) {
  .interactive-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .branch-grid { grid-template-columns: 1fr; }
  .child-preview { grid-template-columns: 1fr; }
}
@media (min-width: 1600px) {
  .branch-grid {
    grid-template-columns: repeat(auto-fit, minmax(24rem, 1fr));
  }
}
@media (max-width: 480px) {
  .branch-card,
  .node-detail,
  .interaction-panel {
    padding: .7rem;
  }
  .tree-node {
    margin-left: .45rem;
    padding-left: .45rem;
  }
  .graph-canvas {
    min-width: 42rem;
  }
}
"""


def interactive_js() -> str:
    return r"""
(() => {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));

  const dataFor = (section) => {
    const script = section.querySelector("script[type='application/json'][data-graph-data]");
    if (!script) return { nodes: [] };
    try { return JSON.parse(script.textContent); }
    catch { return { nodes: [] }; }
  };

  const detailHtml = (node) => `
    <h3>${esc(node.shortPrefix || node.prefix)}</h3>
    <p>${esc(node.label || node.category || "No label")}</p>
    <dl class="detail-grid">
      <div><dt>Prefix</dt><dd><code>${esc(node.prefix)}</code></dd></div>
      <div><dt>Prefix length</dt><dd>/${esc(node.prefixLength)}</dd></div>
      <div><dt>Purpose</dt><dd>${esc(node.category)}</dd></div>
      <div><dt>Children</dt><dd>${esc(node.childCount)}</dd></div>
      <div><dt>Parent</dt><dd>${node.parent ? `<code>${esc(node.parent)}</code>` : "root"}</dd></div>
      ${node.notes ? `<div class="detail-notes"><dt>Notes</dt><dd>${esc(node.notes)}</dd></div>` : ""}
    </dl>
  `;

  const initGraphSection = (section) => {
    const data = dataFor(section);
    const byId = new Map(data.nodes.map((node) => [node.id, node]));
    const canvas = section.querySelector(".graph-canvas");
    const panel = section.querySelector("[data-node-detail]");
    if (!canvas || !panel || byId.size === 0) return;
    const marks = Array.from(section.querySelectorAll(".graph-mark[data-id]"));
    const edges = Array.from(section.querySelectorAll(".graph-edge[data-parent][data-child]"));
    const select = (id) => {
      const node = byId.get(id);
      if (!node) return;
      const path = new Set(node.path || []);
      const children = new Set(data.nodes.filter((item) => item.parent === id).map((item) => item.id));
      canvas.classList.add("has-selection");
      marks.forEach((mark) => {
        const markId = mark.dataset.id;
        mark.classList.toggle("is-selected", markId === id);
        mark.classList.toggle("is-path", path.has(markId) && markId !== id);
        mark.classList.toggle("is-child", children.has(markId));
      });
      edges.forEach((edge) => {
        edge.classList.toggle("is-path", path.has(edge.dataset.parent) && path.has(edge.dataset.child));
      });
      panel.innerHTML = detailHtml(node);
    };
    marks.forEach((mark) => {
      mark.addEventListener("click", () => select(mark.dataset.id));
      mark.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select(mark.dataset.id);
        }
      });
    });
    const initial = marks.find((mark) => mark.dataset.initial === "true") || marks[0];
    if (initial) select(initial.dataset.id);
  };

  const initDendrogram = (section) => {
    const expand = section.querySelector("[data-tree-expand]");
    const collapse = section.querySelector("[data-tree-collapse]");
    const details = Array.from(section.querySelectorAll("details.tree-node"));
    if (expand) expand.addEventListener("click", () => details.forEach((item) => { item.open = true; }));
    if (collapse) collapse.addEventListener("click", () => details.forEach((item) => { item.open = false; }));
  };

  document.querySelectorAll("[data-graph-section]").forEach(initGraphSection);
  document.querySelectorAll("[data-dendrogram-section]").forEach(initDendrogram);
})();
"""


def nav_links(current: str | None = None) -> str:
    links = ['<a href="./">Workbook</a>', '<a href="cidr-hierarchy.html">Tree model</a>', '<a href="visual-options.html">Visual foundations</a>']
    for option_id in OPTION_IDS:
        if current == option_id:
            continue
        links.append(f'<a href="visual-option-{option_id}.html">{html_escape(OPTION_TITLES[option_id])}</a>')
    return "".join(links)


def metric_html(tree: dict, nodes: list[dict]) -> str:
    leaves = len(terminal_nodes(nodes))
    return f"""
<section class="metrics" aria-label="Model metrics">
  <div class="metric"><strong>{count_nodes(tree)}</strong><span>prefix nodes</span></div>
  <div class="metric"><strong>{max_depth(tree)}</strong><span>containment levels</span></div>
  <div class="metric"><strong>{leaves}</strong><span>terminal prefixes</span></div>
  <div class="metric"><strong>{html_escape(tree.get("prefix", ""))}</strong><span>root prefix</span></div>
</section>
"""


def page_shell(title: str, intro: str, body: str, *, font_asset_prefix: str, current: str | None = None) -> str:
    return f"""<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)}</title>
  <style>
{base_css(font_asset_prefix)}
{option_css()}
  </style>
</head>
<body>
  <header class="page-header">
    <div>
      <p class="eyebrow">AS141253 IPv6 visual foundation</p>
      <h1>{html_escape(title)}</h1>
      <p class="summary">{html_escape(intro)}</p>
    </div>
    <nav class="actions" aria-label="Visualisation actions">
      {nav_links(current)}
    </nav>
  </header>
  <main>
    {body}
  </main>
  <footer>
    <p>Generated from repository CSV files. These are the selected foundation models for the next IPv6 visualisation iteration.</p>
  </footer>
  <script>
{interactive_js()}
  </script>
</body>
</html>
"""


def all_sections(tree: dict, nodes: list[dict]) -> dict[str, str]:
    return {
        "branch-cards": branch_cards(nodes),
        "collapsible-dendrogram": collapsible_dendrogram(tree),
        "purpose-cluster-graph": purpose_cluster_graph(nodes),
    }


def render_index(tree: dict, nodes: list[dict], sections: dict[str, str], font_asset_prefix: str) -> str:
    cards = []
    for option_id in OPTION_IDS:
        cards.append(
            '<article class="option-card">'
            f'<h2>{html_escape(OPTION_TITLES[option_id])}</h2>'
            f'<p>{html_escape(OPTION_SUMMARIES[option_id])}</p>'
            f'<a class="open-option" href="visual-option-{option_id}.html">Open standalone</a>'
            f'<a class="open-option" href="#{option_id}">Jump on this page</a>'
            "</article>"
        )
    body = (
        metric_html(tree, nodes)
        + '<section class="option-picker" aria-label="Visual options">'
        + "".join(cards)
        + "</section>"
        + "".join(sections[option_id] for option_id in OPTION_IDS)
    )
    return page_shell(
        "AS141253 IPv6 Visual Foundations",
        "The three selected HTML/CSS/JS foundations for a final readable IPv6 subnetting model: branch cards, collapsible dendrogram, and purpose-cluster graph.",
        body,
        font_asset_prefix=font_asset_prefix,
    )


def build_ipv6_visual_options_artefacts(root: Path, out: Path, manifest: dict) -> dict:
    rows = read_prefix_rows(root, manifest)
    tree = prune_empty_children(attach_children(rows))
    nodes = flatten_tree(tree)
    sections = all_sections(tree, nodes)
    font_prefix = "../../../assets/fonts"

    index_body = render_index(tree, nodes, sections, font_prefix).encode("utf-8")
    index_info = artefact_info(root, out / "visual-options.html", index_body, "text/html; charset=utf-8")
    option_infos = []
    for option_id in OPTION_IDS:
        body = metric_html(tree, nodes) + sections[option_id]
        page = page_shell(
            f"{OPTION_TITLES[option_id]} - AS141253 IPv6 Visual Option",
            OPTION_SUMMARIES[option_id],
            body,
            font_asset_prefix=font_prefix,
            current=option_id,
        ).encode("utf-8")
        info = artefact_info(root, out / f"visual-option-{option_id}.html", page, "text/html; charset=utf-8")
        info.update({
            "id": option_id,
            "title": OPTION_TITLES[option_id],
            "summary": OPTION_SUMMARIES[option_id],
        })
        option_infos.append(info)

    return {
        "model": "generated_html_css_visual_options",
        "source": "CSV Prefix columns and rooted IPv6 prefix containment tree",
        "option_count": len(option_infos),
        "index": index_info,
        "options": option_infos,
    }
