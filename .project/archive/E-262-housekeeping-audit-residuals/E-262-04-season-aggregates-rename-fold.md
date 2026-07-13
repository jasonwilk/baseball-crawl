# E-262-04: Rename/Fold season_aggregates.py Post-Cutover

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`DONE`

## Description
After this story is complete, the misnamed `src/db/season_aggregates.py` module no longer misleads: post-E-259, it computes nothing — it only holds the SUM projection its sole reader consumes — so it is renamed or folded next to that reader, removing the "where are aggregates computed?" orientation trap.

## Context
IDEA-113. After E-259's query-time cutover, `src/db/season_aggregates.py` no longer computes or writes season aggregates — the DELETE+INSERT recompute driver (`canonical_recompute`) was deleted. What survives is the projection SQL builders (`batting_recompute_select()` / `pitching_recompute_select()`) and the `*_RECOMPUTE_KEYS` tuples, consumed only by the query-time readers `get_season_batting` / `get_season_pitching` in `src/api/db.py`. A module named `season_aggregates.py` whose only job is to hand a reader a SUM projection is an orientation trap. Co-locating the projection with its sole consumer also tightens the "exactly one SUM projection" invariant E-259 established.

This is a mechanical rename/fold with no behavior change — the code is correct as-is; only its name and location mislead.

## Acceptance Criteria
- [ ] **AC-1**: Given the season-projection helpers (the `*_recompute_select` builders and `*_RECOMPUTE_KEYS` tuples), when they are located, then they either live in a module whose name reflects "projection for the query-time reader" (not "aggregates that are computed") or are folded into `src/api/db.py` next to `get_season_batting` / `get_season_pitching`.
- [ ] **AC-2**: Given the rename/fold, when the codebase is checked, then no stale import of the old module path or name remains (all importers updated), and the season-aggregate query behavior is unchanged.
- [ ] **AC-3**: The full test suite passes with no behavior change to season-total queries.

## Technical Approach
A mechanical rename-or-fold of `src/db/season_aggregates.py`. The implementer decides between renaming the module in place vs. folding the surviving builders + KEYS tuples into `src/api/db.py` (IDEA-113 open questions weigh both, and whether the `*_recompute_*` symbol names are renamed for clarity or kept for git-blame continuity). First confirm the full importer set post-E-259-02 so the blast radius is known before moving anything. No schema migration — code only.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/season_aggregates.py` (rename or empty/fold)
- `src/api/db.py` (the sole real importer — `get_season_batting`/`get_season_pitching`)
- `tests/test_season_projection.py` (imports the KEYS + select builders)
- `tests/test_season_query_cutover.py`, `tests/test_gs_mixed_appearance_order.py` (docstring/comment refs to the module path)
- `tests/fixtures/parity_consistent.sql` (comment ref to the module path)
- (Importer surface verified by SE + Codex; the implementer re-greps `tests/` + `src/` for any additional reference per `.claude/rules/testing.md` Test Scope Discovery before renaming.)

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Source: IDEA-113 (surfaced by data-engineer in the E-259 holistic review, deliberately kept out of E-259 to avoid enlarging the cutover diff). Anchors: `src/db/season_aggregates.py`, `src/api/db.py`.
