# Active Archive Plan

## Current Objective

Human-first README and chat-independent handoff, approved 2026-11-20.
Implementation is in progress; repository history before this task is at
`9d201c713dabed3f94a3deca8c74f1d34019707d`.

## Work and Completion Gates

1. Complete locally: concise human README, prominent archive link, agent reading
   order and reproducible maintenance instructions.
2. Complete locally: retain historical checkpoints under `docs/history/`; keep
   current state and owner actions in the root documents.
3. Complete locally: export `PLANS.md`, narrowly verify legacy backup snapshots and test
   legacy-to-new publication without executing snapshot code.
4. Checks pass: 176 regressions, compilation, offline integrity, safety scan,
   deterministic rendering and repository-only recovery. Temporary package
   verification from the clean implementation commit is next.
5. Pending: normal publication, exact-revision CI/Pages verification, reviewed
   private backup tooling-pin adoption. Do not dispatch an extra backup run.

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
state before continuing. The coordinator owns documentation, integration,
review and publication; a bounded implementation worker owns exporter/backup
code and tests. Do not depend on a prior chat, worker session or local temp path.

## References

- [Architecture](ARCHITECTURE.md), [decisions](docs/DECISIONS.md),
  [escalation rules](ESCALATION.md)
- [Maintenance](docs/MIRRORING.md), [preservation](docs/PRESERVATION.md),
  [source recovery](docs/SEO_RECOVERY.md)
- [Historical plan](docs/history/PLANS-through-2026-11-16.md) and
  [historical ledger](docs/history/IMPLEMENTATION_STATUS-through-2026-11-16.md)
  are superseded checkpoints, not current instructions.
