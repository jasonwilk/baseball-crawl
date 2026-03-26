# E-160: Fix save_manual_opponent_link Duplicate Team Bug

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
When an admin manually links an opponent via the connect flow, `save_manual_opponent_link` sets `public_id` on the `opponent_links` row but does not create or update a corresponding tracked team in the `teams` table. When the scouting pipeline later runs for that opponent, it creates a new team row (keyed on `public_id`), producing a duplicate team alongside the original stub team created by the schedule loader or opponent discovery.

## Background & Context
The opponent lifecycle has two resolution paths:

1. **Auto-resolve** (`OpponentResolver`): Looks up the opponent via the GC API, creates/finds a tracked team row in `teams` (with `gc_uuid` and `public_id`), and sets `resolved_team_id` on the `opponent_links` row. This path is complete and correct.

2. **Manual connect** (`save_manual_opponent_link`): The admin pastes a GameChanger URL, the system extracts the `public_id`, and updates the `opponent_links` row. However, it sets `resolved_team_id = NULL` and does not touch the `teams` table at all.

The gap in the manual path means:
- The original stub team (created by schedule loader with `source='schedule'` or `source='discovered'`) has no `public_id`
- The `opponent_links` row has a `public_id` but no `resolved_team_id`
- When `ScoutingCrawler._ensure_team_row(public_id=...)` runs, it does `INSERT OR IGNORE INTO teams` keyed on `public_id` — since no existing team has that `public_id`, a new team row is created
- Result: two team rows for the same opponent

No expert consultation required — this is a straightforward bug fix with a clear root cause in the existing code.

## Goals
- Manual opponent linking creates or updates the tracked team's `public_id` in the `teams` table (when a matching stub exists)
- Manual opponent linking sets `resolved_team_id` on the `opponent_links` row (when a matching stub exists)
- No duplicate teams are created when the scouting pipeline runs after a manual link (when a matching stub exists)
- When no matching stub exists, graceful degradation: the link is saved but `resolved_team_id` remains NULL and deduplication is deferred until a stub is created

## Non-Goals
- Cleaning up existing duplicate teams already in the database (that's a data migration, not this fix)
- Changing the auto-resolve path (it already works correctly)
- Adding a team merge/dedup UI (see IDEA-043, IDEA-044)

## Success Criteria
- After manually connecting an opponent (when a matching stub exists), the `teams` row has the correct `public_id` and the `opponent_links` row has a non-NULL `resolved_team_id`
- Running the scouting pipeline after a manual link does not create a duplicate team
- When no matching stub exists, the connect flow completes without error (graceful degradation)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-160-01 | Fix save_manual_opponent_link to update teams and set resolved_team_id | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Root Cause
`save_manual_opponent_link` (in `src/api/db.py`) only updates the `opponent_links` row. It does not:
1. Find an existing tracked team row in `teams` and set `public_id` on it
2. Set `resolved_team_id` on the `opponent_links` row

The auto-resolve path (`OpponentResolver._ensure_opponent_team_row` + `_upsert_resolved`) handles both steps correctly. The manual path must be brought to parity.

### TN-2: Fix Strategy
After writing the `public_id` to `opponent_links`, the fix should:
1. Look up the `opponent_links` row by `link_id` to get `our_team_id` and `opponent_name`
2. Find the existing teams stub using a two-tier lookup: (a) Primary: the `opponent_team_id` in `team_opponents` where `our_team_id` matches and the team name matches `opponent_name` (join `team_opponents` to `teams` on `opponent_team_id = teams.id` where `teams.name = opponent_name` and `teams.membership_type = 'tracked'`). (b) Fallback: if no `team_opponents` row exists (discovery-path stubs created by `bulk_create_opponents` do NOT create `team_opponents` rows — see IDEA-042), match directly on `teams.name = opponent_name` and `teams.membership_type = 'tracked'`. If multiple matches, prefer the one with `public_id IS NULL`; if still ambiguous (multiple NULL-slug stubs with the same name), prefer the highest `id` (most recently created). If no single winner after tie-break, treat as no match (graceful degradation per step 5).
3. If found and `teams.public_id IS NULL`: set `teams.public_id = public_id` on that stub AND set `opponent_links.resolved_team_id` to the stub's `id`
4. If found and `teams.public_id` is already set: apply the TN-3 overwrite rule (update if no collision, skip with WARNING if slug already owned by another team), and set `resolved_team_id` to the stub's `id`
5. If no matching stub found: leave `resolved_team_id = NULL` (current behavior — graceful degradation)

The caller (`connect_opponent` in `src/api/routes/admin.py`) already has the `link` dict with `our_team_id` and `opponent_name`, and should pass the necessary context.

### TN-3: Overwrite Rule
A manual connect is an explicit admin assertion that the entered slug is correct. If the stub team already has a non-NULL `public_id` that DIFFERS from the admin-entered slug, check whether any OTHER `teams` row already owns the new slug (the UNIQUE index on `public_id` would reject a duplicate). If the slug is already owned by another team, skip the overwrite, leave `teams.public_id` unchanged, and log a WARNING: "Slug {slug} already owned by teams.id={other_id} — manual merge required." Otherwise, update `teams.public_id` to the new slug and log a WARNING that the existing slug is being replaced. This is necessary because `scout_all()` enumerates work from `opponent_links.public_id` — if `teams.public_id` still holds the old slug, `_ensure_team_row(public_id=new_slug)` would find no match and create a duplicate. If the slugs match, no update needed. The `resolved_team_id` should be set in all cases (even when the overwrite is skipped due to collision).

### TN-4: Existing opponent_links.resolved_team_id Semantics
Looking at the opponent_links schema and the auto-resolve upsert SQL (`_UPSERT_RESOLVED_SQL`), `resolved_team_id` is the FK to the opponent's tracked team in `teams`. The manual connect path must set this to the same value that the auto-resolve path would.

### TN-5: Disconnect-Path Symmetry
The current `disconnect_opponent_link` function clears `opponent_links.public_id`, `resolved_team_id`, `resolution_method`, and `resolved_at` — but does NOT clear `teams.public_id`. After E-160, the manual connect path writes `teams.public_id`, so disconnect must also clear it to allow a clean reconnect (disconnect → reconnect with correct URL without triggering TN-3's overwrite WARNING).

`disconnect_opponent_link` must be updated to: when `resolution_method = 'manual'`, also clear `teams.public_id` on the stub team — BUT only if no other `opponent_links` rows reference the same `resolved_team_id` (multiple member teams can link to the same tracked opponent). If other links exist, leave `teams.public_id` intact to avoid breaking their resolution. Auto-resolved links are not affected (disconnect already returns 400 for non-manual links).

## Open Questions
None.

## History
- 2026-03-26: Created
- 2026-03-26: Marked READY after 4 Codex iterations and 2 internal review rounds.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 6 | 4 | 2 |
| Internal iteration 1 — Holistic team | 7 | 7 | 0 |
| Internal iteration 2 — CR spec audit | 4 | 3 | 1 |
| Internal iteration 2 — Holistic team | 4 | 4 | 0 |
| Codex iteration 1 | 4 | 4 | 0 |
| Codex iteration 2 | 3 | 3 | 0 |
| Codex iteration 3 | 3 | 3 | 0 |
| Codex iteration 4 | 4 | 4 | 0 |
| **Total** | **~35** | **~32** | **~3** |
