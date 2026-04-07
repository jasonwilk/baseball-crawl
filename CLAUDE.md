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

## Key Metrics

See `.claude/rules/key-metrics.md` for stat definitions, coaching priorities, and the data dictionary reference.

## GameChanger API
- **Auth**: Three-token architecture (client, access, refresh) with programmatic token refresh and login fallback. Auth module implementation constraints (exception hierarchy, client pattern, env var access) are in `.claude/rules/auth-module.md`. See `docs/api/auth.md` for the full auth architecture, token lifetimes, credential variables, and mobile profile details.
- NEVER log, commit, display, or hardcode credentials in source code
- The API is undocumented; we maintain our own spec at `docs/api/README.md` (index) and per-endpoint files in `docs/api/endpoints/`
- API limitations are discovered iteratively -- document everything
- **Authenticated endpoints** (`/teams/*`, `/me/*`) require `gc-token` + `gc-device-id` headers and must handle auth expiration gracefully. Includes a **UUID-to-public_id bridge** (`GET /teams/{team_id}/public-team-profile-id`) that returns the `public_id` slug for teams the authenticated user manages (returns 403 for non-managed teams). For opponent `public_id` discovery, use the `public_id` field returned directly in schedule and opponent list responses instead.
- **Public endpoints** require NO authentication -- no `gc-token`, no `gc-device-id`. Four confirmed under `/public/*`: `GET /public/teams/{public_id}` (name, location, record, staff), `GET /public/teams/{public_id}/games` (game schedule with final scores, opponents, home/away; **caution**: returns perspective-specific game IDs -- the same real-world game gets a different `id` depending on which team's schedule is queried, unlike authenticated `game-summaries` which returns stable `event_id`/`game_stream_id`), `GET /public/teams/{public_id}/games/preview` (near-duplicate of `/games` -- same data minus `has_videos_available`, uses `event_id` instead of `id`; prefer `/games`), and `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` (per-game inning-by-inning scoring, R/H/E totals; same `game_stream_id` as authenticated boxscore -- complementary views of the same game). One additional public-path endpoint uses an **inverted URL pattern**: `GET /teams/public/{public_id}/players` (roster -- NOT `/public/teams/`). Both path structures coexist in the API; do not assume all public endpoints follow `/public/*`. Public endpoints use `public_id` slugs (not UUIDs) except game details which uses `game_stream_id` from game-summaries, and may have different field names than authenticated equivalents (see API spec for details).
- **public_id-to-gc_uuid bridge**: When you have a team's `public_id` but need its `gc_uuid` for authenticated endpoints, use `POST /search` filtered by `public_id` to resolve it. See `.claude/rules/gc-uuid-bridge.md` for the full pattern, storage rules, and edge cases.
- **Opponent scouting pipeline**: Uses opponent `public_id` to fetch schedules and rosters via public endpoints, then per-game boxscores via authenticated endpoint; season aggregates are computed from boxscores (season-stats endpoint is Forbidden for non-owned teams). No UUID or following required. See `docs/api/flows/opponent-scouting.md`.
- **Opponent entry duality**: GC has two opponent entry modes -- manual typing (`root_team_id` only) and team lookup (`root_team_id` + `progenitor_team_id`). `progenitor_team_id` present = coach linked via lookup (reliable single-season dedup signal); absent = manual entry. `root_team_id` is a separate namespace from `gc_uuid` -- NEVER store `root_team_id` in the `gc_uuid` column.
- **HTTP discipline**: All requests must present as a normal browser user. See `.claude/rules/http-discipline.md` for headers, session behavior, rate limiting, and pattern hygiene.

## Commands

The `bb` CLI is the primary operator interface. Run `bb --help` for the full command list. Key command groups: `bb status`, `bb creds`, `bb data`, `bb proxy`, `bb db`. The `bb data` group supports `--crawler` and `--loader` flags for targeted pipeline runs (e.g., `bb data crawl --crawler spray-chart`, `bb data load --loader spray-chart`, `bb data crawl --crawler plays`, `bb data load --loader plays`). `bb data scout` runs the full five-stage scouting pipeline for tracked opponents: scouting crawl, scouting load, gc_uuid resolution, spray crawl, spray load. `bb data dedup` detects and merges duplicate tracked teams (`--dry-run` by default, `--execute` to apply). `bb data dedup-players` detects and merges same-team duplicate player entries caused by cross-perspective UUID mismatch (`--dry-run` by default, `--execute` to apply; recomputes season aggregates after merge). `bb data repair-opponents` back-fills `opponent_links` resolutions to `team_opponents` for opponents resolved before write-through was implemented (`--dry-run` by default, `--execute` to apply). `bb report generate` produces a standalone report for any GC `public_id` (no `team_opponents` link required). `bb report list` shows all generated reports with status and expiry. `bb data reconcile` runs plays-vs-boxscore reconciliation (`--dry-run` by default, `--execute` to apply corrections, `--summary` for aggregate stats, `--game-id X` for single-game verbose output). `bb data backfill-appearance-order` populates `appearance_order` on historical `player_game_pitching` rows from cached boxscore JSON (idempotent -- only updates rows where `appearance_order IS NULL`). **Footgun**: after backfill, run `bb data scout` to recompute scouting season aggregates (tracked-team GS is derived from `appearance_order` at scouting-load time). Underlying scripts in `scripts/` still work directly but `bb` is preferred.

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
- Keep data extraction separate from analysis/processing. Use a clear directory structure: `src/` for source, `tests/` for tests, `data/` for local dev outputs, `docs/` for documentation.
- Extraction should be idempotent. All HTTP requests include proper error handling, retries, and rate limiting. Store raw API responses before transforming (raw -> processed pipeline).
- **Canonical team creation**: `ensure_team_row()` in `src/db/teams.py` — single entry point for all team INSERTs. New team-INSERT paths MUST use this function.
- **Canonical player upsert**: `ensure_player_row()` in `src/db/players.py` — single entry point for all player INSERTs/UPDATEs. Uses length-based name preference (longer name wins; "Unknown" treated as length 0). New player-INSERT paths MUST use this function.
- **Canonical team deletion**: `cascade_delete_team()` and `cleanup_orphan_teams()` in `src/reports/generator.py` — consolidated deletion paths. New team-deletion paths MUST use these functions.
- **Import boundary**: `src/` modules MUST NOT import from `scripts/`. Reusable logic lives in `src/`; scripts are thin wrappers.
- **Repo-root resolution**: Modules in `src/` use `Path(__file__).resolve().parents[N]` for repo-root-relative paths. Never use cwd-relative paths or `sys.path.insert()`.
- **`migrations/` is a Python package**: Has `__init__.py` and is in `pyproject.toml` because `src/db/reset.py` imports from it.
- **Scouting pipeline parity**: `run_scouting_sync` (web) and `bb data scout` (CLI) MUST produce equivalent data artifacts — all five stages in both paths.
- **Canonical opponent resolution**: `finalize_opponent_resolution()` in `src/api/db.py` — single entry point for all resolution paths. All resolution paths MUST use this function.
- **Season_id derivation**: `derive_season_id_for_team()` and `ensure_season_row()` — all loaders MUST use these. Callers must unpack the tuple return type.
- **Pipeline caller convention**: `crawl.run()` and `load.run()` default to `source="yaml"`. For per-team DB-backed filtering, callers MUST pass `source="db"` AND `team_ids=[team_id]`. Omitting either silently processes wrong teams.
- **Shared query functions**: When both dashboard and reports need the same data, the query logic lives in a shared function in `src/api/db.py`. New cross-surface data needs should follow this pattern.
- **Prevention over cleanup**: Prefer preventing bad data at insert time over building cleanup tools after the fact. Example: `GameLoader._find_duplicate_game()` deduplicates cross-perspective games using a natural key (`game_date` + unordered `{home_team_id, away_team_id}`) before insertion, avoiding the need for post-hoc dedup.
- See `.claude/rules/architecture-subsystems.md` for subsystem implementation details (plays, spray, reconciliation, LLM, reports, charts, pipelines, two-tier enrichment).

See `.claude/rules/scouting-data-flows.md` for opponent flow vs. reports flow comparison, naming conventions, and feature parity principle.
See `.claude/rules/data-model.md` for schema design decisions, table conventions, and column semantics.
See `.claude/rules/admin-ui.md` for admin interface structure, team management flows, and opponent resolution workflow.

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
