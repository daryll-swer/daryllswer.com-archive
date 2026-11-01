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

WordPress REST is authoritative for the archive's published-post set. Sitemap
and RSS data are secondary cross-checks. The exact BGP Router ID article URL
is a documented source-sitemap exception. Validation records that exception
but continues to warn for any other archived post absent from the sitemap. It
does not determine or alter GitHub Pages SEO metadata.

## Post Bundle

Each post lives under `content/posts/YYYY-MM-DD-slug/`:

- `index.md` is the human-readable Markdown body with YAML front matter.
- `metadata.json` records source IDs, timestamps, canonical URLs, hashes,
  featured image metadata, taxonomy, and validation state.
- `source/wordpress-post.json` stores the filtered public REST record.
- `source/rendered-article.html` stores the filtered REST-rendered article body.
- `source/canonical-page.html` stores the filtered public canonical HTML capture.
- `assets/manifest.json` records downloaded asset provenance and checksums.
- `content/rights-registry.json` records explicit per-post rights exceptions
  by immutable WordPress ID; matching `metadata.json` files contain structured
  rights data. Source-visible rights blocks and original-publication links are
  preserved without adding archive-only notices. A verified retirement removes
  its matching registry entry transactionally with its current-tree bundle.

Source-rights transformations remove source-site declarations in favour of the
repository's owner-selected rights policy. The archive records generic filter
categories, counts and hashes without retaining removed wording. Stored-file
checksums describe filtered captures; raw canonical content fingerprints remain
separate for drift comparison. Every article resolves rights metadata and one
visible applicable copyright notice. Daryll Swer-owned content is copyright
2026 Daryll Swer, all rights reserved; Swer Networks and third-party material
retain their separately recorded rights.

Markdown conversion is best-effort. Filtered HTML captures are preserved for fidelity
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

### Archive SEO and Discovery

The Pages archive owns its canonical and Open Graph URLs. It does not copy
DS/SN canonical, robots, or Open Graph URL metadata. While the DS source is
active, the archive runs in `source_primary`: only the archive homepage is
indexable, while article readers, the workbook, and the primary IPv6 visual
are `noindex, follow`. Source snapshots and non-reader HTML remain
`noindex, nofollow`. The preserved source remains under `data/`; its Pages
derivative has refresh/base directives removed and a restrictive CSP injected,
so upstream application fallback scripts cannot execute or redirect a reader.

When the independent canonical-health sentinel reaches `frozen_archive`, the
SEO state changes once to `archive_discovery`. The sitemap expands from
the homepage to eligible reader routes, and a local RSS feed is generated from
the stored archive rather than copied from WordPress. The feed and sitemap use
only archive-owned URLs. An external-original repost remains excluded until
the source URL recorded in the rights registry independently reaches
`frozen_source`.

This project does not control the host-root `robots.txt`. A file beneath the
project path is not a crawler policy, so none is generated. Page-level robots
metadata remains in place. The navigation links to the absolute sitemap;
submit `https://daryll-swer.github.io/daryllswer.com-archive/sitemap.xml`
directly in the verified Search Console URL-prefix property.

The generated homepage contains the public Google Search Console verification
token once. It enables ownership verification for the project Pages URL but is
not a secret and does not make crawler discovery depend on future account
access. A later positive HTTP response cannot reverse SEO state automatically;
follow `docs/SEO_RECOVERY.md` after owner-control verification.

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

Use CPython 3.12 and a dedicated virtual environment. Install the reviewed
lockfile with `python -m pip install --require-hashes -r requirements-lock.txt`.
`requirements.in` is the direct-dependency input, not an installation shortcut;
review its changes together with the regenerated lockfile. Do not replace an
existing environment without checking whether it is used by another task.

Use these commands when refreshing or validating the archive, passing
`PYTHON=<environment-python>` to Make when the environment is not activated:

```sh
make sync
make render-site
make validate
make validate-live
make scan-secrets
make check-drift
make render-preview
```

`make validate` checks offline integrity without contacting source services.
`make validate-live` adds the separately reported, paginated live comparison.
An offline pass does not mean the archive matches the live source. Pending
retirement or other live differences remain visible without blocking a valid
monitoring-state commit; reconciliation still rejects unsafe mutation plans.

The scripts use public WordPress/API/sitemap/RSS/export surfaces only. If a
future task needs authentication, private WordPress export, database access, SSH
backend access, or destructive GitHub actions, stop for explicit owner approval
first.

For a portable local snapshot, follow [PRESERVATION.md](PRESERVATION.md).

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

This automation writes durable state to `archive-status.json` and a
human-readable report to `docs/CANONICAL_DRIFT.md`. A healthy run may mirror
every detected changed existing article bundle as one all-or-nothing batch, and
may include one newly detected or restored post. A same-ID URL/slug relocation
remains report-only and blocks the batch rather than being mistaken for an
update or deletion.

The workflow is intentionally low-cost:

- weekly schedule plus manual dispatch;
- no private credentials;
- public unauthenticated WordPress REST only;
- 25 minute job timeout;
- concurrency group with `cancel-in-progress`;
- explicit CPython 3.12 setup and hash-verified locked dependencies before
  archive Python scripts; Actions are pinned to full commit SHAs;
- one new/restored post at most plus all verified existing-post updates in one
  atomic batch, or one confirmed retirement;
- Pages rendering only after verified content, proprietary favicon master or
  discovery eligibility changes; ordinary monitoring timestamps do not cause
  rendering or favicon re-encoding;
- commit only allowlisted drift, manifest, affected bundle, and generated
  Pages paths.

The pip cache accelerates downloads but does not replace installation on clean
runners. Dependency-update PRs require passing CI and maintainer review; no
automatic merging is configured. Push/PR CI is read-only. Offline validation
and safety scanning remain mandatory even when rendering is skipped.

Publication uses an explicit validated Pages artefact, with build,
repository-write and deployment permissions separated. Both maintainer and bot
changes use that path. A successful reconciliation is not proof of a successful
deployment: compare the successful GitHub Pages deployment revision with main.
A later no-content-change run can retry a failed deployment. Never force-push
or manufacture an empty content commit just to request publication.
The deployment workflow listens for successful main-branch canonical workflow
completion as well as maintainer pushes and manual dispatch. This fresh event
binds the deployment to the current main revision, including a bot commit;
checking out a new SHA inside the older monitoring run would not update that
run's Pages deployment identity. Deployment rebuilds and validates its own
checkout, without trusting artefacts from the preceding monitoring run.

Pre-staging and staged checks allow a rights-registry change only when it
exactly removes the verified retired post's record. An unrelated rights or
brand-manifest edit fails the automation boundary.
If the Swer Networks repost (WordPress ID `5324`) is retired and later returns,
its required explicit rights record must be restored by a maintainer before
publication can pass validation. Review the previous record in Git history and
the returning source, then restore the registry entry and bundle together.
Automatic registry additions are not permitted by the monitoring allowlist;
do not replace the ownership exception with the DS default to make a run pass.

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

A single post retirement is not a reachability failure. It requires two
healthy weekly observations at least seven days apart, exactly one absent
WordPress post ID, no concurrent new/relocated/multi-post anomaly, a live post
count exactly one lower than the archive count, and `404` or `410` from both
the post REST endpoint and its canonical URL. Any failed request or anomaly
clears the confirmation sequence and cannot remove archive content. Successful
retirement removes the current-tree post bundle, assets, source evidence,
archive-manifest entry, and generated Pages route; it does not rewrite Git
history. A pending candidate always forces a fresh REST collection fetch rather
than accepting a conditional `304`. Candidate details are cleared from the
current branch after success.

For existing-post updates, the checker compares immutable IDs, title, modified
timestamp, featured image, WordPress-uploaded body media, and a raw canonical
rendered-content fingerprint. A clean healthy comparison backfills the
fingerprint baseline for older bundles once. The synchroniser stages the
complete batch outside the repository, revalidates each expected WordPress ID,
and replaces bundles plus the manifest only after every target succeeds. Any
target failure leaves the published archive unchanged.

Never edit health counters manually to unfreeze the archive. Use the
owner-verified command sequence in [SEO_RECOVERY.md](SEO_RECOVERY.md), then
review, validate, publish and verify the deployed revision.

### Missed Runs and Detection Limits

GitHub is the only scheduler in this phase. Scheduled runs can be delayed, and
public-repository schedules are automatically disabled after 60 days without
repository activity. There is no independent notification path if GitHub or
the schedule stops. Do not manufacture empty keepalive commits.

If a weekly check is missing, inspect the Actions workflow's enabled state,
latest scheduled/manual run, failed step and job summary. Resolve the cause,
re-enable a disabled schedule where appropriate, and manually dispatch a
non-forced check. Verify monitoring state and Pages deployment separately.
Do not accelerate freeze by inventing observations or editing timestamps.

Rendered-content fingerprints and changed media URLs are detected. Replaced
media bytes at an unchanged upstream URL are not independently polled. The
archive preserves the media bytes it actually fetched, not every future
upstream variation.

### Reader Safety

Stored source captures are evidence, not trusted executable reader content.
The reader/RSS renderer uses a maintained HTML allowlist sanitiser and a
restricted embed policy; published source HTML receives separate containment.
Keyboard skip links, visible focus, no-script reading, print and reflow checks
are maintained alongside content fidelity. Automated checks alone are not a
WCAG conformance assessment; representative human assistive-technology testing
and any outstanding limitations must be reported separately.

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
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.json` is the
  developer/AI-facing machine-readable hierarchy model.
- `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.dot` is the
  developer/AI-facing Graphviz DOT export for external layout experiments.
- No separate public CIDR hierarchy HTML page is generated; `visual.html` is
  the single reader path.
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
controls. Every hierarchy disclosure is closed on fresh load: generated
hierarchy `details` elements must not carry `open`. CSV `Notes` values remain
visible at each node. A reserved group with multiple exact prefixes is
collapsed into a count/range summary and expands to those exact prefixes; singleton
reserved allocations sharing a direct parent render as static cards in one responsive grid,
after allocated child branches and before those multi-prefix ranges. This preserves audit
fidelity without empty disclosures or excessive vertical scrolling. The page has
one small
inline progressive-enhancement script: the explicit `Expand all` and
`Collapse all` buttons start hidden, are revealed only when that local script
runs, and do not open anything at load. `Expand all` opens non-leaf hierarchy
nodes and multi-prefix reserved groups; `Collapse all` closes those same
disclosures.
Native per-disclosure controls remain the functional path without JavaScript.
No external script, network request, graph logic, or retired visual-model
JavaScript is emitted for this page; validation rejects any additional or
external script. The final hierarchy section suppresses the generic divider
and places its toolbar within the hierarchy frame to avoid a duplicate top
rule and surplus content-to-footer spacing.

Historical design material is retained outside `docs/` for maintainers and AI
agents only. The render pipeline excludes it, and validation rejects both
legacy Pages files and generated links to them. The public page uses responsive
CSS with `min-width: 0` containment and bounded internal overflow so it reflows
without page-level horizontal overflow from 320 CSS px through wide displays.
