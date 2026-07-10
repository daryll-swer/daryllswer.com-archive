#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Render CSV-backed spreadsheet artefacts as a standalone tabbed HTML workbook."""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path

from font_assets import FONT_BODY_STACK, FONT_HEADING_STACK, font_face_css


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def column_label(index: int) -> str:
    label = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(65 + rem) + label
    return label


def artifact_rel(path: str, sheet_slug: str) -> str:
    marker = sheet_slug + "/"
    if marker in path:
        return path.split(marker, 1)[1]
    return path


def normalise_id(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def read_csv_rows(root: Path, path: str) -> list[list[str]]:
    with (root / path).open(newline="", encoding="utf-8-sig") as fh:
        return [row for row in csv.reader(fh)]


def render_grid(rows: list[list[str]]) -> str:
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return '<p class="empty-sheet">This sheet is empty.</p>'

    header = ["<tr><th class=\"corner\" aria-hidden=\"true\"></th>"]
    for col in range(width):
        header.append(f'<th class="col-header" scope="col">{column_label(col)}</th>')
    header.append("</tr>")

    body = []
    for row_index, row in enumerate(rows, start=1):
        cells = [f'<tr><th class="row-header" scope="row">{row_index}</th>']
        padded = row + [""] * (width - len(row))
        for value in padded:
            class_name = "cell empty" if value == "" else "cell"
            cells.append(f'<td class="{class_name}">{html_escape(value)}</td>')
        cells.append("</tr>")
        body.append("".join(cells))

    return (
        '<div class="sheet-viewport">'
        '<table class="sheet-grid">'
        f"<thead>{''.join(header)}</thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table>"
        "</div>"
    )


def workbook_css(tab_count: int, font_asset_prefix: str | None = None) -> str:
    dynamic = []
    for index in range(tab_count):
        dynamic.append(
            f"#sheet-tab-{index}:checked ~ .sheet-panels #sheet-panel-{index} "
            "{ display: block; }"
        )
        dynamic.append(
            f"#sheet-tab-{index}:checked ~ .sheet-tabs label[for=\"sheet-tab-{index}\"] "
            "{ background: var(--tab-active); border-color: var(--accent); color: var(--text); }"
        )

    fonts = font_face_css(font_asset_prefix) + "\n" if font_asset_prefix else ""
    css = """* { box-sizing: border-box; }
:root {
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-alt: #eef2f6;
  --grid: #d7dde5;
  --grid-strong: #b8c1cc;
  --text: #18202a;
  --muted: #64707d;
  --accent: #188038;
  --tab-active: #e6f4ea;
  --code: #0f172a;
  --font-body: __FONT_BODY__;
  --font-heading: __FONT_HEADING__;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101418;
    --surface: #171d23;
    --surface-alt: #222b35;
    --grid: #34404d;
    --grid-strong: #4a5968;
    --text: #edf2f7;
    --muted: #aab5c1;
    --accent: #81c995;
    --tab-active: #17351f;
    --code: #f8fafc;
  }
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.5;
}
a { color: var(--accent); text-underline-offset: .18em; }
.workbook-header, .workbook-footer {
  max-width: 1180px;
  margin: 0 auto;
  padding: 1rem 1.25rem;
}
.workbook-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  border-bottom: 1px solid var(--grid);
}
.eyebrow, .meta {
  margin: 0 0 .45rem;
  color: var(--muted);
  font-size: .82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
h1 { margin: 0; font-family: var(--font-heading); font-size: clamp(1.6rem, 4vw, 2.8rem); line-height: 1.12; letter-spacing: 0; }
.summary { max-width: 760px; color: var(--muted); }
.workbook-actions { display: flex; gap: .5rem; flex-wrap: wrap; justify-content: flex-end; }
.workbook-actions a {
  display: inline-flex;
  min-height: 2.25rem;
  align-items: center;
  justify-content: center;
  padding: .4rem .7rem;
  border: 1px solid var(--grid);
  border-radius: 8px;
  background: var(--surface);
  text-decoration: none;
  font-weight: 700;
  white-space: nowrap;
}
.workbook {
  max-width: 1180px;
  margin: 1rem auto 2rem;
  padding: 0 1.25rem;
}
.sheet-toggle { position: absolute; opacity: 0; pointer-events: none; }
.sheet-frame {
  border: 1px solid var(--grid-strong);
  border-radius: 8px;
  background: var(--surface);
  overflow: hidden;
}
.sheet-panels { min-height: 22rem; }
.sheet-panel { display: none; }
.sheet-title {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: .75rem .9rem;
  border-bottom: 1px solid var(--grid);
  background: var(--surface-alt);
}
.sheet-title h2 { margin: 0; font-family: var(--font-heading); font-size: 1rem; letter-spacing: 0; }
.sheet-links { display: flex; gap: .7rem; flex-wrap: wrap; font-size: .9rem; }
.sheet-viewport {
  max-height: 70vh;
  overflow: auto;
  background: var(--surface);
}
.sheet-grid {
  border-collapse: separate;
  border-spacing: 0;
  min-width: 100%;
  font-size: .92rem;
}
.sheet-grid th, .sheet-grid td {
  min-width: 8rem;
  max-width: 32rem;
  padding: .42rem .55rem;
  border-right: 1px solid var(--grid);
  border-bottom: 1px solid var(--grid);
  vertical-align: top;
  white-space: pre-wrap;
}
.sheet-grid .corner, .sheet-grid .row-header, .sheet-grid .col-header {
  position: sticky;
  background: var(--surface-alt);
  color: var(--muted);
  font-weight: 700;
  text-align: center;
  z-index: 2;
}
.sheet-grid .corner { left: 0; top: 0; min-width: 3.5rem; z-index: 4; }
.sheet-grid .col-header { top: 0; z-index: 3; }
.sheet-grid .row-header { left: 0; min-width: 3.5rem; max-width: 3.5rem; }
.sheet-grid .cell.empty { background-image: linear-gradient(135deg, transparent 0, transparent 96%, rgba(127,127,127,.08) 96%); }
.sheet-tabs {
  display: flex;
  gap: .35rem;
  overflow-x: auto;
  padding: .6rem;
  border-top: 1px solid var(--grid);
  background: var(--surface-alt);
}
.sheet-tabs label {
  flex: 0 0 auto;
  padding: .42rem .75rem;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--muted);
  cursor: pointer;
  font-size: .9rem;
  font-weight: 700;
  white-space: nowrap;
}
.empty-sheet { padding: 2rem; color: var(--muted); }
.workbook-footer { color: var(--muted); font-size: .92rem; }
@media (max-width: 760px) {
  .workbook-header { flex-direction: column; }
  .workbook-actions { justify-content: flex-start; }
  .sheet-grid th, .sheet-grid td { min-width: 7rem; }
}
"""
    css = css.replace("__FONT_BODY__", FONT_BODY_STACK)
    css = css.replace("__FONT_HEADING__", FONT_HEADING_STACK)
    return fonts + css + "\n".join(dynamic)


def render_workbook_page(
    *,
    root: Path,
    manifest: dict,
    sheet_slug: str,
    home_href: str | None = None,
    repo_href: str | None = None,
    font_asset_prefix: str | None = None,
) -> str:
    tabs = manifest.get("tabs", [])
    inputs = []
    labels = []
    panels = []

    for index, tab in enumerate(tabs):
        tab_id = f"sheet-tab-{index}"
        panel_id = f"sheet-panel-{index}"
        name = tab.get("name") or f"Sheet {index + 1}"
        checked = " checked" if index == 0 else ""
        csv_rel = artifact_rel(tab["csv"]["path"], sheet_slug)
        html_rel = artifact_rel(tab["html"]["path"], sheet_slug)
        csvw_rel = artifact_rel(tab["csvw"]["path"], sheet_slug)
        rows = read_csv_rows(root, tab["csv"]["path"])

        inputs.append(f'<input class="sheet-toggle" type="radio" name="sheet-tab" id="{tab_id}"{checked}>')
        labels.append(f'<label class="sheet-tab-label" for="{tab_id}">{html_escape(name)}</label>')
        panels.append(
            f'<section class="sheet-panel" id="{panel_id}" aria-labelledby="{tab_id}-label">'
            '<div class="sheet-title">'
            f'<h2 id="{tab_id}-label">{html_escape(name)}</h2>'
            '<div class="sheet-links">'
            f'<a href="{html_escape(csv_rel)}">CSV</a>'
            f'<a href="{html_escape(html_rel)}">Google HTML snapshot</a>'
            f'<a href="{html_escape(csvw_rel)}">CSVW metadata</a>'
            "</div>"
            "</div>"
            f"{render_grid(rows)}"
            "</section>"
        )

    ods_rel = artifact_rel(manifest["ods"]["path"], sheet_slug)
    workbook_rel = artifact_rel(manifest["published_workbook_html"]["path"], sheet_slug)
    actions = [
        f'<a href="{html_escape(ods_rel)}">Download ODS</a>',
        f'<a href="{html_escape(workbook_rel)}">Original workbook snapshot</a>',
        f'<a href="{html_escape(manifest["source_url"])}">Original Google Sheet</a>',
    ]
    cidr_hierarchy = manifest.get("cidr_hierarchy", {})
    if cidr_hierarchy.get("html", {}).get("path"):
        actions.insert(
            0,
            f'<a href="{html_escape(artifact_rel(cidr_hierarchy["html"]["path"], sheet_slug))}">CIDR hierarchy</a>',
        )
    visual_model = manifest.get("visual_model", {})
    if visual_model.get("path"):
        actions.insert(
            0,
            f'<a href="{html_escape(artifact_rel(visual_model["path"], sheet_slug))}">Visual model</a>',
        )
    if home_href:
        actions.insert(0, f'<a href="{html_escape(home_href)}">Archive index</a>')
    if repo_href:
        actions.append(f'<a href="{html_escape(repo_href)}">Repository</a>')

    title = manifest.get("title") or "AS141253 IPv6 Architecture Example"
    return f"""<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)}</title>
  <style>{workbook_css(len(tabs), font_asset_prefix)}</style>
</head>
<body>
  <header class="workbook-header">
    <div>
      <p class="eyebrow">CSV-backed spreadsheet archive</p>
      <h1>{html_escape(title)}</h1>
      <p class="summary">A standalone HTML mirror of the public Google Sheet, rendered from repository CSV files with clickable sheet tabs.</p>
    </div>
    <nav class="workbook-actions" aria-label="Workbook actions">
      {''.join(actions)}
    </nav>
  </header>
  <main class="workbook">
    <div class="sheet-frame">
      {''.join(inputs)}
      <div class="sheet-panels">
        {''.join(panels)}
      </div>
      <div class="sheet-tabs" aria-label="Sheet tabs">
        {''.join(labels)}
      </div>
    </div>
  </main>
  <footer class="workbook-footer">
    <p>CSV files are the editable text source for this workbook. The ODS and Google HTML snapshots are preserved for styling/provenance reference.</p>
  </footer>
</body>
</html>
"""
