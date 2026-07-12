# Architecture

## System Overview

Baseball-crawl is a coaching analytics platform for the Lincoln Standing Bear (LSB) High School baseball program. It extracts game data from the GameChanger API, stores it in a SQLite database, and generates on-demand scouting reports for coaching staff.

The system is designed for a small-scale deployment: 4 teams (Freshman, JV, Varsity, Reserve), roughly 12--15 players per team, and approximately 30 games per team per season. The primary users are Jason (system operator) and the LSB coaching staff (report consumers).

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **FastAPI app** | Python 3.13, FastAPI 0.115, Uvicorn | Serves scouting reports, admin pages (reports management, user management), and a JSON health endpoint. Runs inside a Docker container on port 8000. |
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
Standalone reports / admin pages (browser)  <--  Traefik  <--  Cloudflare Tunnel  <--  Internet
```

1. **Credential capture**: Copy a GameChanger API request as a cURL command from browser DevTools. Run `scripts/refresh_credentials.py` (or `bb creds import`) to extract auth tokens into `.env`.
2. **Data extraction**: The `src/gamechanger/client.py` module calls the GameChanger API using credentials from `.env`. All HTTP requests go through the shared session factory (`src/http/session.py`) which handles browser-like headers, rate limiting, and cookie persistence.
3. **Storage**: Parsed data is inserted into the SQLite database via SQL. Migrations are managed by `migrations/apply_migrations.py`.
4. **Serving**: The FastAPI app reads from SQLite and renders Jinja2 templates for standalone reports and admin pages. The health endpoint (`GET /health`) checks database connectivity.
5. **Access**: In production, Cloudflare Tunnel routes internet traffic through Traefik to the app. Cloudflare Zero Trust Access policies control who can reach the admin pages and API.

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
  scripts/            # Utility scripts (credential refresh, backup, smoke test, dev DB reset)
  data/
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
| **Templating** | Jinja2 3.1 | Server-side HTML rendering for reports and admin pages. No client-side JavaScript framework. |
| **Testing** | pytest 8.3 + pytest-asyncio | All tests mock HTTP at the transport layer. No real network calls in the test suite. |
| **Reverse proxy** | Traefik v3 | Docker-native, label-based routing. No config files needed beyond `docker-compose.yml`. |
| **Tunnel** | Cloudflare Tunnel (cloudflared) | Secure exposure without opening ports. Handles SSL and integrates with Zero Trust access policies. |
| **Container** | Docker Compose | Single `docker-compose.yml` defines all services. The app container runs migrations on startup. |

## Schema Changes

**Migration numbering note**: E-220-01 squashed every prior migration into a single new `migrations/001_initial_schema.sql` (see "E-100 Fresh-Start Schema Rewrite" below for the earlier squash it superseded). The `Migration 014`/`009`/`007`/`006` entries below predate that rewrite -- those specific files no longer exist standalone; the columns/tables they describe now live in `001_initial_schema.sql`. Current standalone migrations `002`-`010` postdate the E-220 squash and reuse some of the same numbers for unrelated changes (today's `006` is `drop_season_fallback.sql`, `007` is `play_events_pitch_columns.sql`, `009` is `spray_chart_type_unique.sql` -- see [operations.md: Schema Migrations](operations.md#schema-migrations) for the current file-by-file list). The entries below are accurate as history; only the migration *number* no longer maps to a live file for the pre-E-220 entries.

### E-235: Migration 002 -- Report Generation Run Records

`migrations/002_report_generation_runs.sql` adds a single wide telemetry table:

**Table: `report_generation_runs`** (one row per standalone report generation, FK 1:1 to `reports(id)`)

| Column group | Columns | Notes |
|-------------|---------|-------|
| Identity / lifecycle | `id`, `report_id`, `started_at`, `completed_at`, `overall_status` | `ON DELETE CASCADE` — deleting a report removes its run row. `overall_status`: `running` → `completed` or `failed`. |
| Per-stage status | `crawl_status`, `load_status`, `gc_uuid_status`, `spray_status`, `plays_status`, `reconciliation_status`, `enrichment_status` | NULL means the stage did not run. `enrichment_status` is constrained to `success`, `unavailable-no-key`, `failed` (canonical Tier-2 vocabulary from E-233). |
| Per-stage counts | `completed_games` (M), `completed_games_with_data` (N), `spray_games`, `plays_games_expected`, `plays_games_covered`, `discrepancies_found`, `discrepancies_corrected` | N ≤ M: M counts scored games on the schedule; N counts games with actual player stat rows loaded — a game with a public final score but no GC scorebook contributes to M but not N. N is the data-bearing coverage value used by the report footer's "N of M games" line. |
| Trust flags | `season_id_used`, `identity_match_method` | `identity_match_method`: `anchor` (matched by gc_uuid/public_id) or `name_only` (name+season only, lower trust). |
| Failure | `error_stage`, `error_message` | Stage name and message on pipeline failure. |

A UNIQUE index on `report_id` enforces the 1:1 relationship and serves as the admin-list join index.

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

Populated by the plays pipeline, which is alive -- every report generation runs it (parser in `src/gamechanger/parsers/plays_parser.py`, loader in `src/gamechanger/loaders/plays_loader.py`). E-239 removed the dashboard/member-sync surfaces, not this pipeline; E-245 later repaired its pitch-annotation handling in place (see [operations.md: Schema Migrations](operations.md#schema-migrations), migration 007).

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
| `season_id TEXT` column | Season identifier (e.g., `2026`) for per-season filtering. |
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
| `program_type` | TEXT | One of `'hs'`, `'usssa'`, `'legion'`. Selects the pitch-count rule set for the program. |
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

#### opponent_links

Tracks the resolution state for each opponent entry from the GameChanger opponents endpoint. `opponent_links` records the intermediate resolution state -- from a raw GC opponents entry to a resolved `teams` row. (The `team_opponents` junction table that formerly linked fully-resolved tracked teams was dropped in migration 008 (E-250) -- it served the tracked-opponent flow removed in E-239 and had no remaining reader.)

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

A UNIQUE constraint on `(our_team_id, root_team_id)` prevents duplicate entries. `opponent_links` is the morning-of-game scheduler's resolution ladder (E-240); it no longer feeds a downstream `team_opponents` link now that the tracked-opponent flow is removed.

## Admin Interface

### Admin Routes (E-239)

All routes are under `/admin/` and require an active session. Defined in `src/api/routes/reports_admin.py`.

| Route | Method | Description |
|-------|--------|-------------|
| `/admin/reports` | GET | Reports list: all generated reports with status, expiry, and per-stage pipeline detail |
| `/admin/reports/generate` | POST | Generate a new report from a GameChanger public URL or public ID slug |
| `/admin/reports/{report_id}/delete` | POST | Delete a report (full cascade or report-only depending on guard conditions) |
| `/admin/users` | GET | User list |
| `/admin/users` | POST | Add a new user |
| `/admin/users/{user_id}/edit` | GET | Edit user form |
| `/admin/users/{user_id}/edit` | POST | Save user edits (name, role) |
| `/admin/users/{user_id}/delete` | POST | Delete a user |

Sub-navigation links the Reports and Users pages across all admin views.

### Supporting Modules

| Module | Purpose |
|--------|---------|
| `src/gamechanger/url_parser.py` | Extracts a team identifier from a GameChanger URL, bare public_id slug, or bare UUID. Returns a `TeamIdResult` with the extracted `value` and its `id_type` (`"public_id"` or `"uuid"`). Accepts any URL containing a `/teams/{id}` segment, including mobile share links. Used by the report generation route to parse the operator-supplied GameChanger URL before calling the reports pipeline. |
| `src/gamechanger/team_resolver.py` | Calls `GET /public/teams/{public_id}` (no auth) to resolve a team's name, location, record, and staff into a `TeamProfile` dataclass. Used by the reports pipeline (`src/reports/generator.py`) to look up team metadata during report generation. |

`team_resolver.py` uses the shared HTTP session factory (`src/http/session.py`) with a 10-second timeout. No authentication headers are sent -- these are public GameChanger API endpoints. `url_parser.py` is a pure string parser (imports only `re`, `dataclasses`, and `urllib.parse`) and makes no HTTP calls.

## Cross-References

- **GameChanger API**: Full endpoint documentation in [docs/api/README.md](../api/README.md) (index) and per-endpoint files in `docs/api/endpoints/`.
- **HTTP discipline**: Session factory, rate limiting, and header profile in [docs/http-integration-guide.md](../http-integration-guide.md).
- **Cloudflare setup**: Tunnel creation, Zero Trust policies, and DNS configuration in [cloudflare-access-setup.md](cloudflare-access-setup.md).

---

*Last updated: 2026-07-12 | Source: E-250-05 (migration 008 dropped `team_opponents`; corrected `opponent_links` description to remove the dead downstream reference), E-241-05 (removed season_fallback from trust-flags table, updated program_type notes to pitch-rule role, updated season_id examples to year-only), E-235 (migration 002 report_generation_runs, N vs M coverage semantics), E-196 (migration 014 start_time/timezone, game ordering), E-195 (migration 009 plays/play_events tables), E-173 (unified resolve route, subnav badge, discover-opponents route removed), E-167 (migration 007 name+season_year index), E-158 (src/charts/ module, migration 006 spray chart additions), E-120-06 (opponent_links table, sub-nav Opponents, url_parser correction, port 8001, teams columns), E-115-02 (schema and admin sections rewritten for E-100 fresh-start schema), E-042 (admin team management, url_parser, team_resolver), E-003-02 (original), E-239 (reports-first reframe: removed dashboard surface references, plays pipeline note), E-255-05 (Truth Sweep: fixed the same-dir cloudflare-access-setup.md link now that both runbooks live in docs/admin/; added the migration-numbering note above; corrected the E-195 section's false "plays pipeline removed in E-239" claim -- it is alive, per E-255-R-01), E-256-10 (corrected the stale `data/seeds/` directory-structure line -- the surface and its Dockerfile COPY were removed in E-256-06 -- and the `scripts/` comment's stale "seeding" reference)*
