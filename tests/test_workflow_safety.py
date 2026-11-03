import importlib.util
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load("workflow_change_checker", ROOT / "scripts/check-workflow-changes.py")
DETECTOR = load("workflow_safety_detector", ROOT / "scripts/check-canonical-drift.py")


class WorkflowSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_roots = CHECKER.ROOT, DETECTOR.ROOT
        CHECKER.ROOT = DETECTOR.ROOT = self.root
        (self.root / "content/posts/2026-01-01-retired").mkdir(parents=True)
        (self.root / "content/posts/2026-01-01-retired/index.md").write_text("retired", encoding="utf-8")
        self.manifest = {
            "post_count": 1,
            "generated_at": "2026-01-01T00:00:00Z",
            "posts": [{"id": 7, "slug": "retired", "canonical_url": "https://example.com/retired/", "bundle_path": "content/posts/2026-01-01-retired"}],
        }
        self.registry = {"7": {"rights_holder": "Owner"}, "8": {"rights_holder": "Other"}}
        (self.root / "archive-manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.root / "content/rights-registry.json").write_text(json.dumps(self.registry), encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root, check=True)

    def tearDown(self):
        CHECKER.ROOT, DETECTOR.ROOT = self.old_roots
        self.temp.cleanup()

    def action_plan(self, path):
        evidence = {
            "passed": True,
            "rest": {"passed": True, "status": 404},
            "canonical_route": {"passed": True, "status": 410},
        }
        drift = {
            "missing_posts": [{"id": 7, "slug": "retired", "canonical_url": "https://example.com/retired/", "bundle_path": "content/posts/2026-01-01-retired"}],
            "archived_post_count": 1,
            "live_post_count": 0,
            "new_ids": [], "relocated_posts": [], "changed_posts": [],
        }
        status = {"state": "healthy", "frozen": False, "retirement_candidates": [{
            "id": 7, "slug": "retired", "canonical_url": "https://example.com/retired/", "bundle_path": "content/posts/2026-01-01-retired",
            "healthy_confirmations": [
                {"observed_at": "2026-01-01T00:00:00+00:00"},
                {"observed_at": "2026-01-09T00:00:00+00:00"},
            ],
        }]}
        plan = DETECTOR.build_action_plan(
            status, drift, "2026-01-10T00:00:00+00:00", evidence,
            media_audit={"status": "complete", "distinct_urls": 0, "checked_urls": 0, "changed_assets": 0, "bytes_checked": 0, "failures": [], "elapsed_seconds": 0},
        )
        self.assertTrue(plan["retirement"]["eligible"])
        path.write_text(json.dumps(plan), encoding="utf-8")
        return plan

    def test_registry_allowlist_permits_exact_plan_retirement_only(self):
        plan_path = Path(self.temp.name).parent / (Path(self.temp.name).name + "-plan.json")
        try:
            plan = self.action_plan(plan_path)
            updated = dict(self.registry)
            del updated["7"]
            (self.root / "content/rights-registry.json").write_text(json.dumps(updated), encoding="utf-8")
            self.manifest["posts"] = []
            self.manifest["post_count"] = 0
            (self.root / "archive-manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
            import shutil
            shutil.rmtree(self.root / plan["retirement"]["candidate"]["bundle_path"])
            base = CHECKER.registry_bytes("HEAD:content/rights-registry.json")
            self.assertEqual(CHECKER.expected_registry(base, plan_path), CHECKER.json_bytes(updated))

            unrelated = {**updated, "8": {"rights_holder": "Edited"}}
            (self.root / "content/rights-registry.json").write_text(json.dumps(unrelated), encoding="utf-8")
            self.assertNotEqual(CHECKER.expected_registry(base, plan_path), CHECKER.content("content/rights-registry.json", False))
        finally:
            plan_path.unlink(missing_ok=True)

    def test_staged_retirement_rejects_bundle_entry_left_in_index(self):
        plan_path = Path(self.temp.name).parent / (Path(self.temp.name).name + "-staged-plan.json")
        try:
            plan = self.action_plan(plan_path)
            updated = dict(self.registry)
            del updated["7"]
            (self.root / "content/rights-registry.json").write_text(json.dumps(updated), encoding="utf-8")
            self.manifest["posts"] = []
            self.manifest["post_count"] = 0
            (self.root / "archive-manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
            import shutil
            shutil.rmtree(self.root / plan["retirement"]["candidate"]["bundle_path"])
            subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
            bundle = self.root / plan["retirement"]["candidate"]["bundle_path"]
            bundle.mkdir(parents=True)
            (bundle / "stale.md").write_text("stale staged content", encoding="utf-8")
            subprocess.run(["git", "add", str(bundle / "stale.md")], cwd=self.root, check=True)
            base = CHECKER.registry_bytes("HEAD:content/rights-registry.json")
            with self.assertRaisesRegex(ValueError, "remains in the staged index"):
                CHECKER.expected_registry(base, plan_path, staged=True)
        finally:
            plan_path.unlink(missing_ok=True)

    def test_retirement_requires_action_and_version_not_only_eligible_boolean(self):
        plan_path = Path(self.temp.name).parent / (Path(self.temp.name).name + "-invalid-plan.json")
        try:
            plan = self.action_plan(plan_path)
            plan["action"] = "none"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            base = CHECKER.registry_bytes("HEAD:content/rights-registry.json")
            self.assertEqual(CHECKER.expected_registry(base, plan_path), base)
        finally:
            plan_path.unlink(missing_ok=True)

    def test_pages_workflow_skips_only_successful_revision_and_retries_missing_record(self):
        text = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/pages-deployment-gate.py", text)
        self.assertIn("if: needs.build.outputs.needed == 'true'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("Recheck current main immediately before deployment", text)

    def test_canonical_completion_deploys_trusted_main_sha_without_reusable_call(self):
        pages = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        canonical = (ROOT / ".github/workflows/canonical-drift.yml").read_text(encoding="utf-8")
        self.assertIn('workflows: ["Canonical drift check"]', pages)
        self.assertIn("types: [completed]", pages)
        self.assertIn("branches: [main]", pages)
        self.assertIn("workflow_run.conclusion == 'success'", pages)
        self.assertIn("workflow_run.head_branch == 'main'", pages)
        self.assertIn("workflow_run.head_repository.full_name == github.repository", pages)
        self.assertEqual(pages.count("ref: ${{ github.sha }}"), 2)
        self.assertNotIn("workflow_call:", pages)
        self.assertNotIn("inputs.revision", pages)
        self.assertNotIn("uses: ./.github/workflows/deploy-pages.yml", canonical)

    def test_gate_uses_only_latest_deployment_status_for_sha(self):
        gate = load("pages_deployment_gate_test", ROOT / "scripts/pages-deployment-gate.py")
        records = [
            {"id": 1, "sha": "abc", "created_at": "2026-01-01T00:00:00Z"},
            {"id": 2, "sha": "def", "created_at": "2026-01-02T00:00:00Z"},
        ]
        statuses = {1: [{"state": "success"}], 2: [{"state": "inactive"}, {"state": "success"}]}
        fetch = lambda deployment_id: statuses[deployment_id]
        self.assertFalse(gate.latest_status_for_revision("abc", records, fetch))
        self.assertFalse(gate.latest_status_for_revision("def", records, fetch))
        statuses[2] = [{"state": "success"}]
        self.assertTrue(gate.latest_status_for_revision("def", records, fetch))
        statuses[2] = [{"state": "failure"}]
        self.assertFalse(gate.latest_status_for_revision("def", records, fetch))

    def test_deployment_api_error_fails_closed(self):
        gate = load("pages_deployment_gate_api_error", ROOT / "scripts/pages-deployment-gate.py")
        with patch.object(gate.subprocess, "check_output", side_effect=subprocess.CalledProcessError(1, "gh")):
            with self.assertRaises(subprocess.CalledProcessError):
                gate.gh_json("repos/example/repo/deployments")

    def test_gate_api_queries_are_bounded_to_latest_deployment_and_status(self):
        gate = load("pages_deployment_gate_bounded_calls", ROOT / "scripts/pages-deployment-gate.py")
        calls = []

        def capture(argv, **_kwargs):
            calls.append(argv)
            return "[]"

        with patch.object(gate.subprocess, "check_output", side_effect=capture):
            gate.gh_json("repos/example/repo/deployments?environment=github-pages&per_page=100")
            gate.gh_json("repos/example/repo/deployments/3/statuses?per_page=1")
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("--paginate" not in call for call in calls))
        self.assertIn("per_page=100", calls[0][-1])
        self.assertIn("per_page=1", calls[1][-1])


if __name__ == "__main__":
    unittest.main()
