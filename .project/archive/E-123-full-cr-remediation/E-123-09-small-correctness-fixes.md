# E-123-09: Small Correctness Fixes (Season Default, Display, XSS)

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, three small correctness issues will be fixed: the hardcoded season default will be dynamic, the `_human_size()` function will display fractional values correctly, and the admin user delete confirmation will use safe JS escaping.

## Context
Three small, independent fixes bundled because each is <10 lines:

1. **CR4-M8**: `src/api/db.py:59` hardcodes `season_id = "2026-spring-hs"` as the default. Same at line 143. This will break next season. See `/.project/research/full-code-review/cr4-verified.md` (M-8).

2. **CR5-H3**: `src/cli/status.py:34` uses integer division (`//= 1024`) in `_human_size()`, producing "2.0 MB" when the correct value is "2.4 MB". See `/.project/research/full-code-review/cr5-verified.md` (H-3).

3. **CR1-C3**: `src/api/templates/admin/users.html:57` puts `{{ user.email }}` in an inline JS string within an HTML attribute. Jinja2 auto-escaping covers HTML context but not JS string breakout. The fix is to use `|tojson` filter or a `data-*` attribute pattern. See `/.project/research/full-code-review/cr1-verified.md` (C3).

## Acceptance Criteria
- [ ] **AC-1**: `get_team_batting_stats` and `get_team_pitching_stats` default `season_id` is derived dynamically by querying the most recent `season_id` from the `seasons` table (e.g., `SELECT season_id FROM seasons ORDER BY season_id DESC LIMIT 1`) rather than hardcoded to `"2026-spring-hs"`. A test verifies that calling these functions without an explicit `season_id` uses the most recent season
- [ ] **AC-2**: `_human_size()` uses float division, producing correct fractional display (e.g., 2,560,000 bytes → "2.4 MB" not "2.0 MB")
- [ ] **AC-3**: The admin user delete confirmation escapes `user.email` safely for JavaScript context (e.g., `|tojson` filter or `data-*` attribute approach)
- [ ] **AC-4**: A test verifies `_human_size()` returns correct fractional values
- [ ] **AC-5**: All existing tests pass

## Technical Approach
For the season default: read the current functions in `src/api/db.py` and replace the hardcoded value with a query for the most recent `season_id` from the `seasons` table. For `_human_size`: change `//=` to `/=` (or use float division). For the XSS fix: change `{{ user.email }}` to `{{ user.email|tojson }}` in the JS context, or move the value to a `data-email` attribute and read it in JS. See TN-9 in the epic for verified findings references.

## Dependencies
- **Blocked by**: E-123-05 (both modify `src/api/db.py`)
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py`
- `src/cli/status.py`
- `src/api/templates/admin/users.html`
- `tests/test_cli_status.py` (or add to existing CLI test file)
- `tests/test_db.py` (or appropriate test file -- test that stat functions called without `season_id` use the most recent season)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The season default fix in `src/api/db.py` touches the same file as E-123-05 (two-way player fix), but different functions (`get_team_batting_stats`/`get_team_pitching_stats` vs `get_player_profile`). Low conflict risk but noted for dispatch awareness.
