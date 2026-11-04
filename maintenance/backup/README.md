# Private Backup Bootstrap

No payment method may be added for this archive or its backup operation.
Operation must remain within GitHub's free tier. Do not purchase capacity,
enable paid overage, upgrade to a paid plan, or request payment-method setup
as a recovery step. This permanent policy supports unattended preservation.

The reviewed template is already installed in the private repository. Retain
`BACKUP_ZERO_PAID_OVERAGE_VERIFIED=true` and the full approved
`BACKUP_TOOLING_SHA` unchanged. The guard records the approved operating basis,
not continuous billing inspection. Both jobs remain skipped if either variable
is absent. Future bootstrap must establish the same free-tier-only basis;
never replace it with a paid budget or a payment-method request.

The Tuesday 04:17 UTC run fetches the public archive anonymously, prepares a
BagIt snapshot with the pinned public tooling, validates the successful
`deploy-pages.yml` build/deploy jobs and latest successful Pages deployment for
the exact current `main` SHA, and transfers a one-day artifact. Publication
repeats those source/deployment checks and atomically updates only `snapshot/`.
It also fetches the selected source commit into an isolated temporary bare Git
repository and matches every payload path and byte against that commit. Before
commit, `verify-staged` checks the forced Git index against the complete
verified snapshot, including ignored files.
It does not copy `.git`, run scripts from the snapshot, install dependencies,
prune history, or delete a previous good snapshot on failure. A failed run leaves
the existing backup intact; the next Tuesday retries, including when a monthly
allowance remains exhausted. No accelerated retries, paid fallback or empty
keepalive commits are permitted. Do not assume a weekly allowance reset.
Free-tier-only operation cannot guarantee perpetual service, scheduling or
account continuity; GitHub-only continuity remains the accepted limitation.

## Local Commands

From a trusted tooling checkout, with a separate clean public-source checkout
and no private credentials:

```sh
python3 scripts/backup-preservation.py prepare \
  --source-repository daryll-swer/daryllswer.com-archive \
  --source-sha FULL_PUBLIC_MAIN_SHA \
  --source-checkout /path/to/public-source \
  --tooling-sha FULL_TRUSTED_TOOLING_SHA \
  --output /path/outside/both/checkouts/snapshot

python3 scripts/backup-preservation.py publish \
  --payload /path/to/verified/snapshot \
  --repository /path/to/private-backup-checkout \
  --source-repository daryll-swer/daryllswer.com-archive \
  --tooling-sha FULL_TRUSTED_TOOLING_SHA
```

`prepare` and `publish` use Python's standard library and Git only. The trusted
tooling SHA identifies the code used for both stages; the record binds it to
the exact source SHA and BagIt payload-manifest digest.

Verify an extracted private snapshot, including its backup record, from the
snapshot root with:

```sh
python3 data/scripts/backup-preservation.py verify --snapshot .
```
