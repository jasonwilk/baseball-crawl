# E-187: Threshold Calibration for Youth/HS Seasons

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Calibrate all display thresholds in the scouting report renderer and fix two E-186 post-review findings (search pagination, integration test gaps). The current thresholds (20 PA batting, 15 IP pitching) are calibrated for professional seasons (162 games) and suppress nearly all heat-map coloring for opponents with fewer than ~7 games of data. Youth seasons may be 25 games; HS varsity ~30. The system must show whatever data exists at pragmatically reasonable minimums and improve as depth grows.

## Background & Context
After E-186 delivered standalone scouting reports with spray charts, a report generated for Millard South (5 games, 18 batters) showed almost no heat-map coloring because only 2 batters reached 10+ AB. The user's feedback: "Youth seasons might only be 25 games. We have to start at the minimum reasonable level and just get better as the data gets deeper."

Separately, the E-186 Codex post-dispatch review identified two findings: (1) `_resolve_gc_uuid` doesn't paginate POST /search results (25 per page; common team names may require page 2+), and (2) no integration test covers the full resolution → persist → pass-to-crawler branch.

The user also wants the coaching-season-length philosophy baked into the context layer so every agent building thresholds thinks "25-game season" by default.

## Goals
- Lower display thresholds to pragmatically reasonable minimums for youth/HS season lengths
- Fix the search pagination bug in `_resolve_gc_uuid`
- Add missing integration and pagination tests for the generator
- Codify the season-length calibration principle in the context layer

## Non-Goals
- Adding threshold logic to the dashboard opponent detail pages (dashboard shows raw data -- keep it simple)
- Making thresholds user-configurable at runtime
- Changing the heat-map algorithm itself (percentile-based ranking still works fine)
- Adding graduated confidence tiers (binary small-sample flag at a lower threshold is sufficient for now)

## Success Criteria
1. A scouting report for an opponent with 5 games shows heat-map coloring for batters with >= 5 PA and pitchers with >= 6 IP
2. `_resolve_gc_uuid` paginates through POST /search results up to 5 pages
3. Integration tests cover the gc_uuid resolution → persist → spray-crawler wiring
4. A context-layer rule ensures future agents default to youth/HS season-appropriate thresholds

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-187-01 | Fix search pagination and add integration tests | TODO | None | - |
| E-187-02 | Lower display thresholds for youth/HS seasons | TODO | None | - |
| E-187-03 | Codify season-length calibration in context layer | TODO | None | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### TN-1: Revised Threshold Values

All thresholds live in `src/reports/renderer.py` as module-level constants. The revised values:

| Constant | Current | Revised | Rationale |
|----------|---------|---------|-----------|
| `_MIN_PA_BATTING` | 20 | 5 | ~2 games of PA for a starter (3 PA/game). Shows heat after 2nd game. |
| `_MIN_IP_OUTS_PITCHING` | 45 (15 IP) | 18 (6 IP) | ~2 starts for a HS pitcher (3 IP/start). Shows heat after 2nd outing. |
| `_MIN_BIP_SPRAY` | 3 | 3 | Already appropriate. 3 BIP is the user's stated minimum. |
| `_MIN_BIP_TEAM_SPRAY` | 20 | 20 | Already appropriate. Unchanged. |
| `_KEY_PITCHER_MIN_OUTS` | 45 (15 IP) | 18 (6 IP) | Matches pitching small-sample threshold. |
| `_KEY_BATTER_MIN_PA` | 20 | 5 | Matches batting small-sample threshold. |

The key-player callout thresholds should match the small-sample thresholds. The heat-map algorithm (percentile ranking within qualified players) works correctly regardless of threshold level because it's relative, not absolute.

The code uses strict less-than comparison (`pa < _MIN_PA_BATTING`). A player with exactly 5 PA or 18 ip_outs is considered qualified (not small-sample).

### TN-2: Small-Sample Footnote Text Updates

The template (`src/api/templates/reports/scouting_report.html`) has hardcoded footnote text:
- "* Small sample size (fewer than 20 PA)" → "* Small sample size (fewer than 5 PA)"
- "* Small sample size (fewer than 15 IP)" → "* Small sample size (fewer than 6 IP)"

### TN-3: Search Pagination Protocol

`_resolve_gc_uuid` in `src/reports/generator.py` must paginate POST /search:
- Start at page 0. If the page returns exactly 25 hits and no match found, increment page and retry.
- Cap at 5 pages (125 results). If no match after 5 pages, return None.
- Return immediately when a matching `public_id` is found.
- The `start_at_page` parameter already exists in the API call -- just needs a loop.
- Per `.claude/rules/gc-uuid-bridge.md:45`: "Paginate if needed."

### TN-4: Integration Test Coverage

Two test gaps to fill in `tests/test_report_generator.py`:
1. **Resolution wiring test**: Seed a team with `gc_uuid=NULL`, mock POST /search to return a match, verify: (a) gc_uuid is stored in the teams table, (b) the resolved gc_uuid is passed to `_crawl_and_load_spray`.
2. **Pagination test**: Mock page 0 with 25 non-matching hits, page 1 with a matching hit. Verify `_resolve_gc_uuid` returns the correct gc_uuid and called POST /search twice.

### TN-5: Context Layer Files

The context-layer story creates:
- New rule: `.claude/rules/season-length-calibration.md` -- scoped to display surfaces (`src/reports/**`, `src/api/templates/**`, `src/charts/**`, `src/api/routes/dashboard.py`)
- Update: `.claude/agents/baseball-coach.md` -- add season-length context to the Identity section
- Update: CLAUDE.md Data Model section -- fix stale "10 BIP minimum" reference to reflect actual thresholds (3 BIP per player, 20 BIP team)

### TN-6: Test Updates

At minimum 12 tests in `tests/test_report_renderer.py` require updates. The implementing agent must grep for `_MIN_PA_BATTING`, `_MIN_IP_OUTS_PITCHING`, `< 45`, `< 20`, `fewer than 15`, and `fewer than 20` to find all occurrences. Categories of affected tests:

- **Batting threshold tests**: Tests that use PA values between 5 and 19 as "small sample" data (e.g., PA=12, PA=14, PA=19). These are no longer below threshold. Adjust test data to use PA < 5.
- **Pitching threshold tests**: Tests that use `ip_outs` values between 18 and 44 as "small sample" or "not qualified" data (e.g., `ip_outs=30`). These are no longer below threshold. Adjust test data to use `ip_outs < 18`.
- **Inline `_small_sample` assignments**: 8 pitching heat/key-player tests (lines 697-801) manually set `_small_sample` with `< 45` instead of using the constant. Update to `< 18` for consistency.
- **Footnote text assertions**: Tests checking for "fewer than 15 IP" or "fewer than 20 PA" text. Update to "fewer than 6 IP" and "fewer than 5 PA".

## Open Questions
- None -- all workstreams are well-scoped.

## History
- 2026-03-29: Created. Combines E-186 post-review fixes, threshold calibration, and context-layer codification.
- 2026-03-29: Set to READY after internal review (11 findings: 4 accepted, 7 dismissed). Codex skipped.

### Review Scorecard (Planning)
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 5 | 1 | 4 |
| Internal iteration 1 -- Holistic team (PM) | 6 | 3 | 3 |
| **Total** | **11** | **4** | **7** |
