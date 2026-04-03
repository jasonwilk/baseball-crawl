# E-203: Fix FPS% Formula to Match GameChanger

## Status
`COMPLETED`

## Overview
Our FPS% calculation excludes HBP and Intentional Walk plate appearances from both the numerator and denominator, while GameChanger includes all plate appearances (`FPS / BF`). This causes our reports to show systematically higher FPS% than what coaches see in the GC app and CSV exports -- up to 20pp higher for pitchers with many HBP/IBB PAs. Aligning with GameChanger's formula eliminates coach confusion when cross-referencing our reports against the app.

## Background & Context
Verified by comparing CSV exports against our report output:
- **Freshman Grizzlies**: Caiden Strauss shows 70.0% (ours) vs 50.0% (GC) -- 20pp gap from 4 excluded PAs out of 14 BF.
- **Rebels 14U**: Average delta 0.90pp across 12 pitchers after formula correction.
- After formula fix, a residual ~0.5-1.5pp gap remains due to plays endpoint data limitations (plays data does not perfectly match boxscore BF counts). This residual gap is NOT fixable and is acceptable.

No expert consultation required -- this is a straightforward formula correction to match the authoritative source (GameChanger).

## Goals
- FPS% in standalone reports matches GameChanger's calculation method (`FPS / BF`)
- CLAUDE.md FPS% definition accurately reflects the implemented formula

## Non-Goals
- Changing the `is_first_pitch_strike` flag computation in the plays parser (parser is correct)
- Modifying the plays pipeline, reconciliation engine, or dashboard queries
- Eliminating the residual ~0.5-1.5pp gap from plays endpoint data limitations
- Adding FPS% to the dashboard (separate future work)

## Success Criteria
- Standalone report FPS% values use `FPS / BF` (total batters faced as denominator, no exclusions)
- Existing tests updated to assert the new formula; no regressions in full test suite
- CLAUDE.md FPS% definition updated to remove query-time exclusion language

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-203-01 | Fix FPS% SQL queries in report generator | DONE | None | SE |
| E-203-02 | Update CLAUDE.md FPS% definition | DONE | E-203-01 | CA |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Formula Change
- **Before**: Excluded HBP and Intentional Walk from both numerator and denominator via `CASE WHEN p.outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` on both `fps_sum` and `fps_denom` columns
- **After**: `FPS / BF` -- total batters faced as denominator, no exclusions (matches GameChanger)

### Affected Queries (src/reports/generator.py only)
Two queries use the old exclusion pattern:

1. **`_query_plays_pitching_stats()`** (~line 665-682): Per-pitcher FPS%. The `CASE WHEN outcome NOT IN (...)` filtering on both `fps_sum` and `fps_denom` columns must be simplified to `SUM(p.is_first_pitch_strike)` and `COUNT(*)` respectively.

2. **`_query_plays_team_stats()`** (~line 769-786): Team-level FPS%. Same `CASE WHEN` exclusion pattern must be simplified identically.

### Test Updates (tests/test_report_plays.py)
These tests assert the old exclusion behavior and must be updated:
- `TestQueryPlaysPitchingStats.test_fps_excludes_hbp_and_ibb` (~line 167): Currently asserts HBP/IBB excluded from per-pitcher denominator. Must assert they are included (FPS / total BF).
- `TestTeamFpsExclusion.test_team_fps_excludes_hbp_and_ibb` (~line 503): Currently asserts HBP/IBB excluded from team denominator. Must assert they are included.

Tests that don't use HBP/IBB fixtures (e.g., `test_basic_fps_and_pitches_per_bf`) should pass without changes since `COUNT(*)` equals the old filtered count when no HBP/IBB rows exist.

### CLAUDE.md Update
Line 66 contains: `exclusions (HBP, Intentional Walk) applied at query time only (WHERE outcome NOT IN (...))`. This must be updated to state that FPS% uses total BF as denominator with no query-time exclusions, matching GameChanger's formula.

## Open Questions
None -- formula is verified against GC CSV exports.

## History
- 2026-04-03: Created
- 2026-04-03: READY after 3 review passes (8 findings, 7 accepted, 1 dismissed)
- 2026-04-03: COMPLETED. 2 stories delivered (SE: FPS% SQL query fix, CA: CLAUDE.md definition update). FPS% now uses `FPS / BF` with no exclusions, matching GameChanger.

### Spec Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 2 | 2 | 0 |
| Internal iteration 1 -- PM holistic | 2 | 1 | 1 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **8** | **7** | **1** |

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-203-01 | 1 | 0 | 1 |
| Per-story CR -- E-203-02 | 0 | 0 | 0 |
| CR integration review | 4 | 3 | 1 |
| Codex code review | TBD | TBD | TBD |
| **Total** | **5+** | **3+** | **2+** |

### Documentation Assessment
Documentation impact: stale FPS% formula references in `docs/admin/operations.md:637` and `docs/admin/architecture.md:119` need updating. Dispatch docs-writer before archiving.

### Context-Layer Assessment
| Trigger | Verdict | Notes |
|---------|---------|-------|
| T1: New convention or workflow | NO | Formula change, not a new convention |
| T2: Footgun or failure mode | NO | Old footgun (exclusion mismatch) eliminated by the fix |
| T3: Architectural decision | NO | No new architecture; query simplification only |
| T4: Domain knowledge | NO | FPS% formula already codified in CLAUDE.md by E-203-02 |
| T5: Agent ecosystem change | NO | No agent changes |
| T6: External integration | NO | No new external integrations |

No context-layer dispatch needed.
