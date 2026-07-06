#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Generate a small local HTML preview index under .preview/."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".preview"


def markdown_excerpt(path: Path, limit: int = 500) -> str:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^---.*?---", "", text, flags=re.S).strip()
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*_`>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def main() -> int:
    manifest_path = ROOT / "archive-manifest.json"
    if not manifest_path.exists():
        raise SystemExit("archive-manifest.json missing; run make sync first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for post in manifest.get("posts", []):
        bundle = ROOT / post["bundle_path"]
        md = bundle / "index.md"
        featured = post.get("featured_image")
        image_html = ""
        if featured and (bundle / featured).exists():
            image_html = f'<img src="../{html.escape(post["bundle_path"] + "/" + featured)}" alt="">'
        rows.append(
            "<article>"
            + image_html
            + f'<h2><a href="{html.escape(post["canonical_url"])}">{html.escape(post["title"])}</a></h2>'
            + f"<p><code>{html.escape(post['published'])}</code></p>"
            + f"<p>{html.escape(markdown_excerpt(md))}</p>"
            + f'<p><a href="../{html.escape(post["bundle_path"])}/index.md">Markdown</a></p>'
            + "</article>"
        )
    page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>daryllswer.com Archive Preview</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 1100px; }
    article { border-bottom: 1px solid #ddd; padding: 1.25rem 0; overflow: auto; }
    img { width: 220px; max-height: 140px; object-fit: cover; float: right; margin-left: 1rem; }
    h1, h2 { line-height: 1.2; }
    code { color: #555; }
  </style>
</head>
<body>
  <h1>daryllswer.com Archive Preview</h1>
  <p>This is a local generated preview. The WordPress site remains canonical.</p>
  %s
</body>
</html>
""" % "\n".join(rows)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"preview generated: {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
