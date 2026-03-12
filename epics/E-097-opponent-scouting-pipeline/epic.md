# E-097: Opponent Scouting Data Pipeline

## Status
`READY`

## Overview
Build the end-to-end opponent scouting data pipeline: document the verified multi-endpoint API flow, design storage for opponent rosters and boxscores, implement the ETL crawler that executes the scouting chain, and update the context layer to reflect this new capability. Using only an opponent's `public_id`, we fetch their game schedule (1 unauthenticated call), player roster (1 call), and per-game boxscores (N calls) -- then compute season aggregates from the boxscores ourselves. The entire chain works via public endpoints without needing the team's private UUID or following the team. This gives us game-by-game splits, not just totals -- a better scouting product.

## Background & Context
On 2026-03-12, the operator verified the complete opponent scouting chain works via **public endpoints** -- no team UUID required, no following required. Tested on unfollowed team `8O8bTolVfb9A`:

1. Start with an opponent's `public_id` (already in `opponent_links` from E-088)
2. `GET /public/teams/{public_id}/games` -- game schedule with `id` values that ARE the `game_stream_id` for boxscores (NO auth required)
3. `GET /teams/public/{public_id}/players` -- player names, UUIDs, and numbers (gc-token required, no following)
4. `GET /game-stream-processing/{game_id}/boxscore` -- full batting/pitching lines + player IDs for both teams (gc-token required, no following)
5. Season aggregates are **computed from boxscores** (not from the API -- see "Season-Stats Forbidden" below)

**Key simplification**: The public `/games` endpoint returns an `id` field that works directly as `game_stream_id` for boxscores. No need for the authenticated `game-summaries` endpoint or the `best-game-stream-id` bridge call. The schedule step requires NO authentication at all.

Test data confirmed on two teams: Lincoln Southwest Varsity 2025 (`public_id: DolZd7TTaXj5`, UUID `d8b05a1b-1a4d-4455-b7ae-cea398c30a53`) -- 28 games; and unfollowed team `8O8bTolVfb9A` -- 24 games, full boxscores, 19 players on roster.

### Season-Stats Forbidden for Non-Owned Teams (discovered 2026-03-12)

`GET /teams/{team_id}/season-stats` returns **HTTP 403 Forbidden** when called with a non-owned team's UUID (tested with Lincoln Southwest: `d8b05a1b-1a4d-4455-b7ae-cea398c30a53`, web profile). The players endpoint works fine for any team UUID, but season-stats is locked to teams you are on the coaching staff for.

**Discrepancy note**: The endpoint doc at `docs/api/endpoints/get-teams-team_id-season-stats.md` has a mobile observation note (session 063531, 2026-03-09) claiming it worked with an opponent's `progenitor_team_id`. Web profile returns Forbidden. This discrepancy is unresolved -- mobile may have different access controls, or the observation may have been against an owned team variant.

**Impact on this epic**: The pipeline does NOT use season-stats for opponents. Instead, it fetches per-game boxscores and computes season aggregates itself. This is actually more valuable for coaching -- we get game-by-game splits and trends, not just season totals.

This epic promotes IDEA-019 (Retroactive Opponent Stat Crawling) and IDEA-020 (Public Endpoint Opponent Data Ingestion).

No expert consultation required -- the user directly verified the API flow and specified the team composition (DE, api-scout, CA). All endpoints are already documented in `docs/api/endpoints/`.

## Goals
- Document the opponent scouting flow as a multi-endpoint integration guide
- Design and implement database schema for scouting crawl metadata, with fetch timestamps on scouting-crawled records
- Build the scouting crawler that fetches schedules, rosters, and boxscores for opponents via public endpoints
- Compute season aggregates from boxscore data (season-stats endpoint is Forbidden for non-owned teams)
- Add a `bb data scout` CLI command for operator-triggered scouting crawls
- Update the context layer to reflect the new scouting capability

## Non-Goals
- Scouting dashboard UI (future epic -- data layer first)
- Automated scheduling of scouting crawls (IDEA-012 scope)
- Crawling opponents that have no `public_id` in `opponent_links`
- Play-by-play data for opponent games (IDEA-008 scope)
- Spray chart data for opponents (IDEA-009 scope)

## Success Criteria
- A coach can ask "what are Lincoln Southwest's batting stats this season?" and the data is in the database (aggregated from boxscores)
- Running `bb data scout` crawls schedules, rosters, and boxscores for all opponents with a `public_id`
- The scouting flow is documented as an API integration guide alongside `opponent-resolution.md`
- CLAUDE.md and relevant context-layer files reflect the new scouting pipeline capability

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-097-01 | Document Opponent Scouting Flow | TODO | None | - |
| E-097-02 | Opponent Scouting Schema Migration | TODO | None | - |
| E-097-03 | Opponent Scouting Crawler | TODO | E-097-02 | - |
| E-097-04 | Context-Layer Updates for Scouting Pipeline | TODO | E-097-01, E-097-03 | - |

## Dispatch Team
- api-scout (story 01: flow documentation)
- data-engineer (story 02: schema migration)
- software-engineer (story 03: scouting crawler + loader + CLI)
- claude-architect (story 04: context-layer updates)

## Technical Notes

### The Scouting Chain (revised 2026-03-12, public-endpoint discovery)

Starting point: an opponent in `opponent_links` with `public_id` (slug). The `resolved_team_id` (UUID) is NOT required -- it is saved opportunistically when encountered.

| Step | Endpoint | Auth | Input | Output | API calls |
|------|----------|------|-------|--------|-----------|
| 1 | `GET /public/teams/{public_id}/games` | None | `public_id` | Completed games with `id` (= game_stream_id), scores, opponents | 1 |
| 2 | `GET /teams/public/{public_id}/players` | gc-token | `public_id` | Player roster (names + UUIDs + numbers) | 1 |
| 3 | `GET /game-stream-processing/{game_id}/boxscore` | gc-token | `id` from step 1 | Per-game batting/pitching lines for both teams | 1 per game |
| 4 | Compute season aggregates | N/A | Boxscore data from step 3 | Season batting/pitching totals per player | 0 (local) |

Total for schedule + roster: **1 unauthenticated + 1 authenticated = 2 calls** per opponent.
Total for full scouting crawl: **2 + N** calls (N = number of completed games, typically 20-30).

**Key simplifications vs. authenticated path**:
- No pagination needed (public `/games` returns all completed games in one call)
- Schedule step requires NO auth at all
- `id` field from public games IS the `game_stream_id` for boxscores -- no bridge call needed
- No following required for any step (confirmed on unfollowed team 2026-03-12)

**Season-stats endpoint is NOT usable**: `GET /teams/{team_id}/season-stats` returns Forbidden for non-owned teams (web profile, verified 2026-03-12). Season aggregates must be computed from boxscores. This is actually preferable -- we get game-by-game splits and trends, not just totals.

**Authenticated fallback (game-summaries)**: The authenticated `GET /teams/{team_id}/game-summaries` endpoint exists as an alternative for game discovery. It returns in-progress and upcoming games (not just completed), has documented pagination via `x-next-page`, and returns `game_stream.id` directly. Use this path only if the public `/games` endpoint proves insufficient (e.g., need upcoming games, or pagination is needed for teams with very large game histories). The public path is preferred for scouting.

**Inverted URL pattern warning**: The public players endpoint uses `/teams/public/{public_id}/players` (NOT `/public/teams/`), while the public games endpoint uses `/public/teams/{public_id}/games`. Both path structures coexist in the GC API. The scouting chain uses both patterns.

**Public games limitation**: The `/public/teams/{public_id}/games` endpoint returns only `game_status: "completed"` games. For scouting (stats from completed games), this is exactly what we want. If future use cases need upcoming/in-progress games, use the authenticated `game-summaries` path.

### ID Relationships
- `opponent_links.public_id` = the opponent's public slug -- **primary key for the scouting chain** (used in steps 1 and 2)
- `opponent_links.resolved_team_id` = the opponent's canonical GC team UUID -- **opportunistic**, saved when encountered but never required for scouting
- Public `/games` response: `id` field IS the `game_stream_id` for boxscore/plays endpoints (confirmed 2026-03-12 -- no bridge call needed)
- Boxscore response keys: own-team key is `public_id` slug, opponent key is UUID (asymmetric -- detect via regex)
- `teams.gc_uuid` = nullable column for storing UUIDs discovered opportunistically (e.g., from boxscore response keys)

### Schema Design Direction
- Opponent game boxscores go into the EXISTING `player_game_batting` and `player_game_pitching` tables. Games go into `games`.
- Season aggregates are **computed from boxscores**, not fetched from the API. The loader aggregates per-game lines into season totals and upserts into the existing `player_season_batting` and `player_season_pitching` tables.
- A new `scouting_runs` table (migration 007) tracks when each opponent was last scouted (crawl metadata, separate from `teams.last_synced` which tracks our own team crawls).
- A new `gc_uuid` nullable TEXT column on the `teams` table (migration 008) stores UUIDs discovered opportunistically from boxscore response keys. Partial unique index ensures no duplicates. This avoids a PK migration (9+ FK tables would need cascading updates if `teams.team_id` changed).
- Player name resolution via the roster endpoint feeds into the existing `players` table (upsert on `player_id`).
- Team rosters for opponents feed into the existing `team_rosters` table.

### UUID Opportunism (user directive)
"Save the private UUID any time we see it." The scouting pipeline does NOT require UUIDs, but whenever one is encountered (boxscore response keys, opponent_links.resolved_team_id, progenitor_team_id chains), it is saved to `teams.gc_uuid`. This is a write-through pattern: check if `gc_uuid` is NULL for the team, and if so, UPDATE it. Never block the scouting flow on a missing UUID.

### Fetch Timestamps (re-fetch support)
Every record crawled by the scouting pipeline carries two timestamps:
- **`first_fetched`** (TEXT, ISO 8601) -- when the record was originally crawled. Set on first insert, never updated.
- **`last_checked`** (TEXT, ISO 8601) -- when the record was last fetched from the API. Updated on every re-fetch.

The use case: sometimes we want to re-fetch an individual game (or any record) to verify nothing was updated on the GC side. `last_checked` tells us how stale our data is; comparing `first_fetched` vs `last_checked` tells us if a record has been re-verified.

**Scope for this epic**: Add `first_fetched` and `last_checked` columns to the `scouting_runs` table and to any NEW tables created by the migration. Existing tables (`games`, `players`, `player_game_batting`, etc.) will get these columns in a future migration -- this epic establishes the pattern without a broad schema migration.

### Boxscore Response Shape (corrected 2026-03-12)
The boxscore response has top-level keys that are team identifiers (one `public_id` slug, one UUID — asymmetric). Each team's data includes:
- `players[]`: roster array with `{id, first_name, last_name, number}` — player identity is HERE, not in stat entries
- `groups[]`: two group objects, one per stat category:
  - `groups[category="lineup"]`: batting stats
  - `groups[category="pitching"]`: pitching stats
- Each group contains:
  - `team_stats`: aggregate team totals (for validation)
  - `stats[]`: per-player stat lines with `{player_id, player_text, is_primary (lineup only), stats: {stat_key: value}}`
  - `extra[]`: sparse non-zero stats — `{stat_name, stats: [{player_id, value}]}` — only players with non-zero values listed

**Batting main stats** (always present per player in lineup group): AB, R, H, RBI, BB, SO
**Batting extras** (sparse): 2B, 3B, HR, TB, HBP, SB, CS, E
**Pitching main stats** (always present per player in pitching group): IP, H, R, ER, BB, SO
**Pitching extras** (sparse): WP, HBP, #P (pitch count), TS (strikes), BF (batters faced)

**IP is float decimal innings** (not integer outs): e.g., `3.3333...` = 3⅓ IP = 10 outs. Convert to `ip_outs` via `round(float(IP) * 3)`.

The existing `game_loader.py` already handles this structure correctly (see `_detect_team_keys()`, `_load_boxscore_file()`). The scouting loader should reuse `GameLoader` rather than reimplementing boxscore parsing.

### GameLoader Reuse (architectural decision)
The scouting loader MUST delegate per-game loading to the existing `GameLoader` class (`src/gamechanger/loaders/game_loader.py`) rather than reimplementing boxscore parsing, player stub creation, game record upsert, or batting/pitching line upsert. `GameLoader` already handles all of this correctly.

For scouting: use `GameLoader.load_file()` directly (not `load_all()`, which reads game_summaries.json). The internal `_GameSummaryEntry` namedtuple must be renamed to `GameSummaryEntry` and made public/importable -- E-097-03 already touches game_loader.py for the IP bug fix. Pass the scouted opponent's team_id as `owned_team_id` to `GameLoader`. The boxscore's `public_id` slug key will be detected as `own_key` by `_detect_team_keys()`, and both teams' stats are loaded into the shared tables. The scouting loader's ADDITIONAL responsibilities beyond GameLoader:
1. Orchestrate the crawl chain (schedule → roster → boxscores) via public endpoints
2. Track `scouting_runs` metadata (status, counts, timestamps)
3. Aggregate season stats from per-game rows in `player_game_batting`/`player_game_pitching` (query, sum counting stats, upsert into `player_season_batting`/`player_season_pitching`)

### IP Conversion Bug (pre-existing in game_loader.py)
`game_loader.py:648` has `int(raw_stats["IP"]) * 3` which truncates fractional innings (e.g., 3.333 → 3, then 3*3=9 outs instead of the correct 10). The correct conversion is `round(float(raw_stats["IP"]) * 3)`, which `season_stats_loader.py` already uses via `_ip_to_ip_outs()`. This bug affects all pitchers with partial-inning appearances in existing production data. E-097-03 must fix this as part of the scouting work since the scouting loader reuses GameLoader.

### Auto-Follow Not Required
Following is NOT required for any step in the public-endpoint scouting chain. Confirmed on unfollowed team `8O8bTolVfb9A` on 2026-03-12: schedule (200, no auth), roster (200, gc-token only), boxscore (200, gc-token only). `POST /teams/{team_id}/follow` enables "follow as fan" and unlocks follow-gated endpoints (e.g., reverse bridge), but the scouting chain uses none of those. Auto-follow is intentionally excluded.

### Endpoint Documentation References
- `/public/teams/{public_id}/games`: `docs/api/endpoints/get-public-teams-public_id-games.md` (PRIMARY -- schedule, no auth, `id` = game_stream_id)
- `/teams/public/{public_id}/players`: `docs/api/endpoints/get-teams-public-public_id-players.md` (roster, gc-token, inverted URL pattern)
- `/game-stream-processing/{game_stream_id}/boxscore`: `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`
- `/teams/{team_id}/game-summaries`: `docs/api/endpoints/get-teams-team_id-game-summaries.md` (authenticated fallback for game discovery)
- `/teams/{team_id}/season-stats`: `docs/api/endpoints/get-teams-team_id-season-stats.md` (NOT usable for opponents -- Forbidden; kept for reference)
- Existing flow doc: `docs/api/flows/opponent-resolution.md`
- Stat glossary: `docs/gamechanger-stat-glossary.md`

### Upstream Dependency: Opponent Resolution (E-088)

This pipeline assumes opponents have a non-null `public_id` in `opponent_links`. The `resolved_team_id` (UUID) is NOT required for scouting -- only `public_id`. The resolution is performed by the E-088 opponent resolver, which uses `GET /teams/{progenitor_team_id}` to obtain `public_id` from the team detail response. That endpoint was confirmed working with opponent UUIDs (2026-03-04, 2026-03-09).

**If resolution is constrained in the future** (e.g., `GET /teams/{progenitor_team_id}` starts requiring team association), the scouting pipeline would still work for all previously-resolved opponents. Only new opponent resolution would be affected, and that is E-088's domain, not this epic's.

### Existing Infrastructure to Reuse
- `src/gamechanger/client.py`: `GameChangerClient` with auth, retry, rate limiting, proxy support
- `src/gamechanger/crawlers/`: Existing crawler patterns (roster, schedule, game_stats, opponent, opponent_resolver)
- `src/gamechanger/loaders/`: Existing loader patterns (roster, game, season_stats)
- `migrations/006_opponent_links.sql`: The `opponent_links` table with `resolved_team_id` and `public_id`
- `src/cli/data.py`: Existing CLI commands (`bb data crawl`, `bb data load`)

## Confirmed Findings (moved from Open Questions, 2026-03-12)
- **Public-endpoint scouting chain works without following (CONFIRMED 2026-03-12):** Tested on unfollowed team `8O8bTolVfb9A`: schedule (200, no auth), roster (200, gc-token), boxscore (200, gc-token). No team UUID needed. The `public_id` alone is sufficient for the entire scouting chain.
- **Public games `id` = game_stream_id (CONFIRMED 2026-03-12):** The `id` field from `GET /public/teams/{public_id}/games` works directly as the `game_stream_id` parameter for boxscore requests. No `best-game-stream-id` bridge call needed.
- **Reverse bridge is follow-gated (CONFIRMED):** `GET /teams/public/{public_id}/id` returns 403 for non-followed teams, 200 for followed teams. Two independent controlled tests on 2026-03-12. Irrelevant to this epic — the scouting chain does not use the reverse bridge.
- **Season-stats Forbidden even with following (CONFIRMED):** `GET /teams/{team_id}/season-stats` returns 403 consistently for non-owned teams (3/3 attempts), even when following as fan. Likely requires coaching staff membership. Reinforces the boxscore-aggregation approach.

## Open Questions
- The mobile observation note on season-stats (session 063531) claims it worked with an opponent's `progenitor_team_id`. Web profile returns Forbidden. Is mobile different, or was the observation against a different team? Low priority -- the boxscore-aggregation approach is better for coaching anyway.
- **Forward bridge team-association restriction (reported 2026-03-12):** The operator reported "I can only pull the public id for teams that I follow." The forward bridge (`GET /teams/{team_id}/public-team-profile-id`) is already known to return 403 for opponent UUIDs (confirmed 2026-03-09). The E-088 resolution chain does NOT use this endpoint — it uses `GET /teams/{progenitor_team_id}` (team detail). **Needs clarification**: Does the operator's statement refer to the forward bridge (already known, no impact) or to a new restriction on `GET /teams/{progenitor_team_id}` (would impact E-088, not this epic)?

## History
- 2026-03-12: Created. Promotes IDEA-019 and IDEA-020. All endpoints verified live by the operator. Team: DE + api-scout + CA.
- 2026-03-12: Revised after live testing. (1) `season-stats` returns Forbidden for non-owned teams -- removed from scouting chain; pipeline now computes season aggregates from boxscores. (2) Added `first_fetched`/`last_checked` fetch timestamp pattern to schema design for re-fetch support.
- 2026-03-12: Operator reported "I can only pull the public id for teams that I follow." Investigated: the forward bridge (`/teams/{team_id}/public-team-profile-id`) returning 403 for opponents is already known (2026-03-09). The E-088 resolution chain and this epic's scouting chain do NOT use that endpoint. Added clarification question to Open Questions. The scouting pipeline itself (stories 01-04) is not affected -- it starts from already-resolved opponents in `opponent_links`. Impact would be upstream (E-088 resolution) if the `GET /teams/{progenitor_team_id}` endpoint also has restrictions, but that endpoint was confirmed working with opponent UUIDs on 2026-03-04/2026-03-09.
- 2026-03-12: **Team refinement** (PM, api-scout, DE, SE). Major corrections: (1) Boxscore response shape in Technical Notes completely rewritten — was `batting_lines[]`/`pitching_lines[]` (wrong), now correctly documents `players[]` + `groups[]` structure. (2) Pre-existing IP conversion bug identified in `game_loader.py:648` (`int(IP)*3` truncates fractional innings; correct: `round(float(IP)*3)`). (3) Confirmed: scouting loader should reuse `GameLoader` for boxscore parsing, not reimplement. (4) Confirmed: auto-follow NOT required for scouting chain (endpoints work without following). (5) Moved reverse bridge and season-stats follow-gating from Open Questions to Confirmed Findings. (6) AC corrections: rate stats removed from aggregation (schema stores counting stats only), season creation uses dynamic approach, home/away splits deferred. (7) Dispatch team changed: story 03 reassigned from DE to SE. (8) Story 03 Agent Hint changed to SE.
- 2026-03-12: **Codex spec review triage** (PM, DE, SE). 5 findings triaged: (1) P1-1 REFINED — AC-2 scoped to migration 007 only, AC-8 notes ALTER TABLE relies on runner single-execution (005 precedent), migrations.md updated. (2) P1-2 FIXED — AC-9 tightened to require ON CONFLICT DO UPDATE for scouting_runs (preserving first_fetched), INSERT OR REPLACE allowed on other tables. (3) P2-3 REFINED — concrete season_id derivation rule added ({year}-spring-hs from earliest game date), --season CLI override added to AC-10. (4) P2-4 DISMISSED — AC-5 removed (IDEA-019/020 already PROMOTED in PM memory, PM handles during closure). (5) P2-5 DISMISSED — story 03 kept as-is (tightly coupled vertical slice).
- 2026-03-12: **Public-endpoint discovery refinement** (PM, api-scout, DE, SE). Major rewrite of the scouting chain after discovery that the entire flow works via public endpoints without needing UUIDs or following. Changes: (1) Scouting chain table rewritten — public endpoints as primary path (`/public/teams/{public_id}/games` for schedule, `/teams/public/{public_id}/players` for roster). (2) `public_id` is now the primary scouting input; UUID is opportunistic per user directive. (3) No `game-summaries` endpoint needed — public `/games` `id` field IS the `game_stream_id` for boxscores. (4) No `best-game-stream-id` bridge call needed (previous epic text was wrong). (5) Migration 008 added: `gc_uuid` nullable column on `teams` for UUID opportunism. (6) Story 01: endpoint doc corrections folded in (boxscore caveat, public games cross-ref). (7) Story 03: major rewrite — `scout_team(public_id)` signature, `get_public()` method on GameChangerClient, `GameSummaryEntry` rename, `load_file()` usage, UUID opportunism AC. (8) New UUID Opportunism section in Technical Notes. (9) Inverted URL pattern warning added.
