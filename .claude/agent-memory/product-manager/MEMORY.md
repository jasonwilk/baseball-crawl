# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`. Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
- **Next available epic number: E-245**
- **Next available idea number: IDEA-086**
- Memory numbers go STALE and have caused real collisions (E-229, IDEA-071). Before assigning ANY epic/story/idea number, ALWAYS glob the live dirs: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/`. Trust the filesystem, not these counters.

## Active Epics
Only READY/ACTIVE epics. Full details in the epic file under `/epics/`.
- **E-072** (READY): Proxy Session Ingestion Skill
- **E-073** (READY): API Documentation Validation Sweep
- **E-104** (READY): Athlete Profile Endpoint Probe
- **E-174** (READY): Fix Key Extractor to Search Asset Chunks
- **E-175** (READY): Fix `bb creds import` for POST /auth Curl Commands
- **E-193** (READY): Browser Automation Infrastructure
- **E-242** (READY): Align Dispatch Vocabulary to Subagents — context-layer vocab/breakage fix (TeamCreate/TeamDelete removed in CC v2.1.178; Option B named-subagent framing, keep `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, no behavioral change). Surgical scope (user-confirmed): remove only TeamCreate/TeamDelete ceremony + `[team-name]` placeholder + explicit create/delete-team STEP framing; KEEP "team"/"teammate" collective nouns. CA-led, 3 file-disjoint stories. Planning Scorecard 16/16/0. NOT dispatched (stops at READY).

Recently completed epics (E-218 — E-244) are one-line-indexed in [archived-epics.md](archived-epics.md). Most recent: **E-244** (file plays & spray under canonical game IDs after cross-perspective dedup, COMPLETED + archived 2026-06-28).

## Strategic Frame (reports-first reframe, 2026-06-12)
- Reports are the SOLE coaching surface (generate report for a GC `public_id` + share link). Dashboard / member-sync / tracked-opponent surfaces were REMOVED in E-239 (ROADMAP D2, −59k lines). Admin surface = `src/api/routes/reports_admin.py`.
- Forward feature shipped: morning-of-game scheduled reports (E-240, `bb report morning-run`).
- Permanent non-goals: cross-team player identity, multi-season rollups, longitudinal tracking.
- `docs/ROADMAP.md` is authoritative on scope (slices A–E all COMPLETED: A=E-234, B=E-235, B2=E-236, C=E-237, D1=E-238, D2=E-239, E=E-240). `docs/VISION.md` + `docs/vision-signals.md` still describe the OLD multi-surface vision and await a "curate the vision" session (PM strongly recommends one — large unprocessed signal backlog, last curated 2026-03-13).

## Project Context
- baseball-crawl — GameChanger API → SQLite → coaching scouting reports for Lincoln Standing Bear HS.
- Tech: Python end-to-end. FastAPI + Jinja2 (server-rendered HTML). Docker Compose + Cloudflare Tunnel. SQLite (WAL, `./data/app.db`). Production: https://bbstats.ai.
- Operator CLI: `bb` (Typer), `src/cli/`, devcontainer-only. Key groups: status, creds, data, db, report.
- Credentials: short-lived, profile-scoped (`_WEB`/`_MOBILE`). Primary: `bb creds setup web`. Auth-module rule: `.claude/rules/auth-module.md`.
- See CLAUDE.md for full conventions; `.claude/rules/data-model.md` for schema decisions.

## Key Architectural Decisions
- Storage: SQLite WAL, host-mounted `./data/app.db`, file backup via `scripts/backup_db.py` (no Litestream).
- Serving: FastAPI + Jinja2, single monolithic app, no TypeScript.
- Migrations: numbered SQL (`migrations/NNN_*.sql`), no Alembic, applied at startup. **Next migration: 007** (post-E-241). Full migration history is reconstructable from `migrations/` + `.claude/rules/data-model.md`.
- Canonical entry points (new INSERT/UPDATE/recompute paths MUST route through these): `ensure_team_row()` (`src/db/teams.py`), `ensure_player_row()` (`src/db/players.py`), `cascade_delete_team()`/`cleanup_orphan_teams()` (`src/reports/generator.py`), `canonical_recompute()` (`src/db/season_aggregates.py`), `search_teams_by_name()` (`src/gamechanger/search.py`), `_user_is_admin`/`user_is_admin` + `_get_permitted_teams` (`src/api/auth.py`), `derive_season_id_for_team()`.
- Provenance-ownership: `full`/`supplemented` season rows are member-authoritative; `boxscore_only` is recompute-owned (canonical_recompute owns only boxscore_only). Every per-player stat INSERT carries `perspective_team_id`.
- `ip_outs`: innings pitched stored as integer outs (1 IP = 3 outs).
- Auth model (E-157): all users = magic link + optional passkey; no separate admin login. Admin = `ADMIN_EMAIL` env OR `users.role='admin'`. Admins bypass `user_team_access` (admin-sees-all, E-228) in dev + prod.
- Mobile credentials (E-075): mobile client key CONFIRMED different from web; programmatic mobile refresh blocked.
- Routing model (E-030): orchestrator removed; PM is the direct entry point for work definition.

## User Preferences
- Build it right, no rush. Coaches consume reports; the user (operator) runs the system.
- CLAUDE.md + shipped code/comments describe CURRENT implemented reality, not future plans; epics/stories describe future work until done.
- Archived files are frozen historical records — do not modify.

## Key Workflow Contract
- Routing: planning (user → PM); dispatch (user/main session → implementers directly). PM plans, verifies ACs, owns statuses, and closes; main session spawns/routes/merges.
- PM modes: discover, plan, clarify, triage, close, curate.
- Epic lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED). READY/ACTIVE required before dispatch; PM sets READY explicitly. Dispatch authorization is a separate user call.
- Full-suite-green closure gate (E-230): COMPLETED is authored in the worktree and finalizes only after `python -m pytest tests/` reports 0 failed in main at Step 8; a red gate aborts/reverts.
- Closure gates: documentation assessment (`.claude/rules/documentation.md`) + six-trigger context-layer assessment (`.claude/rules/context-layer-assessment.md`), both recorded per-epic before archiving.
- Direct-routing exceptions (no PM): api-scout, baseball-coach, claude-architect.
- 9 agents: claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer.

## Ideas Backlog
Canonical list: `/.project/ideas/README.md`. Notable recent / promotable:
- **IDEA-085** (filed 2026-06-28, E-243): richer LLM data-block field-translations to match the Variant A SOT exactly (null-pitch IP-proxy numeric form + structured UNAVAILABLE rows); both AC-8-compliant today, refinement needs richer engine output.
- **IDEA-084** (E-243): scouting-coverage fill to lift probable-starter accuracy (lever A: report-time opponent completed-schedule fill; ~40%→50-55% top-2). Bounded follow-on epic candidate; memo `.project/research/scout-coverage-lever.md`.
- **IDEA-083** (E-243): per-arm estimate marker for IP-proxied arms in non-estimate sections (deferred; promote if proven common or a coach is misled).
- **IDEA-080** (E-240, PROMOTABLE): coach-facing scheduled report delivery (email links the morning of the game) — natural next slice after E-240.
- **IDEA-079**: reliably rich predicted-starter/bullpen LLM narrative.
- **IDEA-078**: coaching-docs reports-first rewrite (largely delivered via E-239 doc gate).
- DISCARD candidates from D1/D2 reframe (target surfaces removed): IDEA-018, 022, 034, 035, 036, 043, 064.

## Topic File Index
- [archived-epics.md](archived-epics.md) — one-line-per-epic milestone index (canonical source: `ls /.project/archive/`)
- [lessons-learned.md](lessons-learned.md) — epic authoring / dependency / process patterns, platform constraints
- [mcp-research.md](mcp-research.md) — MCP server evaluation findings
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) — fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) — context-layer epics: CA designs stories, PM frames ACs
- [feedback_acceptance_command_surface_scope.md](feedback_acceptance_command_surface_scope.md) — dispatch failure inside an AC's named command/file is in-scope
- [feedback_clean_reread_before_defect.md](feedback_clean_reread_before_defect.md) — clean re-read + quote literal text before reporting any AC defect
- [feedback_dont_rationalize_weak_assertions.md](feedback_dont_rationalize_weak_assertions.md) — apply the delete-the-behavior teeth test; don't rationalize a no-teeth assertion
