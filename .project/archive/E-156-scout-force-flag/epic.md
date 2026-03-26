# E-156: Add --force Flag to bb data scout

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Add a `--force` flag to `bb data scout` that bypasses the 24-hour freshness check in the all-opponents path, allowing the operator to re-scout every opponent regardless of when they were last scouted. Single-team mode (`--team`) already bypasses freshness, but the all-opponents path has no override -- the operator must wait 24 hours or manually clear `scouting_runs` rows.

## Background & Context
`bb data scout` (all-teams mode) calls `ScoutingCrawler.scout_all()`, which checks `_is_scouted_recently()` per opponent and skips any scouted within the `freshness_hours` threshold (default 24h). The `ScoutingCrawler` constructor already accepts a `freshness_hours` parameter, but the CLI does not expose it. Single-team mode (`--team`) already bypasses freshness because it calls `scout_team()` directly. The operator hit this limitation and had to wait or manually clear database rows to re-scout.

No expert consultation required -- this is a pure CLI pass-through to an existing constructor parameter.

## Goals
- Operator can force re-scouting of all opponents without waiting or manual DB manipulation
- The existing freshness check remains the default behavior (no behavioral change without `--force`)

## Non-Goals
- Changing the default freshness threshold (stays at 24h)
- Adding a configurable `--freshness-hours` option (can be added later if needed)
- Modifying the `--team` path (already bypasses freshness)

## Success Criteria
- `bb data scout --force` re-scouts all opponents regardless of `scouting_runs` timestamps
- `bb data scout` (without `--force`) continues to skip recently-scouted opponents as before
- `bb data scout --force --dry-run` reports the force mode in its output
- The `--force` flag appears in `bb data scout --help`

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-156-01 | Add --force flag to scout CLI command | DONE | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Implementation Path
The `ScoutingCrawler` already accepts `freshness_hours: int = 24` in its constructor. Setting `freshness_hours=0` causes `_is_scouted_recently()` to return `False` for all opponents (since `age_hours < 0` is always false). The CLI change is:

1. Add a `--force` Typer boolean option to the `scout` command
2. Pass `freshness_hours=0` to `ScoutingCrawler(client, conn, freshness_hours=0)` when `--force` is True
3. Update `_scout_dry_run()` to report force mode

### Files Affected
- `src/cli/data.py` -- add `--force` option, thread through to helper functions
- `tests/test_cli_scout.py` -- add tests for `--force`: dry-run output, live-path `freshness_hours` pass-through (follows established pattern)

## Open Questions
None.

## Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 2 | 2 | 0 |
| Internal iteration 1 — PM self-review | 0 | 0 | 0 |
| Codex iteration 1 | 4 | 4 | 0 |
| Codex iteration 2 | 2 | 2 | 0 |
| **Total** | **8** | **8** | **0** |

## History
- 2026-03-25: Created
- 2026-03-25: READY after 2 review iterations (8 findings, 8 accepted, 0 dismissed)
- 2026-03-26: COMPLETED. Added `--force` flag to `bb data scout` that bypasses the 24-hour freshness check by passing `freshness_hours=0` to `ScoutingCrawler`. Dry-run output reports force mode. Default behavior (no `--force`) unchanged. 3 new tests added (17 total, 0 failures).

### Implementation Review Scorecard

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR — E-156-01 | 2 | 1 | 0 (round 1 scope gap, round 2 clean) |
| CR integration review | 0 | 0 | 0 |
| Codex code review | 3 | 2 | 1 |
| **Total** | **5** | **3** | **1** |

Codex dismissed: story status "DONE" (false positive — correct per dispatch workflow). Codex finding 1: devcontainer (confirmed no change in worktree — no fix needed). Codex finding 2: misleading dry-run message (fixed with conditional output).

### Context-Layer Assessment (2026-03-26)

1. New convention, pattern, or constraint? **No**
2. Architectural decision with ongoing implications? **No**
3. Footgun, failure mode, or boundary discovered? **No**
4. Change to agent behavior, routing, or coordination? **No**
5. Domain knowledge discovered? **No**
6. New CLI command, workflow, or operational procedure? **No** — `--force` is a minor flag addition to an existing command, not a new workflow

All 6 triggers: No. No context-layer codification required.
