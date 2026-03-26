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
| `/admin/teams/{id}/discover-opponents` | POST | Discover opponent placeholder entries from team's public schedule |

The team list is a flat table showing all teams (no Lincoln/Opponents split). Columns: name, program, division (classification), membership badge (member/tracked), active/inactive status, opponent count, and an edit link.

The add-team flow is two-phase: Phase 1 accepts a GameChanger team URL or bare identifier. Phase 2 shows the resolved team information and lets the operator set membership type (default: `tracked`), program, and division before saving.

Sub-navigation links Users, Teams, and Opponents pages across all admin views.

### Supporting Modules

| Module | Purpose |
|--------|---------|
| `src/gamechanger/url_parser.py` | Extracts a team identifier from a GameChanger URL, bare public_id slug, or bare UUID. Returns a `TeamIdResult` with the extracted `value` and its `id_type` (`"public_id"` or `"uuid"`). Accepts any URL containing a `/teams/{id}` segment, including mobile share links. Note: while the parser accepts bare UUIDs, the admin add-team route rejects `uuid` id_type with an error directing users to provide a URL or public_id slug instead. |
| `src/gamechanger/team_resolver.py` | Calls `GET /public/teams/{public_id}` (no auth) to resolve a team's name, location, record, and staff into a `TeamProfile` dataclass. Also provides `discover_opponents()` which calls `GET /public/teams/{public_id}/games` and returns a deduplicated list of `DiscoveredOpponent` instances by name. |

`team_resolver.py` uses the shared HTTP session factory (`src/http/session.py`) with a 10-second timeout. No authentication headers are sent -- these are public GameChanger API endpoints. `url_parser.py` is a pure string parser (imports only `re`, `dataclasses`, and `urllib.parse`) and makes no HTTP calls.

## Cross-References

- **GameChanger API**: Full endpoint documentation in [docs/api/README.md](../api/README.md) (index) and per-endpoint files in `docs/api/endpoints/`.
- **HTTP discipline**: Session factory, rate limiting, and header profile in [docs/http-integration-guide.md](../http-integration-guide.md).
- **Cloudflare setup**: Tunnel creation, Zero Trust policies, and DNS configuration in [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md).

---

*Last updated: 2026-03-26 | Source: E-158 (src/charts/ module, migration 006 spray chart additions), E-120-06 (opponent_links table, sub-nav Opponents, url_parser correction, port 8001, teams columns), E-115-02 (schema and admin sections rewritten for E-100 fresh-start schema), E-042 (admin team management, url_parser, team_resolver), E-003-02 (original)*
