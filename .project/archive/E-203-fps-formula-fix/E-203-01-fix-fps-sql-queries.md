# E-203-01: Fix FPS% SQL Queries in Report Generator

## Epic
[E-203: Fix FPS% Formula to Match GameChanger](epic.md)

## Status
`DONE`

## Description
After this story is complete, both FPS% queries in the report generator will use `FPS / BF` (total batters faced) as the denominator instead of excluding HBP and Intentional Walk plate appearances. This aligns our standalone reports with GameChanger's FPS% calculation, eliminating the systematic overstatement that confuses coaches cross-referencing our reports against the GC app.

## Context
Two SQL queries in `src/reports/generator.py` use `CASE WHEN p.outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` to exclude HBP/IBB from both the FPS numerator and denominator. GameChanger counts all batters faced in the denominator. The fix simplifies both queries. Existing tests in `tests/test_report_plays.py` assert the old exclusion behavior and must be updated to match.

## Acceptance Criteria
- [ ] **AC-1**: Given a pitcher with HBP and IBB plate appearances, when `_query_plays_pitching_stats()` computes FPS%, then the HBP/IBB exclusion is removed from both numerator and denominator -- FPS% = `SUM(is_first_pitch_strike) / COUNT(*)` over all PAs.
- [ ] **AC-2**: Given a team's pitching staff with HBP and IBB plate appearances, when `_query_plays_team_stats()` computes team FPS%, then the HBP/IBB exclusion is removed from both numerator and denominator -- same formula as AC-1.
- [ ] **AC-3**: Tests in `tests/test_report_plays.py` that previously asserted HBP/IBB exclusion are updated to assert the new `FPS / BF` formula.
- [ ] **AC-4**: No regressions -- full test suite passes.

## Technical Approach
Two queries in `src/reports/generator.py` contain `CASE WHEN p.outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` exclusion logic on both the numerator and denominator columns. Both need the exclusion removed so the denominator counts all PAs. The epic's Technical Notes section "Affected Queries" identifies both locations and line numbers. The "Test Updates" section identifies which test methods assert the old behavior.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-203-02

## Files to Create or Modify
- `src/reports/generator.py` (modify two SQL queries)
- `tests/test_report_plays.py` (update FPS% exclusion tests)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `is_first_pitch_strike` flag in the plays parser is correct and must NOT be changed.
- After this fix, a residual ~0.5-1.5pp gap vs GC may remain due to plays endpoint data limitations -- this is expected and acceptable.
