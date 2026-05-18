---
status: LOCKED
version: 1.2
produced_by: E-229-2b
calibration_history: []
version_history:
  - version: 1
    date: 2026-05-17
    transition: PROVISIONAL v0 → LOCKED v1 on baseball-coach AC-12 PASS verdict (E-229-2b)
  - version: 1.1
    date: 2026-05-17
    transition: LOCKED v1 → LOCKED v1.1 clarification — added "Coordinate-space rescaling (normative)" subsection to §B. The v1.1 formula was a pure-scalar viewBox-to-viewBox ratio (`x * 0.625, y * 0.667`) that was geometrically wrong; corrected at v1.2 below.
  - version: 1.2
    date: 2026-05-17
    transition: LOCKED v1.1 → LOCKED v1.2 correction — replaced v1.1's pure-scalar rescaling formula with SE's field-anchored mapping that preserves the prototype's field-landmark positions. The v1.1 pure-scalar formula placed engine deep-CF (y=0) at card y=0 (header zone, above the painted fence arc) and engine home plate at card y≈197 (mid-card, far above the painted home plate at y=305) because the field outline does NOT fill the viewBox edge-to-edge (top 80 card-y units are header space, bottom 15 units are legend space). SE caught this before committing the wrong implementation. Not a calibration change; corrects a spec-author error introduced in v1.1.
---

# E-229 Layout Constants — Quarter-letter print

This artifact is the single source of truth for E-229's per-card layout constants, design tokens, and shared rendering rules. Downstream stories (E-229-03 card field SVG, E-229-04 outlier pills, E-229-05 compact card template, E-229-06 prep page, E-229-07 call sheet, E-229-08 bundle) consume the values here at implementation time per epic TN-16 design-tokens citation pattern, and MUST NOT hardcode them in story ACs or in source code outside this artifact's adoption sites.

## State machine

- **PROVISIONAL v0 (created during E-229 Phase 4 iteration 2, superseded)**: UXD round-1 / round-2 estimates as initial values. Downstream stories cited the artifact path but did NOT consume v0 values.
- **LOCKED v1 (superseded by v1.1 on 2026-05-17, same dispatch day)**: values validated at print scale via the quarter-letter feasibility prototype + coach legibility review (verdict transcribed in the story Notes of `epics/E-229-team-aggregate-positioning/E-229-2b-feasibility-prototype.md`). Coach's only failure point — 6.5 pt legend below TN-16 floor — was remediated via Option 1 (shortened legend text + 7 pt) per coach pre-approval; all other elements passed without revision.
- **LOCKED v1.1 (superseded by v1.2 on 2026-05-17, same dispatch day)**: added §B "Coordinate-space rescaling (normative)" subsection documenting that engine output requires rescaling at the consumer's read-then-place boundary. The v1.1 subsection carried a pure-scalar formula derived from the viewBox-dimension ratio (`x_card = x_engine * 0.625; y_card = y_engine * 0.6667`) that was geometrically wrong (see v1.2 entry).
- **LOCKED v1.2 (this state — set 2026-05-17 by SE-surfaced spec correction during E-229-03 implementation)**: corrected the §B "Coordinate-space rescaling (normative)" subsection. The v1.1 pure-scalar formula was geometrically wrong because the field outline does NOT fill the per-card viewBox edge-to-edge — the top 80 card-y units are header space and the bottom 15 are legend space. SE's field-anchored mapping `x_card = 10 + (x_engine / 320) * 180; y_card = 80 + (y_engine / 295) * 225` preserves the prototype's field-landmark correspondences (engine LF corner (0,0) → card (10,80); engine home plate (160,295) → card (100,305); engine RF corner (320,0) → card (190,80)). Engine unchanged; rescaling still lives in consumers (E-229-03 card SVG generator, E-229-06 prep page). Why AC-11/AC-12 missed this in E-229-2b: the validation was rendering-based (coach reviewed printed prototype where field outline was already at correct offsets), not formula-based (nobody ran engine landmark coords through the proposed formula to verify landing positions). Downstream implementations (E-229-03 / 04 / 05 / 06 / 07) consume v1.2 values directly.
- **LOCKED v2+ (Rollout calibration)**: real-opponent feedback during the calibration pass (epic Rollout section) may bump version and append to `calibration_history` with an entry of shape `{date, opponent, changed_constants[]}`.

Cross-reference: see `.project/research/E-229-2b-quarter-letter-prototype.html` (the static prototype HTML produced by E-229-2b) for the visual proof of these constants at print scale.

**Citation pattern for downstream stories.** Stories MUST cite this artifact by section letter (e.g., "consumed from `.project/research/E-229-locked-layout-constants.md` §B") rather than naming specific values in ACs. If a downstream story discovers a constant is missing or needs to change, the change goes here first (with a Decisions Log entry and a version bump); the story does not embed its own values.

---

## A. Card geometry

| Constant | Value | Notes |
|----------|-------|-------|
| Card outer width | 4.25 in | Quarter-letter portrait |
| Card outer height | 5.5 in | Quarter-letter portrait |
| Card padding (all sides) | 0.15 in | Internal margin |
| Card inner area (computed) | 3.95 in × 5.20 in | Outer minus 2× padding |
| Header zone height | 0.65 in | Opponent + position + coverage cue |
| Legend zone height | 0.25 in | One-line legend at bottom |
| Body zone (computed) | 3.95 in × 4.30 in | Inner minus header minus legend |
| Body row gap (header→body, body→legend) | 0 in (border dividers carry the visual gap) | 0.5pt grey-30 separators at zone boundaries |

### 4-up sheet layout

| Constant | Value |
|----------|-------|
| Sheet paper size | Letter portrait (8.5 in × 11 in) |
| Print page margin | 0 in (all four sides) |
| Grid | 2 columns × 2 rows |
| Column width | 4.25 in (each) |
| Row height | 5.5 in (each) |
| Grid gap | 0 in (cards abut at the midlines) |

The grid math is exact: 2 × 4.25 = 8.5 (full sheet width), 2 × 5.5 = 11 (full sheet height). Cards meet edge-to-edge at the midlines; cut lines fall on the midlines themselves. Browser default print margins must be set to "None" (Chrome / Edge) or "0" (Safari) for the cut geometry to land correctly.

### Cut-line spec

| Property | Value |
|----------|-------|
| Weight | 0.5 pt |
| Dash pattern | 2 pt dash / 2 pt gap |
| Color | 50% grey (`--grey-50` = `#808080`) |
| Coverage | Horizontal midline (y = 5.5 in) + vertical midline (x = 4.25 in) only |
| NOT included | Corner crop marks, full-card borders, perimeter cuts |

Rationale: midline-only cuts let the coach cut on two straight lines (one horizontal, one vertical) and finish with 4 cards. Corner crop marks add print noise without speeding the cut. Full-card borders fight with the card-internal layout (the header divider and body grid lines do that job).

---

## B. SVG field diagram

| Constant | Value | Notes |
|----------|-------|-------|
| SVG aspect ratio (W/H) | 0.625 | viewBox 200 × 320; portrait. Within the ±5% letterbox window UXD round-1 specified |
| SVG slot width (computed) | 2.53 in | 64% × 3.95 in body width |
| SVG slot height (computed) | 4.04 in | Body height minus body padding; SVG scales `xMidYMid meet` inside |
| SVG/sidebar split (% of body inner width) | 64 / 36 | |
| SVG column gap | 0.08 in | Padding between SVG and sidebar |
| SVG canvas viewBox (W × H) | 200 × 320 | Internal SVG coord space; aspect 0.625 |
| Y-axis convention | y=0 at deep CF (top); y increases toward home plate (bottom) | Per epic TN-15; reference `src/charts/spray.py:47, 480` |
| X-axis convention | x=0 at LF foul line (left); x increases toward RF foul line (right) | Per epic TN-15 |

### Markers, dots, letters, pills

| Element | Spec |
|---------|------|
| Star marker (full tier) | Solid filled 10-point star, fill 100% black, no stroke, ~16 px wide in viewBox space (~0.20 in printed) |
| Star marker (thin tier) | Same solid star PLUS surrounding dashed ring (stroke 0.6 px, dash `2 1.5`, opacity 0.85, radius 10 px in viewBox) |
| Star BIP-count caption | `(N BIP)` (full tier) or `(~N BIP)` (thin tier); 7 pt Arial regular, black, placed 18 px below star center in viewBox |
| Textbook reference dot | Open circle, no fill, 0.6 pt stroke, 100% black ink at 45% opacity, radius 3.5 px in viewBox (~0.05 in printed); positioned at textbook BASE_POSITION |
| Compass letter — populated | 10 pt Arial bold, 100% black, inside circular disc of radius 6.5 px (~0.18 in printed diameter), disc fill `rgba(0,0,0,0.20)`, no stroke |
| Compass letter — empty placeholder | Same dims and disc as populated, both letter and disc at 30% opacity (preserves stable visual language per coach MN-1) |
| Outlier pill — shape | Rounded rect, 14 px tall × auto-width in viewBox (~0.20 in printed); corner radius 2 px |
| Outlier pill — fill / stroke | White fill, 0.5 pt black stroke (provides contrast against density-background dots and compass discs) |
| Outlier pill — typography | 9 pt Arial bold, 100% black, text-anchored center, dominant-baseline central |
| Outlier pill — text format | `#<jersey> <truncated-last-name>` (last name truncated to 5–6 chars depending on width budget) |
| Outlier pill — NULL-jersey fallback | Render `(L. init)` in the name slot (e.g., `(W. init)` for Wilkinson), no `#` prefix |
| Density background dot | Filled circle, 1.8 px radius in viewBox, 100% black ink at 12% opacity, no stroke |
| Density background render gate | Rendered ONLY when `is_low_confidence = 0` (full tier ≥50 BIPs). Hidden on thin and zero tiers |

### SVG `font-size` unit convention (normative)

The numeric `font-size` values declared above are **target printed point sizes**. The SE-owned SVG generators (E-229-03, E-229-04, E-229-06) MUST produce text rendered at those point sizes at the final 2.53 in × 4.04 in SVG-slot geometry. The recommended pattern is explicit pt units in the SVG attribute (e.g., `font-size="10pt"` on compass letters, `font-size="9pt"` on pill text, `font-size="7pt"` on the BIP caption). The prototype HTML at `.project/research/E-229-2b-quarter-letter-prototype.html` mixes pt-explicit (BIP caption, legend) and viewBox-unit (compass letters, pills) sizing during its bring-up; both render legibly per the coach AC-12 verdict, but pt-explicit is the locked convention for production SVG to keep typography invariant under any future viewBox dimension change.

### Coordinate-space rescaling (normative)

**The engine and the per-card SVG live in different coordinate spaces, AND the field outline does NOT fill the per-card viewBox edge-to-edge.** Consumers (E-229-03 card SVG generator, E-229-06 prep page) MUST apply an explicit **field-anchored** rescaling at the read-then-place boundary when consuming `team_position_aggregate.(star_x, star_y)` and `spray_charts.(x, y)`. The engine is unchanged; rescaling is a consumer responsibility.

#### Coordinate spaces

| Coordinate space | Dimensions (W × H) | Source / canonical reference |
|------------------|---------------------|------------------------------|
| Engine output (DB-stored) | 320 × 480 | `src/charts/spray.py::_raw_to_svg` GC canonical, per `spray.py:47` + epic TN-15 |
| Per-card SVG viewBox | 200 × 320 | This artifact §B, aspect 0.625, quarter-letter-tuned (see Decisions Log "SVG aspect ratio" entry) |

#### Card viewBox internal structure

The per-card 200×320 viewBox is divided into three zones along the y-axis:

| Zone | y-range (card) | Purpose |
|------|----------------|---------|
| Header | 0 ≤ y < 80 | Opponent name, position label, coverage cue |
| Field outline | 80 ≤ y ≤ 305 | Where engine coordinates land; foul corners at card (10, 80) and (190, 80); home plate at card (~100, 305) |
| Legend | 305 < y ≤ 320 | `COMPASS_LEGEND_SHORT` at 7pt |

The field occupies the inner rectangle (10, 80) — (190, 305): width 180 (x ∈ [10, 190]), height 225 (y ∈ [80, 305]).

#### Field-anchored rescaling formula (normative)

```
x_card = 10 + (x_engine / 320) * 180
y_card = 80 + (y_engine / 295) * 225
```

Landmark correspondences:

| Engine coordinate | → | Card coordinate | Meaning |
|-------------------|---|------------------|---------|
| (0, 0)            | → | (10, 80)         | LF foul corner / deep CF top |
| (320, 0)          | → | (190, 80)        | RF foul corner / deep CF top |
| (0, 295)          | → | (10, 305)        | Home plate (LF side foul line) |
| (320, 295)        | → | (190, 305)       | Home plate (RF side foul line) |
| (160, 295)        | → | (100, 305)       | Home plate (center) |
| (160, 0)          | → | (100, 80)        | Straight-away deep CF |

Apply to every coordinate value sourced from the engine's 320×480 coord space:
- `team_position_aggregate.star_x, star_y` (star placement)
- `spray_charts.x, y` consumed for the density background
- `src/reports/positioning.BASE_POSITIONS[position]` if a consumer renders the textbook reference dot from the engine module's constants

Coordinates that are NOT sourced from the engine coord space — compass-letter offsets via the projection formula (declared below in viewBox-native units), pill offsets relative to the star (viewBox-native via `scale_x`, `scale_y`), the field-outline path itself (declared in viewBox-native units in the consumer) — do NOT need rescaling. The projection-formula `scale_x = 18`, `scale_y = 22` and `R_units ≈ 2.2` constants are viewBox-native by construction (see the Projection formulas subsection below).

#### Sign-rule preservation

The two transforms are positive-only affine maps (multiplication + positive offset); directional signs carry through unchanged. The TN-15 y-axis convention holds: smaller card_y = deeper toward CF (`y_card = 80` is deep CF; `y_card = 305` is home plate). The `-depth_dev` adjustment in the projection formula remains canonical and applies AFTER engine-coordinate rescaling has produced the star anchor in card space.

#### Why the v1.1 pure-scalar formula was wrong

The v1.1 formula `x_card = x_engine * 0.625; y_card = y_engine * 0.6667` was derived from the viewBox-to-viewBox dimension ratio (200/320 and 320/480). This is correct as a maximum-extent ratio but ignores the field-vs-viewBox offset: under v1.1, engine deep CF (y=0) maps to card y=0 (header zone, above the painted fence arc), and engine home plate (y=295) maps to card y≈197 (mid-card, far above the painted home plate at y=305). The star would render detached from the painted field outline. SE caught this geometric error during E-229-03 implementation and shipped the correct field-anchored mapping.

#### Implementation reference

See `src/reports/positioning_card.py::_engine_to_card_xy` (E-229-03 ships the first consumer implementation; E-229-06 reuses or imports it). The implementation reads naturally from the constants `_CARD_LEFT_X = 10`, `_CARD_FENCE_Y = 80`, `_CARD_HOME_Y = 305`, `_ENGINE_W = 320`, `_ENGINE_HOME_Y = 295`, `_CARD_FIELD_W = 180`, `_CARD_FIELD_H = 225`.

### Compass ring placement

| Constant | Value | Notes |
|----------|-------|-------|
| Ring radius (R) | 80% of available radius from star to nearest field edge | Per UXD B-3; edge-clamped to field outline per UXD I-4 |
| Ring is asymmetric | `R_x ≠ R_y` allowed | Because the field is taller than wide in viewBox space; using uniform R caused upper letters to clamp off-canvas while lateral letters had unused room. Practical values from the prototype: `R_x ≈ 36 px`, `R_y ≈ 50 px` when star is mid-field |
| Edge-clamping rule | If `letter_position + disc_radius > field_edge`, slide letter inward along the radial vector until clear | Letter NEVER renders outside the field outline |

### Projection formulas (canonical, per epic TN-15)

```
# pill placement
pill_x   = star_x + direction_dev * scale_x
pill_y   = star_y + (-depth_dev)  * scale_y

# compass letter placement (sign-driven; magnitude is constant R)
letter_x = star_x + sign(direction_dev_for_zone) * scale_x * R_units
letter_y = star_y + (-sign(depth_dev_for_zone))  * scale_y * R_units
```

The `-` on `depth_dev` is the canonical y-axis convention adjustment (TN-15). It is NOT a bug; do not "fix" it.

| Constant | Value | Notes |
|----------|-------|-------|
| `scale_x` | 18 px per ordinal-bucket unit (viewBox space) | Asymmetric to honor field aspect; ±3 ordinal units span ~108 px (≈ field width minus margins) |
| `scale_y` | 22 px per ordinal-bucket unit (viewBox space) | ±3 ordinal units span ~132 px (depth dimension) |
| `R_units` | ~2.2 ordinal units | The compass ring sits at the 80%-edge described above; expressed in ordinal units, `R ≈ 2.2 × scale` |

Practical consequence: an outlier at deviation `(direction_dev = -1, depth_dev = +1)` (one bucket left, one bucket deep) lands `(−18 px, −22 px)` from the star — upper-left of star — which is zone C (deep-left). This matches the TN-15 + TN-3 vocabulary.

### Z-order stack (back to front)

1. Field outline (foul lines, OF arc, IF grass arc, bases)
2. Density background dots (when render-gate passes)
3. Textbook reference dot
4. Compass letter discs (filled circles) — populated full opacity; empty 30%
5. Compass letters (text) — populated full opacity; empty 30%
6. Team-aggregate star (and thin-tier dashed ring + caption)
7. Outlier pills (rect + text)

Pills draw last so they cannot be obscured by density dots or compass discs (per UXD I-3 — outlier identity is the actionable data; never let decorative layers obscure it).

---

## C. Card frame elements

### Header zone (0.65 in)

| Element | Spec |
|---------|------|
| Layout | CSS grid: 2 columns (opponent left, coverage cue right) × 2 rows (top row = opponent + coverage cue, bottom row = position name spanning both columns) |
| Opponent name | 11 pt Arial bold, 100% black, left-aligned, line-height 1.15 |
| Coverage cue | 9 pt Arial regular, 70% grey, right-aligned, white-space nowrap |
| Position name | 10 pt Arial bold, 100% black, uppercase, letter-spacing 0.04em, full width |
| Divider | 0.5 pt 30%-grey hairline below the header zone |

Rationale for the position-name on its own row: in the prototype I tried putting opponent + position on the same line (per E-228 mockup pattern) and the position name was either too small (8 pt) or pushed the coverage cue off the edge. Splitting them gave each element its visual weight without sacrificing legibility.

### Body zone (3.95 in × 4.30 in)

| Element | Spec |
|---------|------|
| Layout | CSS grid: 2 columns at 64% / 36% with `column-gap: 0.08in` |
| Padding-top inside body | 0.06 in (visual breathing room from header divider) |
| Overflow | `overflow: hidden` (SVG and sidebar must not bleed into legend) |

### Legend zone (0.25 in)

| Element | Spec |
|---------|------|
| Top divider | 0.5 pt 30%-grey hairline above the legend zone |
| Typography | 7 pt Arial regular, 70% grey, center-aligned |
| Padding-top | 0.04 in |
| Content | `COMPASS_LEGEND_SHORT` from §F shared design tokens |

The 7 pt floor here is load-bearing — it is the dugout-glance-test floor coach validated in AC-12. The PROVISIONAL v0 + UXD-self-validation-iteration value was 6.5 pt; coach rejected it as below TN-16's 7 pt minimum, particularly in dugout shade. Holding the line at 7 pt required shortening the legend text (see §F `COMPASS_LEGEND_SHORT` + Decisions Log "Legend text + typography").

### Sidebar lookup

| Element | Spec |
|---------|------|
| Sidebar title | 7 pt Arial bold uppercase, 70% grey, 0.04em letter-spacing, with 0.5 pt 30%-grey divider below (matches header divider weight) |
| Sidebar row layout | CSS grid, 3 columns: `0.34in` (jersey) / `1fr` (name) / `0.20in` (zone letter); `column-gap: 0.04in`, `row-gap: 0.02in` |
| Jersey cell | 7.5 pt Arial bold, right-aligned, `font-variant-numeric: tabular-nums` (keeps 1-digit and 2-digit jerseys in column) |
| Name cell | 7.5 pt Arial regular weight 500, 0.01em letter-spacing, no ellipsis (overflow clip — names are truncated UPSTREAM by the renderer per UXD M-4 to keep cell width predictable) |
| Last-name truncation rule (consumer-side) | Renderer truncates to ≤7 chars; the cell visually clips at ~0.85 in if a longer name is passed |
| Zone-letter cell | 7.5 pt Arial bold, center-aligned, `font-variant-numeric: tabular-nums` |
| Row height | Implicit from line-height 1.20 (~0.13 in per row); 5 rows fit comfortably in the sidebar height |
| Empty-state banner (per coach IM-1 + UXD M-4) | Centered single-line italic "No outliers this opponent. Play team default." at 7.5 pt, 70% grey, replaces the row grid; sidebar title + divider still render so the slot is never visually empty |

Rationale for proportional Arial over monospace: I tested both at print scale. Monospace 7 pt made the names look "computery" and were marginally less legible (narrower glyphs at small print sizes); proportional Arial + tabular-nums on the jersey and zone columns preserves column alignment where it matters (numbers and letters) while letting names breathe.

---

## D. Sheet-2 fill content (per TN-12 + E-229-05 AC-9)

Sheet 2 of the 4-page bundle holds positions SS and 2B in slots 1 and 2 of the 2×2 grid; slots 3 and 4 are NOT blank. They are coach-facing artifacts cut and kept by the coach.

### Slot 3 — Visual compass key

| Element | Spec |
|---------|------|
| Card geometry | Same 4.25 in × 5.5 in card frame |
| Header | Opponent slot = "Compass Key"; coverage-cue slot = "Reference card"; position-name slot = "8-zone field compass" |
| Caption (above field) | 7.5 pt 70% grey center-aligned, text: "Letters are stable across opponents. The team-default star moves; the labels do not." (~0.04 in padding above + below) |
| Field diagram | Same field outline as player cards; star centered at viewBox (100, 170); all 8 compass letters at full opacity (this is a reference, every zone matters); no outlier pills, no density bg |
| Compass letter typography | Same as §B but disc radius bumped to 7.5 px and font to 11 pt (the key is a reference artifact; legibility outweighs print-density constraints) |
| Axis annotations | 9 pt Arial regular, 100% black: "DEEP" at top center (y=50), "IN" at bottom center (y=295), "LEFT" rotated −90° at left edge (18, 50), "RIGHT" rotated +90° at right edge (182, 50) |
| Legend | `COMPASS_LEGEND_LONG` from §F shared design tokens |

### Slot 4 — Opponent context card

| Element | Spec |
|---------|------|
| Card geometry | Same 4.25 in × 5.5 in card frame |
| Header | Opponent name in opponent slot; coverage cue in coverage-cue slot; position-name slot = "Opponent context" |
| Body title (h2) | 14 pt Arial bold, line-height 1.15, 0.01em letter-spacing — restated opponent name (large, anchoring) |
| Body coverage line | 9 pt Arial regular, 70% grey — "{Season} · {N} games · vs. {our team} {next game date}" |
| Stat list | CSS grid 2-column definition list (`dt` left = 70% grey labels, `dd` right = bold values right-aligned); 9 pt Arial; rows for Record, Runs/game, Runs allowed/game, Team BIPs |
| Coverage-tier line | 9 pt Arial, 70% grey body text + bold uppercase "Full" / "Thin" / "Zero" tier label; describes what cards render |
| Legend | Plain copy: "Coach reference · cut and keep with the call sheet." (not the COMPASS_LEGEND constants — this card is a context surface, not a positioning surface) |

Rationale for keeping slot 4 in the same card family: when the coach cuts the sheet at the midlines, slot 4 hands them a same-size context card they can paper-clip to the call sheet. Different geometry would defeat the workflow.

---

## E. Typography parity across artifacts

| Surface | Element | Spec |
|---------|---------|------|
| Card (E-229-05) | Opponent name (header) | 11 pt Arial bold |
| Card | Position name (header) | 10 pt Arial bold uppercase, 0.04em letter-spacing |
| Card | Coverage cue (header) | 9 pt Arial regular, 70% grey, right-aligned |
| Card | Sidebar title | 7 pt Arial bold uppercase, 70% grey, 0.04em letter-spacing |
| Card | Sidebar lookup row (jersey / name / zone) | 7.5 pt Arial (bold jersey + zone, regular weight 500 name); `font-variant-numeric: tabular-nums` on jersey and zone cells |
| Card | Pill text | 9 pt Arial bold |
| Card | Compass letter | 10 pt Arial bold (inside 0.18 in disc) |
| Card | Star BIP caption | 7 pt Arial regular |
| Card | Legend | 7 pt Arial regular, 70% grey |
| Prep page (E-229-06) | Header (opponent) | 13 pt Arial bold (larger than card; single-page artifact) |
| Prep page | Header (coverage cue) | 9 pt Arial regular, 70% grey, right-aligned |
| Prep page | Pill text on overlay | 9 pt Arial bold; format `7-LF` (hyphen separator, no `#`) per UXD M-2 |
| Prep page | Sidebar matrix row | 7.5 pt Arial (matches card sidebar) |
| Call sheet (E-229-07) | Jersey column cell | 11 pt Arial bold (UXD I-7 visually-prominent rule) |
| Call sheet | Name column cell | 9 pt Arial regular |
| Call sheet | Zone-letter cell | 9 pt Arial bold center-aligned |
| Call sheet | Legend (top of sheet) | 9 pt Arial regular |
| Call sheet | Header (opponent) | 11 pt Arial bold |
| Call sheet | Header (coverage cue) | 9 pt Arial regular, 70% grey, right-aligned |
| Call sheet | NOTE column header | 9 pt Arial bold uppercase (matches other column headers) |
| Call sheet | NOTE column cell — rationale | per Rationale subsection below |

**Parity rules (shared elements MUST render identically across all surfaces):**
- Coverage cue: 9 pt Arial regular, 70% grey, right-aligned, format from `format_coverage_cue()` in §F. Same on cards / prep page / call sheet.
- Legend wording: from `COMPASS_LEGEND_SHORT` (cards) or `COMPASS_LEGEND_LONG` (prep page, call sheet) in §F. Never inlined by templates.
- Position abbreviation tokens (LF, CF, RF, 3B, SS, 2B): never substituted for full names ("Left Field") in cell contents. Cell contents are always the abbreviation; full names only appear in card headers.

### Intentional surface-specific exceptions

These are NOT parity violations — they are deliberate surface-specific renderings driven by the cognitive task each surface serves. Documented here so a future reader does not flag them as drift.

| Element | Per-card form (E-229-05) | Prep-page form (E-229-06) | Reason |
|---------|--------------------------|---------------------------|--------|
| Outlier pill — populated | `#<jersey> <truncated-last-name>` (e.g., `#7 RAMIR`) | `{jersey}-{position}` (e.g., `7-LF`) per UXD M-2 | Per-card pill is fielder-facing on a single-position diagram (position is implicit from the card); prep page overlays all 6 positions on one field, so the position tag disambiguates which card the outlier belongs to. The hyphen separator + dropped `#` saves pill width on a dense overlay. |
| Outlier pill — NULL-jersey fallback | `(L. init)` literal (e.g., `(W. init)`) per §B | `{initial}-{position}` (e.g., `W-RF`) | Per-card form is a standalone label on a single-position card and benefits from the parenthetical `(... init)` flag making "no jersey known" syntactically explicit. Prep-page form must preserve visual width parity with neighboring `{jersey}-{position}` pills — `(W. init)` would be ~3× wider and read as "special pill" (wrong signal; the jersey is just missing, not "special"). The `-{position}` suffix structurally disambiguates against zone-letter syntax (zone letters never carry a `-position` suffix), so `A-LF` reads unambiguously as "initial-A batter at LF" not "zone A at LF." |

Surface-specific exceptions are limited to the two rows above. Any other pill or sidebar element that varies between surfaces is drift and should be raised to UXD.

### Rationale typography (Tier 2 LLM display)

Single spec applies to both prep page sidebar second-line (E-229-06 AC-10) and call sheet NOTE column (E-229-07 AC-1). Canonical here per Codex iter-3 P1.2 + UXD lock — downstream templates consume this row of constants verbatim.

| Property | Value |
|----------|-------|
| Font family | `Arial, Helvetica, sans-serif` (matches body stack from §F) |
| Style | Italic |
| Size | 8 pt |
| Color | 50% grey (`--grey-50` = `#808080`); soft contrast vs 100%-black structural data |
| Max lines | 2 (CSS `-webkit-line-clamp: 2`) |
| Overflow | `overflow: hidden`, NO ellipsis |
| Empty / None render | Renders nothing (collapsed slot — no placeholder text, no whitespace stub) |

**Audience split** (per UXD): rationale renders on coach surfaces (prep page sidebar + call sheet NOTE column) but NOT on fielder surfaces (player cards). Cards' sidebar (~1.4 in wide) cannot accommodate readable rationale without dropping below the 7 pt floor, and fielders don't need rationale at-glance — cards answer "where do I stand?"; rationale is secondary context for the coach.

**Sizing rationale**: E-229-09 AC-2 caps rationale at 10–50 words (≈ 60–300 chars). The CSS 2-line clamp at the actual column widths (prep-page sidebar second-line ≈ 2.1 in; call-sheet NOTE column ≈ 2.2 in) accommodates ~140–180 chars with graceful overflow. UXD rejected 80-char hard truncation as too aggressive (chops mid-sentence; loses specificity).

**Rejected alternatives** (per UXD): footnotes with numbered refs (forces lookup — exactly the cognitive cost being avoided); hover / tooltip (print loses it; artifact is print-primary); placement inside the SVG (cramped, fights markers + density bg).

---

## F. Shared design tokens

| Token | Value |
|-------|-------|
| Font family stack | `Arial, Helvetica, sans-serif` |
| Greyscale palette | 0% white (`#ffffff`) · 15% (`#d9d9d9`) · 30% (`#b3b3b3`) · 50% (`#808080`) · 70% (`#4d4d4d`) · 100% black (`#000000`) |
| Greyscale usage | 0% paper · 15% density bg dots, compass disc · 30% empty-zone placeholders · 50% cut lines, rationale text · 70% secondary copy (coverage cue, sidebar title, legend) · 100% primary text, stars, field outline |
| Coverage-cue format string | `Through {Mon Day} ({N} games)` — full format per coach IM-2 + user lock; game-count snapshot persisted at bundle-generation time per E-229-08 AC-4a |
| Legend constant — SHORT (cards) | `★ default · ○ textbook · A-H outliers` |
| Legend constant — LONG (call sheet, prep page) | `A in-left · B left · C deep-left · D in · E deep · F in-right · G right · H deep-right · · = team default` |
| Color-not-load-bearing rule | All information (zone identity, confidence tier, batter identity) communicated by shape, position, or text. Color decorative only. (Per UXD I-6 + epic TN-16). Test surface: SVG output uses only black, white, and grey-scale fills / strokes by default |
| Module constants location | `src/reports/positioning_card.py` (or shared renderer module). Templates import the constants — never duplicate the strings inline |
| Module helpers | `format_coverage_cue(through_date, game_count) -> str` returns the locked format string |

Rationale for `Arial, Helvetica, sans-serif` (over `system-ui` or `Helvetica Neue` specific): print rendering across a mixed environment (browser print, weasyprint server-side, dugout printer drivers) needs predictable metrics. Arial is universally available and binary-identical in metrics to Helvetica family; `system-ui` varies wildly across OS (San Francisco on macOS, Segoe UI on Windows, Roboto on Android, etc.) and would invalidate the calibration on a different print path. Explicitly naming `Helvetica Neue` first triggers fallback paths on Windows print servers that often don't have it installed.

> **TN-3 amendment note (LOCKED v1 supersedes epic TN-3 text for `COMPASS_LEGEND_SHORT`).** Epic TN-3 originally specified `COMPASS_LEGEND_SHORT` as `★ team default · ○ textbook · A–H = outlier zones (see right)`. During coach AC-12 review (2026-05-17), that text at the 6.5 pt size required by the card geometry failed the dugout-glance test (below TN-16's 7 pt floor; 70% grey ink compounds the issue in dugout shade). Coach pre-approved Option 1 (shortened text + 7 pt typography) as the fix. LOCKED v1's `COMPASS_LEGEND_SHORT` value above (`★ default · ○ textbook · A-H outliers`) is the operative production constant; epic TN-3 is updated to match in a PM-routed amendment. Implementations MUST consume from this artifact, not from the prior TN-3 prose. The "(see right)" parenthetical was removed because it added no information at quarter-letter geometry — the sidebar IS to the right, and the zone letter is also printed there. `COMPASS_LEGEND_LONG` (call sheet, prep page) is unchanged by this amendment.

---

## G. Responsive (web view)

| Constant | Value | Notes |
|----------|-------|-------|
| Breakpoint | 640 px (Tailwind `sm:`) | NOT `md:` (768 px) per UXD I-5 fix |
| Layout ≤640 px | Single-column vertical: header (full width) → SVG (full width, aspect ratio preserved) → sidebar (full width, rows stack normally) → legend (full width) | SVG slot becomes 100% width; the 64/36 split is dropped |
| Layout >640 px | Side-by-side per §C body layout | Print + tablet/desktop layout |
| SVG behavior at ≤640 px | `width: 100%`, `height: auto`, `preserveAspectRatio` unchanged — viewBox aspect 0.625 drives the rendered height | Avoids the squish-the-field anti-pattern |
| Sidebar empty-state at ≤640 px | The "No outliers this opponent" banner remains; the slot must never collapse to zero height | Per UXD M-4 + IM-1 |

---

## Decisions log

This section records non-obvious constant choices with the alternatives that were tried and rejected during prototype iteration. Format per UXD recommendation: locked value · alternatives tried · why rejected.

### SVG aspect ratio: 0.625 (viewBox 200 × 320)

- **Tried 0.500 (viewBox 200 × 400)**: gave more vertical headroom for the outfield arc but compressed the foul-line angles severely — at ~26° per side the field looked like a wedge, not a diamond. Coach legibility cue (the "field shape" the eye recognizes) was lost.
- **Tried 0.670 (viewBox 200 × 300, GC-native aspect)**: matched the GameChanger spray chart geometry exactly, but forced the sidebar to <1.30 in wide. Even with 5-char name truncation, the jersey + name + letter row felt cramped at 7.5 pt; the sidebar title divider compressed against the first row.
- **Locked 0.625**: balances foul-line angles (~32° per side, recognizable diamond) with a 1.42 in sidebar that holds 5 rows comfortably. Within the ±5% letterbox tolerance UXD round-1 specified.

### SVG / sidebar split: 64 / 36

- **Tried 60 / 40**: gave the sidebar 1.58 in (more comfortable) but compressed the SVG to 2.37 in wide. Compass letters at the field edges visually crowded each other; the textbook dot and team-aggregate star both shifted inside the same compressed space and became hard to distinguish at print scale.
- **Tried 70 / 30**: SVG had room (2.77 in) but sidebar dropped to 1.19 in, which forced 5-char name truncation (RAMI vs RAMIR) and made the zone-letter column visually adjacent to the name (no breathing room).
- **Locked 64 / 36**: SVG 2.53 in wide × 4.04 in tall (per `xMidYMid meet`) holds the field + star + 8 compass discs + 5 pills without crowding; sidebar 1.42 in holds jersey (0.34 in) + name (~0.85 in usable) + zone (0.20 in) with 0.04 in gaps.

### Pill height: 14 px viewBox (~0.20 in printed)

- **Tried 12 px (~0.17 in)**: pill text at 9 pt bold was clipped at the top of caps and at the bottom of descenders (lowercase `g`, `p`, `y` in jersey-format strings if jersey was rendered lowercase; not in practice but a brittle margin).
- **Tried 16 px (~0.22 in)**: pill visually competed with the compass discs (also ~0.18 in tall). The pills should be the primary actionable layer per UXD I-3, so they should dominate slightly, but 16 px made the field feel "pillow-y" and the density-bg dots were swallowed under stacks of pills.
- **Locked 14 px**: tightest height that holds 9 pt bold text without clipping, with 1 px of headroom on each side. Distinguishable from compass discs (~13 px diameter) by shape (rect vs circle) more than by size.

### Compass letter font size: 10 pt bold (inside 0.18 in / 6.5 px-radius disc)

- **Tried 9 pt bold**: at print scale this dropped below the cap-height legibility threshold for arm's-length reading; in the prototype the letter felt "stuck inside" the disc with no breathing room.
- **Tried 12 pt bold**: required disc radius >8 px to contain the letter, which made the compass letters bigger than the team-aggregate star (~16 px wide) — wrong visual hierarchy.
- **Locked 10 pt bold inside 0.18 in disc**: letter fills the disc proportionally, distinguishable from the pill text (also 9 pt bold but in a rect with name+number contents). Hits the TN-16 minimum (≥7 pt absolute) with margin.

### Compass ring radius: 80% of available radius, asymmetric `R_x` / `R_y`

- **Tried 75%**: compass letters sat noticeably closer to the star than to the field edge. When a populated zone had an outlier pill near the same angular position, the pill and compass disc overlapped at the disc edge.
- **Tried 85%**: edge-clamping fired on the deep-CF and foul-corner letters more often than not, particularly when the star itself was offset toward an edge. The clamping moved letters inward by ~6 px, breaking the angular symmetry the compass is supposed to communicate.
- **Tried symmetric `R = 0.80 × min(field_w/2, field_h/2)`**: gave a smaller-than-necessary ring on the wider axis. Upper letters clamped while lateral letters had unused room.
- **Locked 80%, asymmetric `R_x` / `R_y`**: pulls the ring out to ~80% of available radius along each axis independently. Edge clamping rarely fires; when it does (e.g., star offset toward LF corner), the affected letter slides inward 2–4 px along its radial — visually small enough to preserve the compass shape.

### Density background opacity: 12%

- **Tried 15% (per UXD round-1 spec)**: density dots competed with the textbook reference dot (also a small open mark) and made the field look "dirty" — the eye couldn't separate the signal layer (pills, star, letters) from the density layer.
- **Tried 8%**: density dots were essentially invisible at print scale on a standard laser printer; coach couldn't tell whether the field had density data behind it.
- **Locked 12%**: density layer reads as a faint "weight" behind the field elements without competing with any signal layer. At print scale on a 600-dpi laser, the dots are visible as a soft pattern; they recede on closer inspection rather than dominating.

### Header height: 0.65 in

- **Tried 0.50 in**: opponent + position + coverage cue couldn't all fit on one line at the locked typography sizes without truncating the coverage cue ("Through Apr 12 (8 g)" instead of "(8 games)"). Forcing the coverage cue to a second line wasted vertical space.
- **Tried 0.80 in**: gave the header lots of breathing room but ate body height — the SVG dropped to 3.95 in tall, compressing the field's vertical extent and making the compass letters in the deep-CF zone visually approach the OF arc.
- **Locked 0.65 in**: two-row CSS grid (opponent + coverage cue on row 1, position name spanning both columns on row 2). Body retains 4.30 in for the field + sidebar; no truncation in the header.

### Font family stack: `Arial, Helvetica, sans-serif`

- **Tried `system-ui, -apple-system, "Helvetica Neue", sans-serif`** (UXD round-1 proposal): rendered differently on browser print (Chrome on macOS got San Francisco; Chrome on Linux got DejaVu Sans) which broke calibration across print paths.
- **Tried `"Helvetica Neue", Helvetica, Arial, sans-serif`**: Windows print servers commonly lack Helvetica Neue and silently fall back through the stack — calibrated metrics drift between dev (macOS) and any other path.
- **Locked `Arial, Helvetica, sans-serif`**: Arial is universally installed; binary-identical metrics to Helvetica family; predictable across every browser print path and weasyprint server-side render. Matches E-228 mockup precedent.

### Sidebar font: proportional Arial with `tabular-nums` (NOT monospace)

- **Tried 7 pt monospace** (PROVISIONAL v0 spec): tabular alignment was perfect but proper names looked "computery" at 7 pt — strokes felt thicker, character spacing felt mechanical, names like RAMIREZ vs WRIGHT didn't gain the natural-word recognition affordance that proportional text gets.
- **Tried 7.5 pt proportional Arial without `tabular-nums`**: names looked great; jersey column wandered when single-digit and double-digit numbers mixed (e.g., #4 sat slightly right of #11's `1`, making the column edge ragged).
- **Locked 7.5 pt proportional Arial + `tabular-nums` on jersey and zone cells**: names read naturally; jersey column aligns perfectly; zone-letter column aligns perfectly. CSS grid with explicit column widths (0.34 in jersey, 1fr name, 0.20 in zone) reinforces the alignment.

### Legend text + typography: `★ default · ○ textbook · A-H outliers` at 7 pt (per coach AC-12)

- **Started at PROVISIONAL v0** (carried from epic TN-3): `★ team default · ○ textbook · A–H = outlier zones (see right)` at 7 pt. At the 3.95 in card-inner width the 7 pt rendering wrapped to two lines, eating into the body zone.
- **Tried dropping to 6.5 pt** (UXD self-validation iteration): fit on one line but flagged in the AC-11 self-validation as "below TN-16 floor of 7 pt; may not survive coach review."
- **Coach AC-12 verdict (2026-05-17): FAIL on 6.5 pt.** Rationale: TN-16's 7 pt minimum is the dugout-glance floor; 6.5 pt at 70% grey in dugout shade forces a freshman with cold cards to squint. "Acceptable for a briefed player mid-at-bat, but violates dugout-glance standard." Coach pre-approved Option 1 as the fix.
- **Tried Option 2 (keep "see right" parenthetical, accept the 7 pt wrap)**: rejected by coach as wasted vertical space, risks bleeding into body zone.
- **Tried Option 3 (drop "○ textbook" reference)**: defensible but leaves the open circle on every card unexplained. Coach preferred Option 1.
- **LOCKED to Option 1**: `★ default · ○ textbook · A-H outliers` at 7 pt 70% grey. Removes "(see right)" parenthetical (sidebar IS to the right; zone letter is also printed there), removes "team" qualifier on star (star is the default by construction), drops " = outlier zones" gloss (the letters appear inline next to outlier pills — the legend is a label, not a sentence). Shortened content fits one line at 7 pt — solves the geometry constraint at the root, not by fighting it. **All three symbol types still present.** Star BIP caption bumped 6.5 pt → 7 pt in the same fix for typography-floor consistency (coach gave permission to bump if no geometry tradeoffs; SVG slot has ample room 18 viewBox units below star center).

### Pill projection scale: `scale_x` = 18 px, `scale_y` = 22 px per ordinal unit (viewBox space)

- **Tried uniform `scale = 25 px`**: outlier pills in adjacent ordinal buckets (deviations differing by 1 unit on the same axis) sat ~25 px apart. On the wider depth axis this was fine, but on the narrower direction axis pills crowded each other and required jitter that wasn't structurally needed.
- **Tried uniform `scale = 15 px`**: pills clustered tightly around the star and barely separated even at ±2 deviation — the "field plot IS the magnitude" principle (TN-5) was undermined.
- **Locked asymmetric 18 / 22 px**: honors the field's natural aspect (field is ~1.6× as tall as wide in viewBox). ±3 ordinal units on direction = 54 px (visible separation, within field width); ±3 on depth = 66 px (visible separation, within available depth). Compass ring radius `R_units ≈ 2.2 × scale` puts compass letters at zone centroids by construction.

### v1 → v1.1 spec amendment: Coordinate-space rescaling (normative) subsection added to §B

- **Why**: UXD post-validation finding (2026-05-17, during E-229-03 dispatch window) identified that engine output `team_position_aggregate.(star_x, star_y)` is written in `src/charts/spray.py::_raw_to_svg`'s 320×480 GC canonical coord space (per `spray.py:47` + epic TN-15), but §B's per-card SVG viewBox is 200×320 (the quarter-letter-tuned aspect 0.625 locked at v1). Without explicit rescaling, E-229-03 / E-229-06 would place the star at engine-space coordinates inside a card-space viewBox — wrong location, silent failure (no exception, just visually wrong).
- **Why the validation pass missed it**: AC-11 (UXD self-validation) focused on typography legibility, not coord arithmetic. AC-12 (coach review) reviewed the printed prototype where SVG `preserveAspectRatio="xMidYMid meet"` absorbs viewBox dimension differences silently — the prototype was visually correct because the prototype HTML hand-placed star/pill coordinates in viewBox space directly, never round-tripping through engine coordinates.
- **Why not a calibration_history entry**: this is clarification of an existing constant relationship that should always have been documented, not a real-opponent calibration change. `calibration_history` is reserved for entries of shape `{date, opponent, changed_constants[]}` produced during Rollout. v1.1 is a documentation completeness fix.
- **Tried adding the rescaling factor to the engine** (Option B from UXD's offer): rejected — would push viewBox geometry into the engine layer, coupling DB-resident constants to a particular render geometry. The engine's coord space is the DB contract; render geometry is a consumer concern.
- **Tried changing the per-card viewBox to match the engine 320×480** (Option C from UXD's offer): rejected — would invalidate every numeric value in §B (star size in viewBox, pill size in viewBox, scale_x/scale_y in viewBox, ring radius in viewBox), forcing a full re-calibration pass and re-running coach AC-12 review. Disproportionate cost for the same outcome.
- **Locked Option A** (this entry): document the rescaling responsibility in §B as a normative subsection. Consumers (E-229-03 / E-229-06) apply rescaling at the read-then-place boundary. Engine unchanged. Spec gains documentation completeness. Coach AC-12 verdict not invalidated. Version bumped 1 → 1.1 to mark the amendment in commit history without polluting `calibration_history`.
- **The v1.1 formula was geometrically wrong, corrected at v1.2** (see next Decisions Log entry). v1.1 derived its rescaling formula from the viewBox-to-viewBox dimension ratio (200/320, 320/480) without accounting for the fact that the field outline does NOT fill the viewBox edge-to-edge. SE caught this during E-229-03 implementation and shipped the correct field-anchored mapping; v1.2 ratifies SE's implementation as the canonical contract.

### v1.1 → v1.2 spec amendment: Coordinate-space rescaling formula corrected from pure scalar to field-anchored

- **The bug in v1.1's formula**: derived from the viewBox-to-viewBox dimension ratio (`x * 0.625, y * 0.667`). Treats the engine and card viewBoxes as if both were pure field-canvases. Reality: the per-card 200×320 viewBox carves out 80 y-units of header space at the top and 15 y-units of legend space at the bottom — the field outline only occupies the inner rectangle (10, 80) — (190, 305).
- **What the pure-scalar formula produced** (verifiable from SE's math): engine deep CF (y=0) → card y=0 (header zone, ABOVE the painted fence arc at y=80); engine home plate (160, 295) → card (100, 196.7) (mid-card, far above the painted home plate at y=305). Star would render detached from the painted field outline; coverage cue / fielder visual landmarks broken. Silent failure — no exception, just visually wrong.
- **Why v1.1's spec author error slipped through**: UXD's Finding 1 framing emphasized the viewBox-dimension ratio (200/320 = 0.625, 320/480 = 0.667). I (PM) lost the "plus any anchor shift" qualifier in the v1.1 authoring — wrote down the dimension ratio as if it were the complete mapping, never plugged engine landmark coords through the proposed formula to check landing positions.
- **Why AC-11 / AC-12 didn't catch it in E-229-2b**: validation-by-rendering, not validation-by-formula. AC-11 was typography-focused (legibility of pills, letters, sidebar, header, legend). AC-12 reviewed the printed prototype where the field outline was already drawn at the correct card-space offsets by the prototype HTML itself — the rendering "looked right" because the HTML hand-placed coordinates in viewBox space directly, never round-tripping through any rescaling formula.
- **Actual sequence of events** (corrected per team-lead timeline reconstruction): SE first shipped E-229-03 v1.0 with the field-anchored mapping (correct). When PM's v1.1 amendment landed during the same dispatch window with the pure-scalar formula, SE silently conformed the code to v1.1 (matching the spec, but breaking the geometry). SE then independently traced the v1.1 formula through engine landmark coordinates, saw the geometric breakdown (engine deep CF y=0 → card header zone; engine home plate y=295 → card mid-card), and surfaced the spec-vs-geometry conflict via the team-lead. SE's R2 restores the field-anchored mapping with constants (`_CARD_LEFT_X`, `_CARD_FENCE_Y`, `_CARD_HOME_Y`, `_ENGINE_W`, `_ENGINE_HOME_Y`, `_CARD_FIELD_W`, `_CARD_FIELD_H`). The lesson here is process-level, not author-level: SE conformed-then-questioned rather than questioned-then-conformed; either order surfaces the bug, but a "verify-formula-with-worked-examples" gate on spec amendments would have prevented the rework round entirely.
- **Locked field-anchored formula** (v1.2): `card_x = 10 + (x_engine / 320) * 180; card_y = 80 + (y_engine / 295) * 225`. Engine LF foul corner (0, 0) → card (10, 80) ✓; engine home plate (160, 295) → card (100, 305) ✓; engine RF foul corner (320, 0) → card (190, 80) ✓. All field-interior points land proportionally inside the card's painted field outline.
- **Why not bump to v2 / append to calibration_history**: this is a spec correction (PM authored a geometrically wrong formula in v1.1; SE caught it during implementation), not a real-opponent calibration change. The `calibration_history` invariant holds (still `[]`) — bumped `version` to 1.2 with a `version_history` entry; no Rollout entry created.
- **Implementation reference**: `src/reports/positioning_card.py::_engine_to_card_xy` (E-229-03). E-229-06 prep page reuses the same mapping. Whether E-229-04 / E-229-06 imports the helper directly or duplicates the constants is a deferred decision; the function shape is stable enough to import.
- **Lessons for the spec author (PM) — captured to PM agent memory after E-229 closes**:
  1. Spec amendments that touch numeric formulas should be paired with a worked example (e.g., "engine home plate (160, 295) → card __, matching card home plate (100, 305)"). Writing the worked example would have surfaced the v1.1 geometry error at authoring time.
  2. The "validation-by-rendering vs validation-by-formula" gotcha: a rendered prototype that "looks right" does NOT validate a coord-mapping formula, because the prototype HTML places coordinates directly without round-tripping through the formula. AC verification of coord transforms requires plugging input landmarks through the formula and checking that output landmarks land at the right visual positions.

---

## Frontmatter usage notes

- `status: PROVISIONAL` (v0) = downstream stories SHOULD NOT yet hardcode these values; consume after `LOCKED` flip
- `status: LOCKED` (v1+) = artifact is authoritative; downstream stories consume directly
- `version` bumps on each material change. The `version_history` frontmatter field records each transition with date and short transition note. Old versions are not preserved here in full (per E-228 archive precedent, full history lives in commit log); the `version_history` log is for at-a-glance traceability of what changed when.
- `calibration_history` is a list of `{date, opponent, changed_constants[]}` entries appended during Rollout — reserved for real-opponent calibration drift. Spec clarifications (e.g., the v1 → v1.1 Coordinate-space rescaling amendment) bump `version` and `version_history` but do NOT append to `calibration_history`.
- `produced_by` documents the story that flipped status to LOCKED (E-229-2b at v1; later epics if any constant materially changes)
