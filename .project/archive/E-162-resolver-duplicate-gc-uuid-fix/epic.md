# E-162: Fix OpponentResolver Duplicate Team Creation

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Fix the bug where `OpponentResolver._ensure_opponent_team_row` creates a duplicate team row when a stub team already owns the target `public_id`. Instead of creating a new row with the `gc_uuid` and hitting a UNIQUE collision on `public_id`, the resolver should find the existing `public_id` stub and merge the `gc_uuid` onto it. This is the auto-resolve code path complement to E-160 (which fixed the manual connect code path).

## Background & Context
Observed in production on 2026-03-26: during sync for Standing Bear Varsity, the resolver created team id=454 for Bennington with `gc_uuid` but no `public_id` (UNIQUE collision prevented writing it). Team 280 already had Bennington's `public_id` from earlier seeding. Team 454 was deleted during cleanup, losing the `gc_uuid` until it was recovered from logs and manually written to team 280.

The root cause: `_ensure_opponent_team_row` does `INSERT OR IGNORE INTO teams ... gc_uuid=?` without first checking whether any existing team already has the target `public_id`. When the INSERT succeeds (new gc_uuid), the subsequent `_write_public_id` detects the collision and logs a warning, but the damage is done — a duplicate team row with gc_uuid and no public_id now exists.

Promoted from IDEA-046. Complementary to E-160 (manual connect fix). Together they close the duplicate-team creation problem for the two confirmed code paths.

## Goals
- Eliminate duplicate team creation when the resolver encounters an opponent whose `public_id` already exists on a different team row
- Merge `gc_uuid` onto the existing `public_id` stub instead of creating a new row
- Preserve all existing protections: manual-link protection, only-write-when-NULL semantics

## Non-Goals
- Fuzzy duplicate detection (IDEA-043) — different scope, broader problem
- Preventing duplicates at creation time across all code paths (IDEA-044) — broader architectural change
- Detecting or cleaning up existing duplicates retroactively

## Success Criteria
- When `_ensure_opponent_team_row` is called with a `gc_uuid` that does not exist in `teams` but the API-returned `public_id` already belongs to an existing team, the resolver merges the `gc_uuid` onto the existing row instead of creating a new one.
- No duplicate team rows are created during a full opponent resolution run.
- Existing behavior is preserved for: new teams (no prior row), teams matched by `gc_uuid`, and teams with manual links.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-162-01 | Merge gc_uuid onto existing public_id stub in OpponentResolver | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Lookup Order in `_ensure_opponent_team_row`

The current code checks `gc_uuid` first (via INSERT OR IGNORE). The fix should add a `public_id` lookup step. The corrected lookup order:

1. **Check by `gc_uuid`**: `SELECT id, name, public_id, season_year FROM teams WHERE gc_uuid = ?`. If found, this is the canonical row — update fields as needed and return.
2. **Check by `public_id`**: `SELECT id, name, gc_uuid, season_year FROM teams WHERE public_id = ?`. If found, this is a stub that needs `gc_uuid` backfilled. Write `gc_uuid` (with UNIQUE collision check) and update other fields as needed. Return this row's ID.
3. **Neither found**: INSERT a new row with `gc_uuid` only (no `public_id` in the INSERT — consistent with existing code pattern). Then call `_write_public_id` afterward for collision-safe `public_id` assignment.

### TN-2: gc_uuid UNIQUE Collision on Merge

When merging `gc_uuid` onto an existing `public_id` stub (step 2 above), the `gc_uuid` being written might already exist on a *different* row (a third row). This is the reverse collision case. Handle it the same way `_write_public_id` handles `public_id` collisions: check for `SELECT id FROM teams WHERE gc_uuid = ? AND id != ?` before writing, log a WARNING if collision detected, and skip the write.

### TN-3: Field Update Rules During Merge

When merging onto an existing stub (step 2):
- **gc_uuid**: Write only when existing row has NULL gc_uuid (only-write-when-NULL, with collision check per TN-2).
- **name**: Update only if existing name equals the gc_uuid string (UUID-as-name stub pattern, matching existing behavior).
- **season_year**: Write only when existing row has NULL season_year (only-write-when-NULL, matching existing behavior).
- **public_id**: Already present on the stub — do not overwrite.

### TN-4: Test Scenarios

1. **Happy path merge**: Team row exists with `public_id` but NULL `gc_uuid`. Resolver calls `_ensure_opponent_team_row` with a new `gc_uuid` and the same `public_id`. Result: `gc_uuid` written to existing row, no new row created.
2. **gc_uuid collision on merge**: Team A has `public_id=X`. Team B has `gc_uuid=Y`. Resolver tries to merge `gc_uuid=Y` onto Team A. Result: WARNING logged, `gc_uuid` write skipped, Team A's ID returned.
3. **Existing gc_uuid match** (no change): Team exists with matching `gc_uuid`. Result: existing behavior preserved.
4. **New team** (no prior row): Neither `gc_uuid` nor `public_id` found. Result: new row created (existing behavior preserved).
5. **Manual-link protection**: Existing `opponent_links` row with `resolution_method='manual'` is not overwritten (existing behavior, verified not broken by this change).

## Open Questions
None — the fix is well-scoped and the merge strategy is clear from the production incident.

## History
- 2026-03-26: Created from IDEA-046. SE and api-scout consulted during discovery.
- 2026-03-26: Codex spec review — 3 findings, all accepted. Fixed AC-6 scenario count (4→5), clarified TN-1 step 3 INSERT is gc_uuid-only, corrected test file path to tests/test_crawlers/.
- 2026-03-26: Set to READY. Review scorecard:

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex iteration 1 | 3 | 3 | 0 |
| Codex iteration 2 | 2 | 2 (refined) | 0 |
| **Total** | **5** | **5** | **0** |

- 2026-03-27: COMPLETED. Single-story epic: refactored `_ensure_opponent_team_row` from INSERT-first to three-step SELECT lookup (gc_uuid → public_id → INSERT), added symmetric `_write_gc_uuid` helper. AC-2 wording updated during CR to reflect canonical gc_uuid-match behavior per TN-1. 50 tests passing (48 existing + 2 new).

  Implementation review scorecard:

  | Review Pass | Findings | Accepted | Dismissed |
  |---|---|---|---|
  | Per-story CR -- E-162-01 | 2 | 1 | 1 |
  | CR integration review | 0 | 0 | 0 |
  | Codex code review | 3 | 3 | 0 |
  | **Total** | **5** | **4** | **1** |

  **Documentation assessment**: No documentation impact. No new features/endpoints, no architecture changes, no schema changes, no new agents.

  **Context-layer assessment**:
  1. New convention, pattern, or constraint established? **No** — the three-step lookup and `_write_gc_uuid` helper are localized to OpponentResolver internals.
  2. Architectural decision with ongoing implications? **No** — bug fix within existing architecture.
  3. Footgun, failure mode, or boundary discovered? **No** — the duplicate-creation footgun was already known (IDEA-046); this epic fixes it rather than discovering a new one.
  4. Change to agent behavior, routing, or coordination? **No** — pure implementation work.
  5. Domain knowledge discovered that should influence agent decisions? **No** — the gc_uuid/public_id merge semantics are implementation details, not domain knowledge.
  6. New CLI command, workflow, or operational procedure? **No** — no new commands or workflows.
