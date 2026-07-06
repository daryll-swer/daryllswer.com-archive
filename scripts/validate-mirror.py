#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Validate the generated public mirror."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UA = "daryllswer-com-archive-validator/1.0 (+https://www.daryllswer.com/)"
POSTS_ENDPOINT = "https://www.daryllswer.com/wp-json/wp/v2/posts?per_page=100&_embed=1"
POST_SITEMAP = "https://www.daryllswer.com/post-sitemap.xml"
ARCHIVE_EXCLUDED_PATTERNS = [
    re.compile(r"It would be appreciated if you could help me continue", re.I),
    re.compile(r"Click here</a>\s*to donate now", re.I),
    re.compile(r"Click here to donate now", re.I),
    re.compile(r"https://www\.daryllswer\.com/donation/?", re.I),
    re.compile(r"This article was sponsored by the cybersecurity company", re.I),
    re.compile(r"You can claim your free 30-day trial using this", re.I),
]
REMOTE_REFERENCE_ANCHOR_PATTERN = re.compile(r"https://www\.daryllswer\.com/[^)\s]+/#(?:h-)?references", re.I)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def request(url: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), dict(resp.headers.items())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_required(data, schema, path: str, errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append(f"{path}: expected object")
        return
    for key in schema.get("required", []):
        if key not in data:
            errors.append(f"{path}: missing required key `{key}`")


def markdown_image_paths(markdown: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown)


def validate_excluded_operational_ctas(path: Path, errors: list[str]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern in ARCHIVE_EXCLUDED_PATTERNS:
        if pattern.search(text):
            errors.append(f"{rel(path)}: excluded site-operational CTA remains")
            return


def validate_post(post_item: dict, errors: list[str], warnings: list[str]) -> None:
    bundle = ROOT / post_item["bundle_path"]
    index = bundle / "index.md"
    metadata_path = bundle / "metadata.json"
    asset_manifest_path = bundle / "assets" / "manifest.json"
    for required in [index, metadata_path, asset_manifest_path, bundle / "source" / "wordpress-post.json", bundle / "source" / "rendered-article.html", bundle / "source" / "canonical-page.html"]:
        if not required.exists():
            errors.append(f"{post_item['slug']}: missing {rel(required)}")
    for filtered_path in [index, bundle / "source" / "rendered-article.html", bundle / "source" / "wordpress-post.json"]:
        validate_excluded_operational_ctas(filtered_path, errors)
    if not metadata_path.exists():
        return
    metadata = load_json(metadata_path)
    schema = load_json(ROOT / "schemas" / "post-metadata.schema.json")
    check_required(metadata, schema, rel(metadata_path), errors)
    if metadata.get("canonical_url") != post_item.get("canonical_url"):
        errors.append(f"{post_item['slug']}: manifest canonical URL does not match metadata")
    featured = metadata.get("featured_image")
    if featured is None:
        warnings.append(f"{post_item['slug']}: no featured image detected")
    elif featured.get("local_path") and not (ROOT / featured["local_path"]).exists():
        errors.append(f"{post_item['slug']}: featured image missing at {featured['local_path']}")
    if index.exists():
        md = index.read_text(encoding="utf-8")
        if REMOTE_REFERENCE_ANCHOR_PATTERN.search(md):
            errors.append(f"{post_item['slug']}: generated Markdown still links reference markers to WordPress #h-references")
        for img_path in markdown_image_paths(md):
            if re.match(r"https?://", img_path):
                warnings.append(f"{post_item['slug']}: Markdown image still remote: {img_path}")
                continue
            target = bundle / img_path
            if not target.exists():
                errors.append(f"{post_item['slug']}: Markdown image missing: {img_path}")
    if asset_manifest_path.exists():
        manifest = load_json(asset_manifest_path)
        schema = load_json(ROOT / "schemas" / "asset-manifest.schema.json")
        check_required(manifest, schema, rel(asset_manifest_path), errors)
        for asset in manifest.get("assets", []):
            local_path = asset.get("local_path")
            if not local_path:
                errors.append(f"{post_item['slug']}: asset download failed for {asset.get('source_url')}")
                continue
            path = ROOT / local_path
            if not path.exists():
                errors.append(f"{post_item['slug']}: asset missing at {local_path}")
            elif asset.get("sha256") and sha256_file(path) != asset["sha256"]:
                errors.append(f"{post_item['slug']}: checksum mismatch for {local_path}")


def sitemap_urls() -> set[str]:
    body, _ = request(POST_SITEMAP)
    root = ET.fromstring(body)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = set()
    for url in root.findall("sm:url", ns):
        loc = url.findtext("sm:loc", default="", namespaces=ns)
        if loc and loc != "https://www.daryllswer.com/":
            urls.add(loc)
    return urls


def validate_spreadsheet(errors: list[str], warnings: list[str]) -> dict | None:
    manifest_path = ROOT / "data" / "sheets" / "as141253-ipv6-architecture-example" / "manifest.json"
    if not manifest_path.exists():
        errors.append("spreadsheet manifest missing")
        return None
    manifest = load_json(manifest_path)
    schema = load_json(ROOT / "schemas" / "spreadsheet-manifest.schema.json")
    check_required(manifest, schema, rel(manifest_path), errors)
    ods = manifest.get("ods", {})
    if not ods.get("path") or not (ROOT / ods["path"]).exists():
        errors.append("spreadsheet ODS export missing")
    elif sha256_file(ROOT / ods["path"]) != ods.get("sha256"):
        errors.append("spreadsheet ODS checksum mismatch")
    for tab in manifest.get("tabs", []):
        csv_info = tab.get("csv", {})
        csv_path = ROOT / csv_info.get("path", "")
        if not csv_path.exists():
            errors.append(f"sheet tab {tab.get('name')}: CSV missing")
            continue
        if sha256_file(csv_path) != csv_info.get("sha256"):
            errors.append(f"sheet tab {tab.get('name')}: CSV checksum mismatch")
        try:
            with csv_path.open(newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.reader(fh))
            if not rows:
                errors.append(f"sheet tab {tab.get('name')}: CSV has no rows")
        except Exception as exc:
            errors.append(f"sheet tab {tab.get('name')}: CSV parse failed: {exc}")
        html_info = tab.get("html", {})
        if not (ROOT / html_info.get("path", "")).exists():
            warnings.append(f"sheet tab {tab.get('name')}: HTML snapshot missing")
        csvw_info = tab.get("csvw", {})
        if not (ROOT / csvw_info.get("path", "")).exists():
            warnings.append(f"sheet tab {tab.get('name')}: CSVW metadata missing")
    return manifest


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    report: list[str] = ["# Validation", "", f"Generated: {now_iso()}", ""]

    archive_path = ROOT / "archive-manifest.json"
    if not archive_path.exists():
        errors.append("archive-manifest.json missing; run make sync first")
        archive = None
    else:
        archive = load_json(archive_path)
        schema = load_json(ROOT / "schemas" / "archive-manifest.schema.json")
        check_required(archive, schema, "archive-manifest.json", errors)

    if archive:
        post_count = archive.get("post_count")
        posts = archive.get("posts", [])
        if post_count != len(posts):
            errors.append(f"archive post_count {post_count} does not match posts length {len(posts)}")
        try:
            body, headers = request(POSTS_ENDPOINT)
            live_posts = json.loads(body.decode("utf-8"))
            live_total = int(headers.get("X-WP-Total", len(live_posts)))
            if live_total != len(posts):
                errors.append(f"WordPress REST reports {live_total} posts, archive has {len(posts)}")
            report.extend(["## WordPress REST", "", f"- Live X-WP-Total: {live_total}", f"- Archived posts: {len(posts)}", ""])
        except Exception as exc:
            warnings.append(f"could not verify WordPress REST count: {exc}")

        try:
            sm_urls = sitemap_urls()
            manifest_urls = {p.get("canonical_url") for p in posts}
            missing = sorted(sm_urls - manifest_urls)
            extra = sorted(manifest_urls - sm_urls)
            if missing:
                errors.append(f"sitemap URLs missing from archive: {missing}")
            if extra:
                warnings.append(f"archive URLs not present in post sitemap: {extra}")
            report.extend(["## Sitemap Cross-Check", "", f"- Sitemap post URLs: {len(sm_urls)}", f"- Archive URLs: {len(manifest_urls)}", ""])
        except Exception as exc:
            warnings.append(f"could not verify sitemap: {exc}")

        for post in posts:
            validate_post(post, errors, warnings)

    sheet_manifest = validate_spreadsheet(errors, warnings)
    if sheet_manifest:
        report.extend(["## Spreadsheet", "", f"- Tabs: {len(sheet_manifest.get('tabs', []))}", f"- ODS: `{sheet_manifest.get('ods', {}).get('path')}`", ""])

    report.extend(["## Result", ""])
    report.append(f"- Errors: {len(errors)}")
    report.append(f"- Warnings: {len(warnings)}")
    report.append("")
    if errors:
        report.extend(["## Errors", ""])
        report.extend(f"- {e}" for e in errors)
        report.append("")
    if warnings:
        report.extend(["## Warnings", ""])
        report.extend(f"- {w}" for w in warnings)
        report.append("")
    if not errors:
        report.extend(["## Status", "", "Validation passed with no blocking errors.", ""])
    (ROOT / "docs" / "VALIDATION.md").write_text("\n".join(report), encoding="utf-8")
    print(f"validation errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
