# Opponent Resolution Flow

> **Last updated:** 2026-03-28 | **Source:** E-168-03

How to resolve an opponent from the authenticated API into identifiers usable across both authenticated and public endpoints.

## The Resolution Chain

### Pass 1: Progenitor Chain (Primary)

#### Step 1: Get the opponent list

**Endpoint:** [`GET /teams/{team_id}/opponents`](../endpoints/get-teams-team_id-opponents.md)

Returns the full opponent registry for a team. Each record contains three UUID fields with different semantics:

| Field | Purpose |
|-------|---------|
| `root_team_id` | Local registry key. Use with `/teams/{team_id}/opponent/{root_team_id}`, roster, avatar. |
| `owning_team_id` | Always equals the path `team_id`. Informational only. |
| `progenitor_team_id` | **Canonical GC team UUID.** Nullable (~14% missing). This is the key to step 2. |

Filter out `is_hidden=true` records (duplicates/bad entries).

#### Step 2: Get team metadata via progenitor_team_id

**Endpoint:** [`GET /teams/{progenitor_team_id}`](../endpoints/get-teams-team_id.md)

Call the team detail endpoint using `progenitor_team_id` as the `team_id` path parameter. The response includes `public_id` -- the slug needed for public endpoints.

This works because `progenitor_team_id` is a canonical GC team UUID, and the `/teams/{team_id}` endpoint accepts any valid team UUID (not just the user's own teams).

#### Step 3: Use public_id for public endpoints

With the `public_id` from step 2, the following unauthenticated endpoints become available:

- [`GET /public/teams/{public_id}`](../endpoints/get-public-teams-public_id.md) -- team profile, record, staff
- [`GET /public/teams/{public_id}/games`](../endpoints/get-public-teams-public_id-games.md) -- game schedule with scores
- [`GET /public/game-stream-processing/{game_stream_id}/details`](../endpoints/get-public-game-stream-processing-game_stream_id-details.md) -- inning-by-inning line scores

### Pass 2: POST /search Fallback (Null-Progenitor Opponents)

Opponents with `progenitor_team_id: null` (~14%) cannot be resolved through the progenitor chain. The **POST /search fallback** runs after the progenitor chain completes, targeting only unlinked opponents (no existing `resolution_method`, not hidden).

**Endpoint:** [`POST /search`](../endpoints/post-search.md)

#### Auto-Accept Criteria

All three conditions must be true for automatic resolution:

1. **Exact name match** (case-insensitive) between `opponent_links.opponent_name` and `result.name`
2. **Season year match**: `result.season.year` matches the member team's `season_year`
3. **Single result**: Exactly one result remains after both filters

If 0 or 2+ results match after filtering, the opponent is left unlinked for manual resolution via the admin UI.

#### What POST /search Returns

Each search hit provides both key identifiers needed for resolution:

- `result.id` -- the `progenitor_team_id` (canonical GC team UUID, stored as `gc_uuid`)
- `result.public_id` -- the public slug for unauthenticated endpoints

This means search-resolved opponents skip the progenitor chain entirely -- a single API call yields both identifiers.

#### Resolution Method

Search-resolved opponents are recorded with `resolution_method='search'`, distinguishing them from progenitor-chain resolutions (`'auto'`). Both the automated search fallback and admin resolve use `resolution_method='search'` (see TN-7). Legacy pre-E-168 admin links may carry `resolution_method='manual'`.

## Admin Resolve Workflow

The admin UI (`/admin/opponents/{link_id}/resolve`) provides a manual resolution path for opponents that neither the progenitor chain nor the search fallback could resolve. The admin resolve workflow uses [`POST /search`](../endpoints/post-search.md) to search the GameChanger team database by name.

The admin enters a search query, reviews the results (which include team name, location, season, staff, and player count), and selects the correct match. The selected team's `id` (gc_uuid) and `public_id` are stored, and the opponent is marked with `resolution_method='search'`.

## WARNING: Bridge Endpoints Restricted to "Followed" Teams Only

Both bridge endpoints are restricted and **cannot be used for opponent resolution**:

- [`GET /teams/{team_id}/public-team-profile-id`](../endpoints/get-teams-team_id-public-team-profile-id.md) -- UUID to public_id. Returns HTTP 403 for opponent UUIDs (confirmed 2026-03-09).
- [`GET /teams/public/{public_id}/id`](../endpoints/get-teams-public-public_id-id.md) -- public_id to UUID. Returns HTTP 403 for opponent public_ids (confirmed 2026-03-11).

Both bridges only work for **teams the authenticated user follows** (operator-reported 2026-03-12). The exact association types that permit access (coaching/admin membership, explicitly followed, bookmarked) have not been independently verified, but the 403 behavioral outcome for opponent teams is confirmed via curl and proxy capture.

**Do NOT use either bridge endpoint for opponent resolution.** The chain above (opponents list -> team detail via progenitor_team_id -> public_id from team metadata) is the correct path -- it requires no follow association.

**Note:** Following can be automated via [`POST /teams/{team_id}/follow`](../endpoints/post-teams-team_id-follow.md) (204 No Content, "follow as fan"). This unlocks bridge endpoints and other follow-gated authenticated data. However, following is not needed for resolution itself, and it is also **not required for the scouting pipeline** -- the public-endpoint scouting chain (schedule, roster, boxscores) works without any follow association (confirmed on unfollowed team, 2026-03-12). See [opponent-scouting.md](opponent-scouting.md#following-not-required).

## Null-Progenitor Fallback

~14% of opponents have `progenitor_team_id: null`. The two-pass resolution architecture addresses this:

1. **POST /search fallback (automated)**: After the progenitor chain completes, the resolver runs POST /search for each unlinked opponent, applying the auto-accept criteria (exact name + season year + single result). This is the primary automated fallback.
2. **Admin resolve (manual)**: Opponents that the search fallback cannot resolve (0 or 2+ matches) are surfaced in the admin UI for manual resolution via POST /search.
3. **Legacy experimental path**: `resolve_unlinked()` in `bb data resolve-opponents` attempts a follow→bridge→unfollow flow for null-progenitor opponents. This is experimental and may not work for all opponents.

## Resolution Statistics

The two-pass architecture resolves opponents through three methods:

| Category | Method | Resolution Method Value |
|----------|--------|------------------------|
| Progenitor chain (pass 1) | Automated via `progenitor_team_id` → team metadata | `'auto'` |
| POST /search fallback (pass 2) | Automated via exact name + season year match | `'search'` |
| Admin resolve | Manual selection via admin UI search | `'search'` |
| Unresolved | No match found; awaiting manual resolution | (none) |

Historical baseline (single team, 70 opponents):

| Category | Count | Percentage |
|----------|-------|------------|
| Auto-resolved (progenitor_team_id present) | ~60/70 | ~86% |
| Null progenitor (candidates for search fallback) | ~10/70 | ~14% |

The search fallback is expected to resolve a significant portion of the ~14% null-progenitor opponents, leaving only ambiguous cases (0 or 2+ matches) for manual resolution.

## Three ID Types Summary

| ID | Source | Purpose |
|----|--------|---------|
| `root_team_id` | `GET /teams/{team_id}/opponents` | Local identifier from GC's opponent registry |
| `progenitor_team_id` | `GET /teams/{team_id}/opponents` | Canonical GC team UUID; nullable (~14% missing) |
| `public_id` | `GET /teams/{progenitor_team_id}` response or `POST /search` result | Public slug for unauthenticated endpoints |

## See Also

- [opponent-scouting.md](opponent-scouting.md) -- How to use `public_id` to retrieve game schedules, player rosters, per-game boxscores, and compute season aggregates
- [`POST /search`](../endpoints/post-search.md) -- Endpoint spec for the team search used in both automated fallback and admin resolve
