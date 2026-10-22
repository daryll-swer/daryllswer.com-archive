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


POLICY = load_script("rights_policy_tests", "rights_policy.py")
SYNC = load_script("rights_sync_tests", "sync-wordpress-posts.py")
VALIDATOR = load_script("rights_validator_tests", "validate-mirror.py")


class RightsPolicyTests(unittest.TestCase):
    def override(self, **changes):
        record = {
            "rights_holder": "Example Publisher",
            "copyright_year": 2026,
            "rights_status": "proprietary/all-rights-reserved",
            "notice_path": "LICENSES/EXAMPLE-PUBLISHER-NOTICE.txt",
            "original_article_url": "https://origin.example/articles/example/",
            "publisher": "Example Publisher",
            "scope": "article-text",
            "media_rights": "separate attribution/right notices",
            "external_fallback": True,
        }
        record.update(changes)
        return record

    def test_default_resolver_returns_complete_proprietary_record(self):
        canonical = "https://archive.example/posts/default/"
        resolved = POLICY.resolve_rights(17, canonical, {})
        self.assertEqual(set(resolved), set(POLICY.RIGHTS_FIELDS))
        self.assertEqual(resolved["rights_holder"], "Daryll Swer")
        self.assertEqual(resolved["copyright_year"], 2026)
        self.assertEqual(resolved["rights_status"], "proprietary/all-rights-reserved")
        self.assertEqual(resolved["notice_path"], POLICY.DEFAULT_NOTICE_PATH)
        self.assertEqual(resolved["original_article_url"], canonical)
        self.assertFalse(resolved["external_fallback"])

    def test_registry_exception_overlays_defaults_without_losing_provenance(self):
        override = self.override()
        resolved = POLICY.resolve_rights(5324, "https://archive.example/posts/repost/", {"5324": override})
        self.assertEqual(resolved, override)
        self.assertTrue(resolved["external_fallback"])
        self.assertEqual(resolved["original_article_url"], override["original_article_url"])

    def test_sync_compatibility_resolver_requires_provenance_for_default(self):
        with self.assertRaisesRegex(ValueError, "canonical_url is required"):
            SYNC.rights_for_post(17, {})
        self.assertEqual(
            SYNC.rights_for_post(5324, {"5324": self.override()})["rights_holder"],
            "Example Publisher",
        )

    def test_exception_record_is_keyed_by_immutable_wordpress_id_and_is_copy_safe(self):
        record = self.override()
        registry = {"5324": record}
        projected = SYNC.rights_for_post(5324, registry)
        self.assertEqual(projected, record)
        projected["publisher"] = "changed in test"
        self.assertEqual(registry["5324"]["publisher"], "Example Publisher")
        self.assertEqual(SYNC.rights_for_post(17, registry, "https://archive.example/default/")["rights_holder"], "Daryll Swer")

    def test_registry_record_rejects_missing_required_field(self):
        invalid = self.override()
        invalid.pop("notice_path")
        with self.assertRaisesRegex(ValueError, "notice_path"):
            POLICY.validate_rights_record("17", invalid)

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
            old_root, old_registry = VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                errors = []
                self.assertEqual(VALIDATOR.validate_rights_registry({"posts": []}, errors), {})
                self.assertEqual(errors, [])
            finally:
                VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH = old_root, old_registry

    def test_archived_exception_requires_a_registry_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "content" / "rights-registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text("{}\n", encoding="utf-8")
            old_root, old_registry = VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                errors = []
                VALIDATOR.validate_rights_registry({"posts": [{"id": 5324}]}, errors)
                self.assertTrue(any("5324" in error for error in errors))
            finally:
                VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH = old_root, old_registry

    def test_metadata_rights_must_have_a_matching_resolved_record(self):
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
            post = {
                "id": 1,
                "slug": "post",
                "canonical_url": "https://archive.example/post/",
                "bundle_path": "content/posts/post",
            }
            old_root, old_registry = VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                errors = []
                VALIDATOR.validate_rights_registry({"posts": [post]}, errors)
                self.assertTrue(any("does not equal resolved" in error for error in errors))
            finally:
                VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH = old_root, old_registry

    def test_generic_source_rights_sanitiser_removes_semantic_declarations(self):
        rights = self.override(
            rights_holder="Swer Networks",
            publisher="Swer Networks",
            notice_path="LICENSES/SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt",
            external_fallback=True,
        )
        source = (
            '<section class="site-copyright"><h2>Copyright</h2>'
            '<p><a rel="license" href="https://terms.example/source">Source terms</a></p>'
            '</section><article><blockquote class="source-notice">'
            '<p>Originally published at <a href="https://origin.example/articles/example/">source</a>.</p>'
            '<p><strong>Copyright:</strong> (c) 2026 Swer Networks. All rights reserved.</p>'
            '<p>This article is republished here from Swer Networks. Source rights wording pending removal. '
            'Media remains subject to separate attribution or rights notices.</p>'
            '</blockquote><p>Body</p></article>'
        )
        filtered, transforms = POLICY.sanitise_source_rights_html(source, full_document=False, rights=rights)
        self.assertNotIn("Source terms", filtered)
        self.assertNotIn("Source rights wording pending removal", filtered)
        self.assertIn("origin.example/articles/example", filtered)
        self.assertIn("Swer Networks", filtered)
        self.assertIn("Media remains subject", filtered)
        self.assertTrue({item["category"] for item in transforms} >= {
            POLICY.SEMANTIC_RIGHTS_CATEGORY,
            POLICY.SITE_COPYRIGHT_CATEGORY,
            POLICY.MAPPED_NOTICE_CATEGORY,
        })
        for item in transforms:
            self.assertEqual(set(item), {"category", "count", "sha256"})

    def test_mapped_notice_requires_bounded_exception_block(self):
        rights = self.override(
            rights_holder="Swer Networks",
            publisher="Swer Networks",
            notice_path="LICENSES/SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt",
            external_fallback=True,
        )
        source = (
            '<article><p>Body links back to <a href="https://origin.example/articles/example/">the source</a> '
            'without being a rights block.</p><p>Keep this self-link.</p></article>'
        )
        filtered, transforms = POLICY.sanitise_source_rights_html(source, full_document=False, rights=rights)
        self.assertEqual(filtered, source)
        self.assertFalse(any(item["category"] == POLICY.MAPPED_NOTICE_CATEGORY for item in transforms))

    def test_article_self_links_and_independent_attribution_are_preserved(self):
        rights = POLICY.resolve_rights(17, "https://archive.example/posts/default/", {})
        source = (
            '<article><section class="article-copyright"><p>Independent Copyright notice for a cited work.</p>'
            '</section><p><a href="https://archive.example/posts/default/">Article self-link</a></p>'
            '<p>Independent attribution remains visible.</p></article>'
        )
        filtered, transforms = POLICY.sanitise_source_rights_html(source, full_document=False, rights=rights)
        self.assertEqual(filtered, source)
        self.assertEqual(transforms, [])

    def test_source_rights_sanitiser_is_idempotent(self):
        rights = self.override()
        source = '<p><a rel="license" href="https://terms.example/source">Source terms</a></p><p>Body</p>'
        filtered, transforms = POLICY.sanitise_source_rights_html(source, full_document=False, rights=rights)
        repeated, repeated_transforms = POLICY.sanitise_source_rights_html(filtered, full_document=False, rights=rights)
        self.assertEqual(repeated, filtered)
        self.assertEqual(repeated_transforms, [])
        self.assertEqual(transforms[0]["category"], POLICY.SEMANTIC_RIGHTS_CATEGORY)

    def test_bounded_markdown_notice_rewrites_without_touching_article_suffix(self):
        rights = self.override(
            rights_holder="Swer Networks",
            publisher="Swer Networks",
            notice_path="LICENSES/SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt",
            external_fallback=True,
        )
        technical_suffix = "\n## Technical section\n\nKeep this Markdown byte-for-byte.\n"
        source = (
            "> Originally published at [Swer Networks](https://origin.example/articles/example/).\n>\n"
            "> **Copyright:** © 2026 Swer Networks. All rights reserved.\n>\n"
            "> This article is republished here from Swer Networks. Source rights wording pending removal. "
            "Media remains subject to separate attribution or rights notices.\n"
            + technical_suffix
        )
        filtered, transforms = POLICY.sanitise_source_rights_markdown(source, rights=rights)
        self.assertIn("This article is republished here from Swer Networks. Media remains subject", filtered)
        self.assertNotIn("Source rights wording pending removal", filtered)
        self.assertTrue(filtered.endswith(technical_suffix))
        repeated, repeated_transforms = POLICY.sanitise_source_rights_markdown(filtered, rights=rights)
        self.assertEqual(repeated, filtered)
        self.assertEqual(repeated_transforms, [])
        self.assertEqual(transforms[0]["category"], POLICY.MAPPED_NOTICE_CATEGORY)

    def test_default_notice_is_compact_and_keeps_provenance_in_metadata_only(self):
        rights = POLICY.resolve_rights(17, "https://archive.example/posts/default/", {})
        notice = POLICY.rights_notice_markdown(rights)
        self.assertEqual(POLICY.markdown_notice_count(notice, rights), 1)
        self.assertNotIn(rights["original_article_url"], notice)
        self.assertEqual(notice.count("Copyright:"), 1)
        self.assertTrue(notice.endswith("\n"))
        self.assertFalse(notice.endswith("\n\n"))
        with_blank_eof = notice.rstrip("\n") + "\n\n"
        self.assertEqual(POLICY.normalise_markdown_notice_eof(with_blank_eof, rights=rights), notice)
        self.assertEqual(POLICY.normalise_markdown_notice_eof(notice, rights=rights), notice)

    def test_rest_sanitiser_filters_structured_rights_keys_and_html(self):
        rights = self.override()
        post = {
            "id": 17,
            "content": {"rendered": '<p><a rel="license" href="https://terms.example/source">Source terms</a></p>'},
            "meta": {"source_license": "https://terms.example/source", "unrelated": "keep"},
        }
        filtered, transforms = POLICY.sanitise_rest_post(post, rights=rights)
        self.assertNotIn("source_license", filtered["meta"])
        self.assertEqual(filtered["meta"]["unrelated"], "keep")
        self.assertNotIn("Source terms", filtered["content"]["rendered"])
        self.assertTrue(any(item["category"] == "source_rights_structured_field" for item in transforms))

    def test_validator_accepts_default_and_exception_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "content" / "rights-registry.json"
            registry_path.parent.mkdir(parents=True)
            override = self.override()
            registry_path.write_text(json.dumps({"18": override}), encoding="utf-8")
            for notice_path in [root / POLICY.DEFAULT_NOTICE_PATH, root / override["notice_path"]]:
                notice_path.parent.mkdir(parents=True, exist_ok=True)
                notice_path.write_text("All rights reserved.\n", encoding="utf-8")
            posts = []
            for post_id, canonical in [(17, "https://archive.example/posts/default/"), (18, "https://archive.example/posts/exception/")]:
                rights = POLICY.resolve_rights(post_id, canonical, {"18": override})
                bundle = root / "content" / "posts" / str(post_id)
                (bundle / "source").mkdir(parents=True)
                (bundle / "assets").mkdir()
                (bundle / "index.md").write_text("# Example\n\n" + POLICY.rights_notice_markdown(rights), encoding="utf-8")
                notice_html = POLICY.rights_notice_html(rights)
                (bundle / "source" / "rendered-article.html").write_text(notice_html, encoding="utf-8")
                (bundle / "source" / "canonical-page.html").write_text(notice_html, encoding="utf-8")
                (bundle / "source" / "wordpress-post.json").write_text(json.dumps({"content": notice_html}), encoding="utf-8")
                (bundle / "metadata.json").write_text(json.dumps({"rights": rights}), encoding="utf-8")
                posts.append({"id": post_id, "canonical_url": canonical, "bundle_path": f"content/posts/{post_id}", "slug": str(post_id)})
            archive = {"posts": posts}
            old_root, old_registry, old_schema = VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH, VALIDATOR.RIGHTS_SCHEMA_PATH
            try:
                VALIDATOR.ROOT = root
                VALIDATOR.RIGHTS_REGISTRY_PATH = registry_path
                VALIDATOR.RIGHTS_SCHEMA_PATH = ROOT / "schemas" / "rights-registry.schema.json"
                errors = []
                self.assertEqual(VALIDATOR.validate_rights_registry(archive, errors), {"18": override})
                self.assertEqual(errors, [])
            finally:
                VALIDATOR.ROOT, VALIDATOR.RIGHTS_REGISTRY_PATH, VALIDATOR.RIGHTS_SCHEMA_PATH = old_root, old_registry, old_schema


if __name__ == "__main__":
    unittest.main()
