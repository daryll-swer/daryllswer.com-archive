#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Check that pinned direct requirements are represented by the hash lock."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def requirements(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)(?:\s+\\)?\s*", line)
        if match:
            result[match.group(1).lower().replace("_", "-")] = match.group(2)
        elif line.lstrip().startswith("--hash=") or not line.strip() or line.lstrip().startswith("#"):
            continue
        else:
            raise ValueError(f"unsupported unhashed/direct requirement syntax in {path.name}: {line}")
    return result


def main() -> int:
    direct = requirements(ROOT / "requirements.in")
    locked = requirements(ROOT / "requirements-lock.txt")
    missing = {name: version for name, version in direct.items() if locked.get(name) != version}
    if missing:
        raise SystemExit(f"direct requirements differ from hash lock: {missing}")
    lock_text = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    for name, version in direct.items():
        if not re.search(rf"(?m)^{re.escape(name)}=={re.escape(version)}\s+\\$", lock_text, re.IGNORECASE):
            raise SystemExit(f"lock entry for {name}=={version} is missing hash continuation")
    print(f"requirements lock matches {len(direct)} pinned direct dependencies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
