import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RENDER = load_script("rights_rendering", "render-site.py")
POLICY = load_script("rights_rendering_policy", "rights_policy.py")


class RightsRenderingTests(unittest.TestCase):
    def write_bundle(self, root: Path, post: dict, body: str, rights: dict) -> None:
        bundle = root / post["bundle_path"]
        (bundle / "source").mkdir(parents=True)
        (bundle / "source" / "rendered-article.html").write_text(body, encoding="utf-8")
        (bundle / "assets").mkdir()
        (bundle / "assets" / "manifest.json").write_text(json.dumps({"assets": []}), encoding="utf-8")
        (bundle / "index.md").write_text("# Example\n\n" + POLICY.rights_notice_markdown(rights), encoding="utf-8")

    def test_pages_and_feed_render_one_default_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            post = {
                "id": 17,
                "slug": "example",
                "title": "Example",
                "canonical_url": "https://archive.example/posts/example/",
                "published": "2026-01-01T00:00:00+00:00",
                "modified": "2026-01-02T00:00:00+00:00",
                "bundle_path": "content/posts/2026-01-01-example",
                "featured_image": None,
            }
            rights = POLICY.resolve_rights(post["id"], post["canonical_url"], {})
            self.write_bundle(root, post, "<p>Body</p>", rights)
            old_root, old_out = RENDER.ROOT, RENDER.OUT
            try:
                RENDER.ROOT = root
                RENDER.OUT = root / "docs"
                RENDER.render_post(post, {"rights": rights, "categories": [], "excerpt": "Example"}, {}, {})
                page = RENDER.OUT / "posts" / "example" / "index.html"
                page_doc = RENDER.lxml.html.parse(str(page))
                self.assertEqual(POLICY.html_notice_count(page_doc, rights), 1)
                self.assertIn("Daryll Swer", page.read_text(encoding="utf-8"))

                RENDER.render_feed([post], {"example": {"rights": rights, "categories": [], "excerpt": "Example"}}, {}, {"seo_state": "archive_discovery"})
                feed = ET.fromstring((RENDER.OUT / "feed.xml").read_bytes())
                body = feed.find("channel/item/{http://purl.org/rss/1.0/modules/content/}encoded").text or ""
                body_doc = RENDER.lxml.html.fragment_fromstring(body, create_parent="div")
                self.assertEqual(POLICY.html_notice_count(body_doc, rights), 1)
            finally:
                RENDER.ROOT, RENDER.OUT = old_root, old_out

    def test_notice_counter_counts_one_marked_block_inside_wrappers(self):
        rights = POLICY.resolve_rights(17, "https://archive.example/posts/default/", {})
        document = POLICY.lxml.html.fragment_fromstring(
            "<article><div><section>" + POLICY.rights_notice_html(rights) + "</section></div></article>",
            create_parent="div",
        )
        self.assertEqual(POLICY.html_notice_count(document, rights), 1)

    def test_existing_original_source_notice_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            post = {
                "id": 18,
                "slug": "repost",
                "title": "Repost",
                "canonical_url": "https://archive.example/posts/repost/",
                "published": "2026-01-01T00:00:00+00:00",
                "modified": "2026-01-02T00:00:00+00:00",
                "bundle_path": "content/posts/2026-01-01-repost",
                "featured_image": None,
            }
            rights = {
                "rights_holder": "Example Publisher",
                "copyright_year": 2026,
                "rights_status": "proprietary/all-rights-reserved",
                "notice_path": "LICENSES/EXAMPLE-PUBLISHER-NOTICE.txt",
                "original_article_url": "https://origin.example/articles/repost/",
                "publisher": "Example Publisher",
                "scope": "article-text",
                "media_rights": "separate attribution/right notices",
                "external_fallback": True,
            }
            body = (
                '<blockquote><p>Originally published at '
                '<a href="https://origin.example/articles/repost/">the source</a>.</p>'
                '<p><strong>Copyright:</strong> © 2026 Example Publisher. All rights reserved.</p>'
                '<p>Media remains subject to separate attribution or rights notices.</p></blockquote>'
            )
            self.write_bundle(root, post, body, rights)
            old_root, old_out = RENDER.ROOT, RENDER.OUT
            try:
                RENDER.ROOT = root
                RENDER.OUT = root / "docs"
                RENDER.render_post(post, {"rights": rights, "categories": [], "excerpt": "Repost"}, {}, {})
                page = RENDER.OUT / "posts" / "repost" / "index.html"
                html = page.read_text(encoding="utf-8")
                self.assertEqual(html.count('data-archive-rights-notice="true"'), 0)
                self.assertEqual(POLICY.html_notice_count(RENDER.lxml.html.parse(str(page)), rights), 1)
            finally:
                RENDER.ROOT, RENDER.OUT = old_root, old_out


if __name__ == "__main__":
    unittest.main()
