# Preservation Export and Private Backup

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

Creating a local export alone does not establish off-site or geographically
independent redundancy. The private GitHub copy below is separate-repository
protection, not protection against a GitHub-wide outage or loss of the same
account. GitHub-only continuity is accepted; an independent scheduler is not
part of this task. WARC capture is not included.

## Private Weekly Snapshots

The approved target is `daryll-swer/daryllswer.com-archive-backup`, private with
Pages disabled. Its `snapshot/` directory contains the latest verified package;
previous packages remain recoverable through that repository's own Git history.
Original development history is not copied. No automatic pruning, force push,
or history rewriting is part of refresh.

The intended schedule is Tuesday **04:17 UTC / 09:47 IST**. A refresh selects
current public `main` only with successful validated Pages evidence for that
exact revision. An unavailable source, failed deployment, failed package
verification or publication check leaves the previous snapshot intact.
Unchanged source produces no backup commit.

Trusted backup tooling is pinned separately from the source checkout. It reads
committed source files through the exporter's explicit `--source-repository`
argument; it never runs scripts from that fetched source. Copied source
workflows live under `snapshot/data/.github/`, where they are inert. The
read-only preparation job and write-scoped publication job exchange a verified
package with one-day artifact retention and no persistent dependency cache.
Publication is restricted to `snapshot/` and the backup record. The record
identifies source revision, trusted tooling revision and manifest digest.
The publisher independently fetches the approved public commit into a
temporary bare Git repository and compares the complete payload file set and
bytes against it. Before commit, staged-index verification checks every
snapshot file and byte, including ignored/hidden files; a path-prefix check
alone is insufficient. Private snapshots use the dedicated offline verifier:

```sh
python3 snapshot/data/scripts/backup-preservation.py verify --snapshot snapshot
```

Exact bootstrap commands and the inactive workflow template are in
[maintenance/backup/README.md](../maintenance/backup/README.md). The template
is not an active workflow in the public repository.

### Permanent Free-Tier Operation

No payment method may be added for this archive or its backup operation.
Operation must remain within GitHub's free tier. Do not purchase capacity,
enable paid overage, upgrade to a paid plan, or request payment-method setup
as a recovery step. This is a permanent constraint for unattended preservation,
not a billing decision awaiting the owner.

The existing `BACKUP_ZERO_PAID_OVERAGE_VERIFIED` variable records the approved
operating basis; it does not continuously inspect billing configuration.
Retain that guard and the trusted-tooling pin unchanged. If free-tier-only
execution becomes unavailable, retain the last verified snapshot rather than
activating paid services. Actual workflow evidence is in the status ledger.

When allowance exhaustion blocks execution, preserve the last good snapshot
and let the next weekly event retry. Included allowances reset monthly, so
more than one weekly attempt may be blocked. Do not accelerate retries, use a
paid fallback, or manufacture keepalive commits. Inspect Actions and the
recorded source revision to distinguish a healthy no-change run from an older
backup left by a failed/blocked run.

GitHub-only continuity is accepted. This policy cannot guarantee perpetual
GitHub availability, free allowances, scheduling or account continuity; no
new owner decision about alternative hosting is required.

Primary guidance: [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[shared storage billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages),
and [workflow token scope](https://docs.github.com/en/actions/concepts/security/github_token).
