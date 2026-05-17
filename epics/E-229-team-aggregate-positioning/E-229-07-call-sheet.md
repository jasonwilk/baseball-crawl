# E-229-07: Coach call sheet — jersey × position matrix, alphabetical sort

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report bundle includes an in-game call sheet: a compact text matrix with rows = batters sorted alphabetically by name and columns = jersey, name, LF, CF, RF, 3B, SS, 2B. Cells contain a single zone letter (A–H) for outlier-zone batters or a center-dot (`·`) for team-default batters at that position. Letter landscape, single page. A top-of-sheet legend defines the A–H vocabulary.

## Context
This is the coach's primary in-game artifact. During an inning the coach scans by row (one batter coming to the plate, what does each position do?) and yells the two-part call ("#7 — LF Zone B, RF Zone G"). The matrix layout — jersey rows × position columns — survived both coach and UXD round-1 with independent agreement.

**Sort policy: alphabetical-by-name as the production sort.** Per DE B-5 (Phase 3 iteration 1 review): `team_rosters` has no `batting_order` column, and `player_game_batting.batting_order` is unpopulated schema with no loader writes. Coach explicitly accepted alphabetical as the fallback in Q-D. We're delivering on the fallback because the primary path (batting-order data) isn't yet wired — captured as IDEA-077 "Season-modal batting order from boxscore backfill" for future work (its own epic if promoted, NOT absorbed into E-229).

UXD round-1 added two refinements: a top-of-sheet legend and a flagged-first grouping. **Per coach BC-1 (Phase 3 iteration 1)**: flagged-first grouping is REMOVED from the call sheet because it breaks the artifact-pairing logic (coach's lineup card sits in alphabetical order in their pocket; the call sheet must mirror that ordering for fast in-game glance between artifacts). Flagged-first lives on the prep page (E-229-06) where the coach is doing pre-game analysis, not in-game tracking.

UXD I-7 added: **make the jersey column visually prominent** (11pt bold vs 9pt regular for other columns; left-aligned with extra horizontal padding) so jersey-lookup is fast when alphabetical order doesn't match the coach's lineup mental model.

## Acceptance Criteria
- [ ] **AC-1**: Matrix layout: rows are batters; columns are `# (jersey)`, `NAME`, `LF`, `CF`, `RF`, `3B`, `SS`, `2B`, **`NOTE`** (rightmost, per Codex iter-3 P1.2 + UXD lock — restores E-228's Note column pattern for Tier 2 LLM rationale display). NO transpose (positions are columns, not rows). Column order is fixed: jersey, name, OF positions left (LF/CF/RF), IF positions (3B/SS/2B), then NOTE. NOTE column width ~2.2" on letter landscape (call sheet has ~5" free horizontal room after the matrix per UXD). Per-column typography (font, weight, size, alignment, padding) consumed from the locked-constants artifact §E typography parity — specifically the jersey-column-prominence rule per UXD I-7 + the rationale typography spec from artifact §E "Rationale" subsection (italic 8pt 50% grey, 2-line clamp). Citation pattern per E-229-2b.
- [ ] **AC-2**: Cells contain a single zone letter (A–H) when the batter has an outlier zone at that position (`zone_id IS NOT NULL AND is_thin = 0`). Cells contain a center-dot character (`·`) when the batter plays the team default at that position (`zone_id IS NULL OR is_thin = 1`). Empty cells are NOT used.
- [ ] **AC-3**: **Row sort: alphabetical by player name** (per DE B-5 + UXD I-7 + Phase 3 iteration 1 locks). The implementation MUST NOT contain a `batting_order`-conditional check — `team_rosters` has no `batting_order` column and `player_game_batting.batting_order` is unpopulated; the conditional would be dead code that future readers misinterpret as a "promise." Alphabetical is the documented production sort because we're delivering on coach's documented fallback while the primary path isn't yet wired. Future work captured as IDEA-077.
- [ ] **AC-4**: **Strict alphabetical sort, NO flagged-first grouping** (per coach BC-1). All batters appear in alphabetical order; no group divider; no outlier/default partition. The call sheet's row order mirrors the lineup card the coach has in their pocket (also alphabetical or jersey-ordered depending on coach prep, but never split into flagged/default groups), enabling fast glance-between. Flagged-first grouping lives on the prep page (E-229-06), not here.
- [ ] **AC-5**: Legend at the top of the sheet, consumed from the locked-constants artifact §F shared design tokens (`COMPASS_LEGEND_LONG` constant — wording matches epic TN-3 vocabulary lock with "in/deep" not "shallow/deep"). The artifact is the single source of truth for legend wording per UXD M-1 + epic TN-16; this AC consumes the constant, does not redefine it. Citation pattern per E-229-2b.
- [ ] **AC-6**: Print CSS supports letter landscape, single page: `@page call-sheet { size: letter landscape; margin: 0.25in }`. The matrix is sized to comfortably fit ~20 batters × 8 columns on one letter landscape page.
- [ ] **AC-7**: **Header includes coverage cue** (per UXD I-1; the prior draft missed this). Header line: opponent name (large, left-aligned) + coverage cue right-aligned. Coverage-cue format string consumed from the locked-constants artifact §F shared design tokens (`Through {Mon Day} ({N} games)` per coach IM-2 + E-229-08 AC-4a snapshot contract). Typography for both opponent name and coverage cue per artifact §E typography parity (call sheet header is the same shape as cards header, smaller than prep page header). Citation pattern per E-229-2b.
- [ ] **AC-8**: Zero-coverage state: when team has 0–14 BIPs total, the call sheet renders header + a dominant "Not enough spray data — play your standard alignment" message in place of the matrix. No legend, no rows.
- [ ] **AC-8a**: **No-outliers state (per UXD I-8)**: when team has ≥15 BIPs but ZERO batters have any non-`·` cell (uniform-spread opponent), the matrix renders all-`·` rows in alphabetical order; NO group divider (no flagged group to separate from). Header banner reads "No outlier batters this opponent. Play team default at all positions." Legend still renders.
- [ ] **AC-9**: Tests cover: (a) alphabetical-by-name sort produces deterministic row order; (b) NO `batting_order`-conditional code path exists (`grep` AC: source contains no reference to `batting_order` other than possibly a code comment pointing to IDEA-077); (c) NO flagged-first grouping (`grep` AC: source contains no partition-by-flag logic); (d) legend content from the module constant; (e) zero-coverage state; (f) no-outliers state per AC-8a; (g) cell contents for outlier-zone and team-default batters; (h) header coverage cue; (i) **NOTE column rendering**: when `generate_rationale()` returns a string for a batter, the NOTE cell renders it with the §E rationale typography (italic 8pt 50% grey, 2-line clamp); when it returns None, the cell renders blank (no placeholder text). **Grep AC**: source contains `NOTE` column reference in the template — column header rendered.

## Technical Approach

**Template surface**: new template `src/api/templates/reports/positioning_call_sheet.html`. Pattern after E-228's call sheet template structurally (similar header + matrix layout) but with E-229 vocabulary and sort behavior.

**Render data**: render function in `src/reports/positioning_call_sheet.py` (focused module per P2.6) reads `batter_positioning` rows for all opponent batters across all 6 positions, JOINs `team_rosters` for jersey + JOINs `players` for name (no `batting_order` in the JOIN — that column doesn't exist on `team_rosters` per DE B-5), and pivots into the jersey×position matrix shape.

**Sort logic** (alphabetical only; no batting_order conditional per DE B-5):
```python
rows.sort(key=lambda r: r.player_name.lower())
```
No flagged-first partition. The row order mirrors the lineup card the coach has in their pocket — strict alphabetical, no group divider, no outlier-vs-default split.

**Cell contents**: a small helper function that takes the per-position row for a batter and returns either the zone letter or `·`. The center-dot character is U+00B7 (·); use the unicode literal, not a period.

**Header + coverage cue**: same coverage-cue source as E-229-03/E-229-06 (the freshness query producing "Through Mon Day (N games)").

**Batting-order data dependency**: Per DE B-5 in Phase 3 iteration 1 review: `team_rosters` has NO `batting_order` column; `player_game_batting.batting_order` is unpopulated schema with no loader writes. Alphabetical-by-name is the documented production sort. Future work captured as IDEA-077 (boxscore backfill); if promoted, IDEA-077 should be its OWN epic per DE, not absorbed into E-229.

## Dependencies
- **Blocked by**: E-229-02 (the engine output rows are what populate the matrix), **E-229-2b (locked-constants artifact for typography/legend/coverage citation per Codex iter-3 P2.4 lock)**
- **Blocks**: E-229-08 (bundle generation needs the call sheet as page 1)

## Files to Create or Modify
- `src/api/templates/reports/positioning_call_sheet.html` — create
- `src/reports/positioning_call_sheet.py` — create (focused module per Codex P2.6 lock; isolated from E-229-06's prep-page module so the two stories cannot conflict on the same file). Implements alphabetical-sort logic with NO flagged-first partition (per coach BC-1). May import shared helpers from `src/reports/positioning_card.py` (E-229-03) for legend constants.
- `tests/test_positioning_call_sheet.py` — create

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-229-08**: a complete letter-landscape call sheet ready to insert as page 1 of the bundle.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Per DE B-5 (Phase 3 iteration 1 review): `team_rosters` has no `batting_order` column; `player_game_batting.batting_order` is in the schema but unpopulated (verified via CLAUDE.md + `git grep` zero matches). Alphabetical-by-name is the documented production sort. The prior draft Note cited "DE round-2 confirmation" of batting_order availability — that citation was retracted during Phase 3 iteration 1 because DE round-2 covered jersey lookup only, not batting_order availability. PM owns the fabrication (captured in `feedback_no_fabricated_expert_confirmation.md`).

Future work: IDEA-077 "Season-modal batting order from boxscore backfill" captures the data-driven path (extract batting_order from boxscore JSON during loading; aggregate season-modal value; populate via new column or view). Per DE, IDEA-077 should be its own epic if promoted, NOT absorbed into E-229. Prerequisite: api-scout verifies the boxscore JSON carries `batting_order` field.
