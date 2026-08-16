#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Prepare the bounded proprietary favicon derivative used by GitHub Pages."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DERIVATIVE_SIZE = 512
SOURCE_PATH = "assets/brand/01_DS_Favicon_Dark_Mode.png"
DERIVATIVE_PATH = "assets/brand/derivatives/01_DS_Favicon_Dark_Mode-512.png"
PAGES_OUTPUT_PATH = "docs/assets/brand/01_DS_Favicon_Dark_Mode-512.png"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(root: Path) -> tuple[Path, dict, dict, Path, Path]:
    """Load the brand manifest and resolve its controlled asset paths."""
    manifest_path = root / "assets" / "brand" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != 1:
        raise ValueError("brand manifest must contain exactly one asset")

    asset = assets[0]
    source_name = asset.get("path")
    pages_derivative = asset.get("pages_derivative")
    derivative_name = pages_derivative.get("path") if isinstance(pages_derivative, dict) else None
    if not isinstance(source_name, str) or Path(source_name).name != source_name:
        raise ValueError("brand manifest source path must be a filename")
    if not isinstance(derivative_name, str) or not Path(derivative_name).name:
        raise ValueError("brand manifest derivative path is missing")
    if source_name != Path(SOURCE_PATH).name or derivative_name != PAGES_OUTPUT_PATH:
        raise ValueError("brand manifest favicon paths do not match the controlled asset contract")
    prepared_name = pages_derivative.get("prepared_path") if isinstance(pages_derivative, dict) else None
    if prepared_name != DERIVATIVE_PATH:
        raise ValueError(f"brand manifest prepared derivative path must be {DERIVATIVE_PATH}")

    source = root / "assets" / "brand" / source_name
    derivative = root / prepared_name
    return manifest_path, manifest, asset, source, derivative


def render_derivative(source_path: Path) -> bytes:
    previous_pixel_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 150_000_000
    try:
        with Image.open(source_path) as source:
            if source.format != "PNG":
                raise ValueError("proprietary brand favicon source must be a PNG")
            if source.width != source.height:
                raise ValueError("proprietary brand favicon source must be square")
            rendered = source.convert("RGBA")
            try:
                rendered.thumbnail((DERIVATIVE_SIZE, DERIVATIVE_SIZE), Image.Resampling.LANCZOS)
                if rendered.size != (DERIVATIVE_SIZE, DERIVATIVE_SIZE):
                    raise ValueError("proprietary brand favicon derivative has unexpected dimensions")
                output = io.BytesIO()
                rendered.save(output, format="PNG", optimize=True)
                return output.getvalue()
            finally:
                rendered.close()
    finally:
        Image.MAX_IMAGE_PIXELS = previous_pixel_limit


def write_atomically(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as fh:
            temporary_path = Path(fh.name)
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def update_manifest(manifest_path: Path, manifest: dict, source_checksum: str, derivative_checksum: str) -> None:
    asset = manifest["assets"][0]
    asset["sha256"] = source_checksum
    pages_derivative = asset["pages_derivative"]
    pages_derivative["source_sha256"] = source_checksum
    pages_derivative["sha256"] = derivative_checksum
    write_atomically(
        manifest_path,
        (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    )


def prepare(root: Path) -> tuple[Path, str, bool]:
    manifest_path, manifest, asset, source_path, derivative_path = load_manifest(root)
    if not source_path.exists():
        raise FileNotFoundError(f"missing proprietary brand favicon master: {source_path}")

    source_checksum = sha256_file(source_path)
    pages_derivative = asset["pages_derivative"]
    manifest_source_checksum = asset.get("sha256")
    derivative_source_checksum = pages_derivative.get("source_sha256")
    derivative_checksum = pages_derivative.get("sha256")
    master_changed = (
        not isinstance(manifest_source_checksum, str)
        or not isinstance(derivative_source_checksum, str)
        or source_checksum != manifest_source_checksum
        or source_checksum != derivative_source_checksum
    )
    if not master_changed:
        if not derivative_path.exists():
            raise ValueError("controlled favicon derivative is missing while the master is unchanged")
        if not isinstance(derivative_checksum, str) or sha256_file(derivative_path) != derivative_checksum:
            raise ValueError("controlled favicon derivative checksum is inconsistent while the master is unchanged")
        return derivative_path, source_checksum, False

    candidate = render_derivative(source_path)
    candidate_checksum = sha256_bytes(candidate)
    changed = not derivative_path.exists() or derivative_path.read_bytes() != candidate
    original_derivative = derivative_path.read_bytes() if derivative_path.exists() else None
    try:
        if changed:
            write_atomically(derivative_path, candidate)
        update_manifest(manifest_path, manifest, source_checksum, candidate_checksum)
    except Exception:
        if original_derivative is None:
            derivative_path.unlink(missing_ok=True)
        else:
            write_atomically(derivative_path, original_derivative)
        raise
    return derivative_path, source_checksum, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: script repository)")
    args = parser.parse_args()
    root = args.root.resolve()
    derivative_path, source_checksum, changed = prepare(root)
    state = "updated" if changed else "unchanged"
    print(f"favicon derivative {state}: {derivative_path}")
    print(f"master sha256: {source_checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
