import importlib.util
import json
import sys
import tempfile
import unittest
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


SYNC = load_script("rights_sync", "sync-wordpress-posts.py")
VALIDATOR = load_script("rights_validator", "validate-mirror.py")


class RightsRegistryTests(unittest.TestCase):
    def test_approved_registry_record_is_keyed_by_immutable_wordpress_id(self):
        registry = SYNC.load_rights_registry()
        record = registry["5324"]
        self.assertEqual(record["rights_holder"], "Swer Networks")
        self.assertEqual(record["rights_status"], "proprietary/all-rights-reserved")
        self.assertFalse(record["default_ds_cc_applies"])
        self.assertEqual(
            record["original_article_url"],
            "https://www.swernetworks.com/blog/bgp-router-id-structuring-in-ipv6-native-networks/",
        )
        self.assertEqual(record["publisher"], "Swer Networks")
        self.assertEqual(record["scope"], "article-text")
        self.assertEqual(record["media_rights"], "separate attribution/right notices")

    def test_metadata_rights_projection_is_registry_exact(self):
        registry = SYNC.load_rights_registry()
        projected = SYNC.rights_for_post(5324, registry)
        self.assertEqual(projected, registry["5324"])
        self.assertIsNone(SYNC.rights_for_post(999999, registry))
        projected["publisher"] = "changed in test"
        self.assertEqual(registry["5324"]["publisher"], "Swer Networks")

    def test_registry_record_rejects_missing_required_field(self):
        record = SYNC.load_rights_registry()["5324"]
        invalid = dict(record)
        invalid.pop("media_rights")
        with self.assertRaisesRegex(ValueError, "media_rights"):
            SYNC.validate_rights_record("5324", invalid)

    def test_empty_registry_is_valid_for_synchronisation(self):
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "content" / "rights-registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(SYNC, "RIGHTS_REGISTRY_PATH", registry_path):
                self.assertEqual(SYNC.load_rights_registry(), {})

    def test_empty_registry_is_valid_when_archive_has_no_rights_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "content" / "rights-registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text("{}\n", encoding="utf-8")
            old_root = VALIDATOR.ROOT
            old_registry_path = VALIDATOR.RIGHTS_REGISTRY_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                errors = []
                self.assertEqual(VALIDATOR.validate_rights_registry({"posts": []}, errors), {})
                self.assertEqual(errors, [])
            finally:
                VALIDATOR.ROOT = old_root
                VALIDATOR.RIGHTS_REGISTRY_PATH = old_registry_path

    def test_archived_5324_requires_a_registry_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "content" / "rights-registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text("{}\n", encoding="utf-8")
            old_root = VALIDATOR.ROOT
            old_registry_path = VALIDATOR.RIGHTS_REGISTRY_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                errors = []
                VALIDATOR.validate_rights_registry({"posts": [{"id": 5324}]}, errors)
                self.assertTrue(any("5324" in error for error in errors))
            finally:
                VALIDATOR.ROOT = old_root
                VALIDATOR.RIGHTS_REGISTRY_PATH = old_registry_path

    def test_metadata_rights_must_have_a_matching_registry_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "content" / "rights-registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text("{}\n", encoding="utf-8")
            bundle = root / "content" / "posts" / "post"
            bundle.mkdir(parents=True)
            (bundle / "metadata.json").write_text(
                json.dumps({"id": 1, "rights": {"unexpected": True}}), encoding="utf-8"
            )
            post = {"id": 1, "slug": "post", "bundle_path": "content/posts/post"}
            old_root = VALIDATOR.ROOT
            old_registry_path = VALIDATOR.RIGHTS_REGISTRY_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                errors = []
                VALIDATOR.validate_rights_registry({"posts": [post]}, errors)
                self.assertTrue(any("no matching registry entry" in error for error in errors))
            finally:
                VALIDATOR.ROOT = old_root
                VALIDATOR.RIGHTS_REGISTRY_PATH = old_registry_path

    def test_validator_requires_registry_entry_to_match_generated_metadata(self):
        archive = json.loads((ROOT / "archive-manifest.json").read_text(encoding="utf-8"))
        errors = []
        registry = VALIDATOR.validate_rights_registry(archive, errors)
        self.assertEqual(registry["5324"], SYNC.load_rights_registry()["5324"])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
