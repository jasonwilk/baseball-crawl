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

## WARNING: `/public-team-profile-id` Returns 403 for Opponents

[`GET /teams/{team_id}/public-team-profile-id`](../endpoints/get-teams-team_id-public-team-profile-id.md) is a UUID-to-public_id bridge, but it **returns HTTP 403 for opponent UUIDs** (confirmed 2026-03-09). It only works for teams the authenticated user is a member of.

**Do NOT use this endpoint for opponent resolution.** The chain above (opponents -> team detail -> public_id) is the correct path.

## Null-Progenitor Fallback

~14% of opponents have `progenitor_team_id: null`. These cannot be auto-resolved through the chain above. They require manual linking -- an operator identifies the team and provides the mapping.

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
