#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Build alternate IPv6 subnetting visualisation prototypes from CSV data."""

from __future__ import annotations

import html
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
]

OPTION_TITLES = {
    "spatial-blocks": "Spatial block map",
    "level-lanes": "Prefix length lanes",
    "nibble-ladder": "Nibble ladder",
    "branch-cards": "Branch cards",
    "purpose-swimlanes": "Purpose swimlanes",
}

OPTION_SUMMARIES = {
    "spatial-blocks": "Nested allocation blocks for quick visual containment checks.",
    "level-lanes": "One horizontal lane per prefix length so hierarchy depth is visible at a glance.",
    "nibble-ladder": "Terminal prefixes as rows with ancestor columns for /32, /34, /40, /44, /48, /52, /56, and /64.",
    "branch-cards": "Operational branches with ancestry, child allocations, and notes grouped together.",
    "purpose-swimlanes": "Prefixes grouped by network purpose such as loopback, OOB, interconnect, CDN, reserved, and services.",
}

PREFIX_LEVELS = [32, 34, 40, 44, 48, 52, 56, 64]


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
@media (max-width: 760px) {
  .branch-grid { grid-template-columns: 1fr; }
  .purpose-lane { grid-template-columns: 1fr; }
}
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
        "Five static HTML/CSS alternatives generated from the same CSV-derived IPv6 prefix model.",
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
