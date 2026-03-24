# E-150: Team Lifecycle Management

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Enable full team deletion with cascade data removal and resolve the public_id gap that prevents scouting of opponents discovered only by UUID. Together these close the two biggest gaps in team lifecycle management: teams can accumulate data but never be removed, and opponents with gc_uuid but no public_id are silently skipped by the scouting pipeline.

## Background & Context
**Team deletion**: The current `POST /admin/teams/{id}/delete` route only deletes teams that are deactivated AND have zero data rows. `_check_team_has_data` checks 7 tables and refuses if any rows exist. `_delete_team_cascade` deletes only junction/access rows (team_opponents, team_rosters, opponent_links, user_team_access, coaching_assignments, crawl_jobs) and the teams row -- it never touches data tables (games, player stats, scouting_runs, spray_charts). The confirmation UI is a browser `window.confirm()` dialog, which is insufficient for a destructive cascade operation. The user explicitly wants deletion to be deliberate but possible: "it shouldn't be trivial but it should be possible."

**Public ID bridge**: `scout_all()` queries `opponent_links WHERE public_id IS NOT NULL`, silently skipping opponents that only have a gc_uuid. The forward bridge (`GET /teams/{uuid}/public-team-profile-id`) exists at `src/gamechanger/bridge.py` but is not wired into the scouting pipeline. See Technical Notes for the 403 constraint on opponent UUIDs.

**Expert consultations**: DE confirmed the 4-phase deletion order, shared-opponent detection via both `team_opponents` and `opponent_links`, and recommended application-code ordering over CASCADE migrations. SE confirmed the admin route patterns, bridge function signature, and scouting pipeline wiring points.

## Goals
- Admin can delete any team (member or tracked) with full cascade removal of all related data
- Deletion confirmation page shows exactly what will be deleted (row counts per table, shared opponent warnings) before the user commits
- Scouting pipeline attempts to resolve public_id for opponents with gc_uuid before filtering, expanding scouting coverage
- Opponents where bridge resolution fails (403) are logged clearly so the operator knows which need manual public_id assignment

## Non-Goals
- Seed data cleanup (user will handle manually once deletion is working)
- Soft delete / undo capability
- ON DELETE CASCADE schema migration (application-code ordering is the established pattern)
- Manual public_id entry UI for opponents (future idea if needed)
- Bulk team deletion

## Success Criteria
- A team with games, player stats, scouting runs, and spray charts can be fully deleted through the admin UI
- Shared opponents trigger a warning before deletion proceeds
- The confirmation page shows accurate counts of all data that will be removed
- `bb data scout` resolves public_id for at least some opponents that previously had gc_uuid only
- Opponents where resolution fails are logged with a clear message

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-150-01 | Cascade Delete with Confirmation Page | TODO | None | - |
| E-150-02 | Public ID Bridge Resolution in Scouting | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Cascade Deletion Order (4 phases)

All deletions run in a single transaction. The team being deleted is referred to as T.

**Phase 1 -- Game-child rows** (transitive deps through games):
- `player_game_batting` WHERE game_id IN (SELECT game_id FROM games WHERE home_team_id=T OR away_team_id=T)
- `player_game_pitching` WHERE game_id IN (SELECT game_id FROM games WHERE home_team_id=T OR away_team_id=T)
- `spray_charts` WHERE game_id IN (SELECT game_id FROM games WHERE home_team_id=T OR away_team_id=T)

**Phase 2 -- Games**:
- `games` WHERE home_team_id=T OR away_team_id=T

**Phase 3 -- Direct team_id FKs** (order within phase is arbitrary):
- `player_season_batting` WHERE team_id=T
- `player_season_pitching` WHERE team_id=T
- `spray_charts` WHERE team_id=T (safety net for rows where game_id IS NULL -- Phase 1 only catches game_id-linked rows)
- `team_rosters` WHERE team_id=T
- `scouting_runs` WHERE team_id=T
- `crawl_jobs` WHERE team_id=T
- `user_team_access` WHERE team_id=T
- `coaching_assignments` WHERE team_id=T
- `team_opponents` WHERE our_team_id=T OR opponent_team_id=T
- `opponent_links` WHERE our_team_id=T OR resolved_team_id=T

**Phase 4 -- Team row**:
- `teams` WHERE id=T

**Critical nuance -- game sharing**: Deleting games for team T also destroys per-game stats for the opponent side of those games (player_game_batting/pitching rows with a different team_id). The Phase 1 subquery correctly catches all player rows for affected games, not just rows where team_id=T. The confirmation page must surface this: "Deleting this team will also remove per-game stats from X games involving Y other teams."

### TN-2: Shared Opponent Detection

Before executing cascade delete on a tracked team, check both junction tables:

```sql
-- team_opponents: how many member teams link to this opponent?
SELECT COUNT(DISTINCT our_team_id) FROM team_opponents WHERE opponent_team_id = T

-- opponent_links: how many member teams reference this resolved team?
SELECT COUNT(DISTINCT our_team_id) FROM opponent_links WHERE resolved_team_id = T
```

If either count >= 1, the tracked team is referenced by at least one member team. The confirmation page must prominently display which member teams reference this opponent. The act of confirming deletion on the confirmation page constitutes acknowledgment -- no separate checkbox or input is required. (Note: delete is a global admin action with no requesting-member-team context, so any linkage count >= 1 triggers the warning.)

For member team deletion: also check if any tracked opponents would become orphaned (linked only from this member team via `team_opponents`). Surface this as informational, not blocking.

### TN-3: Forward Bridge 403 Constraint

The forward bridge (`resolve_uuid_to_public_id` in `src/gamechanger/bridge.py`) calls `GET /teams/{uuid}/public-team-profile-id`. Per the code's docstring and error handling, this endpoint returns 403 for teams not on the authenticated user's account. Most opponent teams are not on the user's account.

**Note**: CLAUDE.md describes this endpoint as working for "any team UUID" including opponents. The bridge.py implementation explicitly handles 403 as `BridgeForbiddenError` with the message "Only teams the user belongs to can use the forward bridge." The code is authoritative -- the CLAUDE.md description is misleading and should be corrected (out of scope for this epic but noted).

**Implementation approach**: Try the bridge for each distinct opponent with `teams.gc_uuid` and no `opponent_links.public_id`. The candidate query joins `opponent_links` to `teams` via `resolved_team_id` and uses `DISTINCT` on `resolved_team_id` to avoid redundant bridge API calls (the same opponent can appear in multiple `opponent_links` rows -- one per member team tracking it). Note: `opponent_links` has no `gc_uuid` column; `root_team_id` is a GC internal registry key, NOT a canonical UUID.

On success, update `teams.public_id` first (to prevent `_ensure_team_row` from creating a duplicate team row on the next scouting run), then update `opponent_links.public_id`, `resolved_at`, and `resolution_method`. If the `teams.public_id` update would violate the partial unique index (another teams row already has that public_id), skip the update for this opponent and log a WARNING: "Bridge resolution skipped for gc_uuid=X: public_id='Y' already assigned to teams.id=Z. Manual row reconciliation may be needed." Do not update `opponent_links` for this opponent. Continue to the next candidate. (Rationale: the stub row may have FK-dependent scouting data across many tables; automated merge is as complex as cascade delete itself and inappropriate for a best-effort enrichment step.)

On `BridgeForbiddenError`, log a clear warning identifying the opponent and skip. This is a best-effort enrichment -- it will resolve any opponents that happen to be on the authenticated account (e.g., if the operator manages multiple programs and one program's teams appear as opponents of another).

### TN-4: Confirmation Page Data Structure

The GET confirmation endpoint should compute and pass to the template:
- Team name, membership type, active status
- Row counts per table (games, player_game_batting, player_game_pitching, player_season_batting, player_season_pitching, team_rosters, scouting_runs, spray_charts, crawl_jobs, opponent_links, team_opponents, user_team_access, coaching_assignments). Note: the spray_charts count must use the combined condition (`WHERE game_id IN (affected games subquery) OR team_id = T`) to match what the cascade actually deletes -- a simple `WHERE team_id = T` undercounts by missing opponent-side rows from Phase 1.
- Total row count across all tables
- For game deletion: count of distinct opponent teams affected (whose per-game stats will also be removed)
- Shared opponent warnings (per TN-2) if the team is tracked
- Orphaned opponent list if the team is a member

## Open Questions
None -- all questions resolved via DE and SE consultation.

## History
- 2026-03-24: Created. DE consulted on cascade ordering and FK relationships. SE consulted on admin route patterns and bridge constraints.
- 2026-03-24: Set to READY after 3 internal review iterations + 2 Codex iterations (31 findings, 26 accepted, 5 dismissed).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic (DE + SE) | 9 | 9 | 0 |
| Internal iteration 2 -- CR spec audit | 1 | 1 | 0 |
| Internal iteration 2 -- Holistic (DE + SE) | 3 | 3 | 0 |
| Internal iteration 3 -- CR spec audit | 1 | 1 | 0 |
| Internal iteration 3 -- Holistic (DE + SE) | 0 | 0 | 0 |
| Codex iteration 1 | 6 | 4 | 2 |
| Codex iteration 2 | 7 | 4 | 3 |
| **Total** | **31** | **26** | **5** |
