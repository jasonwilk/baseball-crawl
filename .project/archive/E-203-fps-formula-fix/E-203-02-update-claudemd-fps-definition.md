# E-203-02: Update CLAUDE.md FPS% Definition

## Epic
[E-203: Fix FPS% Formula to Match GameChanger](epic.md)

## Status
`DONE`

## Description
After this story is complete, the FPS% definition in CLAUDE.md will accurately reflect the implemented formula (`FPS / BF` with no query-time exclusions), matching GameChanger's calculation. This ensures agents and contributors understand the correct formula when working with FPS% in the codebase.

## Context
CLAUDE.md line 66 defines FPS% with language about query-time exclusions: `exclusions (HBP, Intentional Walk) applied at query time only (WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk'))`. After E-203-01 removes these exclusions from the queries, this definition becomes inaccurate. CLAUDE.md must describe current implemented reality, not historical behavior.

## Acceptance Criteria
- [ ] **AC-1**: The FPS% definition in CLAUDE.md states that FPS% is computed as `FPS / BF` (total batters faced as denominator) with no query-time exclusions.
- [ ] **AC-2**: The `is_first_pitch_strike` flag description is unchanged -- it still records the actual first-pitch result for ALL PAs (the flag is correct; only the query formula changed).
- [ ] **AC-3**: The update mentions that this matches GameChanger's calculation method.

## Technical Approach
The FPS% bullet point in CLAUDE.md's "Key Metrics We Track" section needs the exclusion language removed and replaced with a statement that FPS% uses total BF as denominator, matching GameChanger. The `is_first_pitch_strike` flag description (which says the flag records results for ALL PAs) remains correct and should not be changed.

## Dependencies
- **Blocked by**: E-203-01 (CLAUDE.md describes implemented reality; update after the code changes)
- **Blocks**: None

## Files to Create or Modify
- `CLAUDE.md` (modify FPS% definition in Key Metrics section)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- documentation-only change)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- This is a context-layer file, so it routes to claude-architect per agent-routing.md.
- The change is small -- one bullet point update. No other CLAUDE.md sections reference the exclusion formula.
