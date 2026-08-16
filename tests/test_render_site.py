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


if __name__ == "__main__":
    unittest.main()
