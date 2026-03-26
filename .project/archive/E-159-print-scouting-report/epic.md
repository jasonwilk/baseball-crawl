# E-159: Print-Optimized Scouting Report View

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
The opponent scouting page (`/dashboard/opponents/{id}`) looks good on screen but prints poorly — Tailwind CDN doesn't render in print/PDF, wide tables clip, and nav/auth elements waste space. Coaches need clean, printable scouting reports for pre-game preparation. This epic adds a dedicated print route and template with self-contained CSS, landscape orientation, UXD-specified layout, and a spray chart placeholder section ready for future data wiring.

## Background & Context
Coaches frequently print or save scouting reports as PDFs to bring to the dugout. The current web view has interactive sort links, CDN-loaded Tailwind CSS (which doesn't work in print), dark nav headers, auth UI, and bottom navigation — all of which produce garbage when printed. A dedicated print endpoint and template solves this cleanly without compromising the interactive web view.

Expert consultation: UX designer consulted on print layout design — specified section order, typography scale, column trimming, page break strategy, and spray chart placeholder grid design. Baseball-coach consultation not required — the coaching-facing content decisions (pitchers-first ordering, context bar metrics, column trimming, handedness prominence, Batter Tendencies section) were specified directly by the user (who is the head coach and system operator) in the initial brief.

## Goals
- Coaches can print or save-as-PDF a clean, readable scouting report from the browser
- The print template is self-contained (no CDN dependencies) and optimized for landscape US Letter paper
- A "Batter Tendencies" spray chart placeholder section is structurally ready for E-158 data
- The existing interactive scouting report links to the print view

## Non-Goals
- Populating spray chart data (E-158 scope)
- Server-side PDF generation (browser print/save-as-PDF is sufficient)
- Modifying the existing interactive scouting report stats layout or section order (adding a print link is explicitly in scope)
- Adding print styles to other dashboard pages

## Success Criteria
- Opening `/dashboard/opponents/{id}/print` renders a print-optimized page with all scouting data
- Ctrl+P / browser print produces a clean landscape layout with no clipped tables (Page 1: header + pitching; Page 2+: batting + Batter Tendencies, which may span additional pages for large rosters)
- The existing scouting report page has a visible "Print / Save as PDF" link

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-159-01 | Print route and template | DONE | None | - |
| E-159-02 | Add print link to existing scouting report | DONE | E-159-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Route Design
New route: `GET /dashboard/opponents/{opponent_team_id}/print`

Same auth and data pipeline as the existing `opponent_detail` route — reuse `_fetch_opponent_detail_data`, `_compute_opponent_pitching_rates`, `_compute_team_batting`, `_sort_batting`, `_sort_pitching`. Use default sorts only (AVG desc for batting, ERA asc for pitching) — no interactive sort query params needed. Note: `_get_top_pitchers` is NOT used — the print view shows the full pitching table, not a top-3 card.

### TN-2: Page Layout (UXD Spec)

**Page 1:**
```
Report header     — Opponent name · record · "Scouting Report" · print date
Context bar       — Last meeting (date · score · W/L inline) + OBP / K% / BB% / SLG side by side
Pitching table    — Full table (pitchers first — pre-game primary concern)
```

**Page 2** (forced page break before batting section):
```
Batting table     — Full table
Batter Tendencies — Spray chart placeholder grid (3 cards per row)
```

**Cards removed**: The "Their Pitchers" summary card and "Team Batting summary" card from the screen view are NOT used. They are replaced by the compact single-row context bar. No card chrome.

**Context bar fallbacks**: If last meeting is null (first time seeing this opponent), show "No previous meetings". If `team_batting.has_data` is false, show dashes (`—`) for OBP/K%/BB%/SLG.

### TN-3: Typography (Self-Contained, No CDN)
- `font-family: Arial, Helvetica, sans-serif`
- Report title: 18pt bold
- Section headers: 11pt bold, uppercase, `letter-spacing`
- Table column headers: 8pt bold, uppercase
- Table data: 8.5pt
- Context bar: 9pt

### TN-4: Column Trimming

**Pitching table (10 columns)**: `#`, `Player`, `ERA`, `K/9`, `WHIP`, `GP`, `IP`, `BB`, `SO`, `Strike%`
- Dropped from screen view: `H`, `ER`, `#P`
- The Player cell includes pitcher handedness after the name: e.g., `Name (R)` — the `throws` field is available in the pitching query data. This is a critical in-game data point per UXD consultation.

**Batting table (12 columns)**: `#`, `Player`, `AVG`, `OBP`, `SLG`, `GP`, `AB`, `BB`, `SO`, `HR`, `SB`, `RBI`
- Dropped from screen view: `H`

**Inline GP subtext removed**: The screen view shows `"(X GP)"` inline in stat cells. The print view drops this — GP is its own column.

### TN-5: Spray Chart Placeholder Section
- Separate section below batting table titled "Batter Tendencies"
- Grid layout: 3 placeholder cards per row (landscape)
- Each card: player name + jersey number + 160×160px placeholder box with "Spray chart coming soon" centered, light border
- Row order matches batting table sort order
- NOT inline in batting table rows
- When E-158 spray chart data is available, the placeholder text will be replaced with actual spray chart visualizations

### TN-6: Print-Specific CSS
- `@page { size: landscape; margin: 0.5in; }` inside `@media print`
- `page-break-before: always` on the batting section
- `page-break-inside: avoid` on table rows
- Tables: `width: 100%` to prevent overflow — column trimming (TN-4) and font sizes (TN-3) ensure content fits at this width
- Table headers: dark text + thick bottom border (no dark background — saves ink)
- Zebra rows: `#f5f5f5` alternating
- White background throughout, black text
- No `overflow-x-auto` wrappers

### TN-7: Screen Elements (Hidden on Print)
- "Print / Save as PDF" button: `onclick="window.print()"`, hidden via `@media print`
- "View online" back-link beside print button, also hidden on print
- Document-end footer: opponent name (HTML `<div>`, prints on last page only — CSS `@page` margin boxes are not supported in Chromium)

## Open Questions
None.

## History
- 2026-03-26: Created
- 2026-03-26: Updated with UXD print layout spec (section order, typography, column trimming, spray chart grid, page breaks)
- 2026-03-26: Marked READY after 4 Codex iterations and 2 internal review rounds.
- 2026-03-26: COMPLETED. Delivered print-optimized scouting report route (`GET /dashboard/opponents/{id}/print`) with self-contained CSS, landscape layout, pitching-first page order, context bar, spray chart placeholder grid, and print link on the existing interactive scouting report. 2 stories, 11 new tests (49 total passing), 0 regressions.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 6 | 4 | 2 |
| Internal iteration 1 — Holistic team | 7 | 7 | 0 |
| Internal iteration 2 — CR spec audit | 4 | 3 | 1 |
| Internal iteration 2 — Holistic team | 4 | 4 | 0 |
| Codex iteration 1 | 6 | 5 | 1 |
| Codex iteration 2 | 3 | 3 | 0 |
| Codex iteration 3 | 3 | 3 | 0 |
| Codex iteration 4 | 4 | 4 | 0 |
| **Total** | **~37** | **~33** | **~4** |

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-159-01 | 0 | 0 | 0 |
| Per-story CR — E-159-02 | 0 | 0 | 0 |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 2 | 2 | 0 |
| **Total** | **2** | **2** | **0** |

### Documentation Assessment
Trigger 1 (new feature ships): **YES** — new print route and template for scouting reports. Affects `docs/coaching/` (scouting report documentation should mention the print view). Dispatch docs-writer before archiving.

### Context-Layer Assessment
1. **New convention, pattern, or constraint established?** No — the print template follows existing patterns (standalone route, Jinja2 template, inline CSS for self-containment).
2. **Architectural decision with ongoing implications?** No — self-contained print template is a local design choice, not an architectural pattern future epics must follow.
3. **Footgun, failure mode, or boundary discovered?** No — no new gotchas discovered.
4. **Change to agent behavior, routing, or coordination?** No — no agent changes.
5. **Domain knowledge discovered that should influence agent decisions?** No — the print layout spec is fully captured in the epic's Technical Notes and the template itself.
6. **New CLI command, workflow, or operational procedure introduced?** No — no new CLI commands or workflows.
