# E-236-04: Spray-stage honesty — spray_games_with_data (informational) + error-driven status (#3)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, the run record will carry `spray_games_with_data` (distinct games with spray ROWS actually loaded) alongside the existing `spray_games` (API fetch successes) as an INFORMATIONAL coverage column, and `spray_status` will be ERROR-driven (failed only on a real spray crawl/load failure), NOT coverage-driven. This closes finding #3 (operator-telemetry only — the coach footer spray line is already honest) WITHOUT introducing a false "partial" alarm on the modal scorekeeper-didn't-chart case.

## Context
`_spray_stage` (`generator.py:1689`) sets `spray_games = games_crawled` (API successes); a null `spray_chart_data` response still increments, overstating spray coverage on the run record. Per DE D3, do NOT redefine the live `spray_games` column (silently breaks readers) — ADD `spray_games_with_data` as an INFORMATIONAL coverage column (the gap `spray_games_with_data` vs `spray_games` is operator information, NOT a degradation trigger — see DE F1 below). The coach footer reads actual `spray_charts` rows (`generator.py:1963`), so it is already honest and is NOT touched (coach C3, epic Technical Notes TN-3). See TN-1 (classifier + error-driven guardrail), TN-2 (`spray_games_with_data` column), TN-7 (spray = error-driven status).

## Acceptance Criteria
- [ ] **AC-1**: The run record records `spray_games_with_data` = the count of distinct games with spray ROWS actually loaded (for this team's perspective), distinct from `spray_games` (API fetch successes). `spray_games` is NOT redefined (Technical Notes TN-2/DE D3). `spray_games_with_data` is INFORMATIONAL only — it does NOT drive `spray_status`.
- [ ] **AC-2**: `spray_status` is ERROR-driven per Technical Notes TN-1/TN-7 (spray): derived from the spray crawl/load error signal (`spray_result.errors` at `generator.py:725` and the `_SprayOutcome.status == 'failed'` path), NOT from `spray_games_with_data < spray_games`. A healthy spray stage records `"completed"` regardless of how many games happened to carry chart data.
- [ ] **AC-3**: Given a spray stage where some/all crawled games return null `spray_chart_data` (no rows loaded) but NO error occurred, when the report generates, then `spray_games_with_data < spray_games` (or 0) AND `spray_status == "completed"` — NOT `"partial"`. (Spray is scorekeeper-dependent; a coverage shortfall is the NORMAL multi-game case and must NOT false-alarm — DE F1.)
- [ ] **AC-4**: Given an existing spray CRAWL failure (`_SprayOutcome.status == 'failed'`, `spray_games == 0`), when the report generates, then `spray_status == "failed"` — the failure is mapped BEFORE the classifier so the `expected == 0 → completed` branch does NOT mask it (Technical Notes TN-1 precedence / SE-B; mirrors story 02 AC-4).
- [ ] **AC-5**: The coach footer spray line is unchanged (still reads actual `spray_charts` rows) — no coach-facing change (Technical Notes TN-3).
- [ ] **AC-6**: The `perspective_team_id` filter is applied when counting loaded spray games (per perspective-provenance rule), so cross-perspective rows are not miscounted.

## Technical Approach
Two separable changes: (1) the INFORMATIONAL count — the spray loader's `load_from_data` return is currently discarded (loader path ~line 731 per DE) and `_SprayOutcome` (`generator.py:79`) only carries `games_crawled`; surface a distinct-games-loaded count either via the loader return or a post-load `COUNT(DISTINCT game_id) FROM spray_charts WHERE perspective_team_id = ?` (implementer's choice — DE D3), add `spray_games_with_data` to `_SprayOutcome`, and write it. (2) the STATUS — derive `spray_status` from the spray error signal (`spray_result.errors` / `_SprayOutcome.status`), mapping an existing `status == 'failed'` to `"failed"` BEFORE the classifier (TN-1 precedence). Do NOT key `spray_status` off `spray_games_with_data < spray_games` — that is the false-alarm DE F1 flags.

## Dependencies
- **Blocked by**: E-236-01, E-236-03
- **Blocks**: E-236-05, E-236-07, E-236-08

## Files to Create or Modify
- `src/reports/generator.py` (modify — `_SprayOutcome`, `_spray_stage`)
- `src/gamechanger/loaders/scouting_spray_loader.py` (modify only if surfacing the count via the loader return)
- Spray-stage tests (modify/add — locate via `grep -rl` per testing.md)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
DE D3 + DE F1 (HIGH) + SE-B. Operator-telemetry only; coach footer untouched (coach C3 / TN-3). The status is ERROR-driven, not coverage-driven — this was the most important review finding (four-way convergence); coverage shortfall is the normal scorekeeper-didn't-chart case and must never register as `"partial"`.
