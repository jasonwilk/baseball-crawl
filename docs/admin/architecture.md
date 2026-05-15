# Architecture

## System Overview

Baseball-crawl is a coaching analytics platform for the Lincoln Standing Bear (LSB) High School baseball program. It extracts game data from the GameChanger API, stores it in a SQLite database, and serves a web dashboard for coaching staff to review batting stats, scouting reports, and opponent analysis.

The system is designed for a small-scale deployment: 4 teams (Freshman, JV, Varsity, Reserve), roughly 12--15 players per team, and approximately 30 games per team per season. The primary users are Jason (system operator) and the LSB coaching staff (dashboard consumers).

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **FastAPI app** | Python 3.13, FastAPI 0.115, Uvicorn | Serves the web dashboard (Jinja2 templates) and a JSON health endpoint. Runs inside a Docker container on port 8000. |
| **SQLite database** | SQLite with WAL mode | Stores players, teams, rosters, games, per-game/per-season batting and pitching stats, and coaching assignments. Located at `data/app.db` (host-mounted volume). |
| **Docker Compose stack** | Docker Compose | Orchestrates three services: the FastAPI app, Traefik (reverse proxy), and cloudflared (Cloudflare Tunnel). |
| **Traefik** | Traefik v3 | Reverse proxy that routes requests by `Host` header. In development, accessible at `http://localhost:8000`. The app container is also directly accessible at `http://localhost:8001` (bypasses Traefik; useful for health checks from the devcontainer shell). Waits for the app health check before accepting traffic. |
| **Cloudflare Tunnel** | cloudflared | Exposes the stack to the internet through Cloudflare's network. Handles SSL termination and integrates with Cloudflare Zero Trust for access control. |
| **Agent ecosystem** | Claude Code agents | AI agents that manage the project: planning, coding, API exploration, domain expertise, and documentation. See [Agent Guide](agent-guide.md). |

## Data Flow

```
GameChanger Web UI
       |
       | (browser DevTools -> copy as cURL)
       v
refresh_credentials.py  -->  .env (auth tokens)
       |
       v
GameChanger API  <--  src/gamechanger/client.py (authenticated HTTP client)
       |
       | (JSON responses)
       v
src/gamechanger/  (parse & transform)
       |
       v
SQLite database (data/app.db)
       |
       | (SQL queries via src/api/db.py)
       v
FastAPI + Jinja2 templates
       |
       v
Dashboard (browser)  <--  Traefik  <--  Cloudflare Tunnel  <--  Internet
```

1. **Credential capture**: Copy a GameChanger API request as a cURL command from browser DevTools. Run `scripts/refresh_credentials.py` (or `bb creds import`) to extract auth tokens into `.env`.
2. **Data extraction**: The `src/gamechanger/client.py` module calls the GameChanger API using credentials from `.env`. All HTTP requests go through the shared session factory (`src/http/session.py`) which handles browser-like headers, rate limiting, and cookie persistence.
3. **Storage**: Parsed data is inserted into the SQLite database via SQL. Migrations are managed by `migrations/apply_migrations.py`.
4. **Serving**: The FastAPI app reads from SQLite and renders Jinja2 templates for the dashboard. The health endpoint (`GET /health`) checks database connectivity.
5. **Access**: In production, Cloudflare Tunnel routes internet traffic through Traefik to the app. Cloudflare Zero Trust Access policies control who can reach the dashboard and API.

## Directory Structure

```
baseball-crawl/
  src/
    api/              # FastAPI app: routes, templates, static files, db module
    charts/           # Chart rendering modules (spray.py -- matplotlib/numpy)
    gamechanger/      # GameChanger API client and credential parser
    http/             # Shared HTTP session factory and browser headers
    safety/           # PII scanning module
  tests/              # pytest test suite (mocked HTTP, no network calls)
  migrations/         # Numbered SQL migration files and the migration runner
  scripts/            # Utility scripts (credential refresh, seeding, backup, smoke test)
  data/
    seeds/            # Development seed SQL (committed to git)
    app.db            # Runtime SQLite database (git-ignored, host-mounted)
    backups/          # Timestamped database backups (git-ignored)
  docs/               # API specs, guides, and this admin documentation
  epics/              # Active epics and story files (project management)
  .project/           # Archive, ideas, research, templates
  .claude/            # Agent definitions, rules, skills, hooks, memory
  .githooks/          # Git hooks (PII pre-commit scan)
  .devcontainer/      # VS Code devcontainer configuration
```

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.13 | Governed by `.python-version`. All dependencies support 3.13. Version synced across `pyproject.toml`, `Dockerfile`, and `devcontainer.json`. |
| **HTTP client** | httpx 0.28 | Async-capable, supports cookie jars and custom transports. Used for all GameChanger API calls. |
| **Web framework** | FastAPI 0.115 + Uvicorn 0.34 | Lightweight async framework. Serves both JSON endpoints and server-rendered HTML via Jinja2. |
| **Database** | SQLite (WAL mode) | Simple, zero-configuration, file-based. Sufficient for the data volume (~30 games x 4 teams). WAL mode enables concurrent reads during writes. |
| **Templating** | Jinja2 3.1 | Server-side HTML rendering for the dashboard. No client-side JavaScript framework. |
| **Testing** | pytest 8.3 + pytest-asyncio | All tests mock HTTP at the transport layer. No real network calls in the test suite. |
| **Reverse proxy** | Traefik v3 | Docker-native, label-based routing. No config files needed beyond `docker-compose.yml`. |
| **Tunnel** | Cloudflare Tunnel (cloudflared) | Secure exposure without opening ports. Handles SSL and integrates with Zero Trust access policies. |
| **Container** | Docker Compose | Single `docker-compose.yml` defines all services. The app container runs migrations on startup. |

## Schema Changes

### E-228: Migration 002 -- `batter_positioning` Table

`migrations/002_batter_positioning.sql` adds the `batter_positioning` table, which stores the Tier 1 deterministic defensive-positioning recommendation per batter, per fielding position, per season, per perspective.

**Purpose**: Pre-computed engine output consumed by the positioning call sheet and player cards in the scouting report bundle. The engine (E-228-02, `src/reports/positioning.py`) refreshes this table as a pipeline step on every scout run and every standalone-report generation.

**`batter_positioning`** -- one row per (batter × fielding position × season × perspective):

| Column | Type | Notes |
|--------|------|-------|
| `player_id` | `TEXT PK` | FK to `players(player_id)` -- the opposing batter |
| `team_id` | `INTEGER PK` | FK to `teams(id)` -- the batter's team (scouted opponent) |
| `season_id` | `TEXT PK` | FK to `seasons(season_id)` -- season slug, e.g. `2026-spring-hs` |
| `perspective_team_id` | `INTEGER PK` | FK to `teams(id)` -- whose API pull produced the `spray_charts` rows that fed the engine. Part of the PK per the perspective-provenance invariant: two LSB teams scouting the same opponent produce independent rows without collision. |
| `position` | `TEXT PK` | One of `SS`, `2B`, `3B`, `LF`, `CF`, `RF`. P/C/1B are excluded (situation-driven, not spray-driven). |
| `call_state` | `TEXT NOT NULL` | This position's own call: one of `TRUE`, `LEFT`, `LEFT_SHALLOW`, `LEFT_DEEP`, `RIGHT`, `RIGHT_SHALLOW`, `RIGHT_DEEP`, `MIXED`. |
| `team_state_call` | `TEXT NOT NULL` | The batter's single team-wide call, derived from the six per-position `call_state` values (TN-4a MIXED rule). Denormalized identically onto all 6 of the batter's rows so the render path reads it directly rather than re-deriving the lattice in SQL. Never NULL. |
| `direction_shade` | `TEXT` | `left`, `center`, or `right` (NULL when `call_state='TRUE'`). Absolute field direction -- not handedness-relative. |
| `depth_shade` | `TEXT` | `in`, `normal`, or `deep` (NULL when BIP count is below the 25-BIP depth gate). |
| `bip_count` | `INTEGER NOT NULL` | Balls in play for this batter. Over-the-fence HRs have NULL coordinates and are excluded from this count. |
| `hr_count` | `INTEGER NOT NULL` | Over-the-fence HR count (tracked separately because HRs have no x/y and undercount fly-ball tendency). |
| `is_thin` | `INTEGER NOT NULL` | 1 when `bip_count` is below the thin-data gate (< 10 BIP), 0 otherwise. Thin rows still have all 6 per-position rows written -- they are never skipped. |
| `zone_concentration` | `REAL` | Fraction of the position-relevant BIP in the dominant zone (NULL when `call_state='TRUE'`). |
| `direction_deviation` | `INTEGER` | Signed ordinal step bucket on the L-R axis: 0 = on base, ±1 = slight shade, ±2 = significant shade. Negative = toward LF, positive = toward RF. NULL when `call_state='TRUE'`. |
| `depth_deviation` | `INTEGER` | Signed ordinal step bucket on the in-out axis: 0 = on base, ±1 = slight shade, ±2 = significant shade. Negative = shallower, positive = deeper. NULL when `depth_shade` is NULL. |
| `computed_at` | `TEXT NOT NULL` | UTC timestamp of the last recompute (`datetime('now')`). |

**Primary key**: 5-part `(player_id, team_id, season_id, perspective_team_id, position)`.

**Index**: `idx_batter_positioning_lookup` on `(team_id, season_id, perspective_team_id)` -- serves the report-bundle read pattern (fetch all rows for a given opponent/season/perspective, then group in application code by batter and position).

**Idempotency**: delete-then-insert within a single transaction scoped to `(team_id, season_id, perspective_team_id)`. `INSERT OR REPLACE` alone would not remove stale rows for batters who drop out of the lineup or below the minimum-BIP threshold between runs.

The migration is applied automatically on container startup. The table is populated solely by the positioning pipeline stage.

### E-196: Migration 014 -- Game Start Time and Timezone

`migrations/014_games_start_time_timezone.sql` adds two columns to the `games` table:

| Addition | Notes |
|----------|-------|
| `start_time TEXT` | ISO 8601 time-of-day string for the game start (e.g., `"17:00:00"`). Nullable; populated from GameChanger schedule data when available. |
| `timezone TEXT` | IANA timezone identifier for the game (e.g., `"America/Chicago"`). Nullable. |

**Why these columns exist:** GameChanger schedule responses include `start_time` and `timezone` fields for most games. These are stored to enable chronological ordering of same-day games (doubleheaders). Before this migration, doubleheader games were displayed in insertion order, which could differ from game time. After this migration, the schedule views sort by `(date, start_time)` so doubleheaders appear in the correct game-time sequence.

The migration is applied automatically on container startup. Existing rows receive `NULL` for both columns; values are populated on the next schedule crawl and load.

### E-195: Migration 009 -- Plays and Play Events Tables

`migrations/009_plays_play_events.sql` adds two tables for play-by-play data ingestion.

**`plays`** -- one row per plate appearance:

| Addition | Notes |
|----------|-------|
| `plays` table | Core play-by-play record. Columns: `game_id`, `play_order`, `inning`, `half`, `season_id`, `batting_team_id`, `batter_id`, `pitcher_id`, `outcome`, `pitch_count`, `is_first_pitch_strike`, `is_qab`, score and outs context columns. UNIQUE on `(game_id, play_order)`. |
| `idx_plays_game_id` index | On `plays(game_id)`. |
| `idx_plays_batter_id` index | On `plays(batter_id)`. |
| `idx_plays_pitcher_id` index | On `plays(pitcher_id)`. |
| `idx_plays_fps` partial index | On `plays(pitcher_id, is_first_pitch_strike)` WHERE `outcome NOT IN ('Hit By Pitch', 'Intentional Walk')`. Designed for the old FPS% formula; queries now use `FPS / BF` with no exclusions (matches GameChanger). The index remains valid but its WHERE filter is no longer leveraged. |

**`play_events`** -- one row per event within a plate appearance:

| Addition | Notes |
|----------|-------|
| `play_events` table | Individual pitch, baserunner, substitution, and other events. Columns: `play_id` (FK to `plays.id`), `event_order`, `event_type`, `pitch_result`, `is_first_pitch`, `raw_template`. UNIQUE on `(play_id, event_order)`. |

Populated by the plays pipeline (`bb data crawl --crawler plays` + `bb data load --loader plays`). See [operations.md](operations.md) for the full pipeline reference.

### E-167: Migration 007 -- Case-Insensitive Name+Season Year Index

`migrations/007_teams_name_index.sql` adds one index to the `teams` table:

| Addition | Notes |
|----------|-------|
| `idx_teams_name_season_year` index | On `(name COLLATE NOCASE, season_year)`. Supports the name-based lookup step in `ensure_team_row()` and the duplicate detection query in `find_duplicate_teams()`. |

The migration is applied automatically on container startup. No column additions or backfills were needed.

### E-158: Migration 006 -- Spray Chart Schema Additions

`migrations/006_spray_charts_indexes.sql` adds three columns and three indexes to the `spray_charts` table (base table defined in 001, previously unpopulated):

| Addition | Notes |
|----------|-------|
| `event_gc_id TEXT` column | GC UUID per ball-in-play event. UNIQUE index enforces idempotent ingestion. |
| `created_at_ms INTEGER` column | API's `createdAt` timestamp in Unix milliseconds. |
| `season_id TEXT` column | Season slug (e.g., `2026-spring-hs`) for per-season filtering. |
| `idx_spray_charts_event_gc_id` UNIQUE index | Enforces the `event_gc_id` uniqueness constraint used by `INSERT OR IGNORE`. |
| `idx_spray_charts_player` index | On `(player_id, team_id, season_id)`. Serves player and team chart queries. |
| `idx_spray_charts_game` index | On `game_id`. Serves game-level spray queries. |

### E-100 Fresh-Start Schema Rewrite

E-100 replaced the entire prior migration history with a single `migrations/001_initial_schema.sql`. The previous incremental migrations (001--008) are archived in `.project/archive/migrations-pre-E100/`. All DDL lives in the one file.

#### programs

An umbrella entity that groups teams under an organizational program. The seed row for Lincoln Standing Bear HS is included in the migration.

| Column | Type | Notes |
|--------|------|-------|
| `program_id` | TEXT PK | Slug, e.g. `'lsb-hs'` |
| `name` | TEXT | Display name |
| `program_type` | TEXT | One of `'hs'`, `'usssa'`, `'legion'` |
| `org_name` | TEXT | Org display name (nullable) |

#### teams

Every team in the system -- both Lincoln member teams and tracked opponent teams.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK AUTOINCREMENT | Internal identity; used for all FK references |
| `name` | TEXT | Team display name |
| `program_id` | TEXT FK | References `programs(program_id)`; nullable for opponents |
| `membership_type` | TEXT | `'member'` (operator manages in GC) or `'tracked'` (opponent/scouting) |
| `classification` | TEXT | Division: `'varsity'`, `'jv'`, `'freshman'`, `'reserve'`; USSSA age bands `'8U'`--`'14U'`; `'legion'` |
| `gc_uuid` | TEXT (unique when non-null) | Team UUID from the authenticated GC API (nullable) |
| `public_id` | TEXT (unique when non-null) | Team slug from public GC URLs (nullable) |
| `source` | TEXT | Origin of the record (default `'gamechanger'`) |
| `is_active` | INTEGER | 1 = active, 0 = inactive |
| `last_synced` | TEXT | ISO 8601 timestamp of last data sync (nullable) |
| `created_at` | TEXT | ISO 8601 timestamp when the row was created |

**INTEGER PK rationale**: `teams.id` is an internal autoincrement integer. External GC identifiers (`gc_uuid`, `public_id`) live in their own columns with partial unique indexes (enforced via `WHERE ... IS NOT NULL`), allowing multiple NULL values while preventing duplicate non-null identifiers. This separates internal database identity from external API identifiers, which may not always be available -- opponents discovered by name have neither GC identifier until an admin pastes their URL. All FK references to teams use `teams(id)`.

#### team_opponents

A junction table that records which tracked opponent teams are associated with a given member team.

| Column | Type | Notes |
|--------|------|-------|
| `our_team_id` | INTEGER FK | References `teams(id)` -- a member team |
| `opponent_team_id` | INTEGER FK | References `teams(id)` -- a tracked opponent |
| `first_seen_year` | INTEGER | Year the opponent relationship was first recorded (nullable) |

A UNIQUE constraint on `(our_team_id, opponent_team_id)` prevents duplicate links.

#### opponent_links

Tracks the resolution state for each opponent entry from the GameChanger opponents endpoint. Where `team_opponents` links fully-resolved tracked teams, `opponent_links` records the intermediate resolution state -- from a raw GC opponents entry to a resolved `teams` row.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment primary key |
| `our_team_id` | INTEGER FK | References `teams(id)` -- the member team |
| `root_team_id` | TEXT | GC internal registry key from the opponents endpoint (not a canonical UUID) |
| `opponent_name` | TEXT | Opponent name as returned by the opponents endpoint |
| `resolved_team_id` | INTEGER FK | References `teams(id)` after resolution; NULL until resolved |
| `public_id` | TEXT | GC public URL slug, once known (nullable) |
| `resolution_method` | TEXT | How the opponent was resolved, e.g. `'manual'` or `'auto'` (nullable) |
| `resolved_at` | TEXT | ISO 8601 timestamp when resolution occurred (nullable) |
| `is_hidden` | INTEGER | 1 = excluded from UI and scouting pipelines, 0 = visible |
| `created_at` | TEXT | ISO 8601 timestamp when the row was created |

A UNIQUE constraint on `(our_team_id, root_team_id)` prevents duplicate entries. The relationship to `team_opponents`: once an `opponent_links` row is resolved (`resolved_team_id` is set), the resolved team can be linked via `team_opponents` for full scouting workflow access.

## Admin Interface

### Team Management Routes (E-100)

All routes are under `/admin/` and require an active session. Team routes use INTEGER `{id}` path parameters matching `teams.id`.

| Route | Method | Description |
|-------|--------|-------------|
| `/admin/teams` | GET | Flat team list with Phase 1 add-team form |
| `/admin/teams` | POST | Phase 1 submit: resolve URL or identifier, redirect to confirm |
| `/admin/teams/confirm` | GET | Phase 2 confirm page: shows resolved team info, membership radio, program/division dropdowns |
| `/admin/teams/confirm` | POST | Phase 2 save: create team record |
| `/admin/teams/{id}/edit` | GET | Edit form: name, program, division (classification), membership type |
| `/admin/teams/{id}/edit` | POST | Save team edits |
| `/admin/teams/{id}/toggle-active` | POST | Toggle `is_active` between 0 and 1 |
| `/admin/opponents/{link_id}/resolve` | GET/POST | Unified "Find on GameChanger" page -- search by name or paste URL to link an opponent; triggers auto-scout on confirm |

The team list is a flat table showing all teams (no Lincoln/Opponents split). Columns: name, program, division (classification), membership badge (member/tracked), active/inactive status, opponent count, and an edit link.

The add-team flow is two-phase: Phase 1 accepts a GameChanger team URL or bare identifier. Phase 2 shows the resolved team information and lets the operator set membership type (default: `tracked`), program, and division before saving.

Sub-navigation links Users, Teams, and Opponents pages across all admin views. The Opponents tab shows a badge with the count of opponents that need linking.

### Supporting Modules

| Module | Purpose |
|--------|---------|
| `src/gamechanger/url_parser.py` | Extracts a team identifier from a GameChanger URL, bare public_id slug, or bare UUID. Returns a `TeamIdResult` with the extracted `value` and its `id_type` (`"public_id"` or `"uuid"`). Accepts any URL containing a `/teams/{id}` segment, including mobile share links. Note: while the parser accepts bare UUIDs, the admin add-team route rejects `uuid` id_type with an error directing users to provide a URL or public_id slug instead. |
| `src/gamechanger/team_resolver.py` | Calls `GET /public/teams/{public_id}` (no auth) to resolve a team's name, location, record, and staff into a `TeamProfile` dataclass. Also provides `discover_opponents()` which calls `GET /public/teams/{public_id}/games` and returns a deduplicated list of `DiscoveredOpponent` instances by name. |

`team_resolver.py` uses the shared HTTP session factory (`src/http/session.py`) with a 10-second timeout. No authentication headers are sent -- these are public GameChanger API endpoints. `url_parser.py` is a pure string parser (imports only `re`, `dataclasses`, and `urllib.parse`) and makes no HTTP calls.

## Defensive Positioning Engine (E-228)

The positioning engine converts `spray_charts` data into per-batter, per-fielding-position recommendations stored in `batter_positioning`. It has a deliberate two-tier split: **Tier 1 decides, Tier 2 narrates**.

### Tier 1 / Tier 2 Split

| Layer | Module | Role | Fatal? |
|-------|--------|------|--------|
| **Tier 1 (deterministic)** | `src/reports/positioning.py` | Reads `spray_charts`, applies sample gates, computes an optimal fielding point per batter per position, quantizes to a `call_state` enum key. Writes to `batter_positioning`. Always runs. | N/A -- always runs |
| **Tier 2 (optional LLM)** | `src/reports/positioning_llm.py` | Reads the Tier 1 results and writes a 1-2 sentence plain-English rationale per flagged batter. Enabled only when `OPENROUTER_API_KEY` is set. Never touches `spray_charts`. Never sees raw x/y coordinates. Never influences the Tier 1 call. | Non-fatal -- per-batter failures log WARNING and are swallowed |

**Guardrail**: the call sheet is fully usable with the LLM layer disabled. Every flagged batter still shows its named state, per-position cells, and confidence column; only the rationale sentence is absent.

**Why deterministic-decides, LLM-narrates**: the threshold cutoffs (sample gates, sector geometry) are irreducible -- an LLM would only obscure them in non-reproducible prose. The engine's calls must be reproducible and auditable for a pre-game card. The LLM's role is limited to framing the call in plain English for the coach.

### Swappable Geometry Seam

The zone-assignment and per-position filtering logic is isolated behind a swappable seam interface (`assign_zone` and `bips_for_position` in `src/reports/positioning.py`):

- **v1 geometry**: fixed angular-sector zones from the `atan2` pattern already in `src/charts/spray.py`, plus a simple SVG-y threshold (`INFIELD_OUTFIELD_SVG_Y_THRESHOLD`) separating infield and outfield depth bands.
- **Future swap**: a clustering-derived zone set replaces only `assign_zone` and `POSITION_RESPONSIBILITY_SECTORS` without touching the engine's Stage C quantization or the `batter_positioning` schema.

The seam contract: the engine consumes `ZoneAssignment.zone` (a string label). The engine never reaches past the seam into the underlying geometry implementation.

### Per-Position Evaluation

Each fielding position is evaluated independently against its **responsibility sector** -- the subset of the batter's balls in play (BIP) that fall within that position's coverage area. This means:

- SS and 2B can land on different `call_state` values for the same batter.
- `team_state_call = 'MIXED'` is the result when two or more qualifying positions land in non-adjacent states on the adjacency lattice (`LEFT_DEEP` … `TRUE` … `RIGHT_DEEP`).

Positions with a `call_state` of `TRUE` (thin data or no tendency) do not by themselves force a `MIXED` team-state call.

### Stored vs. Display Vocabulary

The `batter_positioning` table stores **absolute enum keys** (`TRUE`, `LEFT`, `LEFT_SHALLOW`, etc.). The **display call-words** a coach sees on the printed card are resolved at render time from a configurable constants dict in `src/reports/renderer.py` (`POSITIONING_CALL_WORDS`). The two layers are intentionally separate:

| Stored key | Default display word |
|-----------|---------------------|
| `TRUE` | STRAIGHT UP |
| `LEFT` | SHADE LEFT |
| `LEFT_SHALLOW` | SHADE LEFT SHALLOW |
| `LEFT_DEEP` | SHADE LEFT DEEP |
| `RIGHT` | SHADE RIGHT |
| `RIGHT_SHALLOW` | SHADE RIGHT SHALLOW |
| `RIGHT_DEEP` | SHADE RIGHT DEEP |
| `MIXED` | MIXED |

To change the call-words, edit `POSITIONING_CALL_WORDS` in `src/reports/renderer.py`. The stored data does not change.

## Cross-References

- **GameChanger API**: Full endpoint documentation in [docs/api/README.md](../api/README.md) (index) and per-endpoint files in `docs/api/endpoints/`.
- **HTTP discipline**: Session factory, rate limiting, and header profile in [docs/http-integration-guide.md](../http-integration-guide.md).
- **Cloudflare setup**: Tunnel creation, Zero Trust policies, and DNS configuration in [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md).

---

*Last updated: 2026-05-15 | Source: E-228 (migration 002 batter_positioning table, Tier 1/Tier 2 positioning engine, swappable geometry seam, stored vs. display vocabulary split), E-196 (migration 014 start_time/timezone, game ordering), E-195 (migration 009 plays/play_events tables), E-173 (unified resolve route, subnav badge, discover-opponents route removed), E-167 (migration 007 name+season_year index), E-158 (src/charts/ module, migration 006 spray chart additions), E-120-06 (opponent_links table, sub-nav Opponents, url_parser correction, port 8001, teams columns), E-115-02 (schema and admin sections rewritten for E-100 fresh-start schema), E-042 (admin team management, url_parser, team_resolver), E-003-02 (original)*
