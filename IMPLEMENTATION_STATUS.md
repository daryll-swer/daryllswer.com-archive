# Current Implementation Status

## Human-First README and Chat-Independent Handoff

- Updated: 2026-11-20. Status: implementation in progress.
- Active specification and next action: [PLANS.md](PLANS.md).
- Baseline: clean `main`, matching remote
  `9d201c713dabed3f94a3deca8c74f1d34019707d`.
- Documentation ownership: coordinator. Exporter, legacy verification and
  regression ownership: bounded implementation worker. No previous agent
  session is required to resume.
- Documentation is implemented locally. Read-only offline validation reports
  zero errors/warnings; safety and whitespace checks pass. Two renders leave
  reader pages, source/media, workbook output and favicon bytes unchanged.
- All 176 regressions pass, including 32 preservation/backup tests and five
  handoff checks. The repository-only recovery review identified the current
  task, owner actions and operating procedures without chat context. Follow-up
  fixes clarify trusted verification tooling, current deployment evidence,
  future pin transitions and the external Python environment.
- Legacy/current transition tests pass, including same-source migration,
  no-op repeats, exact file/byte binding, provenance rejection and rollback.
  A real package from the clean implementation commit and publication remain
  pending. Existing private snapshot offline verification passes.
- Production backup inclusion: pending a successful normal weekly run after
  reviewed tooling-pin adoption; do not claim local tests prove publication.

## Previous Verified Delivery

The canonical URL fix `ccd62b7` and post-2931 refresh `fa574f4` were recorded in
`9d201c7`. Fix CI `43861405062`, fresh reconciliation `43861579956` and successor
Pages `43861732119` passed. These are historical observations, not current
service-health claims. Full evidence is in the
[historical ledger](docs/history/IMPLEMENTATION_STATUS-through-2026-11-16.md).

## Pending Actions and Authority

Known engineering limitation outside this change: the canonical checker's
`--dry-run` can backfill missing raw-content fingerprints before its dry-run
exit. The handoff guide requires a disposable checkout for that diagnostic;
reconciliation behaviour was not changed. This is not a new owner decision.

[PLANS.md](PLANS.md#owner-follow-ups) is the single current owner-action list.
No billing, VoiceOver, backup-setup or continuity decision is outstanding.
For current operation use [maintenance](docs/MIRRORING.md) and
[preservation](docs/PRESERVATION.md), not historical task instructions.
