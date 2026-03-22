# Opponent Resolution Flow

How to resolve an opponent from the authenticated API into identifiers usable across both authenticated and public endpoints.

## The Resolution Chain

### Step 1: Get the opponent list

**Endpoint:** [`GET /teams/{team_id}/opponents`](../endpoints/get-teams-team_id-opponents.md)

Returns the full opponent registry for a team. Each record contains three UUID fields with different semantics:

| Field | Purpose |
|-------|---------|
| `root_team_id` | Local registry key. Use with `/teams/{team_id}/opponent/{root_team_id}`, roster, avatar. |
| `owning_team_id` | Always equals the path `team_id`. Informational only. |
| `progenitor_team_id` | **Canonical GC team UUID.** Nullable (~14% missing). This is the key to step 2. |

Filter out `is_hidden=true` records (duplicates/bad entries).

### Step 2: Get team metadata via progenitor_team_id

**Endpoint:** [`GET /teams/{progenitor_team_id}`](../endpoints/get-teams-team_id.md)

Call the team detail endpoint using `progenitor_team_id` as the `team_id` path parameter. The response includes `public_id` -- the slug needed for public endpoints.

This works because `progenitor_team_id` is a canonical GC team UUID, and the `/teams/{team_id}` endpoint accepts any valid team UUID (not just the user's own teams).

### Step 3: Use public_id for public endpoints

With the `public_id` from step 2, the following unauthenticated endpoints become available:

- [`GET /public/teams/{public_id}`](../endpoints/get-public-teams-public_id.md) -- team profile, record, staff
- [`GET /public/teams/{public_id}/games`](../endpoints/get-public-teams-public_id-games.md) -- game schedule with scores
- [`GET /public/game-stream-processing/{game_stream_id}/details`](../endpoints/get-public-game-stream-processing-game_stream_id-details.md) -- inning-by-inning line scores

## WARNING: Bridge Endpoints Restricted to "Followed" Teams Only

Both bridge endpoints are restricted and **cannot be used for opponent resolution**:

- [`GET /teams/{team_id}/public-team-profile-id`](../endpoints/get-teams-team_id-public-team-profile-id.md) -- UUID to public_id. Returns HTTP 403 for opponent UUIDs (confirmed 2026-03-09).
- [`GET /teams/public/{public_id}/id`](../endpoints/get-teams-public-public_id-id.md) -- public_id to UUID. Returns HTTP 403 for opponent public_ids (confirmed 2026-03-11).

Both bridges only work for **teams the authenticated user follows** (operator-reported 2026-03-12). The exact association types that permit access (coaching/admin membership, explicitly followed, bookmarked) have not been independently verified, but the 403 behavioral outcome for opponent teams is confirmed via curl and proxy capture.

**Do NOT use either bridge endpoint for opponent resolution.** The chain above (opponents list -> team detail via progenitor_team_id -> public_id from team metadata) is the correct path -- it requires no follow association.

**Note:** Following can be automated via [`POST /teams/{team_id}/follow`](../endpoints/post-teams-team_id-follow.md) (204 No Content, "follow as fan"). This unlocks bridge endpoints and other follow-gated authenticated data. However, following is not needed for resolution itself, and it is also **not required for the scouting pipeline** -- the public-endpoint scouting chain (schedule, roster, boxscores) works without any follow association (confirmed on unfollowed team, 2026-03-12). See [opponent-scouting.md](opponent-scouting.md#following-not-required).

## Null-Progenitor Fallback

~14% of opponents have `progenitor_team_id: null`. These cannot be auto-resolved through the chain above. As of E-146, `bb data resolve-opponents` runs an automated follow→bridge→unfollow flow via `resolve_unlinked()` that attempts to resolve null-progenitor opponents by temporarily following the team to unlock the bridge endpoints (experimental -- may not work for all opponents). If the automated flow fails, manual linking remains the fallback: an operator identifies the team and provides the mapping.

## Resolution Statistics

| Category | Count | Percentage |
|----------|-------|------------|
| Auto-resolved (progenitor_team_id present) | ~60/70 | ~86% |
| Manual linking required (null progenitor) | ~10/70 | ~14% |

These numbers are from a single team's opponent registry (70 total opponents). The ratio may vary across teams.

## Three ID Types Summary

| ID | Source | Purpose |
|----|--------|---------|
| `root_team_id` | `GET /teams/{team_id}/opponents` | Local identifier from GC's opponent registry |
| `progenitor_team_id` | `GET /teams/{team_id}/opponents` | Canonical GC team UUID; nullable (~14% missing) |
| `public_id` | `GET /teams/{progenitor_team_id}` response | Public slug for unauthenticated endpoints |

## See Also

- [opponent-scouting.md](opponent-scouting.md) -- How to use `public_id` to retrieve game schedules, player rosters, per-game boxscores, and compute season aggregates
