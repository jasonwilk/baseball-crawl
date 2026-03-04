# E-002: GameChanger Data Ingestion Pipeline

## Status
`ACTIVE`

## Overview
Build the pipeline that crawls GameChanger API endpoints, stores raw JSON responses on disk, and loads normalized records into the SQLite database. When this epic is complete, coaches will have up-to-date game and player stats for their teams -- and their opponents -- persisted in a queryable database.

## Background & Context
With API access established (E-001), the next step is actually pulling data. The pipeline has two responsibilities that must be kept separate per the project architecture:

1. **Raw crawling**: Fetch data from the GameChanger API and write unmodified JSON to the local filesystem. This is the "raw" layer. It is idempotent and can be re-run safely.
2. **Loading/normalization**: Read raw JSON files and insert/upsert normalized records into the database. This is the "processed" layer.

Keeping these separate means: if the database schema changes, we can re-process from raw without re-crawling. If the API changes, we can re-crawl without touching the schema.

Scope for this epic covers Lincoln Standing Bear High School teams (Freshman, JV, Reserve, Varsity) and the opponents they play. Legion teams are explicitly out of scope but the design should not prevent adding them later.

E-001 is COMPLETED (all stories DONE, archived 2026-03-03). The API spec at `docs/gamechanger-api.md` documents five confirmed endpoints. However, no per-player stats or team-level season stats endpoint has been discovered -- stories E-002-03 and E-002-04 are BLOCKED pending api-scout research (see E-002-R-01).

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
- Running `python scripts/crawl.py --teams all` for a configured season produces JSON files in `data/raw/` for every team, game, and player in scope
- Running `python scripts/load.py` after a crawl populates the database with records that match the raw JSON (verify with spot-check queries)
- Re-running both scripts produces no duplicates and no errors
- Opponent stats are present in the database for all games in the schedule
- A `data/raw/manifest.json` file records the crawl timestamp and count of records fetched per endpoint

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-002-R-01 | Research: Discover game stats and player stats endpoints | DONE | None | - |
| E-002-01 | Crawl team roster and write raw JSON | TODO | None | - |
| E-002-02 | Crawl game schedule and game summaries, write raw JSON | TODO | E-002-01 | - |
| E-002-03 | Crawl game stats (box score) and write raw JSON | BLOCKED | E-002-02, E-002-R-01 | - |
| E-002-04 | Crawl player season stats and write raw JSON | TODO | E-002-01, E-002-R-01 | - |
| E-002-05 | Crawl opponent team data for all scheduled games | TODO | E-002-02 | - |
| E-002-06 | Load raw roster JSON into database | TODO | E-002-01, E-003-01 | - |
| E-002-07a | Load raw game JSON into database | BLOCKED | E-002-03, E-003-01 | - |
| E-002-07b | Load raw player stats JSON into database | BLOCKED | E-002-04, E-003-01 | - |
| E-002-08 | Write crawl manifest and orchestration script | TODO | E-002-01, E-002-02, E-002-05 | - |

## Technical Notes

### Confirmed API Endpoints (from docs/gamechanger-api.md)
The following endpoints are confirmed and available for crawl stories:
- `GET /me/teams` -- discover team UUIDs (not needed for crawling if config is manual)
- `GET /teams/{team_id}/schedule` -- returns event objects (schedule)
- `GET /teams/{team_id}/game-summaries` -- returns scored game summaries with opponent_id, scores, game_status. Supports pagination.
- `GET /teams/{team_id}/players` -- returns roster (works for opponent teams too via opponent_id)

**Confirmed 2026-03-04 (E-002-R-01 DONE)**: `GET /teams/{team_id}/season-stats` returns full per-player season batting, pitching, and fielding aggregates. Players are keyed by UUID; cross-reference with `/players` for names. Defense merges pitching and fielding -- use `GP:P` and `GP:F` to determine role. Full schema in `docs/gamechanger-api.md`.

**NOT yet confirmed**: No per-game box score endpoint. The game-summaries endpoint returns game-level scores and metadata but NOT per-player batting/pitching lines. Story E-002-03 remains BLOCKED. To discover the box-score endpoint, user must capture traffic from a specific completed game's detail page on `web.gc.com`.

### Schema Table Names (from E-003-01)
Load stories must use the table names defined in E-003-01:
- `players`, `team_rosters` -- for roster loading (E-002-06)
- `games`, `player_game_batting`, `player_game_pitching` -- for game data loading (E-002-07a)
- `player_season_batting`, `player_season_pitching` -- for season stats loading (E-002-07b)

Note: E-002-06 and E-002-07a/07b are blocked on E-003-01 being DONE. When E-003-01 completes, load stories must use the final table and column names from the delivered migration, not names assumed in the story files.

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
          stats.json              # (pending E-002-R-01 -- may not exist if no stats endpoint)
          games/
            {game_id}.json       # (pending E-002-R-01 -- may not exist if no box score endpoint)
      manifest.json
```

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

### Relationship to E-003
Load stories (E-002-06, E-002-07a, E-002-07b) depend on the database schema being established in E-003-01. The crawl stories (E-002-01 through E-002-05) can proceed independently of E-003.

## Open Questions
- **CRITICAL**: Does GameChanger expose per-game box score data (per-player batting/pitching lines)? The game-summaries endpoint returns scores and game_status but NOT player stats. A separate endpoint (e.g., `/games/{game_id}/stats` or similar) may exist but has not been captured yet. To discover it, user must capture browser traffic from a specific completed game's detail page. (E-002-R-01 did not resolve this -- only team season stats were captured.)
- **RESOLVED (2026-03-04)**: Season aggregate stats endpoint confirmed. `GET /teams/{team_id}/season-stats` returns full per-player batting, pitching, and fielding season aggregates. E-002-04 unblocked.
- Does the season-stats endpoint work for opponent team UUIDs, or only for teams the authenticated user belongs to? Not yet tested.
- What seasons of historical data are available? (One season back? Multiple?)
- Does GameChanger provide play-by-play data, or only aggregate game stats?

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
