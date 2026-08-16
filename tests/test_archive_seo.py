import datetime as dt
import importlib.util
import json
import sys
import tempfile
import types
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock


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


DRIFT = load_script("archive_seo_drift", "check-canonical-drift.py")
MONITOR = load_script("archive_seo_monitor", "external_source_monitor.py")
RENDER = load_script("archive_seo_render", "render-site.py")
MANAGE = load_script("archive_seo_manage", "manage-archive-seo.py")


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"ok"):
        self.status = status
        self.headers = headers or {}
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.body[:limit]

    def getcode(self):
        return self.status


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def open(self, request, timeout=45):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


def iso(day: int) -> str:
    return dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=day)


class ArchiveSeoTests(unittest.TestCase):
    def test_frozen_ds_promotes_seo_once_and_recovery_preserves_archive_discovery(self):
        status = DRIFT.default_status("2026-01-01T00:00:00Z")
        status["failure"]["first_failure_at"] = "2026-01-01T00:00:00Z"
        for count in range(8):
            DRIFT.record_failure(status, f"2026-02-{count + 1:02d}T00:00:00Z", "URLError", "offline")
        self.assertEqual(status["state"], "frozen_archive")
        self.assertEqual(status["seo_state"], "archive_discovery")
        self.assertIsNotNone(status["seo_activated_at"])
        DRIFT.reset_failure(status, "2026-03-01T00:00:00Z")
        self.assertEqual(status["state"], "healthy")
        self.assertEqual(status["seo_state"], "archive_discovery")

    def test_owner_verified_ds_recovery_restores_source_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "archive-status.json"
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status.update({
                "state": "frozen_archive",
                "frozen": True,
                "seo_state": "archive_discovery",
                "seo_activated_at": "2026-02-01T00:00:00Z",
            })
            status_path.write_text(json.dumps(status), encoding="utf-8")
            fake_drift = types.SimpleNamespace(
                request_posts=lambda _status, fresh: ([{"id": 1}], {}, False),
            )
            old_status_path = MANAGE.STATUS_PATH
            try:
                MANAGE.STATUS_PATH = status_path
                with mock.patch.object(MANAGE, "load_module", return_value=fake_drift):
                    MANAGE.resume_ds()
            finally:
                MANAGE.STATUS_PATH = old_status_path
            recovered = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(recovered["state"], "healthy")
            self.assertEqual(recovered["seo_state"], "source_primary")
            self.assertIsNone(recovered["seo_activated_at"])

    def test_external_source_health_gates_swer_network_fallback(self):
        post = {"id": 5324}
        metadata = {"rights": {"external_fallback": True}}
        healthy = {"seo_state": "archive_discovery", "external_sources": {"5324": {"state": "healthy", "promotion_blocked": False}}}
        unavailable = {"seo_state": "archive_discovery", "external_sources": {"5324": {"state": "source_unavailable", "promotion_blocked": False}}}
        frozen = {"seo_state": "archive_discovery", "external_sources": {"5324": {"state": "frozen_source", "promotion_blocked": False}}}
        blocked = {"seo_state": "archive_discovery", "external_sources": {"5324": {"state": "degraded", "promotion_blocked": True}}}
        self.assertFalse(RENDER.post_is_seo_eligible(post, metadata, healthy))
        self.assertFalse(RENDER.post_is_seo_eligible(post, metadata, unavailable))
        self.assertTrue(RENDER.post_is_seo_eligible(post, metadata, frozen))
        self.assertFalse(RENDER.post_is_seo_eligible(post, metadata, blocked))

    def test_blocked_external_status_does_not_count_or_promote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "archive-status.json"
            registry_path = root / "rights-registry.json"
            report_path = root / "report.md"
            status_path.write_text(json.dumps(DRIFT.default_status("2026-01-01T00:00:00Z")), encoding="utf-8")
            registry_path.write_text(json.dumps({"5324": {"external_fallback": True, "original_article_url": "https://example.com/original"}}), encoding="utf-8")
            opener = FakeOpener(error=urllib.error.HTTPError("https://example.com/original", 403, "blocked", {}, None))
            with mock.patch.object(MONITOR, "REPORT_PATH", report_path):
                result = MONITOR.run(status_path=status_path, registry_path=registry_path, now=dt.datetime(2026, 1, 8, tzinfo=dt.timezone.utc), opener=opener)
            source = result["status"]["external_sources"]["5324"]
            self.assertEqual(source["state"], "degraded")
            self.assertTrue(source["promotion_blocked"])
            self.assertEqual(source["consecutive_failures"], 0)
            self.assertEqual(opener.calls, 1)

    def test_countable_external_failure_can_freeze_without_promotion_block(self):
        item = MONITOR.empty_source({"post_id": 5324, "url": "https://example.com/original"})
        for day in range(8):
            MONITOR.apply_observation(
                item,
                {"state": MONITOR.DEGRADED, "countable_failure": True, "promotion_blocked": False},
                (iso(day * 7)).isoformat().replace("+00:00", "Z"),
            )
        self.assertEqual(item["state"], MONITOR.FROZEN_SOURCE)
        self.assertFalse(item["promotion_blocked"])

    def test_targeted_external_check_keeps_other_registered_source_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status["external_sources"] = {
                "99": MONITOR.empty_source({"post_id": 99, "url": "https://example.com/other"})
            }
            status_path = root / "archive-status.json"
            registry_path = root / "rights-registry.json"
            report_path = root / "report.md"
            status_path.write_text(json.dumps(status), encoding="utf-8")
            registry_path.write_text(json.dumps({
                "99": {"external_fallback": True, "original_article_url": "https://example.com/other"},
                "5324": {"external_fallback": True, "original_article_url": "https://example.com/original"},
            }), encoding="utf-8")
            opener = FakeOpener(response=FakeResponse())
            with mock.patch.object(MONITOR, "REPORT_PATH", report_path):
                result = MONITOR.run(
                    status_path=status_path,
                    registry_path=registry_path,
                    force=True,
                    post_ids={5324},
                    now=dt.datetime(2026, 1, 8, tzinfo=dt.timezone.utc),
                    opener=opener,
                )
            self.assertEqual(opener.calls, 1)
            self.assertEqual(set(result["status"]["external_sources"]), {"99", "5324"})

    def test_frozen_external_source_makes_no_network_request_without_force(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status["external_sources"] = {
                "5324": {
                    "post_id": 5324,
                    "url": "https://example.com/original",
                    "state": "frozen_source",
                    "frozen": True,
                    "promotion_blocked": False,
                    "consecutive_failures": 8,
                    "last_checked_at": "2026-01-01T00:00:00Z",
                    "last_success_at": None,
                    "first_failure_at": "2025-12-01T00:00:00Z",
                    "last_failure_at": "2026-01-01T00:00:00Z",
                    "last_observation": None,
                }
            }
            status_path = root / "archive-status.json"
            registry_path = root / "rights-registry.json"
            report_path = root / "report.md"
            status_path.write_text(json.dumps(status), encoding="utf-8")
            registry_path.write_text(json.dumps({"5324": {"external_fallback": True, "original_article_url": "https://example.com/original"}}), encoding="utf-8")
            opener = FakeOpener(response=FakeResponse())
            with mock.patch.object(MONITOR, "REPORT_PATH", report_path):
                result = MONITOR.run(status_path=status_path, registry_path=registry_path, now=dt.datetime(2026, 1, 8, tzinfo=dt.timezone.utc), opener=opener)
            self.assertEqual(opener.calls, 0)
            self.assertEqual(result["skipped_post_ids"], ["5324"])

    def test_frozen_ds_check_makes_no_canonical_request(self):
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "archive-status.json"
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status.update({"state": "frozen_archive", "frozen": True, "seo_state": "archive_discovery", "seo_activated_at": "2026-01-01T00:00:00Z"})
            status_path.write_text(json.dumps(status), encoding="utf-8")
            old_path = DRIFT.STATUS_PATH
            old_argv = sys.argv
            try:
                DRIFT.STATUS_PATH = status_path
                sys.argv = ["check-canonical-drift.py"]
                with mock.patch.object(DRIFT, "request_posts", side_effect=AssertionError("network request made")):
                    self.assertEqual(DRIFT.main(), 0)
            finally:
                DRIFT.STATUS_PATH = old_path
                sys.argv = old_argv

    def test_generated_normal_seo_metadata_and_local_snapshot_urls(self):
        homepage = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<meta name="robots" content="index,follow">', homepage)
        self.assertIn('<meta name="google-site-verification" content="xEHOYZuv2ksSHn7MsBoCv9bkRPlwSFgyGoMtcn6lQIY">', homepage)
        self.assertEqual(homepage.count("google-site-verification"), 1)
        article = (ROOT / "docs" / "posts" / "bgp-router-id-structuring-in-ipv6-native-networks" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex,follow">', article)
        self.assertNotIn("google-site-verification", article)
        snapshot = next((ROOT / "docs" / "sheets" / "as141253-ipv6-architecture-example" / "html").glob("*.html"))
        snapshot_html = snapshot.read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex,nofollow">', snapshot_html)
        self.assertIn('https://daryll-swer.github.io/daryllswer.com-archive/sheets/', snapshot_html)
        self.assertNotIn('<meta property="og:url" content="https://docs.google.com/', snapshot_html)
        self.assertNotIn('http-equiv="refresh"', snapshot_html.lower())
        self.assertIn("http-equiv=\"Content-Security-Policy\"", snapshot_html)
        self.assertIn("script-src 'none'", snapshot_html)

    def test_normal_sitemap_and_robots_are_parseable_and_feed_is_absent(self):
        sitemap = (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(sitemap.count("<loc>"), 1)
        self.assertIn("https://daryll-swer.github.io/daryllswer.com-archive/", sitemap)
        robots = (ROOT / "docs" / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Sitemap: https://daryll-swer.github.io/daryllswer.com-archive/sitemap.xml", robots)
        self.assertFalse((ROOT / "docs" / "feed.xml").exists())

    def test_canonical_drift_report_uses_only_the_supported_recovery_path(self):
        report = DRIFT.render_report(DRIFT.default_status("2026-01-01T00:00:00Z"), None, "test")
        self.assertIn("scripts/manage-archive-seo.py resume-ds --owner-verified", report)
        self.assertNotIn("Edit `archive-status.json`", report)

    def test_archive_feed_uses_local_absolute_urls_and_stable_id_guid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "content" / "posts" / "2026-01-01-example"
            (bundle / "source").mkdir(parents=True)
            (bundle / "source" / "rendered-article.html").write_text('<p>Body <a href="../other/">local</a><img src="assets/image.png"></p>', encoding="utf-8")
            (bundle / "index.md").write_text("# Example\n\nExcerpt text.", encoding="utf-8")
            metadata = {"categories": [{"name": "Networking"}], "excerpt": "Excerpt text."}
            (bundle / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            post = {"id": 77, "slug": "example", "title": "Example", "canonical_url": "https://www.daryllswer.com/example/", "published": "2026-01-01T00:00:00+00:00", "modified": "2026-01-02T00:00:00+00:00", "bundle_path": "content/posts/2026-01-01-example"}
            old_root, old_out = RENDER.ROOT, RENDER.OUT
            try:
                RENDER.ROOT = root
                RENDER.OUT = root / "docs"
                status = {"seo_state": "archive_discovery", "external_sources": {}}
                RENDER.render_sitemap([post], {"example": metadata}, status)
                RENDER.render_feed([post], {"example": metadata}, {}, status)
                feed = ET.fromstring((root / "docs" / "feed.xml").read_bytes())
                item = feed.find("channel/item")
                self.assertIsNotNone(item)
                self.assertEqual(item.findtext("guid"), "urn:daryllswer-com-archive:wordpress-post:77")
                self.assertEqual(item.find("guid").get("isPermaLink"), "false")
                body = item.find("{http://purl.org/rss/1.0/modules/content/}encoded").text or ""
                self.assertNotIn('href="../', body)
                self.assertIn("https://daryll-swer.github.io/daryllswer.com-archive/posts/", body)
                self.assertIn("https://daryll-swer.github.io/daryllswer.com-archive/", item.findtext("link"))
            finally:
                RENDER.ROOT, RENDER.OUT = old_root, old_out

    def test_archive_discovery_excludes_healthy_external_repost_from_sitemap_and_feed(self):
        archive = json.loads((ROOT / "archive-manifest.json").read_text(encoding="utf-8"))
        posts = archive["posts"]
        metadata = {
            post["slug"]: json.loads((ROOT / post["bundle_path"] / "metadata.json").read_text(encoding="utf-8"))
            for post in posts
        }
        canonical_map = RENDER.canonical_post_route_map(posts)
        status = {
            "seo_state": "archive_discovery",
            "seo_activated_at": "2026-08-01T00:00:00Z",
            "external_sources": {"5324": {"state": "healthy", "promotion_blocked": False}},
        }
        with tempfile.TemporaryDirectory() as directory:
            old_out = RENDER.OUT
            try:
                RENDER.OUT = Path(directory) / "docs"
                RENDER.render_sitemap(posts, metadata, status)
                RENDER.render_feed(posts, metadata, canonical_map, status)
                sitemap = ET.fromstring((RENDER.OUT / "sitemap.xml").read_bytes())
                locations = [item.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc") for item in sitemap]
                self.assertNotIn(
                    "https://daryll-swer.github.io/daryllswer.com-archive/posts/bgp-router-id-structuring-in-ipv6-native-networks/",
                    locations,
                )
                self.assertIn("https://daryll-swer.github.io/daryllswer.com-archive/sheets/as141253-ipv6-architecture-example/", locations)
                feed = ET.fromstring((RENDER.OUT / "feed.xml").read_bytes())
                ids = {item.findtext("guid") for item in feed.findall("channel/item")}
                self.assertNotIn("urn:daryllswer-com-archive:wordpress-post:5324", ids)
                self.assertTrue(feed.findtext("channel/lastBuildDate"))
                self.assertEqual(
                    feed.findtext("channel/image/url"),
                    "https://daryll-swer.github.io/daryllswer.com-archive/assets/brand/01_DS_Favicon_Dark_Mode-512.png",
                )
                status["external_sources"]["5324"]["state"] = "frozen_source"
                RENDER.render_sitemap(posts, metadata, status)
                RENDER.render_feed(posts, metadata, canonical_map, status)
                feed = ET.fromstring((RENDER.OUT / "feed.xml").read_bytes())
                bgp = next(
                    item for item in feed.findall("channel/item")
                    if item.findtext("guid") == "urn:daryllswer-com-archive:wordpress-post:5324"
                )
                body = bgp.find("{http://purl.org/rss/1.0/modules/content/}encoded").text or ""
                self.assertIn("https://www.swernetworks.com/blog/bgp-router-id-structuring-in-ipv6-native-networks/", body)
                self.assertIn("Swer Networks", body)
            finally:
                RENDER.OUT = old_out


if __name__ == "__main__":
    unittest.main()
