# E-236-05: no_games outcome signal + two-case copy + CLI branch (#5)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, `GenerationResult` will carry an explicit `outcome` signal, the no-games page will distinguish "no games on record" (M=0) from "games played but no scorebook data" (M>0/N=0) with coach-authored copy, and the CLI will treat a shareable `no_games` outcome as success (exit 0 + URL) instead of branding it a hard failure. This closes finding #5.

## Context
The no-games message (`generator.py:1636-1638`, via `render_no_games_page` at `renderer.py:770`) says "No completed games found" even when scored games exist with no scorebook data — the MODAL scouting case. The CLI `generate` (`cli/report.py:60-67`) brands the shareable `no_games` outcome a hard failure (red + exit 1, no URL), while `list_cmd` (`cli/report.py:97-99`) already treats it as linkable. See epic Technical Notes TN-5 (outcome field shape, exact copy, CLI branch, caller inventory) and coach ruling C1 (the verbatim copy).

## Acceptance Criteria
- [ ] **AC-1**: This story SETS `GenerationResult.outcome` values (the field itself is DEFINED in story 01 per Technical Notes TN-5): `outcome="ready"` at the success return (`generator.py:2002`) and `"no_games"` at the no-games return (`generator.py:1641`); all other `success=False` sites inherit the default `"failed"`. `success` semantics are UNCHANGED (no_games stays `success=False`).
- [ ] **AC-2**: The no-games page copy branches on M (`completed_games`) vs N (`completed_games_with_data`) per Technical Notes TN-5:
  - M=0 → `"No games on record for {team_name} this season."`
  - M>0, N=0 → `"{team_name} has played {M} games this season, but no box score data is available in GameChanger."` (interpolates **M**, not N).
- [ ] **AC-3**: The no-games copy does NOT contain "check back later" (negative AC, coach C1 / Technical Notes TN-5).
- [ ] **AC-4**: The CLI `generate` command branches on `outcome`: `no_games` → exit 0 and prints the URL (shareable page); `ready` → unchanged success output; `failed` → exit 1.
- [ ] **AC-5**: Existing callers of `GenerationResult.success` keep working (Technical Notes TN-5 inventory); no_games tests add an `outcome == "no_games"` assertion (the new contract).
- [ ] **AC-6**: An error-path test (testing.md) proves the CLI no longer exits non-zero for a `no_games` outcome and DOES still exit non-zero for a `failed` outcome.

## Technical Approach
The `outcome` field already exists on `GenerationResult` from story 01 (default `"failed"`) — this story only SETS `"ready"` at the success return (`generator.py:2002`) and `"no_games"` at the no-games return (`generator.py:1641`); the other failure sites inherit the default. Pass M and N (or the already-computed counts) into `render_no_games_page` (`renderer.py:770`) so it can branch the copy. Update `cli/report.py` `generate` (`:60-67`) to branch on `outcome`. Note the Epic E forward-context (TN-5): the web admin path (`admin.py:3382`) discards the in-process result, so unattended runs must read outcome from `report_generation_runs.overall_status` — out of scope here, no web change.

## Dependencies
- **Blocked by**: E-236-01, E-236-04
- **Blocks**: E-236-06, E-236-08

## Files to Create or Modify
- `src/reports/generator.py` (modify — SET `outcome` at no-games + success returns [field defined in 01], pass M/N to renderer)
- `src/reports/renderer.py` (modify — `render_no_games_page` two-case copy)
- `src/cli/report.py` (modify — `generate` branches on `outcome`)
- Tests: no-games copy + outcome (modify/add — `test_report_negative_paths`, `test_report_generator`, CLI tests; locate via `grep -rl` per testing.md). Include a subprocess smoke test if the CLI branch logic warrants it (testing.md).

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
SE S1 + coach C1. The `failed` outcome interacts with SQ1 (story 03 / TN-6): the all-blocked case sets `outcome="failed"`.
