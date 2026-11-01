import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
import urllib.error
import contextlib
import io
import types
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


DRIFT = load_script("health_canonical_drift", "check-canonical-drift.py")
MONITOR = load_script("health_external_monitor", "external_source_monitor.py")
MANAGE = load_script("health_archive_seo_manage", "manage-archive-seo.py")


class SourceHealthTests(unittest.TestCase):
    def test_classification_blocks_access_and_malformed_internal_errors(self):
        for status in (401, 403, 429, 302):
            kind, countable = DRIFT.classify_http_status(status)
            self.assertFalse(countable, (status, kind))
        self.assertEqual(DRIFT.classify_http_status(404), ("not_found", True))
        self.assertEqual(DRIFT.classify_http_status(503), ("server_error", True))

    def test_nonqualifying_observation_resets_pending_freeze_sequence(self):
        status = DRIFT.default_status("2026-01-01T00:00:00Z")
        status["failure"].update({"consecutive_failures": 7, "first_failure_at": "2026-01-01T00:00:00Z"})
        DRIFT.record_failure(status, "2026-02-01T00:00:00Z", "access_restricted", "HTTP 403")
        self.assertEqual(status["failure"]["consecutive_failures"], 0)
        self.assertEqual(status["state"], "degraded")
        self.assertFalse(status["frozen"])

    def test_conditional_304_is_preserved_but_fresh_304_is_rejected(self):
        conditional_error = urllib.error.HTTPError(DRIFT.POSTS_ENDPOINT, 304, "Not Modified", {}, None)
        opener = mock.Mock()
        opener.open.side_effect = conditional_error
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", opener):
            posts, _, not_modified = DRIFT.request_posts({
                "http_cache": {DRIFT.POSTS_ENDPOINT: {"etag": '"v1"'}}
            }, fresh=False)
        self.assertIsNone(posts)
        self.assertTrue(not_modified)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("If-none-match"), '"v1"')

        fresh_opener = mock.Mock()
        fresh_opener.open.side_effect = urllib.error.HTTPError(DRIFT.POSTS_ENDPOINT, 304, "Not Modified", {}, None)
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", fresh_opener):
            with self.assertRaises(DRIFT.SourceObservationError):
                DRIFT.request_posts({"http_cache": {DRIFT.POSTS_ENDPOINT: {"etag": '"v1"'}}}, fresh=True)

        unsolicited_opener = mock.Mock()
        unsolicited_opener.open.side_effect = urllib.error.HTTPError(DRIFT.POSTS_ENDPOINT, 304, "Not Modified", {}, None)
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", unsolicited_opener):
            with self.assertRaises(DRIFT.SourceObservationError):
                DRIFT.request_posts({"http_cache": {}}, fresh=False)

    def test_rest_pages_validate_records_totals_and_page_headers(self):
        def post(post_id):
            return {
                "id": post_id, "slug": f"post-{post_id}", "link": f"https://www.daryllswer.com/post-{post_id}/",
                "modified": "2026-01-01T00:00:00", "title": {"rendered": "Title"},
                "content": {"rendered": "Body"},
            }

        class Response:
            status = 200
            def __init__(self, data, total, pages):
                self.body = json.dumps(data).encode()
                self.headers = {"x-wp-total": str(total), "x-wp-totalpages": str(pages)}
            def getcode(self): return self.status
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, size): return self.body[:size]

        first = [post(index) for index in range(1, 101)]
        second = [post(101)]
        opener = mock.Mock()
        opener.open.side_effect = [Response(first, 101, 2), Response(second, 101, 2)]
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", opener):
            posts, headers, not_modified = DRIFT.request_posts({}, fresh=True)
        self.assertEqual(len(posts), 101)
        self.assertEqual(headers.get("X-WP-Total"), "101")
        self.assertEqual(headers.get("X-WP-TotalPages"), "2")
        self.assertFalse(not_modified)
        self.assertTrue(opener.open.call_args_list[1].args[0].full_url.endswith("&page=2"))

        invalid = [post(1), post(True)]
        opener = mock.Mock()
        opener.open.return_value = Response(invalid, 2, 1)
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", opener):
            with self.assertRaises(DRIFT.SourceObservationError):
                DRIFT.request_posts({}, fresh=True)

        opener = mock.Mock()
        opener.open.side_effect = [Response(first, 101, 2), Response(second, 102, 2)]
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", opener):
            with self.assertRaises(DRIFT.SourceObservationError):
                DRIFT.request_posts({}, fresh=True)

        opener = mock.Mock()
        opener.open.side_effect = [Response(first, 101, 2), Response([post(1)], 101, 2)]
        with mock.patch.object(DRIFT, "NO_REDIRECT_OPENER", opener):
            with self.assertRaisesRegex(DRIFT.SourceObservationError, "duplicate post ID"):
                DRIFT.request_posts({}, fresh=True)

        with self.assertRaises(DRIFT.SourceObservationError):
            DRIFT._parse_pagination({"X-WP-Total": "101", "X-WP-TotalPages": "0"})

    def test_local_oserror_is_internal_and_does_not_count(self):
        self.assertEqual(DRIFT.classify_run_exception(PermissionError("local status file denied"))[0], "internal_error")
        status = DRIFT.default_status("2026-01-01T00:00:00Z")
        status["failure"].update({"consecutive_failures": 7, "first_failure_at": "2026-01-01T00:00:00Z"})
        kind, detail = DRIFT.classify_run_exception(PermissionError("local report denied"))
        DRIFT.record_failure(status, "2026-02-01T00:00:00Z", kind, detail)
        self.assertEqual(status["failure"]["consecutive_failures"], 0)
        self.assertNotEqual(status["state"], "frozen_archive")

    def test_failed_forced_ds_recovery_preserves_frozen_sentinel(self):
        status = DRIFT.default_status("2026-01-01T00:00:00Z")
        status.update({"state": "frozen_archive", "frozen": True, "seo_state": "archive_discovery"})
        status["failure"].update({"consecutive_failures": 8, "first_failure_at": "2026-01-01T00:00:00Z"})
        DRIFT.record_failure(status, "2026-02-01T00:00:00Z", "access_restricted", "HTTP 403")
        self.assertEqual(status["state"], "frozen_archive")
        self.assertTrue(status["frozen"])
        self.assertEqual(status["failure"]["consecutive_failures"], 8)

    def test_forced_frozen_main_is_diagnostic_only_after_healthy_or_failed_probe(self):
        original_paths = (DRIFT.ROOT, DRIFT.STATUS_PATH, DRIFT.REPORT_PATH)
        original_argv = sys.argv
        try:
            for response in (
                ([{"id": 1}], {}, False),
                DRIFT.SourceObservationError("access_restricted", "HTTP 403", countable=False),
                RuntimeError("comparison fault"),
            ):
                with self.subTest(response=response):
                    with tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        DRIFT.ROOT = root
                        DRIFT.STATUS_PATH = root / "archive-status.json"
                        DRIFT.REPORT_PATH = root / "docs" / "CANONICAL_DRIFT.md"
                        status = DRIFT.default_status("2026-01-01T00:00:00Z")
                        status.update({"state": "frozen_archive", "frozen": True, "seo_state": "archive_discovery", "seo_activated_at": "2026-01-01T00:00:00Z"})
                        status["failure"].update({"consecutive_failures": 8, "first_failure_at": "2026-01-01T00:00:00Z"})
                        original = json.dumps(status, sort_keys=True).encode()
                        DRIFT.STATUS_PATH.write_bytes(original)
                        args = types.SimpleNamespace(dry_run=False, force=True, fresh=False, action_plan=None, result=None)
                        sys.argv = ["check-canonical-drift.py", "--force"]
                        with mock.patch.object(DRIFT, "parse_args", return_value=args), \
                             mock.patch.object(DRIFT, "request_posts", **({"side_effect": response} if isinstance(response, BaseException) else {"return_value": response})) as request, \
                             mock.patch.object(DRIFT, "compare_drift", side_effect=RuntimeError("must not compare")) as compare, \
                             mock.patch.object(DRIFT, "backfill_canonical_content_fingerprints") as backfill, \
                             contextlib.redirect_stdout(io.StringIO()):
                            DRIFT.main()
                        self.assertTrue(request.call_args.kwargs["fresh"])
                        compare.assert_not_called()
                        backfill.assert_not_called()
                        self.assertEqual(DRIFT.STATUS_PATH.read_bytes(), original)
                        self.assertFalse(DRIFT.REPORT_PATH.exists())
        finally:
            DRIFT.ROOT, DRIFT.STATUS_PATH, DRIFT.REPORT_PATH = original_paths
            sys.argv = original_argv

    def test_forced_external_probe_requires_explicit_recovery_authorization(self):
        class Response:
            status = 200
            headers = {}
            def getcode(self): return self.status
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return b"public article"

        class Opener:
            def open(self, *_args, **_kwargs): return Response()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "status.json"
            registry_path = root / "rights.json"
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status["seo_state"] = "archive_discovery"
            source = MONITOR.empty_source({"post_id": 7, "url": "https://origin.example/post"})
            source.update({"state": MONITOR.FROZEN_SOURCE, "frozen": True, "consecutive_failures": 8})
            status["external_sources"] = {"7": source}
            status_path.write_text(json.dumps(status), encoding="utf-8")
            registry_path.write_text(json.dumps({"7": {"external_fallback": True, "original_article_url": source["url"]}}), encoding="utf-8")
            with mock.patch.object(MONITOR, "REPORT_PATH", root / "report.md"):
                diagnostic = MONITOR.run(status_path=status_path, registry_path=registry_path, force=True,
                    post_ids={7}, now=dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc), opener=Opener())
            self.assertEqual(diagnostic["status"]["external_sources"]["7"]["state"], MONITOR.FROZEN_SOURCE)
            self.assertEqual(diagnostic["status"]["seo_state"], "archive_discovery")
            with mock.patch.object(MONITOR, "REPORT_PATH", root / "report.md"):
                recovered = MONITOR.run(status_path=status_path, registry_path=registry_path, force=True,
                    recovery_authorized=True, post_ids={7}, now=dt.datetime(2026, 2, 2, tzinfo=dt.timezone.utc), opener=Opener())
            self.assertEqual(recovered["status"]["external_sources"]["7"]["state"], MONITOR.HEALTH)

    def test_manage_external_recovery_passes_authorization_and_records_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "status.json"
            registry_path = root / "rights.json"
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            frozen = MONITOR.empty_source({"post_id": 7, "url": "https://origin.example/post"})
            frozen.update({"state": MONITOR.FROZEN_SOURCE, "frozen": True, "last_checked_at": "2026-01-01T00:00:00Z"})
            status["external_sources"] = {"7": frozen}
            status_path.write_text(json.dumps(status), encoding="utf-8")
            registry_path.write_text(json.dumps({"7": {"external_fallback": True, "original_article_url": frozen["url"]}}), encoding="utf-8")
            old_paths = (MANAGE.STATUS_PATH, MANAGE.REGISTRY_PATH)
            MANAGE.STATUS_PATH, MANAGE.REGISTRY_PATH = status_path, registry_path
            calls = {}
            recovered_status = json.loads(status_path.read_text())
            recovered_status["external_sources"]["7"].update({"state": MONITOR.HEALTH, "last_checked_at": "2026-01-02T00:00:00Z"})
            fake_monitor = types.SimpleNamespace(HEALTH=MONITOR.HEALTH, run=lambda **kwargs: (calls.update(kwargs) or {"status": recovered_status}))
            try:
                with mock.patch.object(MANAGE, "load_module", return_value=fake_monitor), contextlib.redirect_stdout(io.StringIO()):
                    MANAGE.resume_external(7)
                self.assertTrue(calls["force"])
                self.assertTrue(calls["recovery_authorized"])
                self.assertEqual(json.loads(status_path.read_text())["external_sources"]["7"]["manual_recovery"]["owner_verified"], True)
            finally:
                MANAGE.STATUS_PATH, MANAGE.REGISTRY_PATH = old_paths

    def test_manage_ds_recovery_remains_the_authorized_state_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "status.json"
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status.update({"state": "frozen_archive", "frozen": True, "seo_state": "archive_discovery"})
            status_path.write_text(json.dumps(status), encoding="utf-8")
            old_path = MANAGE.STATUS_PATH
            MANAGE.STATUS_PATH = status_path
            fake_drift = types.SimpleNamespace(request_posts=lambda _status, fresh: ([{"id": 1}], {}, False))
            try:
                with mock.patch.object(MANAGE, "load_module", return_value=fake_drift), contextlib.redirect_stdout(io.StringIO()):
                    MANAGE.resume_ds()
                recovered = json.loads(status_path.read_text())
                self.assertEqual(recovered["state"], "healthy")
                self.assertFalse(recovered["frozen"])
                self.assertEqual(recovered["seo_state"], "source_primary")
                self.assertTrue(recovered["manual_recovery"]["owner_verified"])
            finally:
                MANAGE.STATUS_PATH = old_path

    def test_external_same_host_and_missing_location_redirects_are_unverified(self):
        class Response:
            status = 302
            headers = {"Location": "/new-path"}
            def getcode(self): return self.status
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return b"redirect"
        result = MONITOR.observation("https://origin.example/post", opener=mock.Mock(open=mock.Mock(return_value=Response())))
        self.assertFalse(result["countable_failure"])
        self.assertTrue(result["promotion_blocked"])
        self.assertEqual(result["blocked_reason"], "same_host_redirect_unverified")
        Response.headers = {}
        result = MONITOR.observation("https://origin.example/post", opener=mock.Mock(open=mock.Mock(return_value=Response())))
        self.assertTrue(result["promotion_blocked"])
        self.assertIsNone(result["redirect_location"])
        Response.headers = {"Location": "https://other.example/post"}
        result = MONITOR.observation("https://origin.example/post", opener=mock.Mock(open=mock.Mock(return_value=Response())))
        self.assertEqual(result["blocked_reason"], "unexpected_host_redirect")

    def test_only_eight_qualifying_observations_over_thirty_days_freeze(self):
        status = DRIFT.default_status("2026-01-01T00:00:00Z")
        for day in range(7):
            timestamp = (dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=day * 5)).isoformat().replace("+00:00", "Z")
            DRIFT.record_failure(status, timestamp, "server_error", "HTTP 503")
        self.assertEqual(status["failure"]["consecutive_failures"], 7)
        self.assertNotEqual(status["state"], "frozen_archive")
        DRIFT.record_failure(status, "2026-02-05T00:00:00Z", "server_error", "HTTP 503")
        self.assertEqual(status["failure"]["consecutive_failures"], 8)
        self.assertEqual(status["state"], "frozen_archive")

    def test_external_blocked_and_internal_results_do_not_advance_freeze(self):
        source = {"post_id": 7, "url": "https://origin.example/post"}
        for result in (
            {"state": "degraded", "countable_failure": False, "promotion_blocked": True},
            {"state": "degraded", "countable_failure": False, "promotion_blocked": False, "blocked_reason": "internal_error"},
        ):
            item = MONITOR.empty_source(source)
            item.update({"consecutive_failures": 7, "first_failure_at": "2026-01-01T00:00:00Z"})
            MONITOR.apply_observation(item, result, "2026-02-01T00:00:00Z")
            self.assertEqual(item["consecutive_failures"], 0)
            self.assertNotEqual(item["state"], MONITOR.FROZEN_SOURCE)

    def test_external_freeze_requires_eight_qualifying_observations_and_force_recovery(self):
        item = MONITOR.empty_source({"post_id": 7, "url": "https://origin.example/post"})
        for day in range(8):
            when = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=day * 5)
            MONITOR.apply_observation(item, {"state": "degraded", "countable_failure": True}, MONITOR.iso(when))
        self.assertEqual(item["state"], MONITOR.FROZEN_SOURCE)
        self.assertFalse(MONITOR.due_for_check(item, dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc), force=False))
        self.assertTrue(MONITOR.due_for_check(item, dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc), force=True))
        MONITOR.apply_observation(item, {"state": "healthy", "countable_failure": False}, "2026-03-01T00:00:00Z", recovery_authorized=True)
        self.assertEqual(item["state"], MONITOR.HEALTH)

    def test_external_result_separates_eligibility_from_timestamp_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "status.json"
            registry_path = root / "rights.json"
            status = DRIFT.default_status("2026-01-01T00:00:00Z")
            status["seo_state"] = "archive_discovery"
            status["external_sources"] = {"7": {
                "post_id": 7, "url": "https://origin.example/post", "state": "healthy",
                "frozen": False, "consecutive_failures": 0,
            }}
            status_path.write_text(json.dumps(status), encoding="utf-8")
            registry_path.write_text(json.dumps({"7": {
                "external_fallback": True, "original_article_url": "https://origin.example/post",
            }}), encoding="utf-8")
            with mock.patch.object(MONITOR, "REPORT_PATH", root / "report.md"):
                result = MONITOR.run(status_path=status_path, registry_path=registry_path,
                    now=dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc),
                    opener=mock.Mock())
            self.assertFalse(result["eligibility_changed"])
            self.assertTrue(result["timestamp_changed"])


if __name__ == "__main__":
    unittest.main()
