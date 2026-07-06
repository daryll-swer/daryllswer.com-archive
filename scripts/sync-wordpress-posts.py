#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Mirror published daryllswer.com WordPress posts from public endpoints."""

from __future__ import annotations

import datetime as dt
import email.message
import hashlib
import html as html_lib
import json
import mimetypes
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
import copy
from pathlib import Path

try:
    import lxml.html
except Exception as exc:  # pragma: no cover - environment guard
    raise SystemExit("Missing dependency: lxml. Install requirements.txt first.") from exc

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dimension support
    Image = None


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://www.daryllswer.com"
POSTS_ENDPOINT = f"{SITE}/wp-json/wp/v2/posts?per_page=100&_embed=1"
MEDIA_ENDPOINT = f"{SITE}/wp-json/wp/v2/media"
UA = "daryllswer-com-archive-sync/1.0 (+https://www.daryllswer.com/)"
OPERATIONAL_CTA_LABEL = "donation_or_support_cta"
DONATION_TEXT_MARKERS = (
    "it would be appreciated if you could help me continue to provide valuable network engineering content",
    "your donation will help me conduct valuable experiments",
)
DONATION_URL_MARKERS = (
    "/donation/",
)
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "nav",
    "p",
    "section",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def request(url: str) -> tuple[bytes, email.message.Message]:
    req = urllib.request.Request(iri_to_uri(url), headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read(), resp.headers


def iri_to_uri(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parsed.path, safe="/%:@")
    query = urllib.parse.quote(parsed.query, safe="=&?/:;%+")
    fragment = urllib.parse.quote(parsed.fragment, safe="=&?/:;%+")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, fragment))


def fetch_json(url: str):
    body, _ = request(url)
    return json.loads(body.decode("utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    try:
        return lxml.html.fromstring(value).text_content().strip()
    except Exception:
        return re.sub(r"<[^>]+>", "", value).strip()


def normalise_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip().lower()


def nearest_block(el):
    current = el
    while current is not None:
        tag = getattr(current, "tag", "")
        if isinstance(tag, str) and tag.lower() in BLOCK_TAGS:
            return current
        current = current.getparent()
    return el


def element_has_operational_cta(el) -> bool:
    tag = getattr(el, "tag", "")
    if not isinstance(tag, str):
        return False
    text = normalise_text(el.text_content() if tag.lower() != "script" else el.text or "")
    if any(marker in text for marker in DONATION_TEXT_MARKERS):
        return True
    href = el.get("href") or ""
    if any(marker in href for marker in DONATION_URL_MARKERS):
        return True
    return False


def drop_donation_fields_from_jsonld(value):
    """Remove donation URL fields from JSON-LD while preserving other metadata."""
    removed = 0
    if isinstance(value, list):
        out = []
        for item in value:
            cleaned, count = drop_donation_fields_from_jsonld(item)
            removed += count
            out.append(cleaned)
        return out, removed
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(item, str) and any(marker in item for marker in DONATION_URL_MARKERS):
                removed += 1
                continue
            cleaned, count = drop_donation_fields_from_jsonld(item)
            removed += count
            out[key] = cleaned
        return out, removed
    return value, 0


def sanitise_jsonld_scripts(root) -> int:
    removed = 0
    for script in root.xpath(".//script[@type='application/ld+json']"):
        text = script.text or ""
        if not any(marker in text for marker in DONATION_URL_MARKERS):
            continue
        try:
            data = json.loads(text)
        except Exception:
            parent = script.getparent()
            if parent is not None:
                parent.remove(script)
                removed += 1
            continue
        cleaned, count = drop_donation_fields_from_jsonld(data)
        if count:
            script.text = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
            removed += count
    return removed


def sanitise_operational_ctas(html_text: str, *, full_document: bool) -> tuple[str, list[dict]]:
    """Remove site-operational donation/support CTAs from archived article files."""
    if not html_text:
        return html_text, []
    try:
        if full_document:
            root = lxml.html.fromstring(html_text)
        else:
            root = lxml.html.fragment_fromstring(html_text, create_parent="div")
    except Exception:
        return html_text, []

    targets = []
    for el in root.iter():
        if element_has_operational_cta(el):
            targets.append(nearest_block(el))

    final_targets = []
    for target in targets:
        if any(other is not target and other in target.iterdescendants() for other in targets):
            continue
        if target not in final_targets:
            final_targets.append(target)

    exclusions = []
    for target in final_targets:
        parent = target.getparent()
        if parent is None:
            continue
        removed_text = normalise_text(target.text_content())
        exclusions.append({
            "filter": OPERATIONAL_CTA_LABEL,
            "tag": target.tag,
            "redacted": True,
            "removed_text_sha256": sha256_bytes(removed_text.encode("utf-8")),
        })
        parent.remove(target)

    jsonld_removed = sanitise_jsonld_scripts(root) if full_document else 0
    if jsonld_removed:
        exclusions.append({
            "filter": OPERATIONAL_CTA_LABEL,
            "tag": "script",
            "text": f"removed {jsonld_removed} donation URL field(s) from JSON-LD",
        })

    if full_document:
        return lxml.html.tostring(root, encoding="unicode", method="html"), exclusions

    parts = []
    if root.text:
        parts.append(root.text)
    for child in root:
        parts.append(lxml.html.tostring(child, encoding="unicode", method="html"))
    return "".join(parts), exclusions


def slugify_filename(value: str, fallback: str = "asset") -> str:
    value = html_lib.unescape(value)
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    return value or fallback


def date_slug(post: dict) -> str:
    date_part = post["date"][:10]
    return f"{date_part}-{post['slug']}"


def relpath(path: Path, start: Path = ROOT) -> str:
    return path.relative_to(start).as_posix()


def yaml_scalar(value) -> str:
    if value is None:
        return "null"
    text = str(value)
    return json.dumps(text, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n" + "\n".join(f"  - {yaml_scalar(v)}" for v in values)


def taxonomy(post: dict) -> tuple[list[dict], list[dict]]:
    categories: list[dict] = []
    tags: list[dict] = []
    for group in post.get("_embedded", {}).get("wp:term", []) or []:
        for term in group or []:
            item = {
                "id": term.get("id"),
                "name": term.get("name"),
                "slug": term.get("slug"),
                "taxonomy": term.get("taxonomy"),
            }
            if term.get("taxonomy") == "category":
                categories.append(item)
            elif term.get("taxonomy") == "post_tag":
                tags.append(item)
    return categories, tags


def embedded_featured(post: dict) -> dict | None:
    items = post.get("_embedded", {}).get("wp:featuredmedia", []) or []
    for item in items:
        if item and item.get("source_url"):
            return item
    return None


def fetch_media(media_id: int) -> dict | None:
    if not media_id:
        return None
    try:
        return fetch_json(f"{MEDIA_ENDPOINT}/{media_id}")
    except Exception:
        return None


def parse_canonical_metadata(page_html: str) -> dict:
    meta: dict = {"open_graph": {}, "json_ld": []}
    try:
        doc = lxml.html.fromstring(page_html)
    except Exception:
        return meta
    canonical = doc.xpath("//link[translate(@rel, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='canonical']/@href")
    if canonical:
        meta["canonical_url"] = canonical[0]
    for el in doc.xpath("//meta[@property or @name]"):
        key = el.get("property") or el.get("name")
        content = el.get("content")
        if key and content and key.startswith("og:"):
            meta["open_graph"][key] = content
    for script in doc.xpath("//script[@type='application/ld+json']/text()"):
        script = script.strip()
        if not script:
            continue
        try:
            meta["json_ld"].append(json.loads(script))
        except Exception:
            continue
    return meta


def find_jsonld_image(items) -> str | None:
    stack = list(items if isinstance(items, list) else [items])
    while stack:
        item = stack.pop(0)
        if isinstance(item, list):
            stack.extend(item)
            continue
        if not isinstance(item, dict):
            continue
        if "@graph" in item:
            stack.extend(item["@graph"] if isinstance(item["@graph"], list) else [item["@graph"]])
        image = item.get("image")
        if isinstance(image, str):
            return image
        if isinstance(image, dict):
            for key in ("url", "contentUrl"):
                if isinstance(image.get(key), str):
                    return image[key]
        if isinstance(image, list):
            stack.extend(image)
    return None


def first_image_url(content_html: str, base_url: str) -> str | None:
    try:
        root = lxml.html.fragment_fromstring(content_html, create_parent="div")
    except Exception:
        return None
    srcs = root.xpath(".//img/@src")
    if not srcs:
        return None
    return urllib.parse.urljoin(base_url, srcs[0])


def featured_candidate(post: dict, canonical_meta: dict, page_html: str) -> tuple[str | None, dict | None, str]:
    media = embedded_featured(post)
    if media and media.get("source_url"):
        return media["source_url"], media, "rest_embedded_wp_featuredmedia"

    media = fetch_media(int(post.get("featured_media") or 0))
    if media and media.get("source_url"):
        return media["source_url"], media, "rest_featured_media_id"

    og_image = canonical_meta.get("open_graph", {}).get("og:image")
    if og_image:
        return urllib.parse.urljoin(post["link"], og_image), None, "open_graph_og_image"

    jsonld_image = find_jsonld_image(canonical_meta.get("json_ld", []))
    if jsonld_image:
        return urllib.parse.urljoin(post["link"], jsonld_image), None, "json_ld_image"

    fallback = first_image_url(post.get("content", {}).get("rendered", ""), post["link"])
    if fallback:
        return fallback, None, "first_article_image"

    return None, None, "not_found"


def image_dimensions(path: Path) -> tuple[int | None, int | None]:
    if Image is None:
        return None, None
    try:
        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except Exception:
        return None, None


def ext_from_url_or_type(url: str, content_type: str | None, default: str = ".bin") -> str:
    ext = Path(urllib.parse.urlparse(url).path).suffix
    if ext and len(ext) <= 8:
        return ext.split("?")[0]
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return default


def download_asset(
    url: str,
    dest_dir: Path,
    role: str,
    target_name: str | None = None,
    alt: str | None = None,
    caption: str | None = None,
    detection_method: str | None = None,
) -> dict | None:
    if not url:
        return None
    try:
        body, headers = request(url)
    except Exception as exc:
        return {
            "role": role,
            "source_url": url,
            "local_path": None,
            "sha256": None,
            "download_error": str(exc),
            "detection_method": detection_method,
        }
    content_type = headers.get("Content-Type")
    ext = ext_from_url_or_type(url, content_type)
    if target_name:
        filename = target_name if Path(target_name).suffix else f"{target_name}{ext}"
    else:
        parsed_name = Path(urllib.parse.urlparse(url).path).name
        filename = slugify_filename(parsed_name or f"{role}{ext}")
        if not Path(filename).suffix:
            filename += ext
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if dest.exists() and dest.read_bytes() != body:
        stem = dest.stem
        suffix = dest.suffix
        dest = dest.with_name(f"{stem}-{sha256_bytes(body)[:8]}{suffix}")
    dest.write_bytes(body)
    width, height = image_dimensions(dest)
    return {
        "role": role,
        "source_url": url,
        "local_path": relpath(dest),
        "sha256": sha256_bytes(body),
        "mime_type": content_type,
        "bytes": len(body),
        "width": width,
        "height": height,
        "alt": alt,
        "caption": caption,
        "detection_method": detection_method,
    }


def collect_inline_images(content_html: str, base_url: str) -> list[dict]:
    try:
        root = lxml.html.fragment_fromstring(content_html, create_parent="div")
    except Exception:
        return []
    images: list[dict] = []
    for img in root.xpath(".//img"):
        src = img.get("src")
        if not src:
            continue
        caption = None
        fig = img.getparent()
        while fig is not None and getattr(fig, "tag", "").lower() != "figure":
            fig = fig.getparent()
        if fig is not None:
            caps = fig.xpath(".//figcaption")
            if caps:
                caption = " ".join(caps[0].text_content().split())
        images.append({
            "source_url": urllib.parse.urljoin(base_url, src),
            "alt": img.get("alt") or None,
            "caption": caption,
        })
    return images


def text_of(el) -> str:
    return " ".join(el.text_content().split())


def table_to_markdown(table) -> str:
    rows = []
    for tr in table.xpath(".//tr"):
        cells = [text_of(c) for c in tr.xpath("./th|./td")]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |"]
    out.append("| " + " | ".join(["---"] * width) + " |")
    for row in rows[1:]:
        out.append("| " + " | ".join(row) + " |")
    return "\n\n" + "\n".join(out) + "\n\n"


class MarkdownConverter:
    def __init__(self, asset_map: dict[str, str], skip_first_image_url: str | None):
        self.asset_map = asset_map
        self.skip_first_image_url = skip_first_image_url
        self.first_image_seen = False

    def convert_fragment(self, content_html: str, base_url: str) -> str:
        try:
            root = lxml.html.fragment_fromstring(content_html, create_parent="div")
        except Exception:
            return content_html
        text = self.children(root, base_url)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"

    def children(self, el, base_url: str) -> str:
        out = el.text or ""
        for child in el:
            out += self.node(child, base_url)
            out += child.tail or ""
        return out

    def node(self, el, base_url: str) -> str:
        tag = getattr(el, "tag", "").lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            return "\n\n" + "#" * level + " " + text_of(el) + "\n\n"
        if tag == "p":
            return "\n\n" + self.children(el, base_url).strip() + "\n\n"
        if tag == "br":
            return "  \n"
        if tag in {"strong", "b"}:
            return "**" + self.children(el, base_url).strip() + "**"
        if tag in {"em", "i"}:
            return "*" + self.children(el, base_url).strip() + "*"
        if tag == "code":
            return "`" + (el.text_content() or "").strip() + "`"
        if tag == "pre":
            code = el.text_content().rstrip()
            return "\n\n```\n" + code + "\n```\n\n"
        if tag == "a":
            href = el.get("href")
            label = self.children(el, base_url).strip() or href or ""
            if href:
                return f"[{label}]({urllib.parse.urljoin(base_url, href)})"
            return label
        if tag == "img":
            src = urllib.parse.urljoin(base_url, el.get("src") or "")
            if not self.first_image_seen:
                self.first_image_seen = True
                if self.skip_first_image_url and src == self.skip_first_image_url:
                    return ""
            alt = el.get("alt") or ""
            local = self.asset_map.get(src, src)
            return f"![{alt}]({local})"
        if tag == "figure":
            return "\n\n" + self.children(el, base_url).strip() + "\n\n"
        if tag == "figcaption":
            caption = self.children(el, base_url).strip()
            return "\n\n_" + caption + "_\n\n" if caption else ""
        if tag in {"ul", "ol"}:
            lines = []
            ordered = tag == "ol"
            for idx, li in enumerate(el.xpath("./li"), start=1):
                body = self.children(li, base_url).strip()
                prefix = f"{idx}. " if ordered else "- "
                lines.append(prefix + body.replace("\n", "\n  "))
            return "\n\n" + "\n".join(lines) + "\n\n"
        if tag == "li":
            return "- " + self.children(el, base_url).strip() + "\n"
        if tag == "blockquote":
            body = self.children(el, base_url).strip()
            return "\n\n" + "\n".join("> " + line for line in body.splitlines()) + "\n\n"
        if tag == "table":
            return table_to_markdown(el)
        if tag in {"iframe", "video", "audio", "embed"}:
            return "\n\n" + lxml.html.tostring(el, encoding="unicode").strip() + "\n\n"
        return self.children(el, base_url)


def frontmatter(post: dict, categories: list[dict], tags: list[dict], featured_local: str | None) -> str:
    title = strip_html(post.get("title", {}).get("rendered"))
    lines = [
        "---",
        f"title: {yaml_scalar(title)}",
        f"slug: {yaml_scalar(post.get('slug'))}",
        f"date: {yaml_scalar(post.get('date'))}",
        f"last_modified: {yaml_scalar(post.get('modified'))}",
        f"canonical_url: {yaml_scalar(post.get('link'))}",
        f"wordpress_id: {post.get('id')}",
        f"featured_image: {yaml_scalar(featured_local)}",
        "categories:" + yaml_list([c.get("name") or c.get("slug") or "" for c in categories]),
        "tags:" + yaml_list([t.get("name") or t.get("slug") or "" for t in tags]),
        "---",
        "",
    ]
    return "\n".join(lines)


def sync_post(post: dict, generated_at: str) -> dict:
    bundle = ROOT / "content" / "posts" / date_slug(post)
    source_dir = bundle / "source"
    assets_dir = bundle / "assets"
    inline_dir = assets_dir / "inline"
    source_dir.mkdir(parents=True, exist_ok=True)
    inline_dir.mkdir(parents=True, exist_ok=True)

    canonical_body, _ = request(post["link"])
    canonical_html_raw = canonical_body.decode("utf-8", errors="replace")
    rendered_article_raw = post.get("content", {}).get("rendered", "")
    canonical_meta = parse_canonical_metadata(canonical_html_raw)
    rendered_article, article_exclusions = sanitise_operational_ctas(rendered_article_raw, full_document=False)
    canonical_html, page_exclusions = sanitise_operational_ctas(canonical_html_raw, full_document=True)
    categories, tags = taxonomy(post)

    archived_post = copy.deepcopy(post)
    archived_post.setdefault("content", {})["rendered"] = rendered_article
    archived_post["_archive_filters"] = article_exclusions

    write_json(source_dir / "wordpress-post.json", archived_post)
    write_text(source_dir / "rendered-article.html", rendered_article)
    write_text(source_dir / "canonical-page.html", canonical_html)

    assets: list[dict] = []
    asset_map: dict[str, str] = {}

    featured_url, featured_media, featured_method = featured_candidate(post, canonical_meta, canonical_html)
    featured_asset = None
    if featured_url:
        ext = ext_from_url_or_type(featured_url, None, ".img")
        featured_asset = download_asset(
            featured_url,
            assets_dir,
            "featured",
            target_name=f"featured{ext}",
            alt=(featured_media or {}).get("alt_text") if featured_media else None,
            caption=strip_html((featured_media or {}).get("caption", {}).get("rendered")) if featured_media else None,
            detection_method=featured_method,
        )
        if featured_asset:
            assets.append(featured_asset)
            if featured_asset.get("local_path"):
                local_from_md = os.path.relpath(ROOT / featured_asset["local_path"], bundle).replace(os.sep, "/")
                asset_map[featured_url] = local_from_md

    for item in collect_inline_images(rendered_article, post["link"]):
        src = item["source_url"]
        if src in asset_map:
            continue
        asset = download_asset(src, inline_dir, "inline", alt=item.get("alt"), caption=item.get("caption"))
        if not asset:
            continue
        assets.append(asset)
        if asset.get("local_path"):
            asset_map[src] = os.path.relpath(ROOT / asset["local_path"], bundle).replace(os.sep, "/")

    skip_featured = featured_url if featured_url in asset_map else None
    converter = MarkdownConverter(asset_map, skip_featured)
    body_md = converter.convert_fragment(rendered_article, post["link"])
    featured_local = None
    if featured_asset and featured_asset.get("local_path"):
        featured_local = os.path.relpath(ROOT / featured_asset["local_path"], bundle).replace(os.sep, "/")

    title = strip_html(post.get("title", {}).get("rendered"))
    md = frontmatter(post, categories, tags, featured_local)
    if featured_local:
        alt = (featured_asset or {}).get("alt") or title
        md += f"![{alt}]({featured_local})\n\n"
    md += body_md
    write_text(bundle / "index.md", md)

    asset_manifest = {
        "generated_at": generated_at,
        "post_id": post["id"],
        "post_slug": post["slug"],
        "assets": assets,
    }
    write_json(assets_dir / "manifest.json", asset_manifest)

    metadata = {
        "id": post["id"],
        "slug": post["slug"],
        "title": title,
        "canonical_url": post["link"],
        "published": post["date"],
        "modified": post["modified"],
        "author": {
            "id": post.get("author"),
            "name": (post.get("_embedded", {}).get("author", [{}]) or [{}])[0].get("name"),
        },
        "categories": categories,
        "tags": tags,
        "excerpt": strip_html(post.get("excerpt", {}).get("rendered")),
        "source": {
            "api_url": f"{SITE}/wp-json/wp/v2/posts/{post['id']}",
            "canonical_html_path": "source/canonical-page.html",
            "rendered_article_path": "source/rendered-article.html",
            "wordpress_post_path": "source/wordpress-post.json",
            "fetched_at": generated_at,
        },
        "archive_filters": {
            "applied": bool(article_exclusions or page_exclusions),
            "article_body_exclusions": article_exclusions,
            "canonical_page_exclusions": page_exclusions,
        },
        "hashes": {
            "wordpress_post_json_sha256": sha256_file(source_dir / "wordpress-post.json"),
            "canonical_page_html_sha256": sha256_file(source_dir / "canonical-page.html"),
            "rendered_article_html_sha256": sha256_file(source_dir / "rendered-article.html"),
            "index_md_sha256": sha256_file(bundle / "index.md"),
        },
        "featured_image": featured_asset if featured_asset and featured_asset.get("local_path") else None,
        "featured_image_detection_method": featured_method,
        "assets_manifest": "assets/manifest.json",
        "validation": {"status": "pending"},
    }
    if featured_media:
        metadata["featured_media_sizes"] = featured_media.get("media_details", {}).get("sizes", {})
    write_json(bundle / "metadata.json", metadata)

    return {
        "id": post["id"],
        "slug": post["slug"],
        "title": title,
        "canonical_url": post["link"],
        "bundle_path": relpath(bundle),
        "published": post["date"],
        "modified": post["modified"],
        "featured_image": featured_local,
        "validation_status": "pending",
    }


def fetch_all_posts() -> tuple[list[dict], dict[str, str]]:
    body, headers = request(POSTS_ENDPOINT)
    posts = json.loads(body.decode("utf-8"))
    total = int(headers.get("X-WP-Total", len(posts)))
    pages = int(headers.get("X-WP-TotalPages", 1))
    all_posts = list(posts)
    for page in range(2, pages + 1):
        all_posts.extend(fetch_json(f"{POSTS_ENDPOINT}&page={page}"))
    if len(all_posts) != total:
        print(f"warning: REST header reported {total} posts but fetched {len(all_posts)}", file=sys.stderr)
    return all_posts, {"x_wp_total": str(total), "x_wp_totalpages": str(pages)}


def main() -> int:
    generated_at = now_iso()
    posts, rest_headers = fetch_all_posts()
    manifest_posts = [sync_post(post, generated_at) for post in posts]
    manifest = {
        "generated_at": generated_at,
        "source_site": SITE,
        "rest_endpoint": POSTS_ENDPOINT,
        "rest_headers": rest_headers,
        "post_count": len(manifest_posts),
        "posts": manifest_posts,
        "sheets": [
            {
                "name": "AS141253 IPv6 Architecture Example",
                "path": "data/sheets/as141253-ipv6-architecture-example/manifest.json",
            }
        ],
    }
    write_json(ROOT / "archive-manifest.json", manifest)
    print(f"synced {len(manifest_posts)} posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
