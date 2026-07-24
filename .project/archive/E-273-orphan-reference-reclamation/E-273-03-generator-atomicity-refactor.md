# E-273-03: Generator team+report creation atomicity refactor

## Epic
[E-273: Reclaim Orphaned Reference Data After Report Deletion](epic.md)

## Status
`DONE`

## Description
After this story is complete, the report generator commits the scouted-team row and its generating-`reports` row in ONE transaction, so a `teams` row is never visible without its protecting `generating` reports row. This closes the pre-`reports`-row concurrency window that would otherwise let the reclamation sweep see an in-flight generation's scouted team as an orphan — making the reap-then-gate guard airtight rather than merely good.

## Context
The generator commits the scouted `teams` row (generator.py ~:1708 via `_ensure_team_row`), then creates the `reports` row on a SEPARATE connection (~:1717 via `_create_report_and_run_record`); between those two commits the team looks identical to an orphan (TN-5/TN-6). The two commits have no network between them, so merging them into one transaction is a small local refactor contained to the single `run()` call site (generator.py:1579/:1582). This is the minimal piece of the `docs/ROADMAP.md:82` race in scope — it satisfies OQ2's "don't make it worse" and actually makes it better. This story has no source-file overlap with 01/02 (it touches `generator.py`), so it carries no hard dependency on them.

## Acceptance Criteria
- [ ] **AC-1**: Given a normal report generation, when `run()` creates the scouted team and its generating `reports` row, then both writes (and the `report_generation_runs` row) commit in ONE transaction, in FK order teams → reports → run-record, per TN-6.
- [ ] **AC-2**: Given a failure injected between the team write and the reports write (e.g. `_create_report_and_run_record`/`_create_report_row` raises), when `run()` executes, then NEITHER the `teams` row NOR the `reports` row persists (single rolled-back transaction) — a scouted team is never left committed without its `generating` reports row. This is the error-path AC that makes the gate airtight.
- [ ] **AC-3**: The three IDEA-127 identity tests that call `_ensure_team_row` standalone (`test_report_generator.py:1314/:1341/:1375`) remain GREEN with no edit — the connection-injection shape keeps the default (own-connection, self-committing) behavior for standalone callers, per TN-6.
- [ ] **AC-4**: The IDEA-127 public_id-backfill + match_method-downgrade block (`generator.py:1671-1707`) is unchanged in behavior — the refactor moves ONLY the commit boundary, per TN-6.

## Technical Approach
Apply the connection-injection shape from TN-6: give `_ensure_team_row` and `_create_report_and_run_record` an optional `conn` param (default `None` → open+commit own connection, backward-compatible; passed → use it, do NOT commit); `run()` opens one connection, calls both in FK order, commits once. Preserve the IDEA-127 backfill/downgrade block. Add the error-path test (AC-2). Blast radius is contained to `run()` (SE grep-verified, TN-6); `_create_report_and_run_record` has no direct test callers, so it can be refactored freely. Follow the codebase "caller owns the transaction" convention (`reload_game_plays`, `merge_player_pair(manage_transaction=False)`). Run test-scope discovery for `src/reports/generator.py` per `.claude/rules/testing.md`.

## Dependencies
- **Blocked by**: None (touches `generator.py` — disjoint from 01/02's `lifecycle.py`)
- **Blocks**: None (hardens E-273-02's guard but 02 functions without it — a residual microsecond window remains until this lands)

## Files to Create or Modify
- `src/reports/generator.py` (connection-injection on `_ensure_team_row` + `_create_report_and_run_record`; one-transaction commit in `run()`)
- `tests/test_report_generator.py` (atomicity + error-path test)

## Agent Hint
software-engineer

## Handoff Context
<!-- No downstream story consumes an artifact from this one; it hardens E-273-02's guard but 02 does not depend on it. -->

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (the three IDEA-127 tests especially stay green untouched)

## Notes
Per the TN-15 test-file partition, story 03 is the ONLY E-273 story that edits `tests/test_report_generator.py` (its atomicity test colocates with the IDEA-127 tests it must keep green), so it stays disjoint from 01/02/04/05 and carries no intra-epic dependency edge. The only overlap on this file is CROSS-EPIC: E-270-03 also adds a class to `test_report_generator.py` — flag the staging/merge sequencing per TN-11 if both epics dispatch concurrently.
