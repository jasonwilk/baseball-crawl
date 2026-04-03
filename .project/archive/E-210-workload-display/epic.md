# E-210: Pitching Workload Display Redesign

## Status
`COMPLETED`

## Overview
Redesign the P(7d) pitching workload column across all display surfaces to replace the confusing `72/1d` (pitches/span-days) format with `72p (1g)` (pitches + appearances count). Coaches misread the `/1d` suffix as "1 day rest," which contradicts the separate Rest column. The new format eliminates ambiguity in the dugout.

## Background & Context
The `get_pitching_workload()` query in `src/api/db.py` already computes `appearances_7d` (COUNT of games in the 7-day window) but drops it from the final SELECT -- only `span_days_7d` (days spanned between first and last appearance) is returned. The span-days metric is not coaching-useful and causes confusion.

Baseball-coach consultation confirmed: keep Rest as a separate column, change P(7d) format to show pitches with game-count context, use `g` suffix (not `o` -- could be misread as "outs"). UXD consultation confirmed: `72p (1g)` format, `?p (1g)` for unknown pitch counts, `—` for no data, column header `Pitches (7d)`.

No expert consultation required beyond what was already completed in discovery. The changes are purely display-layer (query column exposure + string formatting + template headers).

## Goals
- Eliminate the `/Nd` span-days format that coaches misread as rest days
- Surface game appearances (`Ng`) instead of span days across all pitching workload displays
- Maintain parity between dashboard and standalone reports (per CLAUDE.md shared-query requirement)

## Non-Goals
- Workload threshold flags (pitch-count warning indicators) -- coach suggestion for future
- Changes to the Rest column format or behavior
- Changes to the 7-day window logic or workload query structure
- Changes to the `span_days_7d` computation (it remains in the query but is no longer displayed)

## Success Criteria
- All pitching workload displays (dashboard opponent detail, dashboard print view, standalone report web, standalone report print) show the new `Np (Ng)` format
- Column headers read `Pitches (7d)` on all surfaces
- Existing tests updated and passing; no regressions

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-210-01 | Expose appearances_7d and update workload format across all surfaces | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### Format Specification
| State | Old Format | New Format |
|-------|-----------|------------|
| Normal (pitches known, appearances > 0) | `72/1d` | `72p (1g)` |
| Unknown pitch count (appearances > 0) | `?/1d` | `?p (1g)` |
| No 7-day data (no appearances) | `—` | `—` |
| Zero pitches recorded | `—` | `0p (1g)` (previously showed em-dash; now shows zero explicitly since the pitcher did appear) |

**Zero pitches edge case**: The current code treats `pitches_7d == 0` as no-data (em-dash). With the new format, `pitches_7d == 0` means "pitched but zero pitches recorded" -- this should display `0p (Ng)` rather than suppressing to em-dash. The appearances count provides context that the pitcher was active.

**Suffix rationale**: `g` = games (not `o` = outings, which could be misread as "outs" in dugout shorthand).

### Formatting Branch Order (Critical)
The current `pitches_7d` column has a dual meaning for the value `0`: (a) no appearances in the 7-day window (the CASE branch returns 0 when `sd.appearances_7d IS NULL`), and (b) genuinely zero pitches recorded across real appearances (SUM = 0 with non-NULL pitch counts). The current formatting code branches on `pitches_7d` first, which works only because both cases map to em-dash.

With the new format, these cases diverge: no-appearances = em-dash, zero-pitches = `0p (Ng)`. **The formatting logic MUST branch on `appearances_7d` first**:

1. `appearances_7d` is NULL → `—` (no 7-day data, regardless of `pitches_7d`)
2. `pitches_7d` is NULL → `?p (Ng)` (appeared but pitch counts unknown)
3. Otherwise → `{pitches_7d}p ({appearances_7d}g)` (includes the `pitches_7d == 0` case)

This branch order applies to both `renderer.py` (`_compute_workload_enrichments`) and `dashboard.py` (`_merge_workload_into_pitchers`). Do NOT replicate the current code's `pitches_7d`-first branching pattern.

### Column Header
All surfaces rename from `P (7d)` to `Pitches (7d)`.

### Query Change
`src/api/db.py` `get_pitching_workload()`: Add `sd.appearances_7d` to the final SELECT (line ~290) and add `"appearances_7d"` to the result dict (line ~307). The CTE already computes it. When `sd` is NULL (no 7-day data), `appearances_7d` will be NULL via the LEFT JOIN -- consumers treat NULL as no-data.

### Workload Subline
The key-player workload subline in both renderer.py and dashboard.py currently includes the old P(7d) format after the dot-separator. It should use the new format. No structural change needed -- the subline already references the computed `_p7d_display` / `p7d_display` value.

### JS Interaction (Standalone Reports)
The standalone report's JavaScript (`scouting_report.html`, lines ~659-661) parses the workload subline by splitting on the dot-separator to upgrade the Rest portion to relative days. The P(7d) portion (after the dot) is passed through unchanged. Since the new format is still plain text with no HTML, the JS split-and-reassemble pattern continues to work without modification.

### Files Affected
- `src/api/db.py` -- `get_pitching_workload()` query and result dict
- `src/reports/renderer.py` -- `_compute_workload_enrichments()` P(7d) formatting
- `src/api/routes/dashboard.py` -- `_merge_workload_into_pitchers()` P(7d) formatting
- `src/api/templates/reports/scouting_report.html` -- pitching table `<th>` header
- `src/api/templates/dashboard/opponent_detail.html` -- pitching table `<th>` header
- `src/api/templates/dashboard/opponent_print.html` -- pitching table `<th>` header
- `tests/test_pitching_workload.py` -- query result assertions
- `tests/test_report_workload.py` -- renderer format assertions
- `tests/test_dashboard_workload.py` -- dashboard format assertions

## Open Questions
- None

## History
- 2026-04-03: Created. Discovery complete (baseball-coach + UXD consulted). Single-story epic -- all changes are tightly coupled through the shared query function.
- 2026-04-03: Reverted to DRAFT. Internal spec review in progress (UXD, SE, DE, PM).
- 2026-04-03: Spec review triage complete. 1 finding accepted (DE-3/SE-2-3: explicit formatting branch order on appearances_7d). 2 dismissed (UXD-1 advisory, SE-1 already covered by AC-7). Added "Formatting Branch Order" TN section.
- 2026-04-03: Set to READY. Internal spec review scorecard:

  | Review Pass | Findings | Accepted | Dismissed |
  |---|---|---|---|
  | Internal -- UXD | 1 | 0 | 1 |
  | Internal -- SE | 3 | 1 | 2 |
  | Internal -- DE | 2 | 1 | 1 |
  | **Total** | **6** | **2** | **4** |

- 2026-04-03: COMPLETED. 1 story delivered (E-210-01). All 7 ACs verified. P(7d) format changed from `N/Nd` to `Np (Ng)` across all surfaces (dashboard detail, dashboard print, standalone report). Column headers renamed to `Pitches (7d)`. `appearances_7d` exposed from shared query. CR finding addressed (zero-pitches test coverage added).
