# E-189-04: Add PA/IP badges and heat-map coloring to dashboard opponent detail

## Epic
[E-189: Opponent Flow Pipeline and Display Parity](epic.md)

## Status
`TODO`

## Description
After this story is complete, the dashboard opponent detail page will display PA badges on batting rows, IP badges on pitching rows, and graduated heat-map coloring on rate stats -- matching the standalone reports' display quality and following the "never suppress, always contextualize" display philosophy from `.claude/rules/display-philosophy.md`.

## Context
The dashboard opponent detail template (`opponent_detail.html`) currently shows GP annotations on rate stats (e.g., "(3 GP)" next to ERA) but no PA/IP badges and no heat-map coloring. The standalone reports (produced by E-185/E-187) have graduated heat intensity tiers and PA/IP badges. The display philosophy rule fires on this template. All necessary data (AB, BB, HBP, SHF for PA; ip_outs for IP) is already in the template context from `get_opponent_scouting_report`. Heat-map computation logic already exists in `src/reports/renderer.py` (functions: `_max_heat_for_depth`, `_percentile_rank`, `_percentile_to_level`, `_compute_pa`, plus tier constants `_BATTING_HEAT_TIERS` and `_PITCHING_HEAT_TIERS`). The implementer may extract shared utilities or reimplement for the dashboard route.

## Acceptance Criteria
- [ ] **AC-1**: Each batting row displays a PA badge showing the player's plate appearances (PA = AB + BB + HBP + SHF) replacing the current GP annotation on rate stats (AVG, OBP, SLG)
- [ ] **AC-2**: Each pitching row displays an IP badge showing the player's innings pitched (using the existing `ip_display` filter) replacing the current GP annotation on rate stats (ERA, K/9, WHIP)
- [ ] **AC-3**: Batting rate stat cells (AVG, OBP, SLG) have graduated heat-map background coloring per the tiers in `.claude/rules/display-philosophy.md` (5 PA threshold, 0-2 qualified = no heat, scaled up to 9+ = full heat)
- [ ] **AC-4**: Pitching rate stat cells (ERA, K/9, WHIP) have graduated heat-map background coloring per the tiers in `.claude/rules/display-philosophy.md` (6 IP / 18 outs threshold, 0-1 qualified = no heat, scaled up to 6+ = full heat)
- [ ] **AC-5**: The "Their Pitchers" summary card at the top also shows IP badges (not GP) next to rate stats
- [ ] **AC-6**: The print view (`opponent_print.html`) displays PA/IP badges but does NOT require heat-map coloring (plain black-on-white is acceptable for print)
- [ ] **AC-7**: No stats are suppressed, dimmed, or hidden based on sample size per the display philosophy rule's prohibited patterns

## Technical Approach
The route function (`opponent_detail` in `src/api/routes/dashboard.py`) must compute per-player heat levels and the max-heat tier for the team before passing to the template. The computation follows the graduated heat intensity tiers from the display philosophy rule. PA is computed in the route (or template) from existing fields. The template replaces GP annotations with PA/IP badges and adds CSS classes for heat-map background colors (using inline Tailwind classes or a small set of heat-level utility classes).

Heat-map color palette should be consistent with standalone reports (green spectrum for positive stats like OBP/K9, red spectrum for negative stats like ERA/BB9). The exact CSS classes are an implementation decision.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/dashboard.py` -- compute heat levels and PA values in `opponent_detail` route
- `src/api/templates/dashboard/opponent_detail.html` -- add PA/IP badges, heat-map CSS classes
- `src/api/templates/dashboard/opponent_print.html` -- add PA/IP badges (no heat-map)
- `tests/test_dashboard_opponent_detail.py` -- add/update tests for PA/IP badges and heat levels in template context

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
