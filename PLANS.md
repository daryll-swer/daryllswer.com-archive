# daryllswer.com Archive Plan

## Context and Orientation

- Workspace / project: `daryllswer.com-related-work`
- Thread/workspace id: current Codex Desktop thread
- Source of truth: repository root
- Execution surface: macOS Codex Desktop
- Status: complete; canonical-drift workflow dependency bootstrap is deployed
  and hosted-runner verified
- Created: 2026-07-06 09:07 UTC
- Last updated: 2026-07-13
- Working assumptions: the WordPress site is canonical; this repo is a public mirror/archive of only published public content.
- `forked_from`: N/A

## Durable Project Documents

- Architecture: `ARCHITECTURE.md`
- ADR directory: N/A for now
- Implementation status: `IMPLEMENTATION_STATUS.md`
- Escalation rules: `ESCALATION.md`

## Current Status / Next Pickup

- Current state:
  - Complete: scheduled canonical drift run `29229277522` reached a
    healthy drift state but failed at `make validate` because the clean
    GitHub-hosted runner did not install the declared `lxml` dependency. The
    workflow now has explicit Python setup, requirements installation, and a
    static local regression guard. Manual hosted-runner run `29231087908`
    passed every step.
  - Complete: `cidr-hierarchy.html` is retired as a redundant public
    proof-of-concept page. Generation, source/Page output, and public
    navigation now use `visual.html` only; CSV-derived JSON and DOT hierarchy
    artefacts remain developer-facing source material.
  - Complete: owner selected the existing Full hierarchy disclosure
    model as the sole public AS141253 visual. Historical visual-design logic is
    documented outside `docs/`, while the generated Pages tree contains only
    `visual.html`; all four retired Pages routes return 404.
  - Complete: archive published to `daryll-swer/daryllswer.com-archive`; old `daryll-swer/daryllswer.com-neteng-blog` repo deleted.
  - Complete locally: sponsor/trial lead CTAs are filtered from generated article bodies, and same-post numbered reference markers are rewritten to source URLs where extractable.
  - Complete locally: static GitHub Pages site generated under `docs/` with a home index, article pages, responsive figures, podcast embed fallbacks, and AS141253 sheet landing page.
  - Complete locally: desktop and 390x844 mobile browser QA passed for homepage, IPv6 article, responsive figures, media embeds, and sheet landing page.
  - Complete locally: the AS141253 sheet README has clickable artefact links and generated text artefacts are normalised for stable diffs.
  - Complete: GitHub Pages publishes `main` `/docs` at `https://daryll-swer.github.io/daryllswer.com-archive/`.
  - Complete locally: README is reader-focused; maintainer commands moved to `AGENTS.md` and `docs/MIRRORING.md`.
  - Complete locally: WordPress media downloads preserve URL basenames and direct response bytes wherever possible, with filename-preservation fields in asset manifests.
  - Complete locally: AS141253 sheet is rendered as a CSV-backed tabbed `workbook.html` and generated Pages workbook.
  - Complete locally: generated root navigation/canonical handling now uses clean GitHub Pages directory URLs instead of human-facing `index.html` links.
  - Complete locally: three requested articles were targeted-refreshed from canonical WordPress and now use the updated featured images:
    `Shortcomings_CGNAT_FT-scaled.jpg` and `Multi_WAN_FT-scaled.jpg`.
  - Complete locally: targeted sync support was added to `scripts/sync-wordpress-posts.py` so future refreshes can avoid rewriting every post bundle.
  - Complete locally: canonical drift automation was added with a weekly/manual GitHub Actions workflow, `archive-status.json`, and `docs/CANONICAL_DRIFT.md`.
  - Complete locally: drift automation uses a `healthy` -> `degraded` -> `canonical_unavailable` -> `frozen_archive` state model; `frozen_archive` no-ops before canonical network requests.
  - Complete locally: AS141253 has CSV-derived IPv6 prefix-containment JSON and Graphviz DOT artefacts for developer/AI use.
  - Complete: validation and browser QA passed for refreshed article featured images, workbook link, and CIDR hierarchy page.
  - Complete: implementation and follow-up commits pushed to `main`; GitHub Pages deployed successfully and live routes were verified.
  - Complete: the manual `Canonical drift check` workflow passed on final commit `d20085f` after switching the drift checker to a browser-compatible archive User-Agent.
  - Complete locally: canonical CSS was verified from public HTML/CSS; the
    generated archive now self-hosts `Poppins` for body/content text and
    `Raleway` for headings/titles from `assets/fonts/`.
  - Complete locally: internal article-body links to mirrored daryllswer.com
    posts are rewritten to archive-local targets in both repository Markdown
    and generated Pages output, while non-archived canonical pages remain
    external.
  - Complete locally: generated Pages preserves WordPress `h-...` heading IDs
    and emits non-`h-` alias anchors where needed, including the BGP Router ID
    link to the OOB `#dns-and-loopback-addressing` section.
  - Complete locally: validation now checks self-hosted font assets, generated
    CSS font markers, localisable canonical post links, and generated local
    fragment targets.
  - Complete: responsive generator CSS was tightened after mobile QA
    exposed a misleading cropped Chrome screenshot; CDP mobile emulation
    verified a 390 px viewport with no page-level overflow.
  - Complete: commit `44a2a8c` was pushed to `main`; GitHub Pages deployment
    run `28862244073` completed successfully; live routes/assets were verified
    with HTTP 200 responses.
  - Complete locally: generated article headings now expose human-shareable
    section controls. Plain headings have clickable title text, all headings
    get visible `#` permalinks, and all headings get `Copy` buttons backed by
    generated `docs/assets/archive.js`.
  - Complete locally: archive home typography is explicitly bound to the
    self-hosted `Poppins` body font and `Raleway` heading/card-title font.
  - Complete locally: canonical drift now treats third-party documents, PDFs,
    downloads, and external artefacts as outbound links rather than
    mirror-required media. The A10 PDF drift item is cleared.
  - Complete: commit `62cdc70` was pushed to `main`; GitHub Pages deployment
    run `28878086332` completed successfully; live static and browser checks
    verified home fonts, BGP heading controls, copy-link behaviour, and clean
    drift output.
  - Complete locally: WordPress inline colour classes from canonical source
    HTML are preserved into generated Pages article HTML and styled through
    generated WordPress preset palette CSS.
  - Complete locally: canonical/public REST audit found only one current
    coloured article, `bgp-router-id-structuring-in-ipv6-native-networks`,
    using `has-inline-color`, `has-luminous-vivid-amber-color`,
    `has-vivid-red-color`, and `has-luminous-vivid-orange-color`.
  - Complete: commit `eb06a74` was pushed to `main`; GitHub Pages deployment
    run `28879142430` completed successfully; live static and browser checks
    verified the WordPress palette CSS and BGP Router ID colour rendering.
  - Complete: AS141253 IPv6 visual representation alternatives are
    rendered as generated static HTML/CSS examples from the existing CSV
    prefix model. The gallery includes spatial blocks, prefix-length lanes,
    nibble ladder, branch cards, and purpose swimlanes.
  - Complete: commit `43ce2ac` was pushed to `main`; GitHub Pages deployment
    run `28883547390` completed successfully; live static and browser checks
    passed for the visual-options gallery and five standalone pages.
  - Complete locally: AS141253 visual options have been pruned from eleven
    exploratory generated models down to three owner-selected foundations:
    branch cards, collapsible dendrogram, and purpose cluster graph. The
    discarded standalone source and Pages HTML files were deleted.
  - Complete locally: `scripts/ipv6_visual_options.py` now only generates the
    selected foundations, and `scripts/validate-mirror.py` rejects stale
    discarded option titles/files if they reappear.
  - Complete locally: source artefacts and generated Pages output were
    regenerated from existing CSV data after the public Google Sheet HTML fetch
    timed out. No canonical sheet content update was required for this visual
    pruning step.
  - Complete: commit `67e3ae5` was pushed to `main`; GitHub Pages deployment
    run `28922937285` completed successfully; live static and browser checks
    passed for the pruned three-foundation gallery.
  - Complete locally: branch-card visual foundations now render CSV `Notes`
    values for parent and child prefixes, use bounded child cards, and wrap
    prefix chips so mobile/narrow views do not bleed text to the card edge.
  - Complete locally: collapsible dendrogram summaries now render CSV `Notes`
    values beside the matching prefix node.
  - Complete locally: purpose cluster graph data now carries CSV `notes` into
    the detail panel, while per-node SVG labels are suppressed in favour of
    persistent purpose labels plus click-to-inspect detail. This removes the
    observed label-overlap failure mode.
  - Complete: commit `5f8699e` was pushed to `main`; GitHub Pages deployment
    run `28925442002` completed successfully; live static and browser checks
    verified branch notes, dendrogram notes, no page overflow, and
    overlap-safe purpose graph selection.
  - Complete locally: branch-card `+N more` affordances are native
    `details`/`summary` disclosures, not inert count labels. The first twelve
    children remain visible, and remaining children expand/collapse without
    custom JavaScript.
  - Complete locally: selected visual foundations use a responsive contract
    based on viewport metadata, CSS Grid/Flex wrapping, media queries,
    `min-width: 0` containment, and bounded `.visual-frame` panning for dense
    graph/tree content. Local browser QA passed at 320, 390, 768, 1024, 1440,
    1920, and 2560 px viewport widths with no page-level horizontal overflow.
  - Complete: commit `32fad32` was pushed to `main`; GitHub Pages deployment
    run `28926454066` completed successfully; live static and browser checks
    verified branch disclosures and responsive behaviour.
  - Complete: expanded responsive QA initially found a `360px`
    page-level overflow caused by the shared metrics grid, not by the visual
    sections. `scripts/ipv6_visual_options.py` now lets metrics cards and
    metric values shrink/wrap with `min-width: 0`, `minmax(min(100%, 10rem),
    1fr)`, and `overflow-wrap: anywhere`.
  - Complete: the expanded matrix now passes for 40 CSS-pixel widths
    across all four visual pages: 320, 360, 390, 430, 479/480, 575/576,
    599/600, 639/640, 759/760, 767/768, 899/900, 979/980, 991/992,
    1023/1024, 1199/1200, 1279/1280, 1366, 1399/1400, 1439/1440, 1535/1536,
    1599/1600, 1919/1920, and 2560.
  - Complete: commit `d7bade5` was pushed to `main`; GitHub Pages deployment
    run `28962375073` completed successfully; live static checks and
    Chrome/Playwright browser checks passed for the four selected visual pages.
  - Complete locally: `scripts/ipv6_visual_options.py` now generates
    `visual.html` as the primary AS141253 IPv6 visual model, combining
    branch-card readability, native disclosures, collapsed reserved-prefix
    summaries, a static purpose minimap, and a full disclosure hierarchy.
  - Complete locally: workbook navigation, sheet README, repository Markdown,
    and generated article Pages output now prefer `visual.html` for the
    AS141253 Google Sheet replacement path.
  - Complete: commits `b11b84a` and `5152975` were pushed to `main`.
    GitHub Pages deployment run `28965936383` completed successfully for
    final commit `5152975`.
  - Complete: live GitHub Pages checks passed for `visual.html`, the
    AS141253 workbook route, and the IPv6 article route. Chrome DevTools
    Protocol live QA passed for `visual.html` at 320, 390, 768, 1440, and
    2560 px widths with no page-level horizontal overflow, working reserved
    disclosures, and working SVG minimap anchors.
- Last material update:
  - 2026-07-13 Scheduled GitHub Actions run `29229277522` failed only at
    public-archive validation: `scripts/validate-mirror.py` reported `Missing
    dependency: lxml. Install requirements.txt first.` The preceding canonical
    drift check completed healthy; the commit step was skipped and no archive
    changes were published. Commit `c2b0a06` adds explicit Python bootstrap,
    dependency installation, and a regression guard. Manual hosted-runner run
    `29231087908` passed with CPython 3.12.13, installed `lxml`/Pillow,
    validation at 0 errors/1 known warning, and no drift-status commit.
- Next pickup action:
  - No implementation pickup is pending; the next scheduled run will reuse the
    saved pip cache and enforce the same bootstrap contract.
- Open blockers or risks:
  - WordPress REST has one post not listed in `post-sitemap.xml`.
- Verification gap:
  - None for `visual.html`. The known non-blocking warning remains: WordPress
    REST has one post not listed in `post-sitemap.xml`.

## Purpose / Big Picture

- Problem statement:
  - Build a public, reproducible GitHub archive for daryllswer.com published posts and supporting artefacts.
- Desired behavior:
  - A human, Codex thread, or other tooling can inspect Markdown, source HTML, metadata, images, and spreadsheet data without needing WordPress access.
- Acceptance target:
  - Local repo contains scripts, schemas, manifests, mirrored content, featured images, spreadsheet artefacts, validation output, and public-safety checks.

## Plan of Work

### Milestone 1: Scaffold

- Scope:
  - Create repo docs, schema layout, task runner, public-safety defaults, and implementation scripts.
- Done:
  - The repo has a parseable structure matching the prompt and can run `make sync`, `make validate`, and `make scan-secrets`.

### Milestone 2: Public Sync

- Scope:
  - Fetch published WordPress posts, canonical pages, images/media, featured images, and the Google Sheet artefact from public endpoints.
- Done:
  - Content directories and data artefacts exist with manifests and checksums.

### Milestone 3: Validate

- Scope:
  - Validate metadata schemas, local links/assets, spreadsheet tabs/checksums, and secret-scan coverage.
- Done:
  - `docs/VALIDATION.md` records commands run, pass/fail status, gaps, and next approvals.

### Milestone 4: GitHub Pages Site

- Scope:
  - Generate a static HTML site from mirrored content and spreadsheet artefacts.
- Done:
  - `docs/index.html`, `docs/posts/`, `docs/assets/theme.css`,
    `docs/sheets/`, and `docs/.nojekyll` are generated by
    `scripts/render-site.py`.

## Progress

- [x] 2026-07-06 09:07 UTC Read attached implementation prompt.
- [x] 2026-07-06 09:07 UTC Confirmed workspace is an empty Git repo with no commits and no configured remote.
- [x] 2026-07-06 09:07 UTC Scaffold archive repo.
- [x] 2026-07-06 09:17 UTC Run first public sync.
- [x] 2026-07-06 09:19 UTC Run validation: 0 errors, 1 warning.
- [x] 2026-07-06 09:20 UTC Run public-safety scan: passed, 0 findings.
- [x] 2026-07-06 09:20 UTC Generate local preview under `.preview/index.html`.
- [x] 2026-07-06 09:30 UTC Added donation/support CTA archive filter, regenerated, and validated.
- [x] 2026-07-06 09:32 UTC Applied MIT to scripts/tooling and updated licensing docs.
- [x] 2026-07-06 09:35 UTC Owner selected repo name `daryllswer.com-archive`.
- [x] 2026-07-06 09:37 UTC Created and pushed `daryll-swer/daryllswer.com-archive`.
- [x] 2026-07-06 09:37 UTC Deleted old repo `daryll-swer/daryllswer.com-neteng-blog`.
- [x] 2026-07-06 09:50 UTC Added sponsor/trial CTA filtering and direct source URL rewrites for numbered reference markers; regenerated archive and validated.
- [x] 2026-07-06 11:40 UTC Added generated GitHub Pages site under `docs/`, local linked-media archiving, Markdown embed fallback links, and AS141253 sheet link rewrites.
- [x] 2026-07-06 11:54 UTC Browser-checked generated Pages output on desktop and 390x844 mobile.
- [x] 2026-07-06 12:03 UTC Added clickable AS141253 sheet README artefact links and generated text artefact normalisation.
- [x] 2026-07-06 12:06 UTC Pushed generated Pages site, enabled Pages from `main` `/docs`, and verified live homepage HTTP 200.
- [x] 2026-07-06 12:45 UTC Moved maintainer commands out of README and into directive/process docs.
- [x] 2026-07-06 12:45 UTC Added WordPress media filename preservation and manifest validation.
- [x] 2026-07-06 12:45 UTC Added CSV-backed tabbed AS141253 workbook generation.
- [x] 2026-07-06 12:51 UTC Regenerated and browser-checked the updated Pages output.
- [x] 2026-07-06 12:54 UTC Validated, committed `982244a`, pushed to `main`, and verified GitHub Pages rebuild.
- [x] 2026-07-06 13:34 UTC Implemented clean GitHub Pages root URL navigation/canonical rule.
- [x] 2026-07-06 13:39 UTC Regenerated, validated, and browser-checked clean root links locally.
- [x] 2026-07-06 13:48 UTC Committed `822f47c`, pushed, retried transient Pages deploy failure with empty commit `46ec8cc`, and verified live clean root links.
- [x] 2026-07-06 17:49 UTC Target-refreshed the three requested posts from canonical WordPress.
- [x] 2026-07-06 17:53 UTC Added canonical drift checker, status/report files, and weekly/manual GitHub Actions workflow.
- [x] 2026-07-06 17:59 UTC Added CSV-derived AS141253 IPv6 CIDR hierarchy JSON/DOT proof of concept.
- [x] 2026-07-06 18:01 UTC Regenerated sheet artefacts and GitHub Pages output.
- [x] 2026-07-06 18:04 UTC Validation, public-safety scan, script compile, whitespace check, and local browser QA passed.
- [x] 2026-07-06 18:09 UTC Committed `6b00f09`, pushed to `main`, verified Pages deployment success, and live-checked updated routes/assets.
- [x] 2026-07-06 18:15 UTC Hardened the drift checker User-Agent after GitHub Actions saw HTTP 403, reset drift state to healthy, pushed `d20085f`, and verified the manual workflow passed.
- [x] 2026-07-07 10:57 UTC Verified canonical typography from public CSS and added self-hosted `Poppins`/`Raleway` WOFF2 assets with OFL provenance.
- [x] 2026-07-07 10:57 UTC Added Markdown and Pages internal post-link rewrites that preserve fragments and keep non-archived canonical pages external.
- [x] 2026-07-07 10:57 UTC Added WordPress heading alias anchors and validation for generated local fragment targets.
- [x] 2026-07-07 10:57 UTC Regenerated 19 posts, 9 sheet tabs, and generated Pages output; validation/public-safety passed locally.
- [x] 2026-07-07 11:15 UTC Browser/static QA passed for typography, BGP/OOB anchor navigation, AS141253 workbook/hierarchy pages, and 390 px mobile viewport.
- [x] 2026-07-07 11:18 UTC Final local gates passed after regeneration.
- [x] 2026-07-07 11:21 UTC Pushed `44a2a8c`, Pages deployment `28862244073` succeeded, and live URLs/assets verified.
- [x] 2026-07-07 15:25 UTC Implemented generated heading permalink/copy controls, explicit home font selectors, and third-party document drift exclusion.
- [x] 2026-07-07 15:25 UTC Regenerated Pages and drift report; local validation/public-safety and CDP browser QA passed.
- [x] 2026-07-07 15:28 UTC Pushed `62cdc70`, Pages deployment `28878086332` succeeded, and live static/CDP browser checks passed.
- [x] 2026-07-07 15:40 UTC Added WordPress preset colour CSS/validation, regenerated Pages output, and locally verified BGP Router ID computed colours.
- [x] 2026-07-07 15:43 UTC Pushed `eb06a74`, Pages deployment `28879142430` succeeded, and live colour output was verified.
- [x] 2026-07-07 15:55 UTC Started AS141253 visual-options workstream and inspected CSV/hierarchy generator inputs.
- [x] 2026-07-07 16:49 UTC Generated visual-options HTML/CSS prototypes from CSV hierarchy data and locally browser-checked desktop plus 390 px mobile layouts.
- [x] 2026-07-07 16:53 UTC Pushed `43ce2ac`, Pages deployment `28883547390` succeeded, and live visual-option routes were verified.
- [x] 2026-07-07 21:39 UTC Added six interactive AS141253 visual candidates and locally browser-checked the expanded eleven-option gallery.
- [x] 2026-07-07 21:43 UTC Pushed `bce0d98`, Pages deployment `28900695345` succeeded, and live expanded-gallery routes were verified.
- [x] 2026-07-08 06:32 UTC Pruned AS141253 visual-options source and Pages artefacts to the three selected foundations: branch cards, collapsible dendrogram, and purpose cluster graph.
- [x] 2026-07-08 06:37 UTC Local validation, public-safety scan, browser QA, and removed-page 404 checks passed for the pruned three-foundation gallery.
- [x] 2026-07-08 06:41 UTC Pushed `67e3ae5`, Pages deployment `28922937285` succeeded, and live static/browser checks passed for selected and discarded visual-option routes.
- [x] 2026-07-08 07:23 UTC Added CSV note rendering to branch cards and collapsible dendrogram, tightened branch-card chip/card wrapping, and removed per-node SVG labels from the purpose cluster graph in favour of notes-aware detail-panel inspection.
- [x] 2026-07-08 07:30 UTC Pushed `5f8699e`, Pages deployment `28925442002` succeeded, and live static/browser checks passed for the branch-card notes/wrapping, dendrogram notes, and purpose-cluster graph overlap fix.
- [x] 2026-07-08 07:44 UTC Replaced inert branch-card `+N more` labels with native `details`/`summary` disclosures and locally verified all selected visual foundations across phone, tablet, desktop, and wide-display viewport classes.
- [x] 2026-07-08 07:49 UTC Pushed `32fad32`, Pages deployment `28926454066` succeeded, and live static/browser checks passed for branch-card disclosures plus responsive behaviour.
- [x] 2026-07-08 17:21 UTC Ran the expanded responsive matrix, found and fixed the 360 px metrics-grid overflow, and verified 160 local page/viewport combinations with zero failures.
- [x] 2026-07-08 17:29 UTC Pushed `d7bade5`, Pages deployment `28962375073` succeeded, and live static/browser checks passed for the expanded responsive-matrix fix.
- [x] 2026-07-08 18:03 UTC Implemented and generated primary AS141253 `visual.html` from the three selected foundations.
- [x] 2026-07-08 18:13 UTC Local validation, public-safety scan, and Chrome/Playwright QA passed for `visual.html`, the workbook, and visual-foundation navigation.
- [x] 2026-07-10 Implemented the hierarchy-only AS141253 public visual,
  archived historical model references outside `docs/`, and locally verified
  responsive reflow, native disclosures, public links, and retired-route 404s.

## Decision Log

- Decision: Use `YYYY-MM-DD-slug` post bundle directories.
  - Rationale: Lexical sorting and compatibility with common static-site tooling.
  - Date/Author: 2026-07-06, Codex
  - Status: final for local scaffold
  - Impact: Post content lives under `content/posts/YYYY-MM-DD-slug/`.
- Decision: Do not perform destructive GitHub remote actions in this run.
  - Rationale: The prompt requires explicit confirmation first.
  - Date/Author: 2026-07-06, Codex
  - Status: final
  - Impact: Work remains local unless the user later approves remote actions.
- Decision: Exclude donation/support CTAs and `/donation/` article links from archived article bodies.
  - Rationale: These are live-site operational content and would become stale or broken in the durable repo archive.
  - Date/Author: 2026-07-06, Codex
  - Status: final
  - Impact: `make sync` filters these blocks; `make validate` fails if they reappear in generated article files.
- Decision: Exclude sponsor/trial lead CTAs from archived article bodies.
  - Rationale: Sponsor trial promotions are live-site operational content and can become stale or broken in a durable archive.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final
  - Impact: `make sync` filters these blocks; `make validate` fails if they reappear in generated article files.
- Decision: Rewrite same-article numbered reference anchors to source URLs.
  - Rationale: GitHub readers should not be redirected back to WordPress `#h-references` anchors for citation numbers.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final
  - Impact: `make sync` maps marker `1`, `2`, etc. to matching URLs in the References list, falling back to local `#references` if needed.
- Decision: License scripts and tooling under MIT.
  - Rationale: Owner explicitly selected MIT in side-thread decision.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final
  - Impact: MIT applies to scripts/tooling only; mirrored content remains `CC-BY-NC-SA-4.0` unless metadata says otherwise.
- Decision: Use GitHub repository name `daryllswer.com-archive`.
  - Rationale: Owner selected the shorter archive name.
  - Date/Author: 2026-07-06, user
  - Status: final
  - Impact: Local docs and remote publishing target use `daryll-swer/daryllswer.com-archive`.
- Decision: Delete old GitHub repo `daryllswer.com-neteng-blog`.
  - Rationale: Owner explicitly requested complete deletion after creating/pushing the new archive repo.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final
  - Impact: Old repo no longer resolves via GitHub API.
- Decision: Generate GitHub Pages from `docs/`.
  - Rationale: GitHub Pages can publish a static HTML/CSS site from the repository while keeping source bundles in `content/` and `data/`.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final
  - Impact: `scripts/render-site.py` generates homepage, article pages, sheet landing page, copied assets, and theme CSS under `docs/`.
- Decision: Treat GitHub Pages as generated static output, not runtime dynamic content.
  - Rationale: GitHub Pages is static hosting; deterministic regeneration is simpler and more durable than client-side fetching.
  - Date/Author: 2026-07-06, Codex
  - Status: final
  - Impact: `make render-site` must be rerun after sync/rendering changes.
- Decision: Normalise generated text artefacts for stable Git diffs.
  - Rationale: The repository declares `*.csv text eol=lf`; writing Google CSV responses with source CRLF and generated HTML with trailing line whitespace creates avoidable Git churn.
  - Date/Author: 2026-07-06, Codex
  - Status: final locally
  - Impact: `scripts/export-google-sheet.py` normalises CSV response bodies and Google Sheet HTML snapshots; `scripts/render-site.py` strips trailing line whitespace from generated Pages text output.
- Decision: Keep `README.md` concise and reader-facing.
  - Rationale: Maintainer commands are primarily for AI agents and future repository maintainers, not casual archive readers.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final locally
  - Impact: README lists purpose/layout/licence only; `AGENTS.md` and `docs/MIRRORING.md` contain commands and approval boundaries.
- Decision: Preserve WordPress media basenames and bytes.
  - Rationale: Featured and inline images should remain 1:1 with public WordPress media responses, including embedded metadata/EXIF.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final locally
  - Impact: Sync stores media under WordPress URL basenames, records filename preservation, and validation fails on unexpected filename drift.
- Decision: Render AS141253 as a CSV-backed tabbed HTML workbook.
  - Rationale: A standalone HTML workbook mirrors the Google Sheet experience while keeping CSV files editable and diffable.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final locally
  - Impact: `workbook.html` is generated under `data/sheets/...`; Pages serves the same workbook as `docs/sheets/as141253-ipv6-architecture-example/index.html`.
- Decision: Prefer clean GitHub Pages directory URLs for human-facing root links.
  - Rationale: GitHub Pages still needs `docs/index.html` as the static entry file, but reader-facing links should use `./`, `../../`, or the clean project root URL.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final locally
  - Impact: `scripts/render-site.py` no longer generates visible root navigation links to `index.html`; `scripts/validate-mirror.py` guards against regression.
- Decision: Use detection-first canonical drift automation with a frozen-archive sentinel.
  - Rationale: Future canonical changes should be reviewable, and a permanently dead canonical site should not cause endless failing automation or deletion of archived content.
  - Date/Author: 2026-07-06, user/Codex
  - Status: final locally
  - Impact: `.github/workflows/canonical-drift.yml`, `scripts/check-canonical-drift.py`, `archive-status.json`, and `docs/CANONICAL_DRIFT.md` implement the state/report path.
- Decision: Treat the canonical-drift workflow's Python environment as an explicit dependency contract.
  - Rationale: GitHub-hosted runners are clean and their default Python may change; validation imports `lxml`, which is declared in `requirements.txt` but was not installed by the scheduled workflow.
  - Date/Author: 2026-07-13, user/Codex
  - Status: implemented and hosted-runner verified
  - Impact: The workflow selects Python 3.12, caches pip by `requirements.txt`, installs requirements before any archive script, and local validation detects loss or reordering of that bootstrap.
- Decision: Generate an AS141253 IPv6 prefix containment tree from CSV.
  - Rationale: CIDR hierarchy is naturally represented as a rooted containment tree; CSV remains editable while JSON/DOT preserve an auditable graph for developer and AI tooling.
  - Date/Author: 2026-07-06, user/Codex
  - Status: retained developer/AI artefact
  - Impact: `scripts/ipv6_hierarchy.py` generates `cidr-hierarchy.json` and `cidr-hierarchy.dot`.
- Decision: Retire the redundant public AS141253 CIDR hierarchy page.
  - Rationale: The owner selected the full hierarchy view in `visual.html` as the ideal human reader experience; two public routes for the same data add confusion without capability.
  - Date/Author: 2026-07-11, user/Codex
  - Status: implemented and deployed
  - Impact: `cidr-hierarchy.html` is not generated or published, public navigation targets `visual.html`, and the old Pages route must return 404 after deployment.
- Decision: Self-host canonical typography for the archive.
  - Rationale: Public canonical CSS uses `Poppins` for body/form text and
    `Raleway` for headings; self-hosting keeps GitHub Pages readable without
    depending on WordPress or runtime Google Fonts requests.
  - Date/Author: 2026-07-07, user/Codex
  - Status: implemented locally
  - Impact: `assets/fonts/` stores WOFF2 files, OFL files, and checksums;
    generated Pages copies live under `docs/assets/fonts/`.
- Decision: Rewrite mirrored internal post links locally while preserving
  section fragments.
  - Rationale: Archive readers should not leave the archive for content already
    mirrored in the repository, and canonical section links should still land
    on the intended local heading.
  - Date/Author: 2026-07-07, user/Codex
  - Status: implemented locally
  - Impact: Markdown links target local `content/posts/.../index.md`; Pages
    links target local `../<slug>/` routes; generated Pages emits alias anchors
    for WordPress `h-...` heading IDs where needed.
- Decision: Treat AS141253 visual-option pages as generated selection
  prototypes.
  - Rationale: The original tree model is structurally correct but not
    readable enough for human selection; multiple generated static views let
    the owner choose the representation before making one the canonical
    artefact.
  - Date/Author: 2026-07-07, user/Codex
  - Status: implemented locally
  - Impact: `scripts/ipv6_visual_options.py` generates a comparison gallery
    and eleven standalone static/interactive HTML/CSS/JS option pages from the
    CSV-derived prefix hierarchy.
- Decision: Render CSV notes in selected AS141253 visual foundations.
  - Rationale: The `Notes` column contains operational intent such as slicing
    rules, so a visual model that hides it is less readable than the source
    workbook.
  - Date/Author: 2026-07-08, user/Codex
  - Status: implemented locally
  - Impact: Branch cards render parent and child notes; collapsible dendrogram
    summaries render node notes; purpose cluster graph shows notes in the
    selected-node detail panel.
- Decision: Keep purpose-cluster graph node text out of the SVG plot area.
  - Rationale: Per-node labels overlap when selected paths are highlighted in
    a dense graph; persistent purpose labels plus click-to-inspect details keep
    the artwork readable without losing node metadata.
  - Date/Author: 2026-07-08, user/Codex
  - Status: implemented locally
  - Impact: `scripts/ipv6_visual_options.py` emits category labels in the graph
    and moves selected node prefix/label/notes into the side detail panel.
- Decision: Use native disclosures for branch-card hidden children.
  - Rationale: `+N more` represents hidden additional content, which matches
    the HTML disclosure-widget model. A styled count-only span communicates
    existence but cannot expand/collapse or expose state to the browser.
  - Date/Author: 2026-07-08, user/Codex
  - Status: implemented locally
  - Impact: Branch cards keep twelve children visible and render remaining
    children inside `details.branch-more > summary`, without requiring custom
    JavaScript.
- Decision: Define visual-foundation responsiveness as page-bounded layout plus
  frame-bounded diagram panning.
  - Rationale: Branch cards can fully reflow, but dense tree/graph models lose
    readability if compressed indefinitely. Standard responsive CSS should
    prevent page-level overflow while allowing wide diagram content to pan
    inside its explicit visual frame.
  - Date/Author: 2026-07-08, user/Codex
  - Status: implemented locally
  - Impact: Visual pages use viewport metadata, CSS Grid/Flex wrapping, media
    queries, `min-width: 0` containment, and `.visual-frame` overflow handling.
- Decision: Make Full hierarchy the sole public AS141253 visual model.
  - Rationale: Owner review found native disclosure of the complete hierarchy
    more readable and useful than the hybrid dashboard or its visual
    foundations.
  - Date/Author: 2026-07-10, user/Codex
  - Status: implemented and deployed
  - Impact: `visual.html` will render only the full hierarchy. Historical model
    logic will be documented outside `docs/`; no legacy route, navigation, or
    generated Pages copy may remain.

## Validation and Acceptance

- Reproducible checks:
  - `make sync`: passed; fetched public posts, media, and spreadsheet artefacts.
  - `make validate`: passed at 2026-07-06 09:29 UTC; validation recorded 0 errors and 1 warning.
  - `make scan-secrets`: passed at 2026-07-06 09:29 UTC; public-safety scan recorded 0 findings.
  - `make render-preview`: passed; generated `.preview/index.html`.
  - `rg -n "It would be appreciated|Click here to donate|https://www\\.daryllswer\\.com/donation/?" content/posts -g 'index.md' -g 'source/rendered-article.html' -g 'source/wordpress-post.json' -g 'source/canonical-page.html'`: no matches.
  - `make validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 09:49 UTC; validation recorded 0 errors and 1 warning, public-safety scan recorded 0 findings.
  - `rg -n "https://www\\.daryllswer\\.com/[^)\\s]+/#(?:h-)?references|#h-references|This article was sponsored|FastNetMon|free 30-day" content/posts -g 'index.md'`: no matches.
  - `make sync render-site validate PYTHON=<bundled-python>`: passed at 2026-07-06 11:35 UTC; validation recorded 0 errors and 1 warning.
  - `python3 -m py_compile scripts/sync-wordpress-posts.py scripts/validate-mirror.py scripts/render-site.py`: passed at 2026-07-06 11:52 UTC.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-06 12:00 UTC.
  - `make sync render-site validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 12:03 UTC; validation recorded 0 errors and 1 warning, public-safety scan recorded 0 findings.
  - `make validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 12:00 UTC; validation recorded 0 errors and 1 warning, public-safety scan recorded 0 findings.
  - `git diff --check`: passed at 2026-07-06 12:04 UTC.
  - Local browser QA against `http://127.0.0.1:4173/`: passed at 2026-07-06 11:54 UTC for desktop and 390x844 mobile.
  - `make sync render-site validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 12:51 UTC; validation recorded 0 errors and 1 known sitemap warning, public-safety scan recorded 0 findings.
  - `make validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 12:55 UTC after recording live Pages verification; validation recorded 0 errors and 1 known sitemap warning, public-safety scan recorded 0 findings.
  - Media filename preservation check: passed at 2026-07-06 12:52 UTC; 68 WordPress media assets, 19 featured images, 0 preservation failures.
  - Workbook structure check: passed at 2026-07-06 12:52 UTC; 9 manifest tabs, 9 radio inputs, 9 visible tab labels, and 9 panels in both `data/.../workbook.html` and `docs/.../index.html`.
  - Local browser QA against `http://127.0.0.1:4173/`: passed at 2026-07-06 12:51 UTC for desktop and mobile-sized viewport; index had 19 cards, no broken images, no page overflow, IPv6 article linked local sheet page, workbook tabs switched correctly.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-06 12:51 UTC.
  - `git diff --check`: passed at 2026-07-06 12:51 UTC.
  - GitHub Pages API: passed at 2026-07-06 12:54 UTC; status `built`, source `main` `/docs`.
  - Live route check: passed at 2026-07-06 12:54 UTC; homepage, IPv6 article, AS141253 workbook, ODS artefact, and `Scaffold_FT.png` returned HTTP 200. Live workbook had 9 tabs/9 panels; live homepage had 19 post cards; live article had 2 embed wrappers and the local sheet link.
  - `make render-site validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 13:35 UTC; validation recorded 0 errors and 1 known sitemap warning, public-safety scan recorded 0 findings.
  - Local browser click QA against `http://127.0.0.1:4173/`: passed at 2026-07-06 13:39 UTC; homepage canonical used the clean project root, homepage Index used `./`, article Index used `../../`, workbook Archive index used `../../`, and click targets resolved to `/` without `index.html`.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-06 13:39 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 13:39 UTC; validation recorded 0 errors and 1 known sitemap warning, public-safety scan recorded 0 findings.
  - `git diff --check`: passed at 2026-07-06 13:39 UTC.
  - `rg` check for generated `index.html` root navigation/canonical regressions under `docs/*.html`: no matches at 2026-07-06 13:39 UTC.
  - GitHub Pages deployment: first run for `822f47c` failed during `actions/deploy-pages@v5` with `Deployment failed, try again later`; empty commit `46ec8cc` retriggered Pages successfully at 2026-07-06 13:47 UTC.
  - Live Pages check: passed at 2026-07-06 13:48 UTC; root returned HTTP 200 with clean canonical and `href="./"` Index link, IPv6 article returned HTTP 200 with `href="../../"` Index link, AS141253 workbook returned HTTP 200 with `href="../../"` Archive index and 9 sheet tabs.
  - Targeted article refresh: passed at 2026-07-06 17:49 UTC; live WordPress REST showed the three requested posts modified on 2026-07-06 and using `Shortcomings_CGNAT_FT-scaled.jpg` / `Multi_WAN_FT-scaled.jpg`.
  - `scripts/check-canonical-drift.py`: passed at 2026-07-06 17:53 UTC; state `healthy`, frozen `false`, with one non-target drift item reported for the CGNAT article's A10 PDF.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-06 18:01 UTC.
  - `git diff --check`: passed at 2026-07-06 18:01 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-06 18:01 UTC; validation recorded 0 errors and 1 known sitemap warning, public-safety scan recorded 0 findings.
  - Local browser QA against `http://127.0.0.1:4173/`: passed at 2026-07-06 18:04 UTC; homepage had 19 cards, refreshed target articles had updated featured images, lazy inline images loaded after scroll, workbook linked the CIDR hierarchy, hierarchy page had 153 nodes, and desktop/mobile checks had no page overflow.
  - GitHub Pages deployment for `6b00f09`: passed at 2026-07-06 18:08 UTC; pages-build-deployment completed successfully.
  - Live Pages check: passed at 2026-07-06 18:09 UTC; root showed `Shortcomings_CGNAT_FT-scaled.jpg` and `Multi_WAN_FT-scaled.jpg`, target article/image URLs returned HTTP 200, AS141253 workbook/hierarchy/JSON/DOT routes returned HTTP 200, and hierarchy HTML included the clean `./` workbook link.
  - GitHub Pages deployment for `d20085f`: passed at 2026-07-06 18:14 UTC.
  - Manual `Canonical drift check` workflow for `d20085f`: passed at 2026-07-06 18:15 UTC and did not advance `origin/main`.
  - Final live route check: passed at 2026-07-06 18:15 UTC for the refreshed featured-image assets and AS141253 hierarchy page.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-07 16:48 UTC.
  - `git diff --check`: passed at 2026-07-07 16:48 UTC.
  - `make render-site PYTHON=<bundled-python>`: passed at
    2026-07-07 16:47 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-07
    16:48 UTC with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-07
    16:48 UTC with 0 public-safety findings.
  - Local browser QA against `http://127.0.0.1:4173/`: passed at
    2026-07-07 16:48 UTC for the visual-options gallery and five standalone
    pages at desktop/default and 390 px mobile widths. Page-level
    `scrollWidth` equalled viewport width; wide diagrams scroll inside
    `.visual-frame` containers.
  - Live route checks: passed at 2026-07-07 16:53 UTC for
    `visual-options.html` and all five `visual-option-*.html` pages; all
    returned HTTP 200, included expected markers, and had no unrewritten source
    font paths.
  - Live browser QA: passed at 2026-07-07 16:53 UTC for the visual-options
    gallery at desktop/default and 390 px mobile widths; page-level
    `scrollWidth` equalled viewport width and all five option sections
    rendered.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-07 21:39 UTC.
  - `git diff --check`: passed at 2026-07-07 21:39 UTC.
  - `make render-site PYTHON=<bundled-python>`: passed at
    2026-07-07 21:39 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-07
    21:39 UTC with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at
    2026-07-07 21:39 UTC with 0 public-safety findings.
  - Local browser QA against `http://127.0.0.1:4173/`: passed at
    2026-07-07 21:39 UTC for the expanded visual-options gallery and eleven
    standalone pages at desktop/default and 390 px mobile widths. Page-level
    `scrollWidth` equalled viewport width, no console errors were reported,
    and representative interactions passed for graph node clicks, sunburst
    arc clicks, purpose-cluster node clicks, dendrogram expand/collapse,
    walkthrough next-step, and searchable focus.
  - Live route checks: passed at 2026-07-07 21:43 UTC for
    `visual-options.html` and the six new `visual-option-*.html` pages; all
    returned HTTP 200, included expected markers, and had no unrewritten source
    font paths.
  - Live browser QA: passed at 2026-07-07 21:43 UTC for the expanded gallery
    at desktop/default and 390 px mobile widths; page-level `scrollWidth`
    equalled viewport width, eleven option cards/sections rendered, and
    searchable focus returned loopback matches on the deployed page.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-08 06:37 UTC.
  - `git diff --check`: passed at 2026-07-08 06:37 UTC.
  - `make render-site PYTHON=<bundled-python>`: passed at
    2026-07-08 06:32 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-08
    06:37 UTC with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at
    2026-07-08 06:37 UTC with 0 public-safety findings.
  - Local browser QA against `http://127.0.0.1:4173/`: passed at
    2026-07-08 06:37 UTC for the pruned visual-foundations gallery and three
    standalone pages at desktop/default and 390 px mobile widths. The gallery
    rendered three cards/sections, discarded model titles were absent, page
    `scrollWidth` equalled viewport width, browser console errors were empty,
    dendrogram expand/collapse worked, and purpose-cluster node selection
    updated the detail panel.
  - Local removed-page check: passed at 2026-07-08 06:37 UTC; all eight
    discarded standalone visual-option routes returned HTTP 404 from the local
    `docs/` server.
  - GitHub Pages deployment for `67e3ae5`: passed at 2026-07-08 06:40 UTC;
    pages-build-deployment run `28922937285` completed successfully.
  - Live route checks: passed at 2026-07-08 06:41 UTC for
    `visual-options.html`, the three selected standalone option pages, and the
    eight discarded standalone option routes. The selected routes returned HTTP
    200 with expected markers; discarded routes returned HTTP 404.
  - Live browser QA: passed at 2026-07-08 06:41 UTC for the visual-foundations
    gallery at desktop/default width; three option cards/sections rendered,
    discarded model titles were absent, page-level `scrollWidth` equalled
    viewport width, and browser console errors were empty.
  - Local Chrome/Playwright DOM QA against `http://127.0.0.1:4173/`: passed at
    2026-07-08 07:22 UTC for the three selected visual foundations and gallery.
    Branch cards at 390 px had `scrollWidth=390`, 53 rendered child notes, and
    no page overflow. Collapsible dendrogram at 390 px had `scrollWidth=390`,
    90 rendered tree notes, and no page overflow. Purpose cluster graph at
    1280 px had 0 graph node labels, 9 purpose labels, no detected graph text
    overlaps, and notes appeared in the detail panel after clicking
    `2400:d960:804::/56`.
  - `make render-site PYTHON=<bundled-python>`: passed at 2026-07-08 07:26 UTC;
    generated 19 posts and refreshed sheet/Pages output.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-08 07:24 UTC.
  - `git diff --check`: passed at 2026-07-08 07:26 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-08 07:26 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-08
    07:26 UTC with 0 public-safety findings.
  - GitHub Pages deployment for `5f8699e`: passed at 2026-07-08 07:29 UTC;
    pages-build-deployment run `28925442002` completed successfully.
  - Live static checks: passed at 2026-07-08 07:30 UTC for
    `visual-option-branch-cards.html`,
    `visual-option-collapsible-dendrogram.html`,
    `visual-option-purpose-cluster-graph.html`, and `visual-options.html`.
    All returned HTTP 200 with required note markers and 0
    `graph-node-label` occurrences.
  - Live Chrome/Playwright DOM QA against GitHub Pages: passed at
    2026-07-08 07:30 UTC. Branch cards at 390 px had `scrollWidth=390` and 53
    child notes; collapsible dendrogram at 390 px had `scrollWidth=390` and
    90 tree notes; purpose cluster graph at 1280 px had 0 graph node labels, 9
    purpose labels, no detected graph text overlaps, and notes appeared in the
    detail panel after selecting `2400:d960:804::/56`.
  - Local Chrome/Playwright responsive QA against `http://127.0.0.1:4173/`:
    passed at 2026-07-08 07:42 UTC across 28 page/viewport combinations:
    standalone branch cards, collapsible dendrogram, purpose cluster graph,
    and gallery pages at 320, 390, 768, 1024, 1440, 1920, and 2560 px widths.
    Failures: 0. All combinations had no page-level horizontal overflow,
    graph node labels remained 0, graph text overlaps were 0, and branch-card
    disclosures toggled open/closed in every viewport.
  - `make render-site PYTHON=<bundled-python>`: passed at 2026-07-08 07:46 UTC;
    generated 19 posts and refreshed generated Pages output.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-08 07:46 UTC.
  - `git diff --check`: passed at 2026-07-08 07:46 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-08 07:47 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-08
    07:46 UTC with 0 public-safety findings.
  - GitHub Pages deployment for `32fad32`: passed at 2026-07-08 07:48 UTC;
    pages-build-deployment run `28926454066` completed successfully.
  - Live static checks: passed at 2026-07-08 07:48 UTC for
    `visual-option-branch-cards.html`,
    `visual-option-collapsible-dendrogram.html`,
    `visual-option-purpose-cluster-graph.html`, and `visual-options.html`.
    Required branch disclosure/responsive markers were present, branch-card
    pages had 3 `details.branch-more` controls, and graph node labels remained
    0.
  - Live Chrome/Playwright DOM QA against GitHub Pages: passed at
    2026-07-08 07:49 UTC at 390 px and 1440 px widths. All four visual pages
    had no page-level horizontal overflow, graph text overlaps were 0, and the
    branch-card disclosure opened with the `Show fewer` state.
  - Local expanded Chrome/Playwright responsive QA against
    `http://127.0.0.1:4173/`: first run at 2026-07-08 17:16 UTC failed only
    at 360 px with page overflow `364/360` on all four visual pages. Root
    cause was the shared metrics grid root-prefix card. After the metrics CSS
    fix, the rerun passed at 2026-07-08 17:20 UTC across 160 combinations:
    four visual pages by 40 CSS-pixel widths. Failures: 0.
  - GitHub Pages deployment for `d7bade5`: passed at 2026-07-08 17:26 UTC;
    pages-build-deployment run `28962375073` completed successfully.
  - Live static checks: passed at 2026-07-08 17:27 UTC for
    `visual-option-branch-cards.html`,
    `visual-option-collapsible-dendrogram.html`,
    `visual-option-purpose-cluster-graph.html`, and `visual-options.html`.
    The deployed CSS included the metrics grid/wrapping fix, branch-card pages
    had `details.branch-more` controls, and graph node labels remained 0.
  - Live Chrome/Playwright DOM QA against GitHub Pages: passed at
    2026-07-08 17:28 UTC at 360, 390, 768, 1440, and 1920 px widths. All four
    visual pages had no page-level horizontal overflow, branch-card disclosure
    controls opened/closed, graph node labels stayed absent after click
    interactions, and SVG text overlaps were 0.
  - `make render-site PYTHON=<bundled-python>`: passed at 2026-07-08 17:22 UTC;
    generated 19 posts and refreshed generated Pages output.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-08 17:22 UTC.
  - `git diff --check`: passed at 2026-07-08 17:22 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-08 17:23 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-08
    17:22 UTC with 0 public-safety findings.
  - `make sync PYTHON=<bundled-python>`: passed at 2026-07-08 18:01 UTC;
    synced 19 posts and exported 9 sheet tabs.
  - `make render-site PYTHON=<bundled-python>`: passed at 2026-07-08
    18:02 UTC; generated 19 posts and refreshed generated Pages output.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-08 18:05 UTC.
  - `git diff --check`: passed at 2026-07-08 18:05 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-08 18:05 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-08
    18:05 UTC with 0 public-safety findings.
  - Local Chrome/Playwright QA against `http://127.0.0.1:4173/`: passed at
    2026-07-08 18:13 UTC for `visual.html` at 320, 360, 390, 430, 768, 1024,
    1440, 1920, and 2560 px widths. Failures: 0. Checks covered page-level
    overflow, expected sections, absence of JS on `visual.html`, reserved
    disclosure open/close, SVG minimap anchor targets/clicks, and 390 px smoke
    checks for `visual-options.html` and the workbook.
  - Anchor-fix local Chrome QA against `http://127.0.0.1:4173/`: passed at
    2026-07-08 18:23 UTC for `visual.html` at 320, 360, 390, 430, 768, 1024,
    1440, 1920, and 2560 px widths. Failures: 0. This rerun verified stable
    `#at-a-glance-allocation`, `#operational-branches`, `#purpose-map`, and
    `#full-hierarchy` section anchors plus reserved disclosure and SVG minimap
    behaviour.
  - `python3 -m py_compile scripts/*.py`: passed at 2026-07-08 18:23 UTC.
  - `git diff --check`: passed at 2026-07-08 18:23 UTC.
  - `make validate PYTHON=<bundled-python>`: passed at 2026-07-08 18:23 UTC
    with 0 validation errors and 1 known sitemap warning. Validation now
    requires the final `visual.html` section anchors.
  - `make scan-secrets PYTHON=<bundled-python>`: passed at 2026-07-08
    18:23 UTC with 0 public-safety findings.
  - GitHub Pages deployment for `5152975`: passed at 2026-07-08 18:24 UTC;
    pages-build-deployment run `28965936383` completed successfully.
  - Live static checks: passed at 2026-07-08 18:25 UTC for `visual.html`, the
    AS141253 workbook route, and the IPv6 article route. All returned HTTP
    200; `visual.html` had required final-section markers and no script tag or
    source font path leakage; the article route linked to
    `../../sheets/as141253-ipv6-architecture-example/visual.html`.
  - Live Chrome DevTools Protocol QA against GitHub Pages: passed at
    2026-07-08 18:25 UTC for `visual.html` at 320, 390, 768, 1440, and 2560
    px widths. Failures: 0. Checks covered page-level overflow, final section
    anchors, 57 reserved disclosure groups, reserved disclosure opening, and
    SVG minimap anchor targets/clicks.
  - `make sync PYTHON=<bundled-python>`: passed on 2026-07-10; synced 19 posts
    and exported 9 sheet tabs. `make render-site` regenerated 19 post pages.
  - `python3 -m py_compile scripts/*.py` and `git diff --check`: passed on
    2026-07-10.
  - `make validate PYTHON=<bundled-python>`: passed on 2026-07-10 with 0
    errors and 1 known sitemap warning. `make scan-secrets` passed with 0
    findings.
  - Local Chrome QA: passed on 2026-07-10 at 320, 360, 390, 430, 768, 1024,
    1440, 1920, and 2560 CSS px. No page-level overflow; the hierarchy had 28
    reserved groups; pointer and Enter-key disclosure controls exposed and hid
    exact reserved-prefix details.
  - GitHub Pages deployment for `f94d8b3`: passed on 2026-07-10; run
    `29081542020` completed successfully. Live `visual.html`, workbook, and
    IPv6 article routes returned 200; the retired gallery and all three
    foundation routes returned 404.
- Evidence paths:
  - `docs/VALIDATION.md`
  - `docs/index.html`
  - `docs/PUBLIC_SAFETY.md`
  - `archive-manifest.json`

## Idempotence and Recovery

- Safe re-run policy:
  - Sync scripts must be idempotent: rerunning may update generated files but must not require private state.
- Risky step rollback:
  - Remote GitHub actions are blocked until user confirmation.
- Backup and state-preservation policy:
  - Public source snapshots are stored under each post's `source/` directory for auditability.

## Risks and Assumptions

- Risks:
  - WordPress rendered HTML may contain theme wrappers. Mitigation: use REST content for article body and canonical HTML only for metadata/source snapshot.
  - Markdown conversion may not represent every HTML detail. Mitigation: preserve rendered/source HTML alongside Markdown.
  - Third-party media licensing may be ambiguous. Mitigation: record provenance and flag unclear assets.
- Assumptions:
  - Public WordPress REST, sitemap/RSS, and Google Sheet export endpoints remain accessible.

## Outcomes & Retrospective

- Achieved:
  - Local repo scaffold, public sync, donation/support CTA filtering, spreadsheet export, validation, public-safety scan, preview generation, and generated GitHub Pages site completed.
- Remaining:
  - None for the hierarchy-only AS141253 visual-model revision.
- Retrospective timestamp:
  - 2026-07-06 09:20 UTC
