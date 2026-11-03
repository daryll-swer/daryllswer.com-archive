from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from PIL import Image
from media_audit import MAX_FILE_BYTES, audit_media, safe_asset_path
import media_audit


def slow_child(sender, value: str) -> None:
    time.sleep(5)
    sender.send(value)


def echo_child(sender, value: str) -> None:
    sender.send(value)


def nested_child(sender, value: str) -> None:
    sender.send(media_audit.run_bounded_process(echo_child, (value,), 2))


def fake_media_fetch(sender) -> None:
    sender.send((png_bytes("blue"), "image/png", None))


def nonempty_audit_child(sender, root: str, manifest: dict) -> None:
    media_audit.ROOT = Path(root)

    def fetch(url: str, deadline: float, max_bytes: int):
        return media_audit.run_bounded_process(fake_media_fetch, (), 2)

    media_audit._fetch_image_bounded = fetch
    sender.send(media_audit._audit_media_impl(manifest))


def png_bytes(colour: str = "red", size: tuple[int, int] = (3, 2)) -> bytes:
    image = Image.new("RGB", size, colour)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class MediaAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patcher = mock.patch.object(media_audit, "ROOT", self.root)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.temp.cleanup()

    def add_asset(self, post_id: int, url: str, data: bytes, name: str = "media.png") -> dict:
        bundle = f"content/posts/2026-01-0{post_id}-post{post_id}"
        target = self.root / bundle / "assets" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record = {
            "source_url": url,
            "local_path": f"{bundle}/assets/{name}",
            "role": "inline",
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        manifest_path = self.root / bundle / "assets" / "manifest.json"
        manifest_path.write_text(json.dumps({"post_id": post_id, "assets": [record]}), encoding="utf-8")
        return {"id": post_id, "bundle_path": bundle}

    def fetch_bytes(self, body: bytes, content_type: str, url: str = "https://www.daryllswer.com/wp-content/uploads/image.png") -> tuple[bytes, str]:
        class Headers:
            def get_content_type(self) -> str:
                return content_type.split(";", 1)[0]

            def get(self, name: str):
                return None

        class Response:
            status = 200
            headers = Headers()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def geturl(self) -> str:
                return url

            def read1(self, size: int) -> bytes:
                nonlocal body
                result, body = body[:size], body[size:]
                return result

        class Opener:
            def open(self, request, timeout):
                if request.get_method() != "GET":
                    raise AssertionError("media audit must issue a full GET")
                if request.get_header("If-none-match") or request.get_header("If-modified-since"):
                    raise AssertionError("media audit must not use REST conditional validators")
                if not request.get_header("Cache-control"):
                    raise AssertionError("media audit must request cache revalidation")
                if request.get_header("Accept") != "*/*":
                    raise AssertionError("media audit must match synchroniser representation negotiation")
                if request.get_header("User-agent") != "daryllswer-com-archive-sync/1.0 (+https://www.daryllswer.com/)":
                    raise AssertionError("media audit must match synchroniser user agent")
                return Response()

        with mock.patch.object(media_audit.urllib.request, "build_opener", return_value=Opener()):
            return media_audit._read_image(url, time.monotonic() + 2, media_audit.ByteBudget(1024 * 1024))

    def test_same_url_is_fetched_once_and_updates_every_shared_asset(self) -> None:
        url = "https://www.daryllswer.com/wp-content/uploads/shared.png"
        old = png_bytes("red")
        new = png_bytes("blue")
        posts = [self.add_asset(1, url, old), self.add_asset(2, url, old)]
        with mock.patch.object(media_audit, "_fetch_image_bounded", return_value=(new, "image/png", None)) as fetch:
            updates, audit = media_audit._audit_media_impl({"posts": posts})
        fetch.assert_called_once()
        self.assertEqual(audit["status"], "complete")
        self.assertEqual(len(updates), 2)
        self.assertEqual({item["post_id"] for item in updates}, {1, 2})
        self.assertTrue(all("bytes" not in item for item in updates))

    def test_unchanged_bytes_produce_no_updates(self) -> None:
        url = "https://www.daryllswer.com/wp-content/uploads/same.png"
        data = png_bytes()
        posts = [self.add_asset(1, url, data)]
        with mock.patch.object(media_audit, "_fetch_image_bounded", return_value=(data, "image/png", None)):
            updates, audit = media_audit._audit_media_impl({"posts": posts})
        self.assertEqual(updates, [])
        self.assertEqual(audit["changed_assets"], 0)
        self.assertEqual(audit["bytes_checked"], len(data))

    def test_mixed_media_failure_marks_whole_audit_incomplete(self) -> None:
        posts = [
            self.add_asset(1, "https://www.daryllswer.com/wp-content/uploads/ok.png", png_bytes()),
            self.add_asset(2, "https://www.daryllswer.com/wp-content/uploads/bad.png", png_bytes()),
        ]
        def fetch(url: str, deadline: float, max_bytes: int):
            if url.endswith("bad.png"):
                return b"", "", "ValueError: HTTP 403"
            return png_bytes("blue"), "image/png", None
        with mock.patch.object(media_audit, "_fetch_image_bounded", side_effect=fetch):
            updates, audit = media_audit._audit_media_impl({"posts": posts})
        self.assertEqual(audit["status"], "incomplete")
        self.assertEqual(len(audit["failures"]), 1)
        self.assertEqual(len(updates), 1)  # Observation is retained; the action planner must clear it.

    def test_unapproved_host_and_nondefault_port_are_rejected(self) -> None:
        for url in (
            "https://example.com/wp-content/uploads/a.png",
            "https://www.daryllswer.com:444/wp-content/uploads/a.png",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                media_audit._read_image(url, 10**12, media_audit.ByteBudget(100))

    def test_real_fetch_path_decodes_allowlisted_png_with_matching_mime(self) -> None:
        expected = png_bytes()
        body, mime = self.fetch_bytes(expected, "image/png")
        self.assertEqual(body, expected)
        self.assertEqual(mime, "image/png")

    def test_real_fetch_path_rejects_html_malformed_and_unsafe_formats(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported image MIME"):
            self.fetch_bytes(b"<html>denied</html>", "text/html")
        with self.assertRaisesRegex(ValueError, "invalid or unsafe image"):
            self.fetch_bytes(b"not an image", "image/png")
        with self.assertRaisesRegex(ValueError, "unsupported image MIME"):
            self.fetch_bytes(b"%!PS-Adobe-3.0 EPSF-3.0", "application/postscript")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.fetch_bytes(png_bytes(), "image/jpeg")

    def test_real_fetch_path_enforces_download_byte_limit(self) -> None:
        with mock.patch.object(media_audit, "MAX_FILE_BYTES", 16):
            with self.assertRaisesRegex(ValueError, "exceeds byte limit"):
                self.fetch_bytes(b"x" * 17, "image/png")

    def test_dimension_and_axis_ceiling_rejects_unsafe_raster(self) -> None:
        with mock.patch.object(media_audit, "MAX_IMAGE_PIXELS", 5):
            with self.assertRaisesRegex(ValueError, "dimensions are unsafe"):
                self.fetch_bytes(png_bytes(size=(3, 2)), "image/png")
        with mock.patch.object(media_audit, "MAX_IMAGE_AXIS", 2):
            with self.assertRaisesRegex(ValueError, "dimensions are unsafe"):
                self.fetch_bytes(png_bytes(size=(3, 2)), "image/png")

    def test_exact_reviewed_ripe_image_url_is_approved_not_the_host(self) -> None:
        ripe_url = "https://www.ripe.net/about-us/press-centre/IPv6Chart_2015.png"
        self.assertTrue(media_audit.is_approved_media_url(ripe_url))
        self.assertFalse(media_audit.is_approved_media_url("https://www.ripe.net/about-us/press-centre/other.png"))
        body, mime = self.fetch_bytes(png_bytes("blue"), "image/png", ripe_url)
        self.assertEqual(mime, "image/png")
        self.assertTrue(body.startswith(b"\x89PNG"))

    def test_oversized_archived_file_is_rejected_before_network(self) -> None:
        url = "https://www.daryllswer.com/wp-content/uploads/large.png"
        post = self.add_asset(1, url, png_bytes())
        path = safe_asset_path(post["bundle_path"], "assets/media.png")
        with path.open("ab") as stream:
            stream.truncate(MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "hash does not match"):
            media_audit._audit_media_impl({"posts": [post]})

    def test_asset_symlink_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            safe_asset_path("content/posts/2026-01-01-safe", "assets/../../outside")

    def test_media_audit_process_is_killed_at_absolute_deadline(self) -> None:
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "worker process terminated"):
            media_audit.run_bounded_process(slow_child, ("ignored",), 0.1)
        self.assertLess(time.monotonic() - started, 3)

    def test_audit_worker_can_spawn_bounded_request_child(self) -> None:
        self.assertEqual(media_audit.run_bounded_process(nested_child, ("nested-ok",), 4), "nested-ok")

    def test_audit_entrypoint_runs_clean_empty_inventory_in_bounded_process(self) -> None:
        updates, audit = audit_media({"posts": []}, root=self.root)
        self.assertEqual(updates, [])
        self.assertEqual(audit["status"], "complete")

    def test_nonempty_audit_runs_through_nested_process_and_updates_shared_path(self) -> None:
        url = "https://www.daryllswer.com/wp-content/uploads/process.png"
        post = self.add_asset(1, url, png_bytes("red"))
        updates, audit = media_audit.run_bounded_process(
            nonempty_audit_child,
            (str(self.root), {"posts": [post]}),
            10,
        )
        self.assertEqual(audit["status"], "complete")
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["new_sha256"], hashlib.sha256(png_bytes("blue")).hexdigest())


if __name__ == "__main__":
    unittest.main()
