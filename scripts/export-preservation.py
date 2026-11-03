#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Export and verify a BagIt-compatible archive from an approved Git commit."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git", "__pycache__", ".cache", ".venv", ".venv312", "node_modules",
    "cache", "caches", "private", "secrets",
    "credentials", "auth", "migrations", "migration",
}
EXCLUDED_NAMES = {
    ".env", ".netrc", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "known_hosts",
}
EXCLUDED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdbx", ".token", ".secret"}
ROOT_FILES = {
    ".gitattributes", "AGENTS.md", "ARCHITECTURE.md", "ESCALATION.md",
    "IMPLEMENTATION_STATUS.md",
    "LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt",
    "LICENSES/DARYLL-SWER-PROPRIETARY-CONTENT-NOTICE.txt",
    "LICENSES/MIT.txt", "LICENSES/SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt",
    "LICENSING.md", "Makefile", "README.md", "archive-manifest.json",
    "archive-status.json", "requirements.txt", "requirements.in",
    "requirements-lock.txt", "requirements.lock",
}
ALLOWED_ROOTS = {"assets", "content", "data", "docs", "schemas", "scripts"}


class ExportError(Exception):
    """Raised when an export cannot be completed safely."""


def git(args: list[str], *, repository: Path | None = None, binary: bool = False) -> bytes | str:
    repository = repository or ROOT
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise ExportError(f"git {' '.join(args[:2])} failed: {message}")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def validate_commit(revision: str, allow_dirty: bool, source_repository: Path | None = None) -> str:
    source_repository = source_repository or ROOT
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
        raise ExportError("--commit must be an explicit full commit hash")
    commit = str(git(["rev-parse", "--verify", f"{revision}^{{commit}}"], repository=source_repository))
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ExportError("Git returned an invalid commit identifier")
    if not allow_dirty:
        status = str(git(["status", "--porcelain=v1", "--untracked-files=all"], repository=source_repository))
        if status:
            raise ExportError("working tree is dirty; use a clean checkout or explicitly pass --allow-dirty")
    return commit


def safe_repo_path(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or any(part in {"", ".", ".."} for part in name.split("/")):
        return False
    if any(
        part.lower() in EXCLUDED_NAMES
        or part.lower().startswith((".env.", "secret", "credential"))
        or part.lower().endswith(tuple(EXCLUDED_SUFFIXES))
        for part in path.parts
    ):
        return False
    if name in ROOT_FILES:
        return True
    if name == "docs/.nojekyll":
        return True
    if name in {"maintenance/backup/README.md", "maintenance/backup/backup.yml"}:
        return True
    if name.startswith(".github/workflows/") or name == ".github/dependabot.yml":
        return True
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False
    if any(part.startswith(".") and part != ".well-known" for part in path.parts):
        return False
    return bool(path.parts and path.parts[0] in ALLOWED_ROOTS | {"tests"})


def committed_files(commit: str, source_repository: Path | None = None) -> list[tuple[str, str]]:
    source_repository = source_repository or ROOT
    raw = git(["ls-tree", "-r", "-z", "--full-tree", commit], repository=source_repository, binary=True)
    entries: list[tuple[str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_name = record.split(b"\t", 1)
        mode, kind, object_id = metadata.decode("ascii").split()
        name = os.fsdecode(encoded_name)
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ExportError(f"unsupported committed file type or mode: {name}")
        if not safe_repo_path(name):
            continue
        entries.append((name, object_id))
    if not entries:
        raise ExportError("commit contains no eligible archive files")
    return sorted(entries)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_path(path: str) -> str:
    return path.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def decode_manifest_path(path: str) -> str:
    return unquote(path, errors="strict")


def verify_bag(bag: Path, *, allow_backup_record: bool = False) -> None:
    if bag.is_symlink() or not bag.is_dir():
        raise ExportError("bag path must be a real directory")
    data_dir = bag / "data"
    if data_dir.is_symlink() or not data_dir.is_dir():
        raise ExportError("payload path must be a real directory")
    bagit = bag / "bagit.txt"
    payload_manifest = bag / "manifest-sha256.txt"
    tag_manifest = bag / "tagmanifest-sha256.txt"
    if any(path.is_symlink() or not path.is_file() for path in (bagit, payload_manifest, tag_manifest)):
        raise ExportError("BagIt tag files must be regular files, not symlinks")
    if bagit.read_bytes() != b"BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n":
        raise ExportError("invalid bagit.txt")
    expected_payload: dict[str, str] = {}
    for line in payload_manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) data/(.+)", line)
        if not match:
            raise ExportError("malformed payload manifest entry")
        checksum, encoded = match.groups()
        name = decode_manifest_path(encoded)
        if not safe_repo_path(name) or name in expected_payload:
            raise ExportError(f"unsafe or duplicate payload path: {name}")
        expected_payload[name] = checksum
    actual_payload: set[str] = set()
    for path in data_dir.rglob("*"):
        if path.is_symlink():
            raise ExportError(f"symlink in payload: {path}")
        if path.is_file():
            actual_payload.add(path.relative_to(data_dir).as_posix())
    if actual_payload != set(expected_payload):
        raise ExportError("payload manifest does not exactly cover payload files")
    for name, expected in expected_payload.items():
        if sha256_file(bag / "data" / name) != expected:
            raise ExportError(f"payload checksum mismatch: {name}")
    expected_tags: dict[str, str] = {}
    for line in tag_manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) (.+)", line)
        if not match:
            raise ExportError("malformed tag manifest entry")
        checksum, encoded = match.groups()
        name = decode_manifest_path(encoded)
        tag_path = PurePosixPath(name)
        if (
            tag_path.is_absolute()
            or "\\" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or name.startswith("data/")
            or name in expected_tags
        ):
            raise ExportError(f"unsafe or duplicate tag path: {name}")
        expected_tags[name] = checksum
    tag_files: set[str] = set()
    for path in bag.rglob("*"):
        if path.is_symlink():
            raise ExportError(f"symlink in bag: {path}")
        if path.is_file() and path != tag_manifest and not path.is_relative_to(data_dir):
            relative = path.relative_to(bag).as_posix()
            if allow_backup_record and relative == "backup-record.json":
                continue
            tag_files.add(relative)
    if tag_files != set(expected_tags):
        raise ExportError("tag manifest does not exactly cover tag files")
    for name, expected in expected_tags.items():
        if sha256_file(bag / name) != expected:
            raise ExportError(f"tag checksum mismatch: {name}")


def ensure_external_output(output: Path, source_repository: Path | None = None) -> Path:
    source_repository = source_repository or ROOT
    candidate = output.expanduser()
    parent = candidate.parent.resolve(strict=True)
    destination = parent / candidate.name
    if destination.exists() or destination.is_symlink():
        raise ExportError("output destination already exists")
    source = source_repository.resolve(strict=True)
    tooling = ROOT.resolve(strict=True)
    if destination == source or source in destination.parents or destination == tooling or tooling in destination.parents:
        raise ExportError("output must be outside the repository")
    if not candidate.name or candidate.name in {".", ".."}:
        raise ExportError("invalid output path")
    return destination


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def export(commit: str, output: Path, source_repository: Path | None = None) -> None:
    source_repository = source_repository or ROOT
    target = ensure_external_output(output, source_repository)
    files = committed_files(commit, source_repository)
    parent = target.parent
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=parent))
    try:
        (staging / "data").mkdir()
        payload_entries: list[str] = []
        for name, object_id in files:
            content = git(["cat-file", "blob", object_id], repository=source_repository, binary=True)
            destination = staging / "data" / name
            write_file(destination, content)
            payload_entries.append(f"{hashlib.sha256(content).hexdigest()} data/{manifest_path(name)}")
        toolchain = str(git(["--version"], repository=source_repository))
        tooling_commit = str(git(["rev-parse", "HEAD"]))
        info = (
            "Source-Commit: " + commit + "\n"
            "Source-Repository: https://github.com/daryll-swer/daryllswer.com-archive\n"
            "Tooling-Commit: " + tooling_commit + "\n"
            "Exporter-Format: daryllswer-preservation-1\n"
            "Exporter-Python: " + sys.version.split()[0] + "\n"
            "Exporter-Git: " + toolchain.removeprefix("git version ") + "\n"
        )
        readme = (
            "# Archive Preservation Package\n\n"
            "This BagIt-compatible package contains committed archive sources, media, metadata, "
            "rights records, generated GitHub Pages output, and selected rebuild tooling and instructions.\n\n"
            "## Restore, verify, serve, and rebuild\n\n"
            "To transport the directory, create an archive with `tar -cf preservation.tar -C /path/to/parent BAG_NAME`; "
            "restore with `tar -xf preservation.tar`. After extracting a regular package, verify it from that directory with "
            "`python3 data/scripts/export-preservation.py --verify .`. For a private backup snapshot, run "
            "`python3 data/scripts/backup-preservation.py verify --snapshot .`; it verifies the BagIt files and "
            "the additional `backup-record.json` provenance. Both checks are offline. "
            "Serve the preserved Pages tree locally with `python3 -m http.server 8000 --directory data/docs`. "
            "To rebuild Pages, use Python 3.12 and install the pinned, hashed dependencies with "
            "`python3 -m venv .venv` then `./.venv/bin/python -m pip install --require-hashes -r data/requirements-lock.txt`; "
            "then run `make -C data PYTHON=\"$(pwd)/.venv/bin/python\" render-site` from the package root. "
            "Dependency installation may require package access; it is not an offline step. "
            "Offline repository validation can be run with `./.venv/bin/python data/scripts/validate-mirror.py --offline --no-report`; "
            "the package includes `.github/workflows/` and `data/tests/` for validation guards. Git-history-dependent "
            "sync, drift, and workflow operations cannot run because this package intentionally excludes `.git`. "
            "The source-commit record identifies the exact archived revision.\n\n"
            "To validate offline, block outbound networking at the operating-system or container boundary while running "
            "the checksum verifier and local Pages checks.\n\n"
            "## External references\n\n"
            "External hyperlinks, embedded media, and third-party documents are references, not archived copies. "
            "The generated package does not guarantee that those external resources remain available.\n"
        )
        write_file(staging / "bagit.txt", b"BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n")
        write_file(staging / "bag-info.txt", info.encode("utf-8"))
        write_file(staging / "README-PRESERVATION.md", readme.encode("utf-8"))
        write_file(staging / "manifest-sha256.txt", ("\n".join(payload_entries) + "\n").encode("utf-8"))
        tags = sorted(path.relative_to(staging).as_posix() for path in staging.iterdir() if path.is_file())
        tag_entries = [f"{sha256_file(staging / name)} {manifest_path(name)}" for name in tags]
        write_file(staging / "tagmanifest-sha256.txt", ("\n".join(tag_entries) + "\n").encode("utf-8"))
        verify_bag(staging)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verify_bag(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="explicit approved source commit")
    parser.add_argument("--output", type=Path, help="new output directory outside the repository")
    parser.add_argument("--source-repository", type=Path, help="explicit source checkout; exporter remains trusted tooling")
    parser.add_argument("--allow-dirty", action="store_true", help="allow local changes; only the named commit is exported")
    parser.add_argument("--verify", type=Path, help="verify an extracted BagIt directory")
    args = parser.parse_args(argv)
    try:
        if args.verify is not None:
            if args.commit or args.output or args.allow_dirty or args.source_repository:
                raise ExportError("--verify cannot be combined with export options")
            verify_bag(Path(os.path.abspath(args.verify.expanduser())))
            print("BagIt verification passed")
            return 0
        if not args.commit or args.output is None:
            parser.error("--commit and --output are required for export")
        source_repository = (args.source_repository or ROOT).expanduser().resolve(strict=True)
        commit = validate_commit(args.commit, args.allow_dirty, source_repository)
        export(commit, args.output, source_repository)
        print(f"verified preservation package: {args.output}")
        return 0
    except (ExportError, OSError, UnicodeError, ValueError) as exc:
        print(f"preservation export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
