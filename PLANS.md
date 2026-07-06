# daryllswer.com Archive Plan

## Context and Orientation

- Workspace / project: `daryllswer.com-related-work`
- Thread/workspace id: current Codex Desktop thread
- Source of truth: repository root
- Execution surface: macOS Codex Desktop
- Status: publishing to GitHub; old repo deletion explicitly approved by owner
- Created: 2026-07-06 09:07 UTC
- Last updated: 2026-07-06 09:35 UTC
- Working assumptions: the WordPress site is canonical; this repo is a public mirror/archive of only published public content.
- `forked_from`: N/A

## Durable Project Documents

- Architecture: `ARCHITECTURE.md`
- ADR directory: N/A for now
- Implementation status: `IMPLEMENTATION_STATUS.md`
- Escalation rules: `ESCALATION.md`

## Current Status / Next Pickup

- Current state:
  - Complete locally: scaffold, public sync, donation/support CTA filtering, spreadsheet export, validation, public-safety scan, and local preview generation finished.
- Last material update:
  - 2026-07-06 09:35 UTC Owner selected `daryllswer.com-archive` and approved creation/push plus deletion of old repo.
- Next pickup action:
  - Commit locally, create/push `daryll-swer/daryllswer.com-archive`, then delete `daryll-swer/daryllswer.com-neteng-blog`.
- Open blockers or risks:
  - Remote GitHub destructive deletion has explicit user confirmation for `daryll-swer/daryllswer.com-neteng-blog` only.
  - WordPress REST has one post not listed in `post-sitemap.xml`.
- Verification gap:
  - Browser visual QA was not performed beyond generated preview creation.

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

## Validation and Acceptance

- Reproducible checks:
  - `make sync`: passed; fetched public posts, media, and spreadsheet artefacts.
  - `make validate`: passed at 2026-07-06 09:29 UTC; validation recorded 0 errors and 1 warning.
  - `make scan-secrets`: passed at 2026-07-06 09:29 UTC; public-safety scan recorded 0 findings.
  - `make render-preview`: passed; generated `.preview/index.html`.
  - `rg -n "It would be appreciated|Click here to donate|https://www\\.daryllswer\\.com/donation/?" content/posts -g 'index.md' -g 'source/rendered-article.html' -g 'source/wordpress-post.json' -g 'source/canonical-page.html'`: no matches.
- Evidence paths:
  - `docs/VALIDATION.md`
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
  - Local repo scaffold, public sync, donation/support CTA filtering, spreadsheet export, validation, public-safety scan, and preview generation completed.
- Remaining:
  - Owner review and remote GitHub repo decision.
- Retrospective timestamp:
  - 2026-07-06 09:20 UTC
