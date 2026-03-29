# E-185: Scouting Report Redesign

## Status
`COMPLETED`

## Overview
Redesign standalone scouting reports to be more informative and visually useful for coaching staff. Adds coaching-requested data columns (K%, BB%, PA, SB-CS, handedness), heat-map color coding that instantly highlights threatening players, key-players callout, enriched recent form with opponent names and colored chips, team spray chart, and a print-optimized layout -- all within the existing self-contained HTML report format.

## Background & Context
The user reviewed a current report (Millard South Reserve Patriots 2026) and identified two categories of issues: (1) the data isn't sorted or organized for quick coaching decisions -- pitching sorted by ERA surfaces one-inning wonders before starters, batting sorted by AVG shows high-average bench players before regulars; (2) the visual design doesn't make threats obvious -- a coach scanning a table of 15 batters needs heat-map-style color cues to spot the dangerous hitters in 30 seconds.

Baseball-coach consultation identified must-have data changes (K%/BB% columns, sort by IP/PA, key players callout) and should-have enrichments (opponent names on recent form, handedness, team spray chart, runs scored/allowed). UX-designer provided a complete heat-map color system (5-level green gradient) with composite threat scoring and layout improvements.

Promotes coaching-relevant portions of IDEA-037 (scouting report redesign). IDEA-035 (opponent page redesign) is the dashboard counterpart and remains a separate concern.

Expert consultation: Baseball-coach (completed -- data requirements, sort priorities, key players spec). UX-designer (completed -- heat map system, layout, color values, print considerations).

## Goals
- Coaches can identify the 2-3 most dangerous hitters and pitchers within 30 seconds of opening a report
- Report tables are sorted by playing time (IP desc for pitching, PA desc for batting) so starters appear first
- Key coaching metrics (K%, BB%, PA, SB-CS, handedness) are visible without manual calculation
- Heat-map colors survive PDF export via browser print dialog
- Report remains a self-contained HTML file with no external dependencies

## Non-Goals
- Dashboard opponent detail page changes (separate flow, separate epic)
- Proactive flags / streak detection (requires per-game analysis pipeline -- future IDEA-037 scope)
- Server-side PDF generation via weasyprint (deferred to a future epic)
- Lineup tendency / batting order data (not yet populated in schema)
- L/R split columns (IDEA-029 -- handedness data source unknown for opponents)

## Success Criteria
- A newly generated report shows heat-map coloring on key stat cells, with the most threatening players in darker green
- Pitching table is sorted by IP descending; batting table by PA descending
- K%, BB%, PA columns appear in the batting table; handedness appears in the pitching table
- Key Players callout box appears at the top with the primary pitcher and top batter
- Recent form shows opponent names, home/away indicator, and colored result chips
- Team spray chart appears alongside individual player spray charts
- Reports render correctly in browser and produce legible, colored PDFs via Ctrl+P

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-185-01 | Enrich report data pipeline | DONE | None | SE |
| E-185-02 | Redesign report template | DONE | E-185-01 | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Heat Map System
Five-level single-hue green gradient indicating threat level (higher = more dangerous):
- Level 0: `#ffffff` (white -- baseline or small-sample)
- Level 1: `#f0fdf4` (lightest green)
- Level 2: `#dcfce7` (light green)
- Level 3: `#86efac` (medium green)
- Level 4: `#16a34a` with white text (dark green -- top threat)

**Heat-mapped stats:**
- Batting: AVG, OBP, SLG (higher = more threatening = darker green)
- Pitching: ERA (inverted -- lower ERA = better = darker green), K/9 (higher = darker), WHIP (inverted -- lower WHIP = darker)

**Composite threat score (THR):**
- Batting: OBP × 0.40 + SLG × 0.35 + AVG × 0.25
- Pitching: ERA × 0.40 (inverted) + K/9 × 0.30 + WHIP × 0.30 (inverted)

Percentiles are computed within the team's own roster (not league-wide). Players are ranked among non-small-sample teammates for each stat; percentile = rank / count. THR percentile is computed from the composite score. Percentile thresholds for heat levels: 0-19% → level 1, 20-39% → level 2, 40-69% → level 3, 70-100% → level 4. Small-sample players (< 20 PA batting, < 15 IP pitching) receive level 0 (no heat) and dimmed row text (`#9ca3af`).

The renderer computes percentile ranks and assigns heat levels as integers (0-4) in the template context. The template maps levels to CSS classes.

**THR column display:** The THR column is a narrow visual-only colored block (~24px wide) with no text value. The heat-map background color alone conveys threat level. This keeps the column useful for 30-second scanning without adding cognitive load.

### TN-2: Sort Order Changes
- **Pitching**: Sort by `ip_outs DESC` (most innings first -- shows starters before relievers). Change the ORDER BY in `_query_pitching()`.
- **Batting**: Sort by PA descending (computed as `ab + bb + hbp + shf`). Change the ORDER BY in `_query_batting()`.

Both sorts are applied in the generator queries (ORDER BY clause changes).

### TN-3: New Batting Columns
- **K%**: `so / pa × 100` (formatted as `"18.2%"`)
- **BB%**: `bb / pa × 100` (formatted as `"12.1%"`)
- **PA**: plate appearances (ab + bb + hbp + shf) -- display column
- **SB-CS**: combined display (e.g., `"5-1"`); CS must be added to the `_query_batting()` SELECT from `player_season_batting.cs`
- **HBP**: already in data, just needs a template column
- **XBH**: combined extra-base hits (2B + 3B + HR) -- computed in renderer
- **Column order**: `#, Player, THR, OBP, AVG, SLG, K%, BB%, GP, PA, AB, H, XBH, HR, RBI, BB, SO, SB-CS, HBP`

### TN-4: New Pitching Display
- **Handedness**: `throws` field already in `_query_pitching()` result, displayed after player name (e.g., `"Smith (L)"`)
- **Column order**: `#, Player, THR, ERA, K/9, WHIP, GP, IP, H, ER, BB, SO, #P, Strike%`

### TN-5: Recent Form Enhancement
Current: plain text string `"W 17-5, W 15-4, ..."` assembled in renderer from a list of `{result, our_score, their_score}` dicts.

New: structured list of game dicts with `result`, `our_score`, `their_score`, `opponent_name`, `is_home`. The `_query_recent_games()` function must join the `teams` table to resolve the opponent name from `home_team_id`/`away_team_id` (opponent = whichever is not the scouted team). If opponent name is NULL (team not in DB or name not populated), display "Unknown" as fallback. The renderer passes the structured list directly to the template (instead of formatting to a string). The template renders each game as a colored chip.

**Chip colors:**
- Win: `background: #dcfce7; color: #166534; border: 1px solid #bbf7d0`
- Loss: `background: #fee2e2; color: #991b1b; border: 1px solid #fecaca`
- Tie: `background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb`
- Chip styling: `padding: 2px 8px; border-radius: 4px; font-size: 8pt; display: inline-block; margin: 2px`
- Chip text format: `"W 17-5 vs Millard South"` (home) / `"L 3-7 @ Millard South"` (away)

### TN-6: Key Players Callout
A "Key Players" section after the executive summary strip, before tables:
- **Top pitcher**: highest `ip_outs` among non-small-sample pitchers (≥ 15 IP = 45 outs). Display: name, ERA, K/9, IP.
- **Top batter**: highest OBP among non-small-sample batters (≥ 20 PA). Display: name, OBP, SLG, PA.

Computed in the renderer from the pitching/batting lists after rate stats are computed. If no players meet thresholds, the section is omitted.

### TN-7: Team Spray Chart
Aggregate all individual player spray chart events into a single team-level chart. Rendered via the existing `render_spray_chart()` function in `src/charts/spray.py` with title including team name. Added to template context as `team_spray_uri` (a base64 data URI string), separate from the per-player `spray_data` dict. Requires ≥ 20 total BIP to render (per CLAUDE.md "20 BIP for team aggregates" convention). Displayed at full content width before individual player charts.

### TN-8: Runs Scored/Allowed
Query average runs scored and allowed per game from the `games` table for the team/season. New function in `generator.py` alongside existing `_query_record()`. Display in the executive summary strip: `"Avg: 8.2 scored / 4.1 allowed"`.

### TN-9: Self-Contained HTML Constraints
- All CSS must be inline (in `<style>` tags) -- no external stylesheets or CDN references
- Spray charts remain base64-encoded data URI PNGs
- `print-color-adjust: exact` and `-webkit-print-color-adjust: exact` on `body` for PDF color fidelity
- `@page { size: landscape; margin: 0.5in; }` retained for landscape PDF output
- Autoescape enabled (Jinja2 `| e` filter for user-supplied text)

### TN-10: Layout Structure (UXD Design)
1. **Header**: "SCOUTING REPORT" as small-caps label above team name (reversed from current: currently team name is above label)
2. **Executive summary strip**: single bar combining: record, game count, freshness date, runs scored/allowed avg. Replaces separate freshness-bar and recent-form blocks.
3. **Recent Form chips**: colored result indicators (green=W, red=L, gray=T) with opponent name and score, displayed as inline chips below the executive summary
4. **Key Players callout**: compact box highlighting top pitcher and top batter (per TN-6)
5. **Pitching table**: with heat map, THR column, sort annotation below header ("Sorted by innings pitched")
6. **Batting table**: with heat map, THR column, sort annotation ("Sorted by plate appearances"), diamond indicator (♦) next to player name for players with spray chart data
7. **Spray charts**: team chart first (full content width), then individual charts at 2-per-row (larger than current 3-per-row), with stat summary line under each name
8. **Roster**: retained as-is (4-column grid)
9. **Footer**: generation date, expiry date, bbstats.ai attribution

### TN-11: CSS Design Details
- Heat map column headers get a subtle green underline (`border-bottom: 2px solid #16a34a`) to indicate which columns are color-coded
- Column group separators: subtle vertical borders between identity group (#/Player), threat group (THR), rate group (OBP/AVG/SLG/K%/BB% or ERA/K9/WHIP), and volume/counting groups
- Small-sample rows: dimmed text color (`#9ca3af`), no heat map coloring
- **Row separation**: Disable zebra striping (`tr:nth-child(even) { background }`) on heat-mapped tables to avoid color clashes with heat-map cell backgrounds. Use bottom borders on rows (`border-bottom: 1px solid #e5e7eb`) for visual separation instead.
- **Diamond indicator**: `color: #2563eb` (blue) to visually distinguish from player name text
- **Spray chart stat summary**: `font-size: 7.5pt; color: #6b7280`, format: ".325 AVG · 48 PA · 31 BIP"
- **Key Players callout box**: `border: 1px solid #d1d5db; border-radius: 6px; padding: 10px 14px; margin: 8px 0; background: #f9fafb`. Two-column flex layout. Labels "ACE"/"TOP BAT" in `font-size: 7pt; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280`. Player name `font-weight: bold; font-size: 9pt`. Stats `font-size: 8pt; color: #374151` -- e.g., "2.10 ERA · 8.4 K/9 · 42.0 IP"
- **Mobile responsive** (`max-width: 640px`): hide volume/counting columns via `display: none`. Batting shows: #, Player, THR, OBP, AVG, SLG, K%, BB%, PA, SB-CS. Pitching shows: #, Player, THR, ERA, K/9, WHIP, GP, IP, Strike%.

## Open Questions
- None -- coach and UXD consultation complete.

## History
- 2026-03-29: Created. Promotes IDEA-037 coaching-relevant scope. Coach and UXD consultation completed during pre-discovery phase.
- 2026-03-29: Set to READY after 5 review passes.
- 2026-03-29: COMPLETED. Both stories delivered: enriched data pipeline (heat maps, key players, K%/BB%/XBH/SB-CS, structured recent form, team spray chart, runs averages, sort order changes) and complete template redesign (heat-map color coding, executive summary strip, recent form chips, key players callout, expanded columns, 2-per-row spray charts, print-optimized layout). All 30 ACs verified.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 9 | 9 | 0 |
| Internal iteration 1 -- Holistic team (PM + coach + UXD) | 12 | 8 | 2 |
| Internal iteration 2 -- CR spec audit | 3 | 2 | 1 |
| Internal iteration 2 -- Holistic team (PM) | 4 | 3 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| **Total** | **33** | **27** | **3** |

Note: Some findings overlapped across sources (deduped during triage). Raw totals above.

### Code Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-185-01 | 2 | 0 | 2 |
| Per-story CR -- E-185-02 | 2 | 0 | 2 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 3 | 2 | 1 |
| **Total** | **7** | **2** | **5** |
