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
PAGES_HOME_TITLE = "daryllswer.com – Archive"
RIGHTS_REGISTRY_PATH = ROOT / "content" / "rights-registry.json"
RIGHTS_SCHEMA_PATH = ROOT / "schemas" / "rights-registry.schema.json"
ARCHIVE_STATUS_SCHEMA_PATH = ROOT / "schemas" / "archive-status.schema.json"
RIGHTS_NOTICE_PATH = ROOT / "LICENSES" / "SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt"
RIGHTS_REQUIRED_FIELDS = (
    "rights_holder",
    "rights_status",
    "default_ds_cc_applies",
    "original_article_url",
    "publisher",
    "scope",
    "media_rights",
    "external_fallback",
)
REQUIRED_ARCHIVED_RIGHTS_ID = "5324"
# WordPress REST is authoritative for archived posts. This exact public article
# has a documented source-sitemap exception; unknown sitemap absences remain
# warning candidates.
DOCUMENTED_SOURCE_SITEMAP_EXCEPTIONS = {
    "https://www.daryllswer.com/bgp-router-id-structuring-in-ipv6-native-networks/": (
        "documented source-sitemap exception"
    ),
}
PAGES_BASE_URL = "https://daryll-swer.github.io/daryllswer.com-archive/"
GOOGLE_SITE_VERIFICATION = "xEHOYZuv2ksSHn7MsBoCv9bkRPlwSFgyGoMtcn6lQIY"
LOCALISABLE_HOSTS = {"www.daryllswer.com", "daryllswer.com"}
TEXT_FRAGMENT_PREFIX = ":~:text="
README_BRAND_ASSET_PATH = "assets/readme/13_DS_Logo_Dark_Mode_SEO.png"
README_BRAND_MANIFEST_PATH = "assets/readme/manifest.json"
README_BRAND_PROVENANCE_PATH = "assets/readme/ASSET_PROVENANCE.md"
README_BRAND_NOTICE_PATH = "LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt"
README_BRAND_COPYRIGHT_NOTICE = "© 2026 Daryll Swer. All rights reserved."
PAGES_FAVICON_SOURCE_PATH = "assets/brand/01_DS_Favicon_Dark_Mode.png"
PAGES_FAVICON_MANIFEST_PATH = "assets/brand/manifest.json"
PAGES_FAVICON_PROVENANCE_PATH = "assets/brand/ASSET_PROVENANCE.md"
PAGES_FAVICON_DERIVATIVE_PATH = "assets/brand/derivatives/01_DS_Favicon_Dark_Mode-512.png"
PAGES_FAVICON_OUTPUT_PATH = "docs/assets/brand/01_DS_Favicon_Dark_Mode-512.png"
PAGES_FAVICON_SIZE = 512
README_BRAND_SEMANTIC_LINKS = (
    ("README header logo", README_BRAND_ASSET_PATH),
    ("GitHub Pages favicon source", PAGES_FAVICON_SOURCE_PATH),
    ("generated derivative", PAGES_FAVICON_DERIVATIVE_PATH),
    ("byte-for-byte GitHub Pages favicon", PAGES_FAVICON_OUTPUT_PATH),
)
README_BRAND_LEGACY_PATH_LINKS = tuple(
    f"[{path}]({path})"
    for path in [
        README_BRAND_ASSET_PATH,
        PAGES_FAVICON_SOURCE_PATH,
        PAGES_FAVICON_DERIVATIVE_PATH,
        PAGES_FAVICON_OUTPUT_PATH,
    ]
)
LEGACY_BRAND_PROVENANCE_PATHS = (
    "assets/readme/" + "README.md",
    "assets/brand/" + "README.md",
)
TEXT_REFERENCE_SUFFIXES = {".html", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}
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
FINAL_VISUAL_SCRIPT_MARKERS = (
    "data-final-tree-section",
    "data-final-tree-controls",
    "data-final-tree-expand",
    "data-final-tree-collapse",
    "details.final-tree-node:not(.leaf), details.reserved-group",
    "detail.open = true",
    "detail.open = false",
)
FINAL_VISUAL_CSS_MARKERS = (
    ".tree-node > summary::before",
    ".reserved-group > summary::before",
    ".tree-node[open] > summary::before",
    ".reserved-group[open] > summary::before",
    ".reserved-singleton-grid",
)
FINAL_VISUAL_FORBIDDEN_SCRIPT_MARKERS = (
    "data-graph-data",
    "initGraphSection",
    "JSON.parse",
    "data-dendrogram-section",
    "interactive_js",
)
AS141253_HIERARCHY_PATH = ROOT / "data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json"


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


def archive_route_keys(archive: dict) -> set[str]:
    return {key for item in archive.get("posts", []) or [] if (key := canonical_url_key(item.get("canonical_url") or ""))}


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


def validate_rights_record_shape(post_id: str, record: object, errors: list[str]) -> bool:
    path = f"content/rights-registry.json[{post_id!r}]"
    if not isinstance(record, dict):
        errors.append(f"{path}: expected object")
        return False
    missing = [key for key in RIGHTS_REQUIRED_FIELDS if key not in record]
    if missing:
        errors.append(f"{path}: missing required key(s): {', '.join(missing)}")
    extra = sorted(set(record) - set(RIGHTS_REQUIRED_FIELDS))
    if extra:
        errors.append(f"{path}: unsupported key(s): {', '.join(extra)}")
    valid = not missing and not extra
    for key in ["rights_holder", "rights_status", "original_article_url", "publisher", "scope", "media_rights"]:
        if key in record and (not isinstance(record[key], str) or not record[key].strip()):
            errors.append(f"{path}: `{key}` must be a non-empty string")
            valid = False
    if "default_ds_cc_applies" in record and not isinstance(record["default_ds_cc_applies"], bool):
        errors.append(f"{path}: `default_ds_cc_applies` must be boolean")
        valid = False
    if "external_fallback" in record and not isinstance(record["external_fallback"], bool):
        errors.append(f"{path}: `external_fallback` must be boolean")
        valid = False
    if isinstance(record.get("original_article_url"), str):
        parsed = urllib.parse.urlsplit(record["original_article_url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{path}: `original_article_url` must be an absolute HTTP(S) URL")
            valid = False
    if record.get("rights_status") == "proprietary/all-rights-reserved" and record.get("default_ds_cc_applies") is not False:
        errors.append(f"{path}: proprietary content must set `default_ds_cc_applies` to false")
        valid = False
    return valid


def validate_rights_registry(archive: dict, errors: list[str]) -> dict[str, dict] | None:
    if not RIGHTS_SCHEMA_PATH.exists():
        errors.append("rights registry schema missing")
    else:
        try:
            schema = load_json(RIGHTS_SCHEMA_PATH)
            schema_record = (schema.get("$defs") or {}).get("rights")
            if not isinstance(schema_record, dict) or set(schema_record.get("required", [])) != set(RIGHTS_REQUIRED_FIELDS):
                errors.append("rights registry schema does not define the approved rights record")
        except Exception as exc:
            errors.append(f"rights registry schema parse failed: {exc}")
    if not RIGHTS_REGISTRY_PATH.exists():
        errors.append("rights registry missing at content/rights-registry.json")
        return None
    try:
        registry = load_json(RIGHTS_REGISTRY_PATH)
    except Exception as exc:
        errors.append(f"rights registry parse failed: {exc}")
        return None
    if not isinstance(registry, dict):
        errors.append("rights registry must be an object")
        return None

    valid_records: dict[str, dict] = {}
    posts = archive.get("posts", []) or []
    archived_ids = {post.get("id") for post in posts}
    if 5324 in archived_ids and REQUIRED_ARCHIVED_RIGHTS_ID not in registry:
        errors.append(
            "content/rights-registry.json must contain an entry for archived WordPress post ID 5324"
        )
    for post_id, record in registry.items():
        if not isinstance(post_id, str) or not re.fullmatch(r"[1-9][0-9]*", post_id):
            errors.append(f"content/rights-registry.json: invalid immutable WordPress ID key `{post_id}`")
            continue
        if not validate_rights_record_shape(post_id, record, errors):
            continue
        valid_records[post_id] = record
        matches = [post for post in posts if post.get("id") == int(post_id)]
        if len(matches) != 1:
            errors.append(f"content/rights-registry.json[{post_id!r}]: must resolve to exactly one manifest post; found {len(matches)}")
            continue
        bundle = ROOT / matches[0].get("bundle_path", "")
        metadata_path = bundle / "metadata.json"
        if not metadata_path.exists():
            errors.append(f"{matches[0].get('slug', post_id)}: rights metadata is missing at {rel(metadata_path)}")
            continue
        try:
            metadata = load_json(metadata_path)
        except Exception as exc:
            errors.append(f"{matches[0].get('slug', post_id)}: rights metadata parse failed: {exc}")
            continue
        metadata_rights = metadata.get("rights")
        legacy_record = dict(record)
        legacy_record.pop("external_fallback", None)
        if metadata_rights != record and metadata_rights != legacy_record:
            errors.append(f"{matches[0].get('slug', post_id)}: generated metadata.rights does not match its registry entry")

        if record.get("rights_status") != "proprietary/all-rights-reserved":
            continue
        evidence_paths = [
            bundle / "index.md",
            bundle / "source" / "rendered-article.html",
            bundle / "source" / "canonical-page.html",
            bundle / "source" / "wordpress-post.json",
        ]
        evidence = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in evidence_paths
            if path.exists()
        )
        normalised = " ".join(evidence.split()).lower()
        if record["original_article_url"] not in evidence:
            errors.append(f"{matches[0].get('slug', post_id)}: proprietary rights evidence is missing the original publication link")
        if not all(marker in normalised for marker in ["swer networks", "copyright", "all rights reserved"]):
            errors.append(f"{matches[0].get('slug', post_id)}: proprietary rights evidence is missing Swer Networks copyright/all-rights-reserved wording")
        if not re.search(r"not licensed under .*cc by-nc-sa 4\.0 licen[cs]e", normalised):
            errors.append(f"{matches[0].get('slug', post_id)}: proprietary rights evidence is missing explicit CC exclusion")

    for post in posts:
        metadata_path = ROOT / post.get("bundle_path", "") / "metadata.json"
        if not metadata_path.exists():
            continue
        try:
            metadata = load_json(metadata_path)
        except Exception:
            continue
        if "rights" not in metadata:
            continue
        post_id = str(post.get("id"))
        record = valid_records.get(post_id)
        if record is None:
            errors.append(
                f"{post.get('slug', post_id)}: generated metadata.rights has no matching registry entry"
            )
        elif metadata.get("rights") != record and metadata.get("rights") != {key: value for key, value in record.items() if key != "external_fallback"}:
            errors.append(
                f"{post.get('slug', post_id)}: generated metadata.rights does not exactly match its registry entry"
            )

    if not RIGHTS_NOTICE_PATH.exists():
        errors.append(f"proprietary rights notice missing: {rel(RIGHTS_NOTICE_PATH)}")
    else:
        notice = RIGHTS_NOTICE_PATH.read_text(encoding="utf-8", errors="replace").lower()
        for marker in ["swer networks", "all rights reserved", "not licensed under", "creative commons", "content/rights-registry.json"]:
            if marker not in notice:
                errors.append(f"{rel(RIGHTS_NOTICE_PATH)}: missing `{marker}`")
    return valid_records


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


def validate_collapsed_hierarchy_details(visual_model_html: str, path: str, errors: list[str]) -> None:
    try:
        document = lxml.html.fromstring(visual_model_html)
    except Exception as exc:
        errors.append(f"{path}: could not inspect hierarchy details: {exc}")
        return
    hierarchy_details = document.xpath(
        "//details["
        "contains(concat(' ', normalize-space(@class), ' '), ' final-tree-node ') or "
        "contains(concat(' ', normalize-space(@class), ' '), ' reserved-group ')"
        "]"
    )
    for detail in hierarchy_details:
        if "open" in detail.attrib:
            identifier = detail.get("id") or detail.get("class") or "unknown"
            errors.append(f"{path}: hierarchy detail `{identifier}` must not carry an open attribute")


def expected_reserved_singletons(errors: list[str]) -> dict[str, str] | None:
    """Return static reserved leaves mapped to their immediate parent prefix."""
    try:
        tree = load_json(AS141253_HIERARCHY_PATH)
    except Exception as exc:
        errors.append(f"could not load AS141253 hierarchy for reserved-leaf validation: {exc}")
        return None

    singletons: dict[str, str] = {}

    def is_reserved(node: dict) -> bool:
        text = " ".join(str(node.get(key) or "") for key in ["label", "notes", "source_sheet"]).lower()
        return "reserved" in text

    def visit(node: dict) -> None:
        groups: dict[tuple[int, str, str], list[dict]] = {}
        for child in node.get("children", []):
            if is_reserved(child):
                key = (
                    int(child.get("prefix_length") or 0),
                    str(child.get("label") or ""),
                    str(child.get("notes") or ""),
                )
                groups.setdefault(key, []).append(child)
            visit(child)
        for group in groups.values():
            if len(group) == 1 and group[0].get("prefix"):
                singletons[str(group[0]["prefix"])] = str(node.get("prefix") or "")

    if not isinstance(tree, dict):
        errors.append("AS141253 hierarchy must be a JSON object for reserved-leaf validation")
        return None
    visit(tree)
    return singletons


def validate_reserved_group_shapes(document, path: str, errors: list[str]) -> None:
    reserved_groups = document.xpath(
        "//details["
        "contains(concat(' ', normalize-space(@class), ' '), ' reserved-group ')"
        "]"
    )
    for group in reserved_groups:
        identifier = group.get("id") or group.get("class") or "reserved-group"
        if group.get("data-reserved-group") is None or not any(
            token == "reserved-group" for token in (group.get("class") or "").split()
        ):
            errors.append(f"{path}: {identifier} must expose both reserved-group class and data attribute")
        if "open" in group.attrib:
            errors.append(f"{path}: {identifier} must not carry an open attribute")
        summaries = group.xpath("./summary")
        reserved_items = group.xpath(
            "./div["
            "contains(concat(' ', normalize-space(@class), ' '), ' reserved-items ')"
            "]"
        )
        if len(summaries) != 1 or len(reserved_items) != 1:
            errors.append(
                f"{path}: {identifier} must contain exactly one direct summary and reserved-items container"
            )
        exact_cards = group.xpath(
            "./div["
            "contains(concat(' ', normalize-space(@class), ' '), ' reserved-items ')"
            "]/div["
            "contains(concat(' ', normalize-space(@class), ' '), ' child-item ')"
            "]"
        )
        if len(exact_cards) < 2:
            errors.append(
                f"{path}: {identifier} must contain at least 2 exact reserved prefix cards; found {len(exact_cards)}"
            )
        if len(reserved_items) == 1 and len(reserved_items[0].getchildren()) != len(exact_cards):
            errors.append(f"{path}: {identifier} reserved-items must contain only direct exact prefix cards")
        for card in exact_cards:
            if card.get("data-reserved-leaf") is not None or "reserved-leaf" in (card.get("class") or "").split():
                errors.append(f"{path}: {identifier} multi-prefix group must not contain a static reserved leaf")
            chips = card.xpath(
                ".//*["
                "contains(concat(' ', normalize-space(@class), ' '), ' prefix-chip ')"
                "]"
            )
            prefixes = card.xpath(".//code")
            if len(chips) != 1 or len(prefixes) != 1:
                errors.append(
                    f"{path}: reserved-group exact prefix card must contain exactly one prefix chip and code; found {len(chips)} chips and {len(prefixes)} codes"
                )

    singleton_grids = document.xpath(
        "//*[@data-reserved-singleton-grid or "
        "contains(concat(' ', normalize-space(@class), ' '), ' reserved-singleton-grid ')]"
    )
    expected_singletons = expected_reserved_singletons(errors)
    for grid in singleton_grids:
        identifier = grid.get("id") or grid.get("class") or "reserved-singleton-grid"
        if grid.get("data-reserved-singleton-grid") is None or not any(
            token == "reserved-singleton-grid" for token in (grid.get("class") or "").split()
        ):
            errors.append(f"{path}: {identifier} must expose both singleton-grid class and data attribute")
        if grid.xpath(".//details | .//summary"):
            errors.append(f"{path}: {identifier} must not contain a disclosure control")
        direct_cards = grid.xpath(
            "./div["
            "contains(concat(' ', normalize-space(@class), ' '), ' child-item ')"
            "]"
        )
        if not direct_cards:
            errors.append(f"{path}: {identifier} must contain at least one direct reserved leaf card")
        if len(grid.getchildren()) != len(direct_cards):
            errors.append(f"{path}: {identifier} must contain only direct reserved leaf cards")
        for card in direct_cards:
            if card.get("data-reserved-leaf") is None or "reserved-leaf" not in (card.get("class") or "").split():
                errors.append(f"{path}: {identifier} direct cards must expose reserved-leaf class and data attribute")
        if expected_singletons is not None:
            prefixes = {"".join(code.itertext()).strip() for card in direct_cards for code in card.xpath(".//code")}
            parent_prefixes = {expected_singletons.get(prefix) for prefix in prefixes}
            if len(parent_prefixes) != 1 or None in parent_prefixes:
                errors.append(f"{path}: {identifier} must contain singleton leaves from exactly one hierarchy parent")
            else:
                parent_prefix = parent_prefixes.pop()
                expected_tree_id = f"prefix-{re.sub(r'[^a-z0-9]+', '-', parent_prefix.lower()).strip('-') or 'root'}-tree"
                if grid.get("data-reserved-singleton-parent") != parent_prefix:
                    errors.append(
                        f"{path}: {identifier} parent data must be {parent_prefix!r}"
                    )
                parent = grid.getparent()
                if parent is None or parent.tag != "details" or parent.get("id") != expected_tree_id:
                    errors.append(
                        f"{path}: {identifier} must be a direct child of hierarchy parent {expected_tree_id!r}"
                    )

    reserved_leaves = document.xpath(
        "//*[@data-reserved-leaf or "
        "contains(concat(' ', normalize-space(@class), ' '), ' reserved-leaf ')]"
    )
    rendered_singletons: set[str] = set()
    for leaf in reserved_leaves:
        identifier = leaf.get("id") or leaf.get("class") or "reserved-leaf"
        if leaf.get("data-reserved-leaf") is None or not any(
            token == "reserved-leaf" for token in (leaf.get("class") or "").split()
        ):
            errors.append(f"{path}: {identifier} must expose both reserved-leaf class and data attribute")
        if leaf.tag == "details" or leaf.xpath(".//details | .//summary"):
            errors.append(f"{path}: {identifier} must not contain a disclosure control")
        if leaf.xpath(
            "ancestor::details[contains(concat(' ', normalize-space(@class), ' '), ' reserved-group ')]"
        ):
            errors.append(f"{path}: {identifier} must not be nested inside a reserved-group disclosure")
        singleton_ancestors = leaf.xpath(
            "ancestor::*["
            "contains(concat(' ', normalize-space(@class), ' '), ' reserved-singleton-grid ') or "
            "@data-reserved-singleton-grid"
            "]"
        )
        if len(singleton_ancestors) != 1:
            errors.append(f"{path}: {identifier} must belong to exactly one reserved-singleton-grid")
        elif leaf.getparent() is not singleton_ancestors[0]:
            errors.append(f"{path}: {identifier} must be a direct child of its reserved-singleton-grid")
        chips = leaf.xpath(
            ".//*["
            "contains(concat(' ', normalize-space(@class), ' '), ' prefix-chip ')"
            "]"
        )
        prefixes = leaf.xpath(".//code")
        if len(chips) != 1 or len(prefixes) != 1:
            errors.append(
                f"{path}: {identifier} must contain exactly one visible prefix chip and code; found {len(chips)} chips and {len(prefixes)} codes"
            )
            continue
        rendered_singletons.add("".join(prefixes[0].itertext()).strip())

    expected_prefixes = set(expected_singletons or {})
    if expected_singletons is not None and rendered_singletons != expected_prefixes:
        errors.append(
            f"{path}: reserved static leaves do not match the hierarchy; expected {sorted(expected_prefixes)}, found {sorted(rendered_singletons)}"
        )
    if expected_singletons is not None:
        grid_prefixes = {
            "".join(code.itertext()).strip()
            for grid in singleton_grids
            for code in grid.xpath("./div[contains(concat(' ', normalize-space(@class), ' '), ' reserved-leaf ')]//code")
        }
        if grid_prefixes != expected_prefixes:
            errors.append(
                f"{path}: reserved singleton grids do not match the hierarchy; expected {sorted(expected_prefixes)}, found {sorted(grid_prefixes)}"
            )


def validate_final_visual_html(visual_model_html: str, path: str, errors: list[str]) -> None:
    """Validate the native disclosure model and its one local enhancement script."""
    try:
        document = lxml.html.fromstring(visual_model_html)
    except Exception as exc:
        errors.append(f"{path}: could not inspect final visual: {exc}")
        return

    controls = document.xpath("//*[@data-final-tree-controls]")
    if len(controls) != 1:
        errors.append(f"{path}: final visual must contain exactly one progressive-enhancement control group")
    else:
        control_group = controls[0]
        if "hidden" not in control_group.attrib:
            errors.append(f"{path}: final visual controls must be hidden before enhancement")
        if control_group.get("role") != "group" or control_group.get("aria-label") != "Full hierarchy controls":
            errors.append(f"{path}: final visual controls must expose an accessible group label")
    for attribute, label in [
        ("data-final-tree-expand", "Expand all"),
        ("data-final-tree-collapse", "Collapse all"),
    ]:
        buttons = document.xpath(f"//*[@{attribute}]")
        if len(buttons) != 1:
            errors.append(f"{path}: final visual must contain exactly one {label!r} control")
            continue
        button = buttons[0]
        if button.tag != "button" or button.get("type") != "button":
            errors.append(f"{path}: {label!r} control must be an explicit button")
        if button.get("aria-controls") != "full-hierarchy-tree":
            errors.append(f"{path}: {label!r} control must identify the final hierarchy")
        if " ".join(button.itertext()).strip() != label:
            errors.append(f"{path}: {label!r} control has unexpected accessible text")

    scripts = document.xpath("//script")
    if len(scripts) != 1:
        errors.append(f"{path}: final visual must contain exactly one expected inline script")
    else:
        script = scripts[0]
        if script.get("src"):
            errors.append(f"{path}: final visual must not load an external script")
        if script.get("data-final-tree-enhancement") is None:
            errors.append(f"{path}: final visual script is missing its expected enhancement marker")
        script_text = script.text or ""
        for marker in FINAL_VISUAL_SCRIPT_MARKERS:
            if marker not in script_text:
                errors.append(f"{path}: final visual script is missing `{marker}`")
        for marker in FINAL_VISUAL_FORBIDDEN_SCRIPT_MARKERS:
            if marker in script_text:
                errors.append(f"{path}: final visual script contains unrelated legacy marker `{marker}`")

    for marker in FINAL_VISUAL_CSS_MARKERS:
        if marker not in visual_model_html:
            errors.append(f"{path}: final visual is missing scoped disclosure marker rule `{marker}`")
    if ".tree-node summary" in visual_model_html:
        errors.append(f"{path}: final visual contains an unscoped tree summary selector")
    validate_collapsed_hierarchy_details(visual_model_html, path, errors)
    validate_reserved_group_shapes(document, path, errors)


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
    canonical_fingerprint = (metadata.get("source") or {}).get("canonical_rendered_content_sha256")
    if not isinstance(canonical_fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", canonical_fingerprint):
        errors.append(f"{post_item['slug']}: missing or malformed canonical rendered-content checksum")
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


def classify_sitemap_difference(
    sitemap: set[str], archive: set[str]
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """Separate true sitemap drift from documented source-sitemap exceptions."""
    missing_from_archive = sorted(sitemap - archive)
    missing_from_sitemap = archive - sitemap
    intentional = sorted(
        (url, DOCUMENTED_SOURCE_SITEMAP_EXCEPTIONS[url])
        for url in missing_from_sitemap
        if url in DOCUMENTED_SOURCE_SITEMAP_EXCEPTIONS
    )
    unexpected_missing_from_sitemap = sorted(
        url for url in missing_from_sitemap if url not in DOCUMENTED_SOURCE_SITEMAP_EXCEPTIONS
    )
    return missing_from_archive, unexpected_missing_from_sitemap, intentional


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
        validate_final_visual_html(visual_model_html, rel(visual_model_path), errors)

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


def validate_pages_open_graph_url(page: Path, expected: str, errors: list[str]) -> None:
    try:
        document = parse_html_file(page)
    except Exception as exc:
        errors.append(f"{rel(page)}: generated HTML parse failed while checking Open Graph URL: {exc}")
        return
    values = document.xpath("//meta[@property='og:url']/@content")
    if values != [expected]:
        errors.append(f"{rel(page)}: Open Graph URL must be exactly {expected!r}; found {values!r}")


def validate_pages_home_h1(page: Path, expected: str, errors: list[str]) -> None:
    try:
        document = parse_html_file(page)
    except Exception as exc:
        errors.append(f"{rel(page)}: generated HTML parse failed while checking homepage H1: {exc}")
        return
    headings = document.xpath("//main[contains(concat(' ', normalize-space(@class), ' '), ' home ')]//h1")
    values = [heading.text_content() for heading in headings]
    if values != [expected]:
        errors.append(f"{rel(page)}: homepage H1 must be exactly {expected!r}; found {values!r}")


def validate_pages_canonical_url(page: Path, expected: str, errors: list[str]) -> None:
    try:
        document = parse_html_file(page)
    except Exception as exc:
        errors.append(f"{rel(page)}: generated HTML parse failed while checking canonical URL: {exc}")
        return
    values = document.xpath("//link[@rel='canonical']/@href")
    if values != [expected]:
        errors.append(f"{rel(page)}: canonical URL must be exactly {expected!r}; found {values!r}")


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
    """Keep proprietary identity assets outside archive licences."""
    asset_path = ROOT / README_BRAND_ASSET_PATH
    manifest_path = ROOT / README_BRAND_MANIFEST_PATH
    provenance_path = ROOT / README_BRAND_PROVENANCE_PATH
    notice_path = ROOT / README_BRAND_NOTICE_PATH
    readme_path = ROOT / "README.md"
    licensing_path = ROOT / "LICENSING.md"
    favicon_source_path = ROOT / PAGES_FAVICON_SOURCE_PATH
    favicon_manifest_path = ROOT / PAGES_FAVICON_MANIFEST_PATH
    favicon_provenance_path = ROOT / PAGES_FAVICON_PROVENANCE_PATH
    favicon_derivative_path = ROOT / PAGES_FAVICON_DERIVATIVE_PATH
    favicon_output_path = ROOT / PAGES_FAVICON_OUTPUT_PATH

    for path in [
        asset_path,
        manifest_path,
        provenance_path,
        notice_path,
        readme_path,
        licensing_path,
        favicon_source_path,
        favicon_manifest_path,
        favicon_provenance_path,
        favicon_derivative_path,
        favicon_output_path,
    ]:
        if not path.exists():
            errors.append(f"proprietary brand asset requirement missing: {rel(path)}")
    legacy_reference_bytes = [path.encode("utf-8") for path in LEGACY_BRAND_PROVENANCE_PATHS]
    for candidate in ROOT.rglob("*"):
        if (
            not candidate.is_file()
            or ".git" in candidate.parts
            or candidate.is_symlink()
            or candidate.suffix.lower() not in TEXT_REFERENCE_SUFFIXES
        ):
            continue
        try:
            candidate_bytes = candidate.read_bytes()
        except OSError as exc:
            errors.append(f"could not inspect repository file for legacy provenance path: {rel(candidate)} ({exc})")
            continue
        for legacy_path, legacy_bytes in zip(LEGACY_BRAND_PROVENANCE_PATHS, legacy_reference_bytes):
            if legacy_bytes in candidate_bytes:
                errors.append(f"legacy brand provenance reference `{legacy_path}` found in {rel(candidate)}")
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

    if provenance_path.exists():
        provenance = provenance_path.read_text(encoding="utf-8", errors="replace").lower()
        for marker in [
            "provenance",
            "byte-for-byte",
            "not a licence",
            "controlling legal notice",
            README_BRAND_NOTICE_PATH.lower(),
        ]:
            if marker not in provenance:
                errors.append(f"README brand asset provenance record is missing `{marker}`")

    if readme_path.exists():
        readme = readme_path.read_text(encoding="utf-8", errors="replace")
        readme_normalized = " ".join(readme.split()).lower()
        if f'src="{README_BRAND_ASSET_PATH}"' not in readme:
            errors.append("README does not render the proprietary header logo")
        if 'href="#copyright-and-licences"' not in readme:
            errors.append("README logo must link to the local copyright-and-licences section")
        if "## Copyright and Licences" not in readme:
            errors.append("README is missing the copyright-and-licences destination section")
        if not re.search(r"© 2026 Daryll Swer\. All\s+rights reserved\.", readme):
            errors.append("README does not state the proprietary logo copyright notice")
        for label, path in README_BRAND_SEMANTIC_LINKS:
            marker = f"[{label}]({path})"
            if marker not in readme:
                errors.append(f"README is missing semantic proprietary asset link `{marker}`")
        for marker in README_BRAND_LEGACY_PATH_LINKS:
            if marker in readme:
                errors.append(f"README retains legacy raw-path proprietary asset link `{marker}`")
        for marker in [
            "ASSET_PROVENANCE.md",
            "provenance and byte-preservation evidence only",
            "not a licence",
            "controlling legal notice",
            README_BRAND_NOTICE_PATH,
            "MIT",
            "CC-BY-NC-SA-4.0",
            "applicable law",
            "GitHub's limited public-repository service operation",
        ]:
            if marker.lower() not in readme_normalized:
                errors.append(f"README is missing brand asset licensing/provenance marker `{marker}`")
    if licensing_path.exists():
        licensing = licensing_path.read_text(encoding="utf-8", errors="replace")
        for marker in [
            README_BRAND_ASSET_PATH,
            README_BRAND_PROVENANCE_PATH,
            PAGES_FAVICON_PROVENANCE_PATH,
            README_BRAND_NOTICE_PATH,
            "MIT",
            "CC-BY-NC-SA-4.0",
        ]:
            if marker not in licensing:
                errors.append(f"LICENSING.md is missing README brand asset marker `{marker}`")
    if notice_path.exists():
        notice = notice_path.read_text(encoding="utf-8", errors="replace")
        for marker in [README_BRAND_COPYRIGHT_NOTICE, README_BRAND_ASSET_PATH, "no permission is granted"]:
            if marker not in notice:
                errors.append(f"README proprietary asset notice is missing `{marker}`")
    if (ROOT / "docs" / README_BRAND_ASSET_PATH).exists():
        errors.append("README proprietary logo must not be copied into GitHub Pages output")

    if (
        not favicon_source_path.exists()
        or not favicon_manifest_path.exists()
        or not favicon_derivative_path.exists()
        or not favicon_output_path.exists()
    ):
        return None
    if favicon_provenance_path.exists():
        favicon_provenance = favicon_provenance_path.read_text(encoding="utf-8", errors="replace").lower()
        for marker in ["provenance", "not a licence", "controlling notice", README_BRAND_NOTICE_PATH.lower()]:
            if marker not in favicon_provenance:
                errors.append(f"Pages favicon provenance record is missing `{marker}`")
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
    if derivative.get("prepared_path") != PAGES_FAVICON_DERIVATIVE_PATH:
        errors.append("Pages favicon manifest prepared derivative path is incorrect")
    if derivative.get("format") != "image/png":
        errors.append("Pages favicon manifest derivative format is incorrect")
    if (derivative.get("width"), derivative.get("height")) != (PAGES_FAVICON_SIZE, PAGES_FAVICON_SIZE):
        errors.append("Pages favicon manifest derivative dimensions are incorrect")
    expected_hash = favicon.get("sha256")
    expected_derivative_source_hash = derivative.get("source_sha256")
    expected_derivative_hash = derivative.get("sha256")
    source_checksum = sha256_file(favicon_source_path)
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append("Pages favicon manifest SHA-256 is missing or invalid")
    elif source_checksum != expected_hash:
        errors.append("Pages favicon source checksum mismatch")
    if not isinstance(expected_derivative_source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_derivative_source_hash):
        errors.append("Pages favicon manifest derivative source SHA-256 is missing or invalid")
    elif expected_derivative_source_hash != source_checksum:
        errors.append("Pages favicon manifest derivative source checksum relationship is incorrect")
    if not isinstance(expected_derivative_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_derivative_hash):
        errors.append("Pages favicon manifest derivative SHA-256 is missing or invalid")
    else:
        if sha256_file(favicon_derivative_path) != expected_derivative_hash:
            errors.append("Pages favicon prepared derivative checksum mismatch")
        if sha256_file(favicon_output_path) != expected_derivative_hash:
            errors.append("Pages favicon generated output checksum mismatch")

    previous_pixel_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 150_000_000
    try:
        with Image.open(favicon_source_path) as image:
            if image.format != "PNG" or image.size != (favicon.get("width"), favicon.get("height")):
                errors.append("Pages favicon source format or dimensions do not match its manifest")
        with Image.open(favicon_derivative_path) as image:
            if image.format != "PNG" or image.size != (PAGES_FAVICON_SIZE, PAGES_FAVICON_SIZE):
                errors.append("Prepared Pages favicon derivative must be a 512 px PNG")
        with Image.open(favicon_output_path) as image:
            if image.format != "PNG" or image.size != (PAGES_FAVICON_SIZE, PAGES_FAVICON_SIZE):
                errors.append("Pages favicon derivative must be a 512 px PNG")
    except Exception as exc:
        errors.append(f"Pages favicon image validation failed: {exc}")
    finally:
        Image.MAX_IMAGE_PIXELS = previous_pixel_limit

    if favicon_derivative_path.read_bytes() != favicon_output_path.read_bytes():
        errors.append("Pages favicon prepared derivative and generated output are not byte-for-byte identical")

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


def validate_pages_site(
    posts: list[dict],
    errors: list[str],
    warnings: list[str],
    archived_keys: set[str],
    registry: dict[str, dict] | None = None,
    status: dict | None = None,
) -> dict | None:
    registry = registry or {}
    status = status or {"seo_state": "source_primary"}
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
        reader_robots = None if status_seo_state(status) == "archive_discovery" else "noindex,follow"
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
            visual_route = PAGES_BASE_URL + "sheets/as141253-ipv6-architecture-example/visual.html"
            validate_pages_canonical_url(visual_model, visual_route, errors)
            validate_pages_open_graph_url(visual_model, visual_route, errors)
            validate_pages_robots(visual_model, reader_robots, errors)
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
            validate_final_visual_html(visual_model_html, rel(visual_model), errors)

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

        sheet_route = PAGES_BASE_URL + "sheets/as141253-ipv6-architecture-example/"
        validate_pages_canonical_url(sheet_page, sheet_route, errors)
        validate_pages_open_graph_url(sheet_page, sheet_route, errors)
        validate_pages_robots(sheet_page, reader_robots, errors)

        for page in (ROOT / "docs").rglob("*.html"):
            page_html = page.read_text(encoding="utf-8", errors="replace")
            for legacy_route in legacy_pages:
                if legacy_route in page_html:
                    errors.append(f"GitHub Pages page still links a legacy AS141253 visual route: {rel(page)}")
                    break
    index_html = site_index.read_text(encoding="utf-8", errors="replace")
    if "posts/" not in index_html:
        errors.append("GitHub Pages index does not link to generated post pages")
    if f"<title>{PAGES_HOME_TITLE}</title>" not in index_html:
        errors.append("GitHub Pages index title does not match the archive homepage title")
    if f'<meta property="og:title" content="{PAGES_HOME_TITLE}">' not in index_html:
        errors.append("GitHub Pages index Open Graph title does not match the archive homepage title")
    validate_pages_home_h1(site_index, PAGES_HOME_TITLE, errors)
    if 'href="index.html"' in index_html:
        errors.append("GitHub Pages index navigation should use the clean ./ root URL, not index.html")
    validate_pages_canonical_url(site_index, PAGES_BASE_URL, errors)
    validate_pages_open_graph_url(site_index, PAGES_BASE_URL, errors)
    validate_pages_robots(site_index, None, errors)
    validate_google_verification(site_index, errors)
    for post in posts:
        page = ROOT / "docs" / "posts" / post["slug"] / "index.html"
        if not page.exists():
            errors.append(f"{post['slug']}: GitHub Pages article missing")
            continue
        html = page.read_text(encoding="utf-8", errors="replace")
        validate_pages_canonical_url(page, PAGES_BASE_URL + f"posts/{post['slug']}/", errors)
        validate_pages_open_graph_url(page, PAGES_BASE_URL + f"posts/{post['slug']}/", errors)
        validate_pages_robots(
            page,
            None if status_post_is_eligible(post, registry, status) else "noindex,follow",
            errors,
        )
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
    for page in sorted((ROOT / "docs").rglob("*.html")):
        try:
            document = parse_html_file(page)
            values = document.xpath("//meta[@property='og:url']/@content") + document.xpath("//link[@rel='canonical']/@href")
            for value in values:
                if not value.startswith(PAGES_BASE_URL):
                    errors.append(f"{rel(page)}: canonical/Open Graph URL must remain archive-local; found {value}")
        except Exception as exc:
            errors.append(f"{rel(page)}: generated HTML parse failed while checking archive-local metadata URLs: {exc}")
    snapshot_root = ROOT / "docs" / "sheets" / "as141253-ipv6-architecture-example" / "html"
    for page in sorted(snapshot_root.glob("*.html")):
        validate_pages_robots(page, "noindex,nofollow", errors)
        snapshot_html = page.read_text(encoding="utf-8", errors="replace")
        if re.search(r"<meta\b(?=[^>]*\bhttp-equiv\s*=\s*[\"']?refresh\b)[^>]*>", snapshot_html, re.I):
            errors.append(f"{rel(page)}: raw snapshot must not retain an executable refresh redirect")
        try:
            document = parse_html_file(page)
            csp_values = document.xpath(
                "//meta[translate(@http-equiv, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                "'abcdefghijklmnopqrstuvwxyz')='content-security-policy']/@content"
            )
        except Exception as exc:
            errors.append(f"{rel(page)}: raw snapshot CSP validation failed: {exc}")
            continue
        if len(csp_values) != 1 or "script-src 'none'" not in csp_values[0] or "default-src 'none'" not in csp_values[0]:
            errors.append(f"{rel(page)}: raw snapshot must have one restrictive script-blocking CSP")
    return font_manifest


def status_seo_state(status: dict) -> str:
    value = status.get("seo_state")
    if value in {"source_primary", "archive_discovery"}:
        return value
    return "archive_discovery" if status.get("state") == "frozen_archive" else "source_primary"


def status_post_is_eligible(post: dict, registry: dict[str, dict], status: dict) -> bool:
    if status_seo_state(status) != "archive_discovery":
        return False
    source = (status.get("external_sources") or {}).get(str(post.get("id")))
    if source is not None:
        return source.get("state") == "frozen_source" and source.get("promotion_blocked") is not True
    return (registry.get(str(post.get("id"))) or {}).get("external_fallback") is not True


def meta_values(page: Path, *, name: str | None = None, property_name: str | None = None) -> list[str]:
    document = parse_html_file(page)
    if name:
        return document.xpath(f"//meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='{name.lower()}']/@content")
    return document.xpath(f"//meta[@property='{property_name}']/@content")


def validate_pages_robots(page: Path, expected: str | None, errors: list[str]) -> None:
    try:
        values = meta_values(page, name="robots")
    except Exception as exc:
        errors.append(f"{rel(page)}: generated HTML parse failed while checking robots metadata: {exc}")
        return
    expected_values = [] if expected is None else [expected]
    if values != expected_values:
        errors.append(f"{rel(page)}: robots metadata must be exactly {expected_values!r}; found {values!r}")


def validate_google_verification(site_index: Path, errors: list[str]) -> None:
    try:
        values = meta_values(site_index, name="google-site-verification")
    except Exception as exc:
        errors.append(f"{rel(site_index)}: Google verification metadata parse failed: {exc}")
        return
    if values != [GOOGLE_SITE_VERIFICATION]:
        errors.append(f"{rel(site_index)}: Google site verification tag is missing or not exact")
    for page in sorted((ROOT / "docs").rglob("*.html")):
        if page == site_index:
            continue
        try:
            if meta_values(page, name="google-site-verification"):
                errors.append(f"{rel(page)}: Google site verification tag must appear on the homepage only")
        except Exception as exc:
            errors.append(f"{rel(page)}: generated HTML parse failed while checking Google verification metadata: {exc}")


def validate_generated_seo_outputs(posts: list[dict], metadata_by_slug: dict[str, dict], registry: dict[str, dict], status: dict, errors: list[str]) -> None:
    docs = ROOT / "docs"
    recovery = docs / "SEO_RECOVERY.md"
    if not recovery.exists():
        errors.append("docs/SEO_RECOVERY.md missing; archive SEO recovery would be undocumented")
    else:
        recovery_text = recovery.read_text(encoding="utf-8", errors="replace")
        for marker in [
            "scripts/manage-archive-seo.py resume-ds --owner-verified",
            "scripts/manage-archive-seo.py resume-external --post-id 5324 --owner-verified",
            "Do not edit `archive-status.json` manually.",
        ]:
            if marker not in recovery_text:
                errors.append(f"docs/SEO_RECOVERY.md missing required recovery guidance: {marker}")
    if not (docs / "EXTERNAL_SOURCE_STATUS.md").exists():
        errors.append("docs/EXTERNAL_SOURCE_STATUS.md missing; run scripts/external_source_monitor.py")
    robots = docs / "robots.txt"
    sitemap = docs / "sitemap.xml"
    feed = docs / "feed.xml"
    if not robots.exists():
        errors.append("docs/robots.txt missing; run make render-site")
    else:
        lines = robots.read_text(encoding="utf-8", errors="replace").splitlines()
        if "User-agent: *" not in lines or "Allow: /" not in lines:
            errors.append("docs/robots.txt must allow crawlers to observe page-level robots metadata")
        if f"Sitemap: {PAGES_BASE_URL}sitemap.xml" not in lines:
            errors.append("docs/robots.txt sitemap URL is incorrect")
    expected_urls = {PAGES_BASE_URL}
    if status_seo_state(status) == "archive_discovery":
        expected_urls.update(
            PAGES_BASE_URL + f"posts/{post['slug']}/"
            for post in posts
            if status_post_is_eligible(post, registry, status)
        )
        expected_urls.update({
            PAGES_BASE_URL + "sheets/as141253-ipv6-architecture-example/",
            PAGES_BASE_URL + "sheets/as141253-ipv6-architecture-example/visual.html",
        })
    if not sitemap.exists():
        errors.append("docs/sitemap.xml missing; run make render-site")
    else:
        try:
            root = ET.fromstring(sitemap.read_bytes())
            namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            locations = [item.findtext(namespace + "loc", default="") for item in root.findall(namespace + "url")]
            if set(locations) != expected_urls or len(locations) != len(expected_urls):
                errors.append("docs/sitemap.xml URLs do not match the current SEO eligibility state")
            for item in root.findall(namespace + "url"):
                if item.find(namespace + "priority") is not None or item.find(namespace + "changefreq") is not None:
                    errors.append("docs/sitemap.xml must not contain priority or changefreq")
                loc = item.findtext(namespace + "loc", default="")
                lastmod = item.findtext(namespace + "lastmod")
                matching = next((post for post in posts if loc == PAGES_BASE_URL + f"posts/{post['slug']}/"), None)
                if matching is None and lastmod is not None:
                    errors.append(f"docs/sitemap.xml has lastmod on a non-post route: {loc}")
                if matching is not None:
                    expected_lastmod = matching.get("modified")
                    if lastmod != expected_lastmod and lastmod != (expected_lastmod or "").replace("+00:00", "Z"):
                        errors.append(f"docs/sitemap.xml lastmod is not sourced from post metadata for {loc}")
        except Exception as exc:
            errors.append(f"docs/sitemap.xml parse failed: {exc}")
    if status_seo_state(status) != "archive_discovery":
        if feed.exists():
            errors.append("docs/feed.xml must be absent in source_primary")
        return
    if not feed.exists():
        errors.append("docs/feed.xml missing in archive_discovery")
        return
    try:
        root = ET.fromstring(feed.read_bytes())
        channel = root.find("channel")
        if channel is None or channel.findtext("language") != "en-IN":
            errors.append("docs/feed.xml must declare language en-IN")
        atom = "{http://www.w3.org/2005/Atom}link"
        self_links = [item for item in root.findall(f"channel/{atom}") if item.get("rel") == "self"]
        if len(self_links) != 1 or self_links[0].get("href") != PAGES_BASE_URL + "feed.xml":
            errors.append("docs/feed.xml atom self link is incorrect")
        items = root.findall("channel/item")
        eligible = [post for post in posts if status_post_is_eligible(post, registry, status)]
        expected_ids = {int(post["id"]) for post in sorted(eligible, key=lambda item: (item.get("published") or "", int(item.get("id") or 0)), reverse=True)[:10]}
        actual_ids = set()
        for item in items:
            guid = item.findtext("guid", default="")
            match = re.fullmatch(r"urn:daryllswer-com-archive:wordpress-post:([1-9][0-9]*)", guid)
            if not match:
                errors.append(f"docs/feed.xml has an invalid stable ID-based GUID: {guid}")
            else:
                actual_ids.add(int(match.group(1)))
            link = item.findtext("link", default="")
            if not link.startswith(PAGES_BASE_URL + "posts/"):
                errors.append("docs/feed.xml item link is not archive-local")
            encoded = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            body = encoded.text or "" if encoded is not None else ""
            if re.search(r"(?:href|src)=['\"](?:\.?\.?/|/)", body):
                errors.append("docs/feed.xml content:encoded contains a relative local URL")
            if any(marker in body.lower() for marker in ["<comments", "<slash:", "<wfw:", "<wp:", "appeared first"]):
                errors.append("docs/feed.xml content:encoded contains omitted source/comment metadata")
            if match and match.group(1) == REQUIRED_ARCHIVED_RIGHTS_ID:
                registry_record = registry.get(REQUIRED_ARCHIVED_RIGHTS_ID) or {}
                original = registry_record.get("original_article_url", "")
                if original not in body or "Swer Networks" not in body:
                    errors.append("docs/feed.xml BGP repost item does not retain its visible Swer Networks rights/provenance block")
        if channel is not None:
            last_build = channel.findtext("lastBuildDate", default="")
            if not last_build:
                errors.append("docs/feed.xml must include deterministic lastBuildDate")
            image_url = channel.findtext("image/url", default="")
            if image_url != PAGES_BASE_URL + "assets/brand/01_DS_Favicon_Dark_Mode-512.png":
                errors.append("docs/feed.xml must use the archive favicon derivative")
        if len(items) > 10 or actual_ids != expected_ids:
            errors.append("docs/feed.xml items do not match the ten most recent eligible posts")
    except Exception as exc:
        errors.append(f"docs/feed.xml parse failed: {exc}")


def validate_archive_status(status: dict, registry: dict[str, dict], errors: list[str], warnings: list[str]) -> None:
    if not ARCHIVE_STATUS_SCHEMA_PATH.exists():
        errors.append("archive status schema missing")
    else:
        try:
            schema = load_json(ARCHIVE_STATUS_SCHEMA_PATH)
            check_required(status, schema, "archive-status.json", errors)
        except Exception as exc:
            errors.append(f"archive-status.schema.json parse failed: {exc}")
    allowed = {"healthy", "degraded", "canonical_unavailable", "frozen_archive"}
    if status.get("state") not in allowed:
        errors.append(f"archive-status.json has invalid state `{status.get('state')}`")
    if status.get("state") == "frozen_archive" and status.get("frozen") is not True:
        errors.append("archive-status.json frozen_archive state must set frozen=true")
    if status.get("state") != "frozen_archive" and status.get("frozen") is True:
        errors.append("archive-status.json frozen=true outside frozen_archive state")
    if status.get("seo_state") not in {"source_primary", "archive_discovery"}:
        errors.append("archive-status.json has invalid seo_state")
    if status.get("state") == "frozen_archive" and status.get("seo_state") != "archive_discovery":
        errors.append("archive-status.json must activate archive_discovery exactly with frozen_archive")
    if status.get("seo_state") == "source_primary" and status.get("seo_activated_at") is not None:
        errors.append("archive-status.json must never auto-revert archive_discovery to source_primary")
    policy = status.get("policy") or {}
    if policy.get("frozen_archive_noops_without_network") is not True:
        errors.append("archive-status.json must declare frozen_archive no-op policy")
    external_sources = status.get("external_sources") or {}
    for post_id, source in external_sources.items():
        record = registry.get(post_id)
        if not isinstance(record, dict) or record.get("external_fallback") is not True:
            errors.append(f"archive-status.json tracks an external source not opted into the rights registry: {post_id}")
            continue
        if source.get("post_id") != int(post_id):
            errors.append(f"archive-status.json external source post_id does not match its registry key: {post_id}")
    for post_id, record in registry.items():
        if record.get("external_fallback") is not True:
            continue
        source = external_sources.get(post_id)
        if source is None:
            warnings.append(f"archive-status.json has no observation record for opted-in external source {post_id}")
            continue
        if source.get("url") != record.get("original_article_url"):
            errors.append(f"archive-status.json external source URL does not match rights registry for {post_id}")
        if source.get("state") not in {"healthy", "degraded", "source_unavailable", "frozen_source"}:
            errors.append(f"archive-status.json has invalid external source state for {post_id}")
        if source.get("state") == "frozen_source" and source.get("frozen") is not True:
            errors.append(f"archive-status.json frozen_source must set frozen=true for {post_id}")
        if source.get("state") != "frozen_source" and source.get("frozen") is True:
            errors.append(f"archive-status.json external source frozen flag is inconsistent for {post_id}")


def validate_drift_automation(errors: list[str], warnings: list[str], registry: dict[str, dict] | None = None) -> dict | None:
    registry = registry or {}
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
            ("timeout-minutes:", r"^\s*timeout-minutes:\s*25\s*$"),
            ("controlled favicon preparation", r"make\s+prepare-brand-favicon"),
            ("scripts/check-canonical-drift.py", r"scripts/check-canonical-drift\.py"),
            ("scripts/external_source_monitor.py", r"scripts/external_source_monitor\.py"),
            ("scripts/reconcile-canonical-drift.py", r"scripts/reconcile-canonical-drift\.py"),
            ("action-plan outside checkout", r"runner\.temp.*canonical-drift-action-plan\.json"),
            ("reconciliation result outside checkout", r"runner\.temp.*canonical-drift-reconciliation-result\.json"),
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
            "Prepare controlled brand favicon",
            "Check canonical drift",
            "Check external sources",
            "Reconcile canonical drift",
            "Read reconciliation result",
            "Render generated Pages",
            "Verify reconciled canonical state",
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
            ("Prepare controlled brand favicon", r"^run:\s*\|\s*$", "controlled favicon preparation"),
            ("Prepare controlled brand favicon", r"make\s+prepare-brand-favicon", "controlled favicon make target"),
            ("Check canonical drift", r"--action-plan\s+.*runner\.temp.*canonical-drift-action-plan\.json", "external action-plan output"),
            ("Check external sources", r"scripts/external_source_monitor\.py", "external source monitor"),
            ("Check external sources", r"runner\.temp.*external-source-result\.json", "external source result"),
            ("Reconcile canonical drift", r"scripts/reconcile-canonical-drift\.py", "canonical drift reconciler"),
            ("Reconcile canonical drift", r"--result\s+.*runner\.temp.*canonical-drift-reconciliation-result\.json", "external reconciliation result"),
            ("Read reconciliation result", r"content_changed", "reconciliation content-change output"),
            ("Render generated Pages", r"^run:\s+make\s+render-site\s*$", "generated Pages rendering"),
            ("Render generated Pages", r"steps\.external\.outputs\.changed|steps\.canonical\.outputs\.status_changed", "SEO/source-state render trigger"),
            ("Verify reconciled canonical state", r"scripts/check-canonical-drift\.py\s+--fresh\s*$", "fresh post-reconciliation drift comparison"),
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
            "Prepare controlled brand favicon",
            "Check canonical drift",
            "Check external sources",
            "Reconcile canonical drift",
            "Read reconciliation result",
            "Render generated Pages",
            "Verify reconciled canonical state",
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
    validate_archive_status(status, registry, errors, warnings)
    return status


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    report: list[str] = ["# Validation", "", f"Generated: {now_iso()}", ""]
    status_path = ROOT / "archive-status.json"
    status = load_json(status_path) if status_path.exists() else {}

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
        archived_keys = archive_route_keys(archive)
        if post_count != len(posts):
            errors.append(f"archive post_count {post_count} does not match posts length {len(posts)}")
        rights_registry = validate_rights_registry(archive, errors) or {}
        if rights_registry:
            report.extend([
                "## Per-Post Rights Registry",
                "",
                f"- Registry entries: {len(rights_registry)}",
                "- Registry keys are immutable WordPress post IDs.",
                "",
            ])
        if status.get("state") == "frozen_archive":
            report.extend(["## WordPress REST", "", "- Skipped: frozen archive state forbids DS source requests.", ""])
        else:
            try:
                body, headers = request(POSTS_ENDPOINT)
                live_posts = json.loads(body.decode("utf-8"))
                live_total = int(headers.get("X-WP-Total", len(live_posts)))
                live_ids = {item.get("id") for item in live_posts if item.get("id") is not None}
                archived_ids = {item.get("id") for item in posts if item.get("id") is not None}
                missing_active_ids = sorted(archived_ids - live_ids)
                if missing_active_ids:
                    errors.append(f"WordPress REST is missing active archive post IDs: {missing_active_ids}")
                if live_total != len(posts):
                    errors.append(f"WordPress REST reports {live_total} posts, archive has {len(posts)}")
                report.extend(["## WordPress REST", "", f"- Live X-WP-Total: {live_total}", f"- Archived posts: {len(posts)}", ""])
            except Exception as exc:
                warnings.append(f"could not verify WordPress REST count: {exc}")

            try:
                sm_urls = sitemap_urls()
                manifest_urls = {url for post in posts if isinstance((url := post.get("canonical_url")), str)}
                missing, extra, intentional_exclusions = classify_sitemap_difference(sm_urls, manifest_urls)
                if missing:
                    errors.append(f"sitemap URLs missing from archive: {missing}")
                if extra:
                    warnings.append(f"archive URLs not present in post sitemap: {extra}")
                report.extend(["## Sitemap Cross-Check", "", f"- Sitemap post URLs: {len(sm_urls)}", f"- Archive URLs: {len(manifest_urls)}", f"- Documented source-sitemap exceptions: {len(intentional_exclusions)}"])
                report.extend(f"  - `{url}`: {reason}" for url, reason in intentional_exclusions)
                report.append("")
            except Exception as exc:
                warnings.append(f"could not verify sitemap: {exc}")

        for post in posts:
            validate_post(post, errors, warnings, archived_keys)
        font_manifest = validate_pages_site(posts, errors, warnings, archived_keys, rights_registry, status)
        metadata_by_slug = {
            post["slug"]: load_json(ROOT / post["bundle_path"] / "metadata.json")
            for post in posts
            if (ROOT / post["bundle_path"] / "metadata.json").exists()
        }
        validate_generated_seo_outputs(posts, metadata_by_slug, rights_registry, status, errors)
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
            f"- README logo provenance: `{README_BRAND_PROVENANCE_PATH}`",
            f"- Pages header and favicon source: `{PAGES_FAVICON_SOURCE_PATH}`",
            f"- Pages favicon provenance: `{PAGES_FAVICON_PROVENANCE_PATH}`",
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

    drift_status = validate_drift_automation(errors, warnings, rights_registry if archive else {})
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
