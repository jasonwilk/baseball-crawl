# E-125-03: OBP Formula Correction + Broken Backlink Fix

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the OBP calculation in all dashboard templates will use the correct formula including HBP and SF, and the broken "Back to Team Stats" link on player profile pages will navigate to a valid route. These fixes correct two user-facing bugs that affect coaching decisions and daily navigation.

## Context
**OBP formula** (Review 03 #4): The OBP calculation across all templates uses `(H + BB) / (AB + BB)` instead of the correct `(H + BB + HBP) / (AB + BB + HBP + SF)`. This systematically understates OBP for players who get hit by pitches -- a meaningful coaching metric error. The `player_season_batting` table has `hbp` and `shf` columns, but the DB queries don't fetch them and the templates don't use them.

**Broken backlink** (Review 03 #3): The player profile template links to `/dashboard/stats` which does not exist. The correct route is `/dashboard`. This produces a 404 for every user who clicks "Back to Team Stats."

## Acceptance Criteria
- [ ] **AC-1**: OBP in `team_stats.html` is calculated as `(H + BB + HBP) / (AB + BB + HBP + SF)`
- [ ] **AC-2**: OBP in `opponent_detail.html` is calculated as `(H + BB + HBP) / (AB + BB + HBP + SF)`
- [ ] **AC-3**: OBP in `player_profile.html` (both occurrences) is calculated as `(H + BB + HBP) / (AB + BB + HBP + SF)`
- [ ] **AC-4**: The DB queries in `src/api/db.py` that feed these templates SELECT `hbp` and `shf` columns, using `COALESCE(hbp, 0)` and `COALESCE(shf, 0)` so NULL values are returned as 0 to the templates
- [ ] **AC-5**: The "Back to Team Stats" link in `player_profile.html` navigates to `/dashboard` (with `team_id` param preserved where present), not `/dashboard/stats`
- [ ] **AC-6**: Tests verify the corrected OBP calculation produces expected values (e.g., a player with 1 HBP gets a higher OBP than the old formula would produce)
- [ ] **AC-7**: Template OBP calculations use COALESCE (or equivalent) to treat NULL `hbp` and `shf` values as 0, per TN-9
- [ ] **AC-8**: If the OBP denominator (AB + BB + HBP + SF) equals zero, the template displays "—" instead of a numeric value or a division error, per TN-9
- [ ] **AC-9**: All existing tests pass

## Technical Approach
Per Technical Notes TN-3: Four template files need the OBP formula update. The DB query functions in `src/api/db.py` (around lines 78-92 per the review) need `hbp` and `shf` added to their SELECT lists. The backlink fix is a simple URL change in `player_profile.html` (lines 22 and 26 per the review).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` (add hbp, shf to SELECT queries)
- `src/api/templates/dashboard/team_stats.html` (OBP formula)
- `src/api/templates/dashboard/opponent_detail.html` (OBP formula)
- `src/api/templates/dashboard/player_profile.html` (OBP formula x2, backlink URL)
- `tests/test_dashboard.py` or new test file (OBP calculation test, backlink test)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The reviewer confirmed SLG is correct (the `h + doubles + 2*triples + 3*hr` formula works because h = total hits). Only OBP needs fixing.
- The `shf` column name in the schema corresponds to "sacrifice flies" (SF in baseball notation).
- Per baseball-coach consultation (TN-9): NULL `hbp`/`shf` means "not reported" (older games, incomplete boxscores), not zero events. COALESCE is mandatory. Zero-denominator guard prevents display bugs for players with no plate appearances.
