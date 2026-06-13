# E-234-02: Aggregate parity module + `bb report verify-aggregates`

## Epic
[E-234: Report Regression Guards](epic.md)

## Status
`TODO`

## Description
After this story is complete, a reusable parity function in `src/reports/aggregate_parity.py` diffs stored `player_season_*` aggregate rows against a perspective-filtered recompute from `player_game_*`, an operator command `bb report verify-aggregates` invokes it, and a test asserts it returns an empty mismatch list on a purpose-built rollup-consistent fixture (`tests/fixtures/parity_consistent.sql`). This module doubles as the Epic C cutover gate.

## Context
Stored season aggregates can silently diverge from their source per-game rows (ROADMAP §2: player-dedup merges that run after aggregation; any post-load mutation). The parity guard makes that divergence detectable. Two writers populate `player_season_*` with different semantics, so the diff must be scoped carefully to avoid false positives — see Technical Notes §TN-2 for the row-scope discriminator, the exact column set, the perspective mirror, the `gs` NULL-safe trap, and the staleness-is-a-real-finding rule. Home (SE+DE aligned): logic in `src/`, operator entry under `bb report` (not the quarantined `bb data`).

## Acceptance Criteria
- [ ] **AC-1**: `src/reports/aggregate_parity.py` exposes a function that, given a DB connection, recomputes batting and pitching season aggregates from `player_game_*` and diffs them against stored `player_season_*` rows, scoped to `stat_completeness = 'boxscore_only'` rows and the SUM-column subsets defined in Technical Notes §TN-2 (batting 16 cols; pitching 14 cols, excluding pitching `hr`).
- [ ] **AC-2**: The recompute mirrors `ScoutingLoader._compute_*_aggregates` exactly — perspective filter (`perspective_team_id = team_id`), `JOIN games` on `season_id`, `GROUP BY player_id`, and the verbatim `gs` NULL-safe CASE — with `NULL == NULL` treated as a match, per Technical Notes §TN-2.
- [ ] **AC-3**: Mismatches are returned per `(player_id, team_id, season_id, column)` with `(stored, recomputed)` values, using exact integer equality (no tolerance); a clean DB returns an empty list; the function also returns a `cells_compared` count (rows examined × diffed columns), per Technical Notes §TN-2.
- [ ] **AC-4**: `bb report verify-aggregates` invokes the module and reports mismatches to the operator (non-empty → visible non-zero/flagged outcome; empty → clean success message). The command lives under `bb report`, not `bb data`.
- [ ] **AC-5**: A test imports the `src/reports/aggregate_parity.py` function directly and (a) asserts an EMPTY mismatch list against the purpose-built `tests/fixtures/parity_consistent.sql` fixture (rollup-consistent by construction, NOT seed.sql, no staleness encoded as expected); (b) asserts `cells_compared > 0` on that run (vacuous-pass guard); and (c) asserts an injected divergence — mutating PP_01's stored `gs` from 1 to 5 — is reported as exactly one mismatch `(PP_01, gs, stored=5, recomputed=1)`, per Technical Notes §TN-2.
- [ ] **AC-6**: No change to existing reports-pipeline behavior — new module, new subcommand, and new test only. The recompute is read-only; it does not write to `player_season_*`.

## Technical Approach
Copy each loader aggregate query (minus the INSERT) as the recompute side; select the stored side filtered to `boxscore_only`; diff column-by-column over the defined subset. Keep the result a plain list of dataclasses/dicts. Wire a thin Typer command in `src/cli/report.py` that prints the result. All semantics are specified in Technical Notes §TN-2 — follow it exactly, especially the `gs` CASE and the column exclusions.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/aggregate_parity.py` (new)
- `src/cli/report.py` (modify — add `verify-aggregates` command)
- `tests/fixtures/parity_consistent.sql` (new — purpose-built rollup-consistent parity fixture; values in Technical Notes §TN-2)
- `tests/test_aggregate_parity.py` (new)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for Epic C**: this module is the aggregate-integrity cutover gate referenced in ROADMAP §5 Epic C — a stable `bb report verify-aggregates` operator command to run against a production DB copy before the payload-first loader cutover.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
DE owns the parity semantics (consultation incorporated into §TN-2). SE concurred on the `src/reports/` home and `bb report` entry point. Subcommand name `verify-aggregates` is RESOLVED — approved by team-lead in Phase 3; user retains veto at READY presentation.
