# Opponent Scouting Flow

How to go from an opponent's `public_id` to a complete scouting dataset: game schedule, player roster, per-game boxscores, and locally computed season aggregates -- all via public endpoints, without needing UUIDs, without following.

**Prerequisites:** The opponent must have a non-null `public_id` in the `opponent_links` table. This is populated by the opponent resolution flow (see [opponent-resolution.md](opponent-resolution.md)).

---

## The Scouting Chain (Primary Path -- Public Endpoints)

> **IMPORTANT URL PATTERN WARNING**: Two different URL structures are used in this chain. They are NOT interchangeable:
> - Games: `/public/teams/{public_id}/games` (`public` before `teams`)
> - Players: `/teams/public/{public_id}/players` (`teams` before `public`)
>
> Both coexist in the GC API. The path order determines the auth behavior -- do not swap them.

### Step 1: Get completed game schedule (no auth)

**Endpoint:** [`GET /public/teams/{public_id}/games`](../endpoints/get-public-teams-public_id-games.md)

**Auth:** None required (no `gc-token`, no `gc-device-id`)

**Input:** `opponent_links.public_id` (e.g., `"DolZd7TTaXj5"`)

**Output:** Array of completed games. Extract from each record:
- `id` -- this IS the `game_stream_id` for the boxscore endpoint (step 3). No bridge call needed.
- `score.team`, `score.opponent_team` -- final score
- `home_away` -- `"home"` or `"away"`
- `start_ts` -- game date
- `opponent_team.name` -- opponent name

**Edge cases:**
- Returns only `game_status: "completed"` games. In-progress or scheduled games are not included. For scouting (stats from completed games) this is exactly what we want.
- No pagination observed (28--32 games returned in a single response). If a team has an unusually large history, pagination may be needed -- fall back to the authenticated path (see [Authenticated Fallback](#authenticated-fallback)).
- `opponent_team.avatar_url` is absent (not null, not empty) when no avatar -- use `.get("avatar_url")`.

**API calls:** 1 (no auth)

---

### Step 2: Get player roster (gc-token required)

**Endpoint:** [`GET /teams/public/{public_id}/players`](../endpoints/get-teams-public-public_id-players.md)

**Auth:** `gc-token` required (observed with auth; unauthenticated access unconfirmed)

**Input:** same `public_id` as step 1

**Output:** Array of player objects. Extract:
- `id` -- player UUID (used to match boxscore stat entries in step 3)
- `first_name`, `last_name` -- for display
- `number` -- jersey number (string; not unique within team -- two players can share a number)

**Edge cases:**
- `avatar_url` is an empty string `""` when unset (not null). Normalize with `.get("avatar_url") or None`.
- No pagination observed (full roster returned in single response).

**API calls:** 1 (gc-token)

---

### Step 3: Get per-game boxscore (gc-token required)

**Endpoint:** [`GET /game-stream-processing/{game_stream_id}/boxscore`](../endpoints/get-game-stream-processing-game_stream_id-boxscore.md)

**Auth:** `gc-token` required

**Input:** `id` from each game record in step 1 (this IS the `game_stream_id` -- no bridge call needed)

**Output:** Per-player batting and pitching lines for both teams. Key points:
- Top-level keys are team identifiers: one `public_id` slug (no dashes), one UUID (with dashes). Detect via regex.
- `players[]` array per team: `{id, first_name, last_name, number}` -- player identity lives here, not in stat entries.
- `groups[category="lineup"]`: batting stats per player (`AB`, `R`, `H`, `RBI`, `BB`, `SO` main; sparse extras `2B`, `3B`, `HR`, `TB`, `HBP`, `SB`, `CS`, `E`).
- `groups[category="pitching"]`: pitching stats per player (`IP`, `H`, `R`, `ER`, `BB`, `SO` main; sparse extras `WP`, `HBP`, `#P`, `TS`, `BF`).
- `IP` is a float in decimal innings (e.g., `3.3333...` = 3⅓ IP). Convert to integer outs: `round(float(IP) * 3)`.
- `stats[]` array: per-player entries ordered by batting order (lineup group). `is_primary: false` = substitute (lineup group only).
- `extra[]` array: sparse non-zero extras -- only players with non-zero values are listed.
- Cross-reference: match `stats[].player_id` with `players[].id` for player names (do not use boxscore's `players[]` in isolation -- use roster from step 2 as primary).

**Edge cases:**
- Asymmetric key detection: if key contains dashes → UUID (opponent); if no dashes → `public_id` slug (scouted team). See [boxscore endpoint doc](../endpoints/get-game-stream-processing-game_stream_id-boxscore.md) for detection details.
- Both teams' stats (batting and pitching) are present in a single call. No separate call needed for the opponent.
- Player UUID from boxscore `players[].id` matches `id` in step 2 roster. Use for cross-referencing.

**API calls:** 1 per completed game (N calls total, where N = number of games in step 1)

---

### Step 4: Compute season aggregates (local, no API calls)

**Auth:** N/A

**Input:** Per-game stat rows loaded from step 3 boxscores

**Operation:** Sum counting stats across all games per player, upsert into `player_season_batting` and `player_season_pitching`.

- **Batting:** Sum `AB`, `R`, `H`, `RBI`, `BB`, `SO`, `2B`, `3B`, `HR`, `TB`, `HBP`, `SB`, `CS`, `E` (treat absent extras as 0).
- **Pitching:** Sum `ip_outs` (convert IP → outs first via `round(float(IP) * 3)`), `H`, `R`, `ER`, `BB`, `SO`, `WP`, `HBP`, `#P`, `TS`, `BF` (treat absent extras as 0).
- Compute rate stats from counting totals (AVG, OBP, ERA, WHIP) after aggregation, not from individual game values.

**API calls:** 0

---

## Total API Call Summary

| Scope | Calls | Auth |
|-------|-------|------|
| Schedule | 1 | None |
| Roster | 1 | gc-token |
| Boxscores (N games) | N | gc-token |
| Season aggregates | 0 | N/A |
| **Total per opponent** | **2 + N** | |

For a typical high school team with 20--30 completed games: **22--32 API calls per opponent**.

---

## Edge Cases and Limitations

### Opponents without `public_id`

Skip. If `opponent_links.public_id` is NULL, the scouting chain cannot proceed. The opponent must be resolved first via [opponent-resolution.md](opponent-resolution.md). About 14% of opponents require manual linking due to null `progenitor_team_id`. Do not block the overall crawl -- log the skip and continue to the next opponent.

### Boxscore asymmetric keys

The two top-level keys in the boxscore response are:
- **Scouted team's key**: `public_id` slug (alphanumeric, no dashes, e.g., `"DolZd7TTaXj5"`)
- **The other team's key**: UUID (with dashes, e.g., `"72bb77d8-REDACTED"`)

Detection algorithm:
```python
import re
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
own_key = next(k for k in boxscore if not UUID_RE.match(k))
opp_key = next(k for k in boxscore if UUID_RE.match(k))
```

When the scouted team's `public_id` slug is the key, the paired UUID key is the OTHER team's canonical UUID. Store it opportunistically (see UUID Opportunism below).

### Player UUID cross-referencing

Boxscore `stats[].player_id` = `players[].id` = step 2 roster `id`. Use this UUID as the primary join key. Do not join on name or jersey number (names can have data entry variants; jersey numbers are not unique within a team).

### UUID opportunism

Save any UUID encountered during the scouting crawl to `teams.gc_uuid` (if column is currently NULL). The scouting chain does not require UUIDs to function, but opportunistically saving them enables future authenticated-path access. Never block the crawl waiting for UUID data.

---

## Season-Stats Forbidden

`GET /teams/{team_id}/season-stats` returns **HTTP 403 Forbidden** for non-owned teams (web profile, confirmed 2026-03-12). This was tested on both Lincoln Southwest Varsity 2025 (followed as fan) and an unfollowed team -- both returned 403.

- **3 out of 3 attempts returned 403** with web profile gc-token.
- Even "follow as fan" membership does NOT grant access -- likely requires coaching staff or admin membership.
- There is one unresolved observation: the mobile profile returned HTTP 200 for an opponent's season-stats via `progenitor_team_id` (session 2026-03-09_063531, Nighthawks 14U AAA). The discrepancy between web (403) and mobile (200) has not been reproduced or explained. Do not rely on the mobile 200 until it can be confirmed as reproducible.

**This is why season aggregates are computed locally from boxscores (step 4) rather than fetched from the API.** This is actually preferable for coaching purposes: computing from boxscores gives game-by-game splits and trend data, not just season totals.

See [`GET /teams/{team_id}/season-stats`](../endpoints/get-teams-team_id-season-stats.md) for endpoint schema.

---

## Following Not Required

**Following is NOT required for any step in the public-endpoint scouting chain.**

Confirmed on an unfollowed team (`public_id: 8O8bTolVfb9A`, 2026-03-12):
- Step 1 (schedule, no auth): HTTP 200 ✓
- Step 2 (roster, gc-token): HTTP 200 ✓
- Step 3 (boxscores, gc-token): HTTP 200 ✓ (24 games, 19 players)

`POST /teams/{team_id}/follow` exists and grants "follow as fan" membership. It unlocks follow-gated endpoints (e.g., the reverse bridge `GET /teams/public/{public_id}/id`) but the scouting chain uses none of those. Auto-following opponents is intentionally excluded from the scouting pipeline.

See [`POST /teams/{team_id}/follow`](../endpoints/post-teams-team_id-follow.md).

---

## Authenticated Fallback

If the public `/games` endpoint proves insufficient (e.g., very large game history requiring pagination, or need for in-progress/upcoming games), use the authenticated game discovery path:

**Endpoint:** [`GET /teams/{team_id}/game-summaries`](../endpoints/get-teams-team_id-game-summaries.md)

**Auth:** `gc-token` required + team UUID (`progenitor_team_id` from opponent resolution)

**Advantages over public `/games`:**
- Returns in-progress and upcoming games (not just completed)
- Documented pagination via `x-next-page` header
- Returns `game_stream.id` directly (same UUID as the boxscore `game_stream_id`)

**When to use:** Only if public `/games` is insufficient. The public path is preferred for scouting because it requires no UUID and no auth for the schedule step.

**Note:** This fallback requires the opponent's `progenitor_team_id` (UUID), which may not always be available (null for ~14% of opponents).

---

## ID Relationships Summary

| ID | Source | Used in |
|----|--------|---------|
| `public_id` | `opponent_links.public_id` | Steps 1 and 2 (primary key for this chain) |
| `id` from `/public/.../games` | Step 1 response | Step 3 as `game_stream_id` (direct -- no bridge needed) |
| Player `id` from roster | Step 2 response | Step 3 cross-reference (player name lookup) |
| Boxscore UUID key | Step 3 response | Opportunistic UUID storage (`teams.gc_uuid`) |
| `resolved_team_id` | `opponent_links.resolved_team_id` | NOT required for this chain (saved opportunistically) |

---

## Verified Test Cases

| Team | `public_id` | Games | Players | Verified |
|------|------------|-------|---------|----------|
| Lincoln Southwest Varsity 2025 | `DolZd7TTaXj5` | 28 | confirmed | 2026-03-12 |
| Unfollowed team | `8O8bTolVfb9A` | 24 | 19 | 2026-03-12 |

---

## See Also

- [opponent-resolution.md](opponent-resolution.md) -- How to obtain `public_id` from the authenticated opponent registry
- [`GET /public/teams/{public_id}/games`](../endpoints/get-public-teams-public_id-games.md) -- Step 1: game schedule
- [`GET /teams/public/{public_id}/players`](../endpoints/get-teams-public-public_id-players.md) -- Step 2: player roster
- [`GET /game-stream-processing/{game_stream_id}/boxscore`](../endpoints/get-game-stream-processing-game_stream_id-boxscore.md) -- Step 3: per-game boxscore
- [`GET /teams/{team_id}/game-summaries`](../endpoints/get-teams-team_id-game-summaries.md) -- Authenticated fallback for game discovery
- [`GET /teams/{team_id}/season-stats`](../endpoints/get-teams-team_id-season-stats.md) -- NOT usable for opponents (HTTP 403)
- [`docs/gamechanger-stat-glossary.md`](../../gamechanger-stat-glossary.md) -- Authoritative stat abbreviation definitions
