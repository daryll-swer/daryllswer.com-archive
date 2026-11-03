#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Bounded, read-only audit of already archived WordPress image URLs."""

from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import multiprocessing
from concurrent.futures import FIRST_COMPLETED, wait
import os
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
DEADLINE_SECONDS = 15 * 60
REQUEST_TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5
# Inventory review: two existing Figures are about 113.94M and 110.82M pixels;
# the next largest is 23.89M. A 128M cumulative ceiling fits both while bounding
# two concurrent RGBA decodes to about 1 GiB total. The 16,384 axis cap exceeds
# the measured 9,000x12,660 maximum without admitting unbounded dimensions.
MAX_IMAGE_PIXELS = 128_000_000
MAX_IMAGE_AXIS = 16_384
MAX_IMAGE_FRAMES = 1000
ALLOWED_HOSTS = {"www.daryllswer.com", "daryllswer.com"}
APPROVED_EXTERNAL_MEDIA_URLS = {
    "https://www.ripe.net/about-us/press-centre/IPv6Chart_2015.png",
}
ALLOWED_IMAGE_FORMATS = ("PNG", "JPEG", "WEBP", "GIF", "AVIF")
FORMAT_MIME = {
    "PNG": {"image/png"},
    "JPEG": {"image/jpeg", "image/jpg"},
    "WEBP": {"image/webp"},
    "GIF": {"image/gif"},
    "AVIF": {"image/avif"},
}


def is_approved_media_url(url: str) -> bool:
    if url in APPROVED_EXTERNAL_MEDIA_URLS:
        return True
    try:
        parsed = urllib.parse.urlsplit(url)
        return (
            parsed.scheme == "https"
            and (parsed.hostname or "").lower() in ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


class SameHostRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, original_host: str):
        super().__init__()
        self.original_host = original_host.lower()
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        parsed = urllib.parse.urlsplit(newurl)
        if (
            self.count > MAX_REDIRECTS
            or parsed.scheme != "https"
            or (parsed.hostname or "").lower() != self.original_host
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise urllib.error.HTTPError(newurl, code, "unsafe media redirect", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_asset_path(bundle_path: str, asset_path: str, *, root: Path | None = None) -> Path:
    relative = Path(asset_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe media asset path: {asset_path}")
    if relative.parts[0] != "assets":
        raise ValueError(f"media asset is outside the post assets directory: {asset_path}")
    bundle = Path(bundle_path)
    if bundle.is_absolute() or ".." in bundle.parts or bundle.parts[:2] != ("content", "posts") or len(bundle.parts) != 3:
        raise ValueError(f"unsafe post bundle path: {bundle_path}")
    base = root or ROOT
    current = base
    for part in (*bundle.parts, *relative.parts):
        current /= part
        if current.is_symlink():
            raise ValueError(f"media path contains a symlink: {asset_path}")
    return base / bundle / relative


class ByteBudget:
    def __init__(self, maximum: int):
        self.maximum = maximum
        self.used = 0
        self.lock = threading.Lock()

    def reserve(self, wanted: int) -> int:
        with self.lock:
            count = min(wanted, self.maximum - self.used)
            self.used += count
            return count

    def settle(self, reserved: int, actual: int) -> None:
        with self.lock:
            self.used -= reserved - actual

    def reserve_job(self) -> int:
        with self.lock:
            amount = min(MAX_FILE_BYTES, self.maximum - self.used)
            self.used += amount
            return amount


def _read_image(url: str, audit_deadline: float, budget: ByteBudget) -> tuple[bytes, str]:
    parsed = urllib.parse.urlsplit(url)
    original_host = (parsed.hostname or "").lower()
    if not is_approved_media_url(url):
        raise ValueError("source URL must be unauthenticated HTTPS")
    request_deadline = min(audit_deadline, time.monotonic() + REQUEST_TIMEOUT_SECONDS)
    handler = SameHostRedirects(original_host)
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "daryllswer-com-archive-sync/1.0 (+https://www.daryllswer.com/)",
            "Accept": "*/*",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        },
    )
    timeout = max(0.1, request_deadline - time.monotonic())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"unexpected media HTTP status {response.status}")
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or (final.hostname or "").lower() != original_host or final.port not in (None, 443):
            raise ValueError("media response left the original HTTPS host")
        content_type = response.headers.get_content_type().lower()
        if content_type not in {mime for values in FORMAT_MIME.values() for mime in values}:
            raise ValueError(f"media response has an unsupported image MIME type ({content_type})")
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_FILE_BYTES:
            raise ValueError("media response exceeds byte limit")
        chunks = bytearray()
        while True:
            remaining_time = request_deadline - time.monotonic()
            if remaining_time <= 0:
                raise TimeoutError("media audit deadline exceeded")
            raw = getattr(getattr(response, "fp", None), "raw", None)
            sock = getattr(raw, "_sock", None)
            if sock is not None:
                sock.settimeout(min(REQUEST_TIMEOUT_SECONDS, remaining_time))
            wanted = min(65536, MAX_FILE_BYTES + 1 - len(chunks))
            reserved = budget.reserve(wanted)
            if reserved == 0:
                raise ValueError("aggregate media byte limit exceeded")
            reader = getattr(response, "read1", None) or getattr(response, "read")
            try:
                chunk = reader(reserved)
            except BaseException:
                budget.settle(reserved, 0)
                raise
            budget.settle(reserved, len(chunk))
            if not chunk:
                break
            chunks.extend(chunk)
            if len(chunks) > MAX_FILE_BYTES:
                raise ValueError("media response exceeds byte limit")
    data = bytes(chunks)
    try:
        previous_pixel_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS * 2
        try:
            image_context = Image.open(io.BytesIO(data), formats=ALLOWED_IMAGE_FORMATS)
        finally:
            Image.MAX_IMAGE_PIXELS = previous_pixel_limit
        with image_context as image:
            image_format = (image.format or "").upper()
            if image_format not in FORMAT_MIME or content_type not in FORMAT_MIME[image_format]:
                raise ValueError("image MIME type does not match decoded raster format")
            frame_count = getattr(image, "n_frames", 1)
            if frame_count > MAX_IMAGE_FRAMES:
                raise ValueError("image has too many frames")
            total_pixels = 0
            for frame in range(frame_count):
                if time.monotonic() >= request_deadline:
                    raise TimeoutError("media image validation deadline exceeded")
                image.seek(frame)
                width, height = image.size
                total_pixels += width * height
                if width < 1 or height < 1 or width > MAX_IMAGE_AXIS or height > MAX_IMAGE_AXIS or total_pixels > MAX_IMAGE_PIXELS:
                    raise ValueError("image dimensions are unsafe")
                image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("invalid or unsafe image bytes") from exc
    return data, content_type


def _fetch_process_entry(sender, url: str, deadline: float, max_bytes: int) -> None:
    try:
        data, mime = _read_image(url, deadline, ByteBudget(max_bytes))
        sender.send((data, mime, None))
    except BaseException as exc:
        sender.send((b"", "", f"{type(exc).__name__}: {exc}"))
    finally:
        sender.close()


def _fetch_image_bounded(url: str, audit_deadline: float, max_bytes: int) -> tuple[bytes, str]:
    timeout = min(REQUEST_TIMEOUT_SECONDS, max(0.01, audit_deadline - time.monotonic()))
    return run_bounded_process(_fetch_process_entry, (url, audit_deadline, max_bytes), timeout)


def _audit_media_impl(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Audit all unique archived image URLs; any failure makes the audit incomplete."""
    mapped: dict[str, list[dict[str, Any]]] = {}
    for post in manifest.get("posts", []):
        bundle = post.get("bundle_path")
        if not isinstance(bundle, str):
            raise ValueError("archive post has no bundle path")
        manifest_path = safe_asset_path(bundle, "assets/manifest.json")
        assets = json.loads(manifest_path.read_text(encoding="utf-8")).get("assets", [])
        for asset in assets:
            url = asset.get("source_url")
            asset_path = asset.get("local_path")
            if asset.get("role") not in {"featured", "inline", "linked-media"}:
                continue
            if not isinstance(url, str) or not isinstance(asset_path, str) or not asset_path.startswith(bundle + "/"):
                raise ValueError(f"archive asset mapping is malformed for post {post['id']}")
            path = Path(asset_path).relative_to(bundle).as_posix()
            local_path = safe_asset_path(bundle, path)
            if not local_path.is_file():
                raise ValueError(f"archived media file is missing: {asset_path}")
            recorded_hash = asset.get("sha256") or asset.get("checksum")
            actual_hash = hashlib.sha256(local_path.read_bytes()).hexdigest()
            if not recorded_hash or recorded_hash != actual_hash:
                raise ValueError(f"archived media hash does not match its asset manifest: {asset_path}")
            if not is_approved_media_url(url):
                raise ValueError(f"archived media URL is not approved HTTPS: {url}")
            mapped.setdefault(url, []).append({"post_id": post["id"], "asset_path": asset_path})

    start = time.monotonic()
    deadline = start + DEADLINE_SECONDS
    failures: list[dict[str, str]] = []
    updates: list[dict[str, Any]] = []
    completed_bytes = 0
    budget = ByteBudget(MAX_TOTAL_BYTES)
    futures: dict[concurrent.futures.Future, tuple[str, list[dict[str, Any]], int]] = {}
    urls = iter(mapped.items())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        def fill_slots() -> None:
            while len(futures) < 2 and time.monotonic() < deadline:
                try:
                    url, targets = next(urls)
                except StopIteration:
                    return
                reservation = budget.reserve_job()
                if reservation == 0:
                    failures.append({"source_url": url, "error": "aggregate media byte limit reached"})
                    for remaining_url, _ in urls:
                        failures.append({"source_url": remaining_url, "error": "aggregate media byte limit reached"})
                    return
                future = pool.submit(_fetch_image_bounded, url, deadline, reservation)
                futures[future] = (url, targets, reservation)

        fill_slots()
        while futures:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, _ = wait(futures, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                url, targets, reservation = futures.pop(future)
                try:
                    data, _, error = future.result()
                    if error:
                        budget.settle(reservation, reservation)
                        failures.append({"source_url": url, "error": error})
                        continue
                    budget.settle(reservation, len(data))
                    completed_bytes += len(data)
                    digest = hashlib.sha256(data).hexdigest()
                    for target in targets:
                        bundle = next(post["bundle_path"] for post in manifest["posts"] if post["id"] == target["post_id"])
                        local = safe_asset_path(bundle, Path(target["asset_path"]).relative_to(bundle).as_posix())
                        old = hashlib.sha256(local.read_bytes()).hexdigest()
                        if old != digest:
                            updates.append({"source_url": url, "post_id": target["post_id"], "asset_path": target["asset_path"], "old_sha256": old, "new_sha256": digest})
                except Exception as exc:
                    budget.settle(reservation, reservation)
                    failures.append({"source_url": url, "error": f"{type(exc).__name__}: {exc}"})
            fill_slots()
        if futures:
            for future, (url, _, reservation) in futures.items():
                future.cancel()
                budget.settle(reservation, reservation)
                failures.append({"source_url": url, "error": "TimeoutError: media audit deadline exceeded"})
            for url, _ in urls:
                failures.append({"source_url": url, "error": "TimeoutError: media audit deadline exceeded"})
    status = "complete" if not failures else "incomplete"
    return updates, {
        "status": status,
        "distinct_urls": len(mapped),
        "checked_urls": len(mapped) - len(failures),
        "changed_assets": len(updates),
        "bytes_checked": completed_bytes,
        "failures": failures,
        "elapsed_seconds": round(time.monotonic() - start, 3),
    }


def _audit_process_entry(sender, manifest: dict[str, Any], root: str) -> None:
    global ROOT
    ROOT = Path(root)
    if os.name == "posix":
        os.setsid()
    try:
        updates, audit = _audit_media_impl(manifest)
        sender.send((updates, audit))
    except BaseException as exc:
        sender.send(([], {
            "status": "incomplete",
            "distinct_urls": 0,
            "checked_urls": 0,
            "changed_assets": 0,
            "bytes_checked": 0,
            "failures": [{"source_url": "", "error": f"{type(exc).__name__}: {exc}"}],
            "elapsed_seconds": 0,
        }))
    finally:
        sender.close()


def _terminate(process: multiprocessing.Process, *, process_group: bool) -> None:
    grouped = process_group and os.name == "posix" and process.pid
    if grouped:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.is_alive():
        process.terminate()
    process.join(0.1)
    if grouped:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.is_alive():
        process.kill()
    process.join(0.1)


def run_bounded_process(target, args: tuple[Any, ...], timeout: float, *, process_group: bool = False) -> Any:
    """Return a child result or terminate all of its network/decoder work at timeout."""
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=target, args=(sender, *args), daemon=False)
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            _terminate(process, process_group=process_group)
            raise TimeoutError("media audit deadline exceeded; worker process terminated")
        result = receiver.recv()
        process.join(0.1)
        if process.is_alive():
            _terminate(process, process_group=process_group)
        return result
    finally:
        receiver.close()
        if process.is_alive():
            _terminate(process, process_group=process_group)


def audit_media(manifest: dict[str, Any], *, root: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the two-request audit behind an enforceable process deadline."""
    try:
        return run_bounded_process(
            _audit_process_entry,
            (manifest, str(root or ROOT)),
            DEADLINE_SECONDS,
            process_group=True,
        )
    except TimeoutError as exc:
        return [], {
            "status": "incomplete",
            "distinct_urls": 0,
            "checked_urls": 0,
            "changed_assets": 0,
            "bytes_checked": 0,
            "failures": [{"source_url": "", "error": str(exc)}],
            "elapsed_seconds": DEADLINE_SECONDS,
        }

