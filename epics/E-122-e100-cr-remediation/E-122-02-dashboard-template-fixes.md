# E-122-02: Dashboard Template Fixes — Phantom HR Column + Opponent Back-Link

## Epic
[E-122: E-100 Family Code Review Remediation (Wave 2)](epic.md)

## Status
`TODO`

## Description
After this story is complete, the game detail pitching table will no longer show a phantom HR column (which has no backing data), and the opponent detail page back-link will preserve `team_id` context so users don't lose their team filter when navigating back.

## Context
Two confirmed template issues from the E-100 family code review:

**CR-3-2**: `game_detail.html` renders an HR column header (line 113) and `{{ pitcher.hr }}` (line 129) in the pitching table, but `player_game_pitching` has no `hr` column. The value always renders as empty/zero. E-117-01 AC-13 removes `_PlayerPitching.hr` from the loader dataclass but does not touch the template.

**CR-3-W5**: `opponent_detail.html` line 21 links to `/dashboard/opponents` without preserving `team_id`. The opponents list page filters by `team_id` from query params, so clicking back loses team context. See `/.project/research/cr-e100-family/verified-findings.md` for line numbers.

## Acceptance Criteria
- [ ] **AC-1**: `game_detail.html` pitching table does not contain an HR column header or HR data cell.
- [ ] **AC-2**: The pitching query in the dashboard route does not select or return an `hr` field for pitchers. *(Pre-satisfied: `src/api/db.py` pitching_query already omits `hr`. Verify only — no code change needed.)*
- [ ] **AC-3**: `opponent_detail.html` back-link to the opponents list includes `?team_id={{ active_team_id }}` (or equivalent context parameter used by the opponents list route).
- [ ] **AC-4**: All existing tests pass.

## Technical Approach
Template-only changes for AC-1 and AC-3. For AC-2, check whether the dashboard route's pitching query returns an `hr` field — if it does, remove it; if not, AC-2 is satisfied by the template fix alone. See `/.project/research/cr-e100-family/verified-findings.md` findings CR-3-2 and CR-3-W5 for exact line references.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/dashboard/game_detail.html`
- `src/api/templates/dashboard/opponent_detail.html`
- `src/api/routes/dashboard.py` (if pitching query returns `hr`)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (if applicable — template changes may only need manual verification or existing test coverage)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
