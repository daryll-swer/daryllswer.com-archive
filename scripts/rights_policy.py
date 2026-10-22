#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Shared per-post rights resolution and visible-notice helpers."""

from __future__ import annotations

import copy
import hashlib
import html as html_lib
import json
import re
import urllib.parse
from pathlib import Path

import lxml.html


RIGHTS_FIELDS = (
    "rights_holder",
    "copyright_year",
    "rights_status",
    "notice_path",
    "original_article_url",
    "publisher",
    "scope",
    "media_rights",
    "external_fallback",
)
DEFAULT_NOTICE_PATH = "LICENSES/DARYLL-SWER-PROPRIETARY-CONTENT-NOTICE.txt"
DEFAULT_RIGHTS = {
    "rights_holder": "Daryll Swer",
    "copyright_year": 2026,
    "rights_status": "proprietary/all-rights-reserved",
    "notice_path": DEFAULT_NOTICE_PATH,
    "publisher": "Daryll Swer",
    "scope": "article-text",
    "media_rights": "separate attribution/right notices",
    "external_fallback": False,
}
RIGHTS_STATUS = "proprietary/all-rights-reserved"
NOTICE_MARKER = "data-archive-rights-notice"
SEMANTIC_RIGHTS_CATEGORY = "source_rights_declaration"
SITE_COPYRIGHT_CATEGORY = "source_site_copyright_container"
MAPPED_NOTICE_CATEGORY = "mapped_original_source_notice"


def _normalise_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip().lower()


def _tokens(value: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _absolute_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_rights_record(post_id: str, record: object) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"rights registry entry {post_id} must be an object")
    missing = [key for key in RIGHTS_FIELDS if key not in record]
    if missing:
        raise ValueError(f"rights registry entry {post_id} is missing: {', '.join(missing)}")
    extra = sorted(set(record) - set(RIGHTS_FIELDS))
    if extra:
        raise ValueError(f"rights registry entry {post_id} has unsupported fields: {', '.join(extra)}")
    for key in ["rights_holder", "rights_status", "notice_path", "original_article_url", "publisher", "scope", "media_rights"]:
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError(f"rights registry entry {post_id} field {key} must be a non-empty string")
    if not isinstance(record["copyright_year"], int) or isinstance(record["copyright_year"], bool):
        raise ValueError(f"rights registry entry {post_id} field copyright_year must be an integer")
    if not 1900 <= record["copyright_year"] <= 9999:
        raise ValueError(f"rights registry entry {post_id} field copyright_year is outside the supported range")
    if not isinstance(record["external_fallback"], bool):
        raise ValueError(f"rights registry entry {post_id} field external_fallback must be boolean")
    if not _absolute_http_url(record["original_article_url"]):
        raise ValueError(f"rights registry entry {post_id} original_article_url is not an absolute URL")
    if record["rights_status"] != RIGHTS_STATUS:
        raise ValueError(f"rights registry entry {post_id} has unsupported rights_status")


def load_rights_registry(registry_path, schema_path) -> dict[str, dict]:
    registry_path = registry_path if hasattr(registry_path, "read_text") else Path(registry_path)
    schema_path = schema_path if hasattr(schema_path, "read_text") else Path(schema_path)
    if not registry_path.is_file():
        raise ValueError(f"rights registry missing: {registry_path}")
    if not schema_path.is_file():
        raise ValueError(f"rights registry schema missing: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_record = (schema.get("$defs") or {}).get("rights") if isinstance(schema, dict) else None
    if not isinstance(schema_record, dict) or set(schema_record.get("required", [])) != set(RIGHTS_FIELDS):
        raise ValueError("rights registry schema does not define the approved rights record")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        raise ValueError("rights registry must be an object")
    for post_id, record in registry.items():
        if not isinstance(post_id, str) or not re.fullmatch(r"[1-9][0-9]*", post_id):
            raise ValueError(f"rights registry key must be an immutable WordPress ID: {post_id!r}")
        validate_rights_record(post_id, record)
    return registry


def resolve_rights(post_id: int, canonical_url: str, rights_registry: dict[str, dict]) -> dict:
    if not _absolute_http_url(canonical_url):
        raise ValueError(f"post {post_id} canonical_url is not an absolute URL")
    resolved = copy.deepcopy(DEFAULT_RIGHTS)
    resolved["original_article_url"] = canonical_url
    override = rights_registry.get(str(post_id))
    if override is not None:
        validate_rights_record(str(post_id), override)
        resolved.update(copy.deepcopy(override))
    validate_rights_record(str(post_id), resolved)
    return resolved


def rights_for_post(post_id: int, rights_registry: dict[str, dict], canonical_url: str | None = None) -> dict:
    """Resolve an immutable post ID, retaining a small compatibility wrapper for callers."""
    override = rights_registry.get(str(post_id))
    if canonical_url is None:
        if override is None:
            raise ValueError(f"canonical_url is required to resolve default rights for post {post_id}")
        canonical_url = override["original_article_url"]
    return resolve_rights(post_id, canonical_url, rights_registry)


def _nearest_block(element):
    block_tags = {
        "address", "article", "aside", "blockquote", "div", "figcaption", "figure", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "li", "nav", "p", "section",
    }
    current = element
    while current is not None:
        if isinstance(getattr(current, "tag", None), str) and current.tag.lower() in block_tags:
            return current
        current = current.getparent()
    return element


def _element_has_rights_semantics(element) -> bool:
    for attribute in ("rel", "property", "itemprop", "name", "data-license", "data-licence"):
        value = element.get(attribute)
        if not value:
            continue
        tokens = _tokens(value)
        if "license" in tokens or "licence" in tokens or "rights" in tokens:
            return True
    return False


def _audit(category: str, removed: list[str]) -> dict | None:
    if not removed:
        return None
    digest_input = "\n".join(removed).encode("utf-8")
    return {
        "category": category,
        "count": len(removed),
        "sha256": hashlib.sha256(digest_input).hexdigest(),
    }


def _is_mapped_notice(element, rights: dict) -> bool:
    original = rights.get("original_article_url")
    if not original:
        return False
    for anchor in element.xpath(".//a[@href]"):
        href = urllib.parse.urljoin(original, anchor.get("href") or "")
        if href.rstrip("/") == original.rstrip("/"):
            return True
    return False


def _is_explicit_swer_exception(rights: dict) -> bool:
    return (
        _normalise_text(rights.get("rights_holder")) == "swer networks"
        and rights.get("external_fallback") is True
    )


def _has_article_ancestor(element) -> bool:
    return any(
        isinstance(getattr(ancestor, "tag", None), str) and ancestor.tag.lower() == "article"
        for ancestor in element.iterancestors()
    )


def _is_site_chrome(element) -> bool:
    if _has_article_ancestor(element):
        return False
    for candidate in [element, *element.iterancestors()]:
        if not isinstance(getattr(candidate, "tag", None), str):
            continue
        if candidate.tag.lower() in {"aside", "footer", "nav", "header"}:
            return True
        role = _tokens(candidate.get("role"))
        marker_text = " ".join([candidate.get("id") or "", candidate.get("class") or ""]).lower()
        marker = _tokens(marker_text)
        if role & {"complementary", "contentinfo", "navigation"}:
            return True
        if re.search(r"\bsite[-_ ](?:copyright|footer)\b", marker_text) or marker & {"widget", "sidebar"}:
            return True
    return False


def _source_copyright_targets(root, rights: dict) -> list:
    targets = []
    for element in root.iter():
        if not isinstance(getattr(element, "tag", None), str):
            continue
        marker = " ".join([element.get("id") or "", element.get("class") or "", element.get("role") or ""])
        if "copyright" not in _tokens(marker) or not _is_site_chrome(element):
            continue
        targets.append(element)
    for heading in root.xpath(".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6]"):
        heading_marker = " ".join([heading.get("id") or "", heading.get("class") or "", heading.text_content() or ""])
        if "copyright" not in _tokens(heading_marker):
            continue
        for ancestor in heading.iterancestors():
            if ancestor.tag in {"section", "aside", "footer"} and _is_site_chrome(ancestor):
                targets.append(ancestor)
                break
    return targets


def _prune_mapped_notice(root, rights: dict) -> list[str]:
    removed = []
    if not _is_explicit_swer_exception(rights):
        return removed
    original = rights.get("original_article_url")
    holder = _normalise_text(rights.get("rights_holder"))
    publisher = str(rights.get("publisher") or rights.get("rights_holder") or "").strip()
    if not original or not holder:
        return removed
    candidates = []
    for anchor in root.xpath(".//a[@href]"):
        href = urllib.parse.urljoin(original, anchor.get("href") or "")
        if href.rstrip("/") == original.rstrip("/"):
            for ancestor in anchor.iterancestors("blockquote"):
                if ancestor not in candidates:
                    candidates.append(ancestor)
    for candidate in candidates:
        candidate_text = _normalise_text(candidate.text_content())
        if (
            not _is_mapped_notice(candidate, rights)
            or "copyright" not in candidate_text
            or holder not in candidate_text
            or "all rights reserved" not in candidate_text
        ):
            continue
        paragraphs = list(candidate.xpath(".//p"))
        neutral_text = (
            f"This article is republished here from {publisher}. "
            "Media remains subject to separate attribution or rights notices."
        )
        neutral_normalised = _normalise_text(neutral_text)
        for paragraph in paragraphs:
            text = _normalise_text(paragraph.text_content())
            hrefs = paragraph.xpath(".//a[@href]/@href")
            has_original = any(urllib.parse.urljoin(original, href).rstrip("/") == original.rstrip("/") for href in hrefs)
            keeps_copyright = "copyright" in text and holder in text
            keeps_media = "media" in text and ("right" in text or "attribution" in text)
            if has_original or keeps_copyright:
                continue
            if keeps_media and "republish" in text:
                if text == neutral_normalised:
                    continue
                removed.append(text)
                paragraph.clear()
                paragraph.text = neutral_text
                continue
            if keeps_media:
                continue
            removed.append(text)
            paragraph.getparent().remove(paragraph)
    return removed


def sanitise_source_rights_html(html_text: str, *, full_document: bool, rights: dict) -> tuple[str, list[dict]]:
    """Remove source declarations using semantic markup, without matching policy prose."""
    if not html_text:
        return html_text, []
    try:
        root = lxml.html.fromstring(html_text) if full_document else lxml.html.fragment_fromstring(html_text, create_parent="div")
    except (TypeError, ValueError, lxml.etree.ParserError):
        return html_text, []

    transformations: list[dict] = []
    semantic_targets = []
    for element in root.iter():
        if _element_has_rights_semantics(element):
            target = element if element.tag in {"link", "meta"} else _nearest_block(element)
            if target not in semantic_targets:
                semantic_targets.append(target)
    removed_semantic = []
    for target in semantic_targets:
        parent = target.getparent()
        if parent is None:
            continue
        removed_semantic.append(_normalise_text(target.text_content()))
        parent.remove(target)
    if audit := _audit(SEMANTIC_RIGHTS_CATEGORY, removed_semantic):
        transformations.append(audit)

    removed_containers = []
    for target in _source_copyright_targets(root, rights):
        parent = target.getparent()
        if parent is None or target in semantic_targets:
            continue
        removed_containers.append(_normalise_text(target.text_content()))
        parent.remove(target)
    if audit := _audit(SITE_COPYRIGHT_CATEGORY, removed_containers):
        transformations.append(audit)

    removed_notice = _prune_mapped_notice(root, rights)
    if audit := _audit(MAPPED_NOTICE_CATEGORY, removed_notice):
        transformations.append(audit)

    if full_document:
        return lxml.html.tostring(root, encoding="unicode", method="html"), transformations
    parts = [root.text or ""]
    parts.extend(lxml.html.tostring(child, encoding="unicode", method="html") for child in root)
    return "".join(parts), transformations


def _looks_like_html(value: str) -> bool:
    return "<" in value and ">" in value


def _is_rights_key(key: str) -> bool:
    return bool(re.search(r"(?:^|[_-])(licen[cs]e|usage[_-]?rights)(?:$|[_-])", key.lower()))


def sanitise_rest_post(post: dict, *, rights: dict) -> tuple[dict, list[dict]]:
    """Apply the same source-rights filtering to REST JSON before persistence."""
    transformations: list[dict] = []

    def visit(value, key: str | None = None):
        if isinstance(value, dict):
            cleaned = {}
            removed_fields = []
            for child_key, child_value in value.items():
                if _is_rights_key(child_key):
                    removed_fields.append(child_key)
                    continue
                cleaned[child_key] = visit(child_value, child_key)
            if audit := _audit("source_rights_structured_field", removed_fields):
                transformations.append(audit)
            return cleaned
        if isinstance(value, list):
            return [visit(item, key) for item in value]
        if isinstance(value, str) and _looks_like_html(value):
            cleaned, audits = sanitise_source_rights_html(value, full_document=False, rights=rights)
            transformations.extend(audits)
            return cleaned
        return value

    return visit(copy.deepcopy(post)), transformations


def _notice_text(rights: dict) -> tuple[str, str, str, str]:
    holder = html_lib.escape(str(rights["rights_holder"]))
    year = html_lib.escape(str(rights["copyright_year"]))
    original = str(rights["original_article_url"])
    media = html_lib.escape(str(rights["media_rights"]))
    return holder, year, html_lib.escape(original), media


def rights_notice_html(rights: dict) -> str:
    holder, year, original, media = _notice_text(rights)
    if _is_explicit_swer_exception(rights):
        publisher = html_lib.escape(str(rights.get("publisher") or rights["rights_holder"]))
        return (
            '<blockquote class="archive-rights-notice">'
            f'<p>Originally published at <a href="{original}">{publisher}</a>.</p>'
            f'<p><strong>Copyright:</strong> © {year} {holder}. All rights reserved.</p>'
            f'<p>This article is republished here from {publisher}. '
            f'Media remains subject to {media}.</p>'
            "</blockquote>"
        )
    return (
        f'<p class="archive-rights-notice" {NOTICE_MARKER}="true">'
        f'<strong>Copyright:</strong> © {year} {holder}. All rights reserved.</p>'
    )


def rights_notice_markdown(rights: dict) -> str:
    holder = str(rights["rights_holder"])
    year = str(rights["copyright_year"])
    if _is_explicit_swer_exception(rights):
        publisher = str(rights.get("publisher") or rights["rights_holder"])
        original = str(rights["original_article_url"])
        media = str(rights["media_rights"])
        return (
            f"> Originally published at [{publisher}]({original}).\n>\n"
            f"> **Copyright:** © {year} {holder}. All rights reserved.\n>\n"
            f"> This article is republished here from {publisher}. "
            f"Media remains subject to {media}.\n"
        )
    return (
        f"> **Copyright:** © {year} {holder}. All rights reserved.\n"
    )


def sanitise_source_rights_markdown(markdown: str, *, rights: dict) -> tuple[str, list[dict]]:
    """Normalise one bounded mapped-source notice without re-converting article Markdown."""
    if not markdown or not _is_explicit_swer_exception(rights):
        return markdown, []
    lines = markdown.splitlines(keepends=True)
    groups: list[tuple[int, int, str]] = []
    start = None
    for index, line in enumerate(lines + [""]):
        if line.startswith(">"):
            if start is None:
                start = index
            continue
        if start is not None:
            groups.append((start, index, "".join(lines[start:index])))
            start = None
    holder = _normalise_text(rights.get("rights_holder"))
    original = str(rights.get("original_article_url") or "").rstrip("/")
    for start, end, group in groups:
        normalised = _normalise_text(group)
        if holder not in normalised or "all rights reserved" not in normalised or original not in group:
            continue
        old_text = _normalise_text(group)
        canonical_notice = rights_notice_markdown(rights)
        if normalised == _normalise_text(canonical_notice):
            return markdown, []
        replacement = canonical_notice.rstrip("\n") + "\n"
        updated = "".join(lines[:start] + [replacement] + lines[end:])
        return updated, [_audit(MAPPED_NOTICE_CATEGORY, [old_text])]
    return markdown, []


def normalise_markdown_notice_eof(markdown: str, *, rights: dict) -> str:
    """Collapse trailing blank lines after an existing generated DS notice."""
    if not markdown or _is_explicit_swer_exception(rights):
        return markdown
    canonical = rights_notice_markdown(rights).rstrip("\n")
    if markdown_notice_count(markdown, rights) != 1 or not markdown.rstrip("\n").endswith(canonical):
        return markdown
    return markdown.rstrip("\n") + "\n"


def markdown_notice_count(markdown: str, rights: dict) -> int:
    body = markdown.split("---", 2)[-1] if markdown.lstrip().startswith("---") else markdown
    lines = body.splitlines()
    groups: list[str] = []
    current: list[str] = []
    for line in lines + [""]:
        if line.startswith(">"):
            current.append(line[1:].strip())
        elif current:
            groups.append(" ".join(current))
            current = []
    holder = _normalise_text(rights.get("rights_holder"))
    return sum(
        1
        for group in groups
        if holder in _normalise_text(group)
        and "all rights reserved" in _normalise_text(group)
    )


def html_notice_count(document, rights: dict) -> int:
    holder = _normalise_text(rights.get("rights_holder"))
    original = str(rights.get("original_article_url") or "").rstrip("/")
    count = 0
    for notice in document.xpath(f"//*[@{NOTICE_MARKER}]"):
        text = _normalise_text(notice.text_content())
        if holder in text and "all rights reserved" in text:
            count += 1
    for element in document.xpath(".//blockquote"):
        if element.get(NOTICE_MARKER) or element.xpath(f".//*[@{NOTICE_MARKER}]"):
            continue
        links = [url.rstrip("/") for url in element.xpath(".//a[@href]/@href")]
        text = _normalise_text(element.text_content())
        if original in links and holder in text and "all rights reserved" in text:
            count += 1
    return count

