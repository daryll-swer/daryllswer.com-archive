#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Shared self-hosted font declarations for generated archive HTML."""

from __future__ import annotations

import shutil
from pathlib import Path


FONT_SOURCE_DIR = Path("assets") / "fonts"

POPPINS_DEVANAGARI_RANGE = (
    "U+0900-097F, U+1CD0-1CF9, U+200C-200D, U+20A8, U+20B9, "
    "U+20F0, U+25CC, U+A830-A839, U+A8E0-A8FF, U+11B00-11B09"
)
LATIN_EXT_RANGE = (
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, "
    "U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, "
    "U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, "
    "U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF"
)
LATIN_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, "
    "U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, "
    "U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
)

FONT_FACES = [
    ("Poppins", "300", "Poppins-Light-devanagari.woff2", POPPINS_DEVANAGARI_RANGE),
    ("Poppins", "300", "Poppins-Light-latin-ext.woff2", LATIN_EXT_RANGE),
    ("Poppins", "300", "Poppins-Light-latin.woff2", LATIN_RANGE),
    ("Poppins", "400", "Poppins-Regular-devanagari.woff2", POPPINS_DEVANAGARI_RANGE),
    ("Poppins", "400", "Poppins-Regular-latin-ext.woff2", LATIN_EXT_RANGE),
    ("Poppins", "400", "Poppins-Regular-latin.woff2", LATIN_RANGE),
    ("Poppins", "600", "Poppins-SemiBold-devanagari.woff2", POPPINS_DEVANAGARI_RANGE),
    ("Poppins", "600", "Poppins-SemiBold-latin-ext.woff2", LATIN_EXT_RANGE),
    ("Poppins", "600", "Poppins-SemiBold-latin.woff2", LATIN_RANGE),
    ("Poppins", "700", "Poppins-Bold-devanagari.woff2", POPPINS_DEVANAGARI_RANGE),
    ("Poppins", "700", "Poppins-Bold-latin-ext.woff2", LATIN_EXT_RANGE),
    ("Poppins", "700", "Poppins-Bold-latin.woff2", LATIN_RANGE),
    ("Raleway", "300 800", "Raleway-variable-latin-ext.woff2", LATIN_EXT_RANGE),
    ("Raleway", "300 800", "Raleway-variable-latin.woff2", LATIN_RANGE),
]

FONT_BODY_STACK = '"Poppins", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
FONT_HEADING_STACK = '"Raleway", "Poppins", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'


def font_face_css(font_prefix: str) -> str:
    prefix = font_prefix.rstrip("/") + "/"
    rules = []
    for family, weight, filename, unicode_range in FONT_FACES:
        rules.append(
            "@font-face {\n"
            f"  font-family: '{family}';\n"
            "  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            "  font-display: swap;\n"
            f"  src: url('{prefix}{filename}') format('woff2');\n"
            f"  unicode-range: {unicode_range};\n"
            "}"
        )
    return "\n".join(rules)


def copy_font_assets(root: Path, destination: Path) -> None:
    source = root / FONT_SOURCE_DIR
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)
