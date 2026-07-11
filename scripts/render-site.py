#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Generate the GitHub Pages static HTML site under docs/."""

from __future__ import annotations

import datetime as dt
import html as html_lib
import json
import os
import re
import shutil
import urllib.parse
from pathlib import Path

from font_assets import FONT_BODY_STACK, FONT_HEADING_STACK, copy_font_assets, font_face_css
from sheet_workbook import render_workbook_page
from wordpress_palette import wordpress_palette_css

try:
    import lxml.html
except Exception as exc:  # pragma: no cover - environment guard
    raise SystemExit("Missing dependency: lxml. Install requirements.txt first.") from exc


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
PAGES_BASE_URL = "https://daryll-swer.github.io/daryllswer.com-archive/"
SHEET_SLUG = "as141253-ipv6-architecture-example"
SHEET_SOURCE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ32t5C9BW-rV36gUo93uYcLw9GMPqg7BMks8u17dlLhWmIUzIdCe4iexLBQKdnDwykAom929K2dTxR/pubhtml"
LOCALISABLE_HOSTS = {"www.daryllswer.com", "daryllswer.com"}
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TEXT_FRAGMENT_PREFIX = ":~:text="


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if text:
        text = "\n".join(line.rstrip() for line in text.split("\n"))
    path.write_text(text, encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean_generated_site() -> None:
    for path in [OUT / "posts", OUT / "assets", OUT / "sheets"]:
        if path.exists():
            shutil.rmtree(path)
    for path in [OUT / "index.html", OUT / ".nojekyll"]:
        if path.exists():
            path.unlink()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    try:
        return lxml.html.fromstring(value).text_content().strip()
    except Exception:
        return re.sub(r"<[^>]+>", "", value).strip()


def html_escape(value: object) -> str:
    return html_lib.escape(str(value), quote=True)


def format_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%d %B %Y")


def markdown_excerpt(path: Path, limit: int = 280) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"^---.*?---", "", text, flags=re.S).strip()
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<iframe[^>]*>.*?</iframe>", "", text, flags=re.S | re.I)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*_`>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def post_excerpt(bundle: Path, metadata: dict) -> str:
    excerpt = strip_html(metadata.get("excerpt"))
    excerpt = re.sub(r"\s*Continue reading.*$", "", excerpt, flags=re.I | re.S).strip()
    if excerpt:
        return excerpt
    return markdown_excerpt(bundle / "index.md")


def media_key(url: str | None) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parsed.path)
    name = Path(path).name.lower()
    return re.sub(r"-\d+x\d+(?=\.[a-z0-9]+$)", "", name)


def build_asset_maps(bundle: Path) -> tuple[dict[str, str], dict[str, str]]:
    manifest_path = bundle / "assets" / "manifest.json"
    if not manifest_path.exists():
        return {}, {}
    exact: dict[str, str] = {}
    by_key: dict[str, str] = {}
    manifest = load_json(manifest_path)
    for asset in manifest.get("assets", []):
        local_path = asset.get("local_path")
        source_url = asset.get("source_url")
        if not local_path or not source_url:
            continue
        try:
            rel_path = (ROOT / local_path).relative_to(bundle).as_posix()
        except ValueError:
            continue
        exact[source_url] = rel_path
        key = media_key(source_url)
        if key:
            by_key[key] = rel_path
    return exact, by_key


def local_asset_for(url: str | None, exact: dict[str, str], by_key: dict[str, str]) -> str | None:
    if not url:
        return None
    if url in exact:
        return exact[url]
    key = media_key(url)
    if key and key in by_key:
        return by_key[key]
    return None


def heading_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def heading_xpath() -> str:
    return ".//*[self::h2 or self::h3 or self::h4 or self::h5 or self::h6]"


def ensure_heading_ids(root) -> None:
    seen: set[str] = {
        element_id
        for element_id in root.xpath(".//*[@id]/@id")
        if element_id
    }
    used_heading_ids: set[str] = set()
    for heading in root.xpath(heading_xpath()):
        current = (heading.get("id") or "").strip()
        base = current or heading_slug(heading.text_content())
        slug = base
        counter = 2
        while slug in used_heading_ids:
            slug = f"{base}-{counter}"
            counter += 1
        heading.set("id", slug)
        seen.add(slug)
        used_heading_ids.add(slug)
        if slug.startswith("h-"):
            add_anchor_alias(heading, slug[2:], seen)


def heading_target_id(heading_id: str) -> str:
    return heading_id[2:] if heading_id.startswith("h-") else heading_id


def heading_label(heading) -> str:
    label = re.sub(r"\s+", " ", heading.text_content()).strip()
    return label[:120] or "this section"


def fragment_href(target_id: str) -> str:
    return "#" + urllib.parse.quote(target_id, safe="-._~")


def add_heading_permalink_controls(root) -> None:
    for heading in root.xpath(heading_xpath()):
        heading_id = (heading.get("id") or "").strip()
        if not heading_id:
            continue
        target_id = heading_target_id(heading_id)
        label = heading_label(heading)
        href = fragment_href(target_id)

        if not heading.xpath(".//a"):
            title_link = lxml.html.Element(
                "a",
                {
                    "class": "heading-title-link",
                    "href": href,
                    "aria-label": f"Permalink to {label} section",
                },
            )
            title_link.text = heading.text
            heading.text = None
            for child in list(heading):
                heading.remove(child)
                title_link.append(child)
            heading.append(title_link)

        permalink = lxml.html.Element(
            "a",
            {
                "class": "heading-permalink",
                "href": href,
                "aria-label": f"Permalink to {label} section",
                "title": "Permalink",
            },
        )
        permalink.text = "#"
        copy_button = lxml.html.Element(
            "button",
            {
                "class": "heading-copy",
                "type": "button",
                "data-anchor": target_id,
                "aria-label": f"Copy link to {label} section",
                "title": "Copy link",
            },
        )
        copy_button.text = "Copy"
        heading.append(permalink)
        heading.append(copy_button)


def add_anchor_alias(heading, alias: str, seen: set[str]) -> None:
    if not alias or alias in seen:
        return
    parent = heading.getparent()
    if parent is None:
        return
    marker = lxml.html.Element("span", {"id": alias, "class": "anchor-alias", "aria-hidden": "true"})
    parent.insert(parent.index(heading), marker)
    seen.add(alias)


def canonical_url_key(url: str) -> str | None:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc.lower()
    if host not in LOCALISABLE_HOSTS:
        return None
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(("https", "www.daryllswer.com", path, "", "")).rstrip("/")


def clean_query(query: str) -> str:
    if not query:
        return ""
    kept = []
    for key, value in urllib.parse.parse_qsl(query, keep_blank_values=True):
        if key.lower().startswith("utm_") or key.lower() in TRACKING_QUERY_KEYS:
            continue
        kept.append((key, value))
    return urllib.parse.urlencode(kept, doseq=True)


def local_post_href(current_slug: str, target_slug: str, query: str = "", fragment: str = "") -> str:
    base = "./" if target_slug == current_slug else f"../{target_slug}/"
    if query:
        base += f"?{query}"
    if fragment:
        base += f"#{fragment}"
    return base


def replace_verse_blocks(root) -> None:
    for pre in list(root.xpath(".//pre[contains(concat(' ', normalize-space(@class), ' '), ' wp-block-verse ')]")):
        quote = lxml.html.Element("blockquote", {"class": "archive-note"})
        quote.text = pre.text
        for child in list(pre):
            quote.append(child)
        quote.tail = pre.tail
        pre.getparent().replace(pre, quote)


def wrap_iframes(root) -> None:
    for iframe in list(root.xpath(".//iframe")):
        src = iframe.get("src") or ""
        title = iframe.get("title") or "Embedded media"
        iframe.attrib.pop("width", None)
        iframe.attrib.pop("height", None)
        iframe.attrib.pop("frameborder", None)
        iframe.attrib.pop("scrolling", None)
        iframe.set("loading", "lazy")
        iframe.set("class", "media-frame")

        wrapper = lxml.html.Element("div", {"class": "media-embed"})
        label = lxml.html.Element("p", {"class": "embed-label"})
        label.text = title
        fallback = lxml.html.Element("p", {"class": "embed-fallback"})
        link = lxml.html.Element("a", {"href": src, "target": "_blank", "rel": "noopener noreferrer"})
        link.text = "Open audio player"
        fallback.append(link)

        tail = iframe.tail
        iframe.tail = None
        parent = iframe.getparent()
        parent.replace(iframe, wrapper)
        wrapper.append(label)
        wrapper.append(iframe)
        wrapper.append(fallback)
        wrapper.tail = tail


def rewrite_links(root, current_post: dict, canonical_to_slug: dict[str, str], exact_assets: dict[str, str], keyed_assets: dict[str, str]) -> None:
    current_base = current_post["canonical_url"]
    for anchor in root.xpath(".//a[@href]"):
        href = anchor.get("href") or ""
        if href.startswith("#"):
            continue
        joined = urllib.parse.urljoin(current_base, href)
        joined_key = joined.rstrip("/")
        if joined_key == SHEET_SOURCE_URL.rstrip("/"):
            anchor.set("href", f"../../sheets/{SHEET_SLUG}/visual.html")
            anchor.attrib.pop("target", None)
            anchor.attrib.pop("rel", None)
            continue
        local_asset = local_asset_for(joined, exact_assets, keyed_assets)
        if local_asset:
            anchor.set("href", local_asset)
            anchor.attrib.pop("target", None)
            anchor.attrib.pop("rel", None)
            continue
        parsed = urllib.parse.urlsplit(joined)
        target_key = canonical_url_key(joined)
        target_slug = canonical_to_slug.get(target_key or joined_key)
        if target_slug:
            anchor.set(
                "href",
                local_post_href(
                    current_post["slug"],
                    target_slug,
                    clean_query(parsed.query),
                    parsed.fragment,
                ),
            )
            anchor.attrib.pop("target", None)
            anchor.attrib.pop("rel", None)
            continue
        anchor.set("href", joined)
        parsed = urllib.parse.urlsplit(joined)
        if parsed.scheme in {"http", "https"}:
            anchor.set("target", "_blank")
            anchor.set("rel", "noopener noreferrer")


def rewrite_images(root, current_post: dict, exact_assets: dict[str, str], keyed_assets: dict[str, str]) -> None:
    for image in root.xpath(".//img[@src]"):
        src = urllib.parse.urljoin(current_post["canonical_url"], image.get("src") or "")
        local_asset = local_asset_for(src, exact_assets, keyed_assets)
        if local_asset:
            image.set("src", local_asset)
        image.attrib.pop("srcset", None)
        image.attrib.pop("sizes", None)
        image.attrib.pop("style", None)
        image.set("loading", image.get("loading") or "lazy")
        image.set("decoding", image.get("decoding") or "async")


def remove_unsafe_attrs(root) -> None:
    for element in root.iter():
        for attr in list(element.attrib):
            if attr.lower().startswith("on"):
                del element.attrib[attr]
    for bad in list(root.xpath(".//script|.//style|.//form")):
        bad.drop_tree()


def article_body_html(post: dict, canonical_to_slug: dict[str, str]) -> str:
    bundle = ROOT / post["bundle_path"]
    raw = (bundle / "source" / "rendered-article.html").read_text(encoding="utf-8", errors="replace")
    root = lxml.html.fragment_fromstring(raw, create_parent="div")
    exact_assets, keyed_assets = build_asset_maps(bundle)
    remove_unsafe_attrs(root)
    replace_verse_blocks(root)
    rewrite_images(root, post, exact_assets, keyed_assets)
    rewrite_links(root, post, canonical_to_slug, exact_assets, keyed_assets)
    wrap_iframes(root)
    ensure_heading_ids(root)
    add_heading_permalink_controls(root)
    return "".join(lxml.html.tostring(child, encoding="unicode") for child in root)


def page_shell(
    title: str,
    description: str,
    body: str,
    css_href: str,
    canonical_path: str,
    image_href: str | None = None,
    js_href: str | None = None,
) -> str:
    image_meta = f'\n  <meta property="og:image" content="{html_escape(image_href)}">' if image_href else ""
    script = f'\n  <script src="{html_escape(js_href)}" defer></script>' if js_href else ""
    return f"""<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)}</title>
  <meta name="description" content="{html_escape(description)}">
  <link rel="canonical" href="{html_escape(PAGES_BASE_URL + canonical_path.lstrip('/'))}">
  <meta property="og:title" content="{html_escape(title)}">
  <meta property="og:description" content="{html_escape(description)}">{image_meta}
  <link rel="stylesheet" href="{html_escape(css_href)}">{script}
</head>
<body>
{body}
</body>
</html>
"""


def clean_home_href(prefix: str) -> str:
    return prefix or "./"


def site_header(prefix: str = "") -> str:
    home_href = clean_home_href(prefix)
    return f"""<header class="site-header">
  <a class="brand" href="{home_href}" aria-label="daryllswer.com Archive home">
    <span class="brand-mark">DS</span>
    <span><strong>daryllswer.com</strong><small>Archive</small></span>
  </a>
  <nav class="site-nav" aria-label="Primary">
    <a href="{home_href}">Index</a>
    <a href="https://github.com/daryll-swer/daryllswer.com-archive">Repository</a>
    <a href="https://www.daryllswer.com/">Canonical site</a>
  </nav>
</header>"""


def post_card(post: dict, metadata: dict) -> str:
    bundle = ROOT / post["bundle_path"]
    featured = post.get("featured_image")
    image_html = ""
    if featured and (bundle / featured).exists():
        image_html = (
            f'<a class="post-card-image" href="posts/{html_escape(post["slug"])}/">'
            f'<img src="posts/{html_escape(post["slug"])}/{html_escape(featured)}" alt=""></a>'
        )
    categories = metadata.get("categories") or []
    category_text = ", ".join(c.get("name", "") for c in categories if c.get("name"))
    return f"""<article class="post-card">
  {image_html}
  <div class="post-card-body">
    <p class="meta">{html_escape(format_date(post.get("published")))}{html_escape(" / " + category_text) if category_text else ""}</p>
    <h2><a href="posts/{html_escape(post["slug"])}/">{html_escape(post["title"])}</a></h2>
    <p>{html_escape(post_excerpt(bundle, metadata))}</p>
  </div>
</article>"""


def render_home(posts: list[dict], metadata_by_slug: dict[str, dict]) -> None:
    cards = "\n".join(post_card(post, metadata_by_slug[post["slug"]]) for post in posts)
    body = f"""{site_header()}
<main class="home">
  <section class="home-hero">
    <p class="eyebrow">Public mirror and long-term archive</p>
    <h1>daryllswer.com Archive</h1>
    <p>Network engineering, architecture, IPv6, routing, operations, and related writing mirrored from the canonical WordPress site.</p>
  </section>
  <section class="post-list" aria-label="Archived articles">
    {cards}
  </section>
</main>
<footer class="site-footer">
  <p>Mirrored content follows the repository licensing notes. The WordPress site remains canonical while it is available.</p>
</footer>"""
    write_text(
        OUT / "index.html",
        page_shell(
            "daryllswer.com Archive",
            "Public mirror of daryllswer.com network engineering articles.",
            body,
            "assets/theme.css",
            "",
        ),
    )


def render_post(post: dict, metadata: dict, canonical_to_slug: dict[str, str]) -> None:
    bundle = ROOT / post["bundle_path"]
    out_dir = OUT / "posts" / post["slug"]
    assets_src = bundle / "assets"
    if assets_src.exists():
        shutil.copytree(assets_src, out_dir / "assets", dirs_exist_ok=True)

    featured = post.get("featured_image")
    featured_html = ""
    image_meta = None
    if featured and (out_dir / featured).exists():
        featured_html = f'<img class="featured-image" src="{html_escape(featured)}" alt="">'
        image_meta = PAGES_BASE_URL + f"posts/{post['slug']}/{featured}"
    categories = metadata.get("categories") or []
    category_text = ", ".join(c.get("name", "") for c in categories if c.get("name"))
    body_html = article_body_html(post, canonical_to_slug)
    body = f"""{site_header("../../")}
<main class="article-shell">
  <article class="article">
    <header class="article-header">
      <p class="meta">{html_escape(format_date(post.get("published")))}{html_escape(" / " + category_text) if category_text else ""}</p>
      <h1>{html_escape(post["title"])}</h1>
      <p class="article-summary">{html_escape(post_excerpt(bundle, metadata))}</p>
      {featured_html}
    </header>
    <div class="article-body">
      {body_html}
    </div>
    <footer class="article-footer">
      <p>Canonical source: <a href="{html_escape(post["canonical_url"])}">{html_escape(post["canonical_url"])}</a></p>
      <p>Archive source bundle: <a href="https://github.com/daryll-swer/daryllswer.com-archive/tree/main/{html_escape(post["bundle_path"])}">{html_escape(post["bundle_path"])}</a></p>
    </footer>
  </article>
</main>"""
    write_text(
        out_dir / "index.html",
        page_shell(
            post["title"],
            post_excerpt(bundle, metadata),
            body,
            "../../assets/theme.css",
            f"posts/{post['slug']}/",
            image_meta,
            "../../assets/archive.js",
        ),
    )


def render_sheet_page() -> None:
    source_dir = ROOT / "data" / "sheets" / SHEET_SLUG
    manifest = load_json(source_dir / "manifest.json")
    out_dir = OUT / "sheets" / SHEET_SLUG
    write_text(
        out_dir / "index.html",
        render_workbook_page(
            root=ROOT,
            manifest=manifest,
            sheet_slug=SHEET_SLUG,
            home_href="../../",
            repo_href="https://github.com/daryll-swer/daryllswer.com-archive",
            font_asset_prefix="../../assets/fonts",
        ),
    )
    shutil.copytree(
        source_dir,
        out_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("workbook.html", "legacy-visual-models"),
    )
    font_rewrite_pages = [out_dir / "visual.html"]
    for page in font_rewrite_pages:
        if page.exists():
            text = page.read_text(encoding="utf-8", errors="replace")
            write_text(page, text.replace("../../../assets/fonts/", "../../assets/fonts/"))


def render_css() -> None:
    theme_css = """* { box-sizing: border-box; }
:root {
  color-scheme: light dark;
  --bg: #f7f8fa;
  --surface: #ffffff;
  --surface-alt: #eef3f8;
  --text: #15181d;
  --muted: #5d6875;
  --border: #d8dee7;
  --accent: #0b6f8a;
  --accent-2: #2f7d32;
  --code-bg: #111827;
  --code-text: #f4f7fb;
  --font-body: __FONT_BODY__;
  --font-heading: __FONT_HEADING__;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101418;
    --surface: #171d23;
    --surface-alt: #202832;
    --text: #edf2f7;
    --muted: #a9b4c0;
    --border: #34404d;
    --accent: #6cc7df;
    --accent-2: #8ed18e;
    --code-bg: #070b10;
    --code-text: #f7fafc;
  }
}
html {
  overflow-x: hidden;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-weight: 400;
  line-height: 1.65;
  overflow-x: hidden;
}
a { color: var(--accent); text-decoration-thickness: .08em; text-underline-offset: .18em; }
a:hover { color: var(--accent-2); }
.site-header, .home, .post-card, .site-footer {
  font-family: var(--font-body);
}
.home h1, .post-card h2 {
  font-family: var(--font-heading);
}
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  max-width: 1180px;
  margin: 0 auto;
  padding: 1rem 1.25rem;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: .65rem;
  color: var(--text);
  text-decoration: none;
  min-width: 0;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 2.2rem;
  height: 2.2rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--accent);
  font-family: var(--font-heading);
  font-weight: 800;
}
.brand strong { font-family: var(--font-heading); font-weight: 700; }
.brand small { display: block; color: var(--muted); font-size: .8rem; line-height: 1.1; }
.site-nav { display: flex; gap: .9rem; flex-wrap: wrap; font-size: .95rem; min-width: 0; }
.site-nav a { color: var(--muted); text-decoration: none; }
.home, .article-shell, .sheet-page { max-width: 1180px; margin: 0 auto; padding: 1rem 1.25rem 4rem; }
.home-hero, .sheet-hero {
  padding: 3rem 0 2rem;
  border-top: 1px solid var(--border);
}
.eyebrow, .meta {
  margin: 0 0 .55rem;
  color: var(--muted);
  font-size: .82rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.2; letter-spacing: 0; overflow-wrap: break-word; }
h1, h2, h3, h4, h5, h6 { font-family: var(--font-heading); font-weight: 700; }
h1 { margin: 0 0 1rem; max-width: 900px; font-size: 3.4rem; }
.home-hero p:not(.eyebrow), .sheet-hero p:not(.eyebrow), .article-summary {
  max-width: 760px;
  color: var(--muted);
  font-size: 1.1rem;
  overflow-wrap: break-word;
}
.post-list { display: grid; gap: 1rem; }
.post-card {
  display: grid;
  grid-template-columns: minmax(180px, 280px) minmax(0, 1fr);
  gap: 1rem;
  padding: .9rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-width: 0;
}
.post-card-image { display: block; min-height: 160px; border-radius: 6px; overflow: hidden; background: var(--surface-alt); }
.post-card-image img { width: 100%; height: 100%; object-fit: cover; display: block; }
.post-card-body { min-width: 0; }
.post-card h2 { margin: .15rem 0 .55rem; font-size: 1.55rem; }
.post-card h2 a { color: var(--text); text-decoration: none; }
.post-card p { margin: 0; color: var(--muted); overflow-wrap: break-word; }
.article { max-width: 860px; margin: 0 auto; }
.article-header { padding: 2rem 0 1.5rem; border-top: 1px solid var(--border); }
.featured-image {
  display: block;
  width: 100%;
  height: auto;
  max-height: 520px;
  object-fit: cover;
  margin: 1.5rem 0 0;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.article-body {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: clamp(1rem, 4vw, 2rem);
  min-width: 0;
  overflow-wrap: break-word;
}
.article-body h2,
.article-body h3,
.article-body h4,
.article-body h5,
.article-body h6 {
  scroll-margin-top: 1.25rem;
}
.article-body h2 { margin-top: 2.2rem; padding-top: .3rem; }
.article-body h3 { margin-top: 1.8rem; }
.heading-title-link {
  color: inherit;
  text-decoration: none;
}
.heading-title-link:hover,
.heading-title-link:focus {
  color: var(--accent);
  text-decoration: underline;
}
.heading-permalink,
.heading-copy {
  display: inline-flex;
  align-items: center;
  min-height: 1.35rem;
  margin-left: .45rem;
  vertical-align: .08em;
  font-family: var(--font-body);
  font-size: .72rem;
  line-height: 1;
}
.heading-permalink {
  color: var(--muted);
  text-decoration: none;
}
.heading-copy {
  padding: .16rem .35rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-alt);
  color: var(--muted);
  cursor: pointer;
}
.heading-permalink:hover,
.heading-permalink:focus,
.heading-copy:hover,
.heading-copy:focus {
  color: var(--accent);
  border-color: var(--accent);
}
.heading-copy.copied {
  color: var(--accent-2);
  border-color: var(--accent-2);
}
.anchor-alias {
  display: block;
  position: relative;
  top: -1rem;
  width: 0;
  height: 0;
  overflow: hidden;
}
.article-body img {
  display: block;
  max-width: 100% !important;
  height: auto !important;
  margin: 0 auto;
  border-radius: 6px;
}
.article-body figure, .article-body .wp-block-image {
  max-width: 100%;
  margin: 1.75rem auto;
  text-align: center;
}
.article-body figcaption, .wp-element-caption {
  margin-top: .65rem;
  color: var(--muted);
  font-size: .92rem;
}
.article-body blockquote, .archive-note {
  margin: 1.5rem 0;
  padding: 1rem 1.15rem;
  border-left: 4px solid var(--accent);
  background: var(--surface-alt);
  border-radius: 0 8px 8px 0;
}
pre {
  overflow-x: auto;
  padding: 1rem;
  border-radius: 8px;
  background: var(--code-bg);
  color: var(--code-text);
  line-height: 1.5;
}
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.media-embed {
  margin: 1.5rem 0;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-alt);
  overflow: hidden;
}
.embed-label { margin: 0 0 .5rem; font-weight: 700; }
.media-frame { display: block; width: 100%; height: 52px; min-height: 52px; border: 0; background: var(--surface); }
.embed-fallback { margin: .65rem 0 0; font-size: .92rem; }
.article-footer, .site-footer {
  max-width: 1180px;
  margin: 2rem auto;
  padding: 1rem 1.25rem;
  color: var(--muted);
  border-top: 1px solid var(--border);
  font-size: .92rem;
}
.button-row { display: flex; gap: .75rem; flex-wrap: wrap; }
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.5rem;
  padding: .5rem .85rem;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  font-weight: 700;
}
.button.secondary { background: var(--surface); color: var(--accent); border: 1px solid var(--border); }
.table-wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: .75rem; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: .85rem; text-transform: uppercase; }
@media (max-width: 760px) {
  .site-header { align-items: flex-start; flex-direction: column; }
  .post-card { grid-template-columns: 1fr; }
  .post-card-image { aspect-ratio: 16 / 9; }
  h1 { font-size: 2.2rem; }
  .post-card h2 { font-size: 1.3rem; }
}
@media (max-width: 420px) {
  .site-header, .home, .article-shell, .sheet-page, .article-footer, .site-footer {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  .home-hero, .sheet-hero { padding-top: 2rem; }
  h1 { font-size: 2rem; }
}
"""
    theme_css = theme_css.replace("__FONT_BODY__", FONT_BODY_STACK)
    theme_css = theme_css.replace("__FONT_HEADING__", FONT_HEADING_STACK)
    write_text(
        OUT / "assets" / "theme.css",
        font_face_css("fonts") + "\n" + wordpress_palette_css() + "\n" + theme_css,
    )


def render_js() -> None:
    write_text(
        OUT / "assets" / "archive.js",
        """(() => {
  function sectionUrl(anchor) {
    const url = new URL(window.location.href);
    url.hash = anchor;
    return url.toString();
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".heading-copy");
    if (!button) {
      return;
    }
    const anchor = button.getAttribute("data-anchor");
    if (!anchor) {
      return;
    }
    const text = sectionUrl(anchor);
    try {
      await navigator.clipboard.writeText(text);
      button.classList.add("copied");
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.classList.remove("copied");
        button.textContent = "Copy";
      }, 1600);
    } catch (_) {
      window.location.hash = anchor;
    }
  });
})();
""",
    )


def main() -> int:
    archive = load_json(ROOT / "archive-manifest.json")
    posts = archive.get("posts", [])
    metadata_by_slug = {
        post["slug"]: load_json(ROOT / post["bundle_path"] / "metadata.json")
        for post in posts
    }
    canonical_to_slug = {
        key: post["slug"]
        for post in posts
        if (key := canonical_url_key(post.get("canonical_url") or ""))
    }

    clean_generated_site()
    render_css()
    render_js()
    copy_font_assets(ROOT, OUT / "assets" / "fonts")
    render_home(posts, metadata_by_slug)
    render_sheet_page()
    for post in posts:
        render_post(post, metadata_by_slug[post["slug"]], canonical_to_slug)
    write_text(OUT / ".nojekyll", "")
    print(f"site generated: {OUT / 'index.html'}")
    print(f"posts generated: {len(posts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
