# daryllswer.com Archive Implementation Status

## Current State

- Project / repo: `daryllswer.com-archive`
- Active plan: `PLANS.md`
- Architecture reference: `ARCHITECTURE.md`
- Current sprint / workstream: proprietary README logo provenance naming
  refinement
- Status: complete and deployed; public README links verified
- Last updated: 2026-07-24
- Implementer role/model/thread: delegated `implementer-luna` for the bounded
  generator and validation change; current Codex Desktop integrated and tested
  the result
- Architect role/model/thread: current Codex Desktop thread plus user review
- Current budget/rate-limit state: unknown; no warning observed in this turn

## Scope

- In scope:
  - Public WordPress post mirroring, public featured/inline/linked media, Google Sheet public exports, GitHub Pages static site generation, manifests, schemas, validation, and safety scan.
- Out of scope:
  - Remote force-push/visibility changes without explicit confirmation.
  - Private WordPress admin exports, database access, SSH backend access, private comments, credentials, cookies, browser profiles, and local-only operational state.

## Changed Files / Areas

- `PLANS.md`:
  - Status: modified
  - Notes: Initial durable execution plan.
- `IMPLEMENTATION_STATUS.md`:
  - Status: modified
  - Notes: Initial live implementation ledger.
- Repository scaffold:
  - Status: complete
  - Notes: README, AGENTS, Makefile, schemas, docs, architecture, escalation rules, and scripts added.
- `content/posts/`:
  - Status: complete
  - Notes: 19 generated post bundles with Markdown, metadata, source snapshots, featured images, and assets.
- `data/sheets/as141253-ipv6-architecture-example/`:
  - Status: complete
  - Notes: ODS, 9 LF-normalised CSV exports, 9 CSVW metadata files, whitespace-normalised HTML snapshots, and clickable artefact links generated.
- `docs/VALIDATION.md`:
  - Status: complete
  - Notes: Validation passed with 0 errors and 1 sitemap warning.
- `docs/PUBLIC_SAFETY.md`:
  - Status: complete
  - Notes: Public-safety scan passed with 0 findings after replacing local path references with public-safe placeholders.
- `docs/` GitHub Pages site:
  - Status: complete and deployed
  - Notes: `scripts/render-site.py` generates homepage, article pages, responsive theme CSS, copied post assets, sheet artefact landing page, and `.nojekyll`; GitHub Pages publishes `main` `/docs`.
- Donation/support CTA archive filter:
  - Status: complete
  - Notes: `scripts/sync-wordpress-posts.py` removes article blocks containing the donation CTA or `/donation/` links and stores only redacted/hash audit metadata.
- Sponsor/trial CTA archive filter:
  - Status: complete
  - Notes: `scripts/sync-wordpress-posts.py` removes operational sponsor/trial lead CTAs from generated article bodies and records redacted/hash audit metadata.
- Numbered reference link rewriting:
  - Status: complete
  - Notes: Same-post `#h-references`/`#references` citation links are rewritten to the matching source URL in the article's References list, with local `#references` as fallback.
- Local media and sheet link rewriting:
  - Status: complete locally
  - Notes: WordPress-uploaded media file links are downloaded where possible and rewritten to local archive assets; the AS141253 Google Sheet link is rewritten to repository/Pages sheet artefacts.
- Embedded media handling:
  - Status: complete locally
  - Notes: Markdown uses durable embed links; Pages article output uses iframe wrappers with fallback links.
- Licensing:
  - Status: complete
  - Notes: Scripts/tooling are MIT licensed; mirrored blog content is `CC-BY-NC-SA-4.0`; third-party media/external artefacts are not assumed covered by either licence.
- README proprietary brand asset:
  - Status: complete and verified
  - Notes: Owner-provided `13_DS_Logo_Dark_Mode_SEO.png` is the
    README header with a dedicated all-rights-reserved notice, checksum
    manifest, explicit exclusion from MIT and `CC-BY-NC-SA-4.0`, and a
    validation guard for the path, checksum, notice, local copyright-anchor
    target, and Pages exclusion.
- README logo provenance naming refinement:
  - Status: complete and deployed
  - Notes: Renamed the logo record to
    `assets/readme/ASSET_PROVENANCE.md` and the analogous favicon record to
    `assets/brand/ASSET_PROVENANCE.md`, avoiding mixed terminology. Both
    records are provenance/handling documents, not licences. The controlling
    rights instrument remains
    `LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt`; validation rejects
    either legacy asset `README.md` path or textual reference. Source asset
    bytes, SHA-256 values, manifests, and licence boundaries are unchanged.
    Commit `a401ecd` is deployed by GitHub Pages run `30081615905`; the public
    GitHub README correctly links to both the new logo provenance record and
    controlling notice.
- GitHub Pages proprietary favicon:
  - Status: complete and deployed
  - Notes: Owner-provided `01_DS_Favicon_Dark_Mode.png` remains byte-exact in
    `assets/brand/`; `render-site.py` generates a 512 px proprietary
    derivative for the home/article header mark and browser favicon metadata.
    Validation covers manifests, checksum, notice, image dimensions, generated
    links, removal of the text-only `DS` badge, and exclusion of the full-size
    source from `docs/`.
- GitHub publication:
  - Status: complete
  - Notes: New public repo `daryll-swer/daryllswer.com-archive` created and pushed; old repo `daryll-swer/daryllswer.com-neteng-blog` deleted.
- README maintainer command move:
  - Status: complete and pushed
  - Notes: README is reader-facing; maintainer commands live in `AGENTS.md` and `docs/MIRRORING.md`.
- WordPress media filename/byte preservation:
  - Status: complete and pushed
  - Notes: Sync now stores WordPress media under source basenames where possible, preserves direct response bytes, and records filename-preservation fields in asset manifests.
- AS141253 tabbed workbook:
  - Status: complete and pushed
  - Notes: `scripts/export-google-sheet.py` generates `data/sheets/as141253-ipv6-architecture-example/workbook.html`; `scripts/render-site.py` publishes it as the Pages sheet route.
- AS141253 CIDR hierarchy route retirement:
  - Status: complete and deployed
  - Notes: `visual.html` is the sole human-facing hierarchy model. The
    CSV-derived JSON and DOT exports remain developer/AI artefacts;
    `cidr-hierarchy.html` has been removed from generation, Pages output, and
    navigation. Commit `4b4e813` is deployed by GitHub Pages run
    `29147641547`; live route verification passed.
- Clean GitHub Pages root URL navigation:
  - Status: complete and pushed
  - Notes: `docs/index.html` remains the generated Pages entry file, but visible root navigation and root canonical metadata now use clean directory URLs.
- Targeted article refresh:
  - Status: complete and pushed
  - Notes: The three requested articles were re-synced from canonical WordPress. Featured media now uses `Shortcomings_CGNAT_FT-scaled.jpg` for the CGNAT shortcomings article and `Multi_WAN_FT-scaled.jpg` for both Multi-WAN articles, with source filenames preserved.
- Targeted sync tooling:
  - Status: complete and pushed
  - Notes: `scripts/sync-wordpress-posts.py` supports `--slug` and `--slugs` to refresh selected posts while preserving the rest of `archive-manifest.json`.
- Canonical drift automation:
  - Status: complete and pushed
  - Notes: `.github/workflows/canonical-drift.yml` runs weekly/manual checks. `scripts/check-canonical-drift.py` writes `archive-status.json` and `docs/CANONICAL_DRIFT.md`, with `frozen_archive` no-op behaviour for permanent canonical failure.
- Canonical drift Python bootstrap:
  - Status: complete and hosted-runner verified
  - Notes: Scheduled run `29229277522` failed because the clean runner did not
    install `lxml` before archive validation. The workflow now uses
    `actions/checkout@v6`, `actions/setup-python@v6`, Python 3.12, pip cache
    keyed to `requirements.txt`, and dependency installation before every
    archive script. `validate-mirror.py` guards the active workflow step
    contract, order, and `lxml` declaration. Manual workflow run `29231087908`
    verified the same clean hosted-runner path successfully.
- AS141253 IPv6 hierarchy proof of concept:
  - Status: complete and pushed
  - Notes: `scripts/ipv6_hierarchy.py` derives a rooted IPv6 prefix containment tree from CSV, producing JSON and Graphviz DOT developer/AI artefacts. Current graph has 153 nodes and max depth 5; `visual.html` is the sole public reader model.
- Drift report:
  - Status: generated and pushed
  - Notes: Current state is `healthy` / `frozen=false`; report now shows 0
    changed archived posts. Third-party documents/PDFs/downloads such as the
    A10 PDF stay as outbound links and are not mirror-required drift.
- Drift workflow hardening:
  - Status: complete and pushed
  - Notes: Manual GitHub Actions dispatch initially received HTTP 403 from canonical REST. `scripts/check-canonical-drift.py` now uses a browser-compatible archive User-Agent; the final manual workflow run passed on commit `d20085f` without creating another state commit.
- Canonical typography:
  - Status: implemented locally
  - Notes: Public canonical CSS was verified to use `Poppins` for body/form
    text and `Raleway` for headings. Self-hosted WOFF2 assets and per-family
    OFL provenance live in `assets/fonts/`; `render-site.py` copies them to
    `docs/assets/fonts/`.
- Internal post-link localisation:
  - Status: implemented locally
  - Notes: `scripts/sync-wordpress-posts.py` rewrites Markdown body links to
    mirrored posts as local `content/posts/.../index.md` targets;
    `scripts/render-site.py` rewrites generated Pages article links as local
    `../<slug>/` routes while preserving fragments and dropping tracking query
    parameters.
- Section anchor preservation:
  - Status: implemented locally
  - Notes: Generated Pages keeps WordPress heading IDs such as `h-dns-and-loopback-addressing`
    and emits alias anchors such as `dns-and-loopback-addressing` when needed.
    `scripts/validate-mirror.py` verifies generated local fragment links.
- Typography/link validation:
  - Status: implemented locally
  - Notes: Validation now checks self-hosted font files/checksums, generated
    CSS font markers, localisable canonical post links in Markdown and Pages
    article bodies, and generated local fragment targets.
- Responsive Pages QA:
  - Status: complete and pushed
  - Notes: `scripts/render-site.py` now emits mobile-safe grid/flex sizing and
    fixed responsive heading steps. Chrome DevTools Protocol mobile emulation
    verified the homepage at 390 px with `scrollWidth=390` and
    `clientWidth=390`.
- Heading permalink controls:
  - Status: complete and pushed
  - Notes: Generated article headings now have visible `#` permalinks and
    `Copy` buttons. Plain headings also wrap heading text in a same-section
    link; headings that already contain inline links avoid invalid nested
    anchors and keep the explicit permalink/copy controls.
- Third-party artefact drift policy:
  - Status: complete and pushed
  - Notes: `scripts/check-canonical-drift.py` now tracks WordPress-uploaded
    image-media drift only. Linked third-party PDFs/documents/downloads remain
    outbound links and do not produce mirror-required drift.
- WordPress inline colour palette:
  - Status: complete and pushed
  - Notes: `scripts/render-site.py` now emits WordPress preset colour CSS via
    `scripts/wordpress_palette.py`, and `scripts/validate-mirror.py` checks
    that source WordPress colour classes survive into generated Pages output
    and have generated CSS rules.
- AS141253 visual representation foundations:
  - Status: complete and pushed
  - Notes: `scripts/ipv6_visual_options.py` now generates only the three
    owner-selected foundations from the CSV-derived prefix model: branch cards,
    collapsible dendrogram, and purpose cluster graph. Discarded exploratory
    standalone pages were deleted from `data/` and generated `docs/`, and
    `scripts/validate-mirror.py` now fails if removed model titles/files
    reappear. Commit `67e3ae5` is deployed via GitHub Pages run
    `28922937285`.
- AS141253 visual foundation polish:
  - Status: complete and pushed
  - Notes: `scripts/ipv6_visual_options.py` now renders CSV `Notes` in branch
    cards, child cards, collapsible dendrogram summaries, and the purpose graph
    detail panel. Branch-card chips/cards use bounded wrapping to avoid text
    bleed on narrow screens. Purpose cluster graph suppresses per-node SVG
    labels and keeps category labels plus click-to-inspect detail to avoid
    selected-path label overlap. Commit `5f8699e` is deployed via GitHub Pages
    run `28925442002`.
- AS141253 branch disclosure and responsive hardening:
  - Status: complete and pushed
  - Notes: `scripts/ipv6_visual_options.py` now renders hidden branch-card
    children with native `details`/`summary` controls. Shared visual CSS was
    hardened with wider responsive page bounds, Grid/Flex wrapping,
    `min-width: 0` containment, tablet graph stacking, narrow-phone padding,
    and bounded `.visual-frame` panning for dense graph/tree content. Commit
    `32fad32` is deployed via GitHub Pages run `28926454066`.
- AS141253 expanded responsive matrix:
  - Status: complete and pushed
  - Notes: Expanded QA found a `360px` page-level overflow caused by the shared
    metrics grid/root-prefix card. `scripts/ipv6_visual_options.py` now uses
    `minmax(min(100%, 10rem), 1fr)`, `min-width: 0`, and
    `overflow-wrap: anywhere` for metrics layout/value wrapping. The full
    40-width, 4-page local matrix passes, and commit `d7bade5` is deployed via
    GitHub Pages run `28962375073`.
- AS141253 hierarchy-only public visual model:
  - Status: complete and pushed
  - Notes: Owner selected the native Full hierarchy disclosure model as the
    only public reader path. `visual.html` now renders only the full hierarchy;
    historical model logic is documented under the non-Pages data archive.
    Workbook, README, Markdown, and generated Pages links continue to prefer
    `visual.html`; no legacy visual HTML is copied under `docs/`. Commit
    `f94d8b3` is deployed by GitHub Pages run `29081542020`.
- AS141253 collapsed-first-open production hardening:
  - Status: complete and deployed
  - Notes: `scripts/ipv6_visual_options.py` now emits every full-hierarchy
    `details` element without `open`; native `details`/`summary` controls keep
    each normal and reserved branch individually expandable. Validation now
    rejects an `open` attribute on a hierarchy or reserved-prefix disclosure in
    source or generated Pages output. The cleanup audit found no safely
    removable tracked files or dead active scripts. Proven ignored local
    caches, preview output, bytecode, and Finder metadata were moved to the
    macOS Trash; audit/source/provenance/licence/brand/legacy reference files
    remain intentionally retained. Commit `dabcbda` is deployed by GitHub
    Pages run `30080507753`; live `visual.html` returned HTTP 200 with zero
    hierarchy `details[open]` elements.

## Execution Log

- 2026-07-24:
  - Action: Renamed proprietary logo and favicon provenance records from
    ambiguous asset-local `README.md` names to `ASSET_PROVENANCE.md`.
  - Evidence: Root README, `LICENSING.md`, the controlling proprietary notice,
    architecture, asset records, validation, and generated validation report
    now state the separation between the repository-wide licence map,
    controlling notice, and provenance records. `rg` found zero legacy
    asset-local `README.md` references. Logo and favicon SHA-256 values remain
    `8719bf9e1b143538fb1c5d1def9fce3b4e0998ef16e403dc3c43ab2d2043cc66` and
    `310e104810f12dc633f52ca23043c7350090e2b40f2dcf400ace84aecb16793f`.
  - Validation: bundled-runtime `python -m py_compile scripts/*.py`,
    `git diff --check`, `make validate` (0 errors, 1 known sitemap warning),
    and `make scan-secrets` (0 findings) passed.
  - Deployment/public README verification: commit `a401ecd` was pushed to
    `main`. GitHub Pages run `30081615905` completed successfully. The public
    GitHub README renders one provenance-record link and one controlling-notice
    link at the expected paths; both targets load with their expected headings.
  - Result: pass.
- 2026-07-24:
  - Action: Made the public AS141253 Full hierarchy closed by default and
    completed a cautious production cleanup audit.
  - Evidence: Generated source and Pages `visual.html` each contain 78
    hierarchy disclosures and zero `open` attributes. Browser interaction
    verified normal and nested reserved disclosures open and close; expanding
    the `2 reserved /64 prefixes` group exposes
    `2400:d960:800:9::/64` and `2400:d960:800:a::/64`.
  - Validation: `make render-site`, `python -m py_compile scripts/*.py`,
    `git diff --check`, `make validate` (0 errors, 1 known sitemap warning),
    and `make scan-secrets` (0 findings) passed. Browser QA at 320, 390, 768,
    1024, 1440, 1920, and 2560 CSS px found no page-level horizontal overflow
    or console errors.
  - Cleanup: no tracked path was removed. Removed ignored local transient
    paths were moved to the macOS Trash after reference/CI/Makefile checks;
    no repository history or remote state was changed.
  - Deployment/live verification: commit `dabcbda` was pushed to `main`.
    GitHub Pages run `30080507753` completed successfully. The live
    `visual.html` returned HTTP 200 with its expected AS141253 marker and zero
    hierarchy `details[open]` elements.
  - Result: pass.
- 2026-07-15:
  - Action: Replaced the generated GitHub Pages `DS` text badge with the
    owner-provided official favicon and emitted browser favicon metadata.
  - Evidence: The byte-exact source is
    `assets/brand/01_DS_Favicon_Dark_Mode.png` (SHA-256
    `310e104810f12dc633f52ca23043c7350090e2b40f2dcf400ace84aecb16793f`).
    `render-site.py` creates the proprietary
    `docs/assets/brand/01_DS_Favicon_Dark_Mode-512.png` derivative; Pages home
    and article headers reference it, and the home, article, workbook, and
    `visual.html` pages expose a local PNG favicon link.
  - Validation: bundled-runtime `python -m py_compile scripts/*.py`, `make
    render-site`, `make validate` (0 errors, 1 known sitemap warning), `make
    scan-secrets` (0 findings), `git diff --check`, JSON parsing, image-size,
    and source-checksum checks passed. Local browser QA confirmed the image
    header mark, absence of the legacy text badge, no page-level horizontal
    overflow, and no console errors on the home, BGP article, workbook, and
    visual routes.
  - Deployment/live verification: commit `b42434e` was pushed to `main`.
    GitHub Pages run `29407999695` completed successfully. The live home and
    BGP article use the official image header mark, `visual.html` exposes the
    icon metadata, and the deployed 512 px PNG returned `200 image/png` with
    SHA-256 `c8ae2e50b88dc5252561a74821a7ba35261ae1ebdcfca86995e312ac73e18b35`.
  - Result: pass.
- 2026-07-15:
  - Action: Added the owner-provided proprietary Daryll Swer logo as the
    README header, documented its rights boundary, and linked it to the local
    `#copyright-and-licences` section.
  - Evidence: `assets/readme/13_DS_Logo_Dark_Mode_SEO.png` is byte-identical
    to the supplied original with SHA-256
    `8719bf9e1b143538fb1c5d1def9fce3b4e0998ef16e403dc3c43ab2d2043cc66`.
    `LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt` reserves all rights;
    `LICENSING.md` excludes the logo from MIT and `CC-BY-NC-SA-4.0`.
  - Validation: bundled-runtime `python -m py_compile scripts/*.py`,
    `make validate`, `make scan-secrets`, `git diff --check`, JSON parsing,
    and source/asset checksum comparison passed. Validation recorded 0 errors
    and 1 known sitemap warning; public-safety scan recorded 0 findings.
  - Result: pass.
- 2026-07-13:
  - Action: Diagnosed scheduled canonical-drift run `29229277522` and added a
    self-contained Python bootstrap plus regression validation.
  - Evidence: The run's canonical drift step completed healthy, then
    `make validate` failed with `Missing dependency: lxml. Install
    requirements.txt first.` Commit `c2b0a06` adds the bootstrap and guard.
  - Validation: `python3 -m py_compile scripts/*.py`, `git diff --check`,
    `make validate` (0 errors, 1 known sitemap warning), and
    `make scan-secrets` passed. A mocked missing `setup-python` step caused
    the new workflow guard to fail as required.
  - Deployment/hosted-runner verification: commits `c2b0a06` and `8148973`
    were pushed to `main`. Manual run `29231087908` used CPython 3.12.13,
    installed `lxml`/Pillow, completed archive validation with 0 errors and 1
    known warning, passed the public-safety scan, and found no drift-status
    changes to commit.
  - Result: pass.
- 2026-07-11:
  - Action: Retired the redundant public `cidr-hierarchy.html` route in favour
    of the existing `visual.html` hierarchy reader.
  - Evidence: Removed the retired HTML renderer, source/Pages artefacts, and
    workbook/README/visual navigation links; manifest now contains only JSON
    and DOT hierarchy exports. `make sync` refreshed 19 posts and 9 sheet
    tabs; `make render-site` regenerated Pages output.
  - Validation: `python3 -m py_compile scripts/*.py`, `git diff --check`,
    `make validate`, and `make scan-secrets` passed. Local route smoke checks
    returned 200 for visual/workbook/article and 404 for the retired route.
  - Deployment/live verification: commit `4b4e813` was pushed to `main`;
    GitHub Pages run `29147641547` succeeded. Live `visual.html`, workbook,
    and IPv6 article routes returned 200 while the retired route returned 404.
  - Result: pass.
- 2026-07-10:
  - Action: Implemented the hierarchy-only AS141253 visual-model contract and
    regenerated source and GitHub Pages output.
  - Evidence: `make sync` exported 9 sheet tabs; `make render-site` generated
    19 posts; `make validate` passed with 0 errors and 1 known sitemap warning;
    `make scan-secrets` passed with 0 findings.
  - Browser/local route QA: Chrome verified no page-level overflow at 320, 360,
    390, 430, 768, 1024, 1440, 1920, and 2560 CSS px; 28 reserved disclosure
    groups remained available; pointer and Enter-key toggles exposed and hid an
    exact reserved prefix. Local `visual.html`, workbook, and IPv6 article
    routes returned 200; the gallery and all three retired foundation routes
    returned 404.
  - Deployment/live verification: commit `f94d8b3` was pushed to `main`; GitHub
    Pages run `29081542020` succeeded. Live `visual.html`, workbook, and IPv6
    article routes returned 200; the retired gallery and all three retired
    foundation routes returned 404.
  - Result: pass.
- 2026-07-06 09:07 UTC:
  - Action: Read attached implementation prompt and inspected workspace state.
  - Evidence: `git status --short --branch` showed no commits on `main`; `git remote -v` showed no remotes.
  - Result: pass
- 2026-07-06 09:07 UTC:
  - Action: Added local archive scaffold and sync/validation/safety scripts.
  - Evidence: Files under `scripts/`, `schemas/`, `docs/`, `AGENTS.md`, `Makefile`, `ARCHITECTURE.md`, and `ESCALATION.md`.
  - Result: pending validation
- 2026-07-06 09:17 UTC:
  - Action: Ran public sync.
  - Evidence: `make sync` output reported `synced 19 posts` and `exported 9 sheet tabs`.
  - Result: pass
- 2026-07-06 09:19 UTC:
  - Action: Ran validation.
  - Evidence: `docs/VALIDATION.md`.
  - Result: pass with 0 errors and 1 warning.
- 2026-07-06 09:20 UTC:
  - Action: Ran public-safety scan and preview generation.
  - Evidence: `docs/PUBLIC_SAFETY.md` and `.preview/index.html`.
  - Result: pass
- 2026-07-06 09:30 UTC:
  - Action: Added repeatable donation/support CTA filtering, regenerated archive, validated, scanned, and refreshed preview.
  - Evidence: `scripts/sync-wordpress-posts.py`, `scripts/validate-mirror.py`, `docs/MIRRORING.md`, `AGENTS.md`, `docs/VALIDATION.md`, `docs/PUBLIC_SAFETY.md`.
  - Result: pass
- 2026-07-06 09:32 UTC:
  - Action: Applied MIT licence to scripts/tooling and updated mixed-licence documentation.
  - Evidence: `LICENSES/MIT.txt`, `LICENSING.md`, SPDX headers in `scripts/*.py` and `Makefile`.
  - Result: pass
- 2026-07-06 09:35 UTC:
  - Action: Owner selected `daryllswer.com-archive` and explicitly requested creation/push plus complete deletion of old `daryllswer.com-neteng-blog` repo.
  - Evidence: User instruction in current thread.
  - Result: in progress
- 2026-07-06 09:37 UTC:
  - Action: Created and pushed `daryll-swer/daryllswer.com-archive`.
  - Evidence: GitHub URL `https://github.com/daryll-swer/daryllswer.com-archive`; default branch `main`.
  - Result: pass
- 2026-07-06 09:37 UTC:
  - Action: Deleted `daryll-swer/daryllswer.com-neteng-blog`.
  - Evidence: `gh repo view daryll-swer/daryllswer.com-neteng-blog` returned repository-not-found after deletion.
  - Result: pass
- 2026-07-06 09:42 UTC:
  - Action: Rewrote the new archive repo's initial commit history to use GitHub no-reply commit identity.
  - Evidence: Commits now use `Daryll Swer <80836254+daryll-swer@users.noreply.github.com>`.
  - Result: pass
- 2026-07-06 09:50 UTC:
  - Action: Added site-operational sponsor/trial CTA filtering and direct source URL rewriting for same-article numbered reference markers.
  - Evidence: `scripts/sync-wordpress-posts.py`, `scripts/validate-mirror.py`, `content/posts/2025-04-22-lets-talk-about-cgnat-and-ipv6-yet-again/index.md`, `docs/MIRRORING.md`, `docs/DECISIONS.md`, `AGENTS.md`.
  - Result: pass
- 2026-07-06 09:50 UTC:
  - Action: Regenerated archive content and reran validation/public-safety checks.
  - Evidence: `docs/VALIDATION.md` reports 0 errors and 1 sitemap warning; `docs/PUBLIC_SAFETY.md` reports 0 findings.
  - Result: pass
- 2026-07-06 11:40 UTC:
  - Action: Added GitHub Pages static site generation under `docs/`.
  - Evidence: `scripts/render-site.py`, `docs/index.html`, `docs/posts/`, `docs/assets/theme.css`, `docs/sheets/`.
  - Result: pass
- 2026-07-06 11:40 UTC:
  - Action: Fixed IPv6 architecture article archive rendering issues.
  - Evidence: `content/posts/2023-04-04-ipv6-architecture-and-subnetting-guide-for-network-engineers-and-operators/index.md` has a local AS141253 sheet link and Markdown embed links; generated Pages article has `.media-embed` wrappers, local responsive figures, and a local sheet page link.
  - Result: pass
- 2026-07-06 11:40 UTC:
  - Action: Extended sync to download WordPress-uploaded media links even when they appear as text links rather than inline images.
  - Evidence: linked-media entries in post asset manifests; Pages validation no longer reports WordPress upload media links.
  - Result: pass
- 2026-07-06 11:52 UTC:
  - Action: Regenerated archive content, Pages output, validation report, and public-safety report.
  - Evidence: `docs/VALIDATION.md` reports 0 errors and 1 known sitemap warning; `docs/PUBLIC_SAFETY.md` reports 0 findings.
  - Result: pass
- 2026-07-06 11:54 UTC:
  - Action: Performed local browser QA against the generated GitHub Pages site.
  - Evidence: Desktop and 390x844 mobile checks confirmed 19 index cards, local AS141253 sheet link, 2 media embed wrappers, no raw iframe text, no horizontal overflow, responsive IPv6 figures, and 9 sheet CSV links plus the ODS artefact.
  - Result: pass
- 2026-07-06 12:03 UTC:
  - Action: Added clickable sheet README artefact links and normalised generated text artefacts for stable Git diffs.
  - Evidence: `data/sheets/as141253-ipv6-architecture-example/README.md`, `scripts/export-google-sheet.py`, `scripts/render-site.py`, and `.gitattributes`.
  - Result: pass
- 2026-07-06 12:06 UTC:
  - Action: Pushed generated Pages site and enabled GitHub Pages from `main` `/docs`.
  - Evidence: GitHub Pages API reported `status: built`, source `main` `/docs`, and `curl -I https://daryll-swer.github.io/daryllswer.com-archive/` returned HTTP 200.
  - Result: pass
- 2026-07-08 07:23 UTC:
  - Action: Fixed readability failures in the three selected AS141253 visual foundations.
  - Evidence: Branch cards and collapsible dendrogram now render CSV notes; purpose cluster graph carries notes in graph data/detail panel and emits no per-node SVG labels.
  - Result: pass; local Chrome/Playwright DOM QA, `make render-site`, `python3 -m py_compile scripts/*.py`, `git diff --check`, `make validate`, and `make scan-secrets` passed.
- 2026-07-08 07:44 UTC:
  - Action: Replaced inert branch-card `+N more` labels with native expandable disclosures and hardened responsive CSS for all selected AS141253 visual foundations.
  - Evidence: Generated branch-card pages contain `details.branch-more` controls; local Chrome/Playwright responsive QA passed 28 page/viewport combinations at 320, 390, 768, 1024, 1440, 1920, and 2560 px widths with 0 failures.
  - Result: pass; local responsive QA, `make render-site`, `python3 -m py_compile scripts/*.py`, `git diff --check`, `make validate`, and `make scan-secrets` passed.
- 2026-07-08 17:21 UTC:
  - Action: Checked the visual foundations against the expanded industry-aligned responsive matrix and fixed the only failure.
  - Evidence: First expanded run failed only at 360 px with `364/360` page overflow on all four visual pages; layout inspection traced this to the metrics grid. After the metrics CSS fix, the rerun passed 160 page/viewport combinations with 0 failures.
  - Result: pass; expanded responsive QA, `make render-site`, `python3 -m py_compile scripts/*.py`, `git diff --check`, `make validate`, and `make scan-secrets` passed.
- 2026-07-08 17:29 UTC:
  - Action: Pushed and live-verified the expanded responsive-matrix fix.
  - Evidence: Commit `d7bade5` was pushed to `main`; Pages deployment run `28962375073` succeeded; live static checks found the deployed metrics CSS fix, branch disclosures, and no graph node labels; live Chrome/Playwright checks passed 20 page/viewport combinations at 360, 390, 768, 1440, and 1920 px with 0 failures.
  - Result: pass; deployed GitHub Pages output now matches the local expanded responsive fix.
- 2026-07-08 18:13 UTC:
  - Action: Implemented and locally verified the primary AS141253 `visual.html` model.
  - Evidence: `make sync`, `make render-site`, `python3 -m py_compile scripts/*.py`, `git diff --check`, `make validate`, and `make scan-secrets` passed. Local Chrome/Playwright QA passed for `visual.html` at 320, 360, 390, 430, 768, 1024, 1440, 1920, and 2560 px widths; workbook and `visual-options.html` smoke checks passed at 390 px.
  - Result: pass locally; commit/push/live Pages verification pending.
- 2026-07-06 12:45 UTC:
  - Action: Implemented README command move, WordPress media filename/byte preservation, and CSV-backed AS141253 workbook generation.
  - Evidence: `README.md`, `AGENTS.md`, `docs/MIRRORING.md`, `scripts/sync-wordpress-posts.py`, `scripts/sheet_workbook.py`, `scripts/export-google-sheet.py`, `scripts/render-site.py`, `scripts/validate-mirror.py`, schemas, regenerated content/docs output.
  - Result: pending final validation and browser QA
- 2026-07-06 12:51 UTC:
  - Action: Regenerated archive/site output, validated, public-safety scanned, and browser-checked the update locally.
  - Evidence: `make sync render-site validate scan-secrets PYTHON=<bundled-python>` passed with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings; browser QA confirmed 19 index cards, local IPv6 sheet link, 2 media embed wrappers, 9 workbook tabs, tab switching, no broken images, and no page-level horizontal overflow on desktop/mobile-sized viewports.
  - Result: pass locally
- 2026-07-06 12:54 UTC:
  - Action: Pushed commit `982244a` and verified GitHub Pages rebuilt from `main` `/docs`.
  - Evidence: GitHub Pages API reported `built`; live homepage, IPv6 article, AS141253 workbook, ODS artefact, and `Scaffold_FT.png` returned HTTP 200. Live workbook had 9 tabs/9 panels, live homepage had 19 post cards, and live article had 2 embed wrappers plus the local sheet link.
  - Result: pass
- 2026-07-06 13:34 UTC:
  - Action: Implemented clean GitHub Pages root URL navigation/canonical handling.
  - Evidence: `scripts/render-site.py`, `scripts/validate-mirror.py`, `ARCHITECTURE.md`, `docs/MIRRORING.md`, and `docs/DECISIONS.md`.
  - Result: pending regeneration and verification
- 2026-07-06 13:39 UTC:
  - Action: Regenerated Pages output and browser-checked clean root navigation locally.
  - Evidence: `make render-site validate scan-secrets PYTHON=<bundled-python>` passed with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings. Browser click QA confirmed homepage Index `./`, article Index `../../`, workbook Archive index `../../`, and all clicked routes resolved to `/` without `index.html`. Final `py_compile`, `make validate scan-secrets`, `git diff --check`, and generated HTML regression search also passed.
  - Result: pass locally
- 2026-07-06 13:48 UTC:
  - Action: Pushed clean-root-link update and verified live Pages output.
  - Evidence: Commit `822f47c` contained the generator/output update. Its first Pages deployment failed at `actions/deploy-pages@v5` with `Deployment failed, try again later`; empty commit `46ec8cc` retriggered the same content deployment successfully. Live root/article/workbook checks returned HTTP 200 with clean `./` and `../../` links and no visible root `index.html` links.
  - Result: pass
- 2026-07-06 17:49 UTC:
  - Action: Target-refreshed the three requested posts from canonical WordPress.
  - Evidence: WordPress REST showed modified timestamps on 2026-07-06 and featured URLs `Shortcomings_CGNAT_FT-scaled.jpg` / `Multi_WAN_FT-scaled.jpg`; local manifests preserve filenames and bytes.
  - Result: pass locally
- 2026-07-06 17:53 UTC:
  - Action: Added canonical drift automation and initial drift report.
  - Evidence: `.github/workflows/canonical-drift.yml`, `scripts/check-canonical-drift.py`, `archive-status.json`, `docs/CANONICAL_DRIFT.md`.
  - Result: pass locally; one non-target drift item reported.
- 2026-07-06 17:59 UTC:
  - Action: Added AS141253 IPv6 prefix hierarchy proof of concept.
  - Evidence: `data/sheets/as141253-ipv6-architecture-example/cidr-hierarchy.html`, `.json`, `.dot`; manifest reports 153 nodes and max depth 5.
  - Result: pass locally
- 2026-07-06 18:01 UTC:
  - Action: Regenerated sheet artefacts, GitHub Pages output, validation report, and public-safety report.
  - Evidence: `make validate scan-secrets PYTHON=<bundled-python>` reported 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - Result: pass locally
- 2026-07-06 18:04 UTC:
  - Action: Browser-checked local generated Pages output.
  - Evidence: Homepage 19 cards/no overflow; target article featured images present; lazy inline images loaded after scroll; workbook linked CIDR hierarchy; hierarchy page had 153 nodes; mobile viewport checks had no page overflow.
  - Result: pass locally
- 2026-07-06 18:09 UTC:
  - Action: Committed and pushed `6b00f09`, then verified live GitHub Pages output.
  - Evidence: pages-build-deployment completed successfully. Live root showed updated featured image filenames; target article pages, image assets, AS141253 workbook, hierarchy HTML, JSON, and DOT routes returned HTTP 200.
  - Result: pass
- 2026-07-06 18:15 UTC:
  - Action: Hardened the canonical drift checker User-Agent, reset drift state to healthy, pushed `d20085f`, and reran the manual GitHub Actions workflow.
  - Evidence: Manual `Canonical drift check` run `28813242318` completed successfully on `d20085f`; `git fetch origin main` showed local `main` still synced with `origin/main`, so the workflow did not create another state commit.
  - Result: pass
- 2026-07-07 10:57 UTC:
  - Action: Implemented canonical typography, self-hosted font assets, internal
    post-link localisation, WordPress section-anchor aliases, and validation
    guards.
  - Evidence: `make sync render-site PYTHON=<bundled-python>` regenerated 19
    posts and 9 sheet tabs; the BGP Router ID article now links to the local
    OOB article with `#dns-and-loopback-addressing`; the OOB generated article
    contains both `h-dns-and-loopback-addressing` and
    `dns-and-loopback-addressing`.
  - Result: pass locally; browser QA and live verification pending.
- 2026-07-07 10:57 UTC:
  - Action: Ran validation and public-safety scan after regeneration.
  - Evidence: `make validate scan-secrets PYTHON=<bundled-python>` reported 0
    validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - Result: pass locally.
- 2026-07-07 11:15 UTC:
  - Action: Ran local browser/static QA for the typography/link-anchor update.
  - Evidence: Chrome DevTools Protocol mobile emulation reported
    `innerWidth=390`, `clientWidth=390`, `scrollWidth=390`,
    `bodyFontFamily=Poppins`, and `h1FontFamily=Raleway`; static QA confirmed
    19 home cards, 14 copied theme font files, the BGP OOB link as
    `../out-of-band-network-design-for-service-provider-networks/#dns-and-loopback-addressing`,
    both OOB target anchors, 9 workbook tabs, CIDR hierarchy markup, and
    non-blank screenshots.
  - Result: pass locally; final validation gates, push, and live verification
    pending.
- 2026-07-07 11:18 UTC:
  - Action: Reran sync/render after Markdown trailing-whitespace
    normalisation, then ran final local gates and post-regeneration sanity QA.
  - Evidence: `git diff --check`, `python3 -m py_compile scripts/*.py`, and
    `make validate scan-secrets PYTHON=<bundled-python>` passed. Focused QA
    reconfirmed the theme font files, 19 home cards, BGP -> OOB local anchor,
    OOB alias anchors, 9 workbook tabs, CIDR hierarchy markup, and 390 px CDP
    mobile overflow metrics.
  - Result: pass locally; push and live verification pending.
- 2026-07-07 11:21 UTC:
  - Action: Committed, pushed, waited for GitHub Pages, and verified live
    public routes/assets.
  - Evidence: Commit `44a2a8c` pushed to `main`; Pages deployment run
    `28862244073` completed successfully for head SHA
    `44a2a8cfe77ef3ec987e058ecbaf4e1fe283df44`. Live checks returned HTTP
    200 for the home page, theme CSS, `Poppins-Regular-latin.woff2`, BGP
    article, OOB article, AS141253 workbook, and CIDR hierarchy page; live
    HTML checks confirmed 19 home cards, local BGP -> OOB anchor, OOB
    WordPress and alias anchors, 9 workbook tabs, and hierarchy markup.
  - Result: pass.
- 2026-07-07 15:25 UTC:
  - Action: Implemented heading permalink/copy controls, explicit home font
    selectors, and third-party document drift exclusion; regenerated Pages and
    drift report.
  - Evidence: BGP generated article has `Introduction` as
    `href="#introduction"` plus visible `#` and `Copy` controls; drift report
    now reports `Changed archived posts: 0`; CDP browser QA confirmed home
    `Poppins`/`Raleway` computed fonts, no 390 px overflow, heading click
    updated `location.hash` to `#introduction`, and the copy button wrote the
    full section URL.
  - Result: pass locally; push/live verification pending.
- 2026-07-07 15:28 UTC:
  - Action: Pushed heading permalink/drift update, waited for GitHub Pages, and
    verified live public output.
  - Evidence: Commit `62cdc70` pushed to `main`; Pages deployment run
    `28878086332` completed successfully for head SHA
    `62cdc700230230b7b50f9acf5f4335102e8d9e8f`. Live static checks returned
    HTTP 200 for the home page, theme CSS, generated `archive.js`, BGP article,
    and drift report. Live CDP browser QA confirmed home `Poppins`/`Raleway`
    computed fonts, no 390 px overflow, `Introduction` click updating
    `#introduction`, and the `Copy` button writing the live section URL.
  - Result: pass.
- 2026-07-07 15:40 UTC:
  - Action: Audited canonical/local WordPress inline colour classes, added
    WordPress preset palette CSS, regenerated Pages output, and ran local
    rendered-style QA.
  - Evidence: Fresh WordPress REST audit found only
    `bgp-router-id-structuring-in-ipv6-native-networks` currently uses inline
    colour classes: `has-inline-color`, `has-luminous-vivid-amber-color`,
    `has-vivid-red-color`, and `has-luminous-vivid-orange-color`. Canonical
    CSS maps those presets to `#fcb900`, `#cf2e2e`, and `#ff6900`. Local
    browser computed styles confirmed A `rgb(252, 185, 0)`, B
    `rgb(207, 46, 46)`, C/D `rgb(255, 105, 0)`, and transparent backgrounds.
  - Result: pass locally; push/live verification pending.
- 2026-07-07 15:43 UTC:
  - Action: Pushed WordPress inline-colour update, waited for GitHub Pages, and
    verified live public rendering.
  - Evidence: Commit `eb06a74` pushed to `main`; Pages deployment run
    `28879142430` completed successfully for head SHA
    `eb06a741ee74386d09da3d07cf9d2d9039526834`. Live static checks returned
    HTTP 200 and found WordPress palette CSS plus BGP article colour classes.
    Live browser computed styles confirmed A `rgb(252, 185, 0)`, B
    `rgb(207, 46, 46)`, C/D `rgb(255, 105, 0)`, and transparent backgrounds.
  - Result: pass.
- 2026-07-07 15:55 UTC:
  - Action: Started AS141253 visual-options workstream and inspected existing
    CSV/hierarchy inputs.
  - Evidence: Existing sheet artefacts contain 9 CSV tabs and the hierarchy
    manifest reports 153 prefix nodes and max depth 5.
  - Result: prototype generation pending.
- 2026-07-07 16:49 UTC:
  - Action: Added generated AS141253 visual-option pages and responsive
    containment for wide diagrams.
  - Evidence: `scripts/ipv6_visual_options.py` generates
    `visual-options.html` plus five standalone `visual-option-*.html` pages;
    `scripts/export-google-sheet.py`, `scripts/sheet_workbook.py`,
    `scripts/render-site.py`, and `scripts/validate-mirror.py` integrate and
    validate the artefacts.
  - Result: pass locally.
- 2026-07-07 16:49 UTC:
  - Action: Regenerated sheet and Pages artefacts, validated, scanned, and
    browser-checked the prototype gallery.
  - Evidence: `python3 -m py_compile scripts/*.py`, `git diff --check`,
    `make render-site PYTHON=<bundled-python>`,
    `make validate PYTHON=<bundled-python>`, and
    `make scan-secrets PYTHON=<bundled-python>` passed. Local browser QA
    checked the gallery and five standalone pages at desktop/default and
    390 px mobile widths with page-level `scrollWidth` equal to viewport
    width; wide diagrams scroll within `.visual-frame` containers.
  - Result: pass locally.
- 2026-07-07 16:53 UTC:
  - Action: Pushed the AS141253 visual-option pages and verified live GitHub
    Pages output.
  - Evidence: Commit `43ce2ac` pushed to `main`; Pages deployment run
    `28883547390` completed successfully. Live HTTP checks returned 200 for
    `visual-options.html` and all five `visual-option-*.html` pages. Live
    browser QA confirmed the gallery rendered five option sections and 996
    prefix chips, with page-level `scrollWidth` equal to viewport width at
    desktop/default and 390 px mobile widths.
  - Result: pass.
- 2026-07-07 21:39 UTC:
  - Action: Added six additional interactive AS141253 visual candidates and
    regenerated source/Pages artefacts.
  - Evidence: `scripts/ipv6_visual_options.py` now generates eleven options;
    `data/sheets/as141253-ipv6-architecture-example/manifest.json` reports
    `visual_options.option_count = 11`.
  - Result: pass locally.
- 2026-07-07 21:39 UTC:
  - Action: Validated, scanned, and browser-checked the expanded gallery.
  - Evidence: `python3 -m py_compile scripts/*.py`, `git diff --check`,
    `make render-site PYTHON=<bundled-python>`,
    `make validate PYTHON=<bundled-python>`, and
    `make scan-secrets PYTHON=<bundled-python>` passed. Local browser QA
    checked the gallery and eleven standalone pages at desktop/default and
    390 px mobile widths with page-level `scrollWidth` equal to viewport
    width and no console errors. Representative interactions passed for graph
    node clicks, sunburst arc clicks, purpose-cluster node clicks, dendrogram
    expand/collapse, walkthrough next-step, and searchable focus.
  - Result: pass locally.
- 2026-07-07 21:43 UTC:
  - Action: Pushed the expanded AS141253 visual-option gallery and verified
    live GitHub Pages output.
  - Evidence: Commit `bce0d98` pushed to `main`; Pages deployment run
    `28900695345` completed successfully. Live HTTP checks returned 200 for
    `visual-options.html` and all six new `visual-option-*.html` pages. Live
    browser QA confirmed eleven option cards/sections, graph nodes, active
    walkthrough state, searchable focus results, and page-level `scrollWidth`
    equal to viewport width at desktop/default and 390 px mobile widths.
  - Result: pass.

## Tests and Verification

- Required checks:
  - `make sync`: passed.
  - `make validate`: passed with one non-blocking warning.
  - `make scan-secrets`: passed.
  - `make render-preview`: passed.
  - `make render-site`: passed.
- Last run:
  - `make sync validate scan-secrets render-preview`: pass at 2026-07-06 09:29 UTC.
  - Direct `rg` check for excluded donation CTA/donation URL in generated article files: no matches at 2026-07-06 09:29 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-06 09:49 UTC.
  - `rg -n "https://www\\.daryllswer\\.com/[^)\\s]+/#(?:h-)?references|#h-references|This article was sponsored|FastNetMon|free 30-day" content/posts -g 'index.md'`: no matches at 2026-07-06 09:50 UTC.
  - `make sync render-site validate PYTHON=<bundled-python>`: pass at 2026-07-06 11:35 UTC with 0 errors and 1 known sitemap warning.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-06 12:00 UTC.
  - `make sync render-site validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-06 12:03 UTC with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-06 12:00 UTC with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - `git diff --check`: pass at 2026-07-06 12:04 UTC.
  - Local browser QA against `http://127.0.0.1:4173/`: pass at 2026-07-06 11:54 UTC for desktop and 390x844 mobile.
  - `make sync render-site validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-06 12:51 UTC with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-06 12:55 UTC after recording live Pages verification, with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - Media filename preservation check: pass at 2026-07-06 12:52 UTC; 68 WordPress media assets, 19 featured assets, 0 filename-preservation failures.
  - Workbook structure check: pass at 2026-07-06 12:52 UTC; 9 tabs/labels/panels in source and Pages workbook HTML.
  - Local browser QA against `http://127.0.0.1:4173/`: pass at 2026-07-06 12:51 UTC for desktop and mobile-sized viewport.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-06 12:51 UTC.
  - `git diff --check`: pass at 2026-07-06 12:51 UTC.
  - GitHub Pages API and live route checks: pass at 2026-07-06 12:54 UTC.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-06 18:01 UTC.
  - `git diff --check`: pass at 2026-07-06 18:01 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-06 18:01 UTC with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - Local browser QA against `http://127.0.0.1:4173/`: pass at 2026-07-06 18:04 UTC for desktop/default and 390x844 mobile viewport.
  - GitHub Pages deployment for `6b00f09`: pass at 2026-07-06 18:08 UTC.
  - Live route checks: pass at 2026-07-06 18:09 UTC for refreshed articles/images and AS141253 workbook/hierarchy artefacts.
  - GitHub Pages deployment for `d20085f`: pass at 2026-07-06 18:14 UTC.
  - Manual `Canonical drift check` workflow for `d20085f`: pass at 2026-07-06 18:15 UTC.
  - Final live route checks: pass at 2026-07-06 18:15 UTC for refreshed featured-image assets and AS141253 hierarchy page.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-07 10:57 UTC with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - Local browser/static QA against `http://127.0.0.1:4173/`: pass at 2026-07-07 11:15 UTC for typography, BGP/OOB local anchor link, workbook tabs, CIDR hierarchy, non-blank screenshots, and 390 px mobile overflow.
  - `git diff --check`: pass at 2026-07-07 11:18 UTC.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-07 11:18 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-07 11:18 UTC with 0 validation errors, 1 known sitemap warning, and 0 public-safety findings.
  - Post-regeneration static/CDP QA: pass at 2026-07-07 11:18 UTC.
  - GitHub Pages deployment for `44a2a8c`: pass at 2026-07-07 11:20 UTC.
  - Live route/asset checks: pass at 2026-07-07 11:21 UTC for homepage,
    theme CSS, Poppins WOFF2, BGP/OOB anchor link, AS141253 workbook, and CIDR
    hierarchy page.
  - `git diff --check`: pass at 2026-07-07 15:23 UTC.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-07 15:23 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-07
    15:23 UTC with 0 validation errors, 1 known sitemap warning, and 0
    public-safety findings.
  - Local CDP browser QA against `http://127.0.0.1:4173/`: pass at
    2026-07-07 15:25 UTC for home fonts, heading permalink click, copy button,
    and 390 px mobile overflow.
  - GitHub Pages deployment for `62cdc70`: pass at 2026-07-07 15:27 UTC.
  - Live static checks: pass at 2026-07-07 15:27 UTC for home page, generated
    CSS/JS, BGP article, and clean drift report.
  - Live CDP browser QA: pass at 2026-07-07 15:28 UTC for home fonts, BGP
    heading click/copy behaviour, and 390 px mobile overflow.
  - Fresh WordPress REST inline-colour audit: pass at 2026-07-07 15:35 UTC;
    only BGP Router ID currently uses WordPress inline colour classes.
  - `make render-site PYTHON=<bundled-python>`: pass at 2026-07-07 15:38 UTC.
  - `make validate scan-secrets PYTHON=<bundled-python>`: pass at
    2026-07-07 15:39 UTC with 0 validation errors, 1 known sitemap warning,
    and 0 public-safety findings.
  - Local browser computed-style QA against `http://127.0.0.1:4173/`: pass at
    2026-07-07 15:40 UTC for BGP Router ID WordPress colour marks.
  - GitHub Pages deployment for `eb06a74`: pass at 2026-07-07 15:43 UTC.
  - Live static checks: pass at 2026-07-07 15:43 UTC for generated theme CSS
    WordPress palette markers and BGP article colour classes.
  - Live browser computed-style QA: pass at 2026-07-07 15:43 UTC for BGP
    Router ID WordPress colour marks.
  - AS141253 visual pruning: local implementation at 2026-07-08 06:32 UTC
    removed the eight discarded visual models from generator output, source
    `data/` artefacts, and generated `docs/` artefacts. Kept foundations are
    branch cards, collapsible dendrogram, and purpose cluster graph.
  - Public Google Sheet export attempt: failed at 2026-07-08 06:32 UTC with a
    `TimeoutError` while reading a public Google Sheet HTML tab. The ODS/HTML
    snapshot churn was restored, and local-only CSV-derived visual/workbook
    regeneration was used because canonical sheet data did not need refreshing
    for this pruning step.
  - `make render-site PYTHON=<bundled-python>`: pass at 2026-07-08 06:32 UTC
    after local-only visual artefact regeneration.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-08 06:37 UTC.
  - `git diff --check`: pass at 2026-07-08 06:37 UTC.
  - `make validate PYTHON=<bundled-python>`: pass at 2026-07-08 06:37 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-08
    06:37 UTC with 0 public-safety findings.
  - Local browser QA against `http://127.0.0.1:4173/`: pass at 2026-07-08
    06:37 UTC for the pruned visual-foundations gallery and three standalone
    pages at desktop/default and 390 px mobile widths. The gallery rendered
    three cards/sections, discarded model titles were absent, page
    `scrollWidth` equalled viewport width, browser console errors were empty,
    dendrogram expand/collapse worked, and purpose-cluster node selection
    updated the detail panel.
  - Local removed-page check: pass at 2026-07-08 06:37 UTC; all eight
    discarded standalone visual-option routes returned HTTP 404 from the local
    `docs/` server.
  - GitHub Pages deployment for `67e3ae5`: pass at 2026-07-08 06:40 UTC;
    pages-build-deployment run `28922937285` completed successfully.
  - Live route checks: pass at 2026-07-08 06:41 UTC for `visual-options.html`,
    the three selected standalone option pages, and the eight discarded
    standalone option routes. The selected routes returned HTTP 200 with
    expected markers; discarded routes returned HTTP 404.
  - Live browser QA: pass at 2026-07-08 06:41 UTC for the visual-foundations
    gallery at desktop/default width; three option cards/sections rendered,
    discarded model titles were absent, page-level `scrollWidth` equalled
    viewport width, and browser console errors were empty.
  - AS141253 visual-foundation polish: local implementation at 2026-07-08
    07:23 UTC added CSV note rendering to branch cards and collapsible
    dendrogram, bounded branch-card chip/card wrapping, and overlap-safe
    purpose-cluster detail-panel selection.
  - Local Chrome/Playwright DOM QA against `http://127.0.0.1:4173/`: pass at
    2026-07-08 07:22 UTC. Branch cards at 390 px had `scrollWidth=390`, 53
    rendered child notes, and no page overflow. Collapsible dendrogram at
    390 px had `scrollWidth=390`, 90 rendered tree notes, and no page
    overflow. Purpose cluster graph at 1280 px had 0 graph node labels, 9
    purpose labels, no detected graph text overlaps, and notes appeared in
    the detail panel after selecting `2400:d960:804::/56`.
  - `make render-site PYTHON=<bundled-python>`: pass at 2026-07-08 07:26 UTC;
    generated 19 posts and refreshed sheet/Pages output.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-08 07:24 UTC.
  - `git diff --check`: pass at 2026-07-08 07:26 UTC.
  - `make validate PYTHON=<bundled-python>`: pass at 2026-07-08 07:26 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-08
    07:26 UTC with 0 public-safety findings.
  - GitHub Pages deployment for `5f8699e`: pass at 2026-07-08 07:29 UTC;
    pages-build-deployment run `28925442002` completed successfully.
  - Live static checks: pass at 2026-07-08 07:30 UTC for
    `visual-option-branch-cards.html`,
    `visual-option-collapsible-dendrogram.html`,
    `visual-option-purpose-cluster-graph.html`, and `visual-options.html`.
    All returned HTTP 200 with required note markers and 0
    `graph-node-label` occurrences.
  - Live Chrome/Playwright DOM QA against GitHub Pages: pass at
    2026-07-08 07:30 UTC. Branch cards at 390 px had `scrollWidth=390`, 53
    rendered child notes, and no page overflow. Collapsible dendrogram at
    390 px had `scrollWidth=390`, 90 rendered tree notes, and no page
    overflow. Purpose cluster graph at 1280 px had 0 graph node labels, 9
    purpose labels, no detected graph text overlaps, and notes appeared in
    the detail panel after selecting `2400:d960:804::/56`.
  - AS141253 branch disclosure and responsive hardening: local implementation
    at 2026-07-08 07:44 UTC replaced inert `+N more` labels with native
    `details`/`summary` disclosures and added responsive CSS hardening for all
    selected foundations.
  - Local Chrome/Playwright responsive QA against `http://127.0.0.1:4173/`:
    pass at 2026-07-08 07:42 UTC across 28 page/viewport combinations:
    standalone branch cards, collapsible dendrogram, purpose cluster graph,
    and gallery pages at 320, 390, 768, 1024, 1440, 1920, and 2560 px widths.
    Failures: 0. All combinations had no page-level horizontal overflow,
    graph node labels remained 0, graph text overlaps were 0, and branch-card
    disclosures toggled open/closed in every viewport.
  - `make render-site PYTHON=<bundled-python>`: pass at 2026-07-08 07:46 UTC;
    generated 19 posts and refreshed generated Pages output.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-08 07:46 UTC.
  - `git diff --check`: pass at 2026-07-08 07:46 UTC.
  - `make validate PYTHON=<bundled-python>`: pass at 2026-07-08 07:47 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-08
    07:46 UTC with 0 public-safety findings.
  - GitHub Pages deployment for `32fad32`: pass at 2026-07-08 07:48 UTC;
    pages-build-deployment run `28926454066` completed successfully.
  - Live static checks: pass at 2026-07-08 07:48 UTC for
    `visual-option-branch-cards.html`,
    `visual-option-collapsible-dendrogram.html`,
    `visual-option-purpose-cluster-graph.html`, and `visual-options.html`.
    Required branch disclosure/responsive markers were present, branch-card
    pages had 3 `details.branch-more` controls, and graph node labels remained
    0.
  - Live Chrome/Playwright DOM QA against GitHub Pages: pass at
    2026-07-08 07:49 UTC at 390 px and 1440 px widths. All four visual pages
    had no page-level horizontal overflow, graph text overlaps were 0, and the
    branch-card disclosure opened with the `Show fewer` state.
  - Local expanded Chrome/Playwright responsive QA against
    `http://127.0.0.1:4173/`: first run at 2026-07-08 17:16 UTC failed only
    at 360 px with page overflow `364/360` on all four visual pages. Root
    cause was the shared metrics grid root-prefix card. After the metrics CSS
    fix, the rerun passed at 2026-07-08 17:20 UTC across 160 combinations:
    four visual pages by 40 CSS-pixel widths. Failures: 0.
  - GitHub Pages deployment for `d7bade5`: pass at 2026-07-08 17:26 UTC;
    pages-build-deployment run `28962375073` completed successfully.
  - Live static checks: pass at 2026-07-08 17:27 UTC for
    `visual-option-branch-cards.html`,
    `visual-option-collapsible-dendrogram.html`,
    `visual-option-purpose-cluster-graph.html`, and `visual-options.html`.
    The deployed CSS included the metrics grid/wrapping fix, branch-card pages
    had `details.branch-more` controls, and graph node labels remained 0.
  - Live Chrome/Playwright DOM QA against GitHub Pages: pass at
    2026-07-08 17:28 UTC at 360, 390, 768, 1440, and 1920 px widths. All four
    visual pages had no page-level horizontal overflow, branch-card disclosure
    controls opened/closed, graph node labels stayed absent after click
    interactions, and SVG text overlaps were 0.
  - `make render-site PYTHON=<bundled-python>`: pass at 2026-07-08 17:22 UTC;
    generated 19 posts and refreshed generated Pages output.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-08 17:22 UTC.
  - `git diff --check`: pass at 2026-07-08 17:22 UTC.
  - `make validate PYTHON=<bundled-python>`: pass at 2026-07-08 17:23 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-08
    17:22 UTC with 0 public-safety findings.
  - `make sync PYTHON=<bundled-python>`: pass at 2026-07-08 18:01 UTC;
    synced 19 posts and exported 9 sheet tabs.
  - `make render-site PYTHON=<bundled-python>`: pass at 2026-07-08 18:02 UTC;
    generated 19 posts and refreshed generated Pages output.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-08 18:05 UTC.
  - `git diff --check`: pass at 2026-07-08 18:05 UTC.
  - `make validate PYTHON=<bundled-python>`: pass at 2026-07-08 18:05 UTC
    with 0 validation errors and 1 known sitemap warning.
  - `make scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-08 18:05 UTC
    with 0 public-safety findings.
  - Local Chrome/Playwright QA against `http://127.0.0.1:4173/`: pass at
    2026-07-08 18:13 UTC for `visual.html` at 320, 360, 390, 430, 768, 1024,
    1440, 1920, and 2560 px widths. Failures: 0. Checks covered page-level
    overflow, expected sections, absence of JS on `visual.html`, reserved
    disclosure open/close, SVG minimap anchor targets/clicks, and 390 px smoke
    checks for `visual-options.html` and the workbook.
  - Anchor-fix local Chrome DevTools Protocol QA against
    `http://127.0.0.1:4173/`: pass at 2026-07-08 18:23 UTC for `visual.html`
    at 320, 360, 390, 430, 768, 1024, 1440, 1920, and 2560 px widths.
    Failures: 0. This rerun verified stable final section anchors, reserved
    disclosure opening, and SVG minimap anchor clicks.
  - `python3 -m py_compile scripts/*.py`: pass at 2026-07-08 18:23 UTC.
  - `git diff --check`: pass at 2026-07-08 18:23 UTC.
  - `make validate PYTHON=<bundled-python>`: pass at 2026-07-08 18:23 UTC
    with 0 validation errors and 1 known sitemap warning. Validation now
    requires final `visual.html` section anchors.
  - `make scan-secrets PYTHON=<bundled-python>`: pass at 2026-07-08 18:23 UTC
    with 0 public-safety findings.
  - GitHub Pages deployment for `5152975`: pass at 2026-07-08 18:24 UTC;
    pages-build-deployment run `28965936383` completed successfully.
  - Live static checks: pass at 2026-07-08 18:25 UTC for `visual.html`, the
    AS141253 workbook route, and the IPv6 article route. All returned HTTP
    200; `visual.html` had the expected section markers and no script tag or
    source font path leakage.
  - Live Chrome DevTools Protocol QA against GitHub Pages: pass at
    2026-07-08 18:25 UTC for `visual.html` at 320, 390, 768, 1440, and 2560
    px widths. Failures: 0. Checks covered page-level overflow, final section
    anchors, 57 reserved disclosure groups, reserved disclosure opening, and
    SVG minimap anchor targets/clicks.
- Not run:
  - None for the final AS141253 `visual.html` implementation.

## Next Pickup

- Next action:
  - No implementation pickup is pending for the workflow remediation.
- Current blocker:
  - None.
- Budget/rate blocker:
  - None observed.
- Verification gap:
  - The known non-blocking sitemap warning remains; workflow remediation has
    no open verification gap.

## Completion Criteria

- Done means:
  - Local repo contains scripts, mirrored published content, featured images, spreadsheet artefacts, generated GitHub Pages site, schemas, manifests, docs, validation results, and a public-safety scan result.
- Remaining:
  - None for the final AS141253 `visual.html` implementation.
  - Optional follow-up: decide whether to replace the old canonical Google
    Sheet link on daryllswer.com with the new GitHub Pages `visual.html`.
  - Optional follow-up: decide whether the remaining non-archived canonical
    links to `/contact/`, `/as149794/`, and `/geofeed/` should stay outbound,
    be manually edited, or be represented by archive landing pages.
