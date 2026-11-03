import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


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

    def write_rights_registry(self, post_id=5324):
        registry_path = self.root / "content" / "rights-registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps({
                str(post_id): {
                    "copyright_year": 2026,
                    "media_rights": "separate attribution/right notices",
                    "notice_path": "LICENSES/EXAMPLE-PROPRIETARY-NOTICE.txt",
                    "original_article_url": "https://origin.example/articles/example/",
                    "publisher": "Example Publisher",
                    "rights_holder": "Example Publisher",
                    "rights_status": "proprietary/all-rights-reserved",
                    "scope": "article-text",
                    "external_fallback": True,
                }
            }),
            encoding="utf-8",
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
        plan = DRIFT.build_action_plan(status, drift, iso("2026-01-08"), evidence, media_audit={"status": "complete", "distinct_urls": 0, "checked_urls": 0, "changed_assets": 0, "bytes_checked": 0, "failures": [], "elapsed_seconds": 0})
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
        plan = DRIFT.build_action_plan(DRIFT.default_status(iso("2026-01-08")), drift, iso("2026-01-08"), media_audit={"status": "complete", "distinct_urls": 0, "checked_urls": 0, "changed_assets": 0, "bytes_checked": 0, "failures": [], "elapsed_seconds": 0})
        self.assertEqual(plan["version"], 3)
        self.assertEqual(plan["action"], "sync")
        self.assertEqual([item["id"] for item in plan["update_posts"]], [1, 2])
        self.assertEqual(plan["sync_posts"], [])

    def test_checker_audits_media_after_rest_304(self):
        self.write_archive([])
        status = DRIFT.default_status(iso("2026-01-01"))
        status["last_live_post_summaries"] = [summary(1, "https://www.daryllswer.com/one/", "one")]
        DRIFT.STATUS_PATH.write_text(json.dumps(status), encoding="utf-8")
        drift = {
            "live_post_count": 0, "archived_post_count": 0, "new_ids": [], "missing_ids": [],
            "new_posts": [], "missing_posts": [], "relocated_posts": [], "new_urls": [],
            "missing_urls": [], "changed_posts": [],
        }
        args = type("Args", (), {"dry_run": True, "force": False, "fresh": False, "action_plan": None, "result": None, "audit_media": True})()
        with mock.patch.object(DRIFT, "parse_args", return_value=args), \
             mock.patch.object(DRIFT, "request_posts", return_value=(None, {}, True)), \
             mock.patch.object(DRIFT, "compare_drift", return_value=drift), \
             mock.patch.object(DRIFT, "audit_media", return_value=([], {"status": "complete", "distinct_urls": 2, "checked_urls": 2, "changed_assets": 0, "bytes_checked": 10, "failures": [], "elapsed_seconds": 1.0})) as audit:
            self.assertEqual(DRIFT.main(), 0)
        audit.assert_called_once()

    def test_forced_frozen_diagnostic_never_audits_media(self):
        self.write_archive([])
        status = DRIFT.default_status(iso("2026-01-01"))
        status["state"] = "frozen_archive"
        status["frozen"] = True
        DRIFT.STATUS_PATH.write_text(json.dumps(status), encoding="utf-8")
        args = type("Args", (), {"dry_run": False, "force": True, "fresh": False, "action_plan": None, "result": None, "audit_media": True})()
        with mock.patch.object(DRIFT, "parse_args", return_value=args), \
             mock.patch.object(DRIFT, "request_posts", return_value=([], {}, False)), \
             mock.patch.object(DRIFT, "audit_media") as audit:
            self.assertEqual(DRIFT.main(), 0)
        audit.assert_not_called()

    def test_reconciler_rejects_malformed_or_incomplete_v3_plans(self):
        valid = {
            "version": 3, "action": "none", "media_updates": [],
            "media_audit": {"status": "complete", "distinct_urls": 0, "checked_urls": 0, "changed_assets": 0, "bytes_checked": 0, "failures": [], "elapsed_seconds": 0},
        }
        RECONCILE.validate_action_plan(valid)
        with self.assertRaisesRegex(ValueError, "schema validation"):
            RECONCILE.validate_action_plan({**valid, "media_updates": None})
        with self.assertRaisesRegex(ValueError, "schema validation"):
            RECONCILE.validate_action_plan({"version": 3, "action": "none", "media_updates": []})
        incomplete = {**valid, "action": "sync", "media_audit": {**valid["media_audit"], "status": "incomplete"}}
        incomplete["media_updates"] = [{
            "source_url": "https://www.daryllswer.com/wp-content/uploads/a.png", "post_id": 1,
            "asset_path": "content/posts/x/assets/a.png", "old_sha256": "a" * 64, "new_sha256": "b" * 64,
        }]
        with self.assertRaisesRegex(ValueError, "incomplete media audit"):
            RECONCILE.validate_action_plan(incomplete)

    def test_ineligible_drift_keeps_media_observation_but_clears_actionable_updates(self):
        self.write_archive([])
        update = {
            "source_url": "https://www.daryllswer.com/wp-content/uploads/a.png",
            "post_id": 7,
            "asset_path": "content/posts/2026-01-01-post/assets/a.png",
            "old_sha256": "a" * 64,
            "new_sha256": "b" * 64,
        }
        drift = {
            "live_post_count": 0, "archived_post_count": 1,
            "new_ids": [], "missing_ids": [7], "new_posts": [],
            "missing_posts": [], "relocated_posts": [], "changed_posts": [],
        }
        audit = {"status": "complete", "distinct_urls": 1, "checked_urls": 1, "changed_assets": 1, "bytes_checked": 10, "failures": [], "elapsed_seconds": 1}
        plan = DRIFT.build_action_plan(DRIFT.default_status(iso("2026-01-01")), drift, iso("2026-01-01"), media_updates=[update], media_audit=audit)
        self.assertEqual(plan["action"], "none")
        self.assertEqual(plan["media_updates"], [])
        self.assertEqual(plan["media_audit"]["changed_assets"], 1)

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
            (stage / ".reconcile-baseline.json").write_text(json.dumps({
                "archive_manifest_sha256": hashlib.sha256(original_manifest).hexdigest(),
                "bundles": {
                    str(post["id"]): {"bundle_path": post["bundle_path"], "sha256": RECONCILE.bundle_sha256(bundle)}
                    for post, bundle in zip(posts, originals)
                },
            }), encoding="utf-8")

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
        self.write_rights_registry()
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

    def test_media_only_staged_sync_commits_only_planned_bytes_and_sets_freshness(self):
        url = "https://www.daryllswer.com/wp-content/uploads/image.png"
        post = {**summary(1, "https://www.daryllswer.com/example/", "example"), "title": "Example", "bundle_path": "content/posts/2026-01-01-example"}
        bundle = self.write_bundle(post)
        old_bytes, new_bytes = b"old-image-bytes", b"new-image-bytes"
        other_url = "https://www.daryllswer.com/wp-content/uploads/other.png"
        other_old, other_new = b"other-old", b"other-new"
        asset_path = f"{post['bundle_path']}/assets/image.png"
        other_path = f"{post['bundle_path']}/assets/other.png"
        local_asset = self.root / asset_path
        local_asset.write_bytes(old_bytes)
        (self.root / other_path).write_bytes(other_old)
        old_hash = hashlib.sha256(old_bytes).hexdigest()
        new_hash = hashlib.sha256(new_bytes).hexdigest()
        other_hash = hashlib.sha256(other_old).hexdigest()
        (bundle / "assets" / "manifest.json").write_text(json.dumps({"post_id": 1, "assets": [
            {"source_url": url, "local_path": asset_path, "role": "inline", "sha256": old_hash},
            {"source_url": other_url, "local_path": other_path, "role": "inline", "sha256": other_hash},
        ]}), encoding="utf-8")
        prior_metadata = json.loads((bundle / "metadata.json").read_text())
        prior_metadata["published"] = "2026-01-01T00:00:00"
        prior_metadata["archive_media_updated_at"] = "2026-01-10T00:00:00+00:00"
        (bundle / "metadata.json").write_text(json.dumps(prior_metadata), encoding="utf-8")
        self.write_archive([post])
        original_manifest = (self.root / "archive-manifest.json").read_bytes()
        self.write_rights_registry(9999)
        changed = {
            "id": 1, "slug": "example", "canonical_url": post["canonical_url"], "media_only": True,
            "expected": {"id": 1, "slug": "example", "title": "example", "canonical_url": post["canonical_url"], "modified": post["modified"]},
            "fields": [],
        }
        plan = {
            "media_audit": {"status": "complete"},
            "media_updates": [{"source_url": url, "post_id": 1, "asset_path": asset_path, "old_sha256": old_hash, "new_sha256": new_hash}],
            "drift": {"new_ids": [], "missing_ids": [], "relocated_posts": [], "changed_posts": [changed]},
            "sync_posts": [], "update_posts": [changed],
        }
        self.write_rights_registry(1)

        unplanned_change = False
        def fake_sync(command, cwd, env, check):
            stage_root = Path(env["ARCHIVE_ROOT"])
            staged_bundle = stage_root / post["bundle_path"]
            staged_bundle.mkdir(parents=True, exist_ok=True)
            (staged_bundle / "assets").mkdir(exist_ok=True)
            (staged_bundle / "assets" / "image.png").write_bytes(new_bytes)
            other_bytes = other_new if unplanned_change else other_old
            (staged_bundle / "assets" / "other.png").write_bytes(other_bytes)
            staged_other_hash = hashlib.sha256(other_bytes).hexdigest()
            (staged_bundle / "assets" / "manifest.json").write_text(json.dumps({"post_id": 1, "assets": [
                {"source_url": url, "local_path": asset_path, "role": "inline", "sha256": new_hash},
                {"source_url": other_url, "local_path": other_path, "role": "inline", "sha256": staged_other_hash},
            ]}), encoding="utf-8")
            metadata = {**prior_metadata, "rights": RECONCILE.resolve_rights(1, post["canonical_url"], {"1": json.loads((self.root / "content/rights-registry.json").read_text())["1"]})}
            metadata["source"] = {"canonical_rendered_content_sha256": summary(1, post["canonical_url"], "example").get("canonical_rendered_content_sha256")}
            (staged_bundle / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            (stage_root / "archive-manifest.json").write_text(json.dumps({"post_count": 1, "posts": [post]}), encoding="utf-8")
            return mock.Mock(returncode=0)

        with mock.patch.object(RECONCILE.subprocess, "run", side_effect=fake_sync):
            stage, _, updates = RECONCILE.stage_sync(plan, {"posts": [post]})
        try:
            self.assertEqual(updates, [changed])
            staged_bundle = stage / post["bundle_path"]
            self.assertEqual((staged_bundle / "assets/image.png").read_bytes(), new_bytes)
            staged_metadata = json.loads((staged_bundle / "metadata.json").read_text())
            self.assertEqual(staged_metadata["published"], "2026-01-01T00:00:00")
            self.assertNotEqual(staged_metadata["archive_media_updated_at"], "2026-01-10T00:00:00+00:00")
            self.assertEqual(local_asset.read_bytes(), old_bytes)
            self.assertEqual((self.root / other_path).read_bytes(), other_old)
            (self.root / other_path).write_bytes(other_new)
            try:
                with self.assertRaisesRegex(ValueError, "target bundle changed while synchronization was staged"):
                    RECONCILE.apply_staged_sync(stage, {"posts": [post]}, [], [changed])
                self.assertEqual(local_asset.read_bytes(), old_bytes)
                self.assertEqual((self.root / "archive-manifest.json").read_bytes(), original_manifest)
            finally:
                (self.root / other_path).write_bytes(other_old)
            unplanned_change = True
            with mock.patch.object(RECONCILE.subprocess, "run", side_effect=fake_sync):
                with self.assertRaisesRegex(RuntimeError, "unplanned staged media byte change"):
                    RECONCILE.stage_sync(plan, {"posts": [post]})
            unplanned_change = False
            bad_hash_plan = {**plan, "media_updates": [{**plan["media_updates"][0], "new_sha256": "c" * 64}]}
            with mock.patch.object(RECONCILE.subprocess, "run", side_effect=fake_sync):
                with self.assertRaisesRegex(RuntimeError, "staged media bytes do not match planned hash"):
                    RECONCILE.stage_sync(bad_hash_plan, {"posts": [post]})
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def test_staged_sync_copies_rights_registry_before_public_sync(self):
        post = {**summary(5324, "https://www.daryllswer.com/bgp-router-id-structuring-in-ipv6-native-networks/", "bgp"), "bundle_path": "content/posts/2026-06-04-bgp"}
        self.write_bundle(post)
        self.write_archive([post])
        self.write_rights_registry(5324)
        changed = {
            "id": 5324,
            "slug": "bgp",
            "canonical_url": post["canonical_url"],
            "expected": {"id": 5324, "slug": "bgp"},
            "fields": [{"field": "modified"}],
        }
        plan = {
            "version": 2,
            "drift": {"new_ids": [], "missing_ids": [], "relocated_posts": [], "changed_posts": [changed]},
            "sync_posts": [],
            "update_posts": [changed],
        }

        def fake_sync(command, cwd, env, check):
            stage = Path(env["ARCHIVE_ROOT"])
            staged_registry = stage / "content" / "rights-registry.json"
            self.assertTrue(staged_registry.is_file())
            rights = json.loads(staged_registry.read_text(encoding="utf-8"))["5324"]
            bundle = stage / post["bundle_path"]
            (bundle / "source").mkdir(parents=True)
            (bundle / "assets").mkdir(parents=True)
            (bundle / "assets" / "manifest.json").write_text(json.dumps({"post_id": 5324, "assets": []}), encoding="utf-8")
            (bundle / "metadata.json").write_text(
                json.dumps({"id": 5324, "slug": "bgp", "canonical_url": post["canonical_url"], "rights": rights}),
                encoding="utf-8",
            )
            (stage / "archive-manifest.json").write_text(
                json.dumps({"post_count": 1, "posts": [post]}), encoding="utf-8"
            )
            return mock.Mock(returncode=0)

        with mock.patch.object(RECONCILE.subprocess, "run", side_effect=fake_sync):
            stage, new_posts, updates = RECONCILE.stage_sync(plan, {"posts": [post]})
        try:
            self.assertEqual(new_posts, [])
            self.assertEqual([item["id"] for item in updates], [5324])
            self.assertTrue((stage / "content" / "rights-registry.json").is_file())
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def test_staged_sync_applies_default_rights_when_registry_has_no_exception(self):
        post = {**summary(1, "https://archive.example/one/", "one"), "bundle_path": "content/posts/2026-01-01-one"}
        prior_bundle = self.write_bundle(post)
        prior_metadata_path = prior_bundle / "metadata.json"
        prior_metadata = json.loads(prior_metadata_path.read_text())
        prior_metadata["archive_media_updated_at"] = "2026-02-03T04:05:06+00:00"
        prior_metadata_path.write_text(json.dumps(prior_metadata), encoding="utf-8")
        self.write_archive([post])
        registry_path = self.root / "content" / "rights-registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text("{}", encoding="utf-8")
        changed = {
            "id": 1,
            "slug": "one",
            "canonical_url": post["canonical_url"],
            "expected": {"id": 1, "slug": "one"},
            "fields": [{"field": "modified"}],
        }
        plan = {
            "version": 2,
            "drift": {"new_ids": [], "missing_ids": [], "relocated_posts": [], "changed_posts": [changed]},
            "sync_posts": [],
            "update_posts": [changed],
        }

        def fake_sync(command, cwd, env, check):
            stage = Path(env["ARCHIVE_ROOT"])
            bundle = stage / post["bundle_path"]
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle / "assets").mkdir(exist_ok=True)
            (bundle / "assets" / "manifest.json").write_text(json.dumps({"post_id": 1, "assets": []}), encoding="utf-8")
            rights = RECONCILE.resolve_rights(1, post["canonical_url"], {})
            (bundle / "metadata.json").write_text(
                json.dumps({"id": 1, "slug": "one", "canonical_url": post["canonical_url"], "rights": rights}),
                encoding="utf-8",
            )
            (stage / "archive-manifest.json").write_text(
                json.dumps({"post_count": 1, "posts": [post]}), encoding="utf-8"
            )
            return mock.Mock(returncode=0)

        with mock.patch.object(RECONCILE.subprocess, "run", side_effect=fake_sync):
            stage, new_posts, updates = RECONCILE.stage_sync(plan, {"posts": [post]})
        try:
            staged_rights = json.loads((stage / post["bundle_path"] / "metadata.json").read_text())["rights"]
            self.assertEqual(staged_rights["rights_holder"], "Daryll Swer")
            self.assertEqual(staged_rights["copyright_year"], 2026)
            self.assertEqual(staged_rights["notice_path"], "LICENSES/DARYLL-SWER-PROPRIETARY-CONTENT-NOTICE.txt")
            staged_metadata = json.loads((stage / post["bundle_path"] / "metadata.json").read_text())
            self.assertEqual(staged_metadata["archive_media_updated_at"], "2026-02-03T04:05:06+00:00")
            self.assertEqual(new_posts, [])
            self.assertEqual([item["id"] for item in updates], [1])
        finally:
            shutil.rmtree(stage, ignore_errors=True)

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
            "version": 3,
            "media_audit": {"status": "complete"},
            "media_updates": [],
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

    def test_reconcile_retirement_removes_matching_rights_registry_entry(self):
        post = {**summary(5324, "https://www.swernetworks.com/blog/bgp-router-id-structuring-in-ipv6-native-networks/", "bgp"), "bundle_path": "content/posts/2026-06-04-bgp"}
        self.write_bundle(post)
        self.write_archive([post])
        self.write_rights_registry(5324)
        status = DRIFT.default_status(iso("2026-01-01"))
        candidate = {
            "id": 5324,
            "slug": "bgp",
            "canonical_url": post["canonical_url"],
            "bundle_path": post["bundle_path"],
            "healthy_confirmations": [{"observed_at": iso("2026-01-01")}, {"observed_at": iso("2026-01-08")}],
            "confirmation_count": 2,
        }
        status["retirement_candidates"] = [candidate]
        status["external_sources"] = {
            "5324": {
                "post_id": 5324,
                "url": "https://www.swernetworks.com/blog/bgp-router-id-structuring-in-ipv6-native-networks/",
                "state": "healthy",
            }
        }
        (self.root / "archive-status.json").write_text(json.dumps(status), encoding="utf-8")
        original_manifest = (self.root / "archive-manifest.json").read_bytes()
        plan = {
            "version": 3,
            "media_audit": {"status": "complete"},
            "media_updates": [],
            "canonical_healthy": True,
            "archive_manifest_sha256": hashlib.sha256(original_manifest).hexdigest(),
            "drift": {"live_post_count": 0, "archived_post_count": 1, "missing_posts": [post], "missing_ids": [5324], "new_ids": [], "relocated_posts": [], "changed_posts": []},
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
        RECONCILE.retire_one(plan, json.loads(original_manifest), json.loads((self.root / "archive-status.json").read_text()))
        self.assertEqual(json.loads((self.root / "content" / "rights-registry.json").read_text()), {})
        updated_status = json.loads((self.root / "archive-status.json").read_text())
        self.assertNotIn("5324", updated_status["external_sources"])

    def test_reconcile_retirement_rolls_back_rights_registry_when_commit_fails(self):
        post = {**summary(5324, "https://www.swernetworks.com/blog/bgp-router-id-structuring-in-ipv6-native-networks/", "bgp"), "bundle_path": "content/posts/2026-06-04-bgp"}
        bundle = self.write_bundle(post)
        self.write_archive([post])
        self.write_rights_registry(5324)
        status = DRIFT.default_status(iso("2026-01-01"))
        candidate = {
            "id": 5324,
            "slug": "bgp",
            "canonical_url": post["canonical_url"],
            "bundle_path": post["bundle_path"],
            "healthy_confirmations": [{"observed_at": iso("2026-01-01")}, {"observed_at": iso("2026-01-08")}],
            "confirmation_count": 2,
        }
        status["retirement_candidates"] = [candidate]
        status_path = self.root / "archive-status.json"
        status_path.write_text(json.dumps(status), encoding="utf-8")
        manifest_path = self.root / "archive-manifest.json"
        registry_path = self.root / "content" / "rights-registry.json"
        original_manifest = manifest_path.read_bytes()
        original_status = status_path.read_bytes()
        original_registry = registry_path.read_bytes()
        plan = {
            "version": 3,
            "media_audit": {"status": "complete"},
            "media_updates": [],
            "canonical_healthy": True,
            "archive_manifest_sha256": hashlib.sha256(original_manifest).hexdigest(),
            "drift": {"live_post_count": 0, "archived_post_count": 1, "missing_posts": [post], "missing_ids": [5324], "new_ids": [], "relocated_posts": [], "changed_posts": []},
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
        with mock.patch.object(RECONCILE, "atomic_write_json", side_effect=[None, None, OSError("simulated rights registry failure")]):
            with self.assertRaises(OSError):
                RECONCILE.retire_one(plan, json.loads(original_manifest), json.loads(original_status))
        self.assertTrue(bundle.is_dir())
        self.assertEqual(manifest_path.read_bytes(), original_manifest)
        self.assertEqual(status_path.read_bytes(), original_status)
        self.assertEqual(registry_path.read_bytes(), original_registry)

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
            "version": 3,
            "media_audit": {"status": "complete"},
            "media_updates": [],
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
