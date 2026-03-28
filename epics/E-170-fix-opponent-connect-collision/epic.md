# E-170: Fix Opponent Connect public_id Collision (500 Error)

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Fix a production 500 error when manually connecting an opponent via the admin UI. The `save_manual_opponent_link` function crashes with `sqlite3.IntegrityError: UNIQUE constraint failed: teams.public_id` when the stub team has `public_id=None` but another team row already owns the target `public_id`. The fix adds collision detection, merges by repointing to the existing team, and hardens the confirm page to warn before submission.

## Background & Context
The admin opponent resolution workflow (`POST /admin/opponents/{link_id}/connect`) allows the operator to manually link an unresolved opponent to a GameChanger team by URL/public_id. The DB function `save_manual_opponent_link` finds a tracked stub team and attempts to set its `public_id`. The function has three code paths based on the stub's `existing_public_id`:

1. **`existing_public_id is None`** (line 1301-1305): Blindly UPDATEs -- **no collision check**. This is the bug.
2. **`existing_public_id != public_id`** (line 1306-1326): Correctly checks for collision before updating.
3. **`existing_public_id == public_id`** (implicit): No-op (already correct).

The collision happens when E-167's dedup cascade or the scouting pipeline has already created a team row with the target `public_id`, and the opponent seeder independently created a name-only stub (no `public_id`). When the operator connects the stub to the same GameChanger team, the UPDATE violates the UNIQUE constraint.

The confirm page's duplicate detection (`_get_duplicate_name_for_link` -> `get_duplicate_opponent_name`) only checks the `opponent_links` table, not the `teams` table, so it cannot warn about this scenario.

**Expert consultation**: SE consulted on merge-vs-error behavior. Approach: merge automatically (repoint `resolved_team_id` to the existing team that owns the `public_id`) and surface an informational flash message so the operator knows what happened.

## Goals
- Eliminate the 500 error on `POST /admin/opponents/{link_id}/connect` when `public_id` collides
- Merge gracefully by repointing to the existing team row instead of crashing
- Surface the merge action to the operator via flash message
- Harden the confirm page to detect `teams`-table collisions before submission

## Non-Goals
- Orphan stub cleanup (stubs left behind after merge are harmless name-only rows; cleanup is a separate concern)
- Refactoring the broader `save_manual_opponent_link` function beyond the collision fix
- Fixing the `elif` branch's collision handling (it has the same class of bug — sets `resolved_team_id = stub_id` even when a collision is found — but different trigger conditions: stub already has a different `public_id`; lower priority since the trigger scenario is rarer)

## Success Criteria
- `POST /admin/opponents/{link_id}/connect` succeeds (303 redirect) when the target `public_id` already exists on another team row
- The `opponent_links.resolved_team_id` points to the existing team that owns the `public_id`
- The operator sees a flash message indicating the merge happened
- The confirm page warns when the target `public_id` already exists in the `teams` table
- No regressions in existing opponent connect tests

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-170-01 | Fix public_id collision in save_manual_opponent_link and harden confirm page | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Collision Detection Pattern
The `elif` branch (line 1307-1326) already has the correct collision query:
```sql
SELECT id FROM teams WHERE public_id = ? AND id != ?
```
The `None` branch needs the same check before the UPDATE. When a collision is found, the function should:
1. Skip the `UPDATE teams SET public_id` on the stub
2. Set `resolved_team_id` to `collision[0]` (the existing team's id) instead of `stub_id`
3. Return a signal to the caller indicating a merge occurred (and which team was merged into)

### Unconditional resolved_team_id UPDATE
Line 1328-1331 unconditionally sets `resolved_team_id = stub_id` for all cases where a stub is found — it runs after the if/elif block, not inside any branch. In the merge path (collision found in the `None` branch), the function must use the collision team's id at this line instead of `stub_id`. The implementer should either introduce a variable (`resolved_id`) that is set differently per branch, or restructure the UPDATE to be per-branch.

### Collision Query Must Include Name
The collision query should SELECT both `id` and `name` (e.g., `SELECT id, name FROM teams WHERE public_id = ? AND id != ?`) so the function can return the merged team's name for the flash message without a second query.

### Return Value Change
`save_manual_opponent_link` currently returns `None`. To signal merge info to the route handler, it should return a structured result (e.g., a dict or named tuple) with:
- `merged`: `bool` -- whether a merge occurred
- `merged_team_name`: `str | None` -- name of the team that was merged into (for the flash message)

The route handler uses this to build an appropriate flash message.

### Flash Message Priority
When a merge occurs, the merge flash message takes priority over the `opponent_links` duplicate warning. The duplicate warning is moot after merge — the link now points to the existing team that owns the `public_id`. The route handler should use the merge result to decide the flash message, not layer both messages.

### Confirm Page Hardening
`_get_duplicate_name_for_link` currently delegates to `get_duplicate_opponent_name`, which only queries `opponent_links`. A new check should also query `teams` for an existing row with the target `public_id`. The two warnings are semantically distinct and must have different message text: the existing `opponent_links` duplicate says "This URL is already linked to [name]" (another link uses the same URL); the `teams`-table collision says something like "A team with this URL already exists as [name]" (the connect will merge into the existing team). These may use different template variables or a single variable with differentiated text.

### Existing Test Fixture
`tests/test_admin_opponents.py` has an `opp_db` fixture with test data including teams and opponent_links. The collision scenario can be set up by inserting a team row with the target `public_id` before calling POST /connect. The existing test `test_connect_duplicate_public_id_warns_but_succeeds` (line 716) tests the `opponent_links` duplicate path -- the new tests cover the `teams` table collision path.

## Open Questions
- None

## History
- 2026-03-28: Created. Bug discovered in production -- operator hit 500 error when connecting opponent whose `public_id` was already owned by another team row.
- 2026-03-28: Set to READY after internal review (1 iteration, 3 review passes).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 5 | 2 | 2 |
| Internal iteration 1 -- PM holistic | 4 | 4 | 0 |
| Internal iteration 1 -- SE holistic | 3 | 1 | 2 |
| **Total** | **12** | **7** | **4** |
