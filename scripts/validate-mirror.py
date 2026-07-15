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
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

try:
    import lxml.html
except Exception as exc:  # pragma: no cover - environment guard
    raise SystemExit("Missing dependency: lxml. Install requirements.txt first.") from exc

from wordpress_palette import WORDPRESS_COLOR_PRESETS


ROOT = Path(__file__).resolve().parents[1]
UA = "daryllswer-com-archive-validator/1.0 (+https://www.daryllswer.com/)"
POSTS_ENDPOINT = "https://www.daryllswer.com/wp-json/wp/v2/posts?per_page=100&_embed=1"
POST_SITEMAP = "https://www.daryllswer.com/post-sitemap.xml"
PAGES_BASE_URL = "https://daryll-swer.github.io/daryllswer.com-archive/"
LOCALISABLE_HOSTS = {"www.daryllswer.com", "daryllswer.com"}
TEXT_FRAGMENT_PREFIX = ":~:text="
README_BRAND_ASSET_PATH = "assets/readme/13_DS_Logo_Dark_Mode_SEO.png"
README_BRAND_MANIFEST_PATH = "assets/readme/manifest.json"
README_BRAND_NOTICE_PATH = "LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt"
README_BRAND_COPYRIGHT_NOTICE = "© 2026 Daryll Swer. All rights reserved."
PAGES_FAVICON_SOURCE_PATH = "assets/brand/01_DS_Favicon_Dark_Mode.png"
PAGES_FAVICON_MANIFEST_PATH = "assets/brand/manifest.json"
PAGES_FAVICON_OUTPUT_PATH = "docs/assets/brand/01_DS_Favicon_Dark_Mode-512.png"
PAGES_FAVICON_SIZE = 512
ARCHIVE_EXCLUDED_PATTERNS = [
    re.compile(r"It would be appreciated if you could help me continue", re.I),
    re.compile(r"Click here</a>\s*to donate now", re.I),
    re.compile(r"Click here to donate now", re.I),
    re.compile(r"https://www\.daryllswer\.com/donation/?", re.I),
    re.compile(r"This article was sponsored by the cybersecurity company", re.I),
    re.compile(r"You can claim your free 30-day trial using this", re.I),
]
REMOTE_REFERENCE_ANCHOR_PATTERN = re.compile(r"https://www\.daryllswer\.com/[^)\s]+/#(?:h-)?references", re.I)
WORDPRESS_MEDIA_PATTERN = re.compile(r"https://www\.daryllswer\.com/wp-content/uploads/", re.I)
GOOGLE_SHEET_PATTERN = re.compile(r"https://docs\.google\.com/spreadsheets/d/e/2PACX-1vQ32t5C9BW-rV36gUo93uYcLw9GMPqg7BMks8u17dlLhWmIUzIdCe4iexLBQKdnDwykAom929K2dTxR/pubhtml", re.I)
WORDPRESS_COLOUR_CLASS_RE = re.compile(r"^has-[a-z0-9-]+(?:color|background-color|border-color)$")


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


def source_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    name = urllib.parse.unquote(Path(parsed.path).name).replace("\x00", "")
    return name.replace("/", "-").replace("\\", "-").strip()


def canonical_url_key(url: str) -> str | None:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc.lower()
    if host not in LOCALISABLE_HOSTS:
        return None
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(("https", "www.daryllswer.com", path, "", "")).rstrip("/")


def markdown_body(markdown: str) -> str:
    return re.sub(r"\A---\s*\n.*?\n---\s*\n", "", markdown, flags=re.S)


def hrefs_from_markdown(markdown: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)


def validate_localisable_markdown_links(post_item: dict, markdown: str, archived_keys: set[str], errors: list[str]) -> None:
    for href in hrefs_from_markdown(markdown_body(markdown)):
        if not re.match(r"https?://", href):
            continue
        key = canonical_url_key(href)
        if key and key in archived_keys:
            errors.append(f"{post_item['slug']}: Markdown body still links archived canonical post externally: {href}")


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


def validate_post(post_item: dict, errors: list[str], warnings: list[str], archived_keys: set[str]) -> None:
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
        validate_localisable_markdown_links(post_item, md, archived_keys, errors)
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
            if "/wp-content/uploads/" in (asset.get("source_url") or ""):
                expected = asset.get("source_filename") or source_filename_from_url(asset.get("source_url") or "")
                stored = asset.get("stored_filename") or Path(local_path).name
                if expected and stored != expected:
                    errors.append(f"{post_item['slug']}: asset filename not preserved for {local_path}; expected {expected}")
                if asset.get("filename_preserved") is not True:
                    errors.append(f"{post_item['slug']}: asset manifest does not confirm filename preservation for {local_path}")


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
    workbook = manifest.get("workbook_html", {})
    workbook_path = ROOT / workbook.get("path", "")
    if not workbook.get("path") or not workbook_path.exists():
        errors.append("spreadsheet tabbed workbook HTML missing")
    elif sha256_file(workbook_path) != workbook.get("sha256"):
        errors.append("spreadsheet tabbed workbook HTML checksum mismatch")
    else:
        workbook_html = workbook_path.read_text(encoding="utf-8", errors="replace")
        expected_tabs = len(manifest.get("tabs", []))
        if "sheet-tabs" not in workbook_html:
            errors.append("spreadsheet tabbed workbook HTML missing sheet tabs")
        if workbook_html.count('class="sheet-tab-label"') != expected_tabs:
            errors.append("spreadsheet tabbed workbook HTML tab count does not match manifest")
    hierarchy = manifest.get("cidr_hierarchy", {})
    if hierarchy:
        for key in ["json", "dot"]:
            item = hierarchy.get(key, {})
            path_value = item.get("path")
            if not path_value or not (ROOT / path_value).exists():
                errors.append(f"spreadsheet CIDR hierarchy {key} artefact missing")
                continue
            if item.get("sha256") and sha256_file(ROOT / path_value) != item["sha256"]:
                errors.append(f"spreadsheet CIDR hierarchy {key} checksum mismatch")
        if "html" in hierarchy:
            errors.append("spreadsheet CIDR hierarchy must not expose a redundant HTML reader model")
        if (ROOT / "data" / "sheets" / "as141253-ipv6-architecture-example" / "cidr-hierarchy.html").exists():
            errors.append("spreadsheet retired CIDR hierarchy HTML page remains in source output")
        json_path = ROOT / hierarchy.get("json", {}).get("path", "")
        if json_path.exists():
            try:
                tree = load_json(json_path)
                if not tree.get("prefix") or not tree.get("children"):
                    errors.append("spreadsheet CIDR hierarchy JSON does not contain a prefix tree")
            except Exception as exc:
                errors.append(f"spreadsheet CIDR hierarchy JSON parse failed: {exc}")
    source_visual_dir = ROOT / "data" / "sheets" / "as141253-ipv6-architecture-example"
    visual_model = manifest.get("visual_model", {})
    visual_model_path = ROOT / visual_model.get("path", "")
    if not visual_model.get("path") or not visual_model_path.exists():
        errors.append("spreadsheet full-hierarchy visual model missing")
    elif visual_model.get("sha256") and sha256_file(visual_model_path) != visual_model["sha256"]:
        errors.append("spreadsheet full-hierarchy visual model checksum mismatch")
    else:
        visual_model_html = visual_model_path.read_text(encoding="utf-8", errors="replace")
        for marker in ["AS141253 IPv6 Visual Model", "Full hierarchy", "final-tree-node", "data-reserved-group", "<details"]:
            if marker not in visual_model_html:
                errors.append(f"spreadsheet full-hierarchy visual model missing `{marker}`")
        for marker in [
            'id="at-a-glance-allocation"',
            'id="operational-branches"',
            'id="purpose-map"',
            "<h2>At-a-glance allocation</h2>",
            "<h2>Operational branches</h2>",
            "<h2>Purpose map</h2>",
            ">Visual foundations<",
            "visual-options.html",
        ]:
            if marker in visual_model_html:
                errors.append(f"spreadsheet full-hierarchy visual model exposes legacy marker `{marker}`")
        if "<script" in visual_model_html:
            errors.append("spreadsheet full-hierarchy visual model should not require JavaScript")

    if "visual_options" in manifest:
        errors.append("spreadsheet manifest still exposes retired visual_options metadata")
    legacy = manifest.get("legacy_visual_models", {})
    legacy_path_value = str(legacy.get("path") or "")
    legacy_path = ROOT / legacy_path_value
    expected_legacy_prefix = "data/sheets/as141253-ipv6-architecture-example/legacy-visual-models/"
    if not legacy_path_value.startswith(expected_legacy_prefix) or not legacy_path.exists():
        errors.append("spreadsheet legacy visual-model reference is missing or not outside GitHub Pages output")
    elif legacy.get("sha256") and sha256_file(legacy_path) != legacy["sha256"]:
        errors.append("spreadsheet legacy visual-model reference checksum mismatch")
    elif "excluded from GitHub Pages" not in legacy_path.read_text(encoding="utf-8", errors="replace"):
        errors.append("spreadsheet legacy visual-model reference does not describe Pages exclusion")
    if legacy.get("pages_published") is not False:
        errors.append("spreadsheet legacy visual-model metadata must state pages_published=false")
    for filename in [
        "visual-options.html",
        "visual-option-branch-cards.html",
        "visual-option-collapsible-dendrogram.html",
        "visual-option-purpose-cluster-graph.html",
    ]:
        if (source_visual_dir / filename).exists():
            errors.append(f"spreadsheet legacy visual page remains in public source location: {filename}")

    source_readme = source_visual_dir / "README.md"
    if source_readme.exists():
        source_readme_text = source_readme.read_text(encoding="utf-8", errors="replace")
        if "visual.html" not in source_readme_text:
            errors.append("spreadsheet README missing full-hierarchy visual model link")
        if "visual-options.html" in source_readme_text or "Visual foundations" in source_readme_text:
            errors.append("spreadsheet README still exposes legacy visual models")
        if "cidr-hierarchy.html" in source_readme_text:
            errors.append("spreadsheet README still exposes retired CIDR hierarchy HTML")
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


def parse_html_file(path: Path):
    return lxml.html.fromstring(path.read_text(encoding="utf-8", errors="replace"))


def class_predicate(class_name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {class_name} ')"


def wordpress_colour_classes(doc) -> set[str]:
    classes: set[str] = set()
    for el in doc.xpath("//*[@class]"):
        for class_name in (el.get("class") or "").split():
            if class_name == "has-inline-color" or WORDPRESS_COLOUR_CLASS_RE.match(class_name):
                classes.add(class_name)
    return classes


def validate_wordpress_palette_css(css: str, used_classes: set[str], errors: list[str]) -> None:
    for name, value in WORDPRESS_COLOR_PRESETS.items():
        marker = f"--wp--preset--color--{name}: {value};"
        if marker not in css:
            errors.append(f"GitHub Pages theme CSS missing WordPress colour preset `{marker}`")
    for class_name in sorted(used_classes):
        if class_name == "has-inline-color":
            for marker in ["mark.has-inline-color", "background: transparent", "padding: 0"]:
                if marker not in css:
                    errors.append(f"GitHub Pages theme CSS missing WordPress inline colour marker `{marker}`")
            continue
        if f".{class_name}" not in css:
            errors.append(f"GitHub Pages theme CSS missing WordPress colour class `.{class_name}`")


def heading_target_id(heading_id: str) -> str:
    return heading_id[2:] if heading_id.startswith("h-") else heading_id


def fragment_href(target_id: str) -> str:
    return "#" + urllib.parse.quote(target_id, safe="-._~")


def article_body_links(page: Path):
    try:
        doc = parse_html_file(page)
    except Exception:
        return []
    links = []
    for body in doc.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' article-body ')]"):
        links.extend(body.xpath(".//a[@href]"))
    return links


def validate_pages_heading_controls(page: Path, post: dict, errors: list[str]) -> None:
    try:
        doc = parse_html_file(page)
    except Exception as exc:
        errors.append(f"{rel(page)}: generated article HTML parse failed: {exc}")
        return
    headings = doc.xpath(
        f"//*[ {class_predicate('article-body')} ]"
        "//*[self::h2 or self::h3 or self::h4 or self::h5 or self::h6][@id]"
    )
    for heading in headings:
        heading_id = heading.get("id")
        target_id = heading_target_id(heading_id)
        href = fragment_href(target_id)
        title_links = heading.xpath(
            f".//a[not({class_predicate('heading-permalink')}) and @href=$href]",
            href=href,
        )
        non_control_links = heading.xpath(f".//a[not({class_predicate('heading-permalink')})]")
        permalinks = heading.xpath(
            f"./a[{class_predicate('heading-permalink')} and @href=$href and @aria-label]",
            href=href,
        )
        copy_buttons = heading.xpath(
            f"./button[{class_predicate('heading-copy')} and @data-anchor=$target and @aria-label]",
            target=target_id,
        )
        if not title_links and not non_control_links:
            errors.append(f"{post['slug']}: heading `{heading_id}` is missing a clickable title permalink")
        if not permalinks:
            errors.append(f"{post['slug']}: heading `{heading_id}` is missing visible permalink control")
        if not copy_buttons:
            errors.append(f"{post['slug']}: heading `{heading_id}` is missing copy-link button")


def docs_target_for_href(current_page: Path, href: str) -> Path | None:
    parsed = urllib.parse.urlsplit(href)
    if parsed.scheme in {"http", "https"}:
        if not href.startswith(PAGES_BASE_URL):
            return None
        rel_href = href[len(PAGES_BASE_URL):]
        parsed = urllib.parse.urlsplit(rel_href)
        target = ROOT / "docs" / urllib.parse.unquote(parsed.path.lstrip("/"))
    else:
        target = (current_page.parent / urllib.parse.unquote(parsed.path)).resolve()
    try:
        target.relative_to((ROOT / "docs").resolve())
    except ValueError:
        return None
    if target.is_dir() or href.endswith("/"):
        target = target / "index.html"
    if target.name == "":
        target = target / "index.html"
    return target


def validate_pages_article_links(posts: list[dict], archived_keys: set[str], errors: list[str]) -> None:
    ids_by_page: dict[Path, set[str]] = {}
    pages = [ROOT / "docs" / "posts" / post["slug"] / "index.html" for post in posts]
    for page in pages:
        if not page.exists():
            continue
        try:
            doc = parse_html_file(page)
        except Exception as exc:
            errors.append(f"{rel(page)}: generated article HTML parse failed: {exc}")
            continue
        ids_by_page[page.resolve()] = {item for item in doc.xpath("//*[@id]/@id") if item}

    for post, page in zip(posts, pages):
        if not page.exists():
            continue
        for anchor in article_body_links(page):
            href = anchor.get("href") or ""
            key = canonical_url_key(href)
            if key and key in archived_keys:
                errors.append(f"{post['slug']}: GitHub Pages article body still links archived canonical post externally: {href}")

            parsed = urllib.parse.urlsplit(href)
            fragment = parsed.fragment
            if not fragment or fragment.startswith(TEXT_FRAGMENT_PREFIX):
                continue
            target = docs_target_for_href(page, href)
            if not target or not target.exists():
                continue
            target_ids = ids_by_page.get(target.resolve())
            if target_ids is None:
                try:
                    target_ids = {item for item in parse_html_file(target).xpath("//*[@id]/@id") if item}
                    ids_by_page[target.resolve()] = target_ids
                except Exception:
                    continue
            if fragment not in target_ids:
                errors.append(f"{post['slug']}: local fragment link `{href}` has no matching `{fragment}` ID in {rel(target)}")


def validate_font_assets(errors: list[str]) -> dict | None:
    manifest_path = ROOT / "assets" / "fonts" / "manifest.json"
    if not manifest_path.exists():
        errors.append("self-hosted font manifest missing at assets/fonts/manifest.json")
        return None
    manifest = load_json(manifest_path)
    for item in manifest.get("files", []):
        source_path = ROOT / item.get("file", "")
        generated_path = ROOT / "docs" / item.get("file", "")
        for path in [source_path, generated_path]:
            if not path.exists():
                errors.append(f"font asset missing: {rel(path)}")
            elif item.get("sha256") and sha256_file(path) != item["sha256"]:
                errors.append(f"font asset checksum mismatch: {rel(path)}")
    css_path = ROOT / "docs" / "assets" / "theme.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8", errors="replace")
        for marker in ["font-family: 'Poppins'", "font-family: 'Raleway'", "font-display: swap", "var(--font-body)", "var(--font-heading)"]:
            if marker not in css:
                errors.append(f"GitHub Pages theme CSS missing font marker `{marker}`")
    return manifest


def validate_brand_assets(errors: list[str]) -> dict | None:
    """Keep the proprietary README logo and Pages favicon outside archive licences."""
    asset_path = ROOT / README_BRAND_ASSET_PATH
    manifest_path = ROOT / README_BRAND_MANIFEST_PATH
    notice_path = ROOT / README_BRAND_NOTICE_PATH
    readme_path = ROOT / "README.md"
    licensing_path = ROOT / "LICENSING.md"
    favicon_source_path = ROOT / PAGES_FAVICON_SOURCE_PATH
    favicon_manifest_path = ROOT / PAGES_FAVICON_MANIFEST_PATH
    favicon_output_path = ROOT / PAGES_FAVICON_OUTPUT_PATH

    for path in [
        asset_path,
        manifest_path,
        notice_path,
        readme_path,
        licensing_path,
        favicon_source_path,
        favicon_manifest_path,
        favicon_output_path,
    ]:
        if not path.exists():
            errors.append(f"proprietary brand asset requirement missing: {rel(path)}")
    if not asset_path.exists() or not manifest_path.exists():
        return None

    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        errors.append(f"README brand asset manifest parse failed: {exc}")
        return None
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != 1:
        errors.append("README brand asset manifest must contain exactly one asset")
        return None
    asset = assets[0]
    if asset.get("path") != Path(README_BRAND_ASSET_PATH).name:
        errors.append("README brand asset manifest path does not match the header logo")
    if asset.get("copyright_notice") != README_BRAND_COPYRIGHT_NOTICE:
        errors.append("README brand asset manifest copyright notice is missing or incorrect")
    if asset.get("licence_status") != "Proprietary; no public licence granted":
        errors.append("README brand asset manifest must state proprietary no-public-licence status")
    if asset.get("rights_notice") != "../../" + README_BRAND_NOTICE_PATH:
        errors.append("README brand asset manifest rights notice path is incorrect")
    expected_hash = asset.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append("README brand asset manifest SHA-256 is missing or invalid")
    elif sha256_file(asset_path) != expected_hash:
        errors.append("README brand asset checksum mismatch")

    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8", errors="replace")
        if f'src="{README_BRAND_ASSET_PATH}"' not in readme:
            errors.append("README does not render the proprietary header logo")
        if 'href="#copyright-and-licences"' not in readme:
            errors.append("README logo must link to the local copyright-and-licences section")
        if "## Copyright and Licences" not in readme:
            errors.append("README is missing the copyright-and-licences destination section")
        if not re.search(r"© 2026 Daryll Swer\. All\s+rights reserved\.", readme):
            errors.append("README does not state the proprietary logo copyright notice")
    if licensing_path.exists():
        licensing = licensing_path.read_text(encoding="utf-8", errors="replace")
        for marker in [README_BRAND_ASSET_PATH, README_BRAND_NOTICE_PATH, "MIT", "CC-BY-NC-SA-4.0"]:
            if marker not in licensing:
                errors.append(f"LICENSING.md is missing README brand asset marker `{marker}`")
    if notice_path.exists():
        notice = notice_path.read_text(encoding="utf-8", errors="replace")
        for marker in [README_BRAND_COPYRIGHT_NOTICE, README_BRAND_ASSET_PATH, "no permission is granted"]:
            if marker not in notice:
                errors.append(f"README proprietary asset notice is missing `{marker}`")
    if (ROOT / "docs" / README_BRAND_ASSET_PATH).exists():
        errors.append("README proprietary logo must not be copied into GitHub Pages output")

    if not favicon_source_path.exists() or not favicon_manifest_path.exists() or not favicon_output_path.exists():
        return None
    try:
        favicon_manifest = load_json(favicon_manifest_path)
    except Exception as exc:
        errors.append(f"Pages favicon manifest parse failed: {exc}")
        return None
    favicon_assets = favicon_manifest.get("assets")
    if not isinstance(favicon_assets, list) or len(favicon_assets) != 1:
        errors.append("Pages favicon manifest must contain exactly one asset")
        return None
    favicon = favicon_assets[0]
    if favicon.get("path") != Path(PAGES_FAVICON_SOURCE_PATH).name:
        errors.append("Pages favicon manifest path does not match the source image")
    if favicon.get("copyright_notice") != README_BRAND_COPYRIGHT_NOTICE:
        errors.append("Pages favicon manifest copyright notice is missing or incorrect")
    if favicon.get("licence_status") != "Proprietary; no public licence granted":
        errors.append("Pages favicon manifest must state proprietary no-public-licence status")
    if favicon.get("rights_notice") != "../../" + README_BRAND_NOTICE_PATH:
        errors.append("Pages favicon manifest rights notice path is incorrect")
    if favicon.get("pages_derivative", {}).get("path") != PAGES_FAVICON_OUTPUT_PATH:
        errors.append("Pages favicon manifest derivative path is incorrect")
    derivative = favicon.get("pages_derivative", {})
    if (derivative.get("width"), derivative.get("height")) != (PAGES_FAVICON_SIZE, PAGES_FAVICON_SIZE):
        errors.append("Pages favicon manifest derivative dimensions are incorrect")
    expected_hash = favicon.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append("Pages favicon manifest SHA-256 is missing or invalid")
    elif sha256_file(favicon_source_path) != expected_hash:
        errors.append("Pages favicon source checksum mismatch")

    previous_pixel_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 150_000_000
    try:
        with Image.open(favicon_source_path) as image:
            if image.format != "PNG" or image.size != (favicon.get("width"), favicon.get("height")):
                errors.append("Pages favicon source format or dimensions do not match its manifest")
        with Image.open(favicon_output_path) as image:
            if image.format != "PNG" or image.size != (PAGES_FAVICON_SIZE, PAGES_FAVICON_SIZE):
                errors.append("Pages favicon derivative must be a 512 px PNG")
    except Exception as exc:
        errors.append(f"Pages favicon image validation failed: {exc}")
    finally:
        Image.MAX_IMAGE_PIXELS = previous_pixel_limit

    def validate_favicon_page(page: Path, href: str, *, expects_header: bool = False) -> None:
        if not page.exists():
            errors.append(f"Pages favicon target missing: {rel(page)}")
            return
        page_text = page.read_text(encoding="utf-8", errors="replace")
        marker = f'<link rel="icon" type="image/png" href="{href}">'
        if marker not in page_text:
            errors.append(f"Pages favicon link missing from {rel(page)}")
        if expects_header:
            header_marker = f'<img class="brand-mark" src="{href}" alt=""'
            if header_marker not in page_text:
                errors.append(f"Pages favicon header image missing from {rel(page)}")

    docs_root = ROOT / "docs"
    validate_favicon_page(docs_root / "index.html", f"assets/brand/{Path(PAGES_FAVICON_OUTPUT_PATH).name}", expects_header=True)
    for page in sorted((docs_root / "posts").glob("*/index.html")):
        validate_favicon_page(page, f"../../assets/brand/{Path(PAGES_FAVICON_OUTPUT_PATH).name}", expects_header=True)
    sheet_dir = docs_root / "sheets" / "as141253-ipv6-architecture-example"
    for page in [sheet_dir / "index.html", sheet_dir / "visual.html"]:
        validate_favicon_page(page, f"../../assets/brand/{Path(PAGES_FAVICON_OUTPUT_PATH).name}")
    for page in docs_root.rglob("*.html"):
        if 'class="brand-mark">DS</span>' in page.read_text(encoding="utf-8", errors="replace"):
            errors.append(f"Pages generic DS brand mark remains in {rel(page)}")
    if (docs_root / "assets" / "brand" / Path(PAGES_FAVICON_SOURCE_PATH).name).exists():
        errors.append("Pages must not publish the full-resolution proprietary favicon source")
    return {"readme_logo": asset, "pages_favicon": favicon}


def validate_pages_site(posts: list[dict], errors: list[str], warnings: list[str], archived_keys: set[str]) -> dict | None:
    site_index = ROOT / "docs" / "index.html"
    site_css = ROOT / "docs" / "assets" / "theme.css"
    site_js = ROOT / "docs" / "assets" / "archive.js"
    if not site_index.exists():
        warnings.append("GitHub Pages site missing; run make render-site")
        return None
    font_manifest = None
    if not site_css.exists():
        errors.append("GitHub Pages theme missing at docs/assets/theme.css")
        css_text = ""
    else:
        css_text = site_css.read_text(encoding="utf-8", errors="replace")
    if not site_js.exists():
        errors.append("GitHub Pages heading interaction script missing at docs/assets/archive.js")
    else:
        script = site_js.read_text(encoding="utf-8", errors="replace")
        for marker in ["heading-copy", "navigator.clipboard.writeText", "window.location.hash"]:
            if marker not in script:
                errors.append(f"GitHub Pages heading interaction script missing `{marker}`")
    font_manifest = validate_font_assets(errors)
    if not (ROOT / "docs" / ".nojekyll").exists():
        errors.append("GitHub Pages .nojekyll marker missing")
    sheet_page = ROOT / "docs" / "sheets" / "as141253-ipv6-architecture-example" / "index.html"
    if not sheet_page.exists():
        errors.append("GitHub Pages AS141253 workbook page missing")
    else:
        sheet_html = sheet_page.read_text(encoding="utf-8", errors="replace")
        if "sheet-tabs" not in sheet_html:
            errors.append("GitHub Pages AS141253 workbook page missing sheet tabs")
        expected_tabs = len(load_json(ROOT / "data" / "sheets" / "as141253-ipv6-architecture-example" / "manifest.json").get("tabs", []))
        if sheet_html.count('class="sheet-tab-label"') != expected_tabs:
            errors.append("GitHub Pages AS141253 workbook tab count does not match manifest")
        if "visual.html" not in sheet_html or "Visual model" not in sheet_html:
            errors.append("GitHub Pages AS141253 workbook page missing visual model link")
        if "visual-options.html" in sheet_html or "Visual foundations" in sheet_html:
            errors.append("GitHub Pages AS141253 workbook page exposes retired visual models")
        if "cidr-hierarchy.html" in sheet_html or "CIDR hierarchy" in sheet_html:
            errors.append("GitHub Pages AS141253 workbook page exposes retired CIDR hierarchy HTML")
        if 'href="../../index.html"' in sheet_html:
            errors.append("GitHub Pages AS141253 workbook navigation should use ../../ instead of ../../index.html")
        sheet_manifest = load_json(ROOT / "data" / "sheets" / "as141253-ipv6-architecture-example" / "manifest.json")
        visual_model_meta = sheet_manifest.get("visual_model", {})
        if not visual_model_meta.get("path") or not visual_model_meta.get("sha256"):
            errors.append("AS141253 sheet manifest missing visual_model artefact metadata")
        visual_model = sheet_page.parent / "visual.html"
        if not visual_model.exists():
            errors.append("GitHub Pages AS141253 visual model page missing")
        else:
            visual_model_html = visual_model.read_text(encoding="utf-8", errors="replace")
            for marker in [
                "AS141253 IPv6 Visual Model",
                "Full hierarchy",
                "final-tree-node",
                "data-reserved-group",
                "<details",
            ]:
                if marker not in visual_model_html:
                    errors.append(f"GitHub Pages AS141253 visual model page missing `{marker}`")
            for marker in [
                'id="at-a-glance-allocation"',
                'id="operational-branches"',
                'id="purpose-map"',
                "<h2>At-a-glance allocation</h2>",
                "<h2>Operational branches</h2>",
                "<h2>Purpose map</h2>",
                ">Visual foundations<",
                "visual-options.html",
                "cidr-hierarchy.html",
                ">CIDR hierarchy<",
            ]:
                if marker in visual_model_html:
                    errors.append(f"GitHub Pages AS141253 visual model page exposes legacy marker `{marker}`")
            if "../../../assets/fonts/" in visual_model_html or "/Users/" in visual_model_html or "file://" in visual_model_html:
                errors.append("GitHub Pages AS141253 visual model page leaks a source font or local filesystem path")
            if "<script" in visual_model_html:
                errors.append("GitHub Pages AS141253 visual model page should not require JavaScript")

        legacy_pages = [
            "cidr-hierarchy.html",
            "visual-options.html",
            "visual-option-branch-cards.html",
            "visual-option-collapsible-dendrogram.html",
            "visual-option-purpose-cluster-graph.html",
        ]
        for filename in legacy_pages:
            if (sheet_page.parent / filename).exists():
                errors.append(f"GitHub Pages AS141253 legacy visual page remains published: {filename}")
        if (sheet_page.parent / "legacy-visual-models").exists():
            errors.append("GitHub Pages AS141253 legacy visual-model archive must not be copied under docs")

        for page in (ROOT / "docs").rglob("*.html"):
            page_html = page.read_text(encoding="utf-8", errors="replace")
            for legacy_route in legacy_pages:
                if legacy_route in page_html:
                    errors.append(f"GitHub Pages page still links a legacy AS141253 visual route: {rel(page)}")
                    break
    index_html = site_index.read_text(encoding="utf-8", errors="replace")
    if "posts/" not in index_html:
        errors.append("GitHub Pages index does not link to generated post pages")
    if 'href="index.html"' in index_html:
        errors.append("GitHub Pages index navigation should use the clean ./ root URL, not index.html")
    if 'rel="canonical" href="https://daryll-swer.github.io/daryllswer.com-archive/index.html"' in index_html:
        errors.append("GitHub Pages index canonical URL should use the clean project root")
    for post in posts:
        page = ROOT / "docs" / "posts" / post["slug"] / "index.html"
        if not page.exists():
            errors.append(f"{post['slug']}: GitHub Pages article missing")
            continue
        html = page.read_text(encoding="utf-8", errors="replace")
        try:
            source_doc = parse_html_file(ROOT / post["bundle_path"] / "source" / "rendered-article.html")
            page_doc = parse_html_file(page)
            source_colour_classes = wordpress_colour_classes(source_doc)
            if source_colour_classes:
                page_colour_classes = wordpress_colour_classes(page_doc)
                missing = sorted(source_colour_classes - page_colour_classes)
                if missing:
                    errors.append(f"{post['slug']}: GitHub Pages article dropped WordPress colour classes: {missing}")
                validate_wordpress_palette_css(css_text, source_colour_classes, errors)
        except Exception as exc:
            errors.append(f"{post['slug']}: WordPress colour class validation failed: {exc}")
        validate_excluded_operational_ctas(page, errors)
        if 'href="../../index.html"' in html:
            errors.append(f"{post['slug']}: GitHub Pages article navigation should use ../../ instead of ../../index.html")
        if 'src="../../assets/archive.js"' not in html:
            errors.append(f"{post['slug']}: GitHub Pages article missing heading interaction script")
        if WORDPRESS_MEDIA_PATTERN.search(html):
            errors.append(f"{post['slug']}: GitHub Pages article still links WordPress upload media")
        if post["slug"] == "ipv6-architecture-and-subnetting-guide-for-network-engineers-and-operators":
            if GOOGLE_SHEET_PATTERN.search(html):
                errors.append(f"{post['slug']}: GitHub Pages article still links the Google Sheet instead of the repo sheet page")
            if "../../sheets/as141253-ipv6-architecture-example/visual.html" not in html:
                errors.append(f"{post['slug']}: GitHub Pages article missing repo-hosted AS141253 visual model link")
            if "media-embed" not in html:
                errors.append(f"{post['slug']}: GitHub Pages article missing podcast embed wrapper")
        validate_pages_heading_controls(page, post, errors)
    validate_pages_article_links(posts, archived_keys, errors)
    return font_manifest


def validate_drift_automation(errors: list[str], warnings: list[str]) -> dict | None:
    workflow = ROOT / ".github" / "workflows" / "canonical-drift.yml"
    status_path = ROOT / "archive-status.json"
    report_path = ROOT / "docs" / "CANONICAL_DRIFT.md"
    if not workflow.exists():
        errors.append("canonical drift GitHub Actions workflow missing")
    else:
        text = workflow.read_text(encoding="utf-8", errors="replace")
        active_lines = []
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.split("#", 1)[0].rstrip()
            if line.strip():
                active_lines.append((lineno, line))

        def has_active_line(pattern: str) -> bool:
            return any(re.search(pattern, line) for _, line in active_lines)

        for marker, pattern in [
            ("schedule:", r"^\s*schedule:\s*$"),
            ("workflow_dispatch:", r"^\s*workflow_dispatch:\s*$"),
            ("concurrency:", r"^\s*concurrency:\s*$"),
            ("timeout-minutes:", r"^\s*timeout-minutes:\s*10\s*$"),
            ("scripts/check-canonical-drift.py", r"scripts/check-canonical-drift\.py"),
        ]:
            if not has_active_line(pattern):
                errors.append(f"canonical drift workflow missing active `{marker}`")

        step_blocks: dict[str, list[tuple[int, str]]] = {}
        current_name: str | None = None
        current_lines: list[tuple[int, str]] = []
        for lineno, line in active_lines:
            match = re.match(r"^\s*-\s+name:\s*(.+?)\s*$", line)
            if match:
                if current_name is not None:
                    step_blocks[current_name] = current_lines
                current_name = match.group(1).strip().strip("'\"")
                current_lines = [(lineno, line)]
            elif current_name is not None:
                current_lines.append((lineno, line))
        if current_name is not None:
            step_blocks[current_name] = current_lines

        required_steps = [
            "Check out repository",
            "Set up Python",
            "Install Python dependencies",
            "Check canonical drift",
            "Validate public archive",
        ]
        for step_name in required_steps:
            if step_name not in step_blocks:
                errors.append(f"canonical drift workflow missing active step `{step_name}`")

        def step_has(step_name: str, pattern: str) -> bool:
            return any(re.search(pattern, line.strip()) for _, line in step_blocks.get(step_name, []))

        required_step_lines = [
            ("Check out repository", r"^uses:\s*actions/checkout@v6\s*$", "actions/checkout@v6"),
            ("Set up Python", r"^uses:\s*actions/setup-python@v6\s*$", "actions/setup-python@v6"),
            ("Set up Python", r"^python-version:\s*['\"]?3\.12['\"]?\s*$", "python-version 3.12"),
            ("Set up Python", r"^cache:\s*['\"]?pip['\"]?\s*$", "pip cache"),
            ("Set up Python", r"^cache-dependency-path:\s*['\"]?requirements\.txt['\"]?\s*$", "requirements.txt cache key"),
            ("Install Python dependencies", r"^run:\s*python\s+-m\s+pip\s+install\s+-r\s+requirements\.txt\s*$", "requirements.txt installation"),
        ]
        for step_name, pattern, description in required_step_lines:
            if step_name in step_blocks and not step_has(step_name, pattern):
                errors.append(f"canonical drift workflow missing active `{description}` in `{step_name}`")

        step_lines = {
            name: step_blocks.get(name, [(0, "")])[0][0]
            for name in required_steps
            if name in step_blocks
        }
        ordered_steps = [
            "Check out repository",
            "Set up Python",
            "Install Python dependencies",
            "Check canonical drift",
            "Validate public archive",
        ]
        present_steps = [name for name in ordered_steps if name in step_lines]
        if present_steps != ordered_steps or any(
            step_lines[left] >= step_lines[right]
            for left, right in zip(ordered_steps, ordered_steps[1:])
            if left in step_lines and right in step_lines
        ):
            errors.append("canonical drift workflow Python bootstrap steps are missing or out of order")

        requirements = ROOT / "requirements.txt"
        if not requirements.exists():
            errors.append("requirements.txt missing; canonical drift workflow cannot install dependencies")
        else:
            has_lxml = False
            for raw_line in requirements.read_text(encoding="utf-8", errors="replace").splitlines():
                requirement = raw_line.split("#", 1)[0].strip()
                if re.match(r"^lxml(?:\[[^]]+\])?(?:\s*[<>=!~].*)?$", requirement, re.IGNORECASE):
                    has_lxml = True
                    break
            if not has_lxml:
                errors.append("requirements.txt must declare lxml for the canonical drift validator")
    if not report_path.exists():
        errors.append("canonical drift report missing")
    if not status_path.exists():
        errors.append("archive-status.json missing")
        return None
    try:
        status = load_json(status_path)
    except Exception as exc:
        errors.append(f"archive-status.json parse failed: {exc}")
        return None
    allowed = {"healthy", "degraded", "canonical_unavailable", "frozen_archive"}
    if status.get("state") not in allowed:
        errors.append(f"archive-status.json has invalid state `{status.get('state')}`")
    if status.get("state") == "frozen_archive" and status.get("frozen") is not True:
        errors.append("archive-status.json frozen_archive state must set frozen=true")
    if status.get("state") != "frozen_archive" and status.get("frozen") is True:
        warnings.append("archive-status.json frozen=true outside frozen_archive state")
    policy = status.get("policy", {})
    if policy.get("frozen_archive_noops_without_network") is not True:
        errors.append("archive-status.json must declare frozen_archive no-op policy")
    return status


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
        archived_keys = {
            key
            for post in posts
            if (key := canonical_url_key(post.get("canonical_url") or ""))
        }
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
            validate_post(post, errors, warnings, archived_keys)
        font_manifest = validate_pages_site(posts, errors, warnings, archived_keys)
        if font_manifest:
            font_files = font_manifest.get("files", [])
            font_bytes = sum(int(item.get("bytes") or 0) for item in font_files)
            report.extend([
                "## Typography",
                "",
                "- Body/content font: `Poppins`",
                "- Heading/title font: `Raleway`",
                f"- Self-hosted font files: {len(font_files)}",
                f"- Self-hosted font bytes: {font_bytes}",
                "",
            ])

    brand_assets = validate_brand_assets(errors)
    if brand_assets:
        report.extend([
            "## Repository Identity Assets",
            "",
            f"- README header: `{README_BRAND_ASSET_PATH}`",
            f"- Pages header and favicon source: `{PAGES_FAVICON_SOURCE_PATH}`",
            f"- Copyright: `{brand_assets['readme_logo'].get('copyright_notice')}`",
            "- Licence status: proprietary; excluded from MIT and CC-BY-NC-SA-4.0",
            "",
        ])

    sheet_manifest = validate_spreadsheet(errors, warnings)
    if sheet_manifest:
        report.extend(["## Spreadsheet", "", f"- Tabs: {len(sheet_manifest.get('tabs', []))}", f"- ODS: `{sheet_manifest.get('ods', {}).get('path')}`", ""])
        hierarchy = sheet_manifest.get("cidr_hierarchy", {})
        if hierarchy:
            report.extend([
                f"- CIDR hierarchy nodes: {hierarchy.get('node_count')}",
                f"- CIDR hierarchy max depth: {hierarchy.get('max_depth')}",
                "",
            ])

    drift_status = validate_drift_automation(errors, warnings)
    if drift_status:
        report.extend(["## Canonical Drift Automation", "", f"- State: `{drift_status.get('state')}`", f"- Frozen: `{str(drift_status.get('frozen')).lower()}`", ""])

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
