#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Bounded, unauthenticated health checks for opted-in external originals."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "archive-status.json"
REGISTRY_PATH = ROOT / "content" / "rights-registry.json"
REPORT_PATH = ROOT / "docs" / "EXTERNAL_SOURCE_STATUS.md"
UA = "daryllswer-com-archive-source-monitor/1.0 (+https://github.com/daryll-swer/daryllswer.com-archive)"
HEALTH = "healthy"
DEGRADED = "degraded"
SOURCE_UNAVAILABLE = "source_unavailable"
FROZEN_SOURCE = "frozen_source"
INTERVAL_DAYS = 7
UNAVAILABLE_AFTER_FAILURES = 3
FREEZE_AFTER_FAILURES = 8
FREEZE_AFTER_DAYS = 30
MAX_BODY_BYTES = 65536


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(value: dt.datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def valid_public_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password


def active_external_sources(registry: dict) -> dict[str, dict]:
    sources: dict[str, dict] = {}
    for post_id, record in sorted(registry.items(), key=lambda item: int(item[0])):
        if not isinstance(record, dict) or record.get("external_fallback") is not True:
            continue
        url = record.get("original_article_url")
        if not valid_public_url(url):
            raise ValueError(f"external source for post {post_id} must be a public HTTP(S) URL without credentials")
        sources[str(post_id)] = {"post_id": int(post_id), "url": url}
    return sources


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # pragma: no cover - urllib hook
        return None


NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def error_kind(exc: Exception) -> str:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError):
        return "tls"
    if isinstance(reason, socket.gaierror) or isinstance(exc, socket.gaierror):
        return "dns"
    return "network"


def observation(url: str, *, opener=NO_REDIRECT_OPENER) -> dict:
    """Make exactly one bounded public request without following redirects."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Range": f"bytes=0-{MAX_BODY_BYTES - 1}"},
        method="GET",
    )
    expected_host = urllib.parse.urlsplit(url).netloc.lower()
    try:
        with opener.open(request, timeout=45) as response:
            status = int(getattr(response, "status", response.getcode()))
            response.read(MAX_BODY_BYTES)
            if 200 <= status < 300:
                return {"url": url, "status": status, "state": HEALTH, "countable_failure": False}
            if 300 <= status < 400:
                location = response.headers.get("Location", "")
                target = urllib.parse.urljoin(url, location)
                target_host = urllib.parse.urlsplit(target).netloc.lower()
                if target_host != expected_host:
                    return {
                        "url": url,
                        "status": status,
                        "state": DEGRADED,
                        "countable_failure": False,
                        "promotion_blocked": True,
                        "blocked_reason": "unexpected_host_redirect",
                        "redirect_location": target,
                    }
                return {"url": url, "status": status, "state": HEALTH, "countable_failure": False, "redirect_location": target}
            return {
                "url": url,
                "status": status,
                "state": DEGRADED,
                "countable_failure": status in {404, 410} or 500 <= status < 600,
                "promotion_blocked": not (status in {404, 410} or 500 <= status < 600),
                "blocked_reason": "unexpected_status" if not (status in {404, 410} or 500 <= status < 600) else None,
            }
    except urllib.error.HTTPError as exc:
        try:
            status = int(exc.code)
            location = exc.headers.get("Location", "")
            if 300 <= status < 400:
                target = urllib.parse.urljoin(url, location)
                if urllib.parse.urlsplit(target).netloc.lower() != expected_host:
                    return {
                        "url": url,
                        "status": status,
                        "state": DEGRADED,
                        "countable_failure": False,
                        "promotion_blocked": True,
                        "blocked_reason": "unexpected_host_redirect",
                        "redirect_location": target,
                    }
                return {"url": url, "status": status, "state": HEALTH, "countable_failure": False, "redirect_location": target}
            blocked = status in {401, 403, 429} or (400 <= status < 500 and status not in {404, 410})
            return {
                "url": url,
                "status": status,
                "state": DEGRADED,
                "countable_failure": not blocked and (status in {404, 410} or 500 <= status < 600),
                "promotion_blocked": blocked,
                "blocked_reason": "access_blocked" if blocked else None,
            }
        finally:
            exc.close()
    except Exception as exc:
        return {
            "url": url,
            "status": None,
            "state": DEGRADED,
            "countable_failure": True,
            "promotion_blocked": False,
            "blocked_reason": error_kind(exc),
            "error": f"{type(exc).__name__}: {exc}",
        }


def empty_source(item: dict) -> dict:
    return {
        "post_id": item["post_id"],
        "url": item["url"],
        "state": DEGRADED,
        "frozen": False,
        "promotion_blocked": False,
        "consecutive_failures": 0,
        "last_checked_at": None,
        "last_success_at": None,
        "first_failure_at": None,
        "last_failure_at": None,
        "last_observation": None,
    }


def apply_observation(item: dict, result: dict, observed_at: str) -> None:
    item["last_checked_at"] = observed_at
    item["last_observation"] = result
    item["promotion_blocked"] = result.get("promotion_blocked") is True
    if result.get("state") == HEALTH:
        item.update({
            "state": HEALTH,
            "frozen": False,
            "consecutive_failures": 0,
            "first_failure_at": None,
            "last_failure_at": None,
            "last_success_at": observed_at,
        })
        return
    if not result.get("countable_failure"):
        if item.get("state") == FROZEN_SOURCE:
            # A forced recovery probe that is blocked is not proof the frozen
            # source recovered. Keep its no-request sentinel intact.
            item.update({"promotion_blocked": True})
            return
        item.update({
            "state": DEGRADED,
            "frozen": False,
            "consecutive_failures": 0,
            "first_failure_at": None,
            "last_failure_at": None,
        })
        return
    count = int(item.get("consecutive_failures") or 0) + 1
    first_failure = item.get("first_failure_at") or observed_at
    first_dt = parse_iso(first_failure)
    observed_dt = parse_iso(observed_at)
    elapsed_days = (observed_dt - first_dt).days if first_dt and observed_dt else 0
    state = FROZEN_SOURCE if count >= FREEZE_AFTER_FAILURES and elapsed_days >= FREEZE_AFTER_DAYS else (
        SOURCE_UNAVAILABLE if count >= UNAVAILABLE_AFTER_FAILURES else DEGRADED
    )
    item.update({
        "state": state,
        "frozen": state == FROZEN_SOURCE,
        "consecutive_failures": count,
        "first_failure_at": first_failure,
        "last_failure_at": observed_at,
    })


def due_for_check(item: dict, now: dt.datetime, *, force: bool) -> bool:
    if item.get("state") == FROZEN_SOURCE and not force:
        return False
    if force:
        return True
    last = parse_iso(item.get("last_checked_at"))
    if last is None:
        return True
    return now - last >= dt.timedelta(days=INTERVAL_DAYS)


def render_report(status: dict) -> str:
    lines = [
        "# External Source Status",
        "",
        "Generated by `scripts/external_source_monitor.py` from one bounded public request per due opted-in source.",
        "",
        f"- Archive SEO state: `{status.get('seo_state')}`",
        f"- DS source state: `{status.get('state')}`",
        "",
        "## Sources",
        "",
    ]
    sources = status.get("external_sources") or {}
    if not sources:
        lines.append("- No external fallback sources are opted in.")
    for post_id, item in sorted(sources.items(), key=lambda pair: int(pair[0])):
        lines.extend([
            f"- Post `{post_id}`: `{item.get('state')}`; fallback promotion blocked=`{str(item.get('promotion_blocked')).lower()}`; last checked `{item.get('last_checked_at')}`.",
            f"  - Public source: {item.get('url')}",
        ])
    lines.extend([
        "",
        "`healthy` excludes the post from archive discovery while the DS source is frozen. "
        "Only `frozen_source` permits an opted-in fallback post to become eligible.",
        "",
    ])
    return "\n".join(lines)


def run(*, status_path: Path = STATUS_PATH, registry_path: Path = REGISTRY_PATH, force: bool = False, post_ids: set[int] | None = None, now: dt.datetime | None = None, opener=NO_REDIRECT_OPENER) -> dict:
    now = now or now_utc()
    observed_at = iso(now)
    status = load_json(status_path)
    before = copy.deepcopy(status)
    status["version"] = max(int(status.get("version") or 1), 2)
    status.setdefault("external_sources", {})
    status.setdefault("policy", {})
    status["policy"].setdefault("external_source_interval_days", INTERVAL_DAYS)
    status["policy"].setdefault("external_source_unavailable_after_consecutive_failures", UNAVAILABLE_AFTER_FAILURES)
    status["policy"].setdefault("external_source_frozen_after_consecutive_failures", FREEZE_AFTER_FAILURES)
    status["policy"].setdefault("external_source_frozen_minimum_failure_window_days", FREEZE_AFTER_DAYS)
    if status.get("seo_state") not in {"source_primary", "archive_discovery"}:
        status["seo_state"] = "archive_discovery" if status.get("state") == "frozen_archive" else "source_primary"
    if status.get("state") == "frozen_archive" and status.get("seo_state") == "source_primary":
        status["seo_state"] = "archive_discovery"
        status["seo_activated_at"] = status.get("seo_activated_at") or status.get("updated_at") or observed_at
    status.setdefault("seo_activated_at", None)

    registry = load_json(registry_path)
    active = active_external_sources(registry)
    if post_ids is not None:
        known = {int(post_id) for post_id in active}
        unknown = sorted(post_ids - known)
        if unknown:
            raise ValueError(f"external fallback is not enabled for post IDs: {unknown}")
    updated_sources: dict[str, dict] = {}
    requests = 0
    skipped = []
    for post_id, source in active.items():
        item = copy.deepcopy((status.get("external_sources") or {}).get(post_id) or empty_source(source))
        if item.get("url") != source["url"] or item.get("post_id") != source["post_id"]:
            item = empty_source(source)
        selected = post_ids is None or source["post_id"] in post_ids
        if selected and due_for_check(item, now, force=force):
            result = observation(source["url"], opener=opener)
            apply_observation(item, result, observed_at)
            requests += 1
        else:
            skipped.append(post_id)
        updated_sources[post_id] = item
    status["external_sources"] = updated_sources
    if status.get("external_sources") != before.get("external_sources"):
        status["external_sources_updated_at"] = observed_at
        status["updated_at"] = observed_at

    report = render_report(status)
    report_existed = REPORT_PATH.exists()
    previous_report = REPORT_PATH.read_text(encoding="utf-8") if report_existed else None
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    changed = status != before or report != previous_report
    if status != before:
        write_json(status_path, status)
    return {"changed": changed, "network_requests": requests, "skipped_post_ids": skipped, "status": status}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Allow a check of a frozen_source entry for manual recovery.")
    parser.add_argument("--post-id", type=int, action="append", help="Restrict a manual check to one opted-in immutable WordPress post ID; repeatable.")
    parser.add_argument("--result", help="Write result JSON outside the repository.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run(force=args.force, post_ids=set(args.post_id) if args.post_id else None)
        if args.result:
            destination = Path(args.result).expanduser().resolve()
            if destination.is_relative_to(ROOT.resolve()):
                raise ValueError("external-source result must be outside the repository")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps({k: v for k, v in result.items() if k != "status"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "status"}, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"external source check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
