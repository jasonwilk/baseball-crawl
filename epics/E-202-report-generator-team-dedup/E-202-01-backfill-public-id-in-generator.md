# E-202-01: Backfill public_id in Report Generator After Step-3 Match

## Epic
[E-202: Fix Report Generator Team Deduplication Bug](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report generator will backfill `public_id` on a team row when `ensure_team_row` matched via step 3 (name+season_year) and the generator has verified the association via the public API. This prevents the scouting crawler from creating a duplicate team row, ensuring reports display scouting data correctly.

## Context
The report generator calls `ensure_team_row` with `public_id`, `name`, and `season_year`. When step 3 matches (name+season_year, no `public_id` on the existing row), the returned team lacks `public_id`. The downstream scouting crawler independently calls `ensure_team_row` with only `public_id`, misses the existing team, and creates a duplicate. The fix is to backfill `public_id` in the generator's existing force-update block so the crawler's step-2 lookup succeeds.

## Acceptance Criteria
- [ ] **AC-1**: Given a team row exists with `name='Waverly Vikings Varsity 2026'`, `season_year=2026`, `membership_type='tracked'`, and `public_id IS NULL`, when `generate_report("Xj9LlYlJklcl")` runs (passing a bare public_id slug) and the public API returns `name='Waverly Vikings Varsity 2026'`, then the existing team row's `public_id` is updated to `'Xj9LlYlJklcl'`.
- [ ] **AC-2**: Given a team row exists with `name='Waverly Vikings Varsity 2026'`, `season_year=2026`, `membership_type='tracked'`, and `public_id='existing-slug'` (non-NULL), when `generate_report("different-slug")` runs and the public API returns `name='Waverly Vikings Varsity 2026'` (step 2 misses on `'different-slug'`, step 3 matches by name), then the existing team row's `public_id` remains `'existing-slug'` (the `AND public_id IS NULL` guard prevents overwrite).
- [ ] **AC-3**: Given the public API call fails (the `except` block that logs "Could not fetch public team info"), when `generate_report("Xj9LlYlJklcl")` runs, then no `public_id` backfill is attempted (the backfill is inside the `if team_name_from_api:` guard).
- [ ] **AC-4**: Given AC-1's scenario, after the generator's force-update block completes, the team row has `public_id='Xj9LlYlJklcl'` set. *(Test: query the teams table and assert `public_id` equals the input slug. Step-2 dedup behavior is already covered by `tests/test_ensure_team_row.py`; no need to call `ensure_team_row` again here.)*
- [ ] **AC-5**: All existing tests in `tests/test_report_generator.py` and `tests/test_ensure_team_row.py` continue to pass. New tests cover ACs 1-3, AC-4, AC-6.
- [ ] **AC-6**: Given a team row exists with `name='Old Name'`, `season_year=2025`, and `public_id='existing-slug'` (non-NULL), when `generate_report("different-slug")` runs and the public API returns `name='New Name'` and `season_year=2026`, then the team's `name` is updated to `'New Name'` and `season_year` to `2026` -- the `public_id` backfill guard does not interfere with the existing name/season_year force-update.

## Technical Approach
The fix is in `generate_report()` near the existing force-update block (search for `UPDATE teams SET name = ?`) where the generator already unconditionally updates `name` and `season_year` after the public API call succeeds. The `public_id` backfill must be a separate UPDATE (or use conditional SQL) so that the `AND public_id IS NULL` guard does not interfere with the existing unconditional name/season_year update. The existing UPDATE must continue to fire regardless of the team's current `public_id` value. See epic Technical Notes for the rationale and safety analysis.

The test should set up a team row with name+season_year but no `public_id`, mock the public API response, call the generator flow, and verify the `public_id` was backfilled. Then verify a subsequent `ensure_team_row(public_id=...)` call returns the same team ID (no duplicate).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` -- add `public_id` backfill near the existing force-update block (find by searching for `UPDATE teams SET name = ?`)
- `tests/test_report_generator.py` -- add tests for ACs 1-4 and AC-6

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The fix is intentionally minimal (~3-4 lines of production code) to match the focused bug-fix scope.
- SE consultation confirmed this approach is safe and has the lowest blast radius of the options considered.
- The `AND public_id IS NULL` guard is critical -- it prevents overwriting a `public_id` set through a more authoritative path (e.g., authenticated API, GC search resolution).
- Log the `public_id` backfill at INFO level for operator visibility (e.g., "Backfilled public_id=%s on team_id=%d").
