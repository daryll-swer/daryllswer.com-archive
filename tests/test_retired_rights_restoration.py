import importlib.util
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


RECONCILE = load_script("restored_rights_reconcile", "reconcile-canonical-drift.py")
POLICY = load_script("restored_rights_policy", "rights_policy.py")


def load_validator_with_schema_dependency_stubs():
    jsonschema = types.ModuleType("jsonschema")
    jsonschema.FormatChecker = type("FormatChecker", (), {})
    jsonschema.validators = types.SimpleNamespace()
    referencing = types.ModuleType("referencing")
    referencing.Registry = type("Registry", (), {})
    referencing.Resource = type("Resource", (), {})
    spec = importlib.util.spec_from_file_location("restored_rights_validator", ROOT / "scripts" / "validate-mirror.py")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"jsonschema": jsonschema, "referencing": referencing}):
        assert spec.loader
        spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator_with_schema_dependency_stubs()


class RetiredRightsRestorationTests(unittest.TestCase):
    def test_restored_5324_without_registry_entry_fails_publication_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_reconcile_root = RECONCILE.ROOT
            RECONCILE.ROOT = root
            stage = None
            try:
                post = {
                    "id": 5324,
                    "slug": "bgp-router-id-structuring-in-ipv6-native-networks",
                    "canonical_url": "https://www.daryllswer.com/bgp-router-id-structuring-in-ipv6-native-networks/",
                    "title": "BGP Router ID Structuring in IPv6 Native Networks",
                    "modified": "2026-11-01T00:00:00",
                    "bundle_path": "content/posts/2026-06-04-bgp-router-id-structuring-in-ipv6-native-networks",
                }
                (root / "archive-manifest.json").write_text(json.dumps({"post_count": 0, "posts": []}), encoding="utf-8")
                registry_path = root / "content" / "rights-registry.json"
                registry_path.parent.mkdir(parents=True)
                registry_path.write_text("{}\n", encoding="utf-8")
                plan = {
                    "drift": {"new_ids": [5324], "missing_ids": [], "relocated_posts": [], "changed_posts": []},
                    "sync_posts": [post],
                    "update_posts": [],
                }

                def fake_sync(_command, *, cwd, env, check):
                    self.assertFalse(check)
                    stage_root = Path(env["ARCHIVE_ROOT"])
                    bundle = stage_root / post["bundle_path"]
                    bundle.mkdir(parents=True)
                    (bundle / "metadata.json").write_text(json.dumps({
                        "id": 5324,
                        "canonical_url": post["canonical_url"],
                        "rights": POLICY.resolve_rights(5324, post["canonical_url"], {}),
                    }), encoding="utf-8")
                    (bundle / "index.md").write_text(
                        POLICY.rights_notice_markdown(POLICY.resolve_rights(5324, post["canonical_url"], {})),
                        encoding="utf-8",
                    )
                    (stage_root / "archive-manifest.json").write_text(
                        json.dumps({"post_count": 1, "posts": [post]}), encoding="utf-8"
                    )
                    return types.SimpleNamespace(returncode=0)

                with mock.patch.object(RECONCILE.subprocess, "run", side_effect=fake_sync):
                    stage, new_posts, updates = RECONCILE.stage_sync(plan, {"post_count": 0, "posts": []})
                self.assertEqual([item["id"] for item in new_posts], [5324])
                self.assertEqual(updates, [])
                staged_manifest = json.loads((stage / "archive-manifest.json").read_text(encoding="utf-8"))
                staged_metadata = json.loads((stage / post["bundle_path"] / "metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(staged_metadata["rights"]["rights_holder"], "Daryll Swer")

                schema_path = stage / "schemas" / "rights-registry.schema.json"
                schema_path.parent.mkdir(parents=True)
                schema_path.write_text(json.dumps({
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$defs": {"rights": {"required": list(VALIDATOR.RIGHTS_REQUIRED_FIELDS)}},
                }), encoding="utf-8")
                notice_path = stage / POLICY.DEFAULT_NOTICE_PATH
                notice_path.parent.mkdir(parents=True)
                notice_path.write_text("fixture notice", encoding="utf-8")

                old_validator = (
                    VALIDATOR.ROOT,
                    VALIDATOR.RIGHTS_REGISTRY_PATH,
                    VALIDATOR.RIGHTS_SCHEMA_PATH,
                )
                try:
                    VALIDATOR.ROOT = stage
                    VALIDATOR.RIGHTS_REGISTRY_PATH = stage / "content" / "rights-registry.json"
                    VALIDATOR.RIGHTS_SCHEMA_PATH = schema_path
                    errors = []
                    with mock.patch.object(VALIDATOR, "validate_json_schema", return_value=True):
                        VALIDATOR.validate_rights_registry(staged_manifest, errors)
                    self.assertEqual(errors, [
                        "content/rights-registry.json must contain an entry for archived WordPress post ID 5324"
                    ])
                finally:
                    (VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH, VALIDATOR.RIGHTS_SCHEMA_PATH) = old_validator
            finally:
                RECONCILE.ROOT = old_reconcile_root
                if stage is not None:
                    shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
