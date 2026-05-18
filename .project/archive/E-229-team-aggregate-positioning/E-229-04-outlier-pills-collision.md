# E-229-04: Outlier batter pills — jersey lookup + collision jitter

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, the card field SVG generator from E-229-03 renders numbered jersey pills for each outlier batter (`zone_id IS NOT NULL AND is_thin = 0`) at the batter's specific deviation-projected position relative to the star. Jersey numbers come from a `team_rosters` JOIN with a last-initial fallback when the jersey is NULL. When two pills land within ε of each other, the renderer applies deterministic radial jitter with stable angular order keyed on jersey number.

## Context
DE round-2 flagged that marker collision is a real engineering concern — pills overlapping at near-identical field positions makes them illegible. DE recommended deterministic radial jitter (not a random offset) so the same input always produces the same output, with stable angular ordering keyed on jersey number so visually adjacent pills appear in a predictable rotation. DE also clarified that collision logic is pure render-layer — the engine emits raw deviation values; the renderer projects to SVG and resolves collisions (epic TN-10).

UXD round-1 specified that the pill is the disambiguator: each batter marker carries a small numbered pill (rounded rect with jersey in bold), not an anonymous dot. The fielder hears "#7 — LF Zone B" from the coach and finds the labeled pill on the card.

Jersey number lives in `team_rosters`. Per DE round-2 it's already populated; renderer does a JOIN at render time. Fallback if NULL: last initial of player name (so the card still yells something).

## Acceptance Criteria
- [ ] **AC-1**: For each batter in `batter_positioning` for the (opponent, position) with `zone_id IS NOT NULL AND is_thin = 0`, a numbered pill is rendered at the batter's projected SVG position. **Projection formula per epic TN-15 SVG coordinate convention**: `pill_x = star_x + direction_deviation * scale_x; pill_y = star_y + (-depth_deviation) * scale_y`. The y-axis negation is the canonical convention adjustment (`y=0 at deep CF; y increases toward home plate`). The `scale_x` and `scale_y` factors (pixels per ordinal-bucket unit) are consumed from the locked-constants artifact per E-229-2b.
- [ ] **AC-2**: Pill displays the batter's jersey number + truncated last name from `team_rosters` and `players` via the JOIN pattern in epic TN-7: `batter_positioning JOIN team_rosters USING (team_id, player_id, season_id) JOIN players USING (player_id)`. Pill text format: `#<jersey>` followed by last name truncated to ~6 chars (e.g., `#7 RAMIR` for `RAMIREZ`). **NULL-jersey fallback format consumed from `/.project/research/E-229-locked-layout-constants.md` §B "Outlier pill — NULL-jersey fallback"** (per the citation pattern + AC-3 precedent; the locked artifact is the canonical source for the fallback text rendering, superseding any earlier inline example in this AC's prior drafts). The truncated last name aids in-game identification when coach pairs the verbal call with the visual lookup (per UXD M-4).
- [ ] **AC-3**: Pill style consumed from the locked-constants artifact per E-229-2b (fill, border weight, font face/size/weight, padding, corner radius, minimum/auto-width sizing rule). UXD round-1 estimates (white fill, 0.5pt grey border, 9pt bold black text, ~0.18"×0.14", 2pt corner radius) live in the artifact as PROVISIONAL initial values; E-229-2b validates them at print scale and either confirms or refines. This story does NOT name specific numeric values for pill styling — they come from the artifact at impl time.
- [ ] **AC-4**: Marker collision: when two pills' projected positions land within a collision-radius `ε` of each other in SVG space, the renderer applies deterministic radial jitter. The jitter is keyed on jersey number (sorted ascending). **Ordering convention**: pill 0 (lowest jersey) anchors at the collision centroid; subsequent pills (in jersey-ascending order) rotate clockwise around the centroid at 60° angular intervals from 0° (where 0° is "topmost" in SVG space — straight up from the centroid). Same input always produces the same output.
- [ ] **AC-5**: Z-order is preserved: pills layer on top of the density background, the textbook dot, the star, and the compass letters. Pills do NOT obscure the legend or header.
- [ ] **AC-6**: Pills are NOT rendered for batters with `is_thin = 1` (total BIP < 10 thin gate per epic TN-5). Pills are NOT rendered for batters with `zone_id IS NULL` (at-star batters; the field plot's neutral point already conveys their position).
- [ ] **AC-7**: Tests cover: (a) deterministic jitter — same inputs produce same SVG twice in a row; (b) stable angular order — varying jersey numbers in input produces predictable angular layout per AC-4's ordering convention; (c) jersey JOIN + last-name JOIN + last-initial fallback when `jersey_number` is NULL; (d) z-order layering; (e) thin-gate / null-zone exclusion.
- [ ] **AC-8** (coord-system regression test per DE P1.1 + epic TN-15): Given a batter at position `LF` with `team_position_aggregate.(star_x, star_y) = (160, 240)` and `batter_positioning.(direction_deviation, depth_deviation) = (-1, -1)` (in+left = Zone A), assert the rendered pill's SVG `x < star_x` AND `y > star_y` (lower-left of star). Given a batter at the same position with `(direction_deviation, depth_deviation) = (+1, +1)` (deep+right = Zone H), assert the rendered pill's SVG `x > star_x` AND `y < star_y` (upper-right of star). Two-fixture test, four assertions. **Purpose**: lock the projection contract so a future regression that flips the depth-axis sign (`y_offset = +depth_dev * scale_y` instead of `-depth_dev * scale_y`) is caught by CI.

## Technical Approach

**Pill placement projection**: given the engine's ordinal `(direction_deviation, depth_deviation)` for a batter at a position, project to SVG coordinates relative to that position's star. The projection multiplier (how far ±1 / ±2 ordinal bucket pushes the pill) is a render-layer tuning constant — initially set so a ±1 bucket pill sits halfway between the star and the field edge, and ±2 sits near the edge.

**Collision detection**: O(n²) over the (typically small, ≤15) pills per card is fine. Collision-radius `ε` is a render-layer constant; initial value ~ 1.5x the pill width.

**Deterministic jitter**: when a collision is detected, sort the colliding pills by jersey number (ascending). Place pill 0 at the collision centroid, pill 1 offset by `r * (cos θ, sin θ)` at angle 0°, pill 2 at 60° (or 90°), pill 3 at 120° (or 180°), etc. Jitter radius `r` is small enough that pills remain visually associated with the original position but distinct enough to be individually labeled.

**Jersey JOIN with fallback**: extend the render-layer data-fetch function to JOIN `team_rosters`. If `jersey_number IS NULL` in the result, compute last-initial from `players.name` (or wherever the player name lives).

**Test fixtures**: include deliberate near-collision cases so the jitter logic is exercised. Snapshot tests verify the resulting SVG is stable.

## Dependencies
- **Blocked by**: E-229-03 (the field SVG generator is the surface this story extends), E-229-2b (pill style spec consumed from locked-constants artifact §B per Codex iter-3 P2.4 lock; AC-3 cites the artifact)
- **Blocks**: E-229-05 (the compact card template integrates the pills into the layout)

## Files to Create or Modify
- `src/reports/positioning_card.py` — modify (inherits E-229-03's module placement per CR M3)
- `tests/test_positioning_card_render.py` — extend (add pill + collision tests)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-229-05**: a complete per-position field SVG (star + textbook dot + density bg + compass letters + outlier pills) ready to embed in the compact card template at quarter-letter geometry. E-229-05 wraps the SVG in a card layout with header, sidebar lookup, and legend.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Collision-jitter radius and the pill projection multiplier are render-layer tuning constants. Initial values are conservative; refinement happens during the first-real-opponent calibration pass per epic Rollout.
