#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT
"""Build IPv6 prefix hierarchy artefacts from CSV sheet exports."""

from __future__ import annotations

import csv
import hashlib
import ipaddress
import json
import re
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalise_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "prefix"


def artefact_info(root: Path, path: Path, body: bytes, content_type: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "content_type": content_type,
    }


def read_prefix_rows(root: Path, manifest: dict) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for tab in manifest.get("tabs", []):
        csv_path = root / tab["csv"]["path"]
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "Prefix" not in reader.fieldnames:
                continue
            label_field = next((name for name in reader.fieldnames if name != "Prefix" and name.lower() != "notes"), None)
            for index, row in enumerate(reader, start=2):
                prefix_value = (row.get("Prefix") or "").strip()
                try:
                    network = ipaddress.ip_network(prefix_value, strict=True)
                except ValueError:
                    continue
                if network.version != 6:
                    continue
                canonical = network.compressed
                if canonical in seen:
                    continue
                seen.add(canonical)
                label = (row.get(label_field or "") or "").strip()
                notes = (row.get("Notes") or "").strip()
                rows.append({
                    "id": normalise_id(canonical),
                    "prefix": canonical,
                    "prefix_length": network.prefixlen,
                    "first_address": str(network.network_address),
                    "last_address": str(network.broadcast_address),
                    "address_count_power": 128 - network.prefixlen,
                    "label": label,
                    "notes": notes,
                    "source_sheet": tab.get("name"),
                    "source_csv": tab["csv"]["path"],
                    "source_row": index,
                    "_network": network,
                })
    return sorted(rows, key=lambda item: (item["prefix_length"], int(item["_network"].network_address)))


def attach_children(rows: list[dict]) -> dict:
    by_prefix = {item["prefix"]: {k: v for k, v in item.items() if k != "_network"} | {"children": []} for item in rows}
    networks = {item["prefix"]: item["_network"] for item in rows}
    root_prefix = rows[0]["prefix"] if rows else "IPv6"

    for item in rows:
        network = item["_network"]
        candidates = [
            other
            for other in rows
            if other is not item
            and other["_network"].prefixlen < network.prefixlen
            and network.subnet_of(other["_network"])
        ]
        if not candidates:
            continue
        parent = max(candidates, key=lambda other: other["_network"].prefixlen)
        by_prefix[parent["prefix"]]["children"].append(by_prefix[item["prefix"]])

    child_prefixes = {
        child["prefix"]
        for node in by_prefix.values()
        for child in node["children"]
    }
    roots = [node for prefix, node in by_prefix.items() if prefix not in child_prefixes]
    if len(roots) == 1:
        return roots[0]
    return {
        "id": "ipv6-prefix-plan",
        "prefix": root_prefix,
        "label": "IPv6 prefix plan",
        "notes": "Artificial root for disconnected CSV prefixes.",
        "children": roots,
    }


def prune_empty_children(node: dict) -> dict:
    node["children"] = [prune_empty_children(child) for child in node.get("children", [])]
    if not node["children"]:
        node.pop("children", None)
    return node


def count_nodes(node: dict) -> int:
    return 1 + sum(count_nodes(child) for child in node.get("children", []))


def max_depth(node: dict, depth: int = 0) -> int:
    return max([depth] + [max_depth(child, depth + 1) for child in node.get("children", [])])


def dot_id(prefix: str) -> str:
    return "n_" + re.sub(r"[^A-Za-z0-9_]+", "_", prefix)


def render_dot(tree: dict) -> str:
    lines = [
        "digraph ipv6_hierarchy {",
        "  graph [rankdir=LR, splines=ortho];",
        "  node [shape=box, style=\"rounded,filled\", fillcolor=\"#edf4f7\", color=\"#0b6f8a\", fontname=\"Arial\"];",
        "  edge [color=\"#5f6c78\"];",
    ]

    def visit(node: dict) -> None:
        label = node.get("prefix", "")
        if node.get("label"):
            label += f"\\n{node['label']}"
        lines.append(f'  {dot_id(node.get("prefix", ""))} [label="{label}"];')
        for child in node.get("children", []):
            lines.append(f'  {dot_id(node.get("prefix", ""))} -> {dot_id(child.get("prefix", ""))};')
            visit(child)

    visit(tree)
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_ipv6_hierarchy_artefacts(root: Path, out: Path, manifest: dict) -> dict:
    rows = read_prefix_rows(root, manifest)
    tree = prune_empty_children(attach_children(rows))
    json_body = json.dumps(tree, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    dot_body = render_dot(tree).encode("utf-8")
    (out / "cidr-hierarchy.html").unlink(missing_ok=True)
    return {
        "model": "rooted_ipv6_prefix_containment_tree",
        "source": "CSV Prefix columns",
        "node_count": count_nodes(tree),
        "max_depth": max_depth(tree),
        "json": artefact_info(root, out / "cidr-hierarchy.json", json_body, "application/json; charset=utf-8"),
        "dot": artefact_info(root, out / "cidr-hierarchy.dot", dot_body, "text/vnd.graphviz; charset=utf-8"),
    }
