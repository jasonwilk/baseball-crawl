# Data Engineer -- Agent Memory

## Storage Architecture (E-009 Decision, 2026-02-28)

- SQLite everywhere. Local dev and production both use SQLite. No D1. No Wrangler.
- Local dev DB path: `./data/app.db` (host-mounted Docker volume)
- Production: SQLite in Docker volume with WAL mode + Litestream backup
- Dev/prod parity: `docker compose up` runs the same stack locally and in production

## Migration Tooling

- Migration runner: `apply_migrations.py` (runs at app startup, applies unapplied migrations in order)
- Migration files: `migrations/001_*.sql`, `migrations/002_*.sql`, etc.
  - Three-digit prefix, underscore, descriptive slug, `.sql` extension
- Migrations are append-only. Never edit an applied migration.
- Track applied state in a `_migrations` metadata table
- **Post-E-100-01 state (2026-03-14)**: `migrations/` contains only `001_initial_schema.sql`. Old migrations (002–006) archived to `.project/archive/migrations-pre-E100/`. Next migration: `002`.

## Schema Conventions

### ip_outs Convention
- Innings pitched stored as integer outs: 1 IP = 3 outs, 6.2 IP = 20 outs
- Always integer outs. No floating-point innings. No exceptions.
- To display: `ip_outs // 3` for full innings, `ip_outs % 3` for partial

### Referential Integrity
- FK-safe orphan handling: when a player_id is not in `players`, insert a stub row (first_name='Unknown', last_name='Unknown') before writing the stat row. Log a WARNING for operator backfill.
- Foreign keys declared and enforced (`PRAGMA foreign_keys = ON`)
- Stub rows ensure FK constraints are never violated during ingestion

### Splits
- Home/away and L/R splits stored as nullable columns in season stats tables
- Column naming: `home_obp`, `away_obp`, `vs_lhp_obp`, `vs_rhp_obp`
- Not separate rows. Null means "not enough data to split."

### Timestamps
- All `created_at` and `updated_at` columns: ISO 8601 text (e.g., `2026-03-01T14:30:00Z`)

### IDs
- GameChanger-sourced entities: `TEXT` primary keys (their IDs are opaque strings)
- Internally-generated entities: `INTEGER PRIMARY KEY` (SQLite rowid alias)

## Core Entity Model

| Entity | Purpose |
|--------|---------|
| `Team` | A team identity (LSB Varsity, opponent teams) |
| `Player` | A unique person (cross-team, cross-season identity) |
| `PlayerTeamSeason` | Junction: which player was on which team in which season |
| `Game` | A single game event (date, opponent, location, result) |
| `Lineup` | A player's position in a game lineup (batting order, fielding position) |
| `PlateAppearance` | A single plate appearance event (outcome, counts, matchup context) |
| `PitchingAppearance` | A pitcher's appearance in a game (outs recorded, runs, K, BB) |

### Key Design Decisions
- Store events (plate appearances), compute aggregates on read
- Player identity across teams is the hard problem -- `PlayerTeamSeason` junction handles it
- Opponent data is first-class: same schema structure as own-team data
- Normalize first; denormalize only for proven performance needs

## Team Detail Endpoint (confirmed 2026-03-04)

The `GET /teams/{team_id}` endpoint returns full metadata for a single team. Key schema implications beyond `/me/teams`:

- **`settings.scorekeeping.bats.innings_per_game`** (int): 7 for travel ball, likely 9 for HS varsity. Critical for stat normalization -- K/9, BB/9, and rate stats must be scaled to the correct game length. Store this per-team and use it when computing per-9 stats.
- **`settings.scorekeeping.bats.shortfielder_type`** (string): `"none"` observed. May affect fielding position mapping for younger divisions.
- **`settings.scorekeeping.bats.pitch_count_alert_1/2`** (int or null): Pitch count thresholds set by the team. Null when not configured. Could feed into arm health monitoring.
- **`settings.maxpreps`**: null for travel ball; may contain MaxPreps integration config for HS teams. Cross-reference source if non-null.
- **`organizations`** (array of `{organization_id, status}`): League/org affiliations at team level.
- **Opponent metadata use case**: Use `opponent_id` from schedule as `team_id` here to fetch opponent city, state, competition_level, record, innings_per_game. **CONFIRMED** working (2026-03-04): opponent UUID returns identical 25-field schema, `stat_access_level: confirmed_full`. Same endpoints, same schema -- no access restrictions for opponent teams. Opponent sample: `data/raw/team-detail-opponent-sample.json`.
- Same `ngb` double-JSON-parse quirk as `/me/teams`.
- Raw sample: `data/raw/team-detail-sample.json` (910 bytes, Lincoln Rebels 14U travel ball)

## /me/teams -- Team Metadata (confirmed 2026-03-04)

The `/me/teams` endpoint returns team-level metadata that maps to the `Team` entity. Key schema-relevant fields:
- `id` (UUID string) -- team identifier, used as path param for all `/teams/{id}/*` endpoints
- `name` (string) -- human-readable team name
- `season_year` (int) -- 2019-2026 observed
- `competition_level` (string) -- `"club_travel"`, `"recreational"` observed (expect `"high_school"` or similar for LSB teams)
- `archived` (boolean) -- 8 of 15 teams archived in sample
- `record` (object) -- `{wins, losses, ties}` always present, even for archived teams
- `organizations` (array of `{organization_id, status}`) -- league/org associations

Note: Current gc-token only covers travel ball teams. LSB high school teams require a separate coaching account token. See api-scout memory for details.

## Player-Stats Endpoint (confirmed 2026-03-04)

The `/teams/{team_id}/players/{player_id}/stats` endpoint returns per-game stat records for a single player. Key schema implications:

- **Response**: Bare JSON array of per-game records (80 records, 387 KB observed for one player)
- **Join key**: `event_id` matches `game_stream.game_id` from game-summaries (links player stats to games)
- **Per-game stats**: `player_stats.stats.offense` (84 batting fields), `player_stats.stats.defense` (34-129 pitching/fielding fields), `player_stats.stats.general` -- same field set as season-stats
- **Conditional sections**: `offense` absent for pitcher-only games, `defense` absent for DH-only games -- schema must handle nullable stat blocks
- **Cumulative stats**: `cumulative_stats` provides rolling season totals per game (same structure as player_stats) -- useful for trend analysis but records are NOT chronologically ordered
- **Spray charts**: `offensive_spray_charts` and `defensive_spray_charts` -- array of ball-in-play events with `playType`, `playResult`, `location.x`, `location.y`, defender `position`, `error` flag. Present on ~70% of games (offensive) and ~16% (defensive). This is a NEW data type not in any other endpoint.
- **Player-centric, not game-centric**: To reconstruct a full box score for one game, must call once per roster player (e.g., 12 API calls for 12-player roster) and filter by `event_id`
- **Schema impact**: Spray chart data needs its own table (normalized: game_id, player_id, chart_type, play_type, play_result, x, y, fielder_position, error)

## Schedule Endpoint (confirmed 2026-03-04)

The `/teams/{team_id}/schedule?fetch_place_details=true` endpoint returns the full event schedule for a team. Key schema implications:

- **Response**: Bare JSON array of schedule items; 228 events in one response (no pagination observed)
- **Event types**: `"game"` (103), `"practice"` (90), `"other"` (35) -- only games have `pregame_data`
- **Game entity mapping**: Each game event maps to the `Game` entity. `event.id` == `pregame_data.game_id` (confirmed on all 103 games). This `game_id` also matches `event_id` in game-summaries and player-stats -- universal join key.
- **`opponent_id`**: UUID in `pregame_data`, present on all 103 games. **CONFIRMED** usable as `team_id` in `/teams/{team_id}` (2026-03-04). Likely works in `/teams/{id}/season-stats`, `/teams/{id}/players` etc. -- season-stats/players not yet tested but team-detail access level (`stat_access_level: confirmed_full`) suggests they will work.
- **`home_away`**: `"home"`, `"away"`, or `null` -- maps directly to home/away split columns
- **`lineup_id`**: UUID or null (78/103 non-null) -- may link to an undiscovered lineup endpoint
- **Status filtering**: `"scheduled"` vs `"canceled"` (66 canceled) -- ETL must filter canceled games
- **Location polymorphism**: 6 distinct shapes from empty `{}` to full Google Place enrichment. Schema options: (a) flatten all fields into nullable columns, (b) store as JSON blob. Recommendation: nullable columns for lat/long/name/address (commonly queried), ignore Google Place details for now.
- **Full-day events**: When `full_day=true`, datetime format changes from `{"datetime": "ISO8601"}` to `{"date": "YYYY-MM-DD"}` and `timezone` is null. Parser must handle both formats.
- **Coordinate key inconsistency**: `{latitude, longitude}` in `location.coordinates` vs `{lat, long}` in `google_place_details.lat_long` -- normalize to one convention during ETL.
- **Date range**: 2024-11-08 to 2025-07-15 observed (full team history, not filtered to current season) -- may need season filtering.

## Public Team Profile Endpoint (confirmed 2026-03-04)

The `GET /public/teams/{public_id}` endpoint is the first confirmed **unauthenticated** endpoint. No `gc-token` or `gc-device-id` required. Key schema implications:

- **No-auth data pipeline**: If opponents have `public_id` values (available from authenticated `/teams/{team_id}` response), basic profile data (name, location, record, staff) can be fetched without credential rotation. ETL can split into auth-required vs. no-auth pipelines.
- **Different ID type**: Uses `public_id` slug (short alphanumeric string like `"a1GFM9Ku0BbF"`), NOT the internal UUID. The `id` field in the response IS the slug. Mapping between `public_id` and UUID requires the authenticated `/teams/{team_id}` response. The `Team` entity must store both `id` (UUID) and `public_id` (slug) if this endpoint is used.
- **Record key naming conflict**: Authenticated endpoint uses `record.wins`/`record.losses`/`record.ties` (plural). Public endpoint uses `team_season.record.win`/`team_season.record.loss`/`team_season.record.tie` (singular), wrapped in a `team_season` object. ETL parsers must normalize both shapes to the same schema columns.
- **Current-season only**: Public endpoint `team_season.record` is current season only, vs authenticated endpoint `record` which is cumulative all-time. If both sources are ingested, must track which represents what.
- **`staff` array**: Array of coach/manager name strings (no roles, no IDs). New data type not in any authenticated endpoint. May warrant a `team_staff` table or a JSON column on `Team` if coaching staff tracking is a requirement.
- **`avatar_url`**: Signed CloudFront URL (time-limited). Do NOT store the URL for long-term use; it will expire.
- **Missing fields vs authenticated**: No `competition_level`, `stat_access_level`, `settings`, `organizations`, `url_encoded_name`, `archived`, `created_at`. Cannot replace authenticated endpoint for full team metadata.
- Raw sample: `data/raw/public-team-profile-sample.json`

## Opponents Endpoint (confirmed 2026-03-04)

The `GET /teams/{team_id}/opponents` endpoint returns the complete opponent registry for a team. Key schema implications:

- **Response**: Bare JSON array, paginated (page size 50, cursor-based like game-summaries). 70 records across 2 pages observed.
- **5 fields per record**: `root_team_id`, `owning_team_id`, `name`, `is_hidden`, `progenitor_team_id` (optional)
- **CRITICAL ID DISTINCTION -- three UUIDs with different semantics**:
  - `root_team_id`: Local registry key internal to the opponents list. Do NOT use with other endpoints (`/teams/{id}`, `/season-stats`, etc.). Not a canonical GC team identifier.
  - `owning_team_id`: Always equals the path `team_id` (the team whose opponents these are). Informational only.
  - `progenitor_team_id`: **The canonical GameChanger team UUID.** Use THIS with `/teams/{id}`, `/season-stats`, `/players`, etc. Present on 60/70 records (86%). Missing values indicate placeholders, manual entries, or duplicates.
- **`progenitor_team_id` == `pregame_data.opponent_id`** from schedule (confirmed). Two independent paths to the same canonical opponent UUID.
- **`is_hidden` flag**: 57 visible, 13 hidden (duplicates, bad entries). ETL should filter `is_hidden=true` records by default when building the active opponent catalog.
- **Complete opponent catalog**: Provides a full list of all opponents without crawling game-by-game through schedule. For batch scouting: enumerate all `progenitor_team_id` values where `is_hidden=false`, then call `/teams/{id}/season-stats` for each.
- **Schema impact**: The `Team` entity already stores opponent teams. The opponents endpoint provides a registry view but no new fields beyond what team-detail provides. The ETL value is enumeration (discovering all opponent UUIDs in one call) rather than new entity attributes.
- Raw sample: `data/raw/opponents-sample.json` (70 records, 17 KB)

## Public Game Details Endpoint (confirmed 2026-03-04)

The `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` endpoint is the fourth confirmed **unauthenticated** endpoint. Returns a single JSON object for one game with inning-by-inning scoring. Key schema implications:

- **Same `game_stream_id` as boxscore**: URL param is `game_stream.id` from game-summaries -- the same two-step ID pipeline as the authenticated boxscore. Public details and authenticated boxscore are complementary views of the same game.
- **Line score structure**: `line_score.team.scores` = JSON array of integer runs per inning (e.g., `[2, 0, 0, 0, 0]`). `line_score.team.totals` = `[R, H, E]` (3-element array, positional). Same structure for `opponent_team`. The `line_score` field is **conditional** -- only present when `?include=line_scores` query param is set.
- **R/H/E totals as positional array**: `totals[0]` = Runs, `totals[1]` = Hits, `totals[2]` = Errors. Not a named object. Parser must use positional indexing. Consider storing as `line_runs`, `line_hits`, `line_errors` columns on the `Game` entity for quick scoreboard display.
- **Inning-by-inning runs array**: Variable length (5 innings observed in sample -- game was 5 innings). Store as JSON text column on the `Game` entity (e.g., `inning_scores_team`, `inning_scores_opponent`) since the number of innings varies per game and is rarely queried individually.
- **Complementary to authenticated boxscore**: Public details provides game-level scoring (inning-by-inning, R/H/E line, metadata). Authenticated boxscore provides per-player stats (batting/pitching lines, batting order, names). Together = complete game record. Neither alone is sufficient.
- **No-auth pipeline expansion**: Fourth no-auth endpoint. Game-level results with line scores now available without credentials. Combined with public-team-games (game list + final scores) and public-team-profile (team info), the no-auth pipeline now covers team profile + game list + per-game line scores.
- **Game metadata overlap**: `score`, `home_away`, `start_ts`/`end_ts`, `timezone`, `game_status`, `has_videos_available`, `opponent_team.name` -- all overlap with public-team-games. The unique value of this endpoint is the `line_score` field.
- Raw sample: `data/raw/public-game-details-sample.json`

## Public Team Games Endpoint (confirmed 2026-03-04)

The `GET /public/teams/{public_id}/games` endpoint is the second confirmed **unauthenticated** endpoint. Returns a bare JSON array of game records with final scores embedded. Key schema implications:

- **No-auth game results**: Final scores (`score.team`, `score.opponent_team` as integers) are directly embedded -- no join to game-summaries needed for win/loss/margin. Combined with public-team-profile, enables a full no-auth data pipeline for opponent game results.
- **Join key to authenticated data**: `id` (UUID) matches `event.id` in authenticated schedule and `event_id` in game-summaries/player-stats. Can cross-reference to enrich public data with authenticated details (opponent UUID, per-player stats, venue).
- **No `opponent_id` UUID**: Only `opponent_team.name` (string) and optional `opponent_team.avatar_url` (string, absent when no avatar -- key is missing entirely, not null). Cannot link to opponent team entities without joining through authenticated schedule via `id`.
- **`home_away`** (string: `"home"`/`"away"`): Directly embedded per game -- no join needed for home/away split analysis from public data.
- **`game_status`**: All 32 observed records are `"completed"`. Unknown whether scheduled/future games appear or what their status value would be.
- **Date fields**: `start_ts`/`end_ts` as ISO 8601 UTC with `timezone` (IANA string, e.g., `"America/New_York"`). Different from authenticated schedule's `{"datetime": "..."}` nested format -- parser must handle both shapes.
- **No pagination observed**: 32 records returned in a single response. Unknown if pagination kicks in for teams with larger game histories (80+ games).
- **Schema impact**: Game entity already handles authenticated data. Public game data is a subset (no venue, no opponent UUID, no lineup). If ingested, could populate `Game.result_score_team`, `Game.result_score_opponent` without auth. But the authenticated pipeline provides all this and more -- the primary value is zero-credential passive scouting.
- Raw sample: `data/raw/public-team-games-sample.json` (32 records, 25.7 KB, team `QTiLIb2Lui3b`)

## Boxscore Endpoint (confirmed 2026-03-04)

The `GET /game-stream-processing/{game_stream_id}/boxscore` endpoint returns per-game box scores for BOTH teams in a single call. Key schema implications:

- **Two ID pipelines to game_stream_id**: URL param is `game_stream.id` -- NOT `event_id` or `game_stream.game_id`. Two confirmed paths:
  - **Path 1 (via game-summaries)**: `game-summaries` -> extract `game_stream.id` -> boxscore/plays. Bulk path -- gets all IDs during pagination.
  - **Path 2 (via schedule + best-game-stream-id)**: `schedule` -> `event.id` -> `GET /events/{event_id}/best-game-stream-id` -> `game_stream_id` -> boxscore/plays. Per-game lookup -- extra API call but avoids game-summaries pagination when starting from an event_id.
  - The `game_stream_id` column must be stored during game-summaries ingestion. For bulk ETL, Path 1 is preferred (fewer API calls). Path 2 is useful for on-demand single-game lookups when you already have an event_id.
- **Asymmetric top-level keys**: Response is a JSON object with exactly 2 keys (one per team). Own team key = `public_id` slug format; opponent team key = UUID format. Parser must detect which is which (regex: UUID has dashes, slug does not). Own team's `public_id` is known from `/me/teams`; match against it. The other key is the opponent.
- **Player names embedded**: `players` array per team contains `id`, `first_name`, `last_name`, `number`. No join to `/players` needed. Enables lightweight player stub creation during box score ingestion (FK-safe pattern: upsert stub players before writing stat rows).
- **Two stat groups per team**: `groups` array with `category: "lineup"` (batting) and `category: "pitching"`. Main stats in `stats` array; sparse extras in `extra` array.
- **Batting main stats**: `AB`, `R`, `H`, `RBI`, `BB`, `SO` -- all int, always present per batter.
- **Pitching main stats**: `IP`, `H`, `R`, `ER`, `BB`, `SO` -- all int. **WARNING**: `IP` here is an integer (whole innings only? or formatted?). Check raw sample to determine if this is true innings or ip_outs. If integer innings, convert to ip_outs (multiply by 3) during ETL. If already outs, store directly.
- **Sparse extras pattern**: `extra` is an array of `{stat_name, stats: [{player_id, value}]}`. Only non-zero players appear. Batting extras: 2B, 3B, HR, TB, HBP, SB, CS, E. Pitching extras: WP, HBP, #P (pitch count), TS (strikes), BF (batters faced). Must iterate and merge into player stat rows.
- **Batting order**: Implicit in list ordering within `stats` array (lineup group). `is_primary: false` marks substitutes. Store batting order position as 1-indexed from array position, with a flag for substitutes.
- **Position history**: `player_text` in lineup group encodes positions played (e.g., `"(SS, P)"`, `"(2B, P, 2B)"`). In pitching group, encodes decision (`"(W)"`, `"(L)"`, `""`).
- **Team totals**: `team_stats` object per group has aggregate totals (same fields as individual stats). Useful for validation: sum of individual stats should equal team totals.
- **Opponent data is first-class**: Both teams get identical schema treatment. Opponent stats are ingested with the same pipeline as own-team stats, fulfilling the "opponent data is first-class" design principle.
- **One call per game**: No batch boxscore endpoint. For a 30-game season, this is 30 API calls. Combined with game-summaries (2 pages), total is ~32 calls per team for full box score data.
- Raw sample: `data/raw/boxscore-sample.json` (13 KB, both teams)

## Plays Endpoint (confirmed 2026-03-04)

The `GET /game-stream-processing/{game_stream_id}/plays` endpoint returns the full play-by-play log for a game. Key schema implications:

- **Same two-step ID pipeline as boxscore**: URL param is `game_stream.id` from game-summaries. Same pipeline: game-summaries -> extract `game_stream.id` -> plays.
- **Same asymmetric team key format as boxscore**: `team_players` top-level keys use public_id slug for own team and UUID for opponent. Reuse the same key-detection logic as boxscore parser.
- **PlateAppearance entity alignment**: Each element in the `plays` array is one plate appearance (or base-running event). Fields `order`, `inning`, `half`, `name_template.template` (outcome label), `outs`, `did_outs_change` map to the existing `PlateAppearance` entity concept. `home_score`/`away_score` after each play enables running score reconstruction.
- **Pitch sequence data**: `at_plate_details` is an array of template strings describing each pitch ("Ball 1", "Strike 1 looking", "Foul", "In play") plus in-at-bat events (stolen bases, balks, lineup changes, pickoff attempts, wild pitches, courtesy runners). This is NEW granular data not available in any other endpoint. Storage options: (a) JSON text column on PlateAppearance for the raw sequence, (b) normalized pitch table (pitch_number, type, result per PA). Recommendation: start with JSON text column -- pitch-level queries are low priority vs. getting the PA-level data in first.
- **Player UUID resolution via templates**: All player identities are `${uuid}` tokens in `at_plate_details[].template` and `final_details[].template`. Must regex-extract UUIDs and resolve against `team_players` dict. Same player IDs as boxscore (confirmed -- same roster dict).
- **Lineup change events embedded in pitch sequence**: `at_plate_details` includes entries like "Lineup changed: ${uuid} in at pitcher" and "Pinch runner ${uuid} in for designated hitter ${uuid}". These are inline substitution events, not separate play records.
- **Courtesy runner pattern**: "Courtesy runner ${uuid} in for ${uuid}" appears in `at_plate_details`. This is distinct from pinch runners -- courtesy runners are a specific rule variant (common in travel ball). May need a flag on the PlateAppearance or a separate event type.
- **`messages` field**: Empty array on all 58 plays in the sample. Unknown content when non-empty. Store as JSON text if non-empty; ignore if always empty.
- **Last play anomaly**: Play index 57 (the final record) has `name_template.template` = "${uuid} at bat" with empty `at_plate_details`, empty `final_details`, and scores reset to 0/0. This appears to be an incomplete/abandoned at-bat (game ended mid-PA or data artifact). Parser must handle gracefully -- skip plays with empty `final_details`.
- **One call per game** (same as boxscore): No batch endpoint. For 30 games, 30 API calls.
- Raw sample: `data/raw/game-plays-sample.json` (37 KB, 58 plays, 6-inning game)

## Players/Roster Endpoint (confirmed 2026-03-04)

The `GET /teams/{team_id}/players` (authenticated) and `GET /teams/public/{public_id}/players` (public variant) endpoints return the team roster. Key schema implications:

- **Response**: Bare JSON array of player objects (20 players observed for LSB JV). No pagination triggered (all 20 returned in a single response; `x-pagination: true` was sent but may not be needed).
- **5 fields per player**: `id` (UUID), `first_name` (string), `last_name` (string), `number` (string), `avatar_url` (string). This is a minimal schema -- same 5 fields from boxscore's `players` array.
- **`id` is the canonical player UUID**: Same UUID used in `/teams/{team_id}/players/{player_id}/stats`, in `season-stats` per-player breakdowns, and as `player_id` in boxscore stat rows. This is THE join key for the `Player` entity.
- **Player entity mapping**: Each roster record maps directly to a `Player` entity row. The roster endpoint is the authoritative source for player-to-team membership (the `PlayerTeamSeason` junction). Ingesting a roster = upsert `Player` + insert `PlayerTeamSeason`.
- **`first_name` may be initials**: LSB JV returned single-letter first names ("A", "B", "C") -- likely a data-entry pattern on this team, not an API limitation. Other teams (or the authenticated variant) may return full first names. Schema: store as-is; do not assume length. The boxscore endpoint also embeds player names and may have fuller versions for the same players.
- **Jersey `number` is a string**: Contains leading zeros or non-numeric values in some leagues. Two players share #15 in the sample -- `number` is NOT unique within a team. Do not use as a key or unique constraint.
- **`avatar_url` is empty string when unset**: NOT null, NOT absent -- the key is present with value `""`. Parser must treat empty string as "no avatar" (same semantic as null). The public-team-games endpoint has a different pattern (key absent entirely when no avatar). Normalize both to `NULL` in the schema.
- **URL pattern anomaly**: Public variant uses `/teams/public/{public_id}/players` (NOT `/public/teams/{public_id}/players`). This is the inverse of all other public endpoints. ETL code that constructs public URLs must handle both patterns.
- **Auth requirement unclear**: The public variant was captured WITH auth headers. Whether it works without auth is untested. Until confirmed, treat as potentially authenticated.
- Raw sample: `data/raw/players-roster-sample.json` (20 players, LSB JV, 2.3 KB)

## Public-Team-Profile-ID Endpoint (confirmed 2026-03-04)

The `GET /teams/{team_id}/public-team-profile-id` endpoint returns a single JSON field `{"id": "<slug>"}` -- the `public_id` slug for a team given its UUID. Auth required.

- **UUID-to-public_id bridge**: This is the missing link between the authenticated API (UUIDs everywhere) and the public API (`public_id` slugs). Before this, the only way to get a `public_id` for a team was from the authenticated `/teams/{team_id}` response -- but that endpoint returns a large 25-field object when all you need is the slug.
- **Team entity impact**: The `Team` entity must store both `id` (UUID) and `public_id` (slug). This endpoint provides a lightweight way to populate the `public_id` column for any team whose UUID is known (from schedule `opponent_id`, from opponents `progenitor_team_id`, etc.).
- **Two-tier ETL enablement**: With the bridge, the ETL pipeline can: (1) discover opponent UUIDs via authenticated endpoints (schedule, opponents), (2) call this endpoint to get each opponent's `public_id`, (3) use public endpoints (games, profile, roster, line scores) without consuming auth budget. This splits the pipeline into "auth for discovery" and "no-auth for bulk data" tiers.
- **Opponent UUID behavior unverified**: Whether this endpoint works with opponent UUIDs (from `pregame_data.opponent_id`) is the **highest priority follow-up**. If confirmed, every scheduled opponent gets a `public_id` automatically -- enabling full public API access for the entire opponent catalog.
- **Lightweight**: Single-field response (12-char alphanumeric slug). No pagination, no complex parsing.
- Raw sample: `data/raw/public-team-profile-id-sample.json` (single JSON object, ~20 bytes)

## Token Lifetime and ETL Scheduling (confirmed 2026-03-04)

- **Token lifetime is 14 days** (JWT `exp - iat = 1,209,600 seconds`). Previous assumption of ~1 hour was wrong.
- **Implication for ETL**: A single browser capture can power up to 14 days of authenticated API calls. Batch ingestion jobs (opponent scouting across 50+ teams, full season box score crawls) are feasible within a single token lifetime without credential rotation.
- **Programmatic refresh NOT possible**: The `POST /auth` endpoint requires a `gc-signature` HMAC with an unknown signing key. Token rotation still requires manual browser captures, but at ~2-week intervals rather than hourly.
- **ETL scheduling recommendation**: Plan ingestion runs as batch jobs within a token's lifetime window. A single token can support the full ingestion pipeline (opponents enumeration -> team-detail per opponent -> season-stats per opponent -> game-summaries -> boxscores -> plays) without expiring mid-run.

## ETL Patterns

- Raw-to-processed pipeline: (1) store raw API JSON blobs as audit trail, (2) parse and normalize into schema tables
- Ingestion must be idempotent: `INSERT OR IGNORE` or `INSERT ... ON CONFLICT` patterns
- Bulk-load a full game's worth of data in a single transaction
- Handle missing/null fields gracefully: log warnings, do not crash

### Pagination (confirmed 2026-03-04)
- game-summaries uses cursor-based pagination via `x-next-page` response header
- End-of-pagination signal: `x-next-page` header absent from response (do NOT check for empty body)
- Page size: 50 records max; final page may have fewer
- Full season for one team: 92 game records across 2 pages
- Working pagination loop pattern with code is in `docs/api/pagination.md`

## Project File Paths

- Migrations: `migrations/`
- Database: `./data/app.db`
- API spec (source of truth for response shapes): `docs/api/README.md` (index), `docs/api/endpoints/` (per-endpoint files)
- Stat glossary (authoritative stat abbreviation definitions): `docs/gamechanger-stat-glossary.md`
  - Includes API field name mapping table (UI abbreviation -> API field name) -- critical for mapping season-stats API fields to schema columns
  - Covers: batting (standard + advanced), pitching (standard + advanced), pitch types, fielding, catcher, positional innings
- Source code: `src/`
- Tests: `tests/`
