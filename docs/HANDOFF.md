# Fresh Checkout and Safe Handoff

## Reading Order and Authority

Start at [AGENTS.md](../AGENTS.md), [the active plan](../PLANS.md) and
[the current ledger](../IMPLEMENTATION_STATUS.md). Then read relevant
[architecture](../ARCHITECTURE.md), [decisions](DECISIONS.md),
[escalation rules](../ESCALATION.md) and operational guides below.
`docs/history/` records past observations, not current instructions. Old
approval, worker identity, test count or deployment evidence is not renewed
authority or proof of current health. No previous chat/session is needed.

The plan is the single current task and owner-action list. The ledger records
observed results and unverified items. Record dates and revisions for evidence;
do not label a pending publication or scheduled backup complete. Current
policies take precedence over superseded historical checkpoints.

## Inspect Before Changing Anything

From the public repository checkout:

```sh
git status --short --branch
git diff --stat
git diff --cached --stat
git remote -v
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Confirm the remote is `daryll-swer/daryllswer.com-archive`. The final command
reads remote state without updating local refs; `origin/main` alone may be
stale. Preserve unrelated work. Only after inspection, when authorised to
implement and the checkout is suitable, use `git pull --ff-only`. Stop on
divergence; do not reset, overwrite changes or force-push to make it match.

With GitHub CLI already available and access authorised:

```sh
gh run list --repo daryll-swer/daryllswer.com-archive --branch main --limit 10 \
  --json databaseId,workflowName,headSha,status,conclusion,url
gh run view RUN_ID --repo daryll-swer/daryllswer.com-archive \
  --json headSha,status,conclusion,jobs,url
```

Use an observed `RUN_ID`, not a historical example. Inspect failed steps before
choosing a remedy. Missing account access is a limitation to report, not a
reason to request credentials or alter permissions.

## Reproducible Python Setup

Use CPython 3.12, Git and Make. GitHub CLI is only for connected checks. Do not
modify global Python or reuse a broken/unknown environment. Choose a new
virtual environment outside the repository:

```sh
ENV_DIR="$(mktemp -d "${TMPDIR:-/tmp}/archive-check.XXXXXX")"
python3.12 -m venv "$ENV_DIR/venv"
PYTHON="$ENV_DIR/venv/bin/python"
"$PYTHON" -m pip install --require-hashes -r requirements-lock.txt
"$PYTHON" scripts/check-requirement-lock.py
```

The temporary path is local runtime state, never a durable dependency. If the
runtime or packages are unavailable, report the prerequisite; do not silently
upgrade dependencies or repair unrelated environments.

## Checks Versus Mutations

These checks do not refresh tracked reports or contact DS/SN sources. Tests
may create isolated fixtures, loopback servers and temporary files:

```sh
"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" -m py_compile scripts/*.py tests/*.py
"$PYTHON" scripts/validate-mirror.py --offline --no-report
"$PYTHON" scripts/scan-public-safety.py --no-report
git diff --check
```

These commands intentionally write generated files/reports. Use them for
authorised implementation, then inspect all changes before staging:

```sh
make PYTHON="$PYTHON" render-site
make PYTHON="$PYTHON" validate
make PYTHON="$PYTHON" scan-secrets
git diff --stat
git status --short
```

For determinism, use a clean disposable checkout of the reviewed commit,
render twice and require `git diff --exit-code` after each render. Also inspect
`git ls-files --others --exclude-standard docs data` for unexpected output.
Never reset a working checkout to obtain a clean test.

`make validate-live` contacts sources and writes its report; an offline pass
does not establish live equality. `make sync`, drift/source-health commands
and reconciliation can change content/state. They are not setup steps. Follow
[MIRRORING.md](MIRRORING.md), preserving freeze/ownership gates. Manual recovery
requires [SEO_RECOVERY.md](SEO_RECOVERY.md), never a hand-edited status file.
No backup dispatch or retry is part of routine setup.

Do not assume a `--dry-run` label guarantees a read-only checkout: the canonical
checker can backfill missing raw-content fingerprints in post metadata before
its dry-run exit. Use a disposable checkout for that diagnostic. This existing
behaviour is outside the handoff change; the offline `--no-report` checks above
are the non-source-mutating inspection path.

## Publication Evidence

Normal publication requires reviewed diffs, checks, scoped staging, a normal
commit/push and current authorisation. Never commit private runtime evidence.
The authoritative jobs are `ci.yml` and `deploy-pages.yml`.

Record the full published commit and find CI/Pages runs whose `headSha` equals
it. Require successful CI and Pages build/deploy jobs, then inspect the live
routes. If Pages skips because the revision is already deployed, locate the
existing successful deployment; a skipped job is not new deployment evidence.

```sh
gh api 'repos/daryll-swer/daryllswer.com-archive/deployments?environment=github-pages&per_page=10' \
  --jq '.[] | {id,sha,created_at,statuses_url}'
gh api repos/daryll-swer/daryllswer.com-archive/deployments/DEPLOYMENT_ID/statuses \
  --jq '.[] | {state,environment_url,log_url,created_at}'
```

Use an observed deployment ID and verify its SHA. If main advances,
distinguish the reviewed commit from the deployed successor. A failed Pages
deployment can be retried through that workflow when authorised; do not repeat
content mutation or manufacture an empty commit.

## Backup Evidence and Limits

The private target is `daryll-swer/daryllswer.com-archive-backup`. Access it only
under current scoped authorisation. [PRESERVATION.md](PRESERVATION.md) describes
verification; [backup guidance](../maintenance/backup/README.md) describes the
separately pinned tooling. Read the private workflow result and snapshot record:
source revision, tooling revision and payload-manifest digest must agree with
the verified package. Public deployment success is not backup completion; a
snapshot may legitimately lag main until the next normal weekly run.

No payment method or paid fallback is permitted. Do not change schedules,
permissions or the operating-basis guard during recovery. Review and test an
explicit tooling-pin change before adoption; never execute fetched snapshot
code as trusted tooling. Keep the last verified backup on failure. No
accelerated retries or empty keepalive commits. GitHub-only continuity does
not protect against account loss or a GitHub-wide outage.

## Before Handing Off

Update the plan/ledger with completed work, precise unverified items and the
next safe action. Link evidence instead of copying logs. Keep historical
records separate and repair links when moving them. A fresh reader should
identify the task, policies, checks, publication state and owner follow-ups
without this chat. Account access, source ownership and future availability
cannot be recovered from documentation alone.
