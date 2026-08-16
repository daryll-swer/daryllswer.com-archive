# Archive SEO Recovery

## Purpose

`archive_discovery` and `frozen_source` are deliberate, non-automatic fallback
states. A later successful HTTP response is not enough to restore source
priority: the response could be a temporary recovery, an unrelated redirect,
or a source no longer controlled by the expected owner.

Do not edit `archive-status.json` manually. Use the commands below only after
the owner has verified current control of the relevant public source and the
expected article/service is present.

## DS Recovery

Use this procedure when `archive-status.json` is `frozen_archive` and the DS
site is again demonstrably owner-controlled.

1. Confirm the current public DS REST collection is available and the service,
   domain, and content are under the expected owner control.
2. Use the installed project Python environment to make a fresh public REST
   observation and explicitly restore `source_primary`:

```sh
PYTHON=.venv/bin/python3
"$PYTHON" scripts/manage-archive-seo.py resume-ds --owner-verified
make PYTHON="$PYTHON" render-site
"$PYTHON" -m py_compile scripts/*.py
git diff --check
make PYTHON="$PYTHON" validate
make PYTHON="$PYTHON" scan-secrets
git status --short
```

3. Review the diff. A correct DS recovery removes `docs/feed.xml`, removes the
   homepage RSS alternate link, returns archive reader routes to
   `noindex,follow`, and reduces the sitemap to the archive homepage.
4. Commit and push only after that review. The command does not reconcile or
   overwrite article content; run the normal drift/reconciliation workflow
   separately if source content also changed.

## External-Original Recovery

Use this procedure when a registry-marked source has reached `frozen_source`
and is now again owner-controlled. The affected post becomes `noindex` again;
it remains visible in the archive index.

1. Confirm the exact original source URL, rights holder, and article are under
   expected owner control.
2. For the BGP Router ID repost, force exactly one bounded check of WordPress
   post ID `5324` and restore its source health:

```sh
PYTHON=.venv/bin/python3
"$PYTHON" scripts/manage-archive-seo.py resume-external --post-id 5324 --owner-verified
make PYTHON="$PYTHON" render-site
"$PYTHON" -m py_compile scripts/*.py
git diff --check
make PYTHON="$PYTHON" validate
make PYTHON="$PYTHON" scan-secrets
git status --short
```

3. Review the sitemap and feed diff. The affected post must be absent from
both, even if DS remains in `archive_discovery`.
4. Commit and push only after the review.

For a future registry-marked post, substitute its immutable WordPress ID. The
recovery command refuses IDs not explicitly opted into external fallback.

## Guardrails

- `--owner-verified` is an explicit maintainer acknowledgement, not a
  technical proof of ownership.
- `scripts/manage-archive-seo.py` performs the fresh public request itself.
  It refuses recovery when that request does not return a current healthy
  observation.
- Scheduled monitoring never performs this transition. It makes one low-volume
  weekly public request only while the source is active, and makes none for a
  frozen source unless a maintainer invokes this recovery path.
- No recovery command rewrites Git history, changes repository visibility, or
  mutates mirrored article content.
