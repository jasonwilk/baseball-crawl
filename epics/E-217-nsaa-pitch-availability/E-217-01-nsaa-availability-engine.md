# E-217-01: NSAA Availability Engine + Bullpen Filtering

## Epic
[E-217: NSAA Pitch Count Availability Rules](epic.md)

## Status
`TODO`

## Description
After this story is complete, the starter prediction engine will use NSAA (Nebraska) pitch count rules instead of ad-hoc heuristics to determine pitcher availability. The two existing exclusion functions (`_is_excluded_within_1_day` and `_is_excluded_high_pitch_short_rest`) will be replaced by a single NSAA-based availability function that checks rest-tier compliance and the consecutive-days rule. The bullpen order will include all bullpen-ranked pitchers but mark unavailable ones with the specific reason. The Tier 2 LLM prompt will include the active NSAA rest table.

## Context
The current exclusion logic has two ad-hoc functions with hardcoded thresholds that don't match NSAA rules. This causes both over-restriction (blocking legal arms like low-pitch relievers who pitched yesterday) and under-restriction (missing the 31-50 pitch / 1-day rest tier entirely). The bullpen order has no availability filtering at all, showing unavailable pitchers as options. Coaches use a two-pass model -- compliance first, then effectiveness -- and need the compliance pass to be correct and visible.

## Acceptance Criteria
- [ ] **AC-1**: Given a pitcher who threw 1-30 pitches yesterday, when `compute_starter_prediction()` runs with `reference_date` = today, then that pitcher is NOT excluded from candidates or bullpen.
- [ ] **AC-2**: Given a pitcher who threw 55 pitches 1 day ago, when `compute_starter_prediction()` runs, then that pitcher IS excluded (NSAA requires 2 days rest for 51-70 pitches). Given a doubleheader where a pitcher threw 25 pitches in game 1 and 30 pitches in game 2 on the same day, then same-day pitch counts are combined (55 total → 51-70 tier → 2 days rest required per Technical Notes).
- [ ] **AC-3**: Given a `reference_date` before April 1, when availability is computed, then the pre-April rest tiers are used (max 90 pitches, 4 tiers per Technical Notes). Given a `reference_date` on or after April 1, then the post-April rest tiers are used (max 110, 5 tiers per Technical Notes).
- [ ] **AC-4**: Given a pitcher who has made 2 or more pitching appearances on reference_date-2 and reference_date-1 combined, when availability is computed, then that pitcher IS excluded regardless of pitch count (NSAA allows max 2 appearances per 3-day period; the window is {ref-2, ref-1, ref}, and 2 prior appearances means pitching on ref would be the 3rd = violation). Appearances are counted individually -- a doubleheader counts as 2 appearances on 1 day.
- [ ] **AC-5**: The bullpen order includes all bullpen-ranked pitchers (available and unavailable). Available pitchers sort first by frequency; unavailable pitchers sort after, also by frequency. Each entry has `available: bool` and `unavailability_reason: str | None` fields. Templates render unavailable pitchers with the `unavailability_reason` text visible in the output (e.g., appended in parentheses or as a subtitle).
- [ ] **AC-6**: The exclusion logic is driven by rule data structures (frozen dataclasses), not hardcoded threshold constants. The old constants `_HIGH_PITCH_EXCLUSION`, `_SHORT_REST_DAYS`, `_WITHIN_1_DAY_REST` and the functions `_is_excluded_within_1_day()`, `_is_excluded_high_pitch_short_rest()` are removed.
- [ ] **AC-7**: The Tier 2 LLM system prompt in `src/reports/llm_analysis.py` includes the active NSAA rest table (selected by `reference_date`). The bullpen formatting in `_format_pitcher_table()` includes availability status and reason for each bullpen entry (e.g., "(unavailable: 1d rest -- needs 2)").
- [ ] **AC-8**: All existing tests pass (with appropriate updates for changed behavior). New tests cover: each rest tier boundary (pre and post April 1), the consecutive-days rule (2 appearances in 3 days = excluded, 1 = not excluded, 2 but outside window = not excluded), doubleheader pitch aggregation, null pitch count handling (including doubleheader partial-null), reliever exclusion (reliever with high pitch count is excluded same as starter), and bullpen available/unavailable sorting.
- [ ] **AC-9**: Given a pitcher whose most recent game date has ANY appearance with a null pitch count (including one game of a doubleheader), when availability is computed, then that pitcher is marked unavailable with reason "pitch count unavailable -- cannot verify eligibility."
- [ ] **AC-10**: The exclusion logic checks ALL pitchers (starters and relievers), not just starters. The current `total_starts == 0` guard (line 585) is removed. A reliever who threw 80 pitches 2 days ago is subject to the same NSAA rest tiers as a starter.

## Technical Approach
The engine currently has two exclusion functions (lines 130-170) and hardcoded constants (lines 41-43). These need to be replaced with NSAA rule data structures and a single availability function, per the data structure and availability function design in epic Technical Notes. The bullpen function (lines 342-371) needs the excluded set threaded through, per the bullpen order enhancement design in Technical Notes. The LLM prompt (in `src/reports/llm_analysis.py`, lines 35-59) needs the active rest table injected.

The existing test file has exclusion-specific tests (~3 methods, ~30 lines) that need rewriting. Integration tests that assert exclusion behavior (e.g., `test_ace_excluded`, `test_ace_excluded_high_pitch`) need updating to use NSAA-valid scenarios. Most existing tests should be unaffected. Use the test scope discovery pattern to find all test files importing from both `starter_prediction` and `llm_analysis` (both modules are modified by this story).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/starter_prediction.py` -- replace exclusion functions, add rule data structures, enhance bullpen order
- `src/reports/llm_analysis.py` -- inject NSAA rest table into Tier 2 system prompt, update bullpen formatting to show availability
- `src/api/templates/reports/scouting_report.html` -- render unavailable bullpen pitchers with visual distinction
- `src/api/templates/dashboard/opponent_detail.html` -- render unavailable bullpen pitchers with visual distinction
- `src/api/templates/dashboard/opponent_print.html` -- render unavailable bullpen pitchers with visual distinction
- `tests/test_starter_prediction.py` -- rewrite exclusion tests, add NSAA-specific tests, update integration tests

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The April 1 boundary should be parameterized by year (derive from `reference_date.year`) for cross-season use. This is scoped to NSAA HS spring season -- fall seasons always yield "post-April" which is correct behavior (post-April rules are more permissive).
- The `_is_excluded_within_1_day` function is fully subsumed by NSAA rest tiers + consecutive-days rule -- it can be deleted entirely.
- Doubleheader handling: the engine receives per-appearance data with `game_date` on each entry. The availability function must sum pitches across all appearances on the same `game_date` before doing the rest-tier lookup. See epic Technical Notes for the distinction between rest-tier aggregation (combine pitches) and consecutive-days counting (individual appearances).
- Both call sites of `_build_bullpen_order()` (suppressed path ~line 560 and main path ~line 716) need the excluded dict parameter added.
