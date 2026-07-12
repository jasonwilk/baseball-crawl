# E-256-10: Operator docs/admin updates (backups + smoke pointer + seeds + backfill doc eviction)

## Epic
[E-256: Post-Descope Simplification & Foundations](epic.md)

## Status
`DONE`

## Description
After this story is complete, the epic's `docs/admin/` operator documentation is updated in one docs-writer-owned pass: (1) a required, scheduled backup step that writes OFF the live-DB disk; (2) the Step 1d closure-smoke procedure reference in `production-deployment.md`; (3) the corrected `architecture.md` seeds line; and (4) eviction of the `backfill-appearance-order` runbook section (AC-6, the `docs/admin/` slice of the epic's backfill eviction). This is the single home for the epic's `docs/admin/` edits, consolidated here per CA's Q1 routing rule (docs/admin is docs-writer's domain, so the cross-domain edits from stories 06, 11, and 02 land here rather than as ACs in non-docs-writer stories).

## Context
Three `docs/admin/` edits the epic needs, all docs-writer's domain, consolidated into one story so no non-docs-writer story carries a cross-domain doc AC:
- **Backups** (the original scope): Technical Notes §10 corrects the audit's reason — `backup_database` IS invoked (`bb db backup`, `src/cli/db.py:11,43`); the real finding is (a) nothing schedules it and (b) `_BACKUPS_DIR = _PROJECT_ROOT/"data"/"backups"` (`src/db/backup.py:20`) sits inside the same host-mounted `./data` volume as `app.db`.
- **Smoke procedure pointer** (from story 11, Q1 fold): story 11's Step 1d skill references `production-deployment.md` as the smoke-procedure doc; the doc CONTENT is this story's deliverable.
- **Seeds line** (from story 06, Q1 fold): `docs/admin/architecture.md:67`'s `seeds/ # Development seed SQL (committed to git)` line is false on both halves after story 06 removes the seeds surface.

## Acceptance Criteria
- [ ] **AC-1**: Given `docs/admin/production-deployment.md` (and/or `operations.md`), when this story is complete, then a **required** deploy/runbook step schedules `bb db backup` at a **stated cadence** (e.g. daily), using the host-vs-container-correct invocation form (the `bb`/host-python concerns from the E-253/CE-2 runbook work).
- [ ] **AC-2**: Given `backup_database()` always writes under `./data/backups/` (`src/db/backup.py:20`), when this story is complete, then the runbook reconciles "off the `./data` volume" with that reality by adding a **copy-off-host step** after `bb db backup` (e.g. `rsync`/`cp` the newest backup to an off-host/off-disk target), and states plainly that a backup left inside `./data` is destroyed with the DB on disk loss. (No `src/db/backup.py` change is required; the off-disk copy is a runbook step. If the team later wants a native `--output`/env target, that is IDEA-worthy, not this story.)
- [ ] **AC-3**: Given story 11's Step 1d smoke procedure, when this story is complete, then `docs/admin/production-deployment.md` documents the closure-smoke procedure that Step 1d's skill text points to (`bb report generate` + `reconcile-scoreboard`/`verify-aggregates` + `morning-run --dry-run` + `curl /health`), and the **two-field `.smoke-fixture` operator convention** (`generate=<public_id>` + `morning-run=<lsb-url…>`; both LSB's own identifiers, NEITHER committed — the file is gitignored).
- [ ] **AC-4**: Given `docs/admin/architecture.md:67`, when this story is complete, then the false `seeds/ # Development seed SQL (committed to git)` line (both halves false after story 06) is corrected or removed.
- [ ] **AC-5**: Given the touched docs, when this story is complete, then each carries the staleness convention (Last updated: date, Source: E-256) per `.claude/rules/documentation.md`.
- [ ] **AC-6**: Given `bb data backfill-appearance-order` deleted in story 02, when this story is complete, then `docs/admin/operations.md`'s backfill-appearance-order runbook section (the operator recipe + any precedent references) is struck or reconciled so no operator doc prescribes the deleted command, verified by grep-and-reconcile against the story-02 authoritative surface list (epic Technical Notes §15) — token grep PLUS a semantic read of the touched section, not a keyword grep alone (`.claude/rules/doc-sweep.md`). This is the `docs/admin/`-owned slice of the epic's backfill eviction (routing per §15).

## Technical Approach
docs-writer owns all of `docs/admin/`. The backup off-disk target is achieved by a runbook copy step (Simple first) — do NOT change `src/db/backup.py` (it writes under `./data` by design; the copy-off-host step is the mechanism). Coordinate with story 11 on the exact smoke-procedure wording so the skill's doc pointer and this doc agree (story 11 supplies the procedure; this story writes the doc). AC-4's seeds line depends on story 06 having removed the seeds surface (see Dependencies).

## Dependencies
- **Blocked by**: E-256-02 (AC-6's `operations.md` backfill-runbook eviction follows the command deletion, so the doc matches the built state), E-256-06 (AC-4's seeds-line correction should follow story 06's removal of the `data/seeds/` surface), **E-256-11** (AC-3 consumes story 11's Step 1d smoke procedure + `.smoke-fixture` convention — this story documents what 11 designs, so it must follow 11)
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/production-deployment.md` (backup step + smoke-procedure reference)
- `docs/admin/operations.md` (backup cadence if it lives here; the `backfill-appearance-order` runbook-section eviction, AC-6)
- `docs/admin/architecture.md` (line ~67 seeds correction)

## Agent Hint
docs-writer

## Handoff Context
- **Consumes from E-256-11**: the exact Step 1d smoke-procedure steps + `.smoke-fixture` convention (story 11 designs; this story documents).
- **Consumes from E-256-06**: confirmation the `data/seeds/` surface is removed, so AC-4's correction matches the built state.
- **Consumes from E-256-02**: the deleted `backfill-appearance-order` command name + the authoritative repo-wide grep surface list (epic Technical Notes §15), so AC-6's `operations.md` eviction matches the built state and covers every operator-doc reference (not just the ones enumerated).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Runbook steps executable as written (host-vs-container correct)
- [ ] Docs follow the staleness convention (Last updated / Source)
- [ ] No regressions in existing tests

## Notes
Backup scheduling was also on CE-5's PM docket; it is scoped HERE (foundations). Do not re-add it to any other epic. This story is the single `docs/admin/` owner for E-256 — no other story carries a `docs/admin/` AC (per CA's Q1 routing rule).
