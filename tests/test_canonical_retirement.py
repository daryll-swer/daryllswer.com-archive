import hashlib
import importlib.util
import json
import shutil
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
        if post.get("canonical_rendered_content_sha256"):
            metadata["source"] = {
                "canonical_rendered_content_sha256": post["canonical_rendered_content_sha256"],
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

    def test_pending_retirement_forces_a_fresh_collection_fetch(self):
        self.assertFalse(DRIFT.needs_fresh_collection({}))
        self.assertTrue(DRIFT.needs_fresh_collection({}, forced=True))
        self.assertTrue(DRIFT.needs_fresh_collection({"retirement_candidates": [{"id": 1}]}))

    def test_content_fingerprint_and_all_changed_posts_are_in_one_sync_plan(self):
        post_one = {
            **summary(1, "https://www.daryllswer.com/one/", "one"),
            "canonical_rendered_content_sha256": "original-one",
            "bundle_path": "content/posts/2020-01-01-one",
        }
        post_two = {
            **summary(2, "https://www.daryllswer.com/two/", "two"),
            "canonical_rendered_content_sha256": "original-two",
            "bundle_path": "content/posts/2020-01-02-two",
        }
        for post in [post_one, post_two]:
            self.write_bundle(post)
        self.write_archive([post_one, post_two])
        live = [
            {**summary(1, "https://www.daryllswer.com/one/", "one"), "canonical_rendered_content_sha256": "changed-one"},
            {**summary(2, "https://www.daryllswer.com/two/", "two"), "canonical_rendered_content_sha256": "changed-two"},
        ]
        drift = DRIFT.compare_drift(live)
        self.assertEqual([item["id"] for item in drift["changed_posts"]], [1, 2])
        plan = DRIFT.build_action_plan(DRIFT.default_status(iso("2026-01-08")), drift, iso("2026-01-08"))
        self.assertEqual(plan["version"], 2)
        self.assertEqual(plan["action"], "sync")
        self.assertEqual([item["id"] for item in plan["update_posts"]], [1, 2])
        self.assertEqual(plan["sync_posts"], [])

    def test_clean_comparison_backfills_legacy_content_fingerprints_only(self):
        post = {
            **summary(1, "https://www.daryllswer.com/one/", "one"),
            "bundle_path": "content/posts/2020-01-01-one",
        }
        self.write_bundle(post)
        self.write_archive([post])
        metadata_path = self.root / post["bundle_path"] / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["source"] = {}
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        live = [{**summary(1, post["canonical_url"], post["slug"]), "canonical_rendered_content_sha256": "a" * 64}]
        clean_drift = DRIFT.compare_drift(live)
        self.assertEqual(DRIFT.backfill_canonical_content_fingerprints(clean_drift, live), [1])
        metadata = json.loads((self.root / post["bundle_path"] / "metadata.json").read_text())
        self.assertEqual(metadata["source"]["canonical_rendered_content_sha256"], "a" * 64)

        changed_drift = {**clean_drift, "changed_posts": [{"id": 1}]}
        live[0]["canonical_rendered_content_sha256"] = "b" * 64
        self.assertEqual(DRIFT.backfill_canonical_content_fingerprints(changed_drift, live), [])
        metadata = json.loads((self.root / post["bundle_path"] / "metadata.json").read_text())
        self.assertEqual(metadata["source"]["canonical_rendered_content_sha256"], "a" * 64)

    def test_sync_targets_requires_the_complete_changed_post_batch(self):
        posts = [
            {**summary(1, "https://www.daryllswer.com/one/", "one"), "bundle_path": "content/posts/2020-01-01-one"},
            {**summary(2, "https://www.daryllswer.com/two/", "two"), "bundle_path": "content/posts/2020-01-02-two"},
        ]
        for post in posts:
            self.write_bundle(post)
        self.write_archive(posts)
        changed = []
        for post in posts:
            changed.append({
                "id": post["id"],
                "slug": post["slug"],
                "canonical_url": post["canonical_url"],
                "expected": {"id": post["id"], "slug": post["slug"]},
                "fields": [{"field": "modified"}],
            })
        plan = {
            "version": 2,
            "drift": {"new_ids": [], "missing_ids": [], "relocated_posts": [], "changed_posts": changed},
            "sync_posts": [],
            "update_posts": changed,
        }
        new_posts, updates = RECONCILE.sync_targets(plan, {"posts": posts})
        self.assertEqual(new_posts, [])
        self.assertEqual([item["id"] for item in updates], [1, 2])
        plan["update_posts"] = [changed[0]]
        with self.assertRaises(ValueError):
            RECONCILE.sync_targets(plan, {"posts": posts})

    def test_staged_sync_rolls_back_all_replaced_bundles_when_manifest_write_fails(self):
        posts = [
            {**summary(1, "https://www.daryllswer.com/one/", "one"), "bundle_path": "content/posts/2020-01-01-one"},
            {**summary(2, "https://www.daryllswer.com/two/", "two"), "bundle_path": "content/posts/2020-01-02-two"},
        ]
        originals = [self.write_bundle(post) for post in posts]
        self.write_archive(posts)
        original_manifest = (self.root / "archive-manifest.json").read_bytes()
        original_markers = [(bundle / "source" / "rendered-article.html").read_text(encoding="utf-8") for bundle in originals]

        stage = Path(tempfile.mkdtemp())
        try:
            staged_posts = []
            for post in posts:
                staged = dict(post)
                staged["title"] = f"updated-{post['title']}"
                staged_posts.append(staged)
                bundle = stage / staged["bundle_path"]
                (bundle / "source").mkdir(parents=True)
                (bundle / "metadata.json").write_text(
                    json.dumps({"id": staged["id"], "canonical_url": staged["canonical_url"]}), encoding="utf-8"
                )
                (bundle / "source" / "rendered-article.html").write_text(f"updated-{staged['slug']}", encoding="utf-8")
            (stage / "archive-manifest.json").write_text(json.dumps({"post_count": 2, "posts": staged_posts}), encoding="utf-8")

            with mock.patch.object(RECONCILE, "atomic_write_json", side_effect=OSError("simulated manifest failure")):
                with self.assertRaises(OSError):
                    RECONCILE.apply_staged_sync(stage, {"posts": posts}, [], [{"id": 1}, {"id": 2}])

            self.assertEqual((self.root / "archive-manifest.json").read_bytes(), original_manifest)
            self.assertEqual(
                [(bundle / "source" / "rendered-article.html").read_text(encoding="utf-8") for bundle in originals],
                original_markers,
            )
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def test_staged_sync_failure_leaves_live_bundles_unchanged(self):
        post = {**summary(1, "https://www.daryllswer.com/one/", "one"), "bundle_path": "content/posts/2020-01-01-one"}
        bundle = self.write_bundle(post)
        marker = bundle / "assets" / "existing-media.png"
        marker.write_bytes(b"existing media")
        self.write_archive([post])
        changed = {
            "id": 1,
            "slug": "one",
            "canonical_url": post["canonical_url"],
            "expected": {"id": 1, "slug": "one", "canonical_url": post["canonical_url"]},
            "fields": [{"field": "modified"}],
        }
        plan = {
            "version": 2,
            "drift": {"new_ids": [], "missing_ids": [], "relocated_posts": [], "changed_posts": [changed]},
            "sync_posts": [],
            "update_posts": [changed],
        }
        original_manifest = (self.root / "archive-manifest.json").read_bytes()
        original_article = (bundle / "source" / "rendered-article.html").read_bytes()
        with mock.patch.object(RECONCILE.subprocess, "run", return_value=mock.Mock(returncode=1)):
            with self.assertRaisesRegex(RuntimeError, "staged automatic sync failed"):
                RECONCILE.stage_sync(plan, {"posts": [post]})
        self.assertEqual((self.root / "archive-manifest.json").read_bytes(), original_manifest)
        self.assertEqual((bundle / "source" / "rendered-article.html").read_bytes(), original_article)
        self.assertEqual(marker.read_bytes(), b"existing media")

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
