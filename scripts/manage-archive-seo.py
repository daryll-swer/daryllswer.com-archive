#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Explicit owner-acknowledged recovery for archive SEO source states."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "archive-status.json"
REGISTRY_PATH = ROOT / "content" / "rights-registry.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_owner_acknowledgement(args: argparse.Namespace) -> None:
    if not args.owner_verified:
        raise ValueError("manual recovery requires --owner-verified")


def resume_ds() -> None:
    status = load_json(STATUS_PATH)
    if status.get("state") != "frozen_archive" or status.get("frozen") is not True:
        raise ValueError("resume-ds requires archive-status.json state=frozen_archive and frozen=true")

    drift = load_module("check-canonical-drift.py", "archive_seo_canonical_drift")
    generated_at = now_iso()
    try:
        posts, headers, not_modified = drift.request_posts(status, fresh=True)
        if not isinstance(posts, list) or not posts:
            raise RuntimeError("current canonical observation did not return a non-empty post list")
    except Exception as exc:
        raise RuntimeError(f"current healthy DS source observation failed: {exc}") from exc

    updated = copy.deepcopy(status)
    updated["state"] = "healthy"
    updated["frozen"] = False
    updated["seo_state"] = "source_primary"
    updated["seo_activated_at"] = None
    updated["updated_at"] = generated_at
    updated["last_success_at"] = generated_at
    updated["failure"] = {
        "consecutive_failures": 0,
        "first_failure_at": None,
        "last_failure_at": None,
        "last_failure_kind": None,
        "last_failure_detail": None,
    }
    updated["manual_recovery"] = {
        **(updated.get("manual_recovery") or {}),
        "last_action": "resume-ds",
        "last_action_at": generated_at,
        "owner_verified": True,
    }
    write_json(STATUS_PATH, updated)
    print("DS source resumed after a current healthy public observation; source-primary SEO was restored.")


def resume_external(post_id: int) -> None:
    registry = load_json(REGISTRY_PATH)
    record = registry.get(str(post_id))
    if not isinstance(record, dict) or record.get("external_fallback") is not True:
        raise ValueError(f"post ID {post_id} is not opted in for external fallback")

    monitor = load_module("external_source_monitor.py", "archive_seo_external_monitor")
    before = load_json(STATUS_PATH)
    result = monitor.run(force=True, post_ids={post_id})
    status = result["status"]
    source = (status.get("external_sources") or {}).get(str(post_id))
    if not source or source.get("state") != monitor.HEALTH or source.get("last_checked_at") == before.get("external_sources", {}).get(str(post_id), {}).get("last_checked_at"):
        raise RuntimeError("current healthy external-source observation was not obtained; no recovery promotion was made")

    generated_at = now_iso()
    updated = copy.deepcopy(status)
    updated["external_sources"][str(post_id)]["manual_recovery"] = {
        "last_action": "resume-external",
        "last_action_at": generated_at,
        "owner_verified": True,
    }
    updated["updated_at"] = generated_at
    write_json(STATUS_PATH, updated)
    print(f"external source for post ID {post_id} resumed after a current healthy public observation; SEO state was preserved.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual recovery only; this command never changes archive SEO state or article content automatically."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    ds = subparsers.add_parser("resume-ds", help="Resume DS source checks after owner-verified recovery.")
    ds.add_argument("--owner-verified", action="store_true", help="Acknowledge current owner control of the DS source.")
    external = subparsers.add_parser("resume-external", help="Resume one frozen external source after owner verification.")
    external.add_argument("--post-id", type=int, required=True, help="Immutable archived WordPress post ID.")
    external.add_argument("--owner-verified", action="store_true", help="Acknowledge owner verification of the external source.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_owner_acknowledgement(args)
        if args.command == "resume-ds":
            resume_ds()
        else:
            resume_external(args.post_id)
        return 0
    except Exception as exc:
        print(f"archive SEO recovery refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
