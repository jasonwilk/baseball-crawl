# E-235-04: Close the concurrent-generation team-deletion race

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`TODO`

## Description
After this story is complete, two report generations running at the same time can no longer delete each other's freshly-created teams. The orphan-cleanup step deletes only teams attributable to the current run, not teams identified by a global before/after snapshot diff that cannot distinguish concurrent runs.

## Context
The current orphan cleanup snapshots all team ids before the run and diffs against a post-run snapshot — any team that appeared in between is treated as an orphan and deleted (ROADMAP §2, `generator.py:1088/1198/1317`). With two concurrent generations, run A's diff captures run B's newly-created team and can delete B's legitimately-shared rows. SE called this the epic's sharpest risk. The real boundary is CROSS-PROCESS (admin UI, CLI, and future cron are separate processes on one SQLite file), so an in-process lock does not close it. The full analysis, the recommended structural fix, the lock fallback constraints, and the required SE+DE alignment are in **epic Technical Notes §TN-4**.

## Acceptance Criteria
- [ ] **AC-1**: A regression test proves two interleaved generations (or a simulated interleaving at the orphan-determination boundary) do NOT delete each other's freshly-created teams. This is the defining outcome.
- [ ] **AC-2**: The fix closes the CROSS-PROCESS race (admin-UI + CLI + cron are separate processes on one SQLite file). A bare process-level/asyncio lock is NOT an acceptable sole fix. Per §TN-4.
- [ ] **AC-3**: Orphan cleanup deletes only teams this run INSERTed — tracked via an in-memory per-run created-set capturing inserted-not-matched teams (§TN-4) — replacing the global pre/post snapshot diff. OR, if a lock is chosen instead, it is DB-backed with stale-lock recovery and holds no write transaction across the network crawl. Mechanism is SE's call. (The SE+DE alignment that precedes this story is a process gate tracked in Notes/Open Questions, not an AC.)
- [ ] **AC-4**: The existing blast-radius limits are preserved — cleanup still deletes only games where both participants are orphans and retains teams still FK-referenced by surviving games. Per §TN-4.
- [ ] **AC-5**: The single-generation behavior is unchanged (a lone generation still cleans up its own auto-created opponent stubs); the E-234 golden stat-table test, aggregate-parity test, and E-234-04 negative-path tests stay green (this story mutates `teams` rows the goldens depend on, so the guards are named explicitly).

## Technical Approach
Per §TN-4 (DE-1): use an IN-MEMORY per-run created-set — the set of team ids THIS `generate_report()` call INSERTed — and clean up only those teams, replacing the global pre/post snapshot diff. Team creation and cleanup happen in the same process within one call, so this closes the cross-process race with no migration and no persisted `created_by_run_id` column. The set must capture INSERTed teams, not MATCHED ones (DE-2) — `ensure_team_row()` returns existing ids too, so it must signal insert-vs-match to its caller (the SAME canonical-function extension story 03 introduces in `src/db/teams.py`; this story consumes it). The orphan stubs are created during the scouting load via `ScoutingLoader` → `ensure_team_row()`, so the created-set (or its insert-recording hook) must thread through `src/gamechanger/loaders/scouting_loader.py` (SE-F5) — `ScoutingLoader` has no run knowledge today. Timestamp-based attribution does NOT work (concurrent runs overlap in time). If a lock is chosen instead, it must be DB-backed with stale-lock recovery and must not hold `BEGIN IMMEDIATE` across network I/O. **SE+DE alignment precedes implementation** (see Notes).

## Dependencies
- **Blocked by**: E-235-03 (linear `generator.py` chain per CR-F1; also consumes the `ensure_team_row` insert-vs-match signal story 03 introduces)
- **Blocks**: E-235-05 (serializes `generator.py` deletion-path edits)

## Files to Create or Modify
- `src/reports/generator.py` (orphan-determination + `cleanup_orphan_teams` call site; in-memory created-set)
- `src/gamechanger/loaders/scouting_loader.py` (thread the created-set / insert-recording hook through the stub-creating `ensure_team_row` calls — SE-F5)
- `src/db/teams.py` (CONSUME the insert-vs-match signal story 03 introduces on `ensure_team_row`; do NOT add a second edit if story 03 already covers it — coordinate per the linear 04←03 chain)
- `tests/test_report_generator.py` and/or a new concurrency regression test
- **Migration NOT expected** (DE-1): the in-memory created-set needs no persisted column or lock table. Only add a migration if the SE+DE alignment chooses the DB-lock fallback.

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-235-05**: the final shape of the generation-time cleanup path, so the cleanup-mirror story edits a settled `generator.py` deletion surface.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (including the concurrency regression test)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (E-234 guards green)

## Notes
SE+DE alignment on the mechanism is required before this story freezes (§TN-4) — DE offered to review the choice. If a new column/table is introduced, it needs a migration coordinated with story 01's numbering.
