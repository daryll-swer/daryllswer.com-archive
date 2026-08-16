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
import os
import re
import sys
import tempfile
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
RETIREMENT_CONFIRMATION_MIN_DAYS = 7
ACTION_PLAN_VERSION = 2
DEFAULT_ACTION_PLAN_NAME = "canonical-drift-action-plan.json"
REST_POST_ITEM_TEMPLATE = f"{SITE}/wp-json/wp/v2/posts/{{post_id}}"
WP_UPLOAD_RE = re.compile(
    r"""(?:src|href)=["']([^"']*?/wp-content/uploads/[^"']+)["']""",
    re.I,
)
MIRRORED_WORDPRESS_MEDIA_EXTENSIONS = {
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def is_mirror_required_wordpress_media(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if "/wp-content/uploads/" not in parsed.path:
        return False
    return Path(urllib.parse.unquote(parsed.path)).suffix.lower() in MIRRORED_WORDPRESS_MEDIA_EXTENSIONS


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
        "last_live_post_summaries": [],
        "retirement_candidates": [],
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
    status.setdefault("last_live_post_summaries", [])
    status.setdefault("retirement_candidates", [])
    status.setdefault("manual_recovery", default_status(generated_at)["manual_recovery"])
    return status


def request_posts(status: dict, *, fresh: bool = False) -> tuple[list[dict] | None, dict[str, str], bool]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
    }
    if not fresh:
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


def needs_fresh_collection(status: dict, forced: bool = False) -> bool:
    """Require a body response for explicit and retirement-confirmation checks."""
    return forced or bool(status.get("retirement_candidates"))


def embedded_featured_url(post: dict) -> str | None:
    for item in post.get("_embedded", {}).get("wp:featuredmedia", []) or []:
        if isinstance(item, dict) and item.get("source_url"):
            return item["source_url"]
    return None


def live_post_summary(post: dict) -> dict:
    content_html = post.get("content", {}).get("rendered", "") or ""
    media = sorted({
        url
        for match in WP_UPLOAD_RE.findall(content_html)
        if is_mirror_required_wordpress_media(url := urllib.parse.urljoin(post.get("link") or SITE, match))
    })
    return {
        "id": post.get("id"),
        "slug": post.get("slug"),
        "canonical_url": post.get("link"),
        "title": normalise_text(post.get("title", {}).get("rendered")),
        "modified": post.get("modified"),
        "featured_image_url": embedded_featured_url(post),
        "content_text_sha256": sha256_text(normalise_text(content_html)),
        "canonical_rendered_content_sha256": sha256_text(content_html),
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
        and is_mirror_required_wordpress_media(asset.get("source_url"))
    })
    featured = metadata.get("featured_image") or {}
    source = metadata.get("source") or {}
    return {
        "id": metadata.get("id"),
        "slug": metadata.get("slug"),
        "canonical_url": metadata.get("canonical_url"),
        "title": normalise_text(metadata.get("title")),
        "modified": metadata.get("modified"),
        "featured_image_url": featured.get("source_url"),
        "content_text_sha256": sha256_text(normalise_text(rendered)),
        "canonical_rendered_content_sha256": source.get("canonical_rendered_content_sha256"),
        "content_media_urls": uploaded_assets,
        "bundle_path": post_item.get("bundle_path"),
    }


def _live_summaries(live_posts: list[dict]) -> list[dict]:
    if all("content_text_sha256" in item for item in live_posts):
        return live_posts
    return [live_post_summary(post) for post in live_posts]


def compare_drift(live_posts: list[dict]) -> dict:
    archive = load_json(ROOT / "archive-manifest.json")
    live_items = _live_summaries(live_posts)
    live_by_id = {item.get("id"): item for item in live_items if isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool)}
    archive_items = [archived_post_summary(item) for item in archive.get("posts", [])]
    archive_by_id = {item.get("id"): item for item in archive_items if isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool)}
    if len(live_by_id) != len(live_items):
        raise RuntimeError("WordPress REST returned a post without an immutable integer ID")
    if len(archive_by_id) != len(archive_items):
        raise RuntimeError("archive-manifest.json contains a post without an immutable integer ID")

    live_ids = set(live_by_id)
    archive_ids = set(archive_by_id)
    new_ids = sorted(live_ids - archive_ids)
    missing_ids = sorted(archive_ids - live_ids)
    new_posts = [live_by_id[post_id] for post_id in new_ids]
    missing_posts = [archive_by_id[post_id] for post_id in missing_ids]
    relocated_posts = []
    changed = []

    for post_id in sorted(live_ids & archive_ids):
        live = live_by_id[post_id]
        archived = archive_by_id[post_id]
        live_url = (live.get("canonical_url") or "").rstrip("/")
        archived_url = (archived.get("canonical_url") or "").rstrip("/")
        if live_url != archived_url:
            relocated_posts.append({
                "id": post_id,
                "from": archived_url,
                "to": live_url,
                "slug": live.get("slug") or archived.get("slug"),
            })
        fields = []
        for key in ["slug", "title", "modified", "featured_image_url"]:
            if live.get(key) != archived.get(key):
                fields.append({
                    "field": key,
                    "archived": archived.get(key),
                    "live": live.get(key),
                })
        archived_content_hash = archived.get("canonical_rendered_content_sha256")
        if archived_content_hash and live.get("canonical_rendered_content_sha256") != archived_content_hash:
            fields.append({"field": "canonical_rendered_content_sha256"})
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
                "id": post_id,
                "canonical_url": live_url or archived_url,
                "slug": live.get("slug") or archived.get("slug"),
                "expected": {
                    key: live.get(key)
                    for key in [
                        "id",
                        "slug",
                        "canonical_url",
                        "modified",
                        "featured_image_url",
                        "canonical_rendered_content_sha256",
                    ]
                },
                "fields": fields,
            })

    return {
        "live_post_count": len(live_by_id),
        "archived_post_count": len(archive_by_id),
        "new_ids": new_ids,
        "missing_ids": missing_ids,
        "new_posts": new_posts,
        "missing_posts": missing_posts,
        "relocated_posts": relocated_posts,
        "new_urls": sorted((item.get("canonical_url") or "").rstrip("/") for item in new_posts),
        "missing_urls": sorted((item.get("canonical_url") or "").rstrip("/") for item in missing_posts),
        "changed_posts": changed,
    }


def backfill_canonical_content_fingerprints(drift: dict, live_posts: list[dict]) -> list[int]:
    """Record missing raw canonical-body fingerprints after a clean comparison.

    Existing bundles created before automatic reconciliation did not retain the
    raw canonical body checksum because their stored source HTML had archive
    CTA filtering applied. A clean, healthy REST comparison is the only safe
    time to establish that baseline: no outstanding mutation can be hidden.
    """
    if (
        drift.get("new_ids")
        or drift.get("missing_ids")
        or drift.get("relocated_posts")
        or drift.get("changed_posts")
    ):
        return []

    live_by_id = {item.get("id"): item for item in _live_summaries(live_posts)}
    archive = load_json(ROOT / "archive-manifest.json")
    updated_ids = []
    for post in archive.get("posts") or []:
        post_id = post.get("id")
        live = live_by_id.get(post_id)
        fingerprint = live.get("canonical_rendered_content_sha256") if isinstance(live, dict) else None
        if not isinstance(post_id, int) or not isinstance(fingerprint, str):
            continue
        bundle_path = Path(str(post.get("bundle_path") or ""))
        if (
            bundle_path.is_absolute()
            or ".." in bundle_path.parts
            or bundle_path.parts[:2] != ("content", "posts")
            or len(bundle_path.parts) != 3
        ):
            raise RuntimeError(f"cannot backfill canonical fingerprint for post ID {post_id}: unsafe bundle path")
        bundle = ROOT / bundle_path
        current = ROOT
        for component in bundle_path.parts:
            current /= component
            if current.is_symlink():
                raise RuntimeError(f"cannot backfill canonical fingerprint for post ID {post_id}: bundle path is symlinked")
        metadata_path = bundle / "metadata.json"
        if not metadata_path.is_file() or metadata_path.is_symlink():
            raise RuntimeError(f"cannot backfill canonical fingerprint for post ID {post_id}: metadata is unavailable")
        metadata = load_json(metadata_path)
        if metadata.get("id") != post_id:
            raise RuntimeError(f"cannot backfill canonical fingerprint for post ID {post_id}: metadata ID mismatch")
        source = metadata.get("source")
        if not isinstance(source, dict):
            raise RuntimeError(f"cannot backfill canonical fingerprint for post ID {post_id}: source metadata is malformed")
        if source.get("canonical_rendered_content_sha256"):
            continue
        source["canonical_rendered_content_sha256"] = fingerprint
        write_json(metadata_path, metadata)
        updated_ids.append(post_id)
    return updated_ids


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
    status["retirement_candidates"] = []
    status["updated_at"] = generated_at
    status["failure"] = {
        "consecutive_failures": count,
        "first_failure_at": first_failure_at,
        "last_failure_at": generated_at,
        "last_failure_kind": kind,
        "last_failure_detail": detail[:500],
    }


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # pragma: no cover - urllib hook
        return None


NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def endpoint_status(url: str) -> dict:
    """Return direct endpoint evidence without following redirects."""
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with NO_REDIRECT_OPENER.open(request, timeout=45) as response:
            code = int(getattr(response, "status", response.getcode()))
            return {"url": url, "status": code, "passed": code in {404, 410}}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": int(exc.code), "passed": exc.code in {404, 410}}
    except Exception as exc:
        return {"url": url, "status": None, "passed": False, "error": f"{type(exc).__name__}: {exc}"}


def retirement_endpoint_evidence(missing_posts: list[dict]) -> dict | None:
    if len(missing_posts) != 1:
        return None
    item = missing_posts[0]
    post_id = item.get("id")
    canonical_url = item.get("canonical_url")
    if not isinstance(post_id, int) or not isinstance(canonical_url, str):
        return None
    parsed = urllib.parse.urlsplit(canonical_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"www.daryllswer.com", "daryllswer.com"}:
        return None
    rest = endpoint_status(REST_POST_ITEM_TEMPLATE.format(post_id=post_id))
    route = endpoint_status(canonical_url)
    return {
        "rest": rest,
        "canonical_route": route,
        "passed": rest.get("passed") is True and route.get("passed") is True,
    }


def _candidate_matches(candidate: dict, missing: dict) -> bool:
    return (
        candidate.get("id") == missing.get("id")
        and candidate.get("canonical_url") == missing.get("canonical_url")
        and candidate.get("bundle_path") == missing.get("bundle_path")
    )


def update_retirement_candidate(
    status: dict,
    drift: dict,
    evidence: dict | None,
    generated_at: str,
) -> dict | None:
    """Record only a currently provable, single-post retirement candidate."""
    exact_candidate = (
        len(drift.get("missing_posts", [])) == 1
        and drift.get("live_post_count") == drift.get("archived_post_count", 0) - 1
        and not drift.get("new_ids")
        and not drift.get("relocated_posts")
        and not drift.get("changed_posts")
    )
    existing = status.get("retirement_candidates") or []
    if not exact_candidate:
        status["retirement_candidates"] = []
        return None

    missing = drift["missing_posts"][0]
    current = existing[0] if len(existing) == 1 and _candidate_matches(existing[0], missing) else None
    if not evidence or evidence.get("passed") is not True:
        status["retirement_candidates"] = []
        return None

    candidate = dict(current or {})
    confirmations = list(candidate.get("healthy_confirmations") or [])
    last_confirmation = parse_iso(confirmations[-1].get("observed_at")) if confirmations else None
    now = parse_iso(generated_at)
    if not last_confirmation or (now and (now - last_confirmation).total_seconds() >= RETIREMENT_CONFIRMATION_MIN_DAYS * 86400):
        confirmations.append({
            "observed_at": generated_at,
            "rest_status": evidence["rest"].get("status"),
            "canonical_route_status": evidence["canonical_route"].get("status"),
        })
    candidate.update({
        "id": missing.get("id"),
        "slug": missing.get("slug"),
        "canonical_url": missing.get("canonical_url"),
        "bundle_path": missing.get("bundle_path"),
        "healthy_confirmations": confirmations,
        "confirmation_count": len(confirmations),
        "last_evidence": evidence,
    })
    status["retirement_candidates"] = [candidate]
    return candidate


def candidate_is_eligible(candidate: dict | None, evidence: dict | None, generated_at: str) -> bool:
    if not candidate or not evidence or evidence.get("passed") is not True:
        return False
    confirmations = candidate.get("healthy_confirmations") or []
    if len(confirmations) < 2:
        return False
    first = parse_iso(confirmations[0].get("observed_at"))
    last = parse_iso(confirmations[-1].get("observed_at"))
    now = parse_iso(generated_at)
    return bool(first and last and now and (last - first).total_seconds() >= RETIREMENT_CONFIRMATION_MIN_DAYS * 86400)


def action_plan_path(value: str | None) -> Path:
    if value:
        path = Path(value).expanduser()
    else:
        directory = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
        path = directory / DEFAULT_ACTION_PLAN_NAME
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError(f"action plan must be outside repository root: {resolved}")


def write_action_plan(path: Path, plan: dict) -> None:
    path = action_plan_path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_action_plan(
    status: dict,
    drift: dict | None,
    generated_at: str,
    evidence: dict | None = None,
    note: str = "",
) -> dict:
    plan = {
        "version": ACTION_PLAN_VERSION,
        "generated_at": generated_at,
        "canonical_healthy": status.get("state") == "healthy" and status.get("frozen") is not True,
        "archive_state": status.get("state"),
        "archive_manifest_sha256": sha256_file(ROOT / "archive-manifest.json") if (ROOT / "archive-manifest.json").exists() else None,
        "drift": drift or {},
        "retirement": {
            "candidate": (status.get("retirement_candidates") or [None])[0],
            "endpoint_evidence": evidence,
            "eligible": False,
        },
        "sync_posts": [],
        "update_posts": [],
        "action": "none",
        "reason": note or "No automatic reconciliation action is safe.",
    }
    if not drift or not plan["canonical_healthy"]:
        return plan

    candidate = plan["retirement"]["candidate"]
    eligible = (
        len(drift.get("missing_posts", [])) == 1
        and drift.get("live_post_count") == drift.get("archived_post_count", 0) - 1
        and not drift.get("new_ids")
        and not drift.get("relocated_posts")
        and not drift.get("changed_posts")
        and candidate_is_eligible(candidate, evidence, generated_at)
    )
    plan["retirement"]["eligible"] = eligible
    if eligible:
        plan["action"] = "retire"
        plan["reason"] = "Exactly one ID-based retirement has two healthy confirmations at least seven days apart and direct 404/410 evidence."
        return plan

    new_posts = sorted(drift.get("new_posts", []), key=lambda item: int(item.get("id", 0)))
    changed_posts = sorted(drift.get("changed_posts", []), key=lambda item: int(item.get("id", 0)))
    if (
        len(new_posts) <= 1
        and not drift.get("missing_ids")
        and not drift.get("relocated_posts")
        and (new_posts or changed_posts)
    ):
        plan["sync_posts"] = new_posts
        plan["update_posts"] = changed_posts
        plan["action"] = "sync"
        plan["reason"] = (
            "One new immutable WordPress ID at most, plus every verified changed existing post, "
            "will be mirrored as one atomic reconciliation batch."
        )
    return plan


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
        "## Reconciliation Policy",
        "",
        "- A healthy run may synchronise every detected changed existing post as one all-or-nothing batch.",
        "- The same batch may include at most one newly published or restored post.",
        "- Relocations and missing-post anomalies block automatic synchronisation; retirement has separate two-confirmation safeguards.",
        "- Canonical outages never update or remove archive content.",
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
            f"- Relocated post IDs: {len(drift.get('relocated_posts', []))}",
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
        if drift.get("relocated_posts"):
            lines.extend(["### Relocated Post IDs", ""])
            lines.extend(
                f"- `{item['id']}`: {item['from']} -> {item['to']}"
                for item in drift["relocated_posts"]
            )
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
    parser.add_argument("--fresh", action="store_true", help="Bypass conditional REST validators for a fresh comparison.")
    parser.add_argument(
        "--action-plan",
        help="Write the one-run reconciliation action plan outside the repository.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = iso(now_utc())
    status_existed = STATUS_PATH.exists()
    status = load_status(generated_at)
    previous_status = json.loads(json.dumps(status))
    persist = not status_existed
    action_plan = None

    if status.get("state") == "frozen_archive" and not args.force:
        action_plan = build_action_plan(
            status,
            None,
            generated_at,
            note="Archive is frozen; no canonical network request was made.",
        )
        if args.action_plan:
            write_action_plan(action_plan_path(args.action_plan), action_plan)
        print("archive is frozen; no canonical network requests made")
        return 0

    try:
        live_posts, headers, not_modified = request_posts(
            status,
            fresh=needs_fresh_collection(status, args.fresh),
        )
        update_cache(status, headers)
        reset_failure(status, generated_at)
        if not_modified:
            cached = status.get("last_live_post_summaries") or []
            if not cached:
                raise RuntimeError("canonical REST returned HTTP 304 but no cached post summaries are available")
            drift = compare_drift(cached)
            note = "Canonical REST returned HTTP 304 Not Modified."
        else:
            if live_posts is None:
                raise RuntimeError("internal error: live_posts was unexpectedly empty")
            drift = compare_drift(live_posts)
            baseline_ids = backfill_canonical_content_fingerprints(drift, live_posts)
            status["last_live_post_count"] = drift["live_post_count"]
            status["last_live_post_summaries"] = _live_summaries(live_posts)
            note = "Canonical REST was reachable and compared with the archive manifest."
            if baseline_ids:
                note += f" Recorded canonical content-fingerprint baselines for {len(baseline_ids)} post(s)."
        status["last_live_post_count"] = drift["live_post_count"]
        evidence = retirement_endpoint_evidence(drift.get("missing_posts", []))
        previous_candidates = json.loads(json.dumps(status.get("retirement_candidates") or []))
        candidate = update_retirement_candidate(status, drift, evidence, generated_at)
        current_hash = drift_hash(drift)
        changed = bool(
            drift["new_ids"]
            or drift["missing_ids"]
            or drift.get("relocated_posts")
            or drift["changed_posts"]
        )
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
        persist = persist or previous_candidates != (status.get("retirement_candidates") or [])
        persist = persist or previous_status.get("last_live_post_summaries") != status.get("last_live_post_summaries")
        report = render_report(status, drift, note)
        action_plan = build_action_plan(status, drift, generated_at, evidence, note)
    except Exception as exc:
        record_failure(status, generated_at, type(exc).__name__, str(exc))
        report = render_report(status, None, "Canonical check failed; the existing archive content is preserved.")
        persist = True
        action_plan = build_action_plan(
            status,
            None,
            generated_at,
            note="Canonical check failed; no reconciliation action is safe.",
        )

    if action_plan is None:  # pragma: no cover - defensive guard
        action_plan = build_action_plan(status, None, generated_at, note="No action plan was produced.")
    if args.action_plan:
        write_action_plan(action_plan_path(args.action_plan), action_plan)
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
