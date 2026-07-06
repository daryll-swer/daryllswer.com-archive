# Repository Instructions for Codex

## Source of Truth

- daryllswer.com is canonical. This repository is a public mirror/archive.
- Use public WordPress REST API, sitemap/RSS, canonical HTML, and public export
  URLs first.
- Do not use private WordPress admin exports, database access, SSH backend
  access, cookies, browser profiles, or credentials unless the owner explicitly
  approves that exact action.

## Content Rules

- Do not rewrite article meaning or silently improve prose.
- Preserve canonical URLs, publication dates, modified dates, source snapshots,
  featured images, inline images, outbound links, and artefact provenance.
- Exclude WordPress site chrome by default: sidebar, footer, search widgets,
  subscription UI, theme navigation, and unrelated layout wrappers.
- Exclude donation/support CTAs and `/donation/` article links from archive
  article bodies. They are site-operational content, not durable article
  content.
- Exclude sponsor/ad/trial lead CTAs from archive article bodies when they are
  operational promotion rather than durable article substance.
- Convert same-article numbered reference links away from WordPress
  `#h-references` anchors. Prefer linking each number directly to the matching
  source URL in that post's References list.
- Treat comments as out of scope unless the owner explicitly asks for them.

## Public Repository Safety

- Do not commit tokens, passwords, cookies, private notes, private comments,
  private exports, local database files, browser/session state, or local-only
  operational state.
- Run `make validate` and `make scan-secrets` before final reporting or any
  proposed commit/push.
- Remote destructive GitHub actions require explicit owner confirmation:
  deletion, force-push, replacing default branch, changing visibility, or
  creating a replacement repo.

## Structure

- Use `content/posts/YYYY-MM-DD-slug/index.md` page bundles.
- Keep post source snapshots in `source/`.
- Keep post assets in `assets/` and record checksums in `assets/manifest.json`.
- Keep generated machine-readable metadata in JSON and validate it against
  `schemas/`.
