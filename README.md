# daryllswer.com Archive

This repository is a public mirror/archive of published content from
[daryllswer.com](https://www.daryllswer.com/). The WordPress site remains the
canonical source.

GitHub repository name: `daryllswer.com-archive`.

The archive is designed to be readable by humans, Codex/LLM agents, and normal
repository tooling. Each post is stored as a self-contained content bundle with
Markdown, source snapshots, metadata, featured image, inline assets, and an
asset manifest.

## Layout

- `content/posts/YYYY-MM-DD-slug/` - one page bundle per published post.
- `data/sheets/` - public spreadsheet artefacts linked from posts.
- `schemas/` - JSON Schemas for generated metadata and manifests.
- `scripts/` - public sync, export, validation, preview, and safety-scan tools.
- `docs/` - mirroring, validation, and decision notes.
- `archive-manifest.json` - generated root index of mirrored posts and checks.

## Commands

```sh
make sync
make validate
make scan-secrets
make render-preview
```

The scripts use public WordPress/API/sitemap/RSS/export surfaces only. If a
future task needs authentication, private WordPress export, database access, SSH
backend access, or destructive GitHub actions, it must stop for explicit owner
approval first.

## Licence

Repository scripts/tooling are MIT licensed. Mirrored blog content follows
`CC-BY-NC-SA-4.0`, matching daryllswer.com unless per-file metadata says
otherwise. Third-party media and external artefacts are not assumed to be
covered by either licence. See `LICENSING.md`.
