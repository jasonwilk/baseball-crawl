# E-229-06: Coach prep page — full-field overlay, all 6 positions

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, the report bundle includes a pre-game prep page: a single full-field SVG showing all 6 position stars + all outlier batter pills from all positions overlaid, with a faint spray-density background and a complete jersey×position lookup sidebar. The page is letter landscape and serves as the coach's analysis canvas before the game — distinct from the in-game call sheet (E-229-07) and the per-position cards (E-229-05).

## Context
UXD round-1 identified the prep page as a coach-facing pre-game artifact: full field, all positions, all outliers overlaid in one view. The coach uses it to absorb the opponent's defensive shape before the game starts, then switches to the call sheet for in-game calls.

The prep page reuses the field SVG generator from E-229-03 — it just renders 6 stars + all outliers on one big field rather than 6 separate per-position diagrams. The spray-density background carries the whole-team spray (same JOIN as the cards) so the coach can see why the stars sit where they do.

Each batter pill on the prep page carries a position tag in addition to the jersey number (e.g., "#7 LF") so the coach can identify cross-position outliers (a batter who's flagged on multiple cards).

## Acceptance Criteria
- [ ] **AC-1**: Single full-field SVG rendering all 6 position stars (LF, CF, RF, 3B, SS, 2B) at their `team_position_aggregate` `(star_x, star_y)` coordinates.
- [ ] **AC-2**: All outlier batter pills from all 6 positions overlaid on the same SVG. Each pill format is `7-LF` (no `#`, hyphen separator) per UXD M-2 lock — saves pill width on the dense prep page where pills from all 6 positions overlay. Pill style (fill, border, font, dimensions) consumed from the locked-constants artifact §B (per E-229-2b citation pattern); E-229-04 pill style applies. Typography consumed from artifact §E (typography parity across artifacts). Jersey lookup follows epic TN-7 JOIN pattern with last-initial fallback.
- [ ] **AC-3**: Faint spray-density background showing all opponent (x, y) BIPs from `spray_charts`, same JOIN as E-229-03 AC-5. Same opacity (~15% single-channel grey). Background is hidden when `is_low_confidence = 1` for ALL 6 position rows.
- [ ] **AC-4**: Right sidebar: complete jersey → zone-letter × position lookup table. Sort rule per coach BC-1 + Codex iter-3 P1.1 lock: **two partitions with alphabetical-by-last-name ordering within each partition**:
  - **Partition 1 (flagged)**: all batters with at least one non-`·` cell (any outlier zone at any of the 6 positions), sorted alphabetical-by-last-name within
  - **Visual group divider** (horizontal rule or extra row spacing)
  - **Partition 2 (default)**: all batters with all-`·` cells, sorted alphabetical-by-last-name within
  
  No batting-order conditional (`team_rosters` has no `batting_order` column per DE B-5). No jersey-sort, no severity-sort — coach explicitly rejected both during Codex iter-3 P1.1 consult ("Jersey: bad sort for the prep page sidebar — coach reads by name not by jersey, alpha gives predictable scan order"; severity: "analytically satisfying but adds cognitive complexity, no clean signal across batters"). Coach's framing: "Simple, stable, no special data needed."
  
  Each column is a position (LF, CF, RF, 3B, SS, 2B). Cells contain the zone letter or `·` for team-default. The flagged-first partition is the **key difference from E-229-07** (call sheet uses strict alphabetical with NO group divider per coach BC-1's lineup-card-pairing logic — call sheet is in-game tracking, prep page is pre-game analysis).
- [ ] **AC-5**: Header: opponent name + coverage cue. Coverage-cue format from the locked-constants artifact §F shared design tokens (`Through {Mon Day} ({N} games)` per coach IM-2 + E-229-08 AC-4a snapshot contract). Header typography per artifact §E typography parity (prep-page header is the largest header in the bundle since this is a single-page artifact).
- [ ] **AC-6**: Print CSS supports letter landscape: `@page prep-page { size: letter landscape; margin: 0.25in }`. The prep page does NOT share a CSS page block with the per-position cards (different orientation).
- [ ] **AC-7**: Zero-coverage state: when team has 0–14 BIPs total, the prep page renders header + a dominant "Not enough spray data — play your standard alignment" message in place of the field+sidebar. No stars, no outliers, no density bg, no lookup.
- [ ] **AC-7a**: **No-outliers state (per UXD I-8)**: when team has ≥15 BIPs (star renders) but ZERO batters have `zone_id IS NOT NULL AND is_thin = 0` (uniform-spread opponent), the prep page renders the full field with 6 stars and density bg, no pills, sidebar shows the banner "No outlier batters this opponent. Play team default at all positions." Header still renders normally.
- [ ] **AC-8**: Marker collision handling: where pills from different positions cluster at the same SVG location (e.g., a pull-side hitter shows as a left-field outlier on both LF and CF cards), apply the same deterministic radial jitter from E-229-04 keyed on jersey number, with position tag ordering as the secondary key.
- [ ] **AC-9**: Tests cover the full state, the zero-coverage state, the no-outliers state per AC-7a, the sidebar lookup table contents, the cross-position collision handling, and snapshot the SVG output.
- [ ] **AC-10** (Tier 2 LLM rationale slot per Codex iter-3 P1.2 + UXD lock): each sidebar batter row carries an optional second-line rationale slot underneath the primary row (jersey + last-name + per-position zone-letter cells). The slot is populated from the template-context value threaded by E-229-08's bundle assembler (`Optional[str]` per E-229-08 AC-7); on None, the slot renders nothing (collapsed — no placeholder, no whitespace). Typography is consumed from the locked-constants artifact §E "Rationale" subsection (italic 8pt 50% grey, CSS `-webkit-line-clamp: 2`, overflow hidden, no ellipsis). Tests cover (a) rationale-present rendering with 2-line clamp behavior; (b) rationale-None rendering with no slot (collapsed row); (c) typography matches the artifact's §E spec verbatim.

## Technical Approach

**Template surface**: new template `src/api/templates/reports/positioning_prep.html`, or a section of `positioning_cards.html` if it's cleaner to keep them in one file. Look at E-228's renderer structure to decide.

**Reusing the field-SVG generator from E-229-03**: the prep page is essentially "render 6 cards' worth of stars+pills onto one big field SVG instead of 6 small ones." The function from E-229-03 should be parameterizable so it can target either the per-position card geometry or the prep page geometry. If the function is already shaped that way after E-229-03, this story consumes it directly; if not, E-229-03 refactor may be needed (flag to PM during refinement if so).

**Sidebar contents**: mirror the call sheet (E-229-07) but as a sidebar rather than a full page. Sort order: **alphabetical by name** (matches the call sheet's locked sort per Phase 3 iteration 1 DE B-5 lock; no batting_order conditional). Same cell contents (A-H or `·`). **Flagged-first grouping APPLIES on the prep page** (per coach BC-1: appropriate for pre-game analysis where the coach is reviewing exceptions, NOT for in-game tracking — that's why flagged-first was removed from E-229-07's call sheet but KEPT here).

**Cross-position position-tag suffix on pills**: when a pill represents the same batter at a different position than the dominant outlier, append the position tag. Format: bold jersey + small position tag below or beside. UXD's call on exact rendering.

**Print orientation**: letter landscape gives the field width to layout the full diamond at scale while leaving sidebar space.

## Dependencies
- **Blocked by**: E-229-03 (field SVG generator is the surface this story reuses), E-229-04 (collision-jitter logic is shared per AC-8), E-229-2b (typography per §E + legend/coverage tokens per §F + pill style per §B all consumed from locked-constants artifact per Codex iter-3 P2.4 lock; AC-2/AC-4/AC-5 cite the artifact)
- **Blocks**: E-229-08 (bundle generation needs the prep page to assemble the 4-page bundle)

## Files to Create or Modify
- `src/api/templates/reports/positioning_prep.html` — create
- `src/reports/positioning_prep.py` — create (focused module per Codex P2.6 lock; isolated from E-229-07's call-sheet module so the two stories cannot conflict on the same file). May import shared helpers from `src/reports/positioning_card.py` (E-229-03) for field-SVG primitives.
- `tests/test_positioning_prep_render.py` — create

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-229-08**: a complete letter-landscape prep page ready to insert as page 2 of the bundle.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-position collision (a batter outlier on LF AND CF AND RF) is the realistic case the prep page surfaces best — coach sees one pill with "7" appearing in 3 zones. UXD's pill-rendering details (color, position-tag placement) are this story's design call.
