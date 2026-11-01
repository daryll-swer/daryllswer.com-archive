# Local Preservation Export

## Scope

An export is a portable snapshot of a specified approved Git commit, not a
backup of Git history. It includes committed archive bundles, media, source
evidence, metadata, rights records, generated Pages, and rebuild tooling.
Retired content absent from the selected commit is not recovered from history.

The package follows the BagIt v1.0 layout described in
[RFC 8493](https://www.rfc-editor.org/rfc/rfc8493.html): `bagit.txt`, a `data/`
payload, SHA-256 payload and tag manifests, and descriptive bag metadata.
Checksums detect subsequent changes; they do not independently establish
authenticity or grant any content rights.

Git internals, secrets, caches and private operational material are excluded.
No source services are contacted to create or verify a package. Existing
external links, third-party documents and embeds remain external references,
not preserved media.

## Create and Verify

First review and approve the intended commit. Use a clean checkout with the
project's locked dependencies and run its tests, render, offline validation
and public-safety scan. Do not export unreviewed working changes.

```sh
git status --short --branch
git rev-parse HEAD
python3 scripts/export-preservation.py --commit <approved-full-commit> --output <new-directory-outside-repository>
python3 scripts/export-preservation.py --verify <new-directory-outside-repository>
```

The output directory must not already exist. A dirty tree is rejected by
default. The explicit dirty-tree override, when intentionally used, still
exports only the named committed snapshot, never uncommitted changes.

Read the package's `README-PRESERVATION.md` for its serving, rebuild and
verification commands. The recorded source revision and toolchain information
identify what was exported. Hash verification must succeed before treating a
copied or extracted package as intact.

## Restore Test

Copy or extract the package into a new temporary directory. Verify its complete
payload and tag manifests again. Serve `data/docs/` on loopback with Python's
standard-library HTTP server and block external source/network requests in the
test browser. Test the homepage, a DS article, the Swer Networks repost,
workbook and IPv6 visual, including local images, fonts, section links and
expanded hierarchy nodes. External-media fallback links may remain unavailable
while offline; they are not evidence of damaged local media.

Reading the prebuilt site needs no Python packages beyond the standard library
server. Rebuilding requires the recorded Python dependencies to have been
installed or separately retained; the package is not a universal offline
wheelhouse for every future operating system.

## Limits

Creating a local export does not establish off-site or geographically
independent redundancy. Storage selection, retention/refresh policy and an
independent scheduler are deferred. Keep package verification and restore-test
results separate from any future off-site preservation claim. WARC capture is
not included in this phase.
