# baseball-crawl

## Core Principle

**Simple first. Complexity as needed.**

Every decision in this project -- code, architecture, agent design, process -- starts with the simplest thing that works. Complexity is added only when a real problem demands it, not in anticipation of problems that might never arrive.

What this means in practice:
- Build the smallest working thing, then iterate
- Do not design for scale, generality, or future needs until those needs are real
- One file is better than a framework. A script is better than a pipeline. A dict is better than a class -- until it isn't.
- When in doubt, leave it out. You can always add; removing is harder.

## Project Purpose

Coaching analytics platform for **Lincoln Standing Bear High School** baseball program. Extracts data from GameChanger, builds a queryable database for scouting and game preparation, and (later) publishes dashboards for coaching staff.

**The core value proposition**: Give LSB coaches a competitive advantage through data-driven scouting, lineup optimization, and opponent analysis -- capabilities that most high school programs do not have.

### Scope
- **Teams**: LSB Freshman, JV, Varsity, Reserve. Legion teams added later.
- **Roster size**: 12-15 players per team
- **Season**: ~30 games per team
- **Multi-season**: Players tracked across LSB HS, Legion, and travel ball over time
- **Data sources**: GameChanger API (primary), potentially others later
- **Users**: Jason (system operator), coaching staff (dashboard consumers)

### MVP Target
A queryable database containing team and opponent statistics, sufficient for scouting reports and game prep. Dashboards come after the data layer is solid.

### Deployment Target
- **Local dev**: `docker compose up` starts the full stack at http://localhost:8001
- **Production**: Docker Compose on a Linux server (home server or any machine with Docker)
- **Production URL**: `https://bbstats.ai`
- **Network**: Cloudflare Tunnel for ingress (no exposed ports). App-internal auth via magic links and passkeys (E-023). Cloudflare Access is present but passive (no enforcing policies).
- **Database**: SQLite at `./data/app.db` (host-mounted, WAL mode, simple file backup via `scripts/backup_db.py`)
- See `docs/production-deployment.md` for the verified deployment runbook

## Data Philosophy

**We automate what a coach could do by hand.**

Every piece of data this project gathers is information already visible to any GameChanger user through the normal UI. This project does not access hidden data, reverse-engineer proprietary analytics, or perform novel data mining. It scales the manual work of opening box scores, copying stats into a spreadsheet, and comparing them across games and seasons.

This guides our data-source decisions:
- **GameChanger API** (preferred): Programmatic access to the same data shown in the app.
- **Web scraping** (fallback): Screen-scrape when the API does not cover a data point, but only for data already visible in the UI.
- **Freshness for coaches**: Coaches think in games, not sync timestamps. Data freshness should be presented as game coverage ("Through [date] ([N] games)"), not system sync dates ("Updated Mar 27"). This applies to dashboards, cards, and any UI showing how current the data is.

## Tech Stack
- Python end-to-end (version governed by `.python-version` -- Dockerfile, devcontainer.json, and pyproject.toml must stay in sync with it) -- crawlers, API, dashboard, migrations, and tests
- FastAPI + Jinja2 for the serving layer (server-rendered HTML)
- SQLite (WAL mode, host-mounted Docker volume at `./data/app.db`) for structured storage
- Docker Compose for local development and production deployment
- Cloudflare Tunnel for network ingress; app-internal authentication (magic links + passkeys)
- **Dependency management**: pip-tools (`*.in` → `*.txt`). See `.claude/rules/dependency-management.md` for workflow, file layout, and Python version policy.

## Key Metrics We Track
These are the statistics and dimensions that matter for coaching decisions:
- **Batting**: OBP, strikeout rate, home/away splits, left/right pitcher splits
- **Pitching**: K/9, BB/9, left/right batter splits, home/away splits
- **Per-game splits**: Game-by-game batting and pitching lines for streak detection, recent form, and workload tracking
- **Box scores**: Per-player batting and pitching lines for both teams per game, including batting order, pitch counts, strike counts, and defensive positions -- from a single API call per game
- **Pitch-by-pitch plays**: Full pitch sequence per at-bat (balls, strikes, fouls, in-play), contact quality descriptions, baserunner events, fielder identity on outs, and in-game substitutions -- from a single API call per game via the plays endpoint. Stored in `plays` + `play_events` tables with pre-computed `is_first_pitch_strike` and `is_qab` flags.
- **FPS% (first pitch strike %)**: Pitching stat computed from plays data. Flag records actual first-pitch result for ALL PAs; exclusions (HBP, Intentional Walk) applied at query time only (`WHERE outcome NOT IN ('Hit By Pitch', 'Intentional Walk')`).
- **QAB (quality at-bat)**: Batting stat. 7 qualifying conditions: 2S+3 (3+ pitches after 2-strike count), 6+ pitches, XBH, hard-hit ball (line drive / hard ground ball), walk (not IBB), sacrifice bunt, sacrifice fly. Intentional Walk, Dropped 3rd Strike, and Catcher's Interference are explicitly NOT QABs.
- **Spray charts**: Ball-in-play direction (x/y coordinates), play type, play result, fielder position -- for batting tendency analysis and defensive positioning
- **Players**: Key player identification (aces, closers, leadoff), lineup position history
- **Opponents**: Lineup patterns and changes, tendencies, roster composition, opponent season stats and boxscores (via scouting pipeline)
- **Longitudinal**: Player development across seasons, teams, and levels
- **Pitcher attribution accuracy**: Coaching thresholds from domain consultation -- 90%+ accuracy required for FPS% reporting, 95%+ for pitch count reporting, 80%+ useful for development context. The reconciliation engine measures and corrects pitcher attribution using boxscore BF counts as ground truth.

The authoritative data dictionary mapping all GameChanger stat abbreviations to their definitions is at `docs/gamechanger-stat-glossary.md`. It includes batting, pitching, fielding, catcher, and positional innings stats, plus an API field name mapping table for cases where the API uses different abbreviations than the UI.

## GameChanger API
- **Auth**: Three-token architecture (client, access, refresh) with programmatic token refresh and login fallback. Auth module implementation constraints (exception hierarchy, client pattern, env var access) are in `.claude/rules/auth-module.md`. See `docs/api/auth.md` for the full auth architecture, token lifetimes, credential variables, and mobile profile details.
- NEVER log, commit, display, or hardcode credentials in source code
- The API is undocumented; we maintain our own spec at `docs/api/README.md` (index) and per-endpoint files in `docs/api/endpoints/`
- API limitations are discovered iteratively -- document everything
- **Authenticated endpoints** (`/teams/*`, `/me/*`) require `gc-token` + `gc-device-id` headers and must handle auth expiration gracefully. Includes a **UUID-to-public_id bridge** (`GET /teams/{team_id}/public-team-profile-id`) that returns the `public_id` slug for teams the authenticated user manages (returns 403 for non-managed teams). For opponent `public_id` discovery, use the `public_id` field returned directly in schedule and opponent list responses instead.
- **Public endpoints** require NO authentication -- no `gc-token`, no `gc-device-id`. Four confirmed under `/public/*`: `GET /public/teams/{public_id}` (name, location, record, staff), `GET /public/teams/{public_id}/games` (game schedule with final scores, opponents, home/away), `GET /public/teams/{public_id}/games/preview` (near-duplicate of `/games` -- same data minus `has_videos_available`, uses `event_id` instead of `id`; prefer `/games`), and `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` (per-game inning-by-inning scoring, R/H/E totals; same `game_stream_id` as authenticated boxscore -- complementary views of the same game). One additional public-path endpoint uses an **inverted URL pattern**: `GET /teams/public/{public_id}/players` (roster -- NOT `/public/teams/`). Both path structures coexist in the API; do not assume all public endpoints follow `/public/*`. Public endpoints use `public_id` slugs (not UUIDs) except game details which uses `game_stream_id` from game-summaries, and may have different field names than authenticated equivalents (see API spec for details).
- **public_id-to-gc_uuid bridge**: When you have a team's `public_id` but need its `gc_uuid` for authenticated endpoints, use `POST /search` filtered by `public_id` to resolve it. See `.claude/rules/gc-uuid-bridge.md` for the full pattern, storage rules, and edge cases.
- **Opponent scouting pipeline**: Uses opponent `public_id` to fetch schedules and rosters via public endpoints, then per-game boxscores via authenticated endpoint; season aggregates are computed from boxscores (season-stats endpoint is Forbidden for non-owned teams). No UUID or following required. See `docs/api/flows/opponent-scouting.md`.
- **Opponent entry duality**: GC has two opponent entry modes -- manual typing (`root_team_id` only) and team lookup (`root_team_id` + `progenitor_team_id`). `progenitor_team_id` present = coach linked via lookup (reliable single-season dedup signal); absent = manual entry. `root_team_id` is a separate namespace from `gc_uuid` -- NEVER store `root_team_id` in the `gc_uuid` column.
- **HTTP discipline**: All requests must present as a normal browser user. See `.claude/rules/http-discipline.md` for headers, session behavior, rate limiting, and pattern hygiene.

## Commands

The `bb` CLI is the primary operator interface. Run `bb --help` for the full command list. Key command groups: `bb status`, `bb creds`, `bb data`, `bb proxy`, `bb db`. The `bb data` group supports `--crawler` and `--loader` flags for targeted pipeline runs (e.g., `bb data crawl --crawler spray-chart`, `bb data load --loader spray-chart`, `bb data crawl --crawler plays`, `bb data load --loader plays`). `bb data scout` runs the full five-stage scouting pipeline for tracked opponents: scouting crawl, scouting load, gc_uuid resolution, spray crawl, spray load. `bb data dedup` detects and merges duplicate tracked teams (`--dry-run` by default, `--execute` to apply). `bb data repair-opponents` back-fills `opponent_links` resolutions to `team_opponents` for opponents resolved before write-through was implemented (`--dry-run` by default, `--execute` to apply). `bb report generate` produces a standalone report for any GC `public_id` (no `team_opponents` link required). `bb report list` shows all generated reports with status and expiry. `bb data reconcile` runs plays-vs-boxscore reconciliation (`--dry-run` by default, `--execute` to apply corrections, `--summary` for aggregate stats, `--game-id X` for single-game verbose output). Underlying scripts in `scripts/` still work directly but `bb` is preferred.

## Workflows
- **Plan**: When the user says "plan an epic for X" (or similar -- "plan E-NNN", "create an epic for X", "write stories for X", "let's plan X", "design an epic for X"), load `.claude/skills/plan/SKILL.md` and follow its workflow. The main session suggests a planning team based on domain signals, spawns PM and domain experts, guides through discovery, planning, automatic spec review, refinement, and READY gate. Supports a "plan and dispatch" compound modifier to chain into the implement skill after READY.
- **Implement**: When the user says "implement E-NNN" (or similar -- "start epic", "execute E-NNN", "dispatch E-NNN", "kick off E-NNN"), load `.claude/skills/implement/SKILL.md` and follow its workflow. The main session reads the epic for team composition and spawns implementers, code-reviewer, and PM. Supports an "and review" modifier to chain a code review after implementation completes.
- **Ingest endpoint**: When the user says "ingest endpoint" (or similar -- "curl is ready", "new endpoint to analyze"), load `.claude/skills/ingest-endpoint/SKILL.md` and follow its two-phase workflow. The user has placed a curl command in `secrets/gamechanger-curl.txt` and expects api-scout to execute it (time-sensitive -- the `gc-signature` header in POST requests expires within minutes, and curl commands should be executed promptly regardless of token lifetime), then claude-architect to integrate findings into the context layer.
- **Spec review**: When the user says "spec review" (or similar -- "spec review E-NNN", "codex spec review", "spec review prompt", "codex spec review prompt"), load `.claude/skills/codex-spec-review/SKILL.md` and follow its workflow. Supports two execution paths: headless (default -- runs Codex via script, presents findings, offers advisory triage) and prompt generation (trigger phrase contains "prompt" -- assembles lean prompt for copy-paste).
- **Code review**: When the user says "codex review" (or similar -- "review with codex", "code review", "review epic", "codex review prompt", "code review prompt", "post-dev review"), load `.claude/skills/codex-review/SKILL.md` and follow its workflow. Supports two execution paths: headless (default -- runs Codex via script, presents findings, offers advisory triage) and prompt generation (trigger phrase contains "prompt" -- assembles lean prompt for copy-paste).
- **Curate the vision**: When the user says "curate the vision", invoke the product-manager in curate mode. PM reviews accumulated signals in `docs/vision-signals.md` with the user, discusses which belong in `docs/VISION.md`, updates the vision document, and clears processed signals.
- **Workflow help**: When the user says "/workflow-help" (or similar -- "what commands do I have", "show me the workflows", "cheat sheet"), load `.claude/skills/workflow-help/SKILL.md` and print the workflow cheat sheet.

## App Troubleshooting

After changing `src/`, `migrations/`, `Dockerfile`, `docker-compose.yml`, or `requirements.txt`, rebuild (`docker compose up -d --build app`) and verify the health check passes. See `.claude/rules/app-troubleshooting.md` for the full troubleshooting guide.

## Proxy Boundary (Host vs. Container)

**mitmproxy** runs on the Mac host (not in the devcontainer). Agents MUST NOT start, stop, or manage mitmproxy -- tell the user to run proxy commands on the Mac host. Agents CAN read proxy data in `proxy/data/` and credentials from `.env`. **Bright Data** runs inside the devcontainer as part of the normal HTTP session. See `.claude/rules/proxy-boundary.md` for full boundary rules, Bright Data configuration, and `docs/admin/mitmproxy-guide.md` for mitmproxy setup.

## Security Rules
- IMPORTANT: Credentials and tokens MUST NEVER appear in code, logs, commit history, or agent output
- Use `.env` files locally (always in `.gitignore`)
- Use environment variables via .env files for production (Docker Compose reads .env; files are git-ignored)
- When agents work with API responses, strip or redact auth headers before storing raw responses
- Treat GameChanger session tokens as sensitive data at all times
- **PII scanner**: `src/safety/pii_scanner.py` -- run manually with `python3 src/safety/pii_scanner.py --staged` (also supports `--stdin` and explicit file args)

## Architecture
- Keep data extraction separate from analysis/processing
- Use a clear directory structure: `src/` for source, `tests/` for tests, `data/` for local dev outputs, `docs/` for API specs and documentation
- Extraction should be idempotent -- re-running should not duplicate data
- All HTTP requests should include proper error handling, retries, and rate limiting
- Store raw API responses before transforming (raw -> processed pipeline)
- Credential management: environment variables via .env files (local dev and production; Docker Compose reads .env automatically)
- **Canonical team creation**: `ensure_team_row()` in `src/db/teams.py` is the single entry point for all team INSERT operations. ALL pipeline paths (schedule loader, opponent resolver, game loader, scouting crawler/loader, roster loader, season stats loader) use this function. It implements a deterministic dedup cascade: gc_uuid match → public_id match → name+season_year match (tracked only) → INSERT. A self-tracking guard prevents member teams from being re-created as tracked opponents. Back-fill rules are conservative: gc_uuid/public_id are NOT attached on name-only matches (step 3) to avoid irreversible misidentification. New team-INSERT paths MUST use this function.
- **Import boundary**: `src/` modules MUST NOT import from `scripts/`. `scripts/` contains standalone operator tools that import from `src/`; the reverse direction is not allowed. Reusable logic always lives in `src/`, with scripts as thin wrappers.
- **Repo-root resolution**: Modules in `src/` use `Path(__file__).resolve().parents[N]` to derive repo-root-relative paths (e.g., `parents[2]` for a module three levels deep like `src/db/reset.py`). Never use cwd-relative paths or `sys.path.insert()` in `src/` modules.
- **`migrations/` is a Python package**: It has `__init__.py` and is included in `pyproject.toml` `[tool.setuptools.packages]` because `src/db/reset.py` imports from it. Do not remove `migrations/__init__.py` or the pyproject.toml include without understanding this dependency.
- **Scouting pipeline**: Five stages: (1) scouting crawl (`ScoutingCrawler` -- schedules, rosters, boxscores), (2) scouting load (`ScoutingLoader` -- aggregate boxscores into season stats), (3) gc_uuid resolution (resolve `public_id` → `gc_uuid` via `POST /search` for spray chart access), (4) spray crawl (`SprayChartCrawler`), (5) spray load (`SprayChartLoader`). **Parity requirement**: `run_scouting_sync` (web trigger) and `bb data scout` (CLI) MUST produce equivalent data artifacts -- all five stages in both paths. Changes to either pipeline must maintain parity. Source files: `src/gamechanger/crawlers/scouting.py`, `src/gamechanger/loaders/scouting_loader.py`, `src/pipeline/trigger.py` (web), `src/cli/data.py` (CLI).
- **Background pipeline trigger**: `src/pipeline/trigger.py` provides fire-and-forget pipeline execution from HTTP routes (FastAPI `BackgroundTasks`). Each trigger function creates its own DB connection, refreshes auth eagerly, tracks status via `crawl_jobs` rows, and updates `teams.last_synced` on success. Two pipelines: `run_member_sync` (crawl+load+opponent discovery for owned teams) and `run_scouting_sync` (all five scouting stages for tracked teams -- see Scouting pipeline). `run_member_sync` includes automatic opponent discovery after crawl+load: the schedule seeder (`src/gamechanger/loaders/opponent_seeder.py`) seeds `opponent_links` from cached `schedule.json`/`opponents.json`, then `OpponentResolver.resolve()` upgrades linked rows via live API calls. Seeder failures are non-fatal; `CredentialExpiredError` from the resolver propagates. **Auto-scout after resolution**: When an opponent is resolved with a non-null `public_id`, scouting is triggered automatically. This pattern exists in three places: (1) admin manual connect (`/admin/opponents/{link_id}/resolve`), (2) admin GC search resolve, and (3) auto-resolver during `_discover_opponents()` in `run_member_sync`. Admin routes (manual connect, GC search) enqueue `run_scouting_sync` via FastAPI `BackgroundTasks`; the auto-resolver during `_discover_opponents()` calls `run_scouting_sync` directly (already executing inside a background job). No manual sync trigger needed. **Auto-sync resilience pattern**: Auto-sync triggers from admin actions (team add, merge) use a two-phase approach: `_prepare_auto_sync()` does DB-only work (running-job check, `crawl_jobs` creation) in a thread pool, then `_enqueue_from_prep()` calls `background_tasks.add_task()` from the async handler. Both phases are wrapped in try/except so auto-sync failures never prevent the primary operation from completing.
- **Canonical opponent resolution**: `finalize_opponent_resolution()` in `src/api/db.py` is the single entry point for all opponent resolution paths (GC search, manual connect, auto-resolver). It performs a write-through operation atomically: upserts `team_opponents`, sets `teams.is_active = 1`, discovers and reassigns FKs from old stub teams, and returns the result. All resolution paths MUST use this function -- do not write directly to `team_opponents` during resolution.
- **Season_id derivation**: `derive_season_id_for_team(db, team_id)` in `src/gamechanger/loaders/__init__.py` is the canonical utility for all DB season_id derivation. Returns `tuple[str, int | None]` -- `(season_id, season_year)`. Maps `program_type` to suffix: `hs` → `spring-hs`, `usssa` → `summer-usssa`, `legion` → `summer-legion`. Fallbacks: NULL `season_year` → current year, NULL `program_id` → year-only (no suffix). `ensure_season_row(db, season_id)` is the consolidated function replacing all private `_ensure_season_row()` methods -- all loaders MUST use it. **Callers must unpack the tuple** -- the return type is `tuple`, not `str`.
- **Filesystem vs DB season_id decoupling**: The filesystem path (`data/raw/{season_slug}/teams/{uuid}/`) is for file organization and discovery only. The DB `season_id` column is for data identity. These are decoupled -- a team's data may live in `data/raw/2026-spring-hs/` on disk but be tagged as `2025-summer-usssa` in the DB if the team's actual season context differs. Crawlers write to filesystem paths (derived from crawl config); loaders call `derive_season_id_for_team()` for DB inserts. `scouting_runs.season_id` is a file-discovery column reflecting the crawl directory path -- it does NOT necessarily match the DB season_id of the loaded data.
- **Pipeline caller convention (`source` and `team_ids`)**: `crawl.run()` and `load.run()` both default to `source="yaml"` (reads team config from YAML files). For per-team DB-backed filtering, callers MUST pass `source="db"` AND `team_ids=[team_id]` to both functions. Omitting either parameter silently processes the wrong set of teams -- `source="yaml"` ignores the database entirely, and omitting `team_ids` processes all teams. See `src/pipeline/trigger.py` for the correct calling pattern.
- **Chart rendering**: `src/charts/` package contains headless PNG rendering modules (matplotlib + numpy). Currently: `src/charts/spray.py` (spray chart renderer). Future chart types go in this package. Image endpoints under `/dashboard/charts/` use `run_in_threadpool` for DB + renderer calls.
- **Plays pipeline**: `src/gamechanger/crawlers/plays.py` (crawler), `src/gamechanger/parsers/plays_parser.py` (pure parser, no DB dependency), `src/gamechanger/loaders/plays_loader.py` (thin DB writer). Parser/loader separation pattern: the parser is a pure function producing dataclasses from raw JSON, enabling unit testing without DB fixtures. The loader handles DB writes only. **Pitcher state tracking**: the parser maintains `current_pitcher_top` and `current_pitcher_bottom` state variables that persist across innings within the same half, updated on substitution events, with explicit pitcher references in `final_details` as ground truth override. **team_players asymmetric keys**: own team uses `public_id` slug, opponent uses UUID -- build a flat lookup dict across both. Entry points: `bb data crawl --crawler plays`, `bb data load --loader plays`. Cached data: `data/raw/{season}/teams/{gc_uuid}/plays/{event_id}.json`.
- **Spray chart pipeline**: `src/gamechanger/crawlers/spray_chart.py` (crawler) and `src/gamechanger/loaders/spray_chart_loader.py` (loader). The spray endpoint is team-scoped and asymmetric: calling with the owning team's UUID returns both teams' spray data; calling with a participant's UUID returns only that team's data (verified 2026-03-29). The crawler uses the owning team's UUID to get complete per-game data. Entry points: `bb data crawl --crawler spray-chart`, `bb data load --loader spray-chart`.
- **Spray chart auth exception**: Image routes (`/dashboard/charts/spray/player/{id}.png`, `/dashboard/charts/spray/team/{id}.png`) require an authenticated session but deliberately skip the `permitted_teams` authorization check. Reason: opponent players cannot pass `permitted_teams` but their spray data is legitimately viewable. This is a documented exception to the normal dashboard auth pattern.
- **Worktree guard hook**: `.claude/hooks/worktree-guard.sh` is a PreToolUse hook that blocks Write/Edit operations to the main checkout. Two modes: (1) **Dispatch active** (epic worktree at `/tmp/.worktrees/baseball-crawl-E-*` exists): blocks ALL Write/Edit to `/workspaces/baseball-crawl/` except `.claude/agent-memory/`; (2) **No dispatch**: blocks only implementation paths (`src/`, `tests/`, `migrations/`, `scripts/`). Worktree writes always pass. See `.claude/rules/worktree-isolation.md` for full details.
- **Reports package**: `src/reports/` is a self-contained package for standalone report generation. `generator.py` orchestrates crawl→load→query→render→write; `renderer.py` produces self-contained HTML files written to `data/reports/`. The reports serving route (`/reports/{slug}`) requires no authentication and is separate from the dashboard.
- **Reconciliation package**: `src/reconciliation/` is a post-load quality pass that cross-references plays data against boxscore data to detect and correct discrepancies (e.g., pitcher attribution errors). It reads from the DB (not raw API data) and operates after loaders have populated the database -- it does NOT belong in `src/gamechanger/`. Entry point: `reconcile_game(conn, game_id, dry_run=True)` in `engine.py` for per-game processing; `reconcile_all(conn, dry_run=True)` for batch. Discrepancy records are always written to `reconciliation_discrepancies` (migration 012); only corrections (e.g., `plays.pitcher_id` updates) are gated by `dry_run=False`. BF boundary correction algorithm: walks plays in `play_order`, assigns pitcher by boxscore appearance order and batters-faced counts; pitcher order extracted from cached boxscore JSON (not DB AUTOINCREMENT).

### Scouting Data Flows

Two distinct flows produce scouting intelligence. Confusing them causes wrong auth, wrong data source, or wrong lifecycle assumptions.

| | Opponent Flow (dashboard) | Reports Flow (standalone) |
|-|--------------------------|--------------------------|
| **Entry** | `/dashboard/opponents` | `/admin/reports` or `bb report generate` |
| **Auth** | Session + permitted_teams | Web: admin auth. CLI: none. Serving: none (`/reports/{slug}` is public) |
| **Data** | Live DB queries per page load | Frozen HTML snapshot at generation time |
| **Lifecycle** | Persistent (exists while `team_opponents` link exists) | Ephemeral (14-day expiry, deletable) |
| **Data source** | `team_opponents` + scouting pipeline (tracked teams) | Ad-hoc crawl of any GC `public_id` (no `team_opponents` required) |

**Naming convention**: "scouting report" or "opponent scouting" = opponent flow. "Standalone report" or "generated report" = reports flow.

**Architectural conventions**:
- `/reports/{slug}` MUST NOT query stats tables or render Jinja2 templates at serve time -- only `reports` table lookup + file read from disk
- Reports have no `team_opponents` dependency; generation takes any GC `public_id`
- Reports are ephemeral: 14-day expiry, no versioning, no update-in-place
- `src/reports/` is self-contained (`generator.py`, `renderer.py`); neither module is imported by the opponent flow

**Routing note**: Stories modifying `src/reports/`, `src/api/routes/reports.py`, report handlers in `src/api/routes/admin.py`, or `src/api/templates/admin/reports.html` belong to the reports flow. Stories modifying opponent dashboard routes/templates or `src/gamechanger/loaders/scouting_loader.py` belong to the opponent flow.

## Data Model

The schema is defined in `migrations/001_initial_schema.sql` (base) with incremental migrations (`004_add_team_season_year.sql`, etc.). Key design decisions:

- **Programs**: Umbrella entity grouping teams under an organizational program (e.g., `lsb-hs` = Lincoln Standing Bear HS). Types: `hs`, `usssa`, `legion`.
- **Teams**: INTEGER PRIMARY KEY AUTOINCREMENT (`teams.id`). External GC identifiers live in dedicated UNIQUE columns: `gc_uuid` (authenticated API) and `public_id` (public URL slug). All FK references to teams use `teams(id)`. INTEGER PK applies to `teams` only -- programs, seasons, and players keep TEXT PKs.
- **Membership type**: `teams.membership_type` (`member` or `tracked`). Member teams are those the operator manages in GameChanger; tracked teams are opponents or other teams added for scouting.
- **Season year**: `teams.season_year INTEGER` -- the year this team belongs to, populated from GameChanger API (`season_year` on authenticated endpoints, `team_season.year` on public). NULL falls back to current calendar year in `get_team_year_map()`. Self-healed by pipeline on sync. **Footgun**: stub team auto-creation (in roster/season_stats loaders) must pass `season_year` to `ensure_team_row()` to avoid the current-year fallback producing wrong values for historical data.
- **Classification**: `teams.classification` column. Valid values: `varsity`, `jv`, `freshman`, `reserve` (HS); `8U`-`14U` (USSSA); `legion`. Division dropdown in the admin UI.
- **team_opponents**: Junction table linking member teams to their tracked opponents (`our_team_id` -> `opponent_team_id`), with `first_seen_year` for historical context. `is_hidden` serves dual purpose: admin dismissal ("no match" during resolution) AND pipeline filtering (hidden opponents are skipped by seeder/resolver).
- **TeamRef pattern**: Pipeline code uses a `TeamRef` dataclass (`id: int`, `gc_uuid: str | None`, `public_id: str | None`). `.id` for all DB operations; `.gc_uuid` / `.public_id` for API calls. Tracked teams may have `gc_uuid=None`.
- **Game status values**: Completed games use `status = 'completed'` (not `'final'`). All queries across `src/` filter on `'completed'`; the `game_loader.py` inserts with this value. Do not use `'final'` in game queries.
- **Enriched stat columns** (schema-ready, not yet populated): `game_stream_id` on games (links to game-streams endpoints like `GET /game-streams/{game_stream_id}/events`; NOT a path parameter for game-stream-processing endpoints -- `event_id` from game-summaries is the path parameter for both `GET /game-stream-processing/{event_id}/boxscore` and `GET /game-stream-processing/{event_id}/plays`; the game loader indexes summaries by both `event_id` and `game_stream_id` for robust file matching), `bats`/`throws` on players, home/away and vs-LHP/RHP split columns on season batting/pitching, `pitches`/`total_strikes` on game pitching, `batting_order`/`positions_played`/`is_primary` on game batting, `stat_completeness` tracking on all stat tables.
- **Plays and play events**: Two-table schema (`plays` + `play_events`, migration `009_plays_play_events.sql`). `plays` stores one row per plate appearance with batter/pitcher linkage, pitch count, outcome, and pre-computed boolean flags (`is_first_pitch_strike`, `is_qab`). `play_events` stores individual events within a PA (pitch results, baserunner events, substitutions). Idempotency keys: `UNIQUE(game_id, play_order)` on plays, `UNIQUE(play_id, event_order)` on play_events. **Whole-game idempotency**: before processing, check if any `plays` row exists for the `game_id` -- if yes, skip entirely. Never delete-and-reinsert (parent-child re-insertion problem: `INSERT OR IGNORE` on existing parent returns no `lastrowid` for children). Populated by: `bb data crawl --crawler plays` + `bb data load --loader plays`. 24 confirmed outcome types; 486 `final_details` patterns (regex-parsed, not enumerable). The plays endpoint (`GET /game-stream-processing/{event_id}/plays`) is NOT ownership-gated -- works for opponent games too (unlike season-stats).
- **Spray charts**: `spray_charts` table stores ball-in-play coordinate data (x/y, play type, result, fielder position). Populated by the spray chart pipeline (`bb data crawl --crawler spray-chart` + `bb data load --loader spray-chart`). Data quality: spray data is scorekeeper-dependent (~93% of games have offensive data, ~16% have defensive); `spray_chart_data` is `null` (not empty array) when the scorekeeper did not record. Display thresholds: 3 BIP minimum for per-player charts, 20 BIP for team aggregates.

## Admin UI

The admin UI (`/admin/`) is the **primary operational interface** for routine team management, crawl triggering, and program administration. The `bb` CLI remains available for automation and scripting but is no longer the sole path for day-to-day operations.

- **Team list**: Flat table of all teams at `/admin/teams/`. Columns: team name, program, division (classification), membership badge, active/inactive, opponent count, edit link.
- **Two-phase add-team flow**: Phase 1 = URL input (paste a GameChanger team URL). Phase 2 = confirm page showing resolved team info, gc_uuid status (from reverse bridge lookup), membership radio (`member`/`tracked`, default: `tracked`), optional program dropdown and division dropdown.
- **Edit page**: Program assignment, division, name override, active toggle. Membership type is editable (radio button) as a correction path for misclassification.
- **Crawl triggering**: Admin UI triggers background crawl/load pipelines per-team via `src/pipeline/trigger.py`. Job status tracked in `crawl_jobs` table. See Architecture section for pipeline caller conventions.
- **Opponent resolution**: `/admin/opponents/{link_id}/resolve` provides a GC-search-powered workflow for connecting unresolved opponents to real GC teams. Resolution is a write-through operation via `finalize_opponent_resolution()` (see Architecture). Includes duplicate detection at confirm time (warns if selected team's `public_id` already exists). "No match" dismissal sets `is_hidden=1` (reversible via "Unhide"). Auto-scout triggers in the background when `public_id` is non-null.
- **Dashboard opponent data states**: Opponent lists display three data states: `stats` (scouting stats loaded -- green), `syncing` (crawl job running -- yellow), `scoresheet` (only game data from own team's boxscores -- gray). Opponents are sorted by `next_game_date` ascending (NULLs last), then name.
- **Shared admin subnav**: Admin templates use a `{% include "admin/_subnav.html" %}` partial with `{% with active_tab='...' %}` for consistent sub-navigation across pages.

## Project Management

Epic/story system managed by the **product-manager**. Epics: `E-NNN`, Stories: `E-NNN-SS`, Research: `E-NNN-R-SS`.

### Key Directories
- `/epics/` -- Active epics and stories; `/.project/archive/` -- Completed/abandoned epics
- `/.project/ideas/` -- Pre-epic ideas (see `.claude/rules/ideas-workflow.md`)
- `/.project/research/` -- Standalone research, POCs, and query artifacts
- `/docs/` -- API specs, architecture docs, domain reference; `/docs/VISION.md` -- Product vision

## Git Conventions
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Write descriptive commit messages explaining the "why"
- Keep PRs focused on a single concern
- Reference story IDs in commit messages when working on stories
- After committing, verify the `[pii-scan]` confirmation appears in the output -- if it is missing, the safety scan may not have run; investigate before proceeding

## Agent Ecosystem

This project uses specialized agents coordinated by the product-manager:

| Agent | Alias | Role |
|-------|-------|------|
| **claude-architect** | | Designs and manages agents, CLAUDE.md, rules, skills |
| **product-manager** | PM | Product Manager -- owns what to build, why, and in what order. Discovers requirements, plans epics, delegates implementation to specialists. |
| **baseball-coach** | coach | Domain expert -- translates coaching needs into technical requirements |
| **api-scout** | | Explores GameChanger API, maintains API spec, manages credential patterns |
| **data-engineer** | DE | Database schema design, ETL pipelines, SQLite architecture |
| **software-engineer** | SE | Python implementation, testing, general coding work |
| **docs-writer** | | Documentation specialist for admin/developer and coaching staff audiences. Writes and maintains human-readable documentation in `docs/admin/` and `docs/coaching/`. |
| **ux-designer** | | UX/interface designer for coaching dashboard and UI work. Designs layouts, wireframes, component structure, and user flows for server-rendered HTML (Jinja2 + Tailwind). |
| **code-reviewer** | | Adversarial code reviewer -- verifies ACs and code quality before stories are marked DONE during dispatch. Spawned automatically by the implement skill; does not write or edit code. |

PM discovers requirements, writes epics/stories, and owns status transitions during dispatch. Code-reviewer gates every code story. Any agent identifying future work flags it to PM for idea capture. **Direct-routing exceptions**: `api-scout`, `baseball-coach`, `claude-architect` may be invoked without PM intermediation.
