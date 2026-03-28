# E-169-02: Fallback Display for Unresolved Player Names

## Epic
[E-169: Fix Unknown Player Names in Scouting Data](epic.md)

## Status
`DONE`

## Description
After this story is complete, any remaining players whose names could not be resolved will display as "Player #NN" (using jersey number) or "Unknown Player" (no jersey number) instead of "Unknown Unknown". These entries will have muted, italic visual styling to signal provisional data to coaching staff. The display name cascade is computed in the data/view layer, keeping template logic minimal.

## Context
Story E-169-01 eliminates the vast majority of "Unknown Unknown" entries by extracting names from boxscore data. However, edge cases may persist — players appearing in spray chart data before their boxscore is loaded, or truly orphaned player_ids with no name source. This story provides a coach-friendly fallback display per the UXD consultation recommendations. The fallback cascade and visual treatment are defined in the epic's Technical Notes (Fallback Display Cascade section).

## Acceptance Criteria
- [ ] **AC-1**: Given a player with `first_name='Unknown'` and `last_name='Unknown'` who has a `jersey_number` in `team_rosters`, when the player appears on any opponent scouting page, then the display name is "Player #NN" (where NN is the jersey number). Exception: the top pitchers card already renders a `#NN` prefix, so unresolved names there display only the jersey number (not "Player #NN") per the top pitchers card exception in Technical Notes.
- [ ] **AC-2**: Given a player with `first_name='Unknown'` and `last_name='Unknown'` who has NO `jersey_number`, when the player appears on any opponent scouting page, then the display name is "Unknown Player".
- [ ] **AC-3**: Given an unresolved player name on an HTML dashboard page, the name is rendered with `text-gray-500 italic` styling (without `font-medium`) to visually distinguish it from resolved names. On the print view (`opponent_print.html`), which uses inline styles rather than Tailwind, the equivalent muted/italic treatment is applied via inline CSS.
- [ ] **AC-4**: The fallback display is consistent across all surfaces where opponent player names appear:
  - Opponent detail page (`opponent_detail.html`): season batting table, season pitching table, top pitchers card
  - Opponent print view (`opponent_print.html`): print batting/pitching tables AND Batter Tendencies cards (line 334 renders `player.name`)
  - Game detail page (`game_detail.html`): per-game boxscore batting/pitching lines
- [ ] **AC-5**: Given a player with a resolved real name, when the player appears on any page, then the display is unchanged from current behavior (no visual treatment changes for resolved names).

## Technical Approach
The display name cascade belongs in the data layer. Both the batting and pitching queries in `src/api/db.py` (`get_opponent_scouting_report()`, lines 636-691) already construct `name` as `p.first_name || ' ' || p.last_name` and already LEFT JOIN `team_rosters` returning `jersey_number`. The cascade (real name → "Player #NN" → "Unknown Player") and a boolean flag (e.g., `name_unresolved`) can be applied either in the SQL (CASE WHEN) or as post-processing of query results. Templates use the flag for conditional CSS class application — a single class toggle. The game detail boxscore query (`get_game_box_score()`) may need similar treatment.

## Dependencies
- **Blocked by**: E-169-01 (establishes the name extraction pattern; remaining "Unknown" rows are the input for this story's fallback)
- **Blocks**: None

## Files to Create or Modify
- `src/api/db.py` — display name cascade in scouting report queries (or post-query transform)
- `src/api/templates/dashboard/opponent_detail.html` — conditional CSS classes for unresolved names in batting/pitching tables and top pitchers card
- `src/api/templates/dashboard/opponent_print.html` — fallback display with inline CSS (not Tailwind)
- `src/api/templates/dashboard/game_detail.html` — fallback display in per-game boxscore lines
- `src/api/routes/dashboard.py` — cascade application for game detail route (if not handled in db.py)
- `tests/test_dashboard_opponent_detail.py` (or appropriate existing test file) — tests for the display name cascade logic

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The top pitchers card already renders `#{{ pitcher.jersey_number }}` as a prefix — when the name is unresolved, render just the jersey number (avoid "Player #23" redundancy with the existing prefix)
- Spray chart PNG images (`src/charts/spray.py`) do NOT render player names — `render_spray_chart()` takes `(events, title)` only. No chart renderer changes needed. The print template spray chart alt text is static (`alt="Spray chart"`, line 338) — not player name dependent.
- Print view (`opponent_print.html`) uses inline styles, not Tailwind classes — use inline CSS for the muted/italic treatment (e.g., `style="color: #6b7280; font-style: italic"`)
- Game detail page (`game_detail.html`) wraps player names in links to `/dashboard/players/...` (lines 78, 123). For unresolved player names, render as plain text (no `<a>` link) with muted/italic styling — linking to a player profile that returns 403 for opponent players is broken UX.
- The number of affected players should drop to near-zero after E-169-01; this story handles the remaining edge cases
