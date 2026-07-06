# Decisions

## 2026-07-06: Use Static-Site Page Bundles

- Decision: Store posts as `content/posts/YYYY-MM-DD-slug/index.md` bundles.
- Rationale: This sorts lexically, groups assets with their article, and remains
  compatible with common static-site conventions.
- Impact: Scripts generate one directory per post with sidecar source,
  metadata, and asset manifests.

## 2026-07-06: Preserve HTML Snapshots Alongside Markdown

- Decision: Keep `source/rendered-article.html` and `source/canonical-page.html`
  for each post.
- Rationale: Markdown is readable and diffable, but cannot preserve every
  WordPress block, embed, or layout detail.
- Impact: Consumers can inspect Markdown for readability and HTML for fidelity.

## 2026-07-06: License Scripts and Tooling Under MIT

- Decision: License repository scripts and tooling under MIT.
- Rationale: Owner explicitly selected MIT for script/tooling code in a
  side-thread decision.
- Impact: MIT applies to `scripts/`, `Makefile`, and repository tooling code.
  It does not apply to mirrored article content, mirrored media, spreadsheet
  content, third-party media, or external artefacts.

## 2026-07-06: Exclude Donation and Support CTAs

- Decision: Remove donation/support calls to action and article blocks linking
  to `/donation/` from generated archive article bodies.
- Rationale: These blocks are live-site operational content, not durable blog
  content. They would become stale or broken if daryllswer.com is no longer
  available.
- Impact: `make sync` filters these blocks, and `make validate` checks they do
  not reappear in generated Markdown, rendered article snapshots, or archived
  REST post JSON.

## 2026-07-06: Exclude Operational Sponsor Lead CTAs

- Decision: Remove sponsor/trial lead CTAs from generated archive article
  bodies when they are operational promotion rather than durable article
  substance.
- Rationale: Trial links and sponsor CTAs can become stale and are not part of
  the long-lived technical article archive.
- Impact: `make sync` filters these blocks, and `make validate` checks they do
  not reappear in generated article files.

## 2026-07-06: Rewrite Numbered Reference Links

- Decision: Rewrite same-article numbered reference links from WordPress
  `#h-references` anchors to the matching source URL in the article's
  References list.
- Rationale: GitHub readers should not be sent back to daryllswer.com just to
  resolve a local reference marker.
- Impact: `make sync` maps reference marker `1`, `2`, etc. to the corresponding
  numbered reference URL, and validation fails if WordPress `#h-references`
  links remain in generated Markdown.

## 2026-07-06: Generate GitHub Pages Site Under docs/

- Decision: Generate the human-readable HTML archive into `docs/` for GitHub
  Pages publication from the `main` branch `/docs` folder.
- Rationale: GitHub repository Markdown remains useful for source inspection,
  but a static HTML site gives readers a proper article index, theme, article
  pages, responsive figures, and spreadsheet landing pages.
- Impact: `make render-site` writes `docs/index.html`, `docs/posts/`,
  `docs/assets/theme.css`, `docs/sheets/`, and `docs/.nojekyll`. These outputs
  are generated artefacts and should be changed via `scripts/render-site.py`.

## 2026-07-06: Keep Archive Links Local Where Possible

- Decision: Rewrite mirrored article links that target archived WordPress media
  or the AS141253 Google Sheet to repository-hosted artefacts.
- Rationale: The archive should remain useful if daryllswer.com or the original
  Google Sheet disappears.
- Impact: `make sync` downloads direct WordPress-uploaded media links and
  rewrites Markdown to local asset/sheet paths. `make render-site` rewrites the
  same links to local Pages assets or sheet pages.

## 2026-07-06: Treat Runtime Embeds as Optional Presentation

- Decision: Convert unsupported embeds to durable Markdown links, while the
  generated Pages site may render iframe wrappers with fallback links.
- Rationale: GitHub repository Markdown does not provide a reliable rich embed
  surface, but Pages can render HTML while still preserving a fallback.
- Impact: Markdown no longer contains raw podcast iframes. Pages article output
  uses `.media-embed` wrappers and `make validate` checks the IPv6 article has
  the expected embed treatment.

## 2026-07-06: Normalise Generated Text Artefacts

- Decision: Normalise generated text artefacts before writing them into the
  repository.
- Rationale: The repository declares `*.csv text eol=lf`; preserving source
  CRLF from Google and trailing whitespace from generated HTML creates avoidable
  Git churn.
- Impact: `scripts/export-google-sheet.py` writes LF-normalised CSV files and
  whitespace-normalised Google Sheet HTML snapshots. `scripts/render-site.py`
  strips trailing line whitespace from generated Pages text output.

## 2026-07-06: Keep README Reader-Facing

- Decision: Keep operational maintainer commands out of `README.md` and place
  them in `AGENTS.md` and `docs/MIRRORING.md`.
- Rationale: The README should be clear and simple for readers landing on the
  public archive, while AI agents and future maintainers need more procedural
  instructions.
- Impact: `README.md` describes purpose, layout, licence, and the Pages URL.
  Maintainer commands and approval boundaries live in directive/process docs.

## 2026-07-06: Preserve WordPress Media Filenames and Bytes

- Decision: Store featured, inline, and linked WordPress media using the
  WordPress URL basename and direct response bytes wherever possible.
- Rationale: Filename fidelity and byte preservation keep media provenance
  obvious and preserve embedded metadata/EXIF without re-encoding.
- Impact: `make sync` records source filename, stored filename,
  filename-preserved status, and SHA-256 in asset manifests. `make validate`
  fails if WordPress media filenames are not preserved except for declared
  collision exceptions.

## 2026-07-06: Render AS141253 as a CSV-Backed Tabbed HTML Workbook

- Decision: Mirror the IPv6 Google Sheet as a standalone `workbook.html` with
  clickable tabs, generated from per-tab CSV files.
- Rationale: The repo needs a human-readable Google-Sheets-like workbook while
  keeping CSV as the easy-to-edit source format for future updates.
- Impact: `scripts/export-google-sheet.py` generates
  `data/sheets/as141253-ipv6-architecture-example/workbook.html`.
  `scripts/render-site.py` publishes the same workbook at
  `docs/sheets/as141253-ipv6-architecture-example/index.html`.

## 2026-07-06: Prefer Clean GitHub Pages Directory URLs

- Decision: Keep `docs/index.html` as the generated GitHub Pages entry file,
  but use clean directory URLs in human-facing navigation and root canonical
  metadata.
- Rationale: GitHub Pages publishes static files from the configured source
  folder, including `/docs` on a branch, and `index.html` is the entry file for
  the site. The public project URL is clearer and avoids duplicate-looking
  `index.html` links for readers.
- Evidence: GitHub's Pages documentation describes publishing from a branch
  folder such as `/docs` and creating a Pages site with an `index.html` entry
  file.
- Impact: `scripts/render-site.py` generates homepage links as `./`, nested
  archive-index links as `../../`, and the homepage canonical as
  `https://daryll-swer.github.io/daryllswer.com-archive/`. `make validate`
  fails if generated navigation regresses to visible `index.html` root links.

## 2026-07-06: Use Detection-First Canonical Drift Automation

- Decision: Add a weekly/manual GitHub Actions drift check that records drift
  state and reports, but does not silently rewrite mirrored article bundles.
- Rationale: daryllswer.com remains canonical while alive, but archive changes
  should stay reviewable because content/media changes can affect provenance,
  licensing, and long-term fidelity.
- Evidence: GitHub Actions supports scheduled and manually dispatched
  workflows, concurrency controls, job timeouts, and workflow disabling through
  documented UI/API paths.
- Impact: `.github/workflows/canonical-drift.yml` runs
  `scripts/check-canonical-drift.py`. Durable output lives in
  `archive-status.json` and `docs/CANONICAL_DRIFT.md`.

## 2026-07-06: Prefer Frozen-Archive Sentinel Over Workflow Self-Disabling

- Decision: If canonical failures persist, transition to `frozen_archive` in
  `archive-status.json` and make future scheduled checks no-op before any
  canonical network request.
- Rationale: A repo-visible sentinel avoids extra Actions API credentials,
  avoids fragile self-modifying workflow behaviour, and preserves the last known
  good public archive if the owner is unavailable and the canonical site dies.
- Impact: `scripts/check-canonical-drift.py` moves through
  `healthy`, `degraded`, `canonical_unavailable`, and `frozen_archive`.
  `frozen_archive` requires at least 8 consecutive failures over at least 30
  days.

## 2026-07-06: Model AS141253 IPv6 Data as a Prefix Containment Tree

- Decision: Generate a graph-theory proof of concept from the AS141253 CSV
  files as a rooted IPv6 prefix containment tree.
- Rationale: CIDR allocation hierarchy is naturally a parent/child containment
  tree when each child prefix has one most-specific containing supernet. That
  model is easier to inspect than a multi-sheet workbook and can be rendered as
  static HTML, JSON, and Graphviz DOT.
- Evidence: RFC 4291 defines IPv6 addressing architecture; RFC 5952 defines
  canonical text representation expectations; Python `ipaddress` provides
  IPv4/IPv6 network manipulation including containment operations; D3
  hierarchy, Cytoscape.js, Mermaid, and Graphviz were evaluated as possible
  visualisation paths.
- Impact: `scripts/ipv6_hierarchy.py` generates
  `cidr-hierarchy.html`, `cidr-hierarchy.json`, and `cidr-hierarchy.dot` from
  CSV. The workbook remains the default sheet page until the graph view is
  validated further.
