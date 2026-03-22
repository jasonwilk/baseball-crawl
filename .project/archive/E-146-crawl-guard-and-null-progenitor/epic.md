# E-146: Crawl Pipeline Guards and Null-Progenitor Auto-Resolution

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview

Eliminate wasted API calls from the crawl pipeline and automate resolution of the ~14% of opponents that currently require manual linking. Two related improvements: (1) remove the OpponentCrawler's Phase 2 roster fetch that always 403s for opponent teams, and (2) add a follow→bridge→unfollow flow to resolve null-progenitor opponents to a `public_id`, enabling the scouting pipeline to cover them.

## Background & Context

**Expert consultation completed:** api-scout (endpoint safety, follow/bridge/unfollow flow) and software-engineer (crawler architecture, guard placement).

**Goal 1 -- Known-bad API calls:** The `OpponentCrawler` has a Phase 2 that calls `GET /teams/{progenitor_team_id}/players` for every opponent with a canonical UUID. This authenticated endpoint returns 403 for non-owned teams. The error is caught and logged (`opponent.py:253`), but the calls are entirely wasted -- the scouting pipeline already fetches opponent rosters via the public endpoint `GET /teams/public/{public_id}/players`, which works without team ownership.

**Goal 2 -- Null-progenitor opponents:** ~14% of opponents have `progenitor_team_id: null` in the GC opponents registry. These cannot be auto-resolved through the standard chain (opponents → team detail → public_id). They are stored as unlinked rows in `opponent_links` with `resolution_method=NULL, public_id=NULL`, and are excluded from the scouting pipeline (`scout_all()` filters on `public_id IS NOT NULL`).

For these opponents, we have `root_team_id` -- a UUID that GC accepts in some team-scoped endpoints (`GET /teams/{root_team_id}/players`, avatar). The documented flow: follow the team as fan → use the bridge endpoint to get `public_id` → store it → unfollow. However, api-scout's analysis raises two concerns: (1) `root_team_id` is documented for only 3 specific endpoints -- follow and bridge are NOT among them, and (2) null progenitor may indicate GC has no canonical team record at all ("ghost" entries). The implementation must be defensive: try the flow, handle failure gracefully, and leave opponents unlinked if any step fails. If the flow fails for all null-progenitor opponents, the result is valuable information (confirms manual linking is the only path) at low implementation cost.

**No expert consultation required for:** The member-team pipeline (roster, schedule, player-stats, game-stats crawlers) is already structurally guarded -- `load_config_from_db()` filters to `membership_type = 'member' AND gc_uuid IS NOT NULL`, so tracked teams never reach those crawlers.

## Goals
- Eliminate all known-bad authenticated API calls from the crawl pipeline (currently ~N wasted calls per run from OpponentCrawler Phase 2)
- Automate resolution of null-progenitor opponents via follow→bridge→unfollow, enabling them to enter the scouting pipeline without manual linking
- Handle all untested API paths defensively -- failures leave opponents in their current state (unlinked), never corrupt existing data

## Non-Goals
- Modifying the member-team pipeline crawlers (already guarded by `load_config_from_db()`)
- Adding new admin UI surfaces for null-progenitor resolution status
- Changing the scouting pipeline itself (once opponents have a `public_id`, `scout_all()` picks them up automatically)
- Verifying follow/bridge endpoint behavior ahead of implementation (the code itself is the test -- defensive error handling covers both success and failure paths)
- Implementing a retry/queue system for failed resolution attempts

## Success Criteria
- `OpponentCrawler.crawl_all()` makes zero `GET /teams/{uuid}/players` calls for non-owned teams
- Null-progenitor opponents with a `root_team_id` are attempted via follow→bridge→unfollow during `bb data resolve-opponents`
- Successfully resolved opponents gain a `public_id` in `opponent_links` and become eligible for `scout_all()`
- Failed resolution attempts are logged with the specific failure reason and do not affect existing data
- All changes have test coverage

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-146-01 | Remove OpponentCrawler Phase 2 roster fetch | DONE | None | SE |
| E-146-02 | Add follow→bridge→unfollow auto-resolution for null-progenitor opponents | DONE | None | SE |
| E-146-03 | Wire resolve_unlinked into CLI | DONE | E-146-02 | SE |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: OpponentCrawler Phase 2 removal

`OpponentCrawler.crawl_all()` (opponent.py) currently has two phases:
- Phase 1: Fetch opponent registry via `GET /teams/{team_id}/opponents` for each member team. **Keep this.**
- Phase 2: Fetch rosters via `GET /teams/{progenitor_id}/players` for each unique opponent UUID. **Remove this.**

Phase 2 is entirely redundant with the scouting pipeline, which fetches opponent rosters via `GET /teams/public/{public_id}/players` (a different, public-path endpoint that does not 403).

The removal affects:
- `OpponentCrawler.crawl_all()` -- remove the Phase 2 call to `_crawl_opponent_rosters()`
- `OpponentCrawler._crawl_opponent_rosters()` -- remove the method entirely
- `OpponentCrawler.__init__()` -- remove `self._roster_crawler` instantiation
- The `RosterCrawler` import in opponent.py -- remove if no longer used
- Summary log at the end of `_crawl_opponent_rosters()` -- the useful logging (opponent counts, progenitor stats) should be preserved, moved to Phase 1 or a new post-registry summary

### TN-2: Follow→bridge→unfollow flow

The auto-resolution flow for null-progenitor opponents:

1. **Query**: `SELECT DISTINCT root_team_id FROM opponent_links WHERE public_id IS NULL AND resolution_method IS NULL AND is_hidden = 0` -- one cycle per distinct `root_team_id`, not per row.
2. **For each distinct `root_team_id`:**
   a. `POST /teams/{root_team_id}/follow` (204 expected). If non-204, log and skip.
   b. `GET /teams/{root_team_id}/public-team-profile-id` (expect `{"id": "<public_id>"}`). If 403 or error, log and skip to unfollow.
   c. Store `public_id` via a fan-out UPDATE on all `opponent_links` rows sharing this `root_team_id` (see TN-6). Set `resolution_method='follow-bridge'`. No `teams` row is created (see TN-3).
   d. Unfollow: `DELETE /teams/{root_team_id}/users/{user_id}` then `DELETE /me/relationship-requests/{root_team_id}`. If unfollow fails, log warning but do not fail the overall flow.
3. **Rate limiting**: Minimum 2-second delay between each follow/bridge/unfollow cycle (more conservative than the existing 1.5s `_DELAY_SECONDS` in `OpponentResolver`, because follow is a write operation).

**Key unknowns (handled defensively):**
- Whether `root_team_id` is accepted by the follow endpoint (may return 404 or error). api-scout notes that `root_team_id` is documented for only 3 endpoints (opponent lookup, players, avatar) -- NOT follow or bridge. The follow/bridge endpoints may reject it.
- Whether null-progenitor opponents even have canonical GC team records. api-scout's assessment: null `progenitor_team_id` likely means GC has no canonical record for this team ("ghost" entries in the opponent registry). If so, follow would return 404 regardless of UUID type.
- Whether the two-step unfollow works for pure fan-follows (may only need Step 2)
- The `user_id` for the unfollow Step 1 -- must be obtained via `GET /me/user` or cached from auth

**Expected outcome**: Some or all null-progenitor opponents may fail the follow step. This is acceptable -- the defensive design means failures leave opponents unlinked (current state), and the summary log will show how many succeeded vs. failed. If zero succeed, the operator knows manual linking is the only path for these opponents. The implementation cost is low and the information value (confirming whether the flow works) is high.

**Resolution method**: Use `resolution_method='follow-bridge'` to distinguish from `'auto'` (progenitor chain) and `'manual'` (operator-provided). The existing COALESCE upsert logic in `_UPSERT_RESOLVED_SQL` already protects manual links.

### TN-3: No team row creation in resolve_unlinked

`resolve_unlinked()` does NOT create a `teams` row. It only stores `public_id` on existing `opponent_links` rows. The scouting pipeline's `ScoutingCrawler._ensure_team_row(public_id=...)` creates the team row when it first encounters the opponent during `scout_all()`.

**Why**: Creating a teams row with `gc_uuid=root_team_id` would conflict with the scouting pipeline, which creates team rows keyed by `public_id`. The same opponent would end up with two `teams.id` values -- one keyed by `root_team_id` (from resolve), one by `public_id` (from scouting). Deferring team row creation to the scouting pipeline avoids this split-identity problem.

### TN-6: Fan-out UPDATE for multi-member-team opponents

`opponent_links` is keyed by `(our_team_id, root_team_id)`. The same opponent (same `root_team_id`) may appear under multiple member teams (Lincoln Varsity, Lincoln JV, etc.). When `resolve_unlinked()` successfully obtains a `public_id` for a `root_team_id`, it must UPDATE all rows sharing that `root_team_id` -- not just one. A single UPDATE with `WHERE root_team_id = ? AND resolution_method IS NULL` handles both the fan-out and the manual-link protection (rows with `resolution_method='manual'` or `resolution_method='auto'` are already resolved and excluded).

### TN-4: Pipeline sequencing

The `resolve_unlinked()` method runs AFTER `resolve()` in the same CLI command (`bb data resolve-opponents`). This means:
1. `resolve()` processes all opponents with `progenitor_team_id` (auto-resolving ~86%)
2. `resolve_unlinked()` processes remaining unlinked opponents via follow→bridge→unfollow
3. Any newly resolved opponents immediately have `public_id` and are eligible for `scout_all()` in the next scouting run

### TN-5: User ID for unfollow

The unfollow Step 1 (`DELETE /teams/{team_id}/users/{user_id}`) requires the authenticated user's UUID. This can be obtained from `GET /me/user` (already documented, returns user profile including `id`). The implementation should fetch this once at the start of `resolve_unlinked()` and reuse it across all unfollow cycles.

### TN-7: GameChangerClient POST/DELETE extension

`GameChangerClient` currently only exposes `get()`, `get_paginated()`, and `get_public()`. The follow→bridge→unfollow flow requires `POST /teams/{id}/follow` and `DELETE /teams/{id}/users/{id}` + `DELETE /me/relationship-requests/{id}`. E-146-02 adds `post()` and `delete()` methods to the client, following the same pattern as `get()` (auth headers via `_ensure_access_token()`, error hierarchy). The auth-module rule at `.claude/rules/auth-module.md` notes that `GameChangerClient` uses `create_session()` for data-plane requests -- the new methods use the same session.

**Response shape contracts:**
- `post()`: Must handle 204 No Content (empty body) as success -- do not attempt JSON parsing. Return `None` on 204.
- `delete()`: Must handle both 204 No Content (no body, from `DELETE /teams/{id}/users/{id}`) and 200 with text body `"OK"` (from `DELETE /me/relationship-requests/{id}`) as success. Return `None` on 204, the text body on 200.

## Open Questions
- None remaining after expert consultation. All unknowns are handled via defensive implementation.

## History
- 2026-03-22: Created. Expert consultation: api-scout (endpoint safety, follow/bridge/unfollow flow analysis, root_team_id scope assessment), software-engineer (crawler architecture, guard placement, code locations). api-scout flagged root_team_id viability risk for Goal 2; addressed via defensive design rather than research spike.
- 2026-03-22: 3 spec review iterations, 12 findings accepted and incorporated, 2 dismissed (DE consultation -- single UPDATE, SE-owned). Consistency sweeps clean. Status set to READY.
- 2026-03-22: Dispatch started. Epic set to ACTIVE. E-146-01 assigned to SE.
- 2026-03-22: All 3 stories DONE. Review chain: codex review (3 findings remediated -- RateLimitError handling, errors accounting), per-story CR (2 MUST FIX on E-146-02 resolved), integration CR (clean after full suite). Epic set to COMPLETED.

### Documentation Assessment
- **Trigger fired**: `docs/api/flows/opponent-resolution.md` § "Null-Progenitor Fallback" states null-progenitor opponents "require manual linking." E-146 adds an automated follow→bridge→unfollow alternative. The doc needs updating to describe the experimental auto-resolution path alongside manual linking.
- **Action**: Dispatch docs-writer to update `docs/api/flows/opponent-resolution.md` before archiving.

### Context-Layer Assessment
1. **New agent capability or tool?** NO -- no new agents or tools added. `post()` and `delete()` extend an existing client class, not the agent ecosystem.
2. **New rule, convention, or workflow?** NO -- no new workflow conventions introduced. The resolve_unlinked flow is a feature, not a process change.
3. **Change to existing agent definitions?** NO -- no agent definitions modified.
4. **New skill or skill modification?** NO -- no skills added or changed.
5. **CLAUDE.md update needed?** NO -- the crawl pipeline changes are implementation details. CLAUDE.md already describes the opponent resolution pipeline and scouting flow at an appropriate level; the addition of `resolve_unlinked()` is an extension within that existing scope, not a new architectural pattern.
6. **Hook or settings change?** NO -- no hooks or settings modified.
- **Verdict**: No context-layer impact. No claude-architect dispatch needed.
