# Active Archive Plan

## Current Objective

Human-first README and chat-independent handoff, approved 2026-11-20.
Implementation is published; repository history before this task is at
`9d201c713dabed3f94a3deca8c74f1d34019707d`.

## Work and Completion Gates

1. Complete: concise human README, prominent archive link, agent reading
   order and reproducible maintenance instructions.
2. Complete: retain historical checkpoints under `docs/history/`; keep
   current state and owner actions in the root documents.
3. Complete: export `PLANS.md`, narrowly verify legacy backup snapshots and test
   legacy-to-new publication without executing snapshot code.
4. Complete: 176 regressions, compilation, offline integrity, safety scan,
   clean-checkout deterministic rendering, repository-only recovery and
   extracted 506-file payload checksum/offline-reader verification.
5. Complete: implementation publication, exact-revision CI/Pages verification
   and reviewed private tooling-pin adoption. README rendering passes desktop
   and mobile checks. See the ledger for revision/run evidence.
6. Pending: verify production snapshot migration after the next normal weekly
   backup. Do not dispatch an extra run or claim local tests prove migration.

## Owner Follow-ups

- Google Search Console: verify homepage indexing and sitemap Success. Earlier
  fetch tests passed; account-level acceptance remains unverified.
- Bing Webmaster Tools: optional registration/import decision.
- VoiceOver is cancelled. Backup setup, dependency approvals and same-URL
  media detection are complete. GitHub-only continuity is an accepted limit.
  None of these is a new owner decision.

## Constraints

Preserve rights, article/media bytes, source-first SEO, atomic reconciliation,
source-freeze safeguards, schedules and permissions. No payment method, paid
capacity, history rewrite or accelerated backup retries. Historical approvals
are evidence, not permission for a new consequential action.

## Next Pickup

Read [AGENTS.md](AGENTS.md), then this plan and
[the current ledger](IMPLEMENTATION_STATUS.md). Inspect current Git and remote
state before continuing. Implementation workers have finished. The next safe
action is a read-only check after the normal scheduled private backup: verify
its tooling/source record and `snapshot/data/PLANS.md`, then record success or
the precise blocker. Private access still requires current authorisation. Do
not depend on a prior chat, worker session or local temp path. No owner decision
is needed for this pending verification; the two account follow-ups above are
separate.

## References

- [Architecture](ARCHITECTURE.md), [decisions](docs/DECISIONS.md),
  [escalation rules](ESCALATION.md)
- [Maintenance](docs/MIRRORING.md), [preservation](docs/PRESERVATION.md),
  [source recovery](docs/SEO_RECOVERY.md)
- [Historical plan](docs/history/PLANS-through-2026-11-16.md) and
  [historical ledger](docs/history/IMPLEMENTATION_STATUS-through-2026-11-16.md)
  are superseded checkpoints, not current instructions.
