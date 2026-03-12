# E-097: Opponent Scouting Data Pipeline

## Status
`READY`

## Overview
Build the end-to-end opponent scouting data pipeline: document the verified multi-endpoint API flow, design storage for opponent rosters and boxscores, implement the ETL crawler that executes the scouting chain, and update the context layer to reflect this new capability. With a resolved opponent's UUID, we fetch their roster (1 call), game summaries (1-2 calls), and per-game boxscores (N calls) -- then compute season aggregates from the boxscores ourselves. This gives us game-by-game splits, not just totals -- a better scouting product.

## Background & Context
On 2026-03-12, the operator walked through the complete opponent scouting chain live and verified every step works:

1. Start with a resolved opponent's `public_id` (already in `opponent_links` from E-088)
2. `GET /teams/public/{public_id}/id` -- reverse bridge to team UUID (auth required, own teams only; for opponents use `resolved_team_id` from `opponent_links` directly)
3. `GET /teams/{team_id}/players` -- player names to match UUIDs (auth required)
4. `GET /teams/{team_id}/game-summaries` -- all games with `game_stream.id` values (auth required, paginated)
5. `GET /game-stream-processing/{game_stream_id}/boxscore` -- full batting/pitching lines + player IDs for both teams (auth required)
6. Season aggregates are **computed from boxscores** (not from the API -- see "Season-Stats Forbidden" below)

Test data confirmed: Lincoln Southwest Varsity 2025 (`public_id: DolZd7TTaXj5`, UUID `d8b05a1b-1a4d-4455-b7ae-cea398c30a53`) -- 28 games on schedule, boxscores working, player roster returned.

### Season-Stats Forbidden for Non-Owned Teams (discovered 2026-03-12)

`GET /teams/{team_id}/season-stats` returns **HTTP 403 Forbidden** when called with a non-owned team's UUID (tested with Lincoln Southwest: `d8b05a1b-1a4d-4455-b7ae-cea398c30a53`, web profile). The players endpoint works fine for any team UUID, but season-stats is locked to teams you are on the coaching staff for.

**Discrepancy note**: The endpoint doc at `docs/api/endpoints/get-teams-team_id-season-stats.md` has a mobile observation note (session 063531, 2026-03-09) claiming it worked with an opponent's `progenitor_team_id`. Web profile returns Forbidden. This discrepancy is unresolved -- mobile may have different access controls, or the observation may have been against an owned team variant.

**Impact on this epic**: The pipeline does NOT use season-stats for opponents. Instead, it fetches per-game boxscores and computes season aggregates itself. This is actually more valuable for coaching -- we get game-by-game splits and trends, not just season totals.

This epic promotes IDEA-019 (Retroactive Opponent Stat Crawling) and IDEA-020 (Public Endpoint Opponent Data Ingestion).

No expert consultation required -- the user directly verified the API flow and specified the team composition (DE, api-scout, CA). All endpoints are already documented in `docs/api/endpoints/`.

## Goals
- Document the opponent scouting flow as a multi-endpoint integration guide
- Design and implement database schema for scouting crawl metadata, with fetch timestamps on scouting-crawled records
- Build the scouting crawler that fetches rosters, game summaries, and boxscores for resolved opponents
- Compute season aggregates from boxscore data (season-stats endpoint is Forbidden for non-owned teams)
- Add a `bb data scout` CLI command for operator-triggered scouting crawls
- Update the context layer to reflect the new scouting capability

## Non-Goals
- Scouting dashboard UI (future epic -- data layer first)
- Automated scheduling of scouting crawls (IDEA-012 scope)
- Crawling opponents that have NOT been resolved (null `resolved_team_id` in `opponent_links`)
- Play-by-play data for opponent games (IDEA-008 scope)
- Spray chart data for opponents (IDEA-009 scope)

## Success Criteria
- A coach can ask "what are Lincoln Southwest's batting stats this season?" and the data is in the database (aggregated from boxscores)
- Running `bb data scout` crawls rosters, game summaries, and boxscores for all resolved opponents
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

### The Scouting Chain (revised 2026-03-12)

Starting point: a resolved opponent in `opponent_links` with `resolved_team_id` (UUID) and `public_id` (slug).

| Step | Endpoint | Auth | Input | Output | API calls |
|------|----------|------|-------|--------|-----------|
| 1 | `GET /teams/{team_id}/players` | Yes | `resolved_team_id` | Player roster (names + UUIDs) | 1 |
| 2 | `GET /teams/{team_id}/game-summaries` | Yes | `resolved_team_id` | All games with `game_stream.id` values | 1-2 (paginated) |
| 3 | `GET /game-stream-processing/{game_stream_id}/boxscore` | Yes | `game_stream.id` from step 2 | Per-game batting/pitching lines for both teams | 1 per game |
| 4 | Compute season aggregates | N/A | Boxscore data from step 3 | Season batting/pitching totals per player | 0 (local) |

Total for roster + game discovery: **2-3 API calls** per opponent.
Total for full scouting crawl: **2-3 + N** calls (N = number of games, typically 20-30).

**Season-stats endpoint is NOT usable**: `GET /teams/{team_id}/season-stats` returns Forbidden for non-owned teams (web profile, verified 2026-03-12). Season aggregates must be computed from boxscores. This is actually preferable -- we get game-by-game splits and trends, not just totals.

**Alternative path for game discovery (no auth):**
`GET /public/teams/{public_id}/games` returns game schedule but with `event_id`, not `game_stream_id`. Requires an extra bridge call (`GET /events/{event_id}/best-game-stream-id`) per game. The authenticated `game-summaries` endpoint is more efficient (returns `game_stream.id` directly, paginated).

### ID Relationships
- `opponent_links.resolved_team_id` = the opponent's canonical GC team UUID (use as `team_id` in all authenticated endpoints)
- `opponent_links.public_id` = the opponent's public slug (use for public endpoints)
- `game-summaries` response: `game_stream.id` is the `game_stream_id` for boxscore/plays endpoints (NOT `game_stream.game_id`, NOT `event_id`)
- Boxscore response keys: own-team key is `public_id` slug, opponent key is UUID (asymmetric -- detect via regex)

### Schema Design Direction
- Opponent game boxscores go into the EXISTING `player_game_batting` and `player_game_pitching` tables. Games go into `games`.
- Season aggregates are **computed from boxscores**, not fetched from the API. The loader aggregates per-game lines into season totals and upserts into the existing `player_season_batting` and `player_season_pitching` tables.
- A new `scouting_runs` table tracks when each opponent was last scouted (crawl metadata, separate from `teams.last_synced` which tracks our own team crawls).
- Player name resolution via the roster endpoint feeds into the existing `players` table (upsert on `player_id`).
- Team rosters for opponents feed into the existing `team_rosters` table.

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

For scouting: pass the scouted opponent's `resolved_team_id` (UUID) as `owned_team_id` to `GameLoader`. The boxscore's `public_id` slug key will be detected as `own_key` by `_detect_team_keys()`, and both teams' stats are loaded into the shared tables. The scouting loader's ADDITIONAL responsibilities beyond GameLoader:
1. Orchestrate the crawl chain (roster → game-summaries → boxscores)
2. Track `scouting_runs` metadata (status, counts, timestamps)
3. Aggregate season stats from per-game rows in `player_game_batting`/`player_game_pitching` (query, sum counting stats, upsert into `player_season_batting`/`player_season_pitching`)

### IP Conversion Bug (pre-existing in game_loader.py)
`game_loader.py:648` has `int(raw_stats["IP"]) * 3` which truncates fractional innings (e.g., 3.333 → 3, then 3*3=9 outs instead of the correct 10). The correct conversion is `round(float(raw_stats["IP"]) * 3)`, which `season_stats_loader.py` already uses via `_ip_to_ip_outs()`. This bug affects all pitchers with partial-inning appearances in existing production data. E-097-03 must fix this as part of the scouting work since the scouting loader reuses GameLoader.

### Auto-Follow Not Required
`POST /teams/{team_id}/follow` enables "follow as fan" and unlocks follow-gated endpoints (e.g., reverse bridge). However, the E-097 scouting chain starts from `resolved_team_id` in `opponent_links` and never calls the reverse bridge. The scouting endpoints (`/teams/{team_id}/players`, `/teams/{team_id}/game-summaries`, boxscore) have been confirmed working with opponent UUIDs without following. Auto-follow is NOT a prerequisite for this epic and is intentionally excluded from the scouting chain.

### Endpoint Documentation References
- `/teams/{team_id}/players`: `docs/api/endpoints/get-teams-team_id-players.md`
- `/teams/{team_id}/game-summaries`: `docs/api/endpoints/get-teams-team_id-game-summaries.md`
- `/game-stream-processing/{game_stream_id}/boxscore`: `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`
- `/teams/{team_id}/season-stats`: `docs/api/endpoints/get-teams-team_id-season-stats.md` (NOT usable for opponents -- Forbidden; kept for reference)
- `/public/teams/{public_id}/games`: `docs/api/endpoints/get-public-teams-public_id-games.md` (alternative game discovery, no auth)
- `/events/{event_id}/best-game-stream-id`: `docs/api/endpoints/get-events-event_id-best-game-stream-id.md` (bridge for public game path)
- Existing flow doc: `docs/api/flows/opponent-resolution.md`
- Stat glossary: `docs/gamechanger-stat-glossary.md`

### Upstream Dependency: Opponent Resolution (E-088)

This pipeline assumes opponents have already been resolved (non-null `resolved_team_id` and `public_id` in `opponent_links`). The resolution is performed by the E-088 opponent resolver, which uses `GET /teams/{progenitor_team_id}` to obtain `public_id` from the team detail response. That endpoint was confirmed working with opponent UUIDs (2026-03-04, 2026-03-09). The forward bridge (`GET /teams/{team_id}/public-team-profile-id`) is NOT used by either the resolution or scouting chains -- its 403 restriction for opponents is irrelevant here.

**If resolution is constrained in the future** (e.g., `GET /teams/{progenitor_team_id}` starts requiring team association), the scouting pipeline would still work for all previously-resolved opponents. Only new opponent resolution would be affected, and that is E-088's domain, not this epic's.

### Existing Infrastructure to Reuse
- `src/gamechanger/client.py`: `GameChangerClient` with auth, retry, rate limiting, proxy support
- `src/gamechanger/crawlers/`: Existing crawler patterns (roster, schedule, game_stats, opponent, opponent_resolver)
- `src/gamechanger/loaders/`: Existing loader patterns (roster, game, season_stats)
- `migrations/006_opponent_links.sql`: The `opponent_links` table with `resolved_team_id` and `public_id`
- `src/cli/data.py`: Existing CLI commands (`bb data crawl`, `bb data load`)

## Confirmed Findings (moved from Open Questions, 2026-03-12)
- **Reverse bridge is follow-gated (CONFIRMED):** `GET /teams/public/{public_id}/id` returns 403 for non-followed teams, 200 for followed teams. Two independent controlled tests on 2026-03-12. Irrelevant to this epic — the scouting chain uses `resolved_team_id` directly, not the reverse bridge.
- **Season-stats Forbidden even with following (CONFIRMED):** `GET /teams/{team_id}/season-stats` returns 403 consistently for non-owned teams (3/3 attempts), even when following as fan. Likely requires coaching staff membership. Reinforces the boxscore-aggregation approach.

## Open Questions
- The mobile observation note on season-stats (session 063531) claims it worked with an opponent's `progenitor_team_id`. Web profile returns Forbidden. Is mobile different, or was the observation against a different team? Low priority -- the boxscore-aggregation approach is better for coaching anyway.
- **Forward bridge team-association restriction (reported 2026-03-12):** The operator reported "I can only pull the public id for teams that I follow." The forward bridge (`GET /teams/{team_id}/public-team-profile-id`) is already known to return 403 for opponent UUIDs (confirmed 2026-03-09). The E-088 resolution chain does NOT use this endpoint — it uses `GET /teams/{progenitor_team_id}` (team detail). **Needs clarification**: Does the operator's statement refer to the forward bridge (already known, no impact) or to a new restriction on `GET /teams/{progenitor_team_id}` (would impact E-088, not this epic)?

## History
- 2026-03-12: Created. Promotes IDEA-019 and IDEA-020. All endpoints verified live by the operator. Team: DE + api-scout + CA.
- 2026-03-12: Revised after live testing. (1) `season-stats` returns Forbidden for non-owned teams -- removed from scouting chain; pipeline now computes season aggregates from boxscores. (2) Added `first_fetched`/`last_checked` fetch timestamp pattern to schema design for re-fetch support.
- 2026-03-12: Operator reported "I can only pull the public id for teams that I follow." Investigated: the forward bridge (`/teams/{team_id}/public-team-profile-id`) returning 403 for opponents is already known (2026-03-09). The E-088 resolution chain and this epic's scouting chain do NOT use that endpoint. Added clarification question to Open Questions. The scouting pipeline itself (stories 01-04) is not affected -- it starts from already-resolved opponents in `opponent_links`. Impact would be upstream (E-088 resolution) if the `GET /teams/{progenitor_team_id}` endpoint also has restrictions, but that endpoint was confirmed working with opponent UUIDs on 2026-03-04/2026-03-09.
- 2026-03-12: **Team refinement** (PM, api-scout, DE, SE). Major corrections: (1) Boxscore response shape in Technical Notes completely rewritten — was `batting_lines[]`/`pitching_lines[]` (wrong), now correctly documents `players[]` + `groups[]` structure. (2) Pre-existing IP conversion bug identified in `game_loader.py:648` (`int(IP)*3` truncates fractional innings; correct: `round(float(IP)*3)`). (3) Confirmed: scouting loader should reuse `GameLoader` for boxscore parsing, not reimplement. (4) Confirmed: auto-follow NOT required for scouting chain (endpoints work without following). (5) Moved reverse bridge and season-stats follow-gating from Open Questions to Confirmed Findings. (6) AC corrections: rate stats removed from aggregation (schema stores counting stats only), season creation uses dynamic approach, home/away splits deferred. (7) Dispatch team changed: story 03 reassigned from DE to SE. (8) Story 03 Agent Hint changed to SE.
