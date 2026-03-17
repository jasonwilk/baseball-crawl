# E-123-05: Two-Way Player Recent Games Fix

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the player profile recent games display will show both batting and pitching data for two-way players who bat and pitch in the same game, instead of dropping the pitching row during deduplication.

## Context
CR1-M7 confirmed that `src/api/db.py:747-752` deduplicates recent games by game ID, preferring the batting row. For a two-way player, the pitching data (ip_outs, er, so_pitched) from that game is lost in the recent games view. Season-level pitching stats are unaffected (separate query). See `/.project/research/full-code-review/cr1-verified.md` (M7) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: `get_player_profile` recent games returns two rows for a two-way game -- one with `appearance_type='batting'` (batting stats) and one with `appearance_type='pitching'` (pitching stats). The template already renders both types as separate list items; the dedup logic must stop collapsing them into one row
- [ ] **AC-2**: Single-role games (batting only or pitching only) continue to work correctly
- [ ] **AC-3**: A test verifies that a two-way player's recent games include two rows for the same game_id -- one batting row and one pitching row, each with the correct stats
- [ ] **AC-4**: All existing tests pass

## Technical Approach
Read `get_player_profile()` in `src/api/db.py` around line 747. The current dedup logic keeps only one row per game. The fix must return both rows (one batting, one pitching) for two-way games, tagged with `appearance_type`, consistent with how the player profile template already renders recent games as separate list items. See TN-5 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py`
- `src/api/templates/dashboard/player_profile.html` (verify template already handles two rows per game -- no changes expected, but listed for awareness)
- `tests/test_dashboard.py` (or appropriate test file for player profile queries)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
