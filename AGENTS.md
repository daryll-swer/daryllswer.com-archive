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
- Convert article-body links to mirrored daryllswer.com posts to archive-local
  links. Preserve section fragments and keep non-archived canonical pages
  external unless a deliberate archive-local replacement exists.
- Preserve WordPress heading IDs and generated alias anchors so local section
  links work in GitHub Pages.
- Preserve WordPress inline colour markup and generated Pages colour styling
  for article-body text/characters, including `has-inline-color` and
  WordPress preset classes such as `has-vivid-red-color`.
- Generated article headings must expose shareable section links: heading text
  should link to its own fragment, and generated Pages should provide visible
  permalink/copy-link controls with accessible names.
- Convert WordPress-uploaded image media links to local archived assets
  whenever the linked image is mirrored into the repository.
- Do not mirror third-party documents, PDFs, downloads, or external artefacts
  by default. Keep them as outbound hyperlinks with provenance unless the owner
  explicitly approves mirroring that exact artefact.
- Convert unsupported embedded media in Markdown to durable outbound links. The
  generated GitHub Pages site may render richer embed wrappers with fallback
  links.
- Treat comments as out of scope unless the owner explicitly asks for them.

## Public Repository Safety

- Do not commit tokens, passwords, cookies, private notes, private comments,
  private exports, local database files, browser/session state, or local-only
  operational state.
- Run `make validate` and `make scan-secrets` before final reporting or any
  proposed commit/push.
- Run `make render-site` after sync changes that affect public article
  rendering, site navigation, copied media, or spreadsheet artefact links.
- Remote destructive GitHub actions require explicit owner confirmation:
  deletion, force-push, replacing default branch, changing visibility, or
  creating a replacement repo.

## Maintainer Commands

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

## Structure

- Use `content/posts/YYYY-MM-DD-slug/index.md` page bundles.
- Keep post source snapshots in `source/`.
- Keep post assets in `assets/` and record checksums in `assets/manifest.json`.
- Preserve WordPress media basenames and downloaded bytes for media assets.
  Featured images and inline images must not be renamed or re-encoded unless a
  same-directory filename collision makes exact preservation impossible; record
  any such exception in the asset manifest.
- Keep generated machine-readable metadata in JSON and validate it against
  `schemas/`.
- Keep self-hosted third-party font source files and provenance under
  `assets/fonts/`; generated Pages copies belong under `docs/assets/fonts/`.
- Keep the GitHub Pages static site generated under `docs/`; do not hand-edit
  generated `docs/index.html`, `docs/posts/`, `docs/assets/`, or
  `docs/sheets/` outputs except through `scripts/render-site.py`.
