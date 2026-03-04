# E-002: GameChanger Data Ingestion Pipeline

## Status
`COMPLETED`

## Overview
Build the pipeline that crawls GameChanger API endpoints, stores raw JSON responses on disk, and loads normalized records into the SQLite database. When this epic is complete, coaches will have up-to-date game and player stats for their teams -- and their opponents -- persisted in a queryable database.

## Background & Context
With API access established (E-001), the next step is actually pulling data. The pipeline has two responsibilities that must be kept separate per the project architecture:

1. **Raw crawling**: Fetch data from the GameChanger API and write unmodified JSON to the local filesystem. This is the "raw" layer. It is idempotent and can be re-run safely.
2. **Loading/normalization**: Read raw JSON files and insert/upsert normalized records into the database. This is the "processed" layer.

Keeping these separate means: if the database schema changes, we can re-process from raw without re-crawling. If the API changes, we can re-crawl without touching the schema.

Scope for this epic covers Lincoln Standing Bear High School teams (Freshman, JV, Reserve, Varsity) and the opponents they play. Legion teams are explicitly out of scope but the design should not prevent adding them later.

**Expert consultation**: No baseball-coach consultation required -- this is pure data pipeline infrastructure. Coaching stat requirements are expressed via E-003 schema, which loaders consume. No data-engineer consultation performed -- the schema is finalized (E-003 COMPLETED), and loaders are mechanical JSON-to-SQLite upserts with no complex ETL patterns. FK prerequisite handling is documented in Technical Notes.

E-001 is COMPLETED (archived 2026-03-03). E-003 is COMPLETED (archived 2026-03-04). The API spec at `docs/gamechanger-api.md` now documents 18+ confirmed endpoints including per-game box score, season stats, opponents, plays, and multiple public endpoints. All crawl stories are unblocked. Load stories have their E-003-01 dependency satisfied (schema delivered), but remain blocked on their respective crawler stories (E-002-06 needs E-002-01, E-002-07a needs E-002-03, E-002-07b needs E-002-04).

## Goals
- A crawl script that fetches team roster, schedule, and game stats for all configured teams and writes raw JSON to `data/raw/`
- A load script that reads raw JSON and upserts records into the SQLite database
- Opponent data is captured: when our team plays a game, the opponent's stats for that game are also pulled
- The pipeline is idempotent: re-running does not create duplicate records
- A manifest/log of what was crawled and when, so we know what data is fresh

## Non-Goals
- Real-time or event-driven ingestion (batch only)
- Automatic scheduling (cron) -- that's a separate story
- Any dashboard or visualization of the ingested data
- Stats computation or derived metrics -- only store what the API provides
- Legion/travel team ingestion (out of scope for this epic; designed to be extensible)

## Success Criteria
- Running `python scripts/crawl.py` for a configured season produces JSON files in `data/raw/{season}/` for every team, game, and player in scope (teams come from `config/teams.yaml`, not a CLI flag)
- Running `python scripts/load.py` after a crawl populates the database with records that match the raw JSON (verify with spot-check queries)
- Re-running both scripts produces no duplicates and no errors
- Opponent stats are present in the database for all games in the schedule
- A `data/raw/{season}/manifest.json` file records the crawl timestamp and count of records fetched per crawler

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-002-R-01 | Research: Discover game stats and player stats endpoints | DONE | None | - |
| E-002-01 | Crawl team roster and write raw JSON | DONE | None | - |
| E-002-02 | Crawl game schedule and game summaries, write raw JSON | DONE | E-002-01 | - |
| E-002-03 | Crawl game stats (box score) and write raw JSON | DONE | E-002-02 | - |
| E-002-04 | Crawl player season stats and write raw JSON | DONE | E-002-01 | - |
| E-002-05 | Crawl opponent team data for all scheduled games | DONE | E-002-01 | - |
| E-002-06 | Load raw roster JSON into database | DONE | E-002-01, E-003-01 | - |
| E-002-07a | Load raw game JSON into database | DONE | E-002-03, E-003-01 | - |
| E-002-07b | Load raw player stats JSON into database | DONE | E-002-04, E-003-01 | - |
| E-002-08 | Write crawl manifest and orchestration script | DONE | E-002-01, E-002-02, E-002-05 | - |
| E-002-09 | Wire GameLoader and SeasonStatsLoader into load.py | DONE | E-002-07a, E-002-07b, E-002-08 | dev-06 |
| E-002-10 | Add 5xx retry/backoff to get_paginated() | DONE | None | dev-07 |
| E-002-11 | Distinguish 401 from 403 in GameChangerClient | DONE | None | dev-08 |

## Technical Notes

### Confirmed API Endpoints (from docs/gamechanger-api.md)
The following endpoints are confirmed and available for crawl stories:
- `GET /me/teams` -- discover team UUIDs (not needed for crawling if config is manual)
- `GET /teams/{team_id}/schedule` -- returns event objects (schedule)
- `GET /teams/{team_id}/game-summaries` -- returns scored game summaries with opponent_id, scores, game_status. Supports pagination. **Critical**: `game_stream.id` is the key to all per-game endpoints (boxscore, plays, public details).
- `GET /teams/{team_id}/players` -- returns roster (works for opponent teams too via opponent_id)
- `GET /teams/{team_id}/season-stats` -- full per-player season batting, pitching, and fielding aggregates. Players keyed by UUID; cross-reference with `/players` for names. Defense merges pitching and fielding -- use `GP:P` and `GP:F` to determine role. (Confirmed 2026-03-04, E-002-R-01.)
- `GET /teams/{team_id}/opponents` -- opponent registry with `progenitor_team_id` (canonical UUID) and `name`. Supports pagination. `is_hidden` flag distinguishes active vs stale opponents. `progenitor_team_id` = the UUID for other `/teams/{id}` endpoints. (Confirmed 2026-03-04.)
- `GET /game-stream-processing/{game_stream_id}/boxscore` -- **per-game box score** with per-player batting and pitching lines for BOTH teams. Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`. (Confirmed 2026-03-04. UNBLOCKS E-002-03.)
- `GET /game-stream-processing/{game_stream_id}/plays` -- pitch-by-pitch play log for a completed game. (Confirmed 2026-03-04. Not in E-002 scope -- see IDEA-008.)
- `GET /teams/{team_id}/players/{player_id}/stats` -- per-game stats for a single player across all games, including spray charts. One call per player. (Confirmed 2026-03-04. Not in E-002 scope -- see IDEA-009.)
- `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` -- inning-by-inning scoring, R/H/E totals. No auth required. (Confirmed 2026-03-04. Not in E-002 scope -- see IDEA-008.)
- `GET /public/teams/{public_id}` -- team profile (name, location, record, staff). No auth required.
- `GET /public/teams/{public_id}/games` -- all completed games with scores. No auth required.
- `GET /teams/public/{public_id}/players` -- roster (inverted URL pattern, no auth).
- `GET /teams/{team_id}/public-team-profile-id` -- UUID to public_id bridge.
- `GET /events/{event_id}/best-game-stream-id` -- resolves schedule event_id to game_stream_id (alternative path vs game-summaries which has `game_stream.id` directly).

### Critical ID Mapping for Box Score Pipeline

The boxscore endpoint uses `game_stream.id` from game-summaries -- NOT `event_id`, NOT `game_stream.game_id`.

| ID source | Field | Value | Used for |
|-----------|-------|-------|----------|
| game-summaries | `event_id` | Same as `game_stream.game_id` | Schedule cross-reference, games table PK |
| game-summaries | `game_stream.id` | Different from `game_stream.game_id` | Boxscore/plays/details API calls |

**Data pipeline**: `game-summaries` -> extract `game_stream.id` -> `GET /game-stream-processing/{game_stream.id}/boxscore`.

The schedule endpoint does NOT expose `game_stream.id`. The game-summaries endpoint is the required intermediary.

Raw boxscore files are keyed by `game_stream_id` as the filename (`data/raw/{season}/teams/{team_id}/games/{game_stream_id}.json`) because that is the API lookup key. The loader (E-002-07a) maps back to `event_id` (= `game_stream.game_id`) for the `games.game_id` PK using a mapping extracted from game-summaries data.

### Boxscore Response Shape

The boxscore response is a JSON object with two top-level keys (one per team). Key formats are **asymmetric**: own team = public_id slug, opponent = UUID.

Per team:
- `players[]`: full roster context (all rostered players, not just lineup)
- `groups[]`: array of stat group objects
  - `category: "lineup"` -- batting. Main stats: AB, R, H, RBI, BB, SO. Sparse extras: 2B, 3B, HR, TB, HBP, SB, CS, E.
  - `category: "pitching"` -- pitching. Main stats: IP, H, R, ER, BB, SO. Sparse extras: WP, HBP, #P, TS, BF.
- Batting order is implicit (list position). `player_text` has position(s). `is_primary` distinguishes starters from subs.
- Pitching: `player_text` has decision (W/L/SV). Listed in order pitched.

Full schema documented at `docs/gamechanger-api.md` (GET /game-stream-processing/{game_stream_id}/boxscore).

### Opponents Endpoint Details

`GET /teams/{team_id}/opponents` returns the team's opponent registry:
- `progenitor_team_id` = canonical UUID for use with `/teams/{id}`, `/season-stats`, `/players`, etc. Present on ~86% of records; absent on manually-entered or placeholder opponents.
- `root_team_id` = local registry key (NOT usable as a team_id in other endpoints).
- `is_hidden` = true for stale/deleted/duplicate entries. Filter to `is_hidden: false` for active opponents.
- Supports pagination (x-next-page header, start_at cursor). Page size = 50.
- `pregame_data.opponent_id` in schedule == `progenitor_team_id` here (confirmed).

### Schema Table Names (from E-003-01 -- DONE)
Load stories must use the table names from the delivered `migrations/001_initial_schema.sql`:
- `seasons` -- temporal anchor (season_id TEXT PK, e.g., '2026-spring-hs')
- `players`, `team_rosters` -- for roster loading (E-002-06)
- `teams` -- team identity + crawl config (team_id TEXT PK, is_owned, is_active, last_synced)
- `games`, `player_game_batting`, `player_game_pitching` -- for game data loading (E-002-07a)
- `player_season_batting`, `player_season_pitching` -- for season stats loading (E-002-07b)

Schema conventions:
- `ip_outs` (INTEGER): innings pitched stored as total outs (1 IP = 3 outs, 6.2 IP = 20 outs)
- All GameChanger IDs stored as TEXT (UUIDs)
- FK-safe orphan handling: unknown player_ids get a stub row before stat insert
- Upsert keys: `UNIQUE(game_id, player_id)` for game stats; `UNIQUE(player_id, team_id, season_id)` for season stats
- **FK prerequisite rows**: Every loader is responsible for ensuring its own FK prerequisites exist before inserting data. Specifically: `teams` rows (upserted from config or inferred from API data) and `seasons` rows (upserted from config) must exist before inserting into `team_rosters`, `games`, `player_game_*`, or `player_season_*` tables. This keeps loaders independent and prevents FK constraint violations regardless of execution order.

### Crawler Result Interface
All crawlers return a shared `CrawlResult` dataclass (defined by E-002-01 in `src/gamechanger/crawlers/__init__.py`):
```python
@dataclass
class CrawlResult:
    files_written: int = 0
    files_skipped: int = 0
    errors: int = 0
```
The orchestrator (E-002-08) collects these to build the manifest.

### Directory Structure for Raw Data
```
data/
  raw/
    {season}/
      teams/
        {team_id}/
          roster.json
          schedule.json
          game_summaries.json
          stats.json              # team-level season stats (GET /teams/{team_id}/season-stats)
          opponents.json          # opponent registry (GET /teams/{team_id}/opponents) -- owned teams only
          games/
            {game_stream_id}.json # per-game boxscore (GET /game-stream-processing/{game_stream_id}/boxscore)
      manifest.json
```

**Note on game file naming**: Files are keyed by `game_stream_id` (the API lookup key), not `event_id`/`game_id`. The loader (E-002-07a) resolves back to the `games.game_id` PK using a mapping from game-summaries data.

### Idempotency
Each crawl target should check: does a file for this team/game/season already exist and is it less than N hours old? If yes, skip. If no (or stale), fetch and overwrite. The freshness threshold should be configurable (default: 24 hours).

### Opponent Data
When crawling a game, we know the opponent's team ID from the schedule. Crawl the opponent's public profile using the same endpoints used for our own teams. Opponent data goes in the same directory structure under their team ID.

### Config File
A `config/teams.yaml` file (committed to version control -- contains no credentials) lists the team IDs we own and want to track. Team IDs are manually populated by the operator (obtained from `/me/teams` endpoint or from the GameChanger web UI). Example:
```yaml
season: "2025"
owned_teams:
  - id: "abc123"
    name: "Lincoln Freshman"
    level: "freshman"
  - id: "def456"
    name: "Lincoln Varsity"
    level: "varsity"
```

### Relationship to E-003 (COMPLETED)
E-003 is COMPLETED and archived. The schema is delivered at `migrations/001_initial_schema.sql`. Load stories (E-002-06, E-002-07a, E-002-07b) must use the final table and column names from the delivered migration. E-003-01 dependency is satisfied for all load stories.

## Open Questions
- **RESOLVED (2026-03-04)**: Per-game box score data confirmed via `GET /game-stream-processing/{game_stream_id}/boxscore`. E-002-03 unblocked.
- **RESOLVED (2026-03-04)**: Season aggregate stats endpoint confirmed via `GET /teams/{team_id}/season-stats`. E-002-04 unblocked.
- **RESOLVED (2026-03-04)**: Play-by-play data confirmed via `GET /game-stream-processing/{game_stream_id}/plays`. Captured as IDEA-008 (not in E-002 scope).
- Does the season-stats endpoint work for opponent team UUIDs, or only for teams the authenticated user belongs to? Not yet tested. The opponents endpoint provides `progenitor_team_id` which should work, but this is unconfirmed.
- What seasons of historical data are available? (One season back? Multiple?) The per-player stats endpoint returned 80 records spanning April-July 2025 for one player -- suggests at least one full season is available.
- **IP representation in boxscore**: The boxscore returns `IP` as integer values. Are these whole innings (1 IP = 1 inning) or outs (1 IP = 1 out, matching the schema's `ip_outs` convention)? The schema stores `ip_outs` (3 outs = 1 inning). If the API returns whole innings, the loader must convert (IP * 3 = ip_outs). If the API returns fractional innings as integers representing outs, no conversion needed. Needs confirmation from a game with a partial inning.

## History
- 2026-02-28: Created as DRAFT pending E-001-03 completion
- 2026-03-01: Clarify pass -- replaced all Cloudflare D1 references with SQLite per E-009 tech stack decision. The crawl stories (E-002-01 through E-002-05) are unaffected. The load stories (E-002-06, E-002-07) now target SQLite via apply_migrations.py schema instead of D1.
- 2026-03-03: Major refinement pass based on codex spec review findings:
  - Status reset from ACTIVE to READY (no work had started).
  - Cleared stale E-001 blockers (E-001 COMPLETED 2026-03-03).
  - Added research spike E-002-R-01 to discover game stats and player stats endpoints (not yet confirmed in API spec).
  - Marked E-002-03 and E-002-04 BLOCKED on E-002-R-01.
  - Fixed dependency mismatches: E-002-02 now depends on E-002-01 (needs CrawlConfig). E-002-04 story file corrected to show E-001-03 blocker cleared. E-002-05 story file corrected to show E-001-03 blocker cleared.
  - Split E-002-07 into E-002-07a (game loader) and E-002-07b (player stats loader) -- each was an independent loader class.
  - Fixed blocking direction: E-002-04 blocks E-002-07b (not E-002-06). E-002-05 blocks E-002-08 (removed from E-002-07 blockers).
  - Updated AC field references in E-002-02 to match API spec (schedule returns event objects, not home_team_id/away_team_id directly).
  - Updated AC in E-002-03 to source game_status from game-summaries endpoint.
  - Updated table references in E-002-06 and E-002-07a/07b to note E-003-01 dependency for final names.
  - Added E-002-08 Notes clarification: scripts/load.py is in-scope for E-002-08.
  - E-002-08 dependencies trimmed: only depends on confirmed-endpoint crawlers (01, 02, 05). BLOCKED crawlers (03, 04) are not required for orchestrator MVP.
  - No baseball-coach consultation required -- this epic is pure data pipeline infrastructure. Coaching stat requirements are expressed via E-003 schema, which E-002 loaders consume.
  - No api-scout consultation performed yet for stats endpoints -- captured as E-002-R-01 research spike.
- 2026-03-04: Epic set to ACTIVE (R-01 dispatched). E-002-R-01 DONE. Season-stats endpoint confirmed: `GET /teams/{team_id}/season-stats` returns full per-player batting, pitching, and fielding season aggregates. Full schema documented in `docs/gamechanger-api.md` (Schema: season-stats). E-002-04 unblocked (BLOCKED -> TODO in epic table). E-002-03 remains BLOCKED -- no per-game box-score endpoint was captured from the team stats page traffic. Next step: user must capture traffic from a specific game's detail page to discover the per-game endpoint.
- 2026-03-04: Status audit. Fixed E-002-04 story file status from BLOCKED to TODO (epic table already said TODO but story file was stale). Updated E-002-04 Technical Approach (BLOCKED -> RESOLVED), AC-5 (finalized to team-level endpoint), and Dependencies (R-01 marked DONE).
- 2026-03-04: Major refinement pass -- API discoveries. Boxscore endpoint confirmed (`GET /game-stream-processing/{game_stream_id}/boxscore`), unblocking E-002-03 (BLOCKED -> TODO, R-01 dep removed). E-002-03 fully rewritten with confirmed endpoint details, ID mapping, response schema, accept header. E-002-05 updated with opponents endpoint as primary source for opponent discovery (`progenitor_team_id`). E-002-07a updated with confirmed boxscore response shape and field mapping notes. Technical Notes overhauled: all 18+ confirmed endpoints listed, critical ID mapping section added, boxscore response shape documented, opponents endpoint details added. Open questions updated (boxscore and plays resolved). Directory structure updated (game files keyed by `game_stream_id`, opponents.json added). New ideas captured: IDEA-008 (plays+line-scores crawling), IDEA-009 (per-player per-game stats + spray charts). E-003 dependency notes updated (E-003 COMPLETED). No expert consultation required -- this is a spec update based on confirmed API discoveries.
- 2026-03-04: Codex spec review remediation. Addressed 3 P1 blockers and 12 P2 findings:
  - **P1 fixed**: (1) E-002-04 ACs rewritten to consistently use team-level semantics (no per-player fetch language). (2) FK prerequisite gap closed -- ACs added to E-002-06 (AC-6), E-002-07a (AC-8), E-002-07b (AC-6) requiring each loader to ensure teams/seasons rows exist before FK-dependent inserts. Pattern documented in Technical Notes. (3) Shared `CrawlResult` return type added to E-002-01 (AC-7) and referenced in all other crawler stories; type documented in Technical Notes.
  - **P2 fixed**: E-002-05 dependency corrected (E-002-02 -> E-002-01, opponents endpoint is independent of game-summaries). E-002-02 AC-2 data flow corrected (E-002-03 reads game-summaries, not schedule). E-002-08 Files to Create updated (added scripts/load.py and its tests). Epic Success Criteria fixed (removed --teams all flag, corrected manifest path to {season}/manifest.json). Epic overview corrected ("loaders unblocked" -> "E-003 dependency satisfied, loaders still blocked on crawlers"). E-002-01 AC-1 constructor fixed to match Technical Approach signature. E-002-01 .gitkeep removed (directory exists). R-01 annotated with post-completion boxscore discovery note. Expert consultation note added to Background.
  - **P2 deferred/invalidated**: (1) E-002-08 sizing (crawl+load in one story) -- acceptable, both are thin orchestration wrappers of the same pattern. (2) Stale R-01 findings -- annotated rather than rewritten (historical artifact). (3) E-002-04/07b R-01 references -- informative strikethrough/context, no confusion risk. (4) Data-engineer consultation -- not performed; rationale documented (schema finalized, mechanical transforms).
  - **Endpoint gap analysis**: No undocumented endpoints referenced. Zero-appearance player assumption in E-002-04 AC-3 reworded to avoid API behavior assumptions. Documented-but-unused endpoints already captured in Technical Notes with scope notes (IDEA-008, IDEA-009).
- 2026-03-04: **EPIC COMPLETED.** All 10 stories verified DONE (1 research spike + 5 crawlers + 3 loaders + 1 orchestrator). 594 total tests passing, no regressions. Key artifacts delivered:
  - **Crawlers**: RosterCrawler, ScheduleCrawler, GameStatsCrawler, PlayerStatsCrawler, OpponentCrawler (all in `src/gamechanger/crawlers/`)
  - **Loaders**: RosterLoader, GameLoader, SeasonStatsLoader (all in `src/gamechanger/loaders/`)
  - **Orchestration**: `scripts/crawl.py` (5 crawlers, `--dry-run`, `--crawler` filter, manifest) + `scripts/load.py` (roster loader, `--dry-run`, `--loader` filter)
  - **Config**: `config/teams.yaml` (team configuration), `src/gamechanger/config.py` (CrawlConfig/TeamEntry)
  - **Shared types**: CrawlResult (`src/gamechanger/crawlers/__init__.py`), LoadResult (`src/gamechanger/loaders/__init__.py`)
  - **Client enhancement**: `get_paginated()` added to GameChangerClient for x-next-page cursor pagination
  - No documentation impact -- this is internal pipeline infrastructure with no user-facing changes to docs/admin/ or docs/coaching/.
- 2026-03-04: **Codex code review remediation.** Reverted status from COMPLETED to ACTIVE. Added 3 remediation stories based on codex review findings:
  - **E-002-09 (P1)**: Wire GameLoader and SeasonStatsLoader into `scripts/load.py` -- only roster loader was registered.
  - **E-002-10 (P1)**: Add 5xx retry/backoff to `get_paginated()` -- `get()` retries but `get_paginated()` raises immediately on 5xx.
  - **E-002-11 (P2)**: Distinguish 401 from 403 in `GameChangerClient` -- OpponentCrawler misclassifies expired token as per-opponent access denial.
  All three stories have no mutual file conflicts and can be dispatched in parallel.
- 2026-03-04: **EPIC COMPLETED (post-remediation).** All 13 stories verified DONE (1 research spike + 5 crawlers + 3 loaders + 1 orchestrator + 3 codex remediation). 615 total tests passing, no regressions. Remediation artifacts:
  - E-002-09: `scripts/load.py` now wires all 3 loaders (roster, game, season-stats) in dependency order. 14 orchestrator tests.
  - E-002-10: `get_paginated()` has 3-retry exponential backoff for 5xx, matching `get()`. 5 new client tests.
  - E-002-11: `ForbiddenError(CredentialExpiredError)` subclass splits 401 (abort) from 403 (continue). OpponentCrawler now aborts on token expiry. 9 new/updated tests.
  - No documentation impact -- internal pipeline infrastructure.
