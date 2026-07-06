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

> **Current strategic frame (2026-06-12)**: The product as actually used is reports-first -- generate a one-off scouting report for a GameChanger `public_id` and share the link. The member-team sync, dashboard, and tracked-opponent surfaces were unused and have been **removed** (E-239, the `docs/ROADMAP.md` D2 slice). The forward feature is morning-of-game scheduled reports. Explicit non-goals: cross-team player identity, multi-season rollups, longitudinal tracking. See `docs/ROADMAP.md` for the full reframe, protected core, and epic sequence (A-E). As of the 2026-07-05 "curate the vision" session, `docs/VISION.md` has been reconciled to this reports-first reframe, so `docs/VISION.md` and `docs/ROADMAP.md` now agree on scope (reports-first, single-season, morning-of-game). The Project Purpose / Scope sections below still carry dashboard-era wording from the original multi-surface vision; that CLAUDE.md prose is a separately-tracked truth-sweep item (ROADMAP CE-5), not yet corrected here.

### Scope
- **Teams**: LSB Freshman, JV, Varsity, Reserve. Legion teams added later.
- **Roster size**: 12-15 players per team
- **Season**: ~30 games per team
- **Single-season scope**: Each team-season is tracked independently. There is no multi-season rollup, longitudinal cross-season tracking, or cross-team athlete identity (explicit non-goals)
- **Data sources**: GameChanger API (primary), potentially others later
- **Users**: Jason (system operator), coaching staff (dashboard consumers)

### MVP Target
A queryable database containing team and opponent statistics, sufficient for scouting reports and game prep. Dashboards come after the data layer is solid.

### Deployment Target
- **Local dev**: `docker compose up` starts the full stack at http://baseball.localhost:8001 (the canonical user-facing URL -- matches APP_URL / the WebAuthn origin; `baseball.localhost` resolves to 127.0.0.1). Direct in-container access (curl, health checks) uses http://localhost:8001, the same app port with a `localhost` Host header.
- **Production**: Docker Compose on a Linux server (home server or any machine with Docker)
- **Production URL**: `https://bbstats.ai`
- **Network**: Cloudflare Tunnel for ingress (no exposed ports). App-internal auth via magic links and passkeys (E-023). Cloudflare Access is present but passive (no enforcing policies).
- **Database**: SQLite at `./data/app.db` (host-mounted, WAL mode, simple file backup via `scripts/backup_db.py`)
- See `docs/production-deployment.md` for the verified deployment runbook

## Data Philosophy

**We automate what a coach could do by hand.**

Every piece of data this project gathers is information already visible to any GameChanger user through the normal UI. This project does not access hidden data, reverse-engineer proprietary analytics, or perform novel data mining. It scales the manual work of opening box scores, copying stats into a spreadsheet, and comparing them across games.

This guides our data-source decisions:
- **GameChanger API** (preferred): Programmatic access to the same data shown in the app.
- **Web scraping** (fallback): Screen-scrape when the API does not cover a data point, but only for data already visible in the UI.
- **Freshness for coaches**: Coaches think in games, not sync timestamps. Data freshness should be presented as game coverage ("Through [date] ([N] games)"), not system sync dates ("Updated Mar 27"). This applies to dashboards, cards, and any UI showing how current the data is.

### Operating Principle: Always Get Closer to Byte-Identical Play Ingestion

**Every change to play ingestion moves plays-derived stats closer to GameChanger's official box scores -- never further.** When we derive a stat from play-by-play and call it the same stat GameChanger reports, the burden is on us to prove it reconciles, and to keep proving it as the parser and data sources evolve. This binds all play-ingestion, parser, and reconciliation work: a change that improves one stat's fidelity at the cost of regressing another is not acceptable; the standing direction is the whole-season plays-to-boxscore gap trending toward zero.

This is a direction and a discipline, not a one-time threshold -- quick-scored games, abandoned at-bats, and scorekeeper noise leave an irreducible residual, so a perfect zero is not the bar. See the canonical statement in `docs/VISION.md` ("North Star: Always Get Closer to Byte-Identical Play Ingestion"). The concrete enforcement mechanism (a plays-to-boxscore reconciliation scoreboard, and the rule that ingestion changes must not regress it) is being designed in E-245 and lands when that scoreboard exists; until then, this principle binds intent.

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
- **Public endpoints** require NO authentication -- no `gc-token`, no `gc-device-id`. Four confirmed under `/public/*`: `GET /public/teams/{public_id}` (name, location, record, staff), `GET /public/teams/{public_id}/games` (full game schedule -- completed games with final scores AND upcoming/scheduled games, opponents as free-text names only with no `public_id`, home/away; **caution**: returns perspective-specific game IDs -- the same real-world game gets a different `id` depending on which team's schedule is queried, unlike authenticated `game-summaries` which returns stable `event_id`/`game_stream_id`), `GET /public/teams/{public_id}/games/preview` (near-duplicate of `/games` -- same data minus `has_videos_available`, uses `event_id` instead of `id`; prefer `/games`), and `GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores` (per-game inning-by-inning scoring, R/H/E totals; same `game_stream_id` as authenticated boxscore -- complementary views of the same game). One additional public-path endpoint uses an **inverted URL pattern**: `GET /teams/public/{public_id}/players` (roster -- NOT `/public/teams/`). Both path structures coexist in the API; do not assume all public endpoints follow `/public/*`. Public endpoints use `public_id` slugs (not UUIDs) except game details which uses `game_stream_id` from game-summaries, and may have different field names than authenticated equivalents (see API spec for details).
- **public_id-to-gc_uuid bridge**: When you have a team's `public_id` but need its `gc_uuid` for authenticated endpoints, use `POST /search` filtered by `public_id` to resolve it. See `.claude/rules/gc-uuid-bridge.md` for the full pattern, storage rules, and edge cases.
- **Opponent scouting pipeline**: Uses opponent `public_id` to fetch schedules and rosters via public endpoints, then per-game boxscores via authenticated endpoint; season aggregates are computed from boxscores (season-stats endpoint is Forbidden for non-owned teams). No UUID or following required. See `docs/api/flows/opponent-scouting.md`.
- **Opponent entry duality**: GC has two opponent entry modes -- manual typing (`root_team_id` only) and team lookup (`root_team_id` + `progenitor_team_id`). `progenitor_team_id` present = coach linked via lookup (reliable single-season dedup signal); absent = manual entry. `root_team_id` is a separate namespace from `gc_uuid` -- NEVER store `root_team_id` in the `gc_uuid` column.
- **HTTP discipline**: All requests must present as a normal browser user. See `.claude/rules/http-discipline.md` for headers, session behavior, rate limiting, and pattern hygiene.

## Commands

The `bb` CLI is the primary operator interface. Run `bb --help` for the full command list. Key command groups: `bb status`, `bb creds`, `bb data`, `bb proxy`, `bb db`, `bb report`. `bb report generate` produces a standalone report for any GC `public_id`. `bb report list` shows all generated reports with status and expiry. `bb report cleanup` unlinks the HTML files of expired reports (keeps the `reports` row, nulls `report_path`); the same `cleanup_expired_reports()` also runs opportunistically at the start of `bb report generate`. `bb report verify-aggregates` recomputes the `boxscore_only` season aggregates from per-game rows (perspective-filtered) and diffs them against stored `player_season_*`, reporting per-cell mismatches (empty = consistent; non-empty flags mismatches with a non-zero exit) -- it is the operator parity diagnostic and the Epic C aggregate-integrity cutover gate. `bb report morning-run [--date YYYY-MM-DD] [--dry-run] <team-urls...>` is the cron-invocable scheduled-report driver: for each LSB team (sequentially, in a single process -- a third SQLite writer alongside the admin UI and the CLI), it reads the GC schedule, filters to the target local date (default: today in the venue operating timezone via `operating_today()` / `OPERATING_TIMEZONE`, default `America/Chicago` -- NOT the container's UTC `date.today()`), resolves each upcoming opponent via the resolution ladder, and -- for auto-resolved opponents -- generates a fresh scouting report through the existing `generate_report()` pipeline. Each scheduled slot's outcome is recorded to `scheduled_report_runs` (see `.claude/rules/data-model.md`). For a real (non-dry-run) run it first runs an alerting-config PREFLIGHT and aborts loudly (non-zero exit) if the operator-alert channel cannot deliver (ADMIN_EMAIL unset, or production with `MAILGUN_API_KEY`/`MAILGUN_DOMAIN` unset) -- since the summary email is the only missed-run signal, a dead channel must fail before any work. `--dry-run` prints each slot's three-way resolution outcome plus the eyeball line and generates nothing; an always-sent end-of-run operator summary email is the missed-run signal (silence = something failed). Exit-code contract (a cron/monitor keys on this): the command exits non-zero on a run-body crash, on a failed or skipped end-of-run summary send, or on a misconfigured alerting channel. `bb report map-opponent <root_team_id> <public_id|GC team URL>` (and the `--no-presence` form) is the operator's one-time resolution of an unresolved-but-mappable opponent surfaced by a morning-run line: it UPDATEs the pending `opponent_links` rows keyed on `root_team_id` across all LSB teams to resolved-positive (`resolution_method='operator'`); `--no-presence` takes no target and is the SOLE producer of the operator-declared `no_gc_presence` state (`public_id` NULL, `resolution_method='no_presence'`). The surviving `bb data` commands are data-maintenance passes over already-loaded data: `bb data reconcile` runs plays-vs-boxscore reconciliation (`--dry-run` by default, `--execute` to apply corrections, `--summary` for aggregate stats, `--game-id X` for single-game verbose output); `bb data dedup-players` detects same-team duplicate player entries (cross-perspective UUID mismatch / name variants), groups them into per-`(team_id, season_id)` connected components, COLLAPSES unambiguous single-terminal-name components, and REFUSES ambiguous "forks" (a stub prefix-matching ≥2 distinct fuller names) -- forks are left unmerged, shown in the `--dry-run` preview and emitted as one WARN per fork on `--execute` (`--dry-run` by default, `--execute` to apply; `season_id` is required and auto-derived from the DB -- the sole season is used when exactly one exists, it no-ops on zero, and an explicit `--season-id` is required only when 2+ seasons are present; exits non-zero on merge failure; the CLI owns and commits the season-aggregate recompute). Both the load-path sweep (`dedup_team_players`) and the CLI route through ONE shared planner (`plan_player_dedup` + `execute_collapse`) in `src/db/player_dedup.py`; `bb data backfill-appearance-order` populates `appearance_order` on historical `player_game_pitching` rows from cached boxscore JSON (idempotent -- only updates rows where `appearance_order IS NULL`). **Footgun**: after backfill, recompute the affected season aggregates via `canonical_recompute()` (see Architecture) and confirm with `bb report verify-aggregates` (tracked-team GS is derived from `appearance_order`). `bb data reload-annotated-pitches` (E-245) is a one-time IN-PLACE re-derivation of already-loaded games from stored `play_events.raw_template` -- no API re-fetch and no DELETE: it reclassifies dropped annotated pitches, populates `pitch_type`/`pitch_speed_mph`, recomputes `pitch_count`/`is_first_pitch`/`is_first_pitch_strike`, OR-merges `is_qab` (exclusion-first), and re-derives `batting_team_id` from the fresh `games` row, following the `backfill-appearance-order` operator-maintenance precedent. `bb data fix-self-games` (E-245) corrects the historical `home==away` self-games by re-fetching the affected teams' boxscores via the scouting pipeline (the fixed loader resolves opponents by name) then re-deriving `batting_team_id` in place via `reload_game_plays` (`--dry-run` by default, `--execute` to apply; exits 0 only when the post-run self-game count is 0). `bb data backfill-game-dates` (E-253) is an idempotent operator-maintenance pass that re-derives venue-local `game_date` for existing `games` rows from the recoverable UTC instant (`start_time`), correcting the historical UTC mis-derivation that E-253-04 fixed going-forward (mirrors the `backfill-appearance-order` precedent): 3-tier -- (1) `start_time` + timezone → clean re-derive via `derive_local_date` (see Architecture); (2) `start_time` present, timezone NULL → operating-tz default fallback; (3) `start_time` NULL → left untouched and counted (never fabricated) (`--dry-run` by default, `--execute` to apply).

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
- **Canonical team deletion**: `cascade_delete_team()` and `cleanup_orphan_teams()` in `src/reports/generator.py` — consolidated deletion paths. New team-deletion paths MUST use these functions. Callers (e.g., `src/api/routes/reports_admin.py::_delete_report`) are thin wrappers that delegate cleanup to the canonical helper and add only path-specific concerns (HTTP response shaping, audit logging, flash messages). Callers MUST NOT duplicate cleanup logic in-place.
- **Canonical team-name search**: `search_teams_by_name()` in `src/gamechanger/search.py` — single entry point for all `POST /search` by-team-name calls. Handles the GC punctuation zero-hit quirk (names containing `/`, `'` U+0027, `%`, `#` return zero hits) and Unicode apostrophe trap (indexed names use curly `'` U+2019) transparently via a normalized-name retry. New code MUST NOT call `client.post_json("/search", body={"name": ...}, ...)` directly for team name lookups — use the helper. See `.claude/rules/gc-uuid-bridge.md` for the full quirk, normalization shape, and retry gate.
- **Canonical public_id→gc_uuid resolution**: `resolve_gc_uuid_by_public_id(client, name, public_id)` in `src/gamechanger/search.py` — single paginate-and-filter loop that yields each candidate `gc_uuid` whose hit `public_id` matches exactly. Routes every query through `search_teams_by_name` (NOT `POST /search` directly), so the punctuation/Unicode-apostrophe quirk handling stays centralized; the page-level short-circuits (page-0 empty for a punctuation-dirty name, partial page = no more pages) are owned here. Callers (report generator, own-team opponent resolver) layer their own per-match id validation on the yielded candidates. New public_id-resolution paths MUST use it — do not re-inline the search-and-filter loop.
- **Canonical GC-UUID predicate**: `is_gc_uuid(s)` in `src/gamechanger/url_parser.py` — single source of canonical-UUID matching (the `_UUID_RE` regex lives here only; `ParsedRef.is_uuid` delegates to it). Consolidated three byte-identical `_UUID_RE` copies across `url_parser.py`, `opponents.py`, and `game_loader.py`; the exact anchoring/`IGNORECASE` is load-bearing for `game_loader`'s own-vs-opponent boxscore-key classification, so the pattern must not drift. New canonical-UUID checks MUST call it — do not re-inline the regex.
- **Canonical admin predicate**: `_user_is_admin(conn, user)` (connection-injected, for middleware/`_get_permitted_teams`) and its own-connection wrapper `user_is_admin(user)` in `src/api/auth.py` — single source of the admin check. Admin = `ADMIN_EMAIL` env matches user email OR `users.role = 'admin'`. The reports-admin route module (`reports_admin.py::_require_admin`) delegates to it. New code MUST NOT add another copy of the admin check — delegate to the auth.py predicate.
- **Team access (admin-sees-all)**: `_get_permitted_teams()` in `src/api/auth.py` resolves admins to ALL `teams` rows; non-admins resolve to their explicit `user_team_access` grants. Applies in dev and production. Security-relevant invariant: admins are never gated by `user_team_access`; non-admins always are. Do not reintroduce membership-based auto-grant as the team-access mechanism for admins.
- **Import boundary**: `src/` modules MUST NOT import from `scripts/`. Reusable logic lives in `src/`; scripts are thin wrappers.
- **Repo-root resolution**: Modules in `src/` use `Path(__file__).resolve().parents[N]` for repo-root-relative paths. Never use cwd-relative paths or `sys.path.insert()`.
- **`migrations/` is a Python package**: Has `__init__.py` and is in `pyproject.toml` because `src/db/reset.py` imports from it.
- **Season_id derivation**: `derive_season_id_for_team()` and `ensure_season_row()` — all loaders MUST use these. Callers must unpack the tuple return type.
- **Canonical season-aggregate recompute**: `canonical_recompute(conn, team_id, season_id)` in `src/db/season_aggregates.py` — single entry point for rebuilding `boxscore_only` `player_season_batting`/`player_season_pitching` rows from per-game tables (DELETE+INSERT, perspective-scoped, deterministic Option-B superset columns). Provenance ownership: it owns ONLY `boxscore_only` rows and NEVER touches `full`/`supplemented` (member-authoritative) rows — a player already owning a member row for the scope is excluded from the INSERT so the member row survives. `ScoutingLoader._compute_season_aggregates` and the player-dedup recompute path delegate to it. New recompute paths MUST route through it (do not re-derive the column set or the provenance guard). See `.claude/rules/data-model.md` (Season-Aggregate Parity) for the mixed-provenance scope footgun.
- **Canonical DB-path resolution**: `resolve_db_path(override=None)` in `src/db/paths.py` — single entry point for resolving the SQLite database path (precedence: explicit `override` > `DATABASE_PATH` env, relative resolved against repo root > default `<repo_root>/data/app.db`). The CLI (`bb data`, `bb report`), backup/reset utilities, and the FastAPI app all delegate to it. New DB-path-resolution paths MUST route through `resolve_db_path()` — do not re-implement the override→`DATABASE_PATH`→default cascade inline.
- **Canonical APP_URL resolution**: `get_app_url()` in `src/api/helpers.py` — single read of the `APP_URL` env var with the `http://baseball.localhost:8001` local-dev default (trailing slash stripped). The report generator (`_get_base_url`), reports-admin, and auth routes (magic-link base) all delegate. Production sets `APP_URL` explicitly, so the default only affects local-dev links. New code MUST NOT re-add an inline `os.environ.get("APP_URL", ...)` — use the helper.
- **Canonical production detection**: `is_production()` in `src/api/helpers.py` — single read of `APP_ENV` (`== "production"`, default `development`). `email.py` (send-email tri-state + `validate_alerting_config`), the morning-run CLI alerting preflight, and `routes/auth.py::_is_dev_mode` (which is `not is_production()`) all delegate. New code needing prod-detection MUST route through it — do not re-inline `os.environ.get("APP_ENV", ...) == "production"`. Two intentional non-delegators remain: `src/api/csrf.py` still inlines the check (a tracked follow-up idea — leave it), and `src/api/auth.py`'s DEV_USER_EMAIL guard uses case-insensitive `app_env.lower() == "production"` with an empty default (DIFFERENT fail-safe semantics — MUST NOT be folded into `is_production()`).
- **Canonical operating timezone**: `get_operating_timezone() -> ZoneInfo` and `operating_today(now=None) -> date` in `src/util/timezone.py` — the single venue-local "today" seam. Reads the `OPERATING_TIMEZONE` env var (IANA name, default `America/Chicago`), degrading to the default with a logged WARNING on an invalid zone (never raises). Morning-run's default target date uses `operating_today()` so an evening run in a UTC container does not roll to tomorrow's games. **CE-3 / E-253 `game_date` derivation MUST reuse this seam and MUST NOT introduce a second timezone convention** — import from here.
- **Canonical instant→local-date conversion**: `derive_local_date(start_datetime, tz_name)` in `src/util/timezone.py` — the single converter from a UTC start instant + IANA timezone name to a game's venue-local `"YYYY-MM-DD"` calendar date (returns `None` when `start_datetime` is absent). Relocated here from `src/reports/morning_run.py` in E-253-04 so lower-layer callers can reuse it without inverting the layering (loaders importing from reports); both `morning_run` and `game_loader`/backfill import it from this stdlib-only seam. Pass an IANA name, not a `ZoneInfo` (bridge via `.key`). New instant→local-date derivations MUST use it — do not re-inline a UTC-sliced date, which would miss late-evening games that roll past UTC midnight.
- **Canonical SQLite connection factory**: `get_connection(db_path=None)` in `src/api/db.py` — the single connection factory for every SQLite writer sharing the cross-process WAL file (admin UI, interactive report CLI, morning-run cron). Sets `busy_timeout=30000` + `synchronous=NORMAL` (plus WAL + `foreign_keys`) on every connection so a lock overlap waits instead of raising `database is locked`. INVARIANT: `busy_timeout` is false safety without commit discipline — a writer MUST NOT hold an open write transaction across a network fetch on the shared file (morning-run commits after `ensure_team_row` before the crawl). This covers the scheduled-reports path; the `bb data` writers are a tracked out-of-scope follow-up, not yet routed through the factory.
- **Shared query functions**: Reusable query logic lives in shared functions in `src/api/db.py` (e.g. `get_pitching_workload` / `get_pitching_history` / `build_pitcher_profiles`). These are protected-core seams consumed by the reports flow — the sole forward surface. New query needs that the reports flow consumes belong here.
- **Prevention over cleanup**: Prefer preventing bad data at insert time over building cleanup tools after the fact. Example: `GameLoader._find_duplicate_game()` deduplicates cross-perspective games using a natural key (`game_date` + unordered `{home_team_id, away_team_id}`) before insertion, avoiding the need for post-hoc dedup.
- **Perspective provenance**: Every per-player stat INSERT must include `perspective_team_id` (the team whose API call produced the data). Scouting and reports pipelines use in-memory crawl-to-load (no disk intermediary). See `.claude/rules/perspective-provenance.md` for the full invariant, field classification, and code review checklist.
- See `.claude/rules/architecture-subsystems.md` for subsystem implementation details (plays, spray, reconciliation, LLM, reports, charts, pipelines, two-tier enrichment).

Reports is the SOLE scouting/delivery surface; see `.claude/rules/architecture-subsystems.md` (Reports Package) for the reports flow's serving rules and conventions.
See `.claude/rules/data-model.md` for schema design decisions, table conventions, and column semantics.
See `.claude/rules/admin-ui.md` for admin interface structure, team management flows, and opponent resolution workflow.

## Project Management

Epic/story system managed by the **product-manager**. Epics: `E-NNN`, Stories: `E-NNN-SS`, Research: `E-NNN-R-SS`.

### Key Directories
- `/epics/` -- Active epics and stories; `/.project/archive/` -- Completed/abandoned epics
- `/.project/ideas/` -- Pre-epic ideas (see `.claude/rules/ideas-workflow.md`)
- `/.project/research/` -- Standalone research, POCs, and query artifacts
- `/docs/` -- API specs, architecture docs, domain reference; `/docs/VISION.md` -- Product vision

### Roadmap-Derived Epics
Epics that implement a `docs/ROADMAP.md` §5 slice (sequence A-E) follow the tracking convention defined in `docs/ROADMAP.md` §0 (authoritative): each such epic carries an explicit `## Roadmap` reference back to its §5 slice, and the §0 "Roadmap Tracking" table is updated at two moments -- the planning commit (slice → epic ID, status `PLANNING`) and epic closure (status `COMPLETED`). E-234 (slice A) established this pattern.

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

Dispatch relies on long-lived resumable named subagents (PM and code-reviewer persist across an epic, re-engaged via `SendMessage` with context intact). This requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (set in `.claude/settings.json`); without it the team-coordination tools (`SendMessage` and the shared `Task*` task list) are unavailable and spawned agents are one-shot.
