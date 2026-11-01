# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Refresh CSV-derived sheet HTML and manifest metadata without network access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ipv6_visual_options import render_ipv6_visual_model
from sheet_workbook import render_workbook_page


VISUAL_METADATA = {
    "id": "visual-model",
    "title": "AS141253 IPv6 Visual Model",
    "summary": "Sole public CSV-derived full IPv6 prefix hierarchy model for AS141253.",
}


def artifact_metadata(root: Path, path: Path, body: bytes) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "content_type": "text/html; charset=utf-8",
    }


def refresh_sheet_pages(root: Path, sheet_dir: Path, manifest: dict) -> dict:
    """Regenerate the local visual/workbook HTML and their manifest projections."""
    slug = sheet_dir.name
    visual_path = sheet_dir / "visual.html"
    visual_body = render_ipv6_visual_model(root, manifest)
    manifest["visual_model"] = {**artifact_metadata(root, visual_path, visual_body), **VISUAL_METADATA}

    workbook_path = sheet_dir / "workbook.html"
    workbook_body = render_workbook_page(
        root=root,
        manifest=manifest,
        sheet_slug=slug,
        repo_href="https://github.com/daryll-swer/daryllswer.com-archive",
        font_asset_prefix="../../../assets/fonts",
    ).encode("utf-8")
    manifest["workbook_html"] = artifact_metadata(root, workbook_path, workbook_body)

    visual_path.write_bytes(visual_body)
    workbook_path.write_bytes(workbook_body)
    (sheet_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
