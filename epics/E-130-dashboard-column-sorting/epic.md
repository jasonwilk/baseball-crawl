# E-130: Dashboard Column Sorting

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add sortable column headers to the team batting/pitching stats tables and opponent scouting report tables so coaches can sort by any stat column (AVG, OBP, ERA, K/9, etc.) to quickly identify top performers and weak spots. Sorting uses server-side query parameters -- no JavaScript required.

## Background & Context
The dashboard stats tables currently display data in a fixed sort order: batting sorted by AVG descending, pitching sorted by ERA ascending. Coaches need to sort by different columns depending on the game-prep question they're answering (e.g., "who has the most strikeouts?" or "who has the highest OBP?"). There is no way to re-sort without modifying the source code.

**Expert consultation findings** (2026-03-19):
- **UXD**: Recommends server-side sorting via `?sort=avg&dir=desc` query params. Column headers become `<a>` links. Active sort column shows `▲`/`▼` Unicode indicator. Toggle direction on click. No JS needed -- pure server-rendered HTML. Fits the project's zero-JS dashboard stack. Sort URLs are bookmarkable and shareable.
- **SE**: Confirms tables are simple Jinja2 `{% for %}` loops with `<thead>`/`<tbody>`. Rate stats (AVG, OBP, SLG) are computed in Jinja2 templates; pitching rates (ERA, K/9, BB/9, WHIP) are computed in Python by `_compute_pitching_rates()`. For server-side sorting, the sort key computation can use raw column values (e.g., `h/ab` for AVG) without changing template rendering. No DB query changes needed -- sorting happens in the route handler after data fetch.
- **DE**: No consultation required. Sorting happens in Python after the existing queries return results. No schema or query changes needed.

No expert consultation required for baseball-coach -- sorting is a pure UI/UX capability, not a data or coaching domain question.

## Goals
- Coaches can click any column header on the batting stats table to sort by that column
- Coaches can click any column header on the pitching stats table to sort by that column
- Coaches can sort opponent scouting report batting and pitching tables the same way
- Sort direction toggles on repeated clicks (ascending/descending)
- Active sort column and direction are visually indicated

## Non-Goals
- Sorting on game detail box score tables -- per-game data is positional, not typically sorted
- Sorting on opponent list table -- low row count, low sorting value
- Sorting on player profile career table -- typically 1-3 rows
- Client-side JavaScript sorting -- server-side is simpler and fits the existing stack
- Multi-column sorting (sort by two columns simultaneously)

## Success Criteria
- Clicking a column header on the batting or pitching stats table reloads the page sorted by that column
- Clicking a column header on the opponent scouting report batting or pitching table sorts that table
- Clicking the same header again reverses the sort direction
- The active sort column shows a `▲` or `▼` indicator
- Default sort (no params) remains AVG descending for batting and ERA ascending for pitching
- Sort URLs are bookmarkable (e.g., `/dashboard?team_id=1&sort=obp&dir=desc`)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-130-01 | Sortable batting and pitching stats tables | TODO | None | - |
| E-130-02 | Sortable opponent scouting report tables | TODO | E-130-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Server-Side Sort via Query Parameters

The route handlers (`team_stats()`, `team_pitching()`, and `opponent_detail()`) accept two new optional query parameters:
- `sort`: column key (e.g., `avg`, `obp`, `era`, `k9`, `name`)
- `dir`: `asc` or `desc`

If `sort` is not provided or is not a recognized column key, use the current default sort (AVG DESC for batting, ERA ASC for pitching). If `dir` is not provided, use the default direction for that column.

### TN-2: Sort Key Computation for Rate Stats

Rate stats are not stored in the database -- they are computed from raw counting stats. The sort key must use the same formula without changing how templates render the formatted values.

**Batting rate stats** (currently computed in Jinja2 via `format_avg` filter):
- AVG: `h / ab` (0 if `ab == 0`)
- OBP: `(h + bb + hbp) / (ab + bb + hbp + shf)` (0 if denominator is 0)
- SLG: `(h + doubles + 2*triples + 3*hr) / ab` (0 if `ab == 0`)

**Pitching rate stats** (currently computed in Python by `_compute_pitching_rates()`):
- ERA: `(er * 27) / ip_outs` (infinity if `ip_outs == 0`, sorts to bottom)
- K/9: `(so * 27) / ip_outs`
- BB/9: `(bb * 27) / ip_outs`
- WHIP: `(bb + h) * 3 / ip_outs`

Players/pitchers with zero denominators (0 AB for batting, 0 IP for pitching) should sort to the bottom regardless of sort direction, matching the current SQL behavior.

### TN-3: Column Key Mapping

Each sortable column needs a stable key used in the `sort` query parameter. These keys appear in URLs and must not change once shipped.

**Batting columns**: `name`, `avg`, `obp`, `gp`, `bb`, `so`, `slg`, `h`, `ab`, `2b`, `3b`, `hr`, `sb`, `rbi`

**Pitching columns**: `name`, `era`, `k9`, `bb9`, `whip`, `gp`, `ip`, `h`, `er`, `bb`, `so`, `hr`

**Opponent batting columns** (subset of team batting): `name`, `avg`, `obp`, `gp`, `ab`, `bb`, `so`, `slg`, `h`, `hr`, `sb`, `rbi`

**Opponent pitching columns** (subset of team pitching): `name`, `era`, `k9`, `whip`, `gp`, `ip`, `h`, `er`, `bb`, `so`

### TN-4: Default Sort Directions

When a column is clicked for the first time (no current sort on that column), use a sensible default direction:
- **Descending by default** (higher is better): AVG, OBP, SLG, H, HR, RBI, SB, BB (batting), K/9, SO, IP, GP
- **Ascending by default** (lower is better): SO (batting), ERA, BB/9, WHIP, ER, BB (pitching), HR (pitching)

When the column is already the active sort, toggle the direction.

### TN-5: Sort Param Preservation in Navigation

Sort params are **page-specific** -- batting sort params do not carry to the pitching page or opponent detail and vice versa. Bottom nav links should only carry `team_id` and `season_id` (not sort params).

Sort params should be preserved within a page's own links: team selector on the same page and the active sort column header toggle link. On the opponent detail page, the `sort` and `dir` params apply to that page's URL and are independent of the team batting/pitching sort state.

### TN-7: Opponent Detail Sort Context

The opponent detail page (`/dashboard/opponents/{opponent_team_id}`) has TWO tables (batting leaders and pitching leaders) on a single page. Both tables need independent sort controls.

Approach: use separate query param namespaces -- e.g., `bat_sort`, `bat_dir` for the batting table and `pit_sort`, `pit_dir` for the pitching table. This allows both tables to be sorted independently on the same page load. Alternatively, use a single `sort`/`dir` pair that applies to the table identified by a `table` param (e.g., `?table=batting&sort=avg&dir=desc`). The implementing agent should choose the simpler approach.

### TN-6: Template Header Pattern

Column headers change from static `<th>` to `<th>` containing an `<a>` link. The link includes the current `team_id`, `season_id`, `sort`, and `dir` params with the direction toggled if this column is already the active sort.

The active sort column's header shows a Unicode indicator: `▲` for ascending, `▼` for descending.

## Open Questions
- None remaining.

## History
- 2026-03-19: Created. Scoped to team batting and pitching tables only. Season navigation and tab context persistence identified as fully covered by E-127-11/12 (not duplicated here). UXD, SE consulted. Server-side sorting chosen over client-side JS per UXD recommendation.
- 2026-03-19: Expanded scope to include opponent scouting report tables (E-130-02) per UXD recommendation -- opponent sorting is the core coaching use case for pre-game prep. E-130-02 depends on E-130-01 (reuses sort pattern). Added TN-7 for opponent detail dual-table sort context.
