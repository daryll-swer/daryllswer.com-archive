# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Allowlist sanitisation for article HTML published on GitHub Pages."""

from __future__ import annotations

import html
import urllib.parse

import lxml.html
import nh3


ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "cite", "code", "dd",
    "del", "details", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li", "mark",
    "ol", "p", "pre", "q", "s", "samp", "small", "span", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time", "tr", "u", "ul",
}
DROP_CONTENT_TAGS = {
    "applet", "audio", "canvas", "embed", "form", "iframe", "math", "object",
    "script", "style", "svg", "template", "video",
}
ATTRIBUTES = {
    "*": {"class", "id", "title"},
    "a": {"href", "target", "aria-label"},
    "blockquote": {"cite"},
    "del": {"cite", "datetime"},
    "img": {"src", "alt", "width", "height", "loading", "decoding"},
    "ins": {"cite", "datetime"},
    "ol": {"start", "type"},
    "q": {"cite"},
    "span": {"style", "aria-hidden"},
    "p": {"style"},
    "div": {"style"},
    "table": {"style"},
    "td": {"colspan", "rowspan", "headers", "style"},
    "th": {"colspan", "rowspan", "headers", "scope", "abbr", "style"},
    "time": {"datetime"},
    "mark": {"style"},
}
STYLE_PROPERTIES = {
    "background-color", "color",
}

CLEANER = nh3.Cleaner(
    tags=ALLOWED_TAGS,
    clean_content_tags=DROP_CONTENT_TAGS,
    attributes=ATTRIBUTES,
    url_schemes={"http", "https", "mailto", "tel"},
    tag_attribute_values={"p": {"data-archive-rights-notice": {"true"}}},
    filter_style_properties=STYLE_PROPERTIES,
    link_rel="noopener noreferrer",
)


def _media_link(element) -> None:
    src = element.get("src") or ""
    parsed = urllib.parse.urlsplit(src)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        element.drop_tree()
        return
    label = (element.get("title") or "Embedded media").strip()
    wrapper = lxml.html.Element("div", **{"class": "media-embed"})
    description = lxml.html.Element("p", **{"class": "embed-label"})
    description.text = label
    fallback = lxml.html.Element("p", **{"class": "embed-fallback"})
    anchor = lxml.html.Element("a", href=src, **{"class": "media-fallback", "target": "_blank"})
    anchor.text = f"Open {label}"
    fallback.append(anchor)
    wrapper.append(description)
    wrapper.append(fallback)
    wrapper.tail = element.tail
    element.getparent().replace(element, wrapper)


def sanitize_article_html(fragment: str) -> str:
    """Sanitise a source article fragment while retaining safe editorial markup."""
    root = lxml.html.fragment_fromstring(fragment, create_parent="div")
    for frame in list(root.xpath(".//iframe")):
        _media_link(frame)
    body = html.escape(root.text or "", quote=False) + "".join(
        lxml.html.tostring(child, encoding="unicode") for child in root
    )
    clean = CLEANER.clean(body)
    return clean
