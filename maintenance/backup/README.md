# Private Backup Bootstrap

Copy `backup.yml` into the private backup repository's `.github/workflows/` only
after the coordinator verifies the compute and Actions-storage budget hard stop.
Do not create or enable a repository as part of this template change.

Set repository Actions variable `BACKUP_ZERO_PAID_OVERAGE_VERIFIED=true` only
after that check. Set `BACKUP_TOOLING_SHA` to the full commit SHA published for
the trusted backup tooling. Both jobs remain skipped if either variable is
absent; no placeholder SHA is provided. Keep repository Actions disabled until
the guard and budget decision are reviewed.

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
allowance remains exhausted. Do not assume a free-plan cap or allowance reset.

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
