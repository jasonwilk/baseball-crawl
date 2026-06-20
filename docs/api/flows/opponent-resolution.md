# Opponent Resolution Flow

> **Last updated:** 2026-06-17 | **Source:** E-240-02

How to resolve an opponent from the authenticated API into identifiers usable across both authenticated and public endpoints.

> **Scope note (2026-06-17, E-240-02):** This doc describes the *reusable*
> resolution mechanism only -- **Pass 1** (the `opponents` registry →
> `GET /teams/{progenitor_team_id}` progenitor chain) plus the **`POST /search`
> name fallback**. The deleted machinery that older revisions described -- the
> admin resolve UI (`/admin/opponents/{link_id}/resolve`), the two-pass
> `opponent_resolver.py` / `opponent_seeder.py` modules, and the
> `bb data resolve-opponents` command -- was **removed in E-239** and is gone
> from the repo. The follow→bridge→unfollow path is **BANNED**, not "legacy"
> (`.claude/rules/gc-uuid-bridge.md`). The morning-run scheduled-report flow
> (E-240) consumes exactly this Pass 1 + search mechanism as its rung-(a) /
> rung-(c) resolution ladder.

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

If 0 or 2+ results match after filtering, the opponent is left unlinked for one-time operator mapping via `bb report map-opponent` (the deleted admin UI's replacement).

#### What POST /search Returns

Each search hit provides both key identifiers needed for resolution:

- `result.id` -- the `progenitor_team_id` (canonical GC team UUID, stored as `gc_uuid`)
- `result.public_id` -- the public slug for unauthenticated endpoints

This means search-resolved opponents skip the progenitor chain entirely -- a single API call yields both identifiers.

#### Resolution Method

Search-resolved opponents are recorded with `resolution_method='search'`,
distinguishing them from progenitor-chain resolutions (`'progenitor'`).

> **Removed (E-239):** Earlier revisions described an **admin resolve UI**
> (`/admin/opponents/{link_id}/resolve`) as the manual path for opponents that
> neither the progenitor chain nor the search fallback could resolve. That UI and
> its route were **deleted in E-239** along with the rest of the
> opponent-management surface; there is no admin resolve workflow in the repo.
> The replacement operator path in the scheduled-report flow (E-240) is the
> `bb report map-opponent <root_team_id> <public_id|GC team URL>` CLI command,
> which UPDATEs the pending `opponent_links` row with an operator-supplied
> mapping (or marks it `--no-presence`). The `resolution_method='operator'` value
> records an operator mapping.

## WARNING: Bridge Endpoints Restricted to "Followed" Teams Only

Both bridge endpoints are restricted and **cannot be used for opponent resolution**:

- [`GET /teams/{team_id}/public-team-profile-id`](../endpoints/get-teams-team_id-public-team-profile-id.md) -- UUID to public_id. Returns HTTP 403 for opponent UUIDs (confirmed 2026-03-09).
- [`GET /teams/public/{public_id}/id`](../endpoints/get-teams-public-public_id-id.md) -- public_id to UUID. Returns HTTP 403 for opponent public_ids (confirmed 2026-03-11).

Both bridges only work for **teams the authenticated user follows** (operator-reported 2026-03-12). The exact association types that permit access (coaching/admin membership, explicitly followed, bookmarked) have not been independently verified, but the 403 behavioral outcome for opponent teams is confirmed via curl and proxy capture.

**Do NOT use either bridge endpoint for opponent resolution.** The chain above (opponents list -> team detail via progenitor_team_id -> public_id from team metadata) is the correct path -- it requires no follow association.

**Note:** Following can be automated via [`POST /teams/{team_id}/follow`](../endpoints/post-teams-team_id-follow.md) (204 No Content, "follow as fan"). This unlocks bridge endpoints and other follow-gated authenticated data. However, following is not needed for resolution itself, and it is also **not required for the scouting pipeline** -- the public-endpoint scouting chain (schedule, roster, boxscores) works without any follow association (confirmed on unfollowed team, 2026-03-12). See [opponent-scouting.md](opponent-scouting.md#following-not-required).

## Null-Progenitor Fallback

~14% of opponents have `progenitor_team_id: null` (the key is omitted on
manually-typed opponents). Two resolution paths apply, in order:

1. **POST /search fallback (automated)**: After the progenitor chain completes,
   run `POST /search` (via `search_teams_by_name()`) for each unlinked opponent,
   auto-accepting only on an unambiguous single match. This is the primary
   automated fallback.
2. **Operator mapping (manual)**: Opponents the search fallback cannot resolve
   (0 or 2+ matches, or genuinely unindexed teams) are surfaced to the operator
   and mapped once via `bb report map-opponent <root_team_id> <public_id|GC team URL>`
   (E-240). This replaces the deleted admin resolve UI.

> **BANNED path -- do NOT use.** The **follow → bridge → unfollow** pattern
> (former `resolve_unlinked()` / `_follow_bridge_unfollow()`, run via
> `bb data resolve-opponents`) is **deleted and banned**, not "legacy" or
> "experimental." It followed against `root_team_id` (the WRONG namespace --
> `root_team_id` is not a `gc_uuid`) and *mutated external GameChanger follow
> state* (a `POST /follow`, the bridge call, then best-effort unfollow `DELETE`s),
> so a failed cycle could leave the account following teams it never intended to.
> The module and command were removed in E-239. New work MUST NOT reintroduce
> this path -- see `.claude/rules/gc-uuid-bridge.md` ("BANNED PATH") and route any
> such need to PM. The correct fallbacks are the read-only `POST /search` bridge
> and operator-pasted GC team URLs for unindexed teams.

## Resolution Statistics

Opponents resolve through these methods:

| Category | Method | Resolution Method Value |
|----------|--------|------------------------|
| Progenitor chain (Pass 1) | Automated via `progenitor_team_id` → team metadata | `'progenitor'` |
| POST /search fallback (Pass 2) | Automated via unambiguous single name match | `'search'` |
| Operator mapping | Manual via `bb report map-opponent` (replaces deleted admin UI) | `'operator'` |
| Unresolved | No match found; awaiting operator mapping | (none) |

Historical baseline (single team, 70 opponents):

| Category | Count | Percentage |
|----------|-------|------------|
| Auto-resolved (progenitor_team_id present) | ~60/70 | ~86% |
| Null progenitor (candidates for search fallback) | ~10/70 | ~14% |

The search fallback is expected to resolve a significant portion of the ~14% null-progenitor opponents, leaving only ambiguous cases (0 or 2+ matches) and genuinely unindexed teams for one-time operator mapping via `bb report map-opponent`.

## Three ID Types Summary

| ID | Source | Purpose |
|----|--------|---------|
| `root_team_id` | `GET /teams/{team_id}/opponents` | Local identifier from GC's opponent registry |
| `progenitor_team_id` | `GET /teams/{team_id}/opponents` | Canonical GC team UUID; nullable (~14% missing) |
| `public_id` | `GET /teams/{progenitor_team_id}` response or `POST /search` result | Public slug for unauthenticated endpoints |

## See Also

- [opponent-scouting.md](opponent-scouting.md) -- How to use `public_id` to retrieve game schedules, player rosters, per-game boxscores, and compute season aggregates
- [`POST /search`](../endpoints/post-search.md) -- Endpoint spec for the team search used in the automated name fallback (Pass 2)
- [`.claude/rules/gc-uuid-bridge.md`](../../../.claude/rules/gc-uuid-bridge.md) -- The bridge pattern, the reverse `GET /teams/{gc_uuid}` rung-(a) bridge, and the BANNED follow→bridge→unfollow path
