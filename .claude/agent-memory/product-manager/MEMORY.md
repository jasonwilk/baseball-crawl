# Product Manager -- Agent Memory

## Numbering State
- Next available epic number: E-218
- Next available idea number: IDEA-068
- Before assigning numbers: ALWAYS `ls /epics/` and `ls /.project/ideas/` to avoid collisions

## Project Context
- Project: baseball-crawl -- GameChanger API -> database -> coaching dashboard
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite.
- Architecture: src/ for source (gamechanger/, api/, http/, safety/, cli/), tests/ for tests, data/ for local dev outputs, migrations/ for SQL
- Operator CLI: `bb` command (Typer) -- unified entry point for all operator scripts. src/cli/ package. Entry point in pyproject.toml. Devcontainer-only (not in production image).
- Credentials: short-lived, profile-scoped (_WEB/_MOBILE env keys). Primary web path: `bb creds setup web` (email+password → full login bootstrap, auto-generates device ID). Fallbacks: mitmproxy extractor (auto-detects web/ios), `bb creds import` (curl paste). Mobile: mitmproxy only (iOS client key unknown). Auth-module rule at `.claude/rules/auth-module.md`.
- See CLAUDE.md for full project conventions

## Active Epics

For full details, read the epic file in `/epics/`. Only READY and ACTIVE epics are listed here.

- **E-072** (READY): Proxy Session Ingestion Skill
- **E-073** (READY): API Documentation Validation Sweep
- **E-104** (READY): Athlete Profile Endpoint Probe
- **E-174** (READY): Fix Key Extractor to Search Asset Chunks
- **E-175** (READY): Fix `bb creds import` for POST /auth Curl Commands
- **E-193** (READY): Browser Automation Infrastructure
- **E-217** (READY): NSAA Pitch Count Availability Rules

## Key Architectural Decisions
- Storage: SQLite (WAL mode). Host-mounted at ./data/app.db. Simple file backup via scripts/backup_db.py (no Litestream).
- Serving layer: FastAPI + Jinja2 (Python). Single monolithic app. No TypeScript.
- Deployment: Docker Compose (local + prod). Home Linux server (no VPS, no hosting cost). Cloudflare Tunnel (ingress). App-internal auth (magic links + passkeys). Production: https://bbstats.ai.
- Migrations: numbered SQL scripts (migrations/001_*.sql). No Alembic. apply_migrations.py at startup.
- HTTP layer: src/http/headers.py + src/http/session.py. Dual-header system: BROWSER_HEADERS (Chrome 145/macOS) + MOBILE_HEADERS (iOS Odyssey). create_session(profile="web"|"mobile"). Profile-aware proxy: PROXY_ENABLED + PROXY_URL_WEB/PROXY_URL_MOBILE env vars.
- Dependency management: pip-tools + pyproject.toml dual-source (E-190). Runtime deps in both `pyproject.toml` (`>=` ranges) and `requirements.in` (`~=` ranges). `.in` -> `.txt` via pip-compile. Rule: `.claude/rules/dependency-management.md`.
- ip_outs: innings pitched stored as integer outs (1 IP = 3 outs)
- Mobile credentials (E-075, 2026-03-08): Mobile client key CONFIRMED DIFFERENT from web. iOS app is purely native (no JS bundles). Programmatic mobile refresh blocked on unknown client key.
- FK-safe orphan handling: unknown player_ids get a stub row inserted before the stat row
- Data model (revised 2026-03-31, E-195): Fresh-start schema rewrite in single migration `001_initial_schema.sql` (old 001-008 archived). Key changes: programs table (hs/usssa/legion umbrella entity); teams use INTEGER PK AUTOINCREMENT with gc_uuid/public_id as UNIQUE external identifier columns; `membership_type` (member/tracked) replaces is_owned; `classification` replaces level (varsity/jv/freshman/reserve/8U-14U/legion); team_opponents junction table for opponent relationships; TeamRef dataclass pattern (id/gc_uuid/public_id) for pipeline code; enriched stat columns -- game_stream_id + all counting stats now populated by E-117 (game loader: 12 stats + game_stream_id; season stats: 47 batting + 47 pitching; scouting aggregates: 5 batting + 6 pitching cascade). E-158 added: migration 006 (spray_charts indexes + columns: event_gc_id, created_at_ms, season_id). spray_charts now populated by SprayChartCrawler + SprayChartLoader. E-167 added: migration 007 (idx_teams_name_season_year COLLATE NOCASE index); `src/db/teams.py` with `ensure_team_row()` -- canonical team creation function used by all 8 pipeline INSERT paths. E-195 added: migration 009 (plays + play_events tables with pre-computed is_first_pitch_strike and is_qab flags; partial index for FPS% queries). Plays pipeline: PlaysCrawler + PlaysParser + PlaysLoader. Still unpopulated: bats/throws, splits, batting_order. Auth tables simplified (users/sessions/magic_link_tokens/passkey_credentials/coaching_assignments). E-143 added: migration 002 (users.role column), migration 003 (crawl_jobs table). E-197 added: migration 011 (fix season_id for Rebels 14U -- data correction, USSSA program creation, team 126 assignment). `derive_season_id_for_team()` canonical utility in `src/gamechanger/loaders/__init__.py`. E-198 added: migration 012 (reconciliation_discrepancies table -- per-signal per-player per-team discrepancy records with 5-value status lifecycle). `src/reconciliation/engine.py` with `reconcile_game(conn, game_id, dry_run=True)` and `reconcile_all()`. BF-boundary pitcher attribution correction in execute mode. E-200 added: migration 013 (fix stale season_ids for teams without program_id -- corrects games, plays, player_season_batting, player_season_pitching, team_rosters, spray_charts). E-196 added: migration 014 (start_time TEXT + timezone TEXT on games table). `get_pitching_workload()` in `src/api/db.py` -- shared query for pitching Rest/Last and P(7d) columns on dashboard and standalone reports. E-204 added: migration 015 (`appearance_order INTEGER` on `player_game_pitching`). Game loader populates via `enumerate(stats, start=1)`. Scouting aggregation computes `gs` from `SUM(CASE WHEN appearance_order = 1 ...)`. `bb data backfill-appearance-order` CLI for historical rows. GS/GR display: `{gs}/{g - gs}`, derived at template layer. E-215 added: `src/db/players.py:ensure_player_row()` -- canonical player upsert with length-based name preference (all 7 loader paths migrated). `src/db/player_dedup.py` -- duplicate detection + merge (same-team, prefix-matching names). `bb data dedup-players` CLI (--dry-run/--execute). Post-load dedup sweep in scouting pipeline (two hooks: after boxscore load + after spray load). Cross-perspective UUID mismatch is permanent GC API behavior. `gc_athlete_profile_id` column exists but unpopulated (awaits E-104). E-216 added: `GameLoader._find_duplicate_game()` -- pre-load dedup using natural key (`game_date` + unordered `{home_team_id, away_team_id}`) with doubleheader tiebreakers (`start_time` then score total). `ScoutingLoader._check_duplicate_games()` + `_validate_roster_count()` -- post-load validation (WARNING-only, non-fatal). Prevention-over-cleanup pattern established. Next migration: 016.
- Routing model (2026-03-03): Orchestrator removed (E-030). PM is the direct entry point for all work.
- Auth model (revised 2026-03-26, E-157): ALL users = magic link email + optional passkey. No separate admin login path. Cloudflare Access present but passive (no enforcing policies). Dev bypass via DEV_USER_EMAIL. Role-based access: `users.role` column (admin/user, migration 003). `_require_admin()` accepts EITHER `ADMIN_EMAIL` env var match OR `role='admin'`. Auth tables in 001_initial_schema.sql (folded in during E-100 rewrite).

## User Preferences
- Build it right, no rush
- Coaches see dashboards; user (operator) runs the system
- Multi-team (4 Lincoln levels), multi-season, player tracking across orgs
- CLAUDE.md and shipped code comments describe current implemented reality, NOT future planned state
- Epics/stories describe future work until that work is done
- Archived files are frozen historical records -- do not modify

## Ideas Backlog

Full ideas list: `/.project/ideas/README.md`. Promotable ideas (trigger met or immediately actionable):

- **IDEA-005**: Directory-Scoped Intent Nodes — trigger met (E-002+E-003 complete)
- **IDEA-009**: Per-Player Game Stats + Spray Charts — trigger met (E-002+E-004 complete)
- **IDEA-012**: Crawl Orchestration and Scheduling — all blockers resolved, promotable
- **IDEA-038**: Query-Time Splits and Streaks — trigger met (E-117 complete). Coach MUST HAVE: recent form, doubleheader, season phase.
- **IDEA-040**: Optimistic Pitching Column API Audit — trigger met (E-117 complete)
- **IDEA-043**: Fuzzy Duplicate Team Detection — trigger met (E-155 complete)
- **IDEA-064**: Dashboard-Report Feature Parity — immediately promotable (E-212 shipped). 7 gaps identified.
- **IDEA-066**: League/Level Detection for Pitch Rules — blocked on E-217 completion + first non-HS team tracked
- **IDEA-067**: Catcher-Pitcher Restriction (NSAA) — blocked on E-217 completion + catching innings data availability

## Key Workflow Contract
- Routing model: planning (user -> PM), dispatch (user/main session -> implementers directly). PM plans and closes; main session dispatches.
- PM modes: discover, plan, clarify, triage, close, curate
- Epic lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED)
- READY gate: must be READY/ACTIVE before dispatch. PM sets READY explicitly.
- Dispatch: Main session creates team, spawns implementers + code-reviewer + PM, assigns stories, routes to PM for AC verification and status updates, manages merge-back and cascade.
- Direct-routing exceptions (no PM needed): api-scout, baseball-coach, claude-architect
- Implementing agents needing work auth: software-engineer, data-engineer, docs-writer
- Agent ecosystem: 9 agents (claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer)
- Before assigning epic numbers: ALWAYS ls /epics/ to avoid numbering collisions

## Topic File Index
- [archived-epics.md](archived-epics.md) -- Key milestones and architectural decision points (canonical source: `ls /.project/archive/`)
- [lessons-learned.md](lessons-learned.md) -- Epic authoring patterns, dependency patterns, process patterns, platform constraints
- [mcp-research.md](mcp-research.md) -- MCP server evaluation findings (E-009-R-05, R-06)
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) -- Fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) -- For context-layer epics, CA designs stories; PM frames ACs
