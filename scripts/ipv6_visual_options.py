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
    "spatial-blocks",
    "level-lanes",
    "nibble-ladder",
    "branch-cards",
    "purpose-swimlanes",
    "radial-prefix-graph",
    "collapsible-dendrogram",
    "sunburst-map",
    "animated-walkthrough",
    "purpose-cluster-graph",
    "searchable-focus-graph",
]

OPTION_TITLES = {
    "spatial-blocks": "Spatial block map",
    "level-lanes": "Prefix length lanes",
    "nibble-ladder": "Nibble ladder",
    "branch-cards": "Branch cards",
    "purpose-swimlanes": "Purpose swimlanes",
    "radial-prefix-graph": "Radial prefix graph",
    "collapsible-dendrogram": "Collapsible dendrogram",
    "sunburst-map": "Sunburst allocation map",
    "animated-walkthrough": "Animated allocation walkthrough",
    "purpose-cluster-graph": "Purpose cluster graph",
    "searchable-focus-graph": "Searchable focus graph",
}

OPTION_SUMMARIES = {
    "spatial-blocks": "Nested allocation blocks for quick visual containment checks.",
    "level-lanes": "One horizontal lane per prefix length so hierarchy depth is visible at a glance.",
    "nibble-ladder": "Terminal prefixes as rows with ancestor columns for /32, /34, /40, /44, /48, /52, /56, and /64.",
    "branch-cards": "Operational branches with ancestry, child allocations, and notes grouped together.",
    "purpose-swimlanes": "Prefixes grouped by network purpose such as loopback, OOB, interconnect, CDN, reserved, and services.",
    "radial-prefix-graph": "Interactive graph-theory style rings where each ring is a hierarchy depth and clicks highlight ancestry.",
    "collapsible-dendrogram": "Expandable left-to-right hierarchy so readers can reveal only the branch they are inspecting.",
    "sunburst-map": "Interactive radial allocation map using arc spans to show relative branch density across hierarchy levels.",
    "animated-walkthrough": "Step-through walkthrough from the root allocation to terminal prefixes, with one active prefix length at a time.",
    "purpose-cluster-graph": "Interactive node-link graph clustered by operational purpose rather than pure prefix depth.",
    "searchable-focus-graph": "Search-first graph that expands only the selected prefix, its ancestry, siblings, and immediate children.",
}

PREFIX_LEVELS = [32, 34, 40, 44, 48, 52, 56, 64]
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
INTERACTIVE_OPTION_IDS = {
    "radial-prefix-graph",
    "collapsible-dendrogram",
    "sunburst-map",
    "animated-walkthrough",
    "purpose-cluster-graph",
    "searchable-focus-graph",
}


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
        "<p>Click a node, arc, or result to highlight its ancestry, immediate children, and metadata.</p>"
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
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.55;
}}
a {{ color: var(--accent); text-underline-offset: .18em; }}
.page-header, main, footer {{
  max-width: 1280px;
  margin: 0 auto;
  padding: 1rem 1.25rem;
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
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: .75rem;
  margin: 1rem 0;
}}
.metric {{
  padding: .8rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
.metric strong {{ display: block; font-size: 1.35rem; }}
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
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
.prefix-chip {{
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  min-height: 1.75rem;
  max-width: 100%;
  padding: .22rem .5rem;
  border: 1px solid var(--border);
  border-left: .32rem solid var(--other);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  white-space: nowrap;
}}
.prefix-chip code {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: .86rem;
}}
.chip-small {{ min-height: 1.45rem; padding: .12rem .36rem; font-size: .82rem; }}
.chip-label, .chip-count {{ color: var(--muted); font-size: .82rem; }}
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
}}
footer {{ color: var(--muted); font-size: .92rem; }}
@media (max-width: 760px) {{
  .page-header {{ flex-direction: column; }}
  .actions {{ justify-content: flex-start; }}
}}
"""


def spatial_blocks(tree: dict) -> str:
    def render_node(node: dict, depth: int) -> str:
        children = node.get("children", [])
        label = label_for(node)
        cat = category_slug(category_for(node))
        child_count = len(children)
        if depth >= 5:
            return prefix_chip({**node, "child_count": child_count}, small=True)
        child_html = ""
        if children:
            child_html = '<div class="block-children">' + "".join(render_node(child, depth + 1) for child in children) + "</div>"
        label_html = f'<span>{html_escape(label)}</span>' if label else ""
        return (
            f'<section class="allocation-block depth-{depth} {cat}">'
            '<div class="block-title">'
            f'<code>{html_escape(node.get("prefix", ""))}</code>{label_html}'
            f'<b>{child_count}</b>'
            "</div>"
            f"{child_html}"
            "</section>"
        )

    return f"""
<section class="option-section" id="spatial-blocks">
  <h2>Option 1: Spatial block map</h2>
  <p class="summary">This makes containment physically visible. Larger parent allocations frame smaller child allocations, while reserved space is deliberately subdued.</p>
  <div class="visual-frame"><div class="block-map">{render_node(tree, 0)}</div></div>
</section>
"""


def level_lanes(nodes: list[dict]) -> str:
    by_level: dict[int, list[dict]] = defaultdict(list)
    for node in nodes:
        if node.get("prefix_length") in PREFIX_LEVELS:
            by_level[int(node["prefix_length"])].append(node)
    lanes = []
    for level in PREFIX_LEVELS:
        items = by_level.get(level, [])
        cards = []
        for node in items:
            label = label_for(node)
            cards.append(
                '<article class="lane-card">'
                f'{prefix_chip(node)}'
                f'<p>{html_escape(label or "No label")}</p>'
                f'<small>Parent: {html_escape(node.get("parent") or "root")}</small>'
                "</article>"
            )
        lanes.append(
            f'<section class="level-lane"><h3>/{level}</h3><div class="lane-items">{"".join(cards)}</div></section>'
        )
    return f"""
<section class="option-section" id="level-lanes">
  <h2>Option 2: Prefix length lanes</h2>
  <p class="summary">This layout answers the operational question: which prefixes exist at each allocation length, and how dense is each level?</p>
  <div class="visual-frame"><div class="lane-board">{"".join(lanes)}</div></div>
</section>
"""


def nibble_ladder(nodes: list[dict]) -> str:
    leaves = terminal_nodes(nodes)
    rows = []
    for leaf in leaves:
        by_len = {item.get("prefix_length"): item for item in leaf.get("path", []) if item.get("prefix_length") in PREFIX_LEVELS}
        cells = []
        for level in PREFIX_LEVELS:
            item = by_len.get(level)
            cells.append(f"<td>{prefix_chip(item, small=True) if item else ''}</td>")
        leaf_label = label_for(leaf)
        rows.append(
            "<tr>"
            + "".join(cells)
            + f'<td class="ladder-label">{html_escape(leaf_label or "No label")}</td>'
            + f'<td class="ladder-category">{html_escape(category_for(leaf))}</td>'
            + "</tr>"
        )
    headers = "".join(f"<th>/{level}</th>" for level in PREFIX_LEVELS)
    return f"""
<section class="option-section" id="nibble-ladder">
  <h2>Option 3: Nibble ladder</h2>
  <p class="summary">This is a compact audit view: every terminal prefix row shows its ancestry across nibble-aligned allocation boundaries.</p>
  <div class="visual-frame ladder-frame">
    <table class="ladder-table">
      <thead><tr>{headers}<th>Label</th><th>Purpose</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</section>
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
        child_preview = "".join(prefix_chip(child, small=True) for child in children[:12])
        more = ""
        if len(children) > 12:
            more = f'<span class="more-count">+{len(children) - 12} more</span>'
        notes = node.get("notes") or ""
        notes_html = f'<p>{html_escape(notes)}</p>' if notes else ""
        cards.append(
            '<article class="branch-card">'
            f'<h3>{html_escape(label_for(node) or node.get("prefix", ""))}</h3>'
            f'{path_summary(node)}'
            f'{notes_html}'
            f'<div class="child-preview">{child_preview}{more}</div>'
            "</article>"
        )
    return f"""
<section class="option-section" id="branch-cards">
  <h2>Option 4: Branch cards</h2>
  <p class="summary">This favours operator readability over total density: each meaningful branch keeps its lineage, intent, notes, and immediate children together.</p>
  <div class="visual-frame"><div class="branch-grid">{"".join(cards)}</div></div>
</section>
"""


def purpose_swimlanes(nodes: list[dict]) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        if node.get("prefix_length"):
            groups[category_for(node)].append(node)
    ordered = [
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
    lanes = []
    for category in ordered:
        items = groups.get(category, [])
        if not items:
            continue
        chips = "".join(prefix_chip(node, small=True) for node in items[:34])
        more = f'<span class="more-count">+{len(items) - 34} more</span>' if len(items) > 34 else ""
        lanes.append(
            '<section class="purpose-lane">'
            f'<div class="purpose-heading"><h3>{html_escape(category)}</h3><strong>{len(items)}</strong></div>'
            f'<div class="purpose-items">{chips}{more}</div>'
            "</section>"
        )
    return f"""
<section class="option-section" id="purpose-swimlanes">
  <h2>Option 5: Purpose swimlanes</h2>
  <p class="summary">This ignores pure hierarchy first and groups allocations by how an operator thinks about the prefix during design or troubleshooting.</p>
  <div class="visual-frame"><div class="purpose-board">{"".join(lanes)}</div></div>
</section>
"""


def radial_positions(nodes: list[dict]) -> tuple[dict[str, tuple[float, float]], int, int]:
    width = 980
    height = 820
    center_x = width / 2
    center_y = height / 2
    positions: dict[str, tuple[float, float]] = {}
    by_depth: dict[int, list[dict]] = defaultdict(list)
    for node in nodes:
        by_depth[int(node.get("depth") or 0)].append(node)
    max_seen_depth = max(by_depth) if by_depth else 0
    step = min(width, height) * 0.42 / max(max_seen_depth, 1)
    for depth, depth_nodes in by_depth.items():
        ordered = sorted(depth_nodes, key=node_key)
        if depth == 0:
            for node in ordered:
                positions[node_key(node)] = (center_x, center_y)
            continue
        radius = step * depth
        for index, node in enumerate(ordered):
            angle = (-math.pi / 2) + (2 * math.pi * index / max(len(ordered), 1))
            positions[node_key(node)] = (
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius,
            )
    return positions, width, height


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


def graph_svg(nodes: list[dict], positions: dict[str, tuple[float, float]], width: int, height: int, *, label_depth: int = 1) -> str:
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
        if depth <= label_depth or child_count >= 8:
            label = f'<text x="{x + radius + 4:.1f}" y="{y + 4:.1f}">{html_escape(short_prefix(prefix))}</text>'
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


def radial_prefix_graph(nodes: list[dict]) -> str:
    positions, width, height = radial_positions(nodes)
    section_id = "radial-prefix-graph"
    return f"""
<section class="option-section" id="{section_id}" data-graph-section>
  <h2>Option 6: Radial prefix graph</h2>
  <p class="summary">This keeps graph-theory node links but constrains them into readable hierarchy rings. Click any node to highlight ancestry and immediate children.</p>
  <div class="visual-frame">
    <div class="interactive-grid">
      {graph_svg(nodes, positions, width, height)}
      {graph_detail_panel()}
    </div>
  </div>
  {graph_json_script(section_id, nodes)}
</section>
"""


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
            f'<summary>{prefix_chip(node_with_count, small=True)}</summary>'
            f"{children_html}</details>"
        )

    return f"""
<section class="option-section" id="collapsible-dendrogram" data-dendrogram-section>
  <h2>Option 7: Collapsible dendrogram</h2>
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


def subtree_weight(node: dict) -> int:
    children = node.get("children", [])
    if not children:
        return 1
    return max(1, sum(subtree_weight(child) for child in children))


def polar_point(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    adjusted = angle - math.pi / 2
    return cx + math.cos(adjusted) * radius, cy + math.sin(adjusted) * radius


def arc_path(cx: float, cy: float, inner: float, outer: float, start: float, end: float) -> str:
    if end - start >= 2 * math.pi:
        end = start + 2 * math.pi - 0.001
    large = 1 if end - start > math.pi else 0
    x1, y1 = polar_point(cx, cy, outer, start)
    x2, y2 = polar_point(cx, cy, outer, end)
    x3, y3 = polar_point(cx, cy, inner, end)
    x4, y4 = polar_point(cx, cy, inner, start)
    return (
        f"M{x1:.2f},{y1:.2f} A{outer:.2f},{outer:.2f} 0 {large} 1 {x2:.2f},{y2:.2f} "
        f"L{x3:.2f},{y3:.2f} A{inner:.2f},{inner:.2f} 0 {large} 0 {x4:.2f},{y4:.2f} Z"
    )


def sunburst_map(tree: dict, nodes: list[dict]) -> str:
    node_map = node_lookup(nodes)
    width = 860
    height = 860
    cx = width / 2
    cy = height / 2
    max_seen_depth = max((int(node.get("depth") or 0) for node in nodes), default=1)
    ring = (min(width, height) / 2 - 58) / max(max_seen_depth, 1)
    segments: list[str] = []

    def assign(node: dict, start: float, end: float, depth: int) -> None:
        prefix = node_key(node)
        if depth > 0 and prefix in node_map:
            inner = 42 + (depth - 1) * ring
            outer = inner + ring - 4
            mapped = node_map[prefix]
            cat = category_slug(category_for(mapped))
            segments.append(
                f'<path class="graph-mark {cat}" {graph_mark_attrs(mapped)} tabindex="0" role="button" '
                f'd="{arc_path(cx, cy, inner, outer, start, end)}">'
                f'<title>{html_escape(prefix)} - {html_escape(label_for(mapped) or category_for(mapped))}</title>'
                "</path>"
            )
        children = node.get("children", [])
        total = sum(subtree_weight(child) for child in children)
        cursor = start
        for child in children:
            span = (end - start) * subtree_weight(child) / max(total, 1)
            assign(child, cursor, cursor + span, depth + 1)
            cursor += span

    assign(tree, 0, 2 * math.pi, 0)
    counts = defaultdict(int)
    for node in nodes:
        counts[category_for(node)] += 1
    legend = "".join(
        f'<li class="{category_slug(category)}"><span>{html_escape(category)}</span><strong>{counts[category]}</strong></li>'
        for category in CATEGORY_ORDER
        if counts.get(category)
    )
    section_id = "sunburst-map"
    return f"""
<section class="option-section" id="{section_id}" data-graph-section>
  <h2>Option 8: Sunburst allocation map</h2>
  <p class="summary">This compresses hierarchy into radial allocation bands. Wider arcs mean denser branches; click an arc to see the exact prefix path.</p>
  <div class="visual-frame">
    <div class="sunburst-wrap">
      <svg class="graph-canvas" viewBox="0 0 {width} {height}" role="img" aria-label="IPv6 sunburst allocation map">
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="34" fill="var(--surface)" stroke="var(--border)"></circle>
        <text x="{cx - 28:.1f}" y="{cy + 4:.1f}">root</text>
        {"".join(segments)}
      </svg>
      <div class="interaction-panel">
        <h3>Purpose legend</h3>
        <ul class="legend-list">{legend}</ul>
        {graph_detail_panel()}
      </div>
    </div>
  </div>
  {graph_json_script(section_id, nodes)}
</section>
"""


def animated_walkthrough(nodes: list[dict]) -> str:
    by_level: dict[int, list[dict]] = defaultdict(list)
    for node in nodes:
        if node.get("prefix_length") in PREFIX_LEVELS:
            by_level[int(node["prefix_length"])].append(node)
    steps = []
    for level in PREFIX_LEVELS:
        items = sorted(by_level.get(level, []), key=node_key)
        chips = "".join(prefix_chip(node, small=True) for node in items)
        steps.append(
            f'<section class="walk-step" data-level="/{level}">'
            f"<h3>/{level}</h3>"
            f'<div class="walk-items">{chips}</div>'
            "</section>"
        )
    return f"""
<section class="option-section" id="animated-walkthrough" data-walkthrough-section>
  <h2>Option 9: Animated allocation walkthrough</h2>
  <p class="summary">This turns the subnetting model into a controlled sequence. Step through prefix lengths to explain how the plan descends from aggregate to usable allocations.</p>
  <div class="visual-frame">
    <div class="walk-controls">
      <button type="button" data-walk-prev>Previous</button>
      <button type="button" data-walk-play>Play</button>
      <button type="button" data-walk-next>Next</button>
      <strong data-walk-label>Active prefix length: /32</strong>
    </div>
    <div class="walk-progress"><span data-walk-progress></span></div>
    <div class="walk-stage">
      <div class="walk-track">{"".join(steps)}</div>
    </div>
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
            f'<text x="{sum(xs) / len(xs):.1f}" y="{min(ys) - 34:.1f}" text-anchor="middle">{html_escape(category)}</text>'
        )
    section_id = "purpose-cluster-graph"
    return f"""
<section class="option-section" id="{section_id}" data-graph-section>
  <h2>Option 10: Purpose cluster graph</h2>
  <p class="summary">This keeps node links, but clusters prefixes by operational purpose so the design intent is visible before the exact hierarchy.</p>
  <div class="visual-frame">
    <div class="interactive-grid">
      <div>
        {graph_svg(nodes, positions, width, height, label_depth=0).replace("</svg>", "".join(labels) + "</svg>")}
      </div>
      {graph_detail_panel()}
    </div>
  </div>
  {graph_json_script(section_id, nodes)}
</section>
"""


def searchable_focus_graph(nodes: list[dict]) -> str:
    section_id = "searchable-focus-graph"
    return f"""
<section class="option-section" id="{section_id}" data-focus-section>
  <h2>Option 11: Searchable focus graph</h2>
  <p class="summary">This avoids showing everything at once. Search for a prefix, site, or purpose, then inspect only that node's path, siblings, and children.</p>
  <div class="visual-frame">
    <div class="focus-controls">
      <input data-focus-search type="search" placeholder="Search prefix, purpose, label, or site" aria-label="Search prefixes">
    </div>
    <div class="focus-shell">
      <div>
        <div class="focus-canvas" data-focus-canvas></div>
      </div>
      <div class="interaction-panel">
        <h3>Matches</h3>
        <div class="focus-results" data-focus-results></div>
        {graph_detail_panel()}
      </div>
    </div>
  </div>
  {graph_json_script(section_id, nodes)}
</section>
"""


def option_css() -> str:
    return """
.block-map {
  width: max-content;
  min-width: 100%;
}
.allocation-block {
  margin: .55rem 0;
  padding: .7rem;
  border: 1px solid var(--border);
  border-left-width: .38rem;
  border-radius: 8px;
  background: var(--surface);
}
.depth-0 { background: var(--surface-strong); }
.depth-1 { margin-left: .4rem; }
.depth-2 { margin-left: .8rem; }
.depth-3 { margin-left: 1.2rem; }
.depth-4 { margin-left: 1.6rem; }
.block-title {
  display: flex;
  align-items: center;
  gap: .55rem;
  min-width: 0;
}
.block-title code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight: 800; }
.block-title span { color: var(--muted); overflow-wrap: anywhere; }
.block-title b { margin-left: auto; color: var(--muted); font-size: .85rem; }
.block-children {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: .55rem;
  margin-top: .65rem;
}
.lane-board {
  display: grid;
  grid-template-columns: repeat(8, minmax(16rem, 1fr));
  gap: .75rem;
  width: max-content;
  min-width: 132rem;
  align-items: start;
}
.level-lane {
  min-width: 0;
  padding: .7rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
}
.level-lane h3 { margin: 0 0 .6rem; }
.lane-items { display: grid; gap: .5rem; }
.lane-card {
  display: grid;
  gap: .35rem;
  padding: .5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.lane-card p { margin: 0; color: var(--text); }
.lane-card small { color: var(--muted); overflow-wrap: anywhere; }
.ladder-frame { max-height: 72vh; }
.ladder-table {
  width: 100%;
  min-width: 96rem;
  border-collapse: separate;
  border-spacing: 0;
  font-size: .9rem;
}
.ladder-table th, .ladder-table td {
  padding: .42rem;
  border-right: 1px solid var(--grid);
  border-bottom: 1px solid var(--grid);
  vertical-align: top;
}
.ladder-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--surface-alt);
  text-align: left;
}
.ladder-label, .ladder-category { min-width: 12rem; color: var(--muted); }
.branch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(24rem, 1fr));
  gap: .85rem;
}
.branch-card {
  display: grid;
  gap: .65rem;
  padding: .85rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
}
.branch-card h3 { margin: 0; font-size: 1.05rem; }
.branch-card p { margin: 0; color: var(--muted); }
.child-preview, .purpose-items {
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
}
.more-count {
  display: inline-flex;
  align-items: center;
  min-height: 1.45rem;
  padding: .12rem .45rem;
  border: 1px dashed var(--grid);
  border-radius: 6px;
  color: var(--muted);
  font-size: .82rem;
}
.purpose-board {
  display: grid;
  gap: .85rem;
}
.purpose-lane {
  display: grid;
  grid-template-columns: minmax(12rem, 16rem) minmax(0, 1fr);
  gap: .8rem;
  padding: .75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
}
.purpose-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: .6rem;
}
.purpose-heading h3 { margin: 0; font-size: 1rem; }
.purpose-heading strong { color: var(--muted); }
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
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
  gap: 1rem;
  align-items: start;
}
.graph-canvas {
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
  display: flex;
  justify-content: space-between;
  gap: .8rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: .25rem;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; text-align: right; overflow-wrap: anywhere; }
.tree-toolbar,
.walk-controls,
.focus-controls {
  display: flex;
  align-items: center;
  gap: .55rem;
  flex-wrap: wrap;
  margin: 0 0 .85rem;
}
.tree-toolbar button,
.walk-controls button,
.focus-controls button,
.focus-results button {
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
  min-width: 42rem;
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
  align-items: center;
  gap: .5rem;
  min-height: 2rem;
  cursor: pointer;
  list-style: none;
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
}
.tree-node[open] > summary::before { content: "-"; }
.tree-node.leaf summary::before { content: ""; border-style: dashed; }
.sunburst-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(14rem, 18rem);
  gap: 1rem;
  align-items: start;
}
.legend-list {
  display: grid;
  gap: .45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.legend-list li {
  display: flex;
  justify-content: space-between;
  gap: .8rem;
  padding: .45rem .55rem;
  border: 1px solid var(--border);
  border-left: .4rem solid var(--other);
  border-radius: 6px;
  background: var(--surface);
}
.legend-list .loopback { border-left-color: var(--loopback); }
.legend-list .oob-management { border-left-color: var(--oob); }
.legend-list .interconnect { border-left-color: var(--interconnect); }
.legend-list .content-cdn { border-left-color: var(--cdn); }
.legend-list .service-routed-pools { border-left-color: var(--service); }
.legend-list .network-device-roles { border-left-color: var(--role); }
.legend-list .geography-sites { border-left-color: var(--geo); }
.legend-list .reserved { border-left-color: var(--reserved); }
.walk-stage {
  display: grid;
  gap: .8rem;
}
.walk-track {
  display: grid;
  grid-template-columns: repeat(8, minmax(8rem, 1fr));
  min-width: 72rem;
  gap: .5rem;
}
.walk-step {
  padding: .65rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
  opacity: .5;
  transition: opacity .2s ease, transform .2s ease, border-color .2s ease;
}
.walk-step.is-active {
  opacity: 1;
  transform: translateY(-.18rem);
  border-color: var(--accent);
}
.walk-step h3 { margin: 0 0 .55rem; font-size: 1rem; }
.walk-items {
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
  max-height: 18rem;
  overflow: auto;
}
.walk-progress {
  height: .45rem;
  border-radius: 999px;
  background: var(--surface-alt);
  overflow: hidden;
}
.walk-progress span {
  display: block;
  height: 100%;
  width: 12.5%;
  background: var(--accent);
  transition: width .2s ease;
}
.focus-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(17rem, 22rem);
  gap: 1rem;
}
.focus-controls input {
  flex: 1 1 18rem;
  min-height: 2.35rem;
  min-width: 0;
  padding: .45rem .65rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
}
.focus-results {
  display: grid;
  gap: .4rem;
  max-height: 22rem;
  overflow: auto;
}
.focus-results button {
  display: grid;
  gap: .15rem;
  padding: .45rem .55rem;
  text-align: left;
}
.focus-results small { color: var(--muted); }
.focus-canvas {
  min-width: 44rem;
}
.focus-canvas svg {
  width: 100%;
  min-width: 44rem;
  height: auto;
  border-radius: 8px;
  background: var(--surface-alt);
}
.focus-node rect {
  fill: var(--surface);
  stroke: var(--border);
  stroke-width: 1.4;
}
.focus-node.is-selected rect {
  stroke: var(--accent);
  stroke-width: 2.6;
}
@media (max-width: 760px) {
  .interactive-grid,
  .sunburst-wrap,
  .focus-shell { grid-template-columns: 1fr; }
  .branch-grid { grid-template-columns: 1fr; }
  .purpose-lane { grid-template-columns: 1fr; }
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

  const initWalkthrough = (section) => {
    const steps = Array.from(section.querySelectorAll(".walk-step[data-level]"));
    const label = section.querySelector("[data-walk-label]");
    const progress = section.querySelector("[data-walk-progress]");
    const prev = section.querySelector("[data-walk-prev]");
    const next = section.querySelector("[data-walk-next]");
    const play = section.querySelector("[data-walk-play]");
    if (!steps.length) return;
    let index = 0;
    let timer = null;
    const setStep = (nextIndex) => {
      index = (nextIndex + steps.length) % steps.length;
      steps.forEach((step, stepIndex) => step.classList.toggle("is-active", stepIndex === index));
      if (label) label.textContent = `Active prefix length: ${steps[index].dataset.level}`;
      if (progress) progress.style.width = `${((index + 1) / steps.length) * 100}%`;
    };
    const stop = () => {
      if (timer) window.clearInterval(timer);
      timer = null;
      if (play) play.textContent = "Play";
    };
    const toggle = () => {
      if (timer) {
        stop();
        return;
      }
      if (play) play.textContent = "Pause";
      timer = window.setInterval(() => setStep(index + 1), 1200);
    };
    if (prev) prev.addEventListener("click", () => { stop(); setStep(index - 1); });
    if (next) next.addEventListener("click", () => { stop(); setStep(index + 1); });
    if (play) play.addEventListener("click", toggle);
    steps.forEach((step, stepIndex) => step.addEventListener("click", () => { stop(); setStep(stepIndex); }));
    setStep(0);
  };

  const initFocus = (section) => {
    const data = dataFor(section);
    const byId = new Map(data.nodes.map((node) => [node.id, node]));
    const input = section.querySelector("[data-focus-search]");
    const results = section.querySelector("[data-focus-results]");
    const canvas = section.querySelector("[data-focus-canvas]");
    const panel = section.querySelector("[data-node-detail]");
    if (!input || !results || !canvas || !panel || byId.size === 0) return;

    const nodeButton = (node) => `
      <button type="button" data-focus-id="${esc(node.id)}">
        <code>${esc(node.shortPrefix || node.prefix)}</code>
        <small>${esc(node.label || node.category)}</small>
      </button>
    `;

    const renderResults = () => {
      const term = input.value.trim().toLowerCase();
      const matches = data.nodes
        .filter((node) => !term || `${node.prefix} ${node.label} ${node.category}`.toLowerCase().includes(term))
        .slice(0, 18);
      results.innerHTML = matches.map(nodeButton).join("") || "<p>No matching prefix.</p>";
    };

    const renderFocus = (id) => {
      const node = byId.get(id) || data.nodes[0];
      const path = (node.path || []).map((pathId) => byId.get(pathId)).filter(Boolean);
      const children = data.nodes.filter((item) => item.parent === node.id).slice(0, 10);
      const siblings = node.parent ? data.nodes.filter((item) => item.parent === node.parent && item.id !== node.id).slice(0, 8) : [];
      const row = (items, y, className) => items.map((item, index) => {
        const x = 30 + index * 165;
        return `
          <g class="focus-node ${className} ${item.id === node.id ? "is-selected" : ""}" data-focus-id="${esc(item.id)}" transform="translate(${x},${y})" tabindex="0" role="button">
            <rect width="145" height="58" rx="7"></rect>
            <text x="10" y="23">${esc(item.shortPrefix || item.prefix)}</text>
            <text x="10" y="43">${esc(item.category)}</text>
          </g>
        `;
      }).join("");
      const width = Math.max(760, Math.max(path.length, children.length, siblings.length) * 165 + 80);
      canvas.innerHTML = `
        <svg viewBox="0 0 ${width} 310" aria-label="Focused prefix graph">
          <text x="30" y="24">Ancestry path</text>
          ${row(path, 42, "path")}
          <text x="30" y="135">Immediate children</text>
          ${row(children, 153, "child")}
          <text x="30" y="246">Nearby siblings</text>
          ${row(siblings, 264, "sibling")}
        </svg>
      `;
      panel.innerHTML = detailHtml(node);
      canvas.querySelectorAll("[data-focus-id]").forEach((mark) => {
        mark.addEventListener("click", () => renderFocus(mark.dataset.focusId));
        mark.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            renderFocus(mark.dataset.focusId);
          }
        });
      });
    };

    results.addEventListener("click", (event) => {
      const button = event.target.closest("[data-focus-id]");
      if (button) renderFocus(button.dataset.focusId);
    });
    input.addEventListener("input", renderResults);
    renderResults();
    renderFocus(data.nodes[0].id);
  };

  document.querySelectorAll("[data-graph-section]").forEach(initGraphSection);
  document.querySelectorAll("[data-dendrogram-section]").forEach(initDendrogram);
  document.querySelectorAll("[data-walkthrough-section]").forEach(initWalkthrough);
  document.querySelectorAll("[data-focus-section]").forEach(initFocus);
})();
"""


def nav_links(current: str | None = None) -> str:
    links = ['<a href="./">Workbook</a>', '<a href="cidr-hierarchy.html">Tree model</a>', '<a href="visual-options.html">All options</a>']
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
      <p class="eyebrow">AS141253 IPv6 visual prototype</p>
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
    <p>Generated from repository CSV files. These are selection prototypes, not the final chosen model.</p>
  </footer>
  <script>
{interactive_js()}
  </script>
</body>
</html>
"""


def all_sections(tree: dict, nodes: list[dict]) -> dict[str, str]:
    return {
        "spatial-blocks": spatial_blocks(tree),
        "level-lanes": level_lanes(nodes),
        "nibble-ladder": nibble_ladder(nodes),
        "branch-cards": branch_cards(nodes),
        "purpose-swimlanes": purpose_swimlanes(nodes),
        "radial-prefix-graph": radial_prefix_graph(nodes),
        "collapsible-dendrogram": collapsible_dendrogram(tree),
        "sunburst-map": sunburst_map(tree, nodes),
        "animated-walkthrough": animated_walkthrough(nodes),
        "purpose-cluster-graph": purpose_cluster_graph(nodes),
        "searchable-focus-graph": searchable_focus_graph(nodes),
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
        "AS141253 IPv6 Visual Options",
        "Static and interactive HTML/CSS/JS alternatives generated from the same CSV-derived IPv6 prefix model.",
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
