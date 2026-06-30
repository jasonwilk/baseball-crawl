# E-249-02: CLI Delegation to Shared Planner + Refused-Fork WARN Surfacing

## Epic
[E-249: Player-Dedup Stale-Worklist Fix](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb data dedup-players` will route through the same shared component-planning unit as the load path instead of re-inlining its own `find_duplicate_players` + merge loop. The CLI dry-run preview surfaces refused forks alongside the planned collapses, and the execute path emits the same WARN log per refused fork. This removes the duplicated, separately-buggy CLI merge loop ("de-dup the dedup") so the fix lives in exactly one place.

## Context
The CLI (`src/cli/data.py:106-188`) currently calls `find_duplicate_players` and runs its OWN merge loop — it does not call `dedup_team_players`, so it shares the stale-worklist defect through the two primitives rather than through the orchestrator. E-249-01 fixed the orchestration in a shared planning unit; this story makes the CLI consume it. Per the user decision (epic Technical Notes TN-3), refused forks are surfaced as WARN logs only — no new durable store. The CLI dry-run is the operator's natural review surface, so refused forks must appear in its preview output, not only in the log.

## Acceptance Criteria
- [ ] **AC-1**: Given the `bb data dedup-players` command, when it runs (dry-run or execute), then it consumes the shared component-planning unit from E-249-01 (per Technical Notes TN-4) and contains NO parallel inline `find_duplicate_players` + merge loop.
- [ ] **AC-2**: Given a roster with a single-terminal component and a fork, when `bb data dedup-players --execute` runs, then the single-terminal component collapses (one canonical, combined stats) and the fork is left unmerged with every member surviving — identical collapse/refuse behavior to the load path (per Technical Notes TN-1).
- [ ] **AC-3**: Given a refused fork, when `bb data dedup-players` runs in dry-run, then the preview output lists the refused fork (team + conflicting terminal names) so the operator sees it before executing; when run with `--execute`, then exactly one WARN-level log line is emitted per refused component, per Technical Notes TN-3.
- [ ] **AC-4**: Given the CLI executes merges, when the run completes, then season aggregates are recomputed with the `recompute_aggregates` contract preserved for the CLI path (CLI owns the recompute, per Technical Notes TN-5.4), and `bb report verify-aggregates` reports no mismatch attributable to the merge.
- [ ] **AC-5**: Given a merge raises an error during CLI execute, when the command runs, then the failure is surfaced to the operator (non-zero/reported, not a misleading success) per the Error-Path Testing rule, and the command does not silently report success — covered by a test that forces a merge failure.
- [ ] **AC-6**: Given the CLI executes a multi-member component's merges, when the component is collapsed, then per the per-component transaction footgun in Technical Notes TN-5.3 the component executor owns the transaction/savepoint and the inner per-member merges run with `manage_transaction=False` (the CLI's current bare `merge_player_pair(...)` at `src/cli/data.py:163` defaults to `True` and self-commits per merge, which cannot nest under an outer per-component transaction) — covered by a test asserting no nested-transaction error and a single transaction per component.

## Technical Approach
Replace the inline detection-and-merge block in `src/cli/data.py` (`dedup-players` command, `:106-188`) with a call to the shared planner from E-249-01, rendering its collapse plan and refused-fork list in the existing dry-run preview and execute output. Preserve the CLI's existing presentation (the per-pair table, the per-table preview counts, the summary line) adapted to the plan shape, and keep `recompute_affected_seasons` / the CLI's recompute ownership. Drive each component's merges through a component executor that OWNS the transaction/savepoint and calls the per-member `merge_player_pair(..., manage_transaction=False)` per Technical Notes TN-5.3 — do NOT keep the current bare `manage_transaction=True` self-commit, which both loses per-component atomicity and cannot nest under an outer `BEGIN`. Do not reintroduce orchestration logic in the CLI — the CLI is a thin presentation layer over the shared planner. The exact rendering is the implementer's decision; the binding constraints are in epic Technical Notes TN-1, TN-3, TN-4, TN-5.3, TN-5.4.

## Dependencies
- **Blocked by**: E-249-01 (the shared planning unit must exist)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` (the `dedup-players` command: delegate to the shared planner, render refused forks)
- `tests/` CLI dedup test file(s) — the file(s) covering `bb data dedup-players` (add: delegation/no-inline-loop, dry-run refused-fork surfacing, execute WARN, error-path test, and the per-component transaction AC-6 test). Discover the exact file(s) per the Test Scope Discovery rule, broadened per the DoD below.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (delegation, dry-run refused-fork surfacing, execute WARN, error-path, per-component transaction)
- [ ] Test Scope Discovery per `.claude/rules/testing.md` covering the FULL CLI import surface, not just `tests/test_cli_data.py`: grep `tests/` for importers of `cli.data` AND `cli` (`src/cli/__init__.py:27` imports `data` at module load, so changing `src/cli/data.py` reaches the whole CLI import surface) AND `db.player_dedup`; run all discovered files. Also run the subprocess convention test(s) for the `bb` console entry point (the subprocess smoke tests are not grep-discoverable — included by convention).
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This story is the "de-dup the dedup" consolidation: after it, the connected-components + fork-refusal logic exists in exactly one shared unit, consumed by both the load path (E-249-01) and the CLI (this story). The CLI's subprocess smoke test (`bb --help` style) and any existing `bb data dedup-players` tests must remain green.
