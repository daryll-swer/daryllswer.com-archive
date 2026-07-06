#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Export the public AS141253 IPv6 architecture Google Sheet."""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sheets" / "as141253-ipv6-architecture-example"
PUBHTML = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ32t5C9BW-rV36gUo93uYcLw9GMPqg7BMks8u17dlLhWmIUzIdCe4iexLBQKdnDwykAom929K2dTxR/pubhtml"
PUB = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ32t5C9BW-rV36gUo93uYcLw9GMPqg7BMks8u17dlLhWmIUzIdCe4iexLBQKdnDwykAom929K2dTxR/pub"
UA = "daryllswer-com-archive-sheet-export/1.0 (+https://www.daryllswer.com/)"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def request(url: str) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read(), resp.headers.get("Content-Type")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    value = value.replace("::", "double-colon")
    value = re.sub(r"[/:]+", "-", value)
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    return value.strip("-").lower() or "sheet"


def parse_tabs(pubhtml: str) -> tuple[str, list[dict]]:
    title_match = re.search(r"<title>(.*?)</title>", pubhtml, flags=re.S)
    title = html.unescape(title_match.group(1)).strip() if title_match else "AS141253 IPv6 Architecture Example"
    tabs = []
    for match in re.finditer(r'items\.push\(\{name: "([^"]+?)".*?gid: "([^"]+?)"', pubhtml, flags=re.S):
        name = html.unescape(match.group(1).replace("\\/", "/"))
        gid = match.group(2)
        tabs.append({"name": name, "gid": gid})
    if not tabs:
        raise RuntimeError("No published Google Sheet tabs found in pubhtml")
    return title, tabs


def write_blob(path: Path, body: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(body),
        "bytes": len(body),
    }


def main() -> int:
    generated_at = now_iso()
    OUT.mkdir(parents=True, exist_ok=True)
    pubhtml_body, _ = request(PUBHTML)
    pubhtml_text = pubhtml_body.decode("utf-8", errors="replace")
    title, tabs = parse_tabs(pubhtml_text)

    ods_body, ods_type = request(f"{PUB}?output=ods")
    ods_info = write_blob(OUT / "AS141253-ipv6-architecture-example.ods", ods_body)
    ods_info["content_type"] = ods_type

    html_root = write_blob(OUT / "html" / "published-workbook.html", pubhtml_body)

    manifest_tabs = []
    for tab in tabs:
        name = tab["name"]
        gid = tab["gid"]
        base = slug(name)

        csv_url = f"{PUB}?gid={urllib.parse.quote(gid)}&single=true&output=csv"
        csv_body, csv_type = request(csv_url)
        csv_info = write_blob(OUT / "csv" / f"{base}.csv", csv_body)
        csv_info.update({
            "source_url": csv_url,
            "content_type": csv_type,
            "dialect": {
                "delimiter": ",",
                "quote_char": "\"",
                "encoding": "utf-8",
                "line_ending": "source export; normalised by validation when parsed",
                "empty_cell": "",
            },
        })

        sheet_html_url = f"{PUBHTML}/sheet?headers=false&gid={urllib.parse.quote(gid)}"
        sheet_html_body, sheet_html_type = request(sheet_html_url)
        html_info = write_blob(OUT / "html" / f"{base}.html", sheet_html_body)
        html_info.update({"source_url": sheet_html_url, "content_type": sheet_html_type})

        csvw = {
            "@context": "http://www.w3.org/ns/csvw",
            "url": f"../csv/{base}.csv",
            "dc:title": name,
            "dc:source": csv_url,
            "dialect": {
                "delimiter": ",",
                "quoteChar": "\"",
                "encoding": "utf-8",
                "header": True,
            },
            "tableSchema": {
                "columns": []
            }
        }
        header = csv_body.decode("utf-8-sig", errors="replace").splitlines()[0] if csv_body else ""
        for column in [c.strip() for c in header.split(",") if c.strip()]:
            csvw["tableSchema"]["columns"].append({"name": column, "titles": column})
        csvw_path = OUT / "csvw" / f"{base}.csv-metadata.json"
        write_json(csvw_path, csvw)

        manifest_tabs.append({
            "gid": gid,
            "name": name,
            "csv": csv_info,
            "html": html_info,
            "csvw": {
                "path": csvw_path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(csvw_path.read_bytes()).hexdigest(),
            },
        })

    manifest = {
        "generated_at": generated_at,
        "source_url": PUBHTML,
        "title": title,
        "ods": ods_info,
        "published_workbook_html": html_root,
        "tabs": manifest_tabs,
    }
    write_json(OUT / "manifest.json", manifest)

    readme_lines = [
        "# AS141253 IPv6 Architecture Example",
        "",
        f"Source: {PUBHTML}",
        "",
        "This directory stores the public Google Sheet linked from the IPv6 architecture post.",
        "",
        "- `AS141253-ipv6-architecture-example.ods` is the styled open spreadsheet export.",
        "- `csv/` contains one diffable CSV export per published tab.",
        "- `csvw/` contains lightweight CSVW-style metadata.",
        "- `html/` stores published HTML snapshots for visual/style reference.",
        "",
        "## Tabs",
        "",
    ]
    for tab in manifest_tabs:
        readme_lines.append(f"- `{tab['name']}` (`gid={tab['gid']}`): `{tab['csv']['path']}`")
    (OUT / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    print(f"exported {len(manifest_tabs)} sheet tabs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
