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
ACTION_PLAN_VERSION = 2
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


def external_result_path(value: str) -> Path:
    """Require workflow result records to remain outside the checkout."""
    return action_plan_path(value)


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


def safe_bundle_relative_path(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe bundle path: {value}")
    if relative.parts[:2] != ("content", "posts") or len(relative.parts) != 3:
        raise ValueError(f"bundle path is outside content/posts/<bundle>: {value}")
    return relative


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
    rights_registry_path = ROOT / "content" / "rights-registry.json"
    original_manifest = manifest_path.read_bytes()
    original_status = status_path.read_bytes()
    if rights_registry_path.is_symlink():
        raise ValueError("rights registry is symlinked")
    if rights_registry_path.exists() and not rights_registry_path.is_file():
        raise ValueError("rights registry is not a regular file")
    original_rights_registry = rights_registry_path.read_bytes() if rights_registry_path.exists() else None
    rights_registry = load_json(rights_registry_path) if original_rights_registry is not None else {}
    if not isinstance(rights_registry, dict):
        raise ValueError("rights registry must be an object")
    updated_rights_registry = dict(rights_registry)
    rights_registry_key = str(item["id"])
    rights_registry_changed = rights_registry_key in updated_rights_registry
    if rights_registry_changed:
        del updated_rights_registry[rights_registry_key]
    temporary_root = Path(tempfile.mkdtemp(prefix="daryllswer-retirement-"))
    temporary_bundle = temporary_root / bundle.name
    moved = False
    try:
        shutil.move(str(bundle), str(temporary_bundle))
        moved = True
        atomic_write_json(manifest_path, updated_manifest)
        atomic_write_json(status_path, updated_status)
        if rights_registry_changed:
            atomic_write_json(rights_registry_path, updated_rights_registry)
    except Exception:
        if manifest_path.exists():
            restore_bytes(manifest_path, original_manifest)
        if status_path.exists():
            restore_bytes(status_path, original_status)
        if original_rights_registry is not None:
            restore_bytes(rights_registry_path, original_rights_registry)
        elif rights_registry_path.exists() and rights_registry_path.is_file():
            rights_registry_path.unlink()
        if moved and not bundle.exists() and temporary_bundle.exists():
            shutil.move(str(temporary_bundle), str(bundle))
        raise
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)

    print(f"retired one canonical post ID {item['id']}; run render-site to remove its Pages route")


def sync_targets(plan: dict, manifest: dict) -> tuple[list[dict], list[dict]]:
    """Validate one safe new-post-plus-existing-update batch from immutable IDs."""
    drift = plan.get("drift") or {}
    new_posts = list(plan.get("sync_posts") or [])
    updates = list(plan.get("update_posts") or [])
    if len(new_posts) > 1:
        raise ValueError("automatic sync action contains more than one newly detected post")
    if drift.get("missing_ids") or drift.get("relocated_posts"):
        raise ValueError("automatic sync cannot run beside missing or relocated posts")
    new_ids = set(drift.get("new_ids") or [])
    changed_by_id = {item.get("id"): item for item in drift.get("changed_posts") or []}
    archived_by_id = {item.get("id"): item for item in manifest.get("posts") or []}
    target_ids: set[int] = set()

    for item in new_posts:
        post_id = item.get("id")
        if not isinstance(post_id, int) or post_id not in new_ids or not item.get("slug") or not item.get("canonical_url"):
            raise ValueError("automatic sync new post is not a planned immutable ID")
        if post_id in archived_by_id or post_id in target_ids:
            raise ValueError("automatic sync new post conflicts with the archive manifest")
        target_ids.add(post_id)

    if set(item.get("id") for item in updates) != set(changed_by_id):
        raise ValueError("automatic sync must include every and only checker-reported existing-post update")
    for item in updates:
        post_id = item.get("id")
        expected = item.get("expected") or {}
        archived = archived_by_id.get(post_id)
        detected = changed_by_id.get(post_id)
        if (
            not isinstance(post_id, int)
            or post_id in target_ids
            or not archived
            or not detected
            or item.get("slug") != detected.get("slug")
            or item.get("canonical_url") != detected.get("canonical_url")
            or expected != detected.get("expected")
        ):
            raise ValueError("automatic sync existing-post update does not match the checker action plan")
        if archived.get("slug") != item.get("slug") or archived.get("canonical_url", "").rstrip("/") != item.get("canonical_url", "").rstrip("/"):
            raise ValueError("automatic sync refuses a relocated existing post")
        target_ids.add(post_id)

    if not target_ids:
        raise ValueError("automatic sync action contains no target posts")
    return new_posts, updates


def stage_sync(plan: dict, manifest: dict) -> tuple[Path, list[dict], list[dict]]:
    """Run the public synchroniser in an isolated root before any live mutation."""
    new_posts, updates = sync_targets(plan, manifest)
    targets = [*new_posts, *updates]
    stage_root = Path(tempfile.mkdtemp(prefix="daryllswer-sync-stage-"))
    try:
        (stage_root / "archive-manifest.json").write_bytes((ROOT / "archive-manifest.json").read_bytes())
        registry_source = ROOT / "content" / "rights-registry.json"
        if not registry_source.is_file() or registry_source.is_symlink():
            raise RuntimeError("staged automatic sync requires content/rights-registry.json")
        registry_stage = stage_root / "content" / "rights-registry.json"
        registry_stage.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(registry_source, registry_stage)
        rights_registry = load_json(registry_source)
        command = [
            sys.executable,
            str(ROOT / "scripts" / "sync-wordpress-posts.py"),
            "--slugs",
            ",".join(item["slug"] for item in targets),
        ]
        for item in targets:
            command.extend(["--expected-id", str(item["id"])])
        environment = dict(os.environ)
        environment["ARCHIVE_ROOT"] = str(stage_root)
        result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        if result.returncode:
            raise RuntimeError(f"staged automatic sync failed with exit code {result.returncode}")
        staged_manifest = load_json(stage_root / "archive-manifest.json")
        staged_by_id = {item.get("id"): item for item in staged_manifest.get("posts") or []}
        prior_by_id = {item.get("id"): item for item in manifest.get("posts") or []}
        for item in targets:
            post_id = item["id"]
            staged = staged_by_id.get(post_id)
            if not staged or staged.get("slug") != item["slug"] or staged.get("canonical_url", "").rstrip("/") != item["canonical_url"].rstrip("/"):
                raise RuntimeError(f"staged automatic sync did not preserve planned ID {post_id}")
            if post_id in prior_by_id and staged.get("bundle_path") != prior_by_id[post_id].get("bundle_path"):
                raise RuntimeError(f"staged automatic sync attempted to relocate existing post ID {post_id}")
            relative = safe_bundle_relative_path(staged.get("bundle_path") or "")
            staged_bundle = stage_root / relative
            if not staged_bundle.is_dir() or staged_bundle.is_symlink() or not (staged_bundle / "metadata.json").is_file():
                raise RuntimeError(f"staged automatic sync did not produce a safe bundle for ID {post_id}")
            if str(post_id) in rights_registry:
                staged_metadata = load_json(staged_bundle / "metadata.json")
                if staged_metadata.get("rights") != rights_registry[str(post_id)]:
                    raise RuntimeError(f"staged automatic sync did not apply rights registry for ID {post_id}")
        return stage_root, new_posts, updates
    except Exception:
        shutil.rmtree(stage_root, ignore_errors=True)
        raise


def apply_staged_sync(stage_root: Path, manifest: dict, new_posts: list[dict], updates: list[dict]) -> None:
    """Replace a fully verified synchronisation batch, restoring every bundle on failure."""
    staged_manifest_path = stage_root / "archive-manifest.json"
    staged_manifest = load_json(staged_manifest_path)
    staged_by_id = {item.get("id"): item for item in staged_manifest.get("posts") or []}
    prior_by_id = {item.get("id"): item for item in manifest.get("posts") or []}
    targets = [*new_posts, *updates]
    manifest_path = ROOT / "archive-manifest.json"
    original_manifest = manifest_path.read_bytes()
    temporary_root = Path(tempfile.mkdtemp(prefix="daryllswer-sync-rollback-", dir=ROOT / "content"))
    moved_old: list[tuple[Path, Path]] = []
    moved_new: list[Path] = []
    try:
        for item in targets:
            staged = staged_by_id[item["id"]]
            relative = safe_bundle_relative_path(staged["bundle_path"])
            source = stage_root / relative
            destination = ROOT / relative
            if not source.is_dir() or source.is_symlink():
                raise ValueError(f"staged bundle is unsafe for ID {item['id']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            old = prior_by_id.get(item["id"])
            if old:
                current = safe_bundle_path(old["bundle_path"])
                backup = temporary_root / current.name
                shutil.move(str(current), str(backup))
                moved_old.append((current, backup))
            elif destination.exists():
                raise ValueError(f"new post destination already exists: {relative}")
            shutil.move(str(source), str(destination))
            moved_new.append(destination)
        atomic_write_json(manifest_path, staged_manifest)
    except Exception:
        for destination in reversed(moved_new):
            if destination.exists():
                shutil.rmtree(destination)
        for current, backup in reversed(moved_old):
            if backup.exists():
                shutil.move(str(backup), str(current))
        restore_bytes(manifest_path, original_manifest)
        raise
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def sync_batch(plan: dict, manifest: dict) -> dict:
    stage_root, new_posts, updates = stage_sync(plan, manifest)
    try:
        apply_staged_sync(stage_root, manifest, new_posts, updates)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    return {
        "new_post_ids": [item["id"] for item in new_posts],
        "updated_post_ids": [item["id"] for item in updates],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action-plan", required=True, help="Checker-produced plan outside the repository.")
    parser.add_argument("--result", help="Write the reconciliation result outside the repository.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without applying the action.")
    return parser.parse_args()


def write_result(path: str | None, result: dict) -> None:
    if not path:
        return
    destination = external_result_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    result = {"version": 1, "action": "none", "content_changed": False, "new_post_ids": [], "updated_post_ids": []}
    try:
        plan_path = action_plan_path(args.action_plan)
        plan = load_json(plan_path)
        manifest_path = ROOT / "archive-manifest.json"
        status_path = ROOT / "archive-status.json"
        manifest = load_json(manifest_path)
        status = load_json(status_path)
        action = plan.get("action", "none")
        result["action"] = action
        if action == "none" or action == "frozen":
            print(f"canonical drift action={action}; no reconciliation changes")
            write_result(args.result, result)
            return 0
        validate_common(plan, manifest, status)
        if action == "retire":
            if args.dry_run:
                print(f"dry-run: would retire ID {(plan.get('retirement') or {}).get('candidate', {}).get('id')}")
            else:
                retire_one(plan, manifest, status)
                result["content_changed"] = True
        elif action == "sync":
            new_posts, updates = sync_targets(plan, manifest)
            if args.dry_run:
                print(f"dry-run: would sync {len(new_posts)} new and {len(updates)} changed existing post(s)")
            else:
                result.update(sync_batch(plan, manifest))
                result["content_changed"] = True
                print(
                    "automatically synced "
                    f"{len(result['new_post_ids'])} new and {len(result['updated_post_ids'])} changed existing post(s)"
                )
        else:
            raise ValueError(f"unknown reconciliation action: {action}")
        write_result(args.result, result)
        return 0
    except Exception as exc:
        write_result(args.result, {**result, "error": f"{type(exc).__name__}: {exc}"})
        print(f"canonical drift reconciliation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
