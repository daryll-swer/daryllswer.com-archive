#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Scan for obvious secrets and local-only state before public commit/push."""

from __future__ import annotations

import re
import sys
import datetime as dt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".cache", ".tmp", ".preview", "__pycache__", ".venv", "node_modules"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ods", ".xlsx", ".pdf", ".ico", ".zip", ".gz"}

PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    ("openai api key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("generic secret assignment", re.compile(r"(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}")),
    ("macOS local user path", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("windows local user path", re.compile(r"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._-]+\\\\")),
    ("cookie header", re.compile(r"(?i)\bcookie\s*:\s*[^\\n]{12,}")),
]


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in SKIP_EXTS:
            continue
        yield path


def main() -> int:
    findings: list[str] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path.relative_to(ROOT)}:{lineno}: {name}")
    if findings:
        report = ["# Public Safety Scan", "", f"Generated: {dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}", "", "## Result", "", "- Status: failed", f"- Findings: {len(findings)}", "", "## Findings", ""]
        report.extend(f"- {finding}" for finding in findings)
        (ROOT / "docs" / "PUBLIC_SAFETY.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        print("public-safety scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    report = [
        "# Public Safety Scan",
        "",
        f"Generated: {dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        "## Result",
        "",
        "- Status: passed",
        "- Findings: 0",
        "",
        "No obvious secrets, credentials, cookies, private notes, or local-only paths were found by the pattern scan.",
        "",
        "This is a heuristic scan, not a proof that no sensitive material exists.",
    ]
    (ROOT / "docs" / "PUBLIC_SAFETY.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("public-safety scan passed: no obvious secrets/local-only state found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
