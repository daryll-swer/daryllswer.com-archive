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

## Maintainer Workflow

Use these commands when refreshing or validating the archive:

```sh
make sync
make render-site
make validate
make scan-secrets
make render-preview
```

The scripts use public WordPress/API/sitemap/RSS/export surfaces only. If a
future task needs authentication, private WordPress export, database access, SSH
backend access, or destructive GitHub actions, stop for explicit owner approval
first.

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

## Media and Embeds

Inline images and WordPress-uploaded media links are downloaded where possible
and rewritten to local archive paths. This applies to image figures and to text
links that point directly at files under `www.daryllswer.com/wp-content/uploads/`.

Downloaded media files are stored as direct response bytes with no image
re-encoding, resizing, or metadata stripping. This keeps embedded image
metadata/EXIF identical to the public WordPress media response. The archive
preserves the WordPress URL basename for featured, inline, and linked media
wherever possible, and the asset manifest records the source filename, stored
filename, SHA-256 checksum, and whether the filename was preserved. The only
allowed exception is a same-directory filename collision.

Unsupported embeds such as podcast iframes are converted to durable Markdown
links in `content/posts/.../index.md`. The generated GitHub Pages site keeps a
styled embed wrapper with a fallback outbound link, so readers do not see raw
HTML in the repository view.

The AS141253 Google Sheet link in the IPv6 architecture article is rewritten to
the repository-hosted `data/sheets/as141253-ipv6-architecture-example/workbook.html`
in Markdown and to the generated Pages workbook in HTML.

## Spreadsheet Workbook

The AS141253 Google Sheet is archived as a CSV-backed HTML workbook:

- `data/sheets/as141253-ipv6-architecture-example/workbook.html` is the
  standalone repository copy with clickable sheet tabs.
- `docs/sheets/as141253-ipv6-architecture-example/index.html` is the generated
  GitHub Pages copy of the same workbook.
- `data/sheets/as141253-ipv6-architecture-example/csv/` remains the editable
  text source for each tab.
- `AS141253-ipv6-architecture-example.ods` and `html/` snapshots preserve
  styled/provenance references.

Google's CSV exports are normalised to LF line endings when written to the
repository so tabular diffs remain stable under `.gitattributes`. Generated HTML
artefacts also strip trailing line whitespace; binary ODS/media artefacts are
left as binary files.
