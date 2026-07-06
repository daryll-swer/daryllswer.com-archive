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
