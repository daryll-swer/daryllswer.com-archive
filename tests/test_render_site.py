import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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


RENDER = load_script("render_site_open_graph", "render-site.py")
VALIDATOR = load_script("validate_site_open_graph", "validate-mirror.py")


class RenderSiteOpenGraphTests(unittest.TestCase):
    def test_reader_shell_has_skip_link_and_sitemap_navigation(self):
        page = RENDER.page_shell("Article", "Description", RENDER.site_header("../") + '<main id="main-content">Body</main>', "theme.css", "posts/example/")
        self.assertIn('href="#main-content">Skip to content</a>', page)
        self.assertIn('href="../sitemap.xml">Sitemap</a>', page)
        self.assertIn('name="robots" content="noindex,follow"', page)

    def test_article_body_sanitizes_source_before_adding_trusted_copy_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "content" / "posts" / "2026-01-01-example"
            (bundle / "source").mkdir(parents=True)
            (bundle / "source" / "rendered-article.html").write_text(
                '<h2 id="h-routing">Routing <button class="heading-copy" '
                'data-anchor="forged" aria-label="Forged" onclick="alert(1)">fake</button></h2>'
                '<table><caption>Routes</caption><thead><tr><th scope="col">Prefix</th></tr></thead>'
                '<tbody><tr><td>2001:db8::/32</td></tr></tbody></table>'
                '<script>alert(1)</script>',
                encoding="utf-8",
            )
            (bundle / "assets").mkdir()
            (bundle / "assets" / "manifest.json").write_text('{"assets": []}', encoding="utf-8")
            post = {
                "id": 77,
                "slug": "example",
                "canonical_url": "https://www.daryllswer.com/example/",
                "bundle_path": "content/posts/2026-01-01-example",
            }
            rights = RENDER.resolve_rights(77, post["canonical_url"], {})
            old_root = RENDER.ROOT
            try:
                RENDER.ROOT = root
                output = RENDER.article_body_html(post, {}, rights)
            finally:
                RENDER.ROOT = old_root

            parsed = RENDER.lxml.html.fragment_fromstring(output, create_parent="div")
            buttons = parsed.xpath('.//button[@class="heading-copy"]')
            self.assertEqual(len(buttons), 1)
            self.assertEqual(buttons[0].get("type"), "button")
            self.assertEqual(buttons[0].get("data-anchor"), "routing")
            self.assertEqual(buttons[0].get("aria-label"), "Copy link to Routing fake section")
            self.assertEqual(buttons[0].get("title"), "Copy link")
            self.assertEqual(parsed.xpath('.//h2[@id="h-routing"]'), [parsed.xpath('.//h2')[0]])
            self.assertFalse(parsed.xpath(".//script|.//*[@onclick]"))
            regions = parsed.xpath('.//div[@class="table-wrap"][@role="region"][@tabindex="0"][@aria-label="Scrollable table: Routes"]')
            self.assertEqual(len(regions), 1)
            self.assertEqual(len(regions[0].xpath("./table")), 1)

    def test_raw_evidence_head_directives_are_removed_but_source_is_untouched(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            page_path = Path(directory) / "evidence.html"
            original = ('<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=https://evil.test">'
                        '<meta name="robots" content="index"><base href="https://evil.test/"><script>location="https://evil.test"</script>'
                        '</head><body onload="location=\'https://evil.test\'"><a href="jav&#x61;script:alert(1)">unsafe</a>'
                        '<a href="https://evil.test" target="_blank">external</a><form action="https://evil.test">Evidence</form></body></html>')
            page_path.write_text(original, encoding="utf-8")
            RENDER.rewrite_generated_html_seo(page_path, "https://archive.test/evidence.html", "noindex,nofollow", raw_snapshot=True)
            output = page_path.read_text(encoding="utf-8")
            self.assertNotIn('http-equiv="refresh"', output)
            self.assertNotIn("<base", output)
            self.assertNotIn('name="robots" content="index"', output)
            self.assertNotIn("<script", output)
            self.assertNotIn("<form", output)
            self.assertNotIn("onload", output)
            self.assertNotIn("javascript:", output)
            self.assertIn('rel="noopener noreferrer"', output)
            self.assertIn("default-src 'none'", output)
            self.assertIn("Evidence", output)

    def test_homepage_open_graph_url_is_archive_local(self):
        page = RENDER.page_shell(
            "Archive",
            "Archive description",
            "<main>Home</main>",
            "assets/theme.css",
            "",
        )
        self.assertIn(
            '<meta property="og:url" content="https://daryll-swer.github.io/daryllswer.com-archive/">',
            page,
        )
        self.assertNotIn("daryllswer.com/", page)
        self.assertNotIn("swernetworks.com/", page)

    def test_article_open_graph_url_matches_archive_route(self):
        page = RENDER.page_shell(
            "Article",
            "Article description",
            "<main>Article</main>",
            "../../assets/theme.css",
            "posts/example-article/",
        )
        self.assertIn(
            '<meta property="og:url" content="https://daryll-swer.github.io/daryllswer.com-archive/posts/example-article/">',
            page,
        )
        self.assertNotIn("daryllswer.com/", page)
        self.assertNotIn("swernetworks.com/", page)

    def test_validator_rejects_non_archive_open_graph_url(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            page_path = Path(directory) / "index.html"
            page_path.write_text(
                '<html><head><meta property="og:url" content="https://www.daryllswer.com/example/"></head></html>',
                encoding="utf-8",
            )
            errors = []
            VALIDATOR.validate_pages_open_graph_url(
                page_path,
                "https://daryll-swer.github.io/daryllswer.com-archive/example/",
                errors,
            )
            self.assertTrue(any("Open Graph URL must be exactly" in error for error in errors))

    def test_validator_rejects_daryllswer_canonical_url(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            page_path = Path(directory) / "index.html"
            page_path.write_text(
                '<html><head><link rel="canonical" href="https://www.daryllswer.com/example/"></head></html>',
                encoding="utf-8",
            )
            errors = []
            VALIDATOR.validate_pages_canonical_url(
                page_path,
                "https://daryll-swer.github.io/daryllswer.com-archive/example/",
                errors,
            )
            self.assertTrue(any("canonical URL must be exactly" in error for error in errors))

    def test_validator_rejects_old_homepage_h1(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            page_path = Path(directory) / "index.html"
            page_path.write_text(
                '<main class="home"><h1>daryllswer.com Archive</h1></main>',
                encoding="utf-8",
            )
            errors = []
            VALIDATOR.validate_pages_home_h1(
                page_path,
                VALIDATOR.PAGES_HOME_TITLE,
                errors,
            )
            self.assertTrue(any("homepage H1 must be exactly" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
