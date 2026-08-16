#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Apply one safe, checker-produced canonical drift action."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PLAN_VERSION = 1
ALLOWED_ENDPOINT_STATUSES = {404, 410}
RETIREMENT_CONFIRMATION_MIN_DAYS = 7


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def action_plan_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return path
    raise ValueError(f"action plan must be outside repository root: {path}")


def atomic_write_json(path: Path, data) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def restore_bytes(path: Path, original: bytes) -> None:
    temporary = path.with_name(f".{path.name}.rollback-{os.getpid()}")
    temporary.write_bytes(original)
    os.replace(temporary, path)


def safe_bundle_path(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe bundle path: {value}")
    if relative.parts[:2] != ("content", "posts") or len(relative.parts) != 3:
        raise ValueError(f"bundle path is outside content/posts/<bundle>: {value}")
    current = ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"bundle path contains a symlink: {value}")
    if not current.is_dir():
        raise ValueError(f"bundle path is not an existing directory: {value}")
    return current


def validate_endpoint_evidence(evidence: dict | None) -> None:
    if not evidence or evidence.get("passed") is not True:
        raise ValueError("retirement lacks passing direct endpoint evidence")
    for name in ["rest", "canonical_route"]:
        item = evidence.get(name) or {}
        if item.get("status") not in ALLOWED_ENDPOINT_STATUSES or item.get("passed") is not True:
            raise ValueError(f"retirement {name} endpoint is not a direct 404/410")


def confirmation_window_is_valid(candidate: dict) -> bool:
    confirmations = candidate.get("healthy_confirmations") or []
    if len(confirmations) < 2:
        return False
    try:
        first = dt.datetime.fromisoformat(confirmations[0]["observed_at"].replace("Z", "+00:00"))
        last = dt.datetime.fromisoformat(confirmations[-1]["observed_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    return (last - first).total_seconds() >= RETIREMENT_CONFIRMATION_MIN_DAYS * 86400


def validate_common(plan: dict, manifest: dict, status: dict) -> None:
    if plan.get("version") != ACTION_PLAN_VERSION:
        raise ValueError("unsupported canonical drift action-plan version")
    if plan.get("canonical_healthy") is not True or status.get("state") != "healthy" or status.get("frozen") is True:
        raise ValueError("canonical state is not healthy; no reconciliation action is permitted")
    manifest_path = ROOT / "archive-manifest.json"
    if plan.get("archive_manifest_sha256") != sha256_file(manifest_path):
        raise ValueError("archive-manifest.json changed after the action plan was produced")


def retire_one(plan: dict, manifest: dict, status: dict) -> None:
    drift = plan.get("drift") or {}
    missing = drift.get("missing_posts") or []
    if (
        len(missing) != 1
        or drift.get("live_post_count") != drift.get("archived_post_count", 0) - 1
        or drift.get("new_ids")
        or drift.get("relocated_posts")
        or drift.get("changed_posts")
    ):
        raise ValueError("retirement requires exactly one missing ID and no concurrent drift anomaly")
    candidate = (plan.get("retirement") or {}).get("candidate") or {}
    item = missing[0]
    for key in ["id", "canonical_url", "bundle_path"]:
        if candidate.get(key) != item.get(key):
            raise ValueError(f"retirement candidate mismatch for {key}")
    if not confirmation_window_is_valid(candidate):
        raise ValueError("retirement candidate does not have two confirmations at least seven days apart")
    validate_endpoint_evidence((plan.get("retirement") or {}).get("endpoint_evidence"))
    if (plan.get("retirement") or {}).get("eligible") is not True:
        raise ValueError("checker did not mark the retirement candidate eligible")

    posts = manifest.get("posts") or []
    matches = [post for post in posts if post.get("id") == item.get("id")]
    if len(matches) != 1:
        raise ValueError("archive manifest does not contain exactly one matching post ID")
    archived = matches[0]
    for key in ["canonical_url", "bundle_path"]:
        if archived.get(key) != item.get(key):
            raise ValueError(f"archive manifest changed for candidate {key}")
    bundle = safe_bundle_path(archived["bundle_path"])
    metadata_path = bundle / "metadata.json"
    if not metadata_path.is_file() or metadata_path.is_symlink():
        raise ValueError("candidate bundle metadata is missing or symlinked")
    metadata = load_json(metadata_path)
    if metadata.get("id") != item.get("id") or metadata.get("canonical_url") != item.get("canonical_url"):
        raise ValueError("candidate bundle metadata does not match the action plan")

    updated_manifest = dict(manifest)
    updated_manifest["posts"] = [post for post in posts if post.get("id") != item.get("id")]
    updated_manifest["post_count"] = len(updated_manifest["posts"])
    updated_manifest["generated_at"] = now_iso()
    updated_status = dict(status)
    updated_status["retirement_candidates"] = []
    updated_status["last_drift_hash"] = None
    updated_status["last_drift_detected_at"] = None
    updated_status["updated_at"] = updated_manifest["generated_at"]

    manifest_path = ROOT / "archive-manifest.json"
    status_path = ROOT / "archive-status.json"
    original_manifest = manifest_path.read_bytes()
    original_status = status_path.read_bytes()
    temporary_root = Path(tempfile.mkdtemp(prefix="daryllswer-retirement-"))
    temporary_bundle = temporary_root / bundle.name
    moved = False
    try:
        shutil.move(str(bundle), str(temporary_bundle))
        moved = True
        atomic_write_json(manifest_path, updated_manifest)
        atomic_write_json(status_path, updated_status)
    except Exception:
        if manifest_path.exists():
            restore_bytes(manifest_path, original_manifest)
        if status_path.exists():
            restore_bytes(status_path, original_status)
        if moved and not bundle.exists() and temporary_bundle.exists():
            shutil.move(str(temporary_bundle), str(bundle))
        raise
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)

    print(f"retired one canonical post ID {item['id']}; run render-site to remove its Pages route")


def sync_one(plan: dict) -> None:
    new_posts = plan.get("sync_posts") or []
    if len(new_posts) > 1:
        raise ValueError("automatic sync action contains more than one newly detected post")
    if not new_posts:
        raise ValueError("sync action contains no newly detected post")
    drift = plan.get("drift") or {}
    new_ids = set(drift.get("new_ids") or [])
    item = new_posts[0]
    if item.get("id") not in new_ids or not item.get("slug"):
        raise ValueError("automatic sync post is not a newly detected immutable ID")
    command = [sys.executable, str(ROOT / "scripts" / "sync-wordpress-posts.py"), "--slugs", item["slug"]]
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(f"automatic sync failed with exit code {result.returncode}")
    manifest = load_json(ROOT / "archive-manifest.json")
    if not any(post.get("id") == item.get("id") for post in manifest.get("posts", [])):
        raise RuntimeError("automatic sync completed without adding the planned post ID")
    print(f"automatically synced one newly detected canonical post ID {item['id']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action-plan", required=True, help="Checker-produced plan outside the repository.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without applying the action.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan_path = action_plan_path(args.action_plan)
        plan = load_json(plan_path)
        manifest_path = ROOT / "archive-manifest.json"
        status_path = ROOT / "archive-status.json"
        manifest = load_json(manifest_path)
        status = load_json(status_path)
        action = plan.get("action", "none")
        if action == "none" or action == "frozen":
            print(f"canonical drift action={action}; no reconciliation changes")
            return 0
        validate_common(plan, manifest, status)
        if action == "retire":
            if args.dry_run:
                print(f"dry-run: would retire ID {(plan.get('retirement') or {}).get('candidate', {}).get('id')}")
            else:
                retire_one(plan, manifest, status)
        elif action == "sync":
            if args.dry_run:
                print(f"dry-run: would sync {len(plan.get('sync_posts') or [])} post")
            else:
                sync_one(plan)
        else:
            raise ValueError(f"unknown reconciliation action: {action}")
        return 0
    except Exception as exc:
        print(f"canonical drift reconciliation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
