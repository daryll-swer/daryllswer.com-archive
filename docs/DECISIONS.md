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
