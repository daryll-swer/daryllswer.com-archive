import importlib.util
import json
from types import SimpleNamespace
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("schema_validation", ROOT / "scripts" / "validate-mirror.py")
VALIDATOR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VALIDATOR)


class SchemaValidationTests(unittest.TestCase):
    def test_missing_or_unsupported_schema_dialect_is_rejected(self):
        for schema in [{"type": "object"}, {"$schema": "https://example.com/unknown", "type": "object"}]:
            errors = []
            self.assertFalse(VALIDATOR.validate_json_schema({}, schema, "schema.json", errors))
            self.assertTrue(errors)

    def test_metadata_nested_rights_reference_resolves_locally(self):
        schema = VALIDATOR.load_json(ROOT / "schemas" / "post-metadata.schema.json")
        data = {
            "id": 1, "slug": "post", "title": "Title", "canonical_url": "https://example.com/",
            "published": "2026-01-01", "modified": "2026-01-01", "source": {"canonical_rendered_content_sha256": "a" * 64},
            "hashes": {}, "featured_image": None, "assets_manifest": "assets/manifest.json",
            "rights": {
                "rights_holder": 5, "copyright_year": 2026, "rights_status": "proprietary/all-rights-reserved",
                "notice_path": "notice.txt", "original_article_url": "https://example.com/", "publisher": "Publisher",
                "scope": "article-text", "media_rights": "separate", "external_fallback": False,
            },
        }
        errors = []
        self.assertFalse(VALIDATOR.validate_json_schema(data, schema, "metadata.json", errors))
        self.assertTrue(any("rights_holder" in error for error in errors))

    def test_bad_metadata_and_asset_manifest_shapes_report_without_semantic_access(self):
        metadata_schema = VALIDATOR.load_json(ROOT / "schemas" / "post-metadata.schema.json")
        asset_schema = VALIDATOR.load_json(ROOT / "schemas" / "asset-manifest.schema.json")
        for value, schema in [("not-object", metadata_schema), ([], asset_schema)]:
            errors = []
            self.assertFalse(VALIDATOR.validate_json_schema(value, schema, "bad.json", errors))
            self.assertTrue(errors)

    def test_validate_post_skips_semantics_for_invalid_nested_metadata(self):
        old_root = VALIDATOR.ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                bundle = root / "content/posts/test-post"
                (bundle / "source").mkdir(parents=True)
                (bundle / "assets").mkdir()
                for relative in ["index.md", "source/wordpress-post.json", "source/rendered-article.html", "source/canonical-page.html"]:
                    (bundle / relative).write_text("", encoding="utf-8")
                (root / "schemas").mkdir()
                for schema_name in ["post-metadata.schema.json", "asset-manifest.schema.json"]:
                    (root / "schemas" / schema_name).write_text((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"), encoding="utf-8")
                metadata = {
                    "id": 1, "slug": "test", "title": "Test", "canonical_url": "https://example.com/",
                    "published": "2026-01-01", "modified": "2026-01-01", "source": "malformed",
                    "hashes": [], "featured_image": None, "assets_manifest": "assets/manifest.json", "rights": {},
                }
                (bundle / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
                VALIDATOR.ROOT = root
                errors = []
                VALIDATOR.validate_post({"slug": "test", "bundle_path": "content/posts/test-post", "canonical_url": "https://example.com/"}, errors, [], set())
                self.assertTrue(any("metadata.json:source" in item for item in errors))
                self.assertTrue(any("metadata.json:hashes" in item for item in errors))
        finally:
            VALIDATOR.ROOT = old_root


class PaginationTests(unittest.TestCase):
    def test_rest_pagination_requires_stable_total_and_all_ids(self):
        pages = [{"id": i} for i in range(1, 102)]
        old_detector = VALIDATOR.DETECTOR_MODULE
        try:
            for headers in [
                {"X-WP-Total": "101", "X-WP-TotalPages": "2"},
                {"x-wp-total": "101", "x-wp-totalpages": "2"},
            ]:
                with self.subTest(headers=headers):
                    VALIDATOR.DETECTOR_MODULE = SimpleNamespace(request_posts=lambda *_args, **_kwargs: (pages, headers, False))
                    posts, total = VALIDATOR.paginated_live_posts()
                    self.assertEqual((len(posts), total), (101, 101))
            pages[-1] = {"id": 100}
            VALIDATOR.DETECTOR_MODULE = SimpleNamespace(request_posts=lambda *_args, **_kwargs: (pages, {"x-wp-total": "101", "x-wp-totalpages": "2"}, False))
            with self.assertRaisesRegex(ValueError, "duplicate post IDs"):
                VALIDATOR.paginated_live_posts()
        finally:
            VALIDATOR.DETECTOR_MODULE = old_detector

    def test_rest_pagination_rejects_missing_or_ambiguous_headers(self):
        old_detector = VALIDATOR.DETECTOR_MODULE
        try:
            for headers in [
                {"X-WP-Total": "1"},
                {"X-WP-Total": "1", "x-wp-total": "2", "X-WP-TotalPages": "1"},
            ]:
                with self.subTest(headers=headers):
                    VALIDATOR.DETECTOR_MODULE = SimpleNamespace(request_posts=lambda *_args, **_kwargs: ([{"id": 1}], headers, False))
                    with self.assertRaises(ValueError):
                        VALIDATOR.paginated_live_posts()
        finally:
            VALIDATOR.DETECTOR_MODULE = old_detector

    def test_rest_pagination_rejects_unbounded_page_count(self):
        old_detector = VALIDATOR.DETECTOR_MODULE
        try:
            VALIDATOR.DETECTOR_MODULE = SimpleNamespace(request_posts=lambda *_args, **_kwargs: ([], {"X-WP-Total": "10001", "X-WP-TotalPages": "101"}, False))
            with self.assertRaisesRegex(ValueError, "outside 1..100"):
                VALIDATOR.paginated_live_posts()
        finally:
            VALIDATOR.DETECTOR_MODULE = old_detector


if __name__ == "__main__":
    unittest.main()
