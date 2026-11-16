# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Exact canonical URL comparison with trailing path-slash tolerance."""


def _without_trailing_path_slashes(url: str) -> str:
    query_start = url.find("?")
    fragment_start = url.find("#")
    suffix_start = min((index for index in (query_start, fragment_start) if index >= 0), default=len(url))
    return url[:suffix_start].rstrip("/") + url[suffix_start:]


def canonical_urls_match(left: object, right: object) -> bool:
    """Match raw URL strings, ignoring only trailing slashes before query/fragment."""
    return (
        isinstance(left, str)
        and isinstance(right, str)
        and _without_trailing_path_slashes(left) == _without_trailing_path_slashes(right)
    )
