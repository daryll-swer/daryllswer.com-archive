# Architecture

## Purpose

This repository is a public archive of published daryllswer.com content. It is
not the publishing source of truth; WordPress remains canonical.

## Boundaries

- Public inputs only: WordPress REST API, sitemap/RSS, canonical HTML, media
  URLs, and public Google Sheet exports.
- WordPress REST is authoritative for the archived published-post set; sitemap
  and RSS are secondary cross-checks. The BGP Router ID republication is a
  documented source-sitemap exception; it does not change GitHub Pages SEO.
  Any other archive URL absent from the post sitemap remains validation drift.
- No private admin exports, backend access, database dumps, cookies, browser
  state, or credentials.
- Generated content is deterministic enough to re-run and compare.
- The archive remains a GitHub Pages project site at
  `https://daryll-swer.github.io/daryllswer.com-archive/`; the account-level
  `daryll-swer.github.io` user-site namespace is intentionally reserved for a
  future landing page. The generated archive homepage title and Open Graph
  title are `daryllswer.com – Archive`; article and workbook titles remain
  descriptive to their content.

## Per-Post Rights

- `content/rights-registry.json` records explicit article-rights exceptions by
  immutable WordPress ID. The default `CC-BY-NC-SA-4.0` classification applies
  only to original DS content covered by the DS default licence.
- Registry entries are copied into matching post `metadata.json` `rights`
  objects and validated against the manifest and source body. A registry entry
  cannot be silently applied to a different post.
- Registry-marked proprietary reposts preserve their source-visible rights
  notice and original-publication link. The archive does not inject duplicate
  notices or inherit DS/SN canonical, robots, or Open Graph URL directives;
  generated Pages retains its own archive-local metadata.
- A registry-marked external original may explicitly opt into fallback
  discovery. Its independent availability state is recorded by immutable post
  ID and never inferred from daryllswer.com health. A healthy external source
  keeps its archive repost `noindex`; only that source's separately frozen
  state can make its archive route eligible in archive-discovery mode.
- If a registry-marked post is safely retired, reconciliation removes its
  registry entry and any matching external-source state in the same
  transactional current-tree mutation as the bundle, manifest, and status
  update; a failed mutation restores all of them.

## Repository Identity Assets

- `assets/readme/13_DS_Logo_Dark_Mode_SEO.png` is the owner-provided,
  byte-preserved proprietary logo used as the repository README header.
- `assets/brand/01_DS_Favicon_Dark_Mode.png` is the owner-provided,
  byte-preserved proprietary favicon source. Its controlled 512 px derivative
  is stored under `assets/brand/derivatives/`; `scripts/render-site.py` copies
  that approved byte sequence into `docs/assets/brand/` for the generated
  Pages header and browser icon, avoiding both excessive browser decoding and
  encoder-dependent Pages churn.
- Their SHA-256 checksums and byte-preserved provenance are recorded in
  `assets/readme/ASSET_PROVENANCE.md`, `assets/readme/manifest.json`, and
  `assets/brand/ASSET_PROVENANCE.md`, and `assets/brand/manifest.json`; their
  controlling legal notice is
  `LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt`.
- They are not mirrored WordPress content, third-party media, MIT tooling, or
  `CC-BY-NC-SA-4.0` archive content. Future tooling must not rename,
  re-encode, redistribute, or apply an open licence to the source assets. The
  only permitted generated derivative is the documented 512 px Pages favicon;
  its manifest records both master and derivative checksums. A changed master
  refreshes it through `scripts/prepare-brand-favicon.py`, while ordinary
  renders never re-encode it.

## Data Flow

```mermaid
flowchart LR
  WP["WordPress public REST/API"] --> Sync["sync-wordpress-posts.py"]
  HTML["Canonical public HTML"] --> Sync
  Media["Public media URLs"] --> Sync
  Sheet["Published Google Sheet"] --> SheetExport["export-google-sheet.py"]
  Sync --> Posts["content/posts/..."]
  SheetExport --> Sheets["data/sheets/..."]
  Posts --> Manifest["archive-manifest.json"]
  Sheets --> Manifest
  Posts --> Site["render-site.py"]
  Sheets --> Site
  Manifest --> Site
  Site --> Pages["docs/ GitHub Pages site"]
  Manifest --> Validate["validate-mirror.py"]
  Pages --> Validate
  Manifest --> Drift["check-canonical-drift.py"]
  WP --> Drift
  Drift --> Status["archive-status.json"]
  Drift --> DriftReport["docs/CANONICAL_DRIFT.md"]
  Rights["content/rights-registry.json"] --> SourceHealth["external-original monitor"]
  SourceHealth --> Status
  Status --> Site
  Site --> Discovery["robots.txt, sitemap.xml, feed.xml"]
```

## Rendered Site

- `content/posts/...` and `data/sheets/...` remain the archive source of truth.
- `scripts/render-site.py` generates the public HTML site into `docs/`, which
  can be published by GitHub Pages from the `main` branch `/docs` folder.
- `docs/index.html` is the public article index with title, excerpt, taxonomy,
  date, and featured image for each mirrored post.
- `docs/posts/<slug>/index.html` is the human-readable article page generated
  from the preserved WordPress-rendered article HTML, with localised images,
  internal archive links, responsive figure styling, stable section anchors,
  and embed fallback links.
- The generated Pages theme self-hosts `Poppins` for body/content text and
  `Raleway` for headings/titles from `assets/fonts/`, with generated copies
  under `docs/assets/fonts/`. The font files are third-party OFL artefacts with
  family-specific provenance and checksums.
- The generated Pages theme includes the WordPress preset colour variables and
  class mappings needed by preserved article-body inline colour markup, such as
  `has-inline-color`, `has-vivid-red-color`,
  `has-luminous-vivid-orange-color`, and
  `has-luminous-vivid-amber-color`.
- The generated Pages theme must remain mobile-safe: page-level horizontal
  overflow is avoided with mobile viewport metadata, `min-width: 0` grid/flex
  children, bounded media, and explicit scroll containers for wide code/table
  content.
- `docs/sheets/as141253-ipv6-architecture-example/index.html` is the generated
  tabbed HTML workbook for the AS141253 sheet. It is rendered from repository
  CSV files, uses the same archive typography, and keeps adjacent ODS, CSV,
  CSVW, and Google HTML snapshots for editing/provenance.
- `docs/sheets/as141253-ipv6-architecture-example/visual.html` is the sole
  human-facing AS141253 IPv6 visual model. It renders the complete
  CSV-derived containment hierarchy with native `details`/`summary` controls.
  Every hierarchy disclosure is closed on fresh load: generated hierarchy
  `details` elements must not carry `open`. Reserved sibling groups with two
  or more exact prefixes are collapsed into count/range summaries; singleton
  reserved allocations sharing a direct hierarchy parent are static leaves in
  one responsive card grid, after allocated child branches and before
  multi-prefix reserve ranges. Both retain the exact prefix details. A
  single small inline progressive-enhancement script reveals initially hidden
  `Expand all` and `Collapse all` buttons; it does not open disclosures at
  load and only toggles non-leaf hierarchy nodes and multi-prefix reserved
  groups. Native
  disclosure controls remain usable without JavaScript, and no external or
  unrelated legacy script is emitted. The final hierarchy section suppresses
  the generic section divider, and its toolbar sits inside the hierarchy frame
  so the visual has no duplicate top rule or avoidable footer gap.
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json` and
  `.dot` are derived developer/AI artefacts. They preserve the CSV-derived
  IPv6 containment graph for audit and external tooling; no separate public
  CIDR hierarchy HTML page is generated.
- Historical visual-design material is retained only as a developer/AI
  reference under `data/sheets/as141253-ipv6-architecture-example/legacy-visual-models/`.
  The render pipeline excludes that directory and produces no legacy visual
  pages or navigation under `docs/`, so GitHub Pages cannot serve those routes.
- The public AS141253 hierarchy page must remain responsive across phone,
  tablet, desktop, and wide-display viewport classes. The page itself must not
  introduce horizontal overflow. The responsive support matrix includes the
  WCAG 320 CSS px reflow floor, common phone widths, common framework
  breakpoints, boundary-adjacent widths, desktop widths, and wide displays:
  320, 360, 390, 430, 479/480, 575/576, 599/600, 639/640, 759/760, 767/768,
  899/900, 979/980, 991/992, 1023/1024, 1199/1200, 1279/1280, 1366,
  1399/1400, 1439/1440, 1535/1536, 1599/1600, 1919/1920, and 2560 CSS px.
- Human-facing navigation and canonical URLs use clean directory URLs such as
  `https://daryll-swer.github.io/daryllswer.com-archive/`. The physical
  `docs/index.html` file remains the GitHub Pages entry point and generated
  artefact, not the preferred public link.

### Source-First Archive SEO

- The archive owns its Pages metadata. Every generated reader page has a
  GitHub Pages-local canonical URL and Open Graph URL; DS/SN canonical tags,
  robots directives, and Open Graph URLs are never inherited.
- The initial SEO mode is `source_primary`: the archive homepage is indexable
  as archive navigation, while article reader pages, the workbook, and the
  primary IPv6 visual use `noindex, follow`. Raw source snapshots and
  non-reader HTML artefacts always use `noindex, nofollow`. Canonical snapshot
  source remains preserved under `data/`; the Pages copy additionally strips
  executable refresh/base directives and injects a restrictive CSP so an
  upstream application fallback cannot redirect an archive visitor away.
- `archive_discovery` begins only when the separate DS health state reaches
  `frozen_archive` after eight failures spanning at least 30 days. It does not
  automatically revert after later HTTP success. Eligible archive reader
  routes then become indexable, and the renderer produces an archive sitemap
  and local RSS feed.
- The sitemap contains only the homepage in `source_primary`. In
  `archive_discovery`, it additionally includes eligible posts, the workbook
  landing page, and the primary IPv6 visual with truthful modification dates.
  It excludes assets, source snapshots, validation reports, retired routes,
  legacy references, and still-healthy external-original reposts.
- The archive-generated RSS 2.0 feed exists only in `archive_discovery`. It
  is generated from local archive data, never copied from the live WordPress
  feed, and provides the ten most recently published eligible posts with
  archive-local URLs and stable immutable-ID GUIDs. It deliberately excludes
  WordPress comments and source-domain SEO metadata.
- `robots.txt` always permits crawling and advertises the local absolute
  sitemap URL. The generated homepage carries the public Google Search Console
  verification token once; it is archive configuration, not a credential.
- External originals recorded in the rights registry are monitored weekly only
  while active. Their state is `healthy`, `degraded`, `source_unavailable`, or
  `frozen_source`. DNS, TLS, network, `404`/`410`, and persistent server
  failures may advance failure state; `401`, `403`, `429`, and unexpected-host
  redirects block promotion and require review. Once frozen, a source is not
  requested again unless an owner explicitly invokes the documented recovery
  path.
- A positive HTTP response does not automatically restore source priority or
  `noindex`. Recovery requires a maintainer to verify owner control and use
  the manual procedure in `docs/SEO_RECOVERY.md`; this avoids treating a
  restored, redirected, or hijacked endpoint as authoritative automatically.

## Canonical Drift Automation

- `.github/workflows/canonical-drift.yml` runs a low-frequency weekly check and
  supports manual `workflow_dispatch`.
- `scripts/check-canonical-drift.py` uses only the public WordPress REST index
  and local archive manifests. It checks for new, missing/unlisted, relocated,
  modified, featured-image, and WordPress-uploaded image-media drift by
  immutable WordPress post ID where possible.
- Third-party documents, PDFs, downloads, and external artefacts are not
  mirror-required drift. They remain outbound links unless the owner explicitly
  approves mirroring a specific artefact.
- The automation records drift in `docs/CANONICAL_DRIFT.md` and durable state
  in `archive-status.json`. A separate reconciliation path mirrors every
  verified changed existing post as one atomic batch, may add one new/restored
  post in that batch, or retires one independently verified missing post.
- The workflow has a 25 minute timeout and a concurrency group so overlapping
  scheduled/manual runs cannot pile up. It prepares the controlled favicon on
  every run but renders Pages only after a content, brand-master, archive SEO,
  sitemap, or feed eligibility change.
- The workflow commits only allowlisted reconciliation paths: drift status and
  report, the archive manifest, affected post bundles, and regenerated Pages
  output. Timestamped validation reports and temporary action plans are never
  committed by scheduled checks.
- The workflow must use explicit `actions/checkout@v6` and
  `actions/setup-python@v6` steps, select CPython 3.12, cache pip by
  `requirements.txt`, and run `python -m pip install -r requirements.txt`
  before every archive Python script. The pip cache only reuses downloaded
  packages; it never replaces dependency installation on a clean runner.
- `scripts/validate-mirror.py` treats that workflow bootstrap as an invariant:
  it verifies active steps, their order, and the `lxml` declaration in
  `requirements.txt`. Any intentional action-version, Python-version, or
  bootstrap redesign must update the workflow and its guard in one commit, then
  pass a manually dispatched clean-hosted-runner verification.
- Official GitHub Actions documentation supports scheduled and manual triggers,
  workflow concurrency, timeout controls, and workflow disabling. This repo
  still uses a sentinel/no-op pattern instead of self-disabling because it
  avoids extra API credentials and keeps the archive state visible in Git.

### Failure State Model

- `healthy`: canonical REST is reachable and checked.
- `degraded`: one or two consecutive canonical failures occurred. Existing
  archive content remains untouched.
- `canonical_unavailable`: three or more consecutive canonical failures
  occurred.
- `frozen_archive`: eight consecutive failures across at least 30 days occurred.
  Future scheduled checks no-op before making any canonical network request.

The frozen state is intended for owner-unavailable futures: DNS expiry, TLS
failure, WordPress death, hosting loss, or a possibly hijacked canonical
surface must not cause repeated workflow failures or archive deletion.

The archive SEO mode is separate: it begins at `source_primary`, transitions
once to `archive_discovery` when DS freezes, and can return only through the
documented owner-verified manual recovery procedure. An external original has
its own independent failure sequence, so a DS freeze cannot promote a Swer
Networks repost while its registered original remains active.

### Content Reconciliation Model

- Health state and content reconciliation are separate. A failed canonical
  request can update only the health state; it cannot create or execute a
  retirement plan.
- A post is a retirement candidate only when its immutable WordPress ID is
  absent from a fresh healthy REST collection. A same-ID URL or slug change is
  relocation, not deletion.
- Retirement requires exactly one missing archived post, no concurrent new or
  relocated post, a live count exactly one lower than the archive count, two
  compatible healthy observations at least seven days apart, and direct REST
  item plus canonical URL responses of `404` or `410`.
- A pending retirement candidate forces a fresh REST collection fetch; a
  conditional `304` cannot count as a confirmation.
- The candidate record is temporary. Successful reconciliation removes the
  current-tree post bundle, its media and evidence, its archive-manifest entry,
  and generated Pages output, then clears per-post candidate data. Git history
  is deliberately retained.
- At most one newly detected public post is mirrored in one scheduled run.
  A restored post follows the same new-post path. Every detected existing-post
  change is included in the same staging batch; any failed target rolls the
  whole batch back and nothing is published.
- Same-ID URL/slug changes remain relocation reports, not automatic updates or
  deletions. Missing/relocated anomalies block a synchronisation batch.
- All bundles store a canonical rendered-content checksum before archive CTA
  filtering. A clean healthy comparison backfills the baseline for legacy
  bundles once, supporting content-fingerprint comparison without treating
  deliberate archive filtering as recurring drift.
- Historical Markdown links that prove a target was once mirrored retain a
  local Pages route after retirement. It is intentionally unavailable until a
  later restoration is mirrored; unrelated canonical pages are never
  localised.

## Invariants

- Every mirrored post has a canonical URL, source REST snapshot, source HTML
  snapshot, Markdown body, metadata JSON, and asset manifest.
- Generated article bodies exclude donation/support CTAs and `/donation/`
  links as site-operational content.
- Every local image reference in Markdown points to an existing local file.
- Mirrored article body links to archived daryllswer.com posts are rewritten to
  archive-local targets. Generated Pages links use local post routes and
  Markdown links use local `content/posts/.../index.md` targets.
- Cross-post fragments are preserved. WordPress heading IDs such as
  `h-dns-and-loopback-addressing` are preserved on headings, and matching
  non-`h-` alias anchors such as `dns-and-loopback-addressing` are emitted when
  needed so canonical section links still land correctly.
- WordPress inline colour classes in article source HTML must survive into
  generated Pages article HTML, and `docs/assets/theme.css` must style the
  corresponding WordPress preset colour classes.
- Generated article headings with IDs expose human-shareable controls: the
  heading text links to its own fragment, a visible permalink link updates the
  browser address bar, and a progressive-enhancement copy button copies the
  full section URL when the Clipboard API is available.
- Every downloaded WordPress media asset preserves the WordPress URL basename
  and direct response bytes wherever possible. This preserves embedded image
  metadata/EXIF because the archive does not re-encode media files. Any
  filename collision exception must be recorded in the asset manifest.
- Third-party documents, PDFs, downloads, and external artefacts are preserved
  as outbound hyperlinks with provenance; they are not assumed to be covered by
  the archive content licence and are not mirrored by default.
- Every downloaded asset has a source URL, source filename, stored filename,
  filename-preserved flag, and SHA-256 checksum.
- Spreadsheet CSV files remain diffable; `workbook.html`/Pages sheet output is
  generated from those CSV files; ODS remains the styled editable open
  artefact.
- The AS141253 CIDR hierarchy is derived from CSV, not manually maintained.
  Parent/child edges must be calculated using IPv6 prefix containment. The
  generated JSON and DOT checksums are recorded in the sheet manifest.
- The AS141253 public visual model is generated from CSV/hierarchy data, not
  hand-authored. `visual.html` is the only reader path and renders the full
  hierarchy through native disclosure controls. CSV `Notes` values remain
  first-class metadata; all hierarchy disclosures must be closed on fresh
  load, and reserved prefixes must not disappear. A reserved allocation is an
  expandable summary only when it represents multiple exact prefixes; singleton
  leaves sharing a direct parent render together in a responsive card grid.
  Historical design logic is
  explicitly non-Pages reference material. The public page must keep
  page-level width bounded at common phone, tablet, desktop, and wide-display
  viewports.
- Spreadsheet CSV exports are normalised to LF line endings for stable Git
  diffs; generated HTML artefacts strip trailing line whitespace; ODS remains a
  binary artefact.
- GitHub Pages output is generated, not hand-authored; rerun
  `make render-site` after sync/content changes.
- GitHub Pages output must not expose redundant `index.html` links in visible
  navigation or root canonical metadata when an equivalent clean directory URL
  exists.
- GitHub Pages output must not point article media back to
  `www.daryllswer.com/wp-content/uploads/` when a local archive copy exists.
- GitHub Pages article bodies must not retain external
  `https://www.daryllswer.com/<archived-post-slug>/` links when the target post
  is mirrored locally. Intentional canonical source footers and the canonical
  site navigation link remain external by design.
- Every generated local `#fragment` article-body link must resolve to a target
  element ID, except browser text-fragment links beginning with `#:~:text=`.
- Generated public pages must not introduce page-level horizontal overflow at
  common mobile widths. Wide article code/table/sheet content may scroll inside
  its own explicit container instead of widening the page.
- Remote destructive GitHub actions are outside normal script behaviour.
