#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Decide whether the latest GitHub Pages deployment proves a revision live."""

from __future__ import annotations

import argparse
import json
import re
import subprocess


def latest_status_for_revision(revision: str, deployments: list[dict], get_status) -> bool:
    """Return true only when the newest Pages deployment is active-success for SHA."""
    if not isinstance(deployments, list):
        raise ValueError("GitHub deployments response must be a list")
    if not deployments:
        return False
    if len(deployments) > 100:
        raise ValueError("GitHub deployments response exceeded bounded 100-record query")
    for item in deployments:
        if not isinstance(item, dict) or not isinstance(item.get("created_at"), str) or not isinstance(item.get("id"), int):
            raise ValueError("GitHub deployments response contains malformed records")
    newest = max(deployments, key=lambda item: (item["created_at"], item["id"]))
    if newest.get("sha") != revision:
        return False
    statuses = get_status(newest["id"])
    if not isinstance(statuses, list):
        raise ValueError("GitHub deployment statuses response must be a list")
    if not statuses:
        return False
    latest = statuses[0]
    if not isinstance(latest, dict) or not isinstance(latest.get("state"), str):
        raise ValueError("GitHub latest deployment status is malformed")
    return latest["state"] == "success"


def gh_json(endpoint: str):
    output = subprocess.check_output(["gh", "api", endpoint], text=True)
    return json.loads(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", args.revision):
        parser.error("--revision must be a full hexadecimal Git object ID")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("--repository must be OWNER/REPOSITORY")
    deployments = gh_json(f"repos/{args.repository}/deployments?environment=github-pages&per_page=100")
    needed = not latest_status_for_revision(
        args.revision,
        deployments,
        lambda deployment_id: gh_json(f"repos/{args.repository}/deployments/{deployment_id}/statuses?per_page=1"),
    )
    print(f"needed={'true' if needed else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
