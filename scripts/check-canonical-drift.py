#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Check public daryllswer.com endpoints for mirror drift."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://www.daryllswer.com"
POSTS_ENDPOINT = f"{SITE}/wp-json/wp/v2/posts?per_page=100&_embed=1"
UA = (
    "Mozilla/5.0 (compatible; daryllswer-com-archive-drift-check/1.0; "
    "+https://github.com/daryll-swer/daryllswer.com-archive)"
)
STATUS_PATH = ROOT / "archive-status.json"
REPORT_PATH = ROOT / "docs" / "CANONICAL_DRIFT.md"
UNAVAILABLE_AFTER_FAILURES = 3
FREEZE_AFTER_FAILURES = 8
FREEZE_AFTER_DAYS = 30
WP_UPLOAD_RE = re.compile(
    r"""(?:src|href)=["']([^"']*?/wp-content/uploads/[^"']+)["']""",
    re.I,
)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(value)


def normalise_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", strip_html(value)).strip().lower()


def source_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.unquote(Path(parsed.path).name).replace("\x00", "").strip()


def media_identity(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = unicodedata.normalize("NFC", urllib.parse.unquote(parsed.path)).lower()
    path = re.sub(r"-\d+x\d+(?=\.[a-z0-9]+$)", "", path)
    return f"{parsed.netloc.lower()}{path}"


def default_status(generated_at: str) -> dict:
    return {
        "version": 1,
        "canonical_site": SITE,
        "state": "healthy",
        "frozen": False,
        "created_at": generated_at,
        "updated_at": generated_at,
        "policy": {
            "degraded_after_consecutive_failures": 1,
            "canonical_unavailable_after_consecutive_failures": UNAVAILABLE_AFTER_FAILURES,
            "frozen_archive_after_consecutive_failures": FREEZE_AFTER_FAILURES,
            "frozen_archive_minimum_failure_window_days": FREEZE_AFTER_DAYS,
            "frozen_archive_noops_without_network": True,
        },
        "failure": {
            "consecutive_failures": 0,
            "first_failure_at": None,
            "last_failure_at": None,
            "last_failure_kind": None,
            "last_failure_detail": None,
        },
        "last_success_at": generated_at,
        "last_drift_hash": None,
        "http_cache": {},
        "manual_recovery": {
            "unfreeze_steps": [
                "Confirm the canonical site is again under the owner's control.",
                "Change state from frozen_archive to healthy and frozen from true to false.",
                "Reset failure.consecutive_failures to 0 and clear failure timestamps/details.",
                "Run scripts/check-canonical-drift.py --force, then validate before resuming scheduled mirroring.",
            ]
        },
    }


def load_status(generated_at: str) -> dict:
    if not STATUS_PATH.exists():
        return default_status(generated_at)
    status = load_json(STATUS_PATH)
    status.setdefault("policy", default_status(generated_at)["policy"])
    status.setdefault("failure", default_status(generated_at)["failure"])
    status.setdefault("http_cache", {})
    status.setdefault("manual_recovery", default_status(generated_at)["manual_recovery"])
    return status


def request_posts(status: dict) -> tuple[list[dict] | None, dict[str, str], bool]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
    }
    cache = status.get("http_cache", {}).get(POSTS_ENDPOINT, {})
    if cache.get("etag"):
        headers["If-None-Match"] = cache["etag"]
    if cache.get("last_modified"):
        headers["If-Modified-Since"] = cache["last_modified"]

    req = urllib.request.Request(POSTS_ENDPOINT, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read()
            resp_headers = dict(resp.headers.items())
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, dict(exc.headers.items()), True
        raise

    posts = json.loads(body.decode("utf-8"))
    if not isinstance(posts, list):
        raise RuntimeError("WordPress REST response was not a JSON list")
    pages = int(resp_headers.get("X-WP-TotalPages", "1"))
    for page in range(2, pages + 1):
        page_url = f"{POSTS_ENDPOINT}&page={page}"
        page_req = urllib.request.Request(page_url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(page_req, timeout=45) as resp:
            posts.extend(json.loads(resp.read().decode("utf-8")))
    return posts, resp_headers, False


def embedded_featured_url(post: dict) -> str | None:
    for item in post.get("_embedded", {}).get("wp:featuredmedia", []) or []:
        if isinstance(item, dict) and item.get("source_url"):
            return item["source_url"]
    return None


def live_post_summary(post: dict) -> dict:
    content_html = post.get("content", {}).get("rendered", "") or ""
    media = sorted({
        urllib.parse.urljoin(post.get("link") or SITE, match)
        for match in WP_UPLOAD_RE.findall(content_html)
    })
    return {
        "id": post.get("id"),
        "slug": post.get("slug"),
        "canonical_url": post.get("link"),
        "title": normalise_text(post.get("title", {}).get("rendered")),
        "modified": post.get("modified"),
        "featured_image_url": embedded_featured_url(post),
        "content_text_sha256": sha256_text(normalise_text(content_html)),
        "content_media_urls": media,
    }


def archived_post_summary(post_item: dict) -> dict:
    bundle = ROOT / post_item["bundle_path"]
    metadata = load_json(bundle / "metadata.json")
    rendered = (bundle / "source" / "rendered-article.html").read_text(encoding="utf-8", errors="replace")
    asset_manifest = load_json(bundle / "assets" / "manifest.json")
    uploaded_assets = sorted({
        asset.get("source_url")
        for asset in asset_manifest.get("assets", [])
        if asset.get("role") != "featured"
        and asset.get("source_url")
        and "/wp-content/uploads/" in asset.get("source_url")
    })
    featured = metadata.get("featured_image") or {}
    return {
        "id": metadata.get("id"),
        "slug": metadata.get("slug"),
        "canonical_url": metadata.get("canonical_url"),
        "title": normalise_text(metadata.get("title")),
        "modified": metadata.get("modified"),
        "featured_image_url": featured.get("source_url"),
        "content_text_sha256": sha256_text(normalise_text(rendered)),
        "content_media_urls": uploaded_assets,
    }


def compare_drift(live_posts: list[dict]) -> dict:
    archive = load_json(ROOT / "archive-manifest.json")
    live_by_url = {
        (item.get("canonical_url") or "").rstrip("/"): item
        for item in (live_post_summary(post) for post in live_posts)
        if item.get("canonical_url")
    }
    archive_by_url = {
        (item.get("canonical_url") or "").rstrip("/"): archived_post_summary(item)
        for item in archive.get("posts", [])
        if item.get("canonical_url")
    }

    live_urls = set(live_by_url)
    archive_urls = set(archive_by_url)
    new_urls = sorted(live_urls - archive_urls)
    missing_urls = sorted(archive_urls - live_urls)
    changed = []

    for url in sorted(live_urls & archive_urls):
        live = live_by_url[url]
        archived = archive_by_url[url]
        fields = []
        for key in ["slug", "title", "modified", "featured_image_url"]:
            if live.get(key) != archived.get(key):
                fields.append({
                    "field": key,
                    "archived": archived.get(key),
                    "live": live.get(key),
                })
        live_media = {media_identity(item): item for item in live.get("content_media_urls", [])}
        archived_media = {media_identity(item): item for item in archived.get("content_media_urls", [])}
        added_media = sorted(live_media[key] for key in set(live_media) - set(archived_media))
        removed_media = sorted(archived_media[key] for key in set(archived_media) - set(live_media))
        if added_media or removed_media:
            fields.append({
                "field": "content_media_urls",
                "added": added_media,
                "removed": removed_media,
            })
        if fields:
            changed.append({
                "canonical_url": url,
                "slug": live.get("slug") or archived.get("slug"),
                "fields": fields,
            })

    return {
        "live_post_count": len(live_by_url),
        "archived_post_count": len(archive_by_url),
        "new_urls": new_urls,
        "missing_urls": missing_urls,
        "changed_posts": changed,
    }


def drift_hash(drift: dict) -> str:
    return sha256_text(json.dumps(drift, ensure_ascii=False, sort_keys=True))


def update_cache(status: dict, headers: dict[str, str]) -> None:
    cache = status.setdefault("http_cache", {}).setdefault(POSTS_ENDPOINT, {})
    if headers.get("ETag"):
        cache["etag"] = headers["ETag"]
    if headers.get("Last-Modified"):
        cache["last_modified"] = headers["Last-Modified"]


def reset_failure(status: dict, generated_at: str) -> None:
    status["state"] = "healthy"
    status["frozen"] = False
    status["updated_at"] = generated_at
    status["last_success_at"] = generated_at
    status["failure"] = {
        "consecutive_failures": 0,
        "first_failure_at": None,
        "last_failure_at": None,
        "last_failure_kind": None,
        "last_failure_detail": None,
    }


def record_failure(status: dict, generated_at: str, kind: str, detail: str) -> None:
    failure = status.setdefault("failure", {})
    count = int(failure.get("consecutive_failures") or 0) + 1
    first_failure_at = failure.get("first_failure_at") or generated_at
    first_dt = parse_iso(first_failure_at)
    elapsed_days = 0
    if first_dt:
        elapsed_days = max(0, (parse_iso(generated_at) - first_dt).days)  # type: ignore[operator]

    if count >= FREEZE_AFTER_FAILURES and elapsed_days >= FREEZE_AFTER_DAYS:
        state = "frozen_archive"
        frozen = True
    elif count >= UNAVAILABLE_AFTER_FAILURES:
        state = "canonical_unavailable"
        frozen = False
    else:
        state = "degraded"
        frozen = False

    status["state"] = state
    status["frozen"] = frozen
    status["updated_at"] = generated_at
    status["failure"] = {
        "consecutive_failures": count,
        "first_failure_at": first_failure_at,
        "last_failure_at": generated_at,
        "last_failure_kind": kind,
        "last_failure_detail": detail[:500],
    }


def render_report(status: dict, drift: dict | None, note: str) -> str:
    lines = [
        "# Canonical Drift Report",
        "",
        "This report is generated by `scripts/check-canonical-drift.py` from public unauthenticated endpoints only.",
        "",
        "## State",
        "",
        f"- Canonical site: {SITE}/",
        f"- Archive state: `{status.get('state')}`",
        f"- Frozen: `{str(status.get('frozen')).lower()}`",
        f"- Note: {note}",
        "",
        "## Failure Policy",
        "",
        f"- `degraded`: after 1 failed run.",
        f"- `canonical_unavailable`: after {UNAVAILABLE_AFTER_FAILURES} consecutive failed runs.",
        f"- `frozen_archive`: after {FREEZE_AFTER_FAILURES} consecutive failed runs across at least {FREEZE_AFTER_DAYS} days.",
        "- When `frozen_archive` is set, future scheduled checks no-op before any canonical network request.",
        "",
    ]

    if status.get("failure", {}).get("consecutive_failures"):
        failure = status["failure"]
        lines.extend([
            "## Latest Failure",
            "",
            f"- Consecutive failures: {failure.get('consecutive_failures')}",
            f"- First failure: {failure.get('first_failure_at')}",
            f"- Last failure: {failure.get('last_failure_at')}",
            f"- Kind: `{failure.get('last_failure_kind')}`",
            f"- Detail: {failure.get('last_failure_detail')}",
            "",
        ])

    if drift is None:
        lines.extend(["## Drift", "", "- Not checked in this run.", ""])
    else:
        lines.extend([
            "## Drift",
            "",
            f"- Live posts: {drift['live_post_count']}",
            f"- Archived posts: {drift['archived_post_count']}",
            f"- New canonical URLs: {len(drift['new_urls'])}",
            f"- Missing/unlisted canonical URLs: {len(drift['missing_urls'])}",
            f"- Changed archived posts: {len(drift['changed_posts'])}",
            "",
        ])
        if drift["new_urls"]:
            lines.extend(["### New Canonical URLs", ""])
            lines.extend(f"- {url}" for url in drift["new_urls"])
            lines.append("")
        if drift["missing_urls"]:
            lines.extend(["### Missing Or Unlisted Canonical URLs", ""])
            lines.extend(f"- {url}" for url in drift["missing_urls"])
            lines.append("")
        if drift["changed_posts"]:
            lines.extend(["### Changed Posts", ""])
            for item in drift["changed_posts"]:
                lines.append(f"- `{item['slug']}`: {item['canonical_url']}")
                for field in item["fields"]:
                    if field["field"] == "content_media_urls":
                        if field["added"]:
                            lines.append(f"  - media added: {', '.join(source_filename_from_url(url) for url in field['added'])}")
                        if field["removed"]:
                            lines.append(f"  - media removed: {', '.join(source_filename_from_url(url) for url in field['removed'])}")
                    else:
                        lines.append(f"  - `{field['field']}` changed")
            lines.append("")

    lines.extend([
        "## Manual Recovery",
        "",
        "If the archive is frozen and a future maintainer verifies that the canonical site is healthy and still owner-controlled:",
        "",
        "1. Edit `archive-status.json` and set `state` to `healthy` and `frozen` to `false`.",
        "2. Reset `failure.consecutive_failures` to `0` and clear failure timestamps/details.",
        "3. Run `python3 scripts/check-canonical-drift.py --force`.",
        "4. Run `make validate` and `make scan-secrets` before resuming scheduled mirroring.",
        "",
    ])
    return "\n".join(lines)


def maybe_write(path: Path, text: str, dry_run: bool) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    if dry_run:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print status without writing state/report files.")
    parser.add_argument("--force", action="store_true", help="Bypass frozen_archive no-op for a manual recovery check.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = iso(now_utc())
    status_existed = STATUS_PATH.exists()
    status = load_status(generated_at)
    previous_status = json.loads(json.dumps(status))
    persist = not status_existed

    if status.get("state") == "frozen_archive" and not args.force:
        print("archive is frozen; no canonical network requests made")
        return 0

    try:
        live_posts, headers, not_modified = request_posts(status)
        update_cache(status, headers)
        reset_failure(status, generated_at)
        if not_modified:
            drift = {
                "live_post_count": status.get("last_live_post_count", 0),
                "archived_post_count": load_json(ROOT / "archive-manifest.json").get("post_count", 0),
                "new_urls": [],
                "missing_urls": [],
                "changed_posts": [],
            }
            note = "Canonical REST returned HTTP 304 Not Modified."
        else:
            if live_posts is None:
                raise RuntimeError("internal error: live_posts was unexpectedly empty")
            drift = compare_drift(live_posts)
            status["last_live_post_count"] = drift["live_post_count"]
            note = "Canonical REST was reachable and compared with the archive manifest."
        current_hash = drift_hash(drift)
        changed = bool(drift["new_urls"] or drift["missing_urls"] or drift["changed_posts"])
        previous_failure_count = int(previous_status.get("failure", {}).get("consecutive_failures") or 0)
        previous_hash = previous_status.get("last_drift_hash")
        previous_was_clean = (
            previous_status.get("state") == "healthy"
            and previous_status.get("frozen") is not True
            and previous_failure_count == 0
        )
        if changed:
            status["last_drift_hash"] = current_hash
            status["last_drift_detected_at"] = generated_at
            persist = persist or current_hash != previous_hash or not previous_was_clean
        elif status.get("last_drift_hash"):
            status["last_drift_hash"] = None
            status["last_drift_detected_at"] = None
            persist = True
        else:
            persist = persist or not previous_was_clean
        report = render_report(status, drift, note)
    except Exception as exc:
        record_failure(status, generated_at, type(exc).__name__, str(exc))
        report = render_report(status, None, "Canonical check failed; the existing archive content is preserved.")
        persist = True

    if args.dry_run:
        print(json.dumps({"state": status.get("state"), "frozen": status.get("frozen")}, indent=2))
        print(report)
        return 0

    if persist:
        write_json(STATUS_PATH, status)
        maybe_write(REPORT_PATH, report, dry_run=False)
    print(f"canonical drift state={status.get('state')} frozen={status.get('frozen')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
