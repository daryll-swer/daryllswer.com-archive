#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Shared conservative classification for public source observations."""

from __future__ import annotations

import socket
import ssl
import urllib.error


class SourceObservationError(Exception):
    def __init__(self, kind: str, detail: str, *, countable: bool):
        super().__init__(detail)
        self.kind = kind
        self.countable = countable


def classify_http_status(status: int) -> tuple[str, bool]:
    if status in {401, 403, 429}:
        return "access_restricted", False
    if status in {404, 410}:
        return "not_found", True
    if 500 <= status <= 599:
        return "server_error", True
    if 300 <= status <= 399:
        return "redirect_blocked", False
    if 200 <= status <= 299:
        return "success", False
    return "unexpected_http_status", False


def classify_exception(exc: Exception) -> SourceObservationError:
    if isinstance(exc, SourceObservationError):
        return exc
    if isinstance(exc, urllib.error.HTTPError):
        status = int(exc.code)
        kind, countable = classify_http_status(status)
        exc.close()
        return SourceObservationError(kind, f"HTTP {status}", countable=countable)
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, Exception):
        return classify_exception(exc.reason)
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError):
        return SourceObservationError("tls", str(exc), countable=True)
    if isinstance(reason, socket.gaierror) or isinstance(exc, socket.gaierror):
        return SourceObservationError("dns", str(exc), countable=True)
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, urllib.error.URLError)):
        return SourceObservationError("transport", str(exc), countable=True)
    return SourceObservationError("internal_error", f"{type(exc).__name__}: {exc}", countable=False)
