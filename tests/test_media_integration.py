import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RENDER = load_script("media_integration_render", "render-site.py")
VALIDATOR = load_script("media_integration_validator", "validate-mirror.py")
CHECKER = load_script("media_integration_workflow_checker", "check-workflow-changes.py")
WORKFLOW = (ROOT / ".github" / "workflows" / "canonical-drift.yml").read_text(encoding="utf-8")


class MediaIntegrationTests(unittest.TestCase):
    def test_action_plan_schema_requires_v3_and_final_audit_result_contract(self):
        schema = json.loads((ROOT / "schemas/canonical-drift-action-plan.schema.json").read_text())
        validator = CHECKER.validators.validator_for(schema)(schema, format_checker=CHECKER.FormatChecker())
        audit = {
            "status": "incomplete",
            "distinct_urls": 2,
            "checked_urls": 1,
            "changed_assets": 0,
            "bytes_checked": 64,
            "failures": [{"source_url": "https://example.test/image.jpg", "error": "timeout"}],
            "elapsed_seconds": 1.5,
        }
        plan = {"version": 3, "action": "none", "media_updates": [], "media_audit": audit}
        self.assertEqual(list(validator.iter_errors(plan)), [])
        self.assertTrue(list(validator.iter_errors({**plan, "version": 2})))
        unsafe_path_plan = {
            **plan,
            "media_updates": [{
                "source_url": "https://example.test/image.jpg",
                "post_id": 1,
                "asset_path": "../image.jpg",
                "old_sha256": "0" * 64,
                "new_sha256": "1" * 64,
            }],
        }
        self.assertTrue(list(validator.iter_errors(unsafe_path_plan)))
        self.assertTrue(list(validator.iter_errors({
            **plan,
            "media_audit": {key: value for key, value in audit.items() if key != "elapsed_seconds"},
        })))

    def test_workflow_runs_audit_and_reports_result(self):
        self.assertIn("--audit-media", WORKFLOW)
        self.assertIn("media_audit", WORKFLOW)
        self.assertIn("GITHUB_STEP_SUMMARY", WORKFLOW)
        lines = WORKFLOW.splitlines()
        start = lines.index("          python3 - <<'PY'") + 1
        end = lines.index("          PY", start)
        script = textwrap.dedent("\n".join(line[10:] for line in lines[start:end]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            summary_path = root / "summary.md"
            plan_path.write_text(json.dumps({"media_audit": {"status": "complete", "bytes_checked": 10}}))
            subprocess.run(
                [sys.executable, "-c", script],
                check=True,
                env={**os.environ, "ACTION_PLAN_PATH": str(plan_path), "GITHUB_STEP_SUMMARY": str(summary_path)},
            )
            summary = summary_path.read_text()
            self.assertIn("### Same-URL media audit\n\n```json\n", summary)
            self.assertTrue(summary.endswith("\n```\n"))
            self.assertNotIn("\\n", summary)

    def test_archive_media_timestamp_drives_generated_freshness_without_mutating_source_date(self):
        post = {"slug": "example", "modified": "2026-01-02T00:00:00+00:00"}
        metadata = {"archive_media_updated_at": "2026-02-03T04:05:06+00:00"}
        expected = "2026-02-03T04:05:06Z"
        self.assertEqual(RENDER.post_lastmod(post, metadata), expected)
        self.assertEqual(VALIDATOR.generated_post_lastmod(post, metadata), expected)
        self.assertEqual(post["modified"], "2026-01-02T00:00:00+00:00")

    def test_feed_build_date_includes_archive_media_freshness(self):
        posts = [{"slug": "example", "modified": "2026-01-02T00:00:00+00:00"}]
        metadata = {"example": {"archive_media_updated_at": "2026-02-03T04:05:06+00:00"}}
        status = {"seo_activated_at": "2026-01-01T00:00:00+00:00"}
        expected = "Tue, 03 Feb 2026 04:05:06 GMT"
        self.assertEqual(RENDER.feed_last_build_date(posts, metadata, status), expected)
        self.assertEqual(VALIDATOR.generated_feed_last_build_date(posts, metadata, status), expected)

    def test_feed_build_date_normalises_non_utc_media_timestamp(self):
        posts = [{"slug": "example", "modified": "2026-01-02T00:00:00+00:00"}]
        metadata = {"example": {"archive_media_updated_at": "2026-02-03T09:35:06+05:30"}}
        status = {"seo_activated_at": None}
        expected = "Tue, 03 Feb 2026 04:05:06 GMT"
        self.assertEqual(RENDER.feed_last_build_date(posts, metadata, status), expected)
        self.assertEqual(VALIDATOR.generated_feed_last_build_date(posts, metadata, status), expected)

    def test_feed_build_date_ignores_media_refresh_outside_item_window(self):
        posts = [
            {
                "id": index + 1,
                "slug": f"post-{index}",
                "published": f"2026-02-{index + 1:02d}T00:00:00+00:00" if index else "2026-01-01T00:00:00+00:00",
                "modified": "2026-01-01T00:00:00+00:00",
            }
            for index in range(11)
        ]
        metadata = {"post-0": {"archive_media_updated_at": "2026-03-04T05:06:07+00:00"}}
        status = {"seo_activated_at": None}
        feed_posts = VALIDATOR.latest_feed_posts(posts)
        expected_feed_posts = list(reversed(posts[1:]))
        expected = "Thu, 01 Jan 2026 00:00:00 GMT"
        self.assertEqual(RENDER.feed_last_build_date(feed_posts, metadata, status), expected)
        self.assertEqual([post["slug"] for post in feed_posts], [post["slug"] for post in expected_feed_posts])
        self.assertEqual(VALIDATOR.generated_feed_last_build_date(feed_posts, metadata, status), expected)

    def test_metadata_timestamp_requires_date_time_format(self):
        schema = json.loads((ROOT / "schemas/post-metadata.schema.json").read_text())
        errors = list(CHECKER.validators.validator_for(schema)(schema, format_checker=CHECKER.FormatChecker()).iter_errors(
            {"archive_media_updated_at": "not-a-timestamp"}
        ))
        self.assertFalse(any("archive_media_updated_at" in error.message for error in errors))
        semantic_errors = []
        self.assertFalse(VALIDATOR.validate_archive_media_timestamp(
            {"archive_media_updated_at": "not-a-timestamp"}, "metadata.json", semantic_errors
        ))
        self.assertTrue(any("timezone-qualified ISO date-time" in error for error in semantic_errors))
        self.assertFalse(VALIDATOR.validate_archive_media_timestamp(
            {"archive_media_updated_at": "2026-02-03T04:05:06"}, "metadata.json", []
        ))
        self.assertTrue(VALIDATOR.validate_archive_media_timestamp(
            {"archive_media_updated_at": "2026-02-03T04:05:06+00:00"}, "metadata.json", []
        ))

    def test_media_update_must_match_base_asset_source_and_both_hashes(self):
        old_root, old_schema = CHECKER.ROOT, CHECKER.ACTION_PLAN_SCHEMA
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            CHECKER.ROOT = root
            CHECKER.ACTION_PLAN_SCHEMA = old_schema
            bundle = "content/posts/2026-01-01-example"
            asset_path = f"{bundle}/assets/image.jpg"
            source_url = "https://www.daryllswer.com/wp-content/uploads/image.jpg"
            old_bytes, new_bytes = b"old-image", b"new-image"
            old_hash = hashlib.sha256(old_bytes).hexdigest()
            new_hash = hashlib.sha256(new_bytes).hexdigest()
            (root / bundle / "assets").mkdir(parents=True)
            (root / asset_path).write_bytes(old_bytes)
            (root / f"{bundle}/assets/manifest.json").write_text(json.dumps({
                "post_id": 42,
                "assets": [{"local_path": asset_path, "source_url": source_url, "sha256": old_hash}],
            }))
            (root / "archive-manifest.json").write_text(json.dumps({
                "posts": [{"id": 42, "bundle_path": bundle}],
            }))
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            (root / asset_path).write_bytes(new_bytes)
            (root / f"{bundle}/assets/manifest.json").write_text(json.dumps({
                "post_id": 42,
                "assets": [{"local_path": asset_path, "source_url": source_url, "sha256": new_hash}],
            }))
            plan = {
                "action": "sync",
                "canonical_healthy": True,
                "media_audit": {"status": "complete"},
                "media_updates": [{
                "source_url": source_url,
                "post_id": 42,
                "asset_path": asset_path,
                "old_sha256": old_hash,
                "new_sha256": new_hash,
                }],
            }
            try:
                CHECKER.validate_media_updates(plan, staged=False)
                subprocess.run(["git", "add", asset_path, f"{bundle}/assets/manifest.json"], cwd=root, check=True)
                CHECKER.validate_media_updates(plan, staged=True)
                plan["media_updates"][0]["new_sha256"] = old_hash
                with self.assertRaisesRegex(ValueError, "new media hash"):
                    CHECKER.validate_media_updates(plan, staged=False)
                plan["action"] = "none"
                plan["media_updates"][0]["new_sha256"] = "0" * 64
                CHECKER.validate_media_updates(plan, staged=False)
            finally:
                CHECKER.ROOT, CHECKER.ACTION_PLAN_SCHEMA = old_root, old_schema


if __name__ == "__main__":
    unittest.main()
