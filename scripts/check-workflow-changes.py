#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Validate canonical workflow changes against its narrow action plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from jsonschema import FormatChecker, validators
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "content/rights-registry.json"
ACTION_PLAN_SCHEMA = ROOT / "schemas" / "canonical-drift-action-plan.schema.json"
MASTER_FAVICON = "assets/brand/01_DS_Favicon_Dark_Mode.png"
ALLOWED = re.compile(
    r"(?:archive-manifest\.json|archive-status\.json|docs/CANONICAL_DRIFT\.md|"
    r"docs/EXTERNAL_SOURCE_STATUS\.md|docs/VALIDATION\.md|docs/PUBLIC_SAFETY\.md|"
    r"docs/sitemap\.xml|docs/feed\.xml|docs/index\.html|docs/\.nojekyll|"
    r"assets/brand/(?:manifest\.json|derivatives/.+)|docs/assets/.+|"
    r"docs/posts/.+|docs/sheets/.+|content/posts/.+|content/rights-registry\.json)"
)


def git(*args: str, check: bool = True) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=check, stdout=subprocess.PIPE).stdout


def json_bytes(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def registry_bytes(source: str) -> bytes:
    try:
        raw = git("show", source, check=False)
        if not raw:
            raise ValueError
        return raw
    except Exception as exc:
        raise ValueError(f"cannot read {REGISTRY} from {source}") from exc


def git_json(source: str) -> object:
    return json.loads(git("show", source).decode("utf-8"))


def validate_action_plan(plan: object) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("action plan must be an object")
    schema = json.loads(ACTION_PLAN_SCHEMA.read_text(encoding="utf-8"))
    validator_class = validators.validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(plan), key=lambda error: list(error.path))
    if errors:
        raise ValueError("action plan schema validation failed: " + "; ".join(error.message for error in errors))
    return plan


def validate_media_updates(plan: dict, staged: bool) -> None:
    updates = plan.get("media_updates")
    if not isinstance(updates, list):
        raise ValueError("action plan media_updates must be an array")
    seen: set[str] = set()
    for update in updates:
        if not isinstance(update, dict):
            raise ValueError("media update must be an object")
        asset_path = update["asset_path"]
        path = Path(asset_path)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != asset_path:
            raise ValueError(f"media asset_path must be a normal repository-relative path: {asset_path}")
        if asset_path in seen:
            raise ValueError(f"duplicate media update path: {asset_path}")
        seen.add(asset_path)
    if plan.get("action") != "sync":
        return
    if plan.get("canonical_healthy") is not True or (plan.get("media_audit") or {}).get("status") != "complete":
        raise ValueError("media replacement requires a healthy canonical state and complete media audit")
    manifest = git_json("HEAD:archive-manifest.json")
    base_manifests: dict[str, dict] = {}
    current_manifests: dict[str, dict] = {}
    for update in updates:
        asset_path = update["asset_path"]
        post_id = update["post_id"]
        matches = [post for post in manifest.get("posts", []) if post.get("id") == post_id]
        if len(matches) != 1:
            raise ValueError(f"media update post_id does not identify one archived post: {post_id}")
        bundle = matches[0].get("bundle_path", "")
        if not asset_path.startswith(bundle + "/assets/"):
            raise ValueError(f"media asset_path is outside the planned post assets directory: {asset_path}")
        manifest_path = f"{bundle}/assets/manifest.json"
        if manifest_path not in base_manifests:
            base_manifests[manifest_path] = json.loads(git("show", f"HEAD:{manifest_path}").decode("utf-8"))
        base_manifest = base_manifests[manifest_path]
        records = [
            asset for asset in base_manifest.get("assets", [])
            if asset.get("local_path") == asset_path
            and asset.get("source_url") == update["source_url"]
        ]
        if len(records) != 1 or base_manifest.get("post_id") != post_id:
            raise ValueError(f"media update does not match one exact source asset record: {asset_path}")
        base = subprocess.run(["git", "show", f"HEAD:{asset_path}"], cwd=ROOT, stdout=subprocess.PIPE)
        if base.returncode != 0:
            raise ValueError(f"planned old media asset is missing from HEAD: {asset_path}")
        if hashlib.sha256(base.stdout).hexdigest() != update["old_sha256"]:
            raise ValueError(f"planned old media hash does not match HEAD: {asset_path}")
        current = content(asset_path, staged)
        if current is None or hashlib.sha256(current).hexdigest() != update["new_sha256"]:
            raise ValueError(f"planned new media hash does not match changed asset: {asset_path}")
        if manifest_path not in current_manifests:
            current_manifest_bytes = content(manifest_path, staged)
            if current_manifest_bytes is None:
                raise ValueError(f"updated media asset manifest is missing: {manifest_path}")
            current_manifests[manifest_path] = json.loads(current_manifest_bytes)
        current_manifest = current_manifests[manifest_path]
        current_records = [
            asset for asset in current_manifest.get("assets", [])
            if asset.get("local_path") == asset_path
            and asset.get("source_url") == update["source_url"]
        ]
        if len(current_records) != 1 or current_records[0].get("sha256") != update["new_sha256"]:
            raise ValueError(f"updated media manifest does not record the planned bytes: {asset_path}")
        if update["old_sha256"] == update["new_sha256"]:
            raise ValueError(f"media update does not change bytes: {asset_path}")


def expected_registry(base: bytes, action_plan_path: Path | None, *, staged: bool = False) -> bytes:
    base_obj = json.loads(base)
    if not isinstance(base_obj, dict):
        raise ValueError("base rights registry must be a JSON object")
    if action_plan_path is None or not action_plan_path.exists():
        return base
    plan = validate_action_plan(json.loads(action_plan_path.read_text(encoding="utf-8")))
    retirement = plan.get("retirement") or {}
    candidate = retirement.get("candidate") or {}
    drift = plan.get("drift") or {}
    base_manifest_bytes = git("show", "HEAD:archive-manifest.json")
    if plan.get("archive_manifest_sha256") != hashlib.sha256(base_manifest_bytes).hexdigest():
        raise ValueError("action plan does not match the base archive manifest")
    missing = drift.get("missing_posts") or []
    if (
        plan.get("version") != 3
        or plan.get("action") != "retire"
        or retirement.get("eligible") is not True
        or plan.get("canonical_healthy") is not True
        or len(missing) != 1
        or not isinstance(candidate.get("id"), int)
        or candidate.get("id") != missing[0].get("id")
        or candidate.get("bundle_path") != missing[0].get("bundle_path")
        or candidate.get("canonical_url") != missing[0].get("canonical_url")
        or drift.get("live_post_count") != drift.get("archived_post_count", 0) - 1
        or drift.get("new_ids")
        or drift.get("relocated_posts")
        or drift.get("changed_posts")
        or plan.get("sync_posts")
        or plan.get("update_posts")
    ):
        return base
    key = str(candidate["id"])
    base_manifest = json.loads(base_manifest_bytes)
    base_matches = [post for post in base_manifest.get("posts", []) if post.get("id") == candidate["id"]]
    if len(base_matches) != 1 or base_matches[0].get("bundle_path") != candidate.get("bundle_path"):
        raise ValueError("retirement plan does not identify one exact base-manifest post bundle")
    final_manifest_bytes = content("archive-manifest.json", staged)
    if final_manifest_bytes is None:
        raise ValueError("reconciled archive manifest missing")
    final_manifest = json.loads(final_manifest_bytes)
    base_posts = base_manifest.get("posts", [])
    final_posts = final_manifest.get("posts", [])
    expected_posts = [post for post in base_posts if post.get("id") != candidate["id"]]
    if final_posts != expected_posts or final_manifest.get("post_count") != len(expected_posts):
        raise ValueError("reconciled archive manifest is not exactly the planned post retirement")
    if any(key not in {"posts", "post_count", "generated_at"} and final_manifest.get(key) != value for key, value in base_manifest.items()):
        raise ValueError("reconciled archive manifest contains unrelated changes")
    if any(post.get("id") == candidate["id"] for post in final_posts):
        raise ValueError("planned retirement post remains in the reconciled archive manifest")
    if staged:
        if bundle_remains_indexed(candidate["bundle_path"]):
            raise ValueError("planned retirement bundle remains in the staged index")
    elif (ROOT / candidate["bundle_path"]).exists():
        raise ValueError("planned retirement bundle remains in the reconciled tree")
    expected = dict(base_obj)
    expected.pop(key, None)
    return json_bytes(expected)


def paths_for(staged: bool) -> set[str]:
    if staged:
        return set(git("diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB").decode().splitlines())
    paths: set[str] = set()
    for args in [("diff", "--name-only"), ("diff", "--cached", "--name-only"), ("ls-files", "--others", "--exclude-standard")]:
        paths.update(git(*args).decode().splitlines())
    return paths


def bundle_remains_indexed(bundle_path: str) -> bool:
    return bool(git("ls-files", "--stage", "--", bundle_path).strip())


def validate_regular_paths(paths: set[str], staged: bool) -> None:
    for path in paths:
        target = ROOT / path
        if staged:
            entries = git("ls-files", "--stage", "--", path).decode().splitlines()
            if any(not line.split(maxsplit=1)[0].startswith("100") for line in entries):
                raise ValueError(f"changed path is not a regular file in the index: {path}")
        elif target.exists() and (target.is_symlink() or not target.is_file()):
            raise ValueError(f"changed path is not a regular file in the worktree: {path}")


def content(path: str, staged: bool) -> bytes | None:
    if staged:
        proc = subprocess.run(["git", "show", f":{path}"], cwd=ROOT, stdout=subprocess.PIPE)
        return proc.stdout if proc.returncode == 0 else None
    target = ROOT / path
    return target.read_bytes() if target.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--action-plan", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    paths = paths_for(args.staged)
    plan = None
    if args.action_plan and args.action_plan.exists():
        try:
            plan = validate_action_plan(json.loads(args.action_plan.read_text(encoding="utf-8")))
            validate_media_updates(plan, args.staged)
        except Exception as exc:
            errors.append(f"action-plan validation failed: {exc}")
    try:
        validate_regular_paths(paths, args.staged)
    except Exception as exc:
        errors.append(f"changed-path type check failed: {exc}")
    unexpected = sorted(path for path in paths if not ALLOWED.fullmatch(path))
    if unexpected:
        errors.append("unexpected workflow path(s): " + ", ".join(unexpected))

    if REGISTRY in paths:
        try:
            base = registry_bytes("HEAD:" + REGISTRY)
            expected = expected_registry(base, args.action_plan, staged=args.staged)
            actual = content(REGISTRY, args.staged)
            if actual != expected:
                errors.append("rights registry delta is not exactly the eligible retirement ID deletion")
        except Exception as exc:
            errors.append(f"rights registry allowlist check failed: {exc}")

    brand_changes = {path for path in paths if path.startswith("assets/brand/") or path.startswith("docs/assets/brand/")}
    if brand_changes:
        try:
            base_manifest = git_json("HEAD:assets/brand/manifest.json")
            current_manifest_bytes = content("assets/brand/manifest.json", args.staged)
            if current_manifest_bytes is None:
                raise ValueError("brand manifest missing from working/index state")
            current_manifest = json.loads(current_manifest_bytes)
            base_derivative = base_manifest["assets"][0]["pages_derivative"]
            current_asset = current_manifest["assets"][0]
            current_derivative = current_asset["pages_derivative"]
            current_master = content(MASTER_FAVICON, args.staged)
            current_hash = hashlib.sha256(current_master or b"").hexdigest()
            if base_derivative.get("source_sha256") == current_hash:
                raise ValueError("brand allowlist changes require an actual master favicon change")
            if current_asset.get("sha256") != current_hash or current_derivative.get("source_sha256") != current_hash:
                raise ValueError("prepared brand manifest does not match the current master favicon")
            allowed_brand = {"assets/brand/manifest.json", current_derivative["prepared_path"], current_derivative["path"]}
            if brand_changes - allowed_brand:
                raise ValueError("brand allowlist contains an unapproved path")
            derivative = content(current_derivative["prepared_path"], args.staged)
            if derivative is None or hashlib.sha256(derivative).hexdigest() != current_derivative.get("sha256"):
                raise ValueError("prepared brand derivative checksum is invalid")
        except Exception as exc:
            errors.append(f"brand allowlist check failed: {exc}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Workflow changes validated ({len(paths)} changed path(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
