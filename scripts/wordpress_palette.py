#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""WordPress colour preset helpers for the static archive renderer."""

from __future__ import annotations


WORDPRESS_COLOR_PRESETS = {
    "black": "#000000",
    "cyan-bluish-gray": "#abb8c3",
    "white": "#ffffff",
    "pale-pink": "#f78da7",
    "vivid-red": "#cf2e2e",
    "luminous-vivid-orange": "#ff6900",
    "luminous-vivid-amber": "#fcb900",
    "light-green-cyan": "#7bdcb5",
    "vivid-green-cyan": "#00d084",
    "pale-cyan-blue": "#8ed1fc",
    "vivid-cyan-blue": "#0693e3",
    "vivid-purple": "#9b51e0",
}


def wordpress_palette_css(scope: str = ".article-body") -> str:
    lines = [":root {"]
    for name, value in WORDPRESS_COLOR_PRESETS.items():
        lines.append(f"  --wp--preset--color--{name}: {value};")
    lines.extend([
        "}",
        f"{scope} mark.has-inline-color,",
        f"{scope} .has-inline-color {{",
        "  background: transparent;",
        "  padding: 0;",
        "}",
    ])
    for name in WORDPRESS_COLOR_PRESETS:
        var_name = f"var(--wp--preset--color--{name})"
        lines.append(f"{scope} .has-{name}-color {{ color: {var_name} !important; }}")
        lines.append(f"{scope} .has-{name}-background-color {{ background-color: {var_name} !important; }}")
        lines.append(f"{scope} .has-{name}-border-color {{ border-color: {var_name} !important; }}")
    return "\n".join(lines)
