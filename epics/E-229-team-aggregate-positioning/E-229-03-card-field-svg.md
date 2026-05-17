# E-229-03: Card field SVG generator — star, textbook dot, compass letter ring, density background

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`TODO`

## Description
After this story is complete, a card-level field SVG generator produces a per-position field diagram given an opponent + position. The diagram renders the team-aggregate star (sized/styled per confidence tier, with a BIP-count caption at every star-rendering tier), a whisper-quiet textbook reference dot, the full 8-zone compass letter ring at fixed positions (populated zones full-opacity; empty zones faint placeholders), and a faint spray-density background (hidden when confidence is low). Three confidence states (zero-coverage / thin-data / full) are supported. Outlier batter pills are NOT in this story — they ship in E-229-04. The story consumes the locked layout constants produced by E-229-2b (feasibility prototype).

## Context
E-228's renderer drew a field SVG but tied direction information to categorical labels. E-229's renderer is purely spatial: the star moves per opponent (engine output), the textbook dot stays put for variance context, and the compass letters anchor at fixed angular positions around the star so the direction language stays stable across opponents (per epic TN-3).

Per UXD round-1 + holistic findings: the textbook dot is **whisper-quiet** (open outlined circle, 30–40% grey, no fill, no label, smaller than star). The spray-density background is tightly constrained (single channel, ~15% opacity, dot-only, dropped when `is_low_confidence = 1`).

Per epic TN-3 (stable direction language) + coach MN-1 + UXD B-3/I-4 + CR I1 holistic findings: render **all 8 compass letters always**, with populated zones at full opacity and empty zones as faint grey placeholders. This preserves stable visual language across opponents while still emphasizing the relevant zones. Letters anchor at the **outer edge** of each zone (~75–85% available radius) to avoid z-order collision with pill clusters near the star, with edge-clamping to the field outline.

Per epic TN-4, three confidence-tier visual states must work:
- **Zero-coverage (0–14 BIPs)**: no star, dominant message ("Not enough spray data — play your standard alignment"), no outliers, no density bg, no compass letters
- **Thin-data (15–49 BIPs)**: star with thin-data badge (dashed ring or "(~N BIP)" caption), no density bg, full compass letter ring (faint placeholders where empty), no outliers (outliers come in E-229-04)
- **Full (50+ BIPs)**: solid star **with small BIP-count caption** (per coach BC-3 "always contextualize"), density bg shown, full compass letter ring (faint placeholders where empty)

## Acceptance Criteria
- [ ] **AC-1**: A function in `src/reports/positioning_card.py` (module placement locked per CR M3) takes `(opponent_id, position, conn)` and returns an SVG string (or appends to a template render context) for a single position's field diagram. **SVG aspect ratio + dimensions + all stroke/font specifics are consumed from the locked-constants artifact at `/.project/research/E-229-locked-layout-constants.md` (produced by E-229-2b)**. This story does NOT name specific numeric values for those constants — they come from the artifact at impl time. The function queries `team_position_aggregate` and `spray_charts` directly per epic TN-7 JOIN patterns.
- [ ] **AC-2**: Star marker rendered at `team_position_aggregate.(star_x, star_y)` for this position. Visual state per epic TN-4 confidence tier: full tier renders a solid star **with a small BIP-count caption** (e.g., "(N BIP)" at ~6–7pt below or beside the star, per coach BC-3 "always contextualize, never suppress"); thin-data tier renders a dashed-ring or "(~N BIP)" thin-data badge; zero-coverage renders no star (per AC-9).
- [ ] **AC-3**: Textbook reference dot rendered at `BASE_POSITION[position]`: open outlined circle, no fill, ~1pt stroke, 30–40% grey, no label, smaller than the star. The textbook dot is OMITTED in the zero-coverage state.
- [ ] **AC-4**: All 8 compass letters render at fixed offsets around the star per epic TN-15 SVG coordinate convention (`y=0 at deep CF; y increases toward home`). **Per-letter SVG offset is computed from the zone vocabulary via the projection formula** `(x_offset = sign(direction_for_zone) * scale_x * R, y_offset = -sign(depth_for_zone) * scale_y * R)` where R is the ring radius (consumed from the locked-constants artifact per E-229-2b). For example, Zone A (in+left) projects to `(-R, +R)` — lower-left of star; Zone H (deep+right) projects to `(+R, -R)` — upper-right. **No hand-mapped angular-degree table** in this AC or in Technical Approach (the prior draft's degree map baked in a y-inversion assumption that contradicted `src/charts/spray.py:47`; the formula computes positions correctly from vocabulary, eliminating the bug class). Letter placement is at the **outer edge** of each zone, ~75–85% of available radius from star toward field perimeter (R value from the artifact), **edge-clamped to the field outline** (a letter whose projected position would fall outside the field is clamped to the nearest on-field position preserving angular direction). Letter rendering style consumed from the locked-constants artifact (font, size, weight, backing-circle diameter, opacity). **Populated zones (≥1 outlier batter with `zone_id IS NOT NULL AND is_thin = 0`) render at full opacity; empty zones render as faint placeholders (~30% opacity)** so the visual compass is stable across opponents per epic TN-3.
- [ ] **AC-5**: Spray-density background rendered behind everything else when `is_low_confidence = 0` (full tier only). Background is a faint grey dot layer (~15% opacity, single channel, no play-type differentiation, no hit/out coloring). When `is_low_confidence = 1` (thin-data or zero-coverage), the density background is omitted entirely.
- [ ] **AC-6**: Card legend rendered at the bottom of the diagram from the `COMPASS_LEGEND_SHORT` module-level constant (per UXD M-1 single-source legend wording, also referenced in epic TN-3). Format: `★ default · ○ textbook · A-H outliers` (locked per E-229-2b coach AC-12 Option 1 remediation + epic TN-3 amendment + `/.project/research/E-229-locked-layout-constants.md` §F). One line, 7pt (the TN-16 dugout-glance floor — do not drop below).
- [ ] **AC-7**: Card header rendered at the top: opponent name, position name, and coverage cue (`Through <Mon Day> (<N> games)`) from the `format_coverage_cue()` helper (locked source: reuses E-228's freshness function with the bundle-generation snapshot input from E-229-08 per epic TN-16; ungated by the "TBD" deferred from prior iteration). Typography per the design-tokens TN-16 (epic).
- [ ] **AC-8**: No-outliers state: when zero zones have populated outlier batters (all `zone_id IS NULL` or all `is_thin = 1`), the diagram renders star + textbook dot + density bg (if applicable) + legend + a one-line "No outliers this opponent" note at the bottom. **Compass letters render as faint placeholders for all 8 zones** (per AC-4 — stable visual language).
- [ ] **AC-9**: Zero-coverage state: when `is_low_confidence = 1` AND `bip_count < 15`, the diagram renders header + legend + a dominant "Not enough spray data — play your standard alignment" message centered on the field area. No star, no textbook dot, no compass letters, no density bg, no outlier markers.
- [ ] **AC-10**: Tests cover all three confidence states (full / thin / zero), the no-outliers branch, the legend + header content from module constants, the always-render compass ring with faint-placeholder + edge-clamping behavior, and the JOIN-based density bg rendering. Snapshot tests against a deterministic test fixture verify the SVG output is stable.

## Technical Approach

**Module organization**: create `src/reports/positioning_card.py` (CR M3 lock; the focused module name eliminates the "OR renderer.py" ambiguity in the draft). E-229-04 inherits this module placement.

**Field shape primitives**: reuse `src/charts/spray.py` if it provides field-outline + base-position-anchor primitives. If not, draw the field outline inline (rectangle + foul lines + outfield arc, matching E-228's mockup). SVG dimensions consume the constants locked by E-229-2b feasibility prototype.

**Compass letter ring placement**: 8 anchor points around the star, computed by the SVG offset formula in AC-4 per epic TN-15 coordinate convention. **No hand-mapped angular-degree table** — the renderer computes positions from the zone vocabulary directly via `(x_offset = sign(direction_for_zone) * scale_x * R, y_offset = -sign(depth_for_zone) * scale_y * R)`. The y-axis negation is the canonical convention adjustment per `src/charts/spray.py:47` (y=0 at deep CF; depth-negative "in" plots toward y=max bottom). Concrete consequence: Zone A (in+left) at lower-left of star; Zone D (in, centered) straight down; Zone E (deep, centered) straight up; Zone H (deep+right) at upper-right. **Outer-edge placement** at ~75–85% of available radius from star toward field perimeter (R value consumed from the locked-constants artifact per E-229-2b). **Edge-clamping**: if a letter's projected position would fall outside the field outline (e.g., the star is itself near the field edge), the letter is clamped to the nearest on-field position while preserving angular direction. Edge-clamping prevents the letters from disappearing into off-field whitespace.

**Letter style**: 10pt bold capital letter inside a 0.18" diameter 20%-opacity grey filled circle. Black text on the circle. Populated zones at full opacity (zone has ≥1 outlier batter); empty zones at ~30% opacity (faint grey placeholder).

**Density background SQL**: per epic TN-7 — `spray_charts WHERE team_id=? AND season_id=? AND perspective_team_id=? AND chart_type='offensive' AND x IS NOT NULL AND y IS NOT NULL`. Same `(x, y)` pool fuels all 6 cards.

**Module-level legend constants** (per UXD M-1 + epic TN-3): a single source of truth for legend wording. Suggested module-level constants:
```python
COMPASS_LEGEND_SHORT = "★ default · ○ textbook · A-H outliers"  # locked per E-229-2b TN-3 amendment (coach AC-12 Option 1)
COMPASS_LEGEND_LONG = "A in-left · B left · C deep-left · D in · E deep · F in-right · G right · H deep-right · · = team default"
```
Importable by all template renderers across cards, prep page, and call sheet.

**Zero-coverage state message**: large, centered, single-line ("Not enough spray data — play your standard alignment"). E-228's report-bundle zero-state styling is the precedent.

**Z-order** (back to front): density bg → field outline → textbook dot → star (+ BIP caption) → compass letters → (outlier pills layered on top in E-229-04).

**Coverage cue source**: locked per CR I4 fix — reuses E-228's freshness function (`format_coverage_cue()`-equivalent helper that produces "Through Mon Day (N games)" from a snapshot input). The game-count snapshot is produced by E-229-08 at bundle-generation time per epic TN-16 (coverage-cue path = restore-with-snapshot, user-confirmed).

## Dependencies
- **Blocked by**: E-229-02 (engine output `team_position_aggregate` + `batter_positioning` rows), E-229-2b (locked layout constants from feasibility prototype)
- **Blocks**: E-229-04 (outlier pills extend this SVG), E-229-06 (prep page reuses the field generator)

## Files to Create or Modify
- `src/reports/positioning_card.py` — create (module placement locked per CR M3)
- `src/charts/spray.py` — modify, optional (if field-shape primitives need extension)
- `tests/test_positioning_card_render.py` — create (snapshot tests + state coverage + always-render-compass-with-faint-placeholder + edge-clamping)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-229-04**: a stable field SVG with anchor coordinates the outlier-pill rendering can extend. E-229-04 overlays numbered pills on top of this SVG at coordinates derived from per-batter deviation values; E-229-04 inherits this story's module choice (`src/reports/positioning_card.py`).
- **Produces for E-229-06**: a reusable field-SVG-generator function the prep page can call to render all 6 positions overlaid on one full-field SVG.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- Letter ring radius (75–85% of available radius), letter font size (10pt), BIP-caption font size (6–7pt), and pill projection multiplier are tuning constants. E-229-2b's feasibility prototype locks these; this story consumes the locked values.
- The always-render-compass with faint-placeholder behavior (AC-4) is the unified resolution of coach MN-1 (consider always-render), UXD B-3 (outer edge + edge-clamping), UXD I-4 (full letter styling spec), and CR I1 (stable language vs only-populated). All four reviewers' concerns are addressed by the single fix.
