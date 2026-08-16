import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DRIFT = load_script("canonical_drift", "check-canonical-drift.py")
RECONCILE = load_script("reconcile_canonical_drift", "reconcile-canonical-drift.py")


def iso(day: str) -> str:
    return f"{day}T00:00:00Z"


def summary(post_id: int, url: str, slug: str) -> dict:
    return {
        "id": post_id,
        "slug": slug,
        "canonical_url": url,
        "title": slug,
        "modified": "2026-01-01T00:00:00",
        "featured_image_url": None,
        "content_text_sha256": hashlib.sha256(slug.encode()).hexdigest(),
        "content_media_urls": [],
    }


class CanonicalRetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_roots = {
            DRIFT: (DRIFT.ROOT, DRIFT.STATUS_PATH, DRIFT.REPORT_PATH),
            RECONCILE: RECONCILE.ROOT,
        }
        DRIFT.ROOT = self.root
        DRIFT.STATUS_PATH = self.root / "archive-status.json"
        DRIFT.REPORT_PATH = self.root / "docs" / "CANONICAL_DRIFT.md"
        RECONCILE.ROOT = self.root
        (self.root / "docs").mkdir()

    def tearDown(self):
        DRIFT.ROOT, DRIFT.STATUS_PATH, DRIFT.REPORT_PATH = self.old_roots[DRIFT]
        RECONCILE.ROOT = self.old_roots[RECONCILE]
        self.temp.cleanup()

    def write_archive(self, posts):
        (self.root / "archive-manifest.json").write_text(
            json.dumps({"post_count": len(posts), "posts": posts}, indent=2), encoding="utf-8"
        )

    def write_bundle(self, post):
        bundle = self.root / post["bundle_path"]
        (bundle / "source").mkdir(parents=True)
        (bundle / "assets").mkdir()
        metadata = {
            "id": post["id"],
            "slug": post["slug"],
            "canonical_url": post["canonical_url"],
            "title": post["title"],
            "modified": post["modified"],
            "featured_image": None,
        }
        (bundle / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (bundle / "source" / "rendered-article.html").write_text(post["slug"], encoding="utf-8")
        (bundle / "assets" / "manifest.json").write_text(json.dumps({"assets": []}), encoding="utf-8")
        return bundle

    def test_id_classification_separates_new_missing_and_relocation(self):
        archived = [
            {**summary(1, "https://www.daryllswer.com/old/", "old"), "bundle_path": "content/posts/2020-01-01-old"},
            {**summary(2, "https://www.daryllswer.com/missing/", "missing"), "bundle_path": "content/posts/2020-01-02-missing"},
        ]
        for post in archived:
            self.write_bundle(post)
        self.write_archive(archived)
        live = [
            summary(1, "https://www.daryllswer.com/new/", "new"),
            summary(3, "https://www.daryllswer.com/created/", "created"),
        ]
        drift = DRIFT.compare_drift(live)
        self.assertEqual(drift["new_ids"], [3])
        self.assertEqual(drift["missing_ids"], [2])
        self.assertEqual(drift["relocated_posts"][0]["id"], 1)
        self.assertEqual(drift["relocated_posts"][0]["from"], "https://www.daryllswer.com/old")

    def test_two_confirmations_require_seven_days_and_select_no_more_than_one_new_post(self):
        missing = {**summary(2, "https://www.daryllswer.com/missing/", "missing"), "bundle_path": "content/posts/2020-01-02-missing"}
        self.write_bundle(missing)
        self.write_archive([missing])
        status = DRIFT.default_status(iso("2026-01-01"))
        evidence = {
            "passed": True,
            "rest": {"status": 404, "passed": True},
            "canonical_route": {"status": 410, "passed": True},
        }
        drift = {
            "live_post_count": 0,
            "archived_post_count": 1,
            "missing_posts": [missing],
            "missing_ids": [2],
            "new_posts": [],
            "new_ids": [],
            "relocated_posts": [],
            "changed_posts": [],
        }
        candidate = DRIFT.update_retirement_candidate(status, drift, evidence, iso("2026-01-01"))
        self.assertEqual(candidate["confirmation_count"], 1)
        candidate = DRIFT.update_retirement_candidate(status, drift, evidence, iso("2026-01-07"))
        self.assertEqual(candidate["confirmation_count"], 1)
        candidate = DRIFT.update_retirement_candidate(status, drift, evidence, iso("2026-01-08"))
        self.assertEqual(candidate["confirmation_count"], 2)
        plan = DRIFT.build_action_plan(status, drift, iso("2026-01-08"), evidence)
        self.assertEqual(plan["action"], "retire")

        new_drift = {
            **drift,
            "missing_posts": [],
            "missing_ids": [],
            "new_ids": [4, 5],
            "new_posts": [summary(4, "https://www.daryllswer.com/four/", "four"), summary(5, "https://www.daryllswer.com/five/", "five")],
        }
        status["retirement_candidates"] = []
        new_plan = DRIFT.build_action_plan(status, new_drift, iso("2026-01-08"), None)
        self.assertEqual(new_plan["action"], "none")
        self.assertEqual(new_plan["sync_posts"], [])

    def test_reconcile_retirement_removes_one_bundle_and_clears_candidate(self):
        post = {**summary(2, "https://www.daryllswer.com/missing/", "missing"), "bundle_path": "content/posts/2020-01-02-missing"}
        self.write_bundle(post)
        manifest = {"post_count": 1, "posts": [post]}
        self.write_archive([post])
        status = DRIFT.default_status(iso("2026-01-01"))
        candidate = {
            "id": 2,
            "slug": "missing",
            "canonical_url": post["canonical_url"],
            "bundle_path": post["bundle_path"],
            "healthy_confirmations": [{"observed_at": iso("2026-01-01")}, {"observed_at": iso("2026-01-08")}],
            "confirmation_count": 2,
        }
        status["retirement_candidates"] = [candidate]
        (self.root / "archive-status.json").write_text(json.dumps(status), encoding="utf-8")
        plan = {
            "version": 1,
            "canonical_healthy": True,
            "archive_manifest_sha256": hashlib.sha256((self.root / "archive-manifest.json").read_bytes()).hexdigest(),
            "drift": {"live_post_count": 0, "archived_post_count": 1, "missing_posts": [post], "missing_ids": [2], "new_ids": [], "relocated_posts": [], "changed_posts": []},
            "retirement": {
                "candidate": candidate,
                "eligible": True,
                "endpoint_evidence": {
                    "passed": True,
                    "rest": {"status": 404, "passed": True},
                    "canonical_route": {"status": 410, "passed": True},
                },
            },
            "action": "retire",
        }
        RECONCILE.retire_one(plan, manifest, status)
        self.assertFalse((self.root / post["bundle_path"]).exists())
        result = json.loads((self.root / "archive-manifest.json").read_text())
        self.assertEqual(result["post_count"], 0)
        self.assertNotIn("retired_routes", result)
        updated_status = json.loads((self.root / "archive-status.json").read_text())
        self.assertEqual(updated_status["retirement_candidates"], [])

    def test_reconcile_rejects_unsafe_bundle_path(self):
        with self.assertRaises(ValueError):
            RECONCILE.safe_bundle_path("content/posts/../../outside")

    def test_reconcile_rolls_back_bundle_and_json_when_status_commit_fails(self):
        post = {**summary(2, "https://www.daryllswer.com/missing/", "missing"), "bundle_path": "content/posts/2020-01-02-missing"}
        bundle = self.write_bundle(post)
        self.write_archive([post])
        status = DRIFT.default_status(iso("2026-01-01"))
        candidate = {
            "id": 2,
            "slug": "missing",
            "canonical_url": post["canonical_url"],
            "bundle_path": post["bundle_path"],
            "healthy_confirmations": [{"observed_at": iso("2026-01-01")}, {"observed_at": iso("2026-01-08")}],
            "confirmation_count": 2,
        }
        status["retirement_candidates"] = [candidate]
        (self.root / "archive-status.json").write_text(json.dumps(status), encoding="utf-8")
        original_manifest = (self.root / "archive-manifest.json").read_bytes()
        original_status = (self.root / "archive-status.json").read_bytes()
        plan = {
            "version": 1,
            "canonical_healthy": True,
            "archive_manifest_sha256": hashlib.sha256(original_manifest).hexdigest(),
            "drift": {"live_post_count": 0, "archived_post_count": 1, "missing_posts": [post], "missing_ids": [2], "new_ids": [], "relocated_posts": [], "changed_posts": []},
            "retirement": {
                "candidate": candidate,
                "eligible": True,
                "endpoint_evidence": {
                    "passed": True,
                    "rest": {"status": 404, "passed": True},
                    "canonical_route": {"status": 410, "passed": True},
                },
            },
            "action": "retire",
        }
        with mock.patch.object(RECONCILE, "atomic_write_json", side_effect=[None, OSError("simulated status failure")]):
            with self.assertRaises(OSError):
                RECONCILE.retire_one(plan, json.loads(original_manifest), json.loads(original_status))
        self.assertTrue(bundle.is_dir())
        self.assertEqual((self.root / "archive-manifest.json").read_bytes(), original_manifest)
        self.assertEqual((self.root / "archive-status.json").read_bytes(), original_status)


if __name__ == "__main__":
    unittest.main()
