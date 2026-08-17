import importlib.util
import json
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


VALIDATOR = load_script("canonical_drift_workflow_validator", "validate-mirror.py")
WORKFLOW = (ROOT / ".github" / "workflows" / "canonical-drift.yml").read_text(encoding="utf-8")


class CanonicalDriftWorkflowTests(unittest.TestCase):
    def validate_workflow(self, workflow: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_path = root / ".github" / "workflows" / "canonical-drift.yml"
            workflow_path.parent.mkdir(parents=True)
            workflow_path.write_text(workflow, encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "CANONICAL_DRIFT.md").write_text("# Drift\n", encoding="utf-8")
            (root / "requirements.txt").write_text("lxml\n", encoding="utf-8")
            (root / "schemas").mkdir()
            schema = (ROOT / "schemas" / "archive-status.schema.json").read_text(encoding="utf-8")
            (root / "schemas" / "archive-status.schema.json").write_text(schema, encoding="utf-8")
            (root / "archive-status.json").write_text(
                json.dumps(
                    {
                        "version": 2,
                        "state": "healthy",
                        "frozen": False,
                        "seo_state": "source_primary",
                        "seo_activated_at": None,
                        "policy": {"frozen_archive_noops_without_network": True},
                        "external_sources": {},
                    }
                ),
                encoding="utf-8",
            )
            old_root = VALIDATOR.ROOT
            try:
                VALIDATOR.ROOT = root
                errors: list[str] = []
                VALIDATOR.validate_drift_automation(errors, [], {})
                return errors
            finally:
                VALIDATOR.ROOT = old_root

    def test_workflow_requires_safe_root_staging_and_both_allowlist_checks(self):
        self.assertEqual(self.validate_workflow(WORKFLOW), [])

    def test_validator_rejects_literal_optional_feed_staging(self):
        broken = WORKFLOW.replace("git add -A -- .", "git add -A -- . docs/feed.xml")

        errors = self.validate_workflow(broken)

        self.assertTrue(
            any("must not pass optional docs/feed.xml directly to git add" in error for error in errors)
        )

    def test_validator_rejects_staging_without_root_scope(self):
        broken = WORKFLOW.replace("git add -A -- .", "git add -A -- docs")

        errors = self.validate_workflow(broken)

        self.assertTrue(any("root-scoped all-state staging" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
