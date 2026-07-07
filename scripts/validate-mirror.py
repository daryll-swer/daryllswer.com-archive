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
        for key in ["json", "html", "dot"]:
            item = hierarchy.get(key, {})
            path_value = item.get("path")
            if not path_value or not (ROOT / path_value).exists():
                errors.append(f"spreadsheet CIDR hierarchy {key} artefact missing")
                continue
            if item.get("sha256") and sha256_file(ROOT / path_value) != item["sha256"]:
                errors.append(f"spreadsheet CIDR hierarchy {key} checksum mismatch")
        json_path = ROOT / hierarchy.get("json", {}).get("path", "")
        html_path = ROOT / hierarchy.get("html", {}).get("path", "")
        if json_path.exists():
            try:
                tree = load_json(json_path)
                if not tree.get("prefix") or not tree.get("children"):
                    errors.append("spreadsheet CIDR hierarchy JSON does not contain a prefix tree")
            except Exception as exc:
                errors.append(f"spreadsheet CIDR hierarchy JSON parse failed: {exc}")
        if html_path.exists():
            hierarchy_html = html_path.read_text(encoding="utf-8", errors="replace")
            if "prefix-tree" not in hierarchy_html or "AS141253 IPv6 CIDR Hierarchy" not in hierarchy_html:
                errors.append("spreadsheet CIDR hierarchy HTML missing expected tree UI")
    visual_options = manifest.get("visual_options", {})
    if visual_options:
        index_info = visual_options.get("index", {})
        index_path = ROOT / index_info.get("path", "")
        if not index_info.get("path") or not index_path.exists():
            errors.append("spreadsheet visual options index missing")
        elif index_info.get("sha256") and sha256_file(index_path) != index_info["sha256"]:
            errors.append("spreadsheet visual options index checksum mismatch")
        else:
            index_html = index_path.read_text(encoding="utf-8", errors="replace")
            for marker in ["Spatial block map", "Prefix length lanes", "Nibble ladder", "Branch cards", "Purpose swimlanes"]:
                if marker not in index_html:
                    errors.append(f"spreadsheet visual options index missing `{marker}`")
        options = visual_options.get("options", [])
        if visual_options.get("option_count") != len(options):
            errors.append("spreadsheet visual options option_count does not match options length")
        for option in options:
            option_path = ROOT / option.get("path", "")
            option_title = option.get("title") or option.get("id") or "visual option"
            if not option.get("path") or not option_path.exists():
                errors.append(f"spreadsheet visual option missing: {option_title}")
                continue
            if option.get("sha256") and sha256_file(option_path) != option["sha256"]:
                errors.append(f"spreadsheet visual option checksum mismatch: {option_title}")
            option_html = option_path.read_text(encoding="utf-8", errors="replace")
            if option_title not in option_html:
                errors.append(f"spreadsheet visual option page missing title: {option_title}")
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
        if "visual-options.html" not in sheet_html:
            errors.append("GitHub Pages AS141253 workbook page missing visual options link")
        if 'href="../../index.html"' in sheet_html:
            errors.append("GitHub Pages AS141253 workbook navigation should use ../../ instead of ../../index.html")
        hierarchy_page = sheet_page.parent / "cidr-hierarchy.html"
        if not hierarchy_page.exists():
            errors.append("GitHub Pages AS141253 CIDR hierarchy page missing")
        else:
            hierarchy_html = hierarchy_page.read_text(encoding="utf-8", errors="replace")
            if "prefix-tree" not in hierarchy_html:
                errors.append("GitHub Pages AS141253 CIDR hierarchy page missing prefix tree UI")
            if 'href="index.html"' in hierarchy_html:
                errors.append("GitHub Pages AS141253 CIDR hierarchy should link back to ./ instead of index.html")
        visual_index = sheet_page.parent / "visual-options.html"
        if not visual_index.exists():
            errors.append("GitHub Pages AS141253 visual options page missing")
        else:
            visual_html = visual_index.read_text(encoding="utf-8", errors="replace")
            for marker in ["Spatial block map", "Prefix length lanes", "Nibble ladder", "Branch cards", "Purpose swimlanes"]:
                if marker not in visual_html:
                    errors.append(f"GitHub Pages AS141253 visual options page missing `{marker}`")
            if "../../../assets/fonts/" in visual_html:
                errors.append("GitHub Pages AS141253 visual options page has unrewritten source font path")
        for option_name in ["spatial-blocks", "level-lanes", "nibble-ladder", "branch-cards", "purpose-swimlanes"]:
            option_page = sheet_page.parent / f"visual-option-{option_name}.html"
            if not option_page.exists():
                errors.append(f"GitHub Pages AS141253 visual option missing: {option_name}")
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
            if "../../sheets/as141253-ipv6-architecture-example/" not in html:
                errors.append(f"{post['slug']}: GitHub Pages article missing repo-hosted AS141253 sheet link")
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
        for marker in ["schedule:", "workflow_dispatch:", "concurrency:", "timeout-minutes:", "scripts/check-canonical-drift.py"]:
            if marker not in text:
                errors.append(f"canonical drift workflow missing `{marker}`")
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
