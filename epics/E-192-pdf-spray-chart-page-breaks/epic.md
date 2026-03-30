# E-192: Fix Spray Chart PDF Page Breaks

## Status
`READY`

## Overview
Spray charts in scouting reports break across pages when printing to PDF via the browser print dialog. Charts split mid-image because Chrome's print engine ignores `page-break-inside: avoid` inside CSS Grid containers. This epic switches both affected templates to flexbox layout with a 4-column grid so that 8+ spray charts fit per printed page without splitting.

## Background & Context
The user confirmed the problem with two real reports (York Varsity Dukes and Lincoln North Star Reserve 26'). Both scouting report templates use CSS Grid for spray chart layout. Chrome's print engine has a well-known limitation: it poorly handles fragmentation hints (`break-inside: avoid`, `page-break-inside: avoid`) on items inside CSS Grid containers, routinely splitting content mid-element across page boundaries.

Two templates are affected:

1. **`opponent_print.html`** (dashboard opponent flow) -- uses `.tendencies-grid` with `display: grid; grid-template-columns: repeat(3, 1fr)`. Spray charts are loaded via live `<img>` URLs from the dashboard chart endpoints. Note: `.tendency-card` currently has `break-inside: avoid` but lacks `page-break-inside: avoid`.

2. **`scouting_report.html`** (standalone reports flow) -- uses `.spray-grid` with `display: grid; grid-template-columns: repeat(2, 1fr)`. Spray charts are embedded as base64 data URIs rendered by `_encode_spray_chart()` in `renderer.py`. Note: `.spray-card` already has both `break-inside: avoid` and `page-break-inside: avoid`.

Same root cause, same fix pattern, different CSS class names and data sources.

**UXD consultation** (2026-03-30): Recommended 4-column flexbox layout for print. CSS-only approach -- no renderer changes required. `width: 100%` on chart images scales them to card width automatically. 4 columns fits 8-12 charts per landscape page; 3 columns wastes space, 5 columns too small for readability.

## Goals
- Spray charts do not split across page boundaries when printing scouting reports to PDF
- 8+ spray charts fit per printed landscape page at a readable size
- Screen layout remains unchanged (print-only CSS overrides)

## Non-Goals
- Server-side PDF generation (out of scope -- browser print is the mechanism)
- Changing chart rendering quality or matplotlib parameters (CSS scaling handles sizing)
- Modifying spray chart data or thresholds
- Changing the dashboard (non-print) spray chart views

## Success Criteria
- Printing either scouting report template to PDF produces spray chart pages where no chart image is split across a page boundary
- At least 8 individual spray charts fit per landscape page
- Screen rendering of both templates is visually unchanged

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-192-01 | Fix spray chart print layout in both templates | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Two Templates, One Fix Pattern

Both templates need the same logical change: replace CSS Grid with flexbox in the print context. The class names differ:

| Template | Grid class | Card class | Card name class |
|----------|-----------|------------|-----------------|
| `opponent_print.html` | `.tendencies-grid` | `.tendency-card` | `.tendency-card-name` |
| `scouting_report.html` | `.spray-grid` | `.spray-card` | `.spray-card-name` |

### TN-2: Flexbox Layout Specification (from UXD consultation)

**Print layout** (inside `@media print`):

The spray chart grid switches from CSS Grid to flexbox for print only. Each card gets `width: calc(25% - 5px)` for a 4-column layout with 6px gap. Card selectors must include both fragmentation properties for cross-browser compatibility:

```
break-inside: avoid;
page-break-inside: avoid;
```

These properties on flex items are respected by Chrome's print engine (unlike grid items).

**Screen layout**: Keep existing CSS Grid unchanged. The flexbox override applies only inside `@media print`.

### TN-3: Page Geometry

Landscape, 0.5in margins: ~9.5" usable width, ~6.5" usable height.

With 4 columns at 6px gap: each card ~2.25" wide. At the chart's ~2:3 aspect ratio, each card is ~1.75" tall (image + name). This fits 3 rows x 4 columns = 12 charts per page, conservatively 8+ with spacing.

### TN-4: Card Design Adjustments for Print

In the `@media print` context, apply to both `.tendency-card` and `.spray-card`:
- Card padding: `4px` (from current `6px`)
- Card gap: `6px` (from current `8px`)

Player name selectors (`.tendency-card-name` and `.spray-card-name`):
- Keep current font size
- Single line: `overflow: hidden; text-overflow: ellipsis; white-space: nowrap`

Chart image: `width: 100%; display: block` (scales to card width automatically).

Stats line (`scouting_report.html` only, `.spray-card-stats`): `display: none` in print to save vertical space.

### TN-5: Page Break Strategy

**Existing fragmentation properties:**
- `scouting_report.html`: `.spray-card` already has both `break-inside: avoid` and `page-break-inside: avoid` in base CSS. The print override reinforces these.
- `opponent_print.html`: `.tendency-card` has only `break-inside: avoid` in base CSS. The print override must add `page-break-inside: avoid`.

**Page-level breaks:**
- `opponent_print.html`: `page-break-before: always` on `.tendencies-section` -- keep (spray charts start on a fresh page).
- `scouting_report.html`: `page-break-before: always` on `.spray-section` -- keep (same rationale).

If a card doesn't fit at the bottom of a page, it flows to the next page naturally.

### TN-6: Team Spray Chart (scouting_report.html only)

The standalone report has a full-width team spray chart above individual charts (`.spray-team-chart`). This element is not part of the flex grid and receives no print-specific CSS rules. Its existing screen-context styling (`max-width: 100%`, centered via `margin: 0 auto`) carries through to print unchanged.

## Open Questions
None.

## History
- 2026-03-30: Created. UXD consultation completed (4-column flexbox recommendation).
- 2026-03-30: Iteration 1 review. 9 findings accepted (CR-1 through CR-8, PM-1, PM-3), 3 dismissed (PM-2, UXD-4, UXD-5). ACs reframed for implementer verifiability; fragmentation properties specified per-template; TN-4/TN-5 updated with selector mappings.
- 2026-03-30: Codex iteration 1. 2 findings accepted (AC-6 ambiguity, AC-7 font-size gap), 1 dismissed (DoD manual print step -- unverifiable in devcontainer). AC-6/TN-6 reframed as no-touch rule; AC-7 adds font-size preservation.
- 2026-03-30: Set to READY.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 8 | 8 | 0 |
| Internal iteration 1 -- Holistic team (PM + UXD) | 5 | 2 | 3 |
| Codex iteration 1 | 3 | 2 | 1 |
| **Total** | **16** | **12** | **4** |

Note: SE findings were not received by PM despite re-send, so they are not counted. PM-1 and PM-3 were subsumed by CR findings (counted under CR).
