# Mirroring Model

The WordPress site is canonical. This repository stores a reproducible public
mirror for audit, readability, and long-term maintenance.

## Source Priority

1. WordPress REST API for post records and rendered article body.
2. WordPress media API and embedded media records for featured/media metadata.
3. Canonical post HTML for source snapshot, Open Graph data, structured data,
   and fallback featured image detection.
4. Sitemap/RSS for cross-checking missing posts.
5. Public Google Sheet export endpoints for linked spreadsheet artefacts.

## Post Bundle

Each post lives under `content/posts/YYYY-MM-DD-slug/`:

- `index.md` is the human-readable Markdown body with YAML front matter.
- `metadata.json` records source IDs, timestamps, canonical URLs, hashes,
  featured image metadata, taxonomy, and validation state.
- `source/wordpress-post.json` stores the public REST record.
- `source/rendered-article.html` stores the REST-rendered article body.
- `source/canonical-page.html` stores the public canonical HTML snapshot.
- `assets/manifest.json` records downloaded asset provenance and checksums.

Markdown conversion is best-effort. HTML snapshots are preserved for fidelity
where Markdown cannot represent the original formatting safely.

## GitHub Pages Site

`scripts/render-site.py` generates a static HTML site under `docs/`.

- `docs/index.html` is the public archive index.
- `docs/posts/<slug>/index.html` is the rendered article page.
- `docs/assets/theme.css` is the shared minimal visual theme.
- `assets/fonts/` is the source store for self-hosted `Poppins` and `Raleway`
  WOFF2 font files. `make render-site` copies these to `docs/assets/fonts/`.
- `docs/sheets/as141253-ipv6-architecture-example/index.html` is the tabbed
  AS141253 workbook generated from repository CSV files. The ODS, CSV, CSVW,
  and Google HTML snapshots are copied next to it for editing/provenance.

GitHub Pages is static hosting, so the site is regenerated from repository
content by `make render-site`; it does not fetch article bodies from WordPress
or GitHub at runtime.

The generated source still contains `docs/index.html` because GitHub Pages
serves that entry file for the project site. Human-facing navigation and
canonical metadata should use clean directory URLs, for example
`https://daryll-swer.github.io/daryllswer.com-archive/` and relative `./` or
`../../` links, instead of redundant `index.html` links.

The generated theme uses the canonical site typography:

- `Poppins` for body/content text.
- `Raleway` for headings, titles, card titles, and brand text.

Fonts are self-hosted for archive durability and loaded with `font-display:
swap`. Font provenance, source URLs, checksums, and OFL licence files live under
`assets/fonts/`.

The generated theme also maps WordPress preset colour classes used inside
article bodies. WordPress-rendered source HTML preserves inline colour markup
such as `has-inline-color`, `has-vivid-red-color`,
`has-luminous-vivid-orange-color`, and `has-luminous-vivid-amber-color`; the
generated Pages CSS supplies the matching preset colour values so coloured
text/characters render like canonical. Markdown remains a best-effort text view
where portable visual colour is not guaranteed.

## Maintainer Workflow

Use these commands when refreshing or validating the archive:

```sh
make sync
make render-site
make validate
make scan-secrets
make check-drift
make render-preview
```

The scripts use public WordPress/API/sitemap/RSS/export surfaces only. If a
future task needs authentication, private WordPress export, database access, SSH
backend access, or destructive GitHub actions, stop for explicit owner approval
first.

## Canonical Drift Automation

`.github/workflows/canonical-drift.yml` runs the public canonical drift check
weekly and can be started manually with `workflow_dispatch`.

The workflow calls `scripts/check-canonical-drift.py`, which compares public
WordPress REST data with `archive-manifest.json` and per-post metadata. It
checks for:

- new published posts;
- missing or unlisted archived posts;
- changed slugs, titles, modified timestamps, and featured image URLs;
- changed WordPress-uploaded body image-media links.

Linked third-party documents, PDFs, downloads, and external artefacts are not
mirror-required drift. They remain outbound links unless the owner explicitly
approves mirroring a specific artefact.

This automation is detection-first. It writes durable state to
`archive-status.json` and a human-readable report to
`docs/CANONICAL_DRIFT.md`; it does not automatically refresh article bundles.

The workflow is intentionally low-cost:

- weekly schedule plus manual dispatch;
- no private credentials;
- public unauthenticated WordPress REST only;
- 10 minute job timeout;
- concurrency group with `cancel-in-progress`;
- commit only durable drift state/report changes.

Design references:

- GitHub Actions workflow syntax:
  <https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions>
- GitHub Actions events and scheduled workflow behaviour:
  <https://docs.github.com/actions/using-workflows/events-that-trigger-workflows>
- Disabling and enabling workflows:
  <https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow>
- REST endpoint for disabling workflows, which requires Actions write
  permission:
  <https://docs.github.com/en/rest/actions/workflows>

If `archive-status.json` reaches `frozen_archive`, future scheduled runs exit
before making canonical network requests. This preserves the last known good
archive if daryllswer.com becomes unavailable permanently.

To unfreeze manually, a future maintainer must verify that the canonical site
is healthy and owner-controlled, edit `archive-status.json` back to `healthy`,
clear the failure counters, then run:

```sh
python3 scripts/check-canonical-drift.py --force
make validate
make scan-secrets
```

## Archive Filters

The archive intentionally removes site-operational calls to action from
generated article bodies. These include the repeated top-of-article donation
heading, article blocks linking to `/donation/`, and sponsor/trial lead CTAs
that are operational promotion rather than durable article substance.

Rationale: the repository is a durable public content archive, while donation
pages and support CTAs are live-site operational content that may become
irrelevant or broken if the WordPress site disappears.

Filtering happens during `make sync`, and `make validate` fails if those CTAs
reappear in generated Markdown, rendered article snapshots, or archived REST
post JSON.

## Reference Links

Some WordPress articles use Wikipedia-style numbered citation markers that link
to the article's `#h-references` section. In the GitHub archive, those links
must not point back to daryllswer.com.

During `make sync`, if an article has a References list, numbered same-article
reference markers are rewritten to link directly to the matching source URL in
that list. If no matching URL can be found, the fallback is the local Markdown
anchor `#references`.

`make validate` fails if generated Markdown still links citation markers to a
WordPress `#h-references` URL.

## Internal Canonical Links and Anchors

Links inside mirrored article bodies that target another mirrored
`daryllswer.com` post are rewritten to archive-local links.

- Repository Markdown links use local `content/posts/.../index.md` paths.
- Generated Pages links use local `../<slug>/` article routes.
- URL fragments are preserved so section links continue to work.
- Tracking query parameters such as `utm_*`, `fbclid`, `gclid`, `mc_cid`, and
  `mc_eid` are dropped during local rewrites.

WordPress heading IDs are preserved where present. When a heading uses an ID
such as `h-dns-and-loopback-addressing`, the generated Pages article also emits
a hidden alias anchor `dns-and-loopback-addressing` so both canonical and
archive-local fragment forms can land on the intended section.

Generated article headings also expose shareable section controls. The heading
text links to its own fragment, the visible `#` permalink updates the browser
address bar, and the `Copy` button copies the full section URL when the browser
Clipboard API is available. If JavaScript is unavailable, the permalink remains
a normal fragment link.

Links to non-archived canonical pages, such as `/contact/`, `/geofeed/`, and
`/as149794/`, intentionally remain external until a deliberate archive-local
replacement exists. Canonical source footers also intentionally remain external.

`make validate` checks article bodies for localisable canonical post links and
checks generated local fragment links for matching target IDs, excluding browser
text-fragment links that begin with `#:~:text=`.

## Media and Embeds

Inline images and WordPress-uploaded image media links are downloaded where
possible and rewritten to local archive paths. This applies to image figures
and to text links that point directly at image files under
`www.daryllswer.com/wp-content/uploads/`.

Downloaded media files are stored as direct response bytes with no image
re-encoding, resizing, or metadata stripping. This keeps embedded image
metadata/EXIF identical to the public WordPress media response. The archive
preserves the WordPress URL basename for featured, inline, and linked media
wherever possible, and the asset manifest records the source filename, stored
filename, SHA-256 checksum, and whether the filename was preserved. The only
allowed exception is a same-directory filename collision.

Third-party documents, PDFs, downloads, and external artefacts remain outbound
links by default. Do not download or commit them unless the owner explicitly
approves mirroring that exact artefact and its provenance/licensing status is
recorded.

Unsupported embeds such as podcast iframes are converted to durable Markdown
links in `content/posts/.../index.md`. The generated GitHub Pages site keeps a
styled embed wrapper with a fallback outbound link, so readers do not see raw
HTML in the repository view.

The AS141253 Google Sheet link in the IPv6 architecture article is rewritten to
the repository-hosted `data/sheets/as141253-ipv6-architecture-example/visual.html`
in Markdown and to the generated Pages visual model in HTML. Workbook, CSV,
ODS, and source snapshots remain linked from the sheet area for audit and
editing.

## Spreadsheet Workbook

The AS141253 Google Sheet is archived as a CSV-backed HTML workbook:

- `data/sheets/as141253-ipv6-architecture-example/workbook.html` is the
  standalone repository copy with clickable sheet tabs.
- `docs/sheets/as141253-ipv6-architecture-example/index.html` is the generated
  GitHub Pages copy of the same workbook.
- `data/sheets/as141253-ipv6-architecture-example/visual.html` is the sole
  public full-hierarchy visual model for human readers.
- `docs/sheets/as141253-ipv6-architecture-example/visual.html` is the generated
  GitHub Pages copy of that supported public model.
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.html` is the
  static IPv6 CIDR containment tree proof of concept generated from CSV.
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json` is the
  machine-readable hierarchy model.
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.dot` is the
  Graphviz DOT export for external layout experiments.
- `data/sheets/as141253-ipv6-architecture-example/csv/` remains the editable
  text source for each tab.
- `AS141253-ipv6-architecture-example.ods` and `html/` snapshots preserve
  styled/provenance references.

Google's CSV exports are normalised to LF line endings when written to the
repository so tabular diffs remain stable under `.gitattributes`. Generated HTML
artefacts also strip trailing line whitespace; binary ODS/media artefacts are
left as binary files.

The CIDR hierarchy uses a rooted IPv6 prefix containment tree. Prefixes are
parsed from CSV `Prefix` columns with Python `ipaddress`; parent selection is
the most-specific existing supernet containing a child prefix. The graph output
is a proof of concept and does not replace the workbook view yet.

The public `visual.html` page uses the same CSV-derived hierarchy model and
renders the complete containment tree with native HTML `details`/`summary`
controls. CSV `Notes` values remain visible at each node. Reserved siblings are
collapsed into count/range summaries by default and expand to their exact
prefixes, preserving audit fidelity without making the default tree unreadable.

Historical design material is retained outside `docs/` for maintainers and AI
agents only. The render pipeline excludes it, and validation rejects both
legacy Pages files and generated links to them. The public page uses responsive
CSS with `min-width: 0` containment and bounded internal overflow so it reflows
without page-level horizontal overflow from 320 CSS px through wide displays.
