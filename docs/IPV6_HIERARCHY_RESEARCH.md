# IPv6 CIDR Hierarchy Research

Generated: 2026-07-06

## Decision Supported

Replace or supplement the AS141253 multi-sheet workbook with a more readable
web-native representation of IPv6 CIDR hierarchy while keeping CSV as the
editable source of truth.

## Source Matrix

| Source | Type | Relevance |
| --- | --- | --- |
| RFC 4291, <https://www.rfc-editor.org/info/rfc4291/> | Standard | Defines IPv6 addressing architecture and prefix/address model. |
| RFC 5952, <https://www.rfc-editor.org/info/rfc5952/> | Standard | Defines recommended canonical IPv6 text representation. |
| Python `ipaddress`, <https://docs.python.org/3/library/ipaddress.html> | Official runtime docs | Provides IPv4/IPv6 network parsing and containment operations used by the generator. |
| D3 hierarchy, <https://d3js.org/d3-hierarchy> | Official library docs | Strong candidate for future interactive tree, cluster, partition, icicle, or sunburst layouts. |
| Cytoscape.js, <https://js.cytoscape.org/> | Official library docs | Strong candidate for richer graph analysis/visualisation; heavier than needed for this tree PoC. |
| Mermaid on GitHub, <https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams> | Official GitHub docs | Useful for Markdown diagrams, but less suitable for large interactive prefix trees on Pages. |
| Graphviz DOT, <https://graphviz.org/doc/info/lang.html> | Official format docs | Useful durable graph interchange/export format. |
| W3C CSVW metadata, <https://www.w3.org/TR/tabular-metadata/> | Web data standard | Supports the existing CSV-plus-metadata direction for spreadsheet artefacts. |

## Evaluation

| Option | Fit | Notes |
| --- | --- | --- |
| Rooted prefix tree | High | Correct model when every child prefix belongs to one most-specific parent prefix. Good for /32 -> /34 -> /40 -> /44 -> /48 -> /52/56/64 allocations. |
| DAG | Low for current data | CIDR containment should not need multi-parent edges. A DAG only becomes useful if the model later overlays orthogonal relationships such as service ownership, geography, and operational state. |
| Collapsible indented tree | High | Works well in static HTML, keyboard/screen-reader friendly with `<details>`, and readable on GitHub Pages without external JS. |
| D3 tree/cluster | High future fit | Best richer interactive view after the data model is validated; supports compact hierarchy layouts. |
| D3 partition/icicle/sunburst | Medium | Useful for allocation-size visualisation, but can hide labels and become harder to read for operational prefix names. |
| Cytoscape.js | Medium | Excellent graph library, but more weight and complexity than needed for a single containment tree. |
| Mermaid | Low to medium | Good for repo Markdown diagrams, but large prefix sets become unwieldy and GitHub Pages would still need rendering support. |
| Graphviz DOT | Medium | Good export/debug artefact and offline rendering path, but static SVG/PNG output is less ergonomic for large expandable trees. |

## Implemented Proof Of Concept

Implemented files:

- `scripts/ipv6_hierarchy.py`
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.html`
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json`
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.dot`

Model:

- parse every CSV row with a valid IPv6 value in the `Prefix` column;
- canonicalise using Python `ipaddress`;
- sort prefixes by prefix length and network address;
- choose the parent as the most-specific existing supernet containing the child;
- emit a rooted tree.

Current generated graph:

- 153 prefix nodes;
- maximum depth 5;
- self-contained HTML, no CDN dependency;
- adjacent JSON and Graphviz DOT outputs for future visualisation work.

## Recommendation

Keep the workbook as the default sheet page for now, but promote
`cidr-hierarchy.html` as the readability proof of concept. If this view proves
useful, the next iteration should add a richer D3 hierarchy view generated from
`cidr-hierarchy.json`, with the current self-contained `<details>` tree kept as
the durable fallback.
