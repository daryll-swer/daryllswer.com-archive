from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DRIFT = load_script("monitoring_integrity_drift", SCRIPTS / "check-canonical-drift.py")
ORIGINAL_NOW_UTC = DRIFT.now_utc
HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


def copy_ignore(_directory: str, names: list[str]) -> set[str]:
    excluded = {".git", ".cache", ".tmp", ".preview", "__pycache__", "node_modules"}
    return {
        name for name in names
        if name in excluded or name.startswith((".venv", "venv"))
    }


class MonitoringIntegrityIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "archive-copy"
        shutil.copytree(REPO_ROOT, self.root, ignore=copy_ignore)
        self.status_path = self.root / "archive-status.json"
        self.report_path = self.root / "docs" / "CANONICAL_DRIFT.md"
        self.manifest = json.loads((self.root / "archive-manifest.json").read_text(encoding="utf-8"))
        self.original_status = json.loads(self.status_path.read_text(encoding="utf-8"))
        self.configure_drift()

    def configure_drift(self) -> None:
        DRIFT.ROOT = self.root
        DRIFT.STATUS_PATH = self.status_path
        DRIFT.REPORT_PATH = self.report_path
        DRIFT.now_utc = lambda: dt.datetime(2026, 11, 1, 12, tzinfo=dt.timezone.utc)

    def tearDown(self) -> None:
        DRIFT.ROOT = REPO_ROOT
        DRIFT.STATUS_PATH = REPO_ROOT / "archive-status.json"
        DRIFT.REPORT_PATH = REPO_ROOT / "docs" / "CANONICAL_DRIFT.md"
        DRIFT.now_utc = ORIGINAL_NOW_UTC

    def summaries(self, omitted_ids: set[int]) -> list[dict]:
        return [
            DRIFT.archived_post_summary(post)
            for post in self.manifest["posts"]
            if post["id"] not in omitted_ids
        ]

    def run_monitor(self, live_posts: list[dict], action_plan: Path) -> dict:
        def endpoint_result(url: str) -> dict:
            status = 404 if "/wp-json/" in url else 410
            return {"url": url, "status": status, "passed": True}

        argv = ["check-canonical-drift.py", "--audit-media", "--action-plan", str(action_plan)]
        complete_audit = {"status": "complete", "distinct_urls": 0, "checked_urls": 0, "changed_assets": 0, "bytes_checked": 0, "failures": [], "elapsed_seconds": 0}
        with (
            mock.patch.object(DRIFT, "request_posts", return_value=(live_posts, {}, False)),
            mock.patch.object(DRIFT, "endpoint_status", side_effect=endpoint_result) as endpoint_check,
            mock.patch.object(DRIFT, "audit_media", return_value=([], complete_audit)),
            mock.patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(DRIFT.main(), 0)
        self.assertTrue(action_plan.is_file())
        self.endpoint_check = endpoint_check
        return json.loads(action_plan.read_text(encoding="utf-8"))

    def test_first_healthy_missing_confirmation_persists_without_retirement_action(self) -> None:
        missing = self.manifest["posts"][0]
        action_path = Path(self.temporary.name) / "single-missing-plan.json"
        plan = self.run_monitor(self.summaries({missing["id"]}), action_path)
        status = json.loads(self.status_path.read_text(encoding="utf-8"))

        self.assertEqual(status["state"], "healthy")
        self.assertEqual(len(status["retirement_candidates"]), 1)
        candidate = status["retirement_candidates"][0]
        self.assertEqual(candidate["id"], missing["id"])
        self.assertEqual(candidate["confirmation_count"], 1)
        self.assertEqual(plan["action"], "none")
        self.assertFalse(plan["retirement"]["eligible"])
        self.assertEqual(plan["drift"]["missing_ids"], [missing["id"]])
        self.assertTrue(status["last_drift_hash"])
        self.assertEqual(len(status["last_live_post_summaries"]), len(self.manifest["posts"]) - 1)

    @unittest.skipUnless(HAS_JSONSCHEMA, "bundled Python has no jsonschema; offline validator import is unavailable")
    def test_offline_validator_accepts_pending_candidate_without_source_requests(self) -> None:
        missing = self.manifest["posts"][0]
        action_path = Path(self.temporary.name) / "single-missing-plan.json"
        plan = self.run_monitor(self.summaries({missing["id"]}), action_path)
        self.assertEqual(plan["action"], "none")
        self.assertEqual(json.loads(self.status_path.read_text())["retirement_candidates"][0]["confirmation_count"], 1)

        snapshot_scripts = str(self.root / "scripts")
        sys.path.insert(0, snapshot_scripts)
        try:
            validator = load_script("monitoring_integrity_validator", self.root / "scripts" / "validate-mirror.py")
        finally:
            sys.path.remove(snapshot_scripts)
        validator.ROOT = self.root
        validator.RIGHTS_REGISTRY_PATH = self.root / "content" / "rights-registry.json"
        validator.RIGHTS_SCHEMA_PATH = self.root / "schemas" / "rights-registry.schema.json"
        validator.ARCHIVE_STATUS_SCHEMA_PATH = self.root / "schemas" / "archive-status.schema.json"
        validator.AS141253_HIERARCHY_PATH = self.root / "data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json"
        with (
            mock.patch.object(validator, "paginated_live_posts", side_effect=AssertionError("source REST requested")),
            mock.patch.object(validator, "sitemap_urls", side_effect=AssertionError("source sitemap requested")),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("source network requested")),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(validator.main(["--offline", "--no-report"]), 0)
        self.assertIn("validation errors=0 warnings=0", output.getvalue())

    def test_unknown_multi_post_anomaly_has_no_action_and_persists_monitoring_evidence(self) -> None:
        first, second = self.manifest["posts"][:2]
        missing_ids = {first["id"], second["id"]}
        action_path = Path(self.temporary.name) / "multi-missing-plan.json"
        new_ids = {9_000_001, 9_000_002}
        unknown_posts = [
            {
                "id": post_id,
                "slug": f"unarchived-{post_id}",
                "canonical_url": f"https://www.daryllswer.com/unarchived-{post_id}/",
                "title": "unarchived post",
                "modified": "2026-11-01T00:00:00",
                "featured_image_url": None,
                "content_text_sha256": "a" * 64,
                "canonical_rendered_content_sha256": "b" * 64,
                "content_media_urls": [],
            }
            for post_id in sorted(new_ids)
        ]
        plan = self.run_monitor(self.summaries(missing_ids) + unknown_posts, action_path)
        status = json.loads(self.status_path.read_text(encoding="utf-8"))
        report = self.report_path.read_text(encoding="utf-8")

        self.assertEqual(plan["action"], "none")
        self.assertEqual(plan["drift"]["missing_ids"], sorted(missing_ids))
        self.assertEqual(plan["drift"]["new_ids"], sorted(new_ids))
        self.assertIsNone(plan["retirement"]["endpoint_evidence"])
        self.endpoint_check.assert_not_called()
        self.assertEqual(status["state"], "healthy")
        self.assertEqual(len(status["last_live_post_summaries"]), len(self.manifest["posts"]))
        self.assertTrue(new_ids.issubset({item["id"] for item in status["last_live_post_summaries"]}))
        self.assertTrue(status["last_drift_hash"])
        self.assertIn("Missing/unlisted canonical URLs: 2", report)
        self.assertIn(first["canonical_url"].rstrip("/"), report)
        self.assertIn(second["canonical_url"].rstrip("/"), report)
        self.assertTrue(all(item["canonical_url"].rstrip("/") in report for item in unknown_posts))


if __name__ == "__main__":
    unittest.main()
