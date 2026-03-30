# E-194: Spray Chart Card Redesign

## Status
`COMPLETED`

## Overview
Redesign spray chart cards across scouting report templates (standalone and opponent print) to use a compact 3-column layout with enriched per-player scouting stats, and extend direction/contact enrichments to all dashboard spray chart views. The current 2-column layout produces oversized cards that break across PDF pages and omit OBP, SLG, field zone tendencies, and contact type breakdowns -- data coaches need to make pre-game decisions. Individual player chart images also bake in a title that duplicates the HTML card header -- titles are removed globally since all views now show the name in HTML context.

## Background & Context
An experimental session (PM + UXD + SE) validated a new card design through rapid prototyping. Key findings:

- **Layout**: 3-column fits 6 cards per landscape PDF page vs 4 cards in the old 2-column layout.
- **OBP/SLG bug**: `_build_spray_player_stats()` in `renderer.py` never reads OBP/SLG from the batting lookup, even though the data is computed during heat-map enrichment. Cards show only AVG.
- **Missing scouting data**: No field zone breakdown (Left/Center/Right) or contact type distribution (GB/LD/FB/PU/BU).
- **Bunt indistinguishable**: Bunts use the same circle marker as ground balls on spray charts, losing coaching-valuable information ("it is GREAT to know that somebody is a good bunter").
- **Chart size**: 4x6 inch figsize creates excessive whitespace; 3x4 eliminates it and centers the field.
- **Print stats hidden**: `.spray-card-stats { display: none }` in the print CSS removes the only context line.

All design decisions were validated during the experiment session. No expert consultation required -- this is pure implementation of validated designs.

## Goals
- Spray chart cards display OBP, SLG (in addition to AVG), PA, field zone counts (L/C/R), and contact type counts (GB/LD/FB/PU/BU)
- 3-column layout in both screen and print for both templates
- Bunts visually distinct from ground balls on spray charts
- Charts compact (3x4) with no baked-in title for individual player charts (global title removal)
- All card stats visible in PDF output (not hidden by print CSS)
- Direction/contact enrichments on all dashboard spray chart views (player profile, opponent detail)

## Non-Goals
- Changes to team spray chart (stays full-width with title)
- Changes to chart rendering quality, DPI, or color scheme
- Changes to spray data thresholds or BIP minimums
- Heat-map coloring on opponent_print.html (black-on-white is fine for print)

## Success Criteria
- A scouting report PDF (both standalone and opponent print) shows 6 compact spray chart cards per page in 3-column layout, each card displaying jersey number, name, AVG/OBP/SLG slash line, PA badge, spray chart image, L/C/R zone counts, and contact type counts. Bunts appear as down-triangles on charts and are counted separately from ground balls.
- Individual player spray chart images no longer bake in a player name title (all views show the name in HTML context).
- Dashboard spray chart views (player profile, opponent detail) display L/C/R zone counts and contact type counts alongside the chart image.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-194-01 | Chart rendering: figsize, bunt marker, legend | DONE | None | se |
| E-194-02 | Data enrichment + scouting report template redesign | DONE | E-194-01 | se |
| E-194-03 | Opponent print template card redesign | DONE | E-194-01, E-194-02 | se |
| E-194-04 | Dashboard spray chart enrichments + global title removal | DONE | E-194-02, E-194-03 | se |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Bunt Marker and Legend
The bunt play_type currently maps to `"o"` (circle), identical to ground ball. Change to `"v"` (down-triangle). Update the legend from 4 entries/ncols=4 to 5 entries/ncols=5, adding a "Bunt" entry with the `"v"` marker.

### TN-2: figsize Change
Change `render_spray_chart` from `figsize=(4, 6)` to `figsize=(3, 4)`. This removes excess whitespace and centers the field. Individual player charts should be called with `title=None` (no baked-in title); team spray chart keeps its title.

### TN-3: OBP/SLG Computation and Formatting
Recompute OBP/SLG from raw batting fields (`h`, `ab`, `bb`, `hbp`, `shf`, `doubles`, `triples`, `hr`). Do NOT rely on `_obp_raw`/`_slg_raw` from heat computation -- both `render_report()` and the opponent print route pop these values before spray stats are built.

**Formulas**:
- OBP = (h + bb + hbp) / (ab + bb + hbp + shf)
- SLG = (h + doubles + 2*triples + 3*hr) / ab

**Formatting**: Baseball convention -- `.342` for values < 1.0, `1.000` for values >= 1.0. When denominator is zero, display `-`.

### TN-4: Field Zone Classification
Angle-based classification from home plate using SVG-space coordinates. Home plate is approximately at (160, 295) in SVG space. The raw API coordinates MUST be transformed to SVG space using `_raw_to_svg()` before classification.

**Angle convention**: `atan2(dx, -dy)` where `dx = svg_x - 160`, `dy = svg_y - 295`. Negating dy accounts for SVG y-axis inversion (y=0 is top/CF). This produces:
- Positive angles for balls hit to the RIGHT side of the field (svg_x > 160)
- Negative angles for balls hit to the LEFT side of the field (svg_x < 160)
- Zero for dead center

**Zone boundaries**: Define a named constant `ZONE_ANGLE_THRESHOLD = 0.206` radians (~11.8°) for equal angular thirds of fair territory. The constant value is authoritative; the degree approximation is for human readability only.

- **Left**: angle < -ZONE_ANGLE_THRESHOLD
- **Center**: angle between -ZONE_ANGLE_THRESHOLD and +ZONE_ANGLE_THRESHOLD
- **Right**: angle > +ZONE_ANGLE_THRESHOLD

We use absolute "Left/Center/Right" labels (not Pull/Center/Oppo) because we lack reliable batter handedness data. Events with `x=None` or `y=None` are excluded from zone counts.

### TN-5: Contact Type Categories
Five categories mapping `play_type` API values:
- **GB**: `ground_ball`, `hard_ground_ball`
- **LD**: `line_drive`, `hard_line_drive`
- **FB**: `fly_ball`
- **PU**: `popup`, `pop_fly`, `pop_up`
- **BU**: `bunt`

Note: The popup variant spellings (`popup`, `pop_fly`, `pop_up`) reflect values observed in the `_PLAY_TYPE_MARKERS` dict in `src/charts/spray.py`. SE should verify these variants against actual `spray_charts.play_type` values in the database. Events with `play_type=None` or unmapped values are excluded from contact counts.

### TN-6: Card Structure (UXD-validated)
```
┌─────────────────────────────┐
│ #24  J. Martinez            │  ← Identity: jersey 11pt/900 navy + name 11pt/700 black
│ .342 AVG  .421 OBP  .513 SLG │  ← Slash line: 9pt, stat values bold (600)
│ 47 PA                       │  ← PA badge: 8pt, depth-badge style
│                             │
│     ┌───────────────┐       │
│     │  spray chart  │       │
│     └───────────────┘       │
│                             │
│  Left 7  Ctr 3  Right 5    │  ← Direction: 8.5pt, values bold (700)
│  6GB  1LD  4FB  1PU  2BU   │  ← Contact: 8pt, weight 500
└─────────────────────────────┘
```

### TN-7: CSS Class Names
**Shared card properties** (apply to both templates):
- Card container: `border: 1px solid #d1d5db; padding: 6px 8px; text-align: center; break-inside: avoid; page-break-inside: avoid`
- Identity row: `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` (prevents long names from breaking layout)

**scouting_report.html** uses `.spray-card-*` prefix:
- `.spray-card-identity` -- container for jersey + name (truncation via shared props above)
- `.spray-card-jersey` -- 11pt, weight 900, color #1e3a5f, margin-right 4px
- `.spray-card-name` -- 11pt, weight 700, color #111 (replaces old `.spray-card-name`)
- `.spray-card-slash` -- 9pt, color #374151, bold values via `<b>` tags
- `.spray-card-pa` -- 8pt depth-badge style (gray pill)
- `.spray-card-direction` -- 8.5pt, color #374151, bold values (700)
- `.spray-card-contact` -- 8pt, color #6b7280, weight 500
- `.spray-card-empty` -- 8pt, color #999 (for "No spray chart data available" placeholder)

**opponent_print.html** uses `.tendency-card-*` prefix:
- `.tendency-card-identity`, `.tendency-card-jersey`, `.tendency-card-name`, `.tendency-card-slash`, `.tendency-card-pa`, `.tendency-card-direction`, `.tendency-card-contact`, `.tendency-card-empty`

### TN-8: Layout Specifications
**Both screen and print**: Use flexbox layout (not CSS Grid). E-192 proved that Chrome's print engine respects `break-inside: avoid` on flex items but not on grid items. Using the same layout engine for both contexts avoids visual discrepancies.

- Container: `display: flex; flex-wrap: wrap; gap: 8px`
- Cards: `flex: 0 0 calc(33.333% - 6px)` with `break-inside: avoid; page-break-inside: avoid`
- Print override (if any gap/sizing tweaks needed): `gap: 6px`

Remove `display: none` on `.spray-card-stats` in print -- all stats must be visible.

### TN-9: opponent_print.html Data Requirements
The opponent print route currently passes `player_spray_bip_counts` but NOT raw spray events. To display zone and contact stats, the route handler must:
1. Fetch raw spray events per player from the DB (for players meeting BIP threshold)
2. Classify events into L/C/R zones and 5 contact type categories
3. Compute OBP/SLG per player (batting data already available in `scouting_report`)
4. Pass enriched stats dict to template context

The classification logic (zone angles, contact type mapping) lives in shared helpers in `src/charts/spray.py` (added by E-194-02). The route handler imports and uses these helpers.

### TN-10: Card Iteration Base Difference
The two templates have intentionally different iteration bases:
- **Standalone report** (`scouting_report.html`): Renders spray cards only for players with sufficient BIP (iterates `spray_data`, which is pre-filtered by the BIP threshold). Below-threshold players get no card.
- **Opponent print** (`opponent_print.html`): Renders a card for every batter in the roster. Players below the BIP threshold get a card with name, slash line, and PA badge, plus "No spray chart data available" placeholder (no image, no direction/contact stats).

This difference reflects the templates' different contexts: standalone reports focus on players with data; opponent print shows the full roster for game-day reference.

### TN-11: Global Individual Chart Title Removal
The `/dashboard/charts/spray/player/{id}.png` endpoint (dashboard.py:2029) currently bakes a player name title into chart images via `get_player_spray_events()` → `render_spray_chart(events, title)`. Since ALL spray chart views (print and dashboard) now show the player name in HTML context, the baked-in title is redundant everywhere. Remove it globally by passing `title=None` to `render_spray_chart()` in the player chart endpoint. The team spray chart endpoint keeps its title.

### TN-12: Dashboard Spray Chart Views
The dashboard spray chart views are structurally different from the card grid views:

- **player_profile.html**: Single player spray chart in a standalone card. Has "Spray Chart" heading and BIP count. Add direction (L/C/R) and contact type (GB/LD/FB/PU/BU) stats below the chart image. Uses Tailwind CSS (not inline styles).
- **opponent_detail.html**: Team spray chart in a standalone full-width card. Per-player spray charts are "View spray" links in the batting table that open a modal popup. Add direction/contact stats below the team spray chart. Per-player modal images benefit from the global title removal and figsize change (E-194-01) but do not need card redesign.

Both templates extend `base.html` and use Tailwind classes (unlike the print/report templates which use inline CSS).

**Tailwind classes for direction/contact rows** (scaled up from print pt sizes for dashboard readability):

Direction row:
```html
<div class="text-sm font-semibold text-gray-700 mt-2">
  Left <span class="font-bold">7</span> &nbsp; Ctr <span class="font-bold">3</span> &nbsp; Right <span class="font-bold">5</span>
</div>
```
- `text-sm` (14px/~10.5pt) instead of print 8.5pt -- dashboard uses larger fonts
- `text-gray-700` = `#374151` -- matches TN-7 direction color

Contact row:
```html
<div class="text-xs text-gray-500 mt-1">
  6GB · 1LD · 4FB · 1PU · 2BU
</div>
```
- `text-xs` (12px/~9pt) instead of print 8pt -- secondary to direction
- `text-gray-500` = `#6b7280` -- matches TN-7 contact color

## Open Questions
- None (all design decisions validated during experiment session)

## History
- 2026-03-30: Created from experiment session findings (PM + UXD + SE)
- 2026-03-30: Scope expanded to include dashboard views (player_profile.html, opponent_detail.html) per user decision. Added E-194-04. Removed Non-Goal about dashboard views. Global chart title removal replaces per-view workaround.
- 2026-03-30: Set to READY after 6 review passes.
- 2026-03-30: Set to ACTIVE. Dispatch started.
- 2026-03-30: All 4 stories DONE. Epic COMPLETED. 12 implementation review findings (11 accepted, 1 dismissed). Documentation assessment: No documentation impact -- spray chart rendering and template changes. Context-layer assessment: No context-layer impact -- no new patterns (triggers: new agent patterns? no; new API endpoints? no; new architectural decisions? no; new rules/conventions? no; changed file organization? no; changed deployment/infra? no).

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-194-01 | 2 | 2 | 0 |
| Per-story CR -- E-194-02 | 3 | 3 | 0 |
| Per-story CR -- E-194-03 (R1+R2) | 2 | 2 | 0 |
| Per-story CR -- E-194-04 | 1 | 0 | 1 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 3 | 3 | 0 |
| **Total** | **12** | **11** | **1** |

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 8 | 0 |
| Internal iteration 1 -- Holistic team (PM + SE + UXD) | 11 | 7 | 4 |
| Codex iteration 1 | 5 | 4 | 1 |
| Codex iteration 2 | 2 | 1 | 1 |
| Internal iteration 2 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 2 -- Holistic team (PM + SE + UXD) | 8 | 6 | 2 |
| **Total** | **38** | **30** | **8** |

Key fixes across review iterations: TN-4 angle sign convention corrected (critical), shared helper extraction mandated in spray.py, TN-3 rewritten to mandate recompute, test file paths verified, E-194-03/04 dependency chain formalized, TN-12 Tailwind class specs added, E-194-04 data source claims corrected.
