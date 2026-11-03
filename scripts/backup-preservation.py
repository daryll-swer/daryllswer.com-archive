#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Prepare a verified archive snapshot and safely publish it to a private backup checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = ROOT / "scripts" / "export-preservation.py"
MAX_API_BYTES = 2_000_000
SHA_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
RECORD_NAME = "backup-record.json"


class BackupError(Exception):
    """Raised when the backup cannot be verified or safely installed."""


def isolated_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name == "GIT_CONFIG_PARAMETERS" or re.fullmatch(r"GIT_CONFIG_(?:KEY|VALUE)_\d+", name):
            environment.pop(name)
    environment.pop("GIT_ASKPASS", None)
    environment.pop("SSH_ASKPASS", None)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_COUNT"] = "1"
    environment["GIT_CONFIG_KEY_0"] = "credential.helper"
    environment["GIT_CONFIG_VALUE_0"] = ""
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def load_exporter(path: Path = EXPORTER_PATH):
    spec = importlib.util.spec_from_file_location("trusted_preservation_exporter", path)
    if not spec or not spec.loader:
        raise BackupError("trusted exporter could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def api_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            final_url = urlparse(response.geturl())
            if final_url.scheme != "https" or final_url.hostname != "api.github.com" or final_url.username or final_url.password:
                raise BackupError("public GitHub evidence request redirected outside api.github.com")
            if response.status != 200:
                raise BackupError(f"GitHub API returned HTTP {response.status}")
            body = response.read(MAX_API_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise BackupError(f"public GitHub evidence request failed: {exc}") from exc
    if len(body) > MAX_API_BYTES:
        raise BackupError("GitHub API response exceeded the bounded response size")
    try:
        return json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BackupError("GitHub API returned invalid JSON") from exc


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode:
        raise BackupError(f"git {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def bare_git(repository: Path, *args: str, binary: bool = False) -> bytes | str:
    try:
        result = subprocess.run(
            ["git", f"--git-dir={repository}", *args], check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=isolated_git_environment(), timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise BackupError("isolated source Git operation exceeded 120 seconds") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise BackupError(f"source git {' '.join(args[:2])} failed: {detail}")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def fetch_source_commit(repository: str, revision: str, git_dir: Path, *, git_url: str | None = None) -> Path:
    if git_dir.exists() or git_dir.is_symlink():
        raise BackupError("temporary source git directory must not already exist")
    git_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        init = subprocess.run(
            ["git", "init", "--bare", str(git_dir)], check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=isolated_git_environment(), timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise BackupError("temporary bare Git initialisation exceeded 120 seconds") from exc
    if init.returncode:
        raise BackupError(f"cannot initialise temporary bare source repository: {init.stderr.decode('utf-8', 'replace').strip()}")
    remote = git_url or f"https://github.com/{repository}.git"
    bare_git(git_dir, "-c", "credential.helper=", "fetch", "--no-tags", "--depth=1", remote, revision)
    fetched = str(bare_git(git_dir, "rev-parse", "FETCH_HEAD"))
    if fetched != revision:
        raise BackupError("anonymous source fetch did not resolve to the verified source SHA")
    return git_dir


def fetch_additional_source_commit(repository: str, revision: str, git_dir: Path) -> None:
    remote = f"https://github.com/{repository}.git"
    bare_git(git_dir, "-c", "credential.helper=", "fetch", "--no-tags", "--depth=1", remote, revision)
    fetched = str(bare_git(git_dir, "rev-parse", "FETCH_HEAD"))
    if fetched != revision:
        raise BackupError("anonymous source fetch did not resolve to the recorded prior SHA")


def verify_payload_matches_source(snapshot: Path, source_sha: str, source_git_dir: Path, exporter) -> None:
    expected_files = exporter.committed_files(source_sha, source_git_dir)
    expected = dict(expected_files)
    payload = snapshot / "data"
    actual: dict[str, Path] = {}
    for path in payload.rglob("*"):
        if path.is_symlink():
            raise BackupError(f"symlink in source payload: {path.relative_to(payload)}")
        if path.is_file():
            relative = path.relative_to(payload).as_posix()
            actual[relative] = path
    if set(actual) != set(expected):
        raise BackupError("snapshot payload file set does not exactly match the source commit")
    for name, object_id in expected.items():
        committed = exporter.git(["cat-file", "blob", object_id], repository=source_git_dir, binary=True)
        committed_hash = hashlib.sha256(committed).hexdigest()
        if hashlib.sha256(actual[name].read_bytes()).hexdigest() != committed_hash:
            raise BackupError(f"snapshot payload bytes do not match source commit: {name}")


def verify_staged(repository: Path, snapshot_relative: str = "snapshot", exporter=None) -> None:
    exporter = exporter or load_exporter()
    if snapshot_relative != "snapshot":
        raise BackupError("staged verification is restricted to snapshot/")
    repo = repository.resolve(strict=True)
    snapshot = repo / snapshot_relative
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise BackupError("staged snapshot must be a real directory")
    validate_snapshot(snapshot, exporter)
    for path in snapshot.rglob("*"):
        if path.is_symlink():
            raise BackupError(f"symlink in staged snapshot: {path.relative_to(repo)}")
        if not path.is_file() and not path.is_dir():
            raise BackupError(f"unsupported staged snapshot entry: {path.relative_to(repo)}")
    diff = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only", "-z"],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if diff.returncode:
        raise BackupError(f"cannot inspect staged paths: {diff.stderr.decode('utf-8', 'replace').strip()}")
    staged_changes = {os.fsdecode(item) for item in diff.stdout.split(b"\0") if item}
    if any(name != snapshot_relative and not name.startswith(snapshot_relative + "/") for name in staged_changes):
        raise BackupError("staged changes include paths outside snapshot/")
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--stage", "-z", "--", snapshot_relative],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if listing.returncode:
        raise BackupError(f"cannot inspect staged snapshot: {listing.stderr.decode('utf-8', 'replace').strip()}")
    indexed: dict[str, str] = {}
    for item in listing.stdout.split(b"\0"):
        if not item:
            continue
        try:
            metadata, raw_name = item.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
            name = os.fsdecode(raw_name)
        except (ValueError, UnicodeError) as exc:
            raise BackupError("Git returned malformed staged index entries") from exc
        if mode not in {"100644", "100755"} or stage != "0" or not name.startswith(snapshot_relative + "/"):
            raise BackupError(f"unsupported staged snapshot entry: {name}")
        if name in indexed:
            raise BackupError(f"duplicate staged path: {name}")
        indexed[name] = object_id
    actual: dict[str, Path] = {
        path.relative_to(repo).as_posix(): path
        for path in snapshot.rglob("*") if path.is_file()
    }
    if set(indexed) != set(actual):
        raise BackupError("staged snapshot file set does not exactly match the verified worktree")
    for name, object_id in indexed.items():
        staged_bytes = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", object_id],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if staged_bytes.returncode:
            raise BackupError(f"cannot read staged blob for {name}")
        if hashlib.sha256(staged_bytes.stdout).digest() != hashlib.sha256(actual[name].read_bytes()).digest():
            raise BackupError(f"staged bytes differ from verified snapshot: {name}")
    print(f"staged snapshot verified: {len(indexed)} files")


def validate_revision(value: str, label: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise BackupError(f"{label} must be a full hexadecimal commit SHA")
    return value


def successful_deploy_workflow(repository: str, revision: str, fetch=api_json) -> dict[str, Any]:
    runs_url = f"https://api.github.com/repos/{repository}/actions/workflows/deploy-pages.yml/runs?head_sha={revision}&per_page=100"
    response = fetch(runs_url)
    runs = response.get("workflow_runs") if isinstance(response, dict) else None
    if not isinstance(runs, list) or len(runs) > 100:
        raise BackupError("deploy-pages workflow response is malformed or exceeded 100 runs")
    candidates = [
        run for run in runs
        if isinstance(run, dict)
        and isinstance(run.get("head_repository"), dict)
        and isinstance(run["head_repository"].get("full_name"), str)
        and run.get("head_sha") == revision
        and run.get("head_branch") == "main"
        and run.get("event") in {"push", "workflow_dispatch", "workflow_run"}
        and run["head_repository"].get("full_name", "").casefold() == repository.casefold()
        and run.get("path") == ".github/workflows/deploy-pages.yml"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    ]
    for run in candidates:
        jobs_url = f"https://api.github.com/repos/{repository}/actions/runs/{run.get('id')}/jobs?per_page=100"
        job_response = fetch(jobs_url)
        jobs = job_response.get("jobs") if isinstance(job_response, dict) else None
        if not isinstance(jobs, list) or len(jobs) > 100:
            raise BackupError("deploy-pages job evidence is malformed or exceeded 100 jobs")
        by_name = {job.get("name"): job for job in jobs if isinstance(job, dict)}
        build = by_name.get("build")
        deploy = by_name.get("deploy")
        if (
            build and build.get("status") == "completed" and build.get("conclusion") == "success"
            and deploy and deploy.get("status") == "completed" and deploy.get("conclusion") == "success"
        ):
            return run
    raise BackupError("no successful validated deploy-pages run with successful build and deploy jobs for this SHA")


def successful_pages_deployment(repository: str, revision: str, fetch=api_json) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repository}/deployments?environment=github-pages&per_page=100"
    deployments = fetch(url)
    if not isinstance(deployments, list) or len(deployments) > 100:
        raise BackupError("Pages deployment response is malformed or exceeded 100 records")
    for item in deployments:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int) or not isinstance(item.get("created_at"), str):
            raise BackupError("Pages deployment response contains malformed records")
    if not deployments:
        raise BackupError("no Pages deployments are available")
    latest = max(deployments, key=lambda item: (item["created_at"], item["id"]))
    if latest.get("sha") != revision:
        raise BackupError("latest github-pages deployment is not for the selected main SHA")
    statuses_url = f"https://api.github.com/repos/{repository}/deployments/{latest['id']}/statuses?per_page=1"
    statuses = fetch(statuses_url)
    if not isinstance(statuses, list) or not statuses or not isinstance(statuses[0], dict):
        raise BackupError("latest Pages deployment has no valid status evidence")
    if statuses[0].get("state") != "success":
        raise BackupError("latest Pages deployment status is not success")
    return latest


def verify_public_source(repository: str, revision: str, fetch=api_json) -> tuple[dict[str, Any], dict[str, Any]]:
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise BackupError("source repository must be OWNER/REPOSITORY")
    if any(part in {".", ".."} for part in repository.split("/")):
        raise BackupError("source repository contains an invalid path component")
    validate_revision(revision, "source SHA")
    ref = fetch(f"https://api.github.com/repos/{repository}/git/ref/heads/main")
    main_sha = (((ref or {}).get("object") or {}).get("sha")) if isinstance(ref, dict) else None
    if main_sha != revision:
        raise BackupError("selected source SHA is not the current public main revision")
    workflow = successful_deploy_workflow(repository, revision, fetch)
    deployment = successful_pages_deployment(repository, revision, fetch)
    return workflow, deployment


def record_for(snapshot: Path, source_sha: str, tooling_sha: str) -> dict[str, str]:
    return {
        "format": "daryllswer-private-backup-1",
        "sourceSHA": source_sha,
        "toolingSHA": tooling_sha,
        "manifestSHA256": hashlib.sha256((snapshot / "manifest-sha256.txt").read_bytes()).hexdigest(),
        "verifiedUTC": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def validate_snapshot(snapshot: Path, exporter, *, check_record: bool = True) -> dict[str, Any] | None:
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise BackupError("snapshot payload must be a real directory")
    for path in snapshot.rglob("*"):
        if path.is_symlink():
            raise BackupError(f"symlink in transferred payload: {path.relative_to(snapshot)}")
        relative = path.relative_to(snapshot).as_posix()
        pure = PurePosixPath(relative)
        if pure.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
            raise BackupError(f"unsafe payload path: {relative}")
        if path.is_file() and relative != RECORD_NAME and relative.startswith("data/"):
            repo_path = relative.removeprefix("data/")
            if not exporter.safe_repo_path(repo_path):
                raise BackupError(f"disallowed source payload path: {repo_path}")
    try:
        exporter.verify_bag(snapshot, allow_backup_record=True)
    except exporter.ExportError as exc:
        raise BackupError(str(exc)) from exc
    record_path = snapshot / RECORD_NAME
    if not check_record:
        if record_path.exists() or record_path.is_symlink():
            raise BackupError("prepared BagIt transfer must not contain a backup record")
        return None
    if record_path.is_symlink() or not record_path.is_file():
        raise BackupError("snapshot backup record must be a regular file")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BackupError("snapshot backup record is invalid JSON") from exc
    if not isinstance(record, dict) or record.get("format") != "daryllswer-private-backup-1":
        raise BackupError("snapshot backup record has an unsupported format")
    record_source = validate_revision(record.get("sourceSHA", ""), "record source SHA")
    record_tooling = validate_revision(record.get("toolingSHA", ""), "record tooling SHA")
    info_lines = (snapshot / "bag-info.txt").read_text(encoding="utf-8").splitlines()
    bag_source = [line.removeprefix("Source-Commit: ") for line in info_lines if line.startswith("Source-Commit: ")]
    bag_tooling = [line.removeprefix("Tooling-Commit: ") for line in info_lines if line.startswith("Tooling-Commit: ")]
    if bag_source != [record_source] or bag_tooling != [record_tooling]:
        raise BackupError("snapshot backup record does not match BagIt commit provenance")
    expected_manifest = hashlib.sha256((snapshot / "manifest-sha256.txt").read_bytes()).hexdigest()
    if record.get("manifestSHA256") != expected_manifest:
        raise BackupError("snapshot backup record manifest digest mismatch")
    return record


def prepare(repository: str, revision: str, source_checkout: Path, output: Path, tooling_sha: str) -> None:
    validate_revision(tooling_sha, "tooling SHA")
    if git(ROOT, "rev-parse", "HEAD") != tooling_sha:
        raise BackupError("trusted tooling checkout does not match the pinned tooling SHA")
    if git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BackupError("trusted tooling checkout is not clean")
    verify_public_source(repository, revision)
    if git(source_checkout, "rev-parse", "HEAD") != revision:
        raise BackupError("source checkout HEAD does not match the verified public main SHA")
    if git(source_checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BackupError("source checkout is not clean")
    exporter = load_exporter()
    bag = exporter.ensure_external_output(output, source_checkout)
    exporter.export(revision, bag, source_checkout)
    try:
        validate_snapshot(bag, exporter, check_record=False)
    except Exception:
        shutil.rmtree(bag, ignore_errors=True)
        raise
    print(f"prepared verified snapshot for {revision}: {bag}")


def changed_paths(repository: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain=v1", "--no-renames", "--untracked-files=all", "-z"],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise BackupError(f"git status failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    paths: set[str] = set()
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        if len(record) < 4:
            raise BackupError("git returned malformed worktree status")
        path = os.fsdecode(record[3:])
        paths.add(path)
    return paths


def _publish_verified_snapshot(
    source: Path, repo: Path, source_sha: str, tooling_sha: str,
    source_git_dir: Path, exporter,
) -> bool:
    verify_payload_matches_source(source, source_sha, source_git_dir, exporter)
    destination = repo / "snapshot"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise BackupError("existing snapshot must be a real directory")
    if destination.exists():
        existing_record_path = destination / RECORD_NAME
        if existing_record_path.is_symlink() or not existing_record_path.is_file():
            raise BackupError("existing snapshot has no valid backup record")
        existing = validate_snapshot(destination, exporter)
        assert existing is not None
        existing_sha = existing["sourceSHA"]
        verify_payload_matches_source(destination, existing_sha, source_git_dir, exporter)
        if existing_sha == source_sha:
            print(f"snapshot already verified for source SHA {source_sha}; no changes")
            return False
    stage = Path(tempfile.mkdtemp(prefix=f".{repo.name}-snapshot-stage-", dir=repo.parent))
    rollback_dir = Path(tempfile.mkdtemp(prefix=f".{repo.name}-snapshot-rollback-", dir=repo.parent))
    backup_old = rollback_dir / "snapshot"
    if os.stat(stage).st_dev != os.stat(repo).st_dev or os.stat(rollback_dir).st_dev != os.stat(repo).st_dev:
        shutil.rmtree(stage)
        shutil.rmtree(rollback_dir)
        raise BackupError("snapshot staging must share a filesystem with the backup checkout")
    moved_old = False
    installed_new = False
    try:
        shutil.rmtree(stage)
        shutil.copytree(source, stage, symlinks=True)
        record = record_for(stage, source_sha, tooling_sha)
        (stage / RECORD_NAME).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_snapshot(stage, exporter)
        verify_payload_matches_source(stage, source_sha, source_git_dir, exporter)
        if destination.exists():
            os.replace(destination, backup_old)
            moved_old = True
        os.replace(stage, destination)
        installed_new = True
        if any(path != "snapshot" and not path.startswith("snapshot/") for path in changed_paths(repo)):
            raise BackupError("publication changed paths outside snapshot/")
    except Exception:
        if installed_new and destination.exists():
            shutil.rmtree(destination)
        if moved_old and backup_old.exists():
            os.replace(backup_old, destination)
        if stage.exists():
            shutil.rmtree(stage)
        if rollback_dir.exists():
            shutil.rmtree(rollback_dir)
        raise
    shutil.rmtree(rollback_dir)
    print(f"published verified snapshot for {source_sha}")
    return True


def publish(
    payload: Path, repository: Path, source_repository: str, tooling_sha: str,
    exporter=None, fetch=api_json, source_git_dir: Path | None = None,
) -> bool:
    exporter = exporter or load_exporter()
    validate_revision(tooling_sha, "pinned tooling SHA")
    if git(ROOT, "rev-parse", "HEAD") != tooling_sha:
        raise BackupError("trusted tooling checkout does not match the pinned tooling SHA")
    if git(ROOT, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BackupError("trusted tooling checkout is not clean")
    if repository.is_symlink():
        raise BackupError("backup repository root cannot be a symlink")
    repo = repository.resolve(strict=True)
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BackupError("backup repository worktree must be clean before publication")
    if payload.is_symlink():
        raise BackupError("transferred snapshot path cannot be a symlink")
    source = payload.resolve(strict=True)
    if not source.is_dir():
        raise BackupError("transferred snapshot must be a real directory")
    if source == repo or repo in source.parents:
        raise BackupError("transferred snapshot must be outside the backup checkout")
    validate_snapshot(source, exporter, check_record=False)
    source_info = (source / "bag-info.txt").read_text(encoding="utf-8").splitlines()
    source_line = next((line for line in source_info if line.startswith("Source-Commit: ")), "")
    tooling_line = next((line for line in source_info if line.startswith("Tooling-Commit: ")), "")
    if not source_line or not tooling_line:
        raise BackupError("transferred bag lacks source or tooling commit provenance")
    source_sha = validate_revision(source_line.removeprefix("Source-Commit: "), "bag source SHA")
    if validate_revision(tooling_line.removeprefix("Tooling-Commit: "), "bag tooling SHA") != tooling_sha:
        raise BackupError("transferred bag does not match the expected trusted tooling SHA")
    verify_public_source(source_repository, source_sha, fetch)
    if source_git_dir is None:
        with tempfile.TemporaryDirectory(prefix="archive-source-git-") as temporary:
            git_dir = Path(temporary) / "source.git"
            fetch_source_commit(source_repository, source_sha, git_dir)
            destination = repo / "snapshot"
            if destination.exists() and not destination.is_symlink():
                previous_record = validate_snapshot(destination, exporter)
                assert previous_record is not None
                previous_sha = previous_record["sourceSHA"]
                if previous_sha != source_sha:
                    fetch_additional_source_commit(source_repository, previous_sha, git_dir)
            return _publish_verified_snapshot(source, repo, source_sha, tooling_sha, git_dir, exporter)
    fetched = str(git(source_git_dir, "rev-parse", source_sha))
    if fetched != source_sha:
        raise BackupError("provided source Git repository does not contain the exact source SHA")
    return _publish_verified_snapshot(source, repo, source_sha, tooling_sha, source_git_dir, exporter)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source-repository", required=True)
    prepare_parser.add_argument("--source-sha", required=True)
    prepare_parser.add_argument("--source-checkout", required=True, type=Path)
    prepare_parser.add_argument("--tooling-sha", required=True)
    prepare_parser.add_argument("--output", required=True, type=Path)
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--payload", required=True, type=Path)
    publish_parser.add_argument("--repository", required=True, type=Path)
    publish_parser.add_argument("--source-repository", required=True)
    publish_parser.add_argument("--tooling-sha", required=True)
    verify_parser = subparsers.add_parser("verify", help="verify BagIt payload and private backup record")
    verify_parser.add_argument("--snapshot", required=True, type=Path)
    staged_parser = subparsers.add_parser("verify-staged", help="verify staged snapshot paths and bytes before commit")
    staged_parser.add_argument("--repository", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(args.source_repository, args.source_sha, args.source_checkout, args.output, args.tooling_sha)
        elif args.command == "publish":
            publish(args.payload, args.repository, args.source_repository, args.tooling_sha)
        elif args.command == "verify":
            snapshot = Path(os.path.abspath(args.snapshot.expanduser()))
            record = validate_snapshot(snapshot, load_exporter())
            assert record is not None
            print(f"backup snapshot verification passed: source SHA {record['sourceSHA']}")
        else:
            verify_staged(args.repository)
        return 0
    except (BackupError, OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
        print(f"backup preservation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
