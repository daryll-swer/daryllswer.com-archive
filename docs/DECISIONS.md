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
