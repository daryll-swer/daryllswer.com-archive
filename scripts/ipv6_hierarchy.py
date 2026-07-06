#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Build IPv6 prefix hierarchy artefacts from CSV sheet exports."""

from __future__ import annotations

import csv
import hashlib
import html
import ipaddress
import json
import re
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def normalise_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "prefix"


def artefact_info(root: Path, path: Path, body: bytes, content_type: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "content_type": content_type,
    }


def read_prefix_rows(root: Path, manifest: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for tab in manifest.get("tabs", []):
        csv_path = root / tab["csv"]["path"]
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "Prefix" not in reader.fieldnames:
                continue
            label_field = next((name for name in reader.fieldnames if name != "Prefix" and name.lower() != "notes"), None)
            for index, row in enumerate(reader, start=2):
                prefix_value = (row.get("Prefix") or "").strip()
                try:
                    network = ipaddress.ip_network(prefix_value, strict=True)
                except ValueError:
                    continue
                if network.version != 6:
                    continue
                canonical = network.compressed
                if canonical in seen:
                    continue
                seen.add(canonical)
                label = (row.get(label_field or "") or "").strip()
                notes = (row.get("Notes") or "").strip()
                rows.append({
                    "id": normalise_id(canonical),
                    "prefix": canonical,
                    "prefix_length": network.prefixlen,
                    "first_address": str(network.network_address),
                    "last_address": str(network.broadcast_address),
                    "address_count_power": 128 - network.prefixlen,
                    "label": label,
                    "notes": notes,
                    "source_sheet": tab.get("name"),
                    "source_csv": tab["csv"]["path"],
                    "source_row": index,
                    "_network": network,
                })
    return sorted(rows, key=lambda item: (item["prefix_length"], int(item["_network"].network_address)))


def attach_children(rows: list[dict]) -> dict:
    by_prefix = {item["prefix"]: {k: v for k, v in item.items() if k != "_network"} | {"children": []} for item in rows}
    networks = {item["prefix"]: item["_network"] for item in rows}
    root_prefix = rows[0]["prefix"] if rows else "IPv6"

    for item in rows:
        network = item["_network"]
        candidates = [
            other
            for other in rows
            if other is not item
            and other["_network"].prefixlen < network.prefixlen
            and network.subnet_of(other["_network"])
        ]
        if not candidates:
            continue
        parent = max(candidates, key=lambda other: other["_network"].prefixlen)
        by_prefix[parent["prefix"]]["children"].append(by_prefix[item["prefix"]])

    child_prefixes = {
        child["prefix"]
        for node in by_prefix.values()
        for child in node["children"]
    }
    roots = [node for prefix, node in by_prefix.items() if prefix not in child_prefixes]
    if len(roots) == 1:
        return roots[0]
    return {
        "id": "ipv6-prefix-plan",
        "prefix": root_prefix,
        "label": "IPv6 prefix plan",
        "notes": "Artificial root for disconnected CSV prefixes.",
        "children": roots,
    }


def prune_empty_children(node: dict) -> dict:
    node["children"] = [prune_empty_children(child) for child in node.get("children", [])]
    if not node["children"]:
        node.pop("children", None)
    return node


def count_nodes(node: dict) -> int:
    return 1 + sum(count_nodes(child) for child in node.get("children", []))


def max_depth(node: dict, depth: int = 0) -> int:
    return max([depth] + [max_depth(child, depth + 1) for child in node.get("children", [])])


def render_tree(node: dict, depth: int = 0) -> str:
    open_attr = " open" if depth <= 2 else ""
    label = node.get("label") or node.get("source_sheet") or ""
    notes = node.get("notes") or ""
    meta = []
    if label:
        meta.append(f'<span class="prefix-label">{html_escape(label)}</span>')
    if node.get("source_sheet"):
        meta.append(f'<span class="prefix-source">{html_escape(node["source_sheet"])}</span>')
    children = node.get("children", [])
    child_html = ""
    if children:
        child_html = "<ul>" + "".join(render_tree(child, depth + 1) for child in children) + "</ul>"
    notes_html = f'<p class="prefix-notes">{html_escape(notes)}</p>' if notes else ""
    return (
        "<li>"
        f"<details{open_attr}>"
        "<summary>"
        f'<span class="prefix">{html_escape(node.get("prefix", ""))}</span>'
        f'<span class="prefix-length">/{html_escape(node.get("prefix_length", ""))}</span>'
        f"{''.join(meta)}"
        f'<span class="child-count">{len(children)} child prefix{"es" if len(children) != 1 else ""}</span>'
        "</summary>"
        f"{notes_html}"
        f"{child_html}"
        "</details>"
        "</li>"
    )


def render_html(tree: dict, source_url: str) -> str:
    total = count_nodes(tree)
    depth = max_depth(tree)
    return f"""<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AS141253 IPv6 CIDR Hierarchy</title>
  <style>
* {{ box-sizing: border-box; }}
:root {{
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-alt: #edf4f7;
  --text: #17202a;
  --muted: #5f6c78;
  --border: #d6dde5;
  --accent: #0b6f8a;
  --reserved: #7a5c00;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #101418;
    --surface: #171d23;
    --surface-alt: #202a32;
    --text: #edf2f7;
    --muted: #a8b4c0;
    --border: #34404d;
    --accent: #6cc7df;
    --reserved: #e7c45d;
  }}
}}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
}}
a {{ color: var(--accent); text-underline-offset: .18em; }}
.page-header, main, footer {{
  max-width: 1180px;
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
.actions {{ display: flex; gap: .6rem; flex-wrap: wrap; justify-content: flex-end; }}
.actions a {{
  display: inline-flex;
  min-height: 2.25rem;
  align-items: center;
  padding: .4rem .7rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  text-decoration: none;
  font-weight: 700;
}}
.eyebrow {{
  margin: 0 0 .45rem;
  color: var(--muted);
  font-size: .82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}}
h1 {{ margin: 0; font-size: clamp(1.8rem, 4vw, 3.2rem); line-height: 1.12; letter-spacing: 0; }}
.summary {{ max-width: 780px; color: var(--muted); }}
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: .75rem;
  margin: 1rem 0;
}}
.metric {{
  padding: .85rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
.metric strong {{ display: block; font-size: 1.45rem; }}
.tree-shell {{
  overflow-x: auto;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
.prefix-tree, .prefix-tree ul {{
  list-style: none;
  margin: 0;
  padding-left: 1.15rem;
  border-left: 1px solid var(--border);
}}
.prefix-tree {{ padding-left: 0; border-left: 0; }}
.prefix-tree li {{ margin: .45rem 0; }}
details {{ min-width: 48rem; }}
summary {{
  display: flex;
  align-items: center;
  gap: .5rem;
  min-height: 2.35rem;
  padding: .4rem .55rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
  cursor: pointer;
}}
.prefix {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 800;
  color: var(--accent);
}}
.prefix-length {{ color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
.prefix-label, .prefix-source, .child-count {{
  display: inline-flex;
  align-items: center;
  min-height: 1.55rem;
  padding: .15rem .45rem;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: .85rem;
  white-space: nowrap;
}}
.prefix-notes {{
  max-width: 760px;
  margin: .45rem 0 .65rem 1.75rem;
  color: var(--muted);
}}
footer {{ color: var(--muted); font-size: .92rem; }}
@media (max-width: 760px) {{
  .page-header {{ flex-direction: column; }}
  .actions {{ justify-content: flex-start; }}
}}
  </style>
</head>
<body>
  <header class="page-header">
    <div>
      <p class="eyebrow">Graph-theory proof of concept</p>
      <h1>AS141253 IPv6 CIDR Hierarchy</h1>
      <p class="summary">A rooted prefix-containment tree generated from the repository CSV files. Parent/child edges are calculated with IPv6 network containment, not manual indentation.</p>
    </div>
    <nav class="actions" aria-label="Hierarchy actions">
      <a href="./">Workbook</a>
      <a href="cidr-hierarchy.json">JSON</a>
      <a href="cidr-hierarchy.dot">DOT</a>
      <a href="{html_escape(source_url)}">Original Google Sheet</a>
    </nav>
  </header>
  <main>
    <section class="metrics" aria-label="Hierarchy metrics">
      <div class="metric"><strong>{total}</strong><span>prefix nodes</span></div>
      <div class="metric"><strong>{depth}</strong><span>containment levels below root</span></div>
      <div class="metric"><strong>{html_escape(tree.get("prefix", ""))}</strong><span>root prefix</span></div>
    </section>
    <section class="tree-shell" aria-label="IPv6 CIDR hierarchy">
      <ul class="prefix-tree">
        {render_tree(tree)}
      </ul>
    </section>
  </main>
  <footer>
    <p>This is a static, self-contained HTML proof of concept. The CSV files remain the editable source of truth.</p>
  </footer>
</body>
</html>
"""


def dot_id(prefix: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]+", "_", prefix)


def render_dot(tree: dict) -> str:
    lines = [
        "digraph ipv6_hierarchy {",
        "  graph [rankdir=LR, splines=ortho];",
        "  node [shape=box, style=\"rounded,filled\", fillcolor=\"#edf4f7\", color=\"#0b6f8a\", fontname=\"Arial\"];",
        "  edge [color=\"#5f6c78\"];",
    ]

    def visit(node: dict) -> None:
        label = node.get("prefix", "")
        if node.get("label"):
            label += f"\\n{node['label']}"
        lines.append(f'  {dot_id(node.get("prefix", ""))} [label="{label}"];')
        for child in node.get("children", []):
            lines.append(f'  {dot_id(node.get("prefix", ""))} -> {dot_id(child.get("prefix", ""))};')
            visit(child)

    visit(tree)
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_ipv6_hierarchy_artefacts(root: Path, out: Path, manifest: dict) -> dict:
    rows = read_prefix_rows(root, manifest)
    tree = prune_empty_children(attach_children(rows))
    json_body = json.dumps(tree, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    html_body = render_html(tree, manifest.get("source_url", "")).encode("utf-8")
    dot_body = render_dot(tree).encode("utf-8")
    return {
        "model": "rooted_ipv6_prefix_containment_tree",
        "source": "CSV Prefix columns",
        "node_count": count_nodes(tree),
        "max_depth": max_depth(tree),
        "json": artefact_info(root, out / "cidr-hierarchy.json", json_body, "application/json; charset=utf-8"),
        "html": artefact_info(root, out / "cidr-hierarchy.html", html_body, "text/html; charset=utf-8"),
        "dot": artefact_info(root, out / "cidr-hierarchy.dot", dot_body, "text/vnd.graphviz; charset=utf-8"),
    }
