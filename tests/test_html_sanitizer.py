import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("html_sanitizer", SCRIPTS / "html_sanitizer.py")
SANITIZER = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(SANITIZER)


class ArticleSanitizerTests(unittest.TestCase):
    def test_preserves_article_structure_colour_classes_ids_and_local_media(self):
        source = (
            '<h1 id="h-article-title">Article title</h1>'
            '<h2 id="h-routing"><span id="alias-routing"></span>Routing</h2>'
            '<p class="has-inline-color has-vivid-red-color" style="color:#cf2e2e">Text</p>'
            '<mark style="background-color:#ffff00;position:fixed">Highlighted</mark>'
            '<table><thead><tr><th scope="col">Prefix</th></tr></thead>'
            '<tbody><tr><td>2001:db8::/32</td></tr></tbody>'
            '<tfoot><tr><td>Reserved</td></tr></tfoot></table>'
            '<dl><dt>Protocol</dt><dd>IPv6</dd></dl>'
            '<a href="#h-routing" aria-label="Permalink to routing section">#</a>'
            '<span id="alias-routing-2" aria-hidden="true"></span>'
            '<figure><img src="../assets/diagram.png" alt="Network diagram"></figure>'
            '<p>Copyright 2026 Daryll Swer. All rights reserved.</p>'
        )
        output = SANITIZER.sanitize_article_html(source)
        for expected in (
            'id="h-article-title"', 'id="h-routing"', 'id="alias-routing"', 'has-vivid-red-color',
            "color:#cf2e2e", "<table>", 'scope="col"', "2001:db8::/32",
            "background-color:#ffff00", "Highlighted", "<tfoot>", "<dl>", "<dt>", "<dd>",
            'aria-label="Permalink to routing section"', 'aria-hidden="true"',
            'src="../assets/diagram.png"', 'alt="Network diagram"',
            "Copyright 2026 Daryll Swer",
        ):
            self.assertIn(expected, output)

    def test_removes_active_content_events_and_encoded_executable_urls(self):
        source = (
            '<script>alert(1)</script><svg><foreignObject><img src=x onerror=alert(1)>'
            '</foreignObject></svg><p onclick="alert(1)" onfocus="x">Safe</p>'
            '<a href="jav&#x61;script:alert(1)">bad</a>'
            '<img src="data:text/html,<script>alert(1)</script>" onerror="x">'
            '<iframe srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;" src="https://evil.test/"></iframe>'
            '<form><input value="x"></form><meta http-equiv="refresh" content="0;url=https://evil.test">'
        )
        output = SANITIZER.sanitize_article_html(source)
        for forbidden in ("<script", "<svg", "foreignObject", "onclick", "onfocus", "javascript:", "data:text/html", "srcdoc", "<iframe", "<form", "<input", "<meta"):
            self.assertNotIn(forbidden, output.lower())
        self.assertIn("Safe", output)

    def test_media_frames_become_descriptive_outbound_links_in_layout_wrapper(self):
        source = (
            '<iframe title="Blubrry Podcast Player" src="https://packetpushers.net/?powerpress_embed=53518-podcast&amp;powerpress_player=mediaelement-audio"></iframe>'
            '<iframe title="Unreviewed" src="https://evil.test/embed"></iframe>'
        )
        output = SANITIZER.sanitize_article_html(source)
        self.assertIn("Open Blubrry Podcast Player", output)
        self.assertIn('href="https://packetpushers.net/?powerpress_embed=53518-podcast&amp;powerpress_player=mediaelement-audio"', output)
        self.assertIn('class="media-embed"', output)
        self.assertIn("Unreviewed", output)
        self.assertIn("https://evil.test/embed", output)
        self.assertNotIn("<iframe", output)

    def test_root_level_text_is_not_lost(self):
        self.assertTrue(SANITIZER.sanitize_article_html("Leading text <p>body</p>Trailing text").startswith("Leading text"))
        output = SANITIZER.sanitize_article_html("Use &lt;script&gt; literally")
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>", output)


if __name__ == "__main__":
    unittest.main()
