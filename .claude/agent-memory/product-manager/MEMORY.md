# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`. Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
- **Next available epic number: E-250** (E-249 created 2026-06-30, player-dedup stale-worklist fix)
- **Next available idea number: IDEA-091** (IDEA-090 created 2026-06-30, codex review-script modernization)
- Memory numbers go STALE and have caused real collisions (E-229, IDEA-071). Before assigning ANY epic/story/idea number, ALWAYS glob the live dirs: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/`. Trust the filesystem, not these counters.

## Active Epics
Only READY/ACTIVE epics. Full details in the epic file under `/epics/`.
- **E-072** (READY): Proxy Session Ingestion Skill
- **E-073** (READY): API Documentation Validation Sweep
- **E-104** (READY): Athlete Profile Endpoint Probe
- **E-174** (READY): Fix Key Extractor to Search Asset Chunks
- **E-175** (READY): Fix `bb creds import` for POST /auth Curl Commands
- **E-193** (READY): Browser Automation Infrastructure

Recently completed epics (E-218 — E-249) are one-line-indexed in [archived-epics.md](archived-epics.md). Most recent: **E-249** (Player-Dedup Stale-Worklist Fix — replaced the stale up-front merge worklist with per-`(team_id, season_id)` connected-components grouping: collapse only single-terminal-NAME components, REFUSE any fork = ≥2 DISTINCT-named terminals (equal-named two-UUID members still collapse via the existing tiebreak — keying on terminal COUNT would have regressed the modal same-name cross-perspective duplicate), no cross-merge by construction, one txn/component, season rows via `_delete_or_repoint_season_rows`. ONE shared planner `plan_player_dedup`/`execute_collapse` consumed by both the load path and the CLI (CLI stopped re-inlining its loop + got a recompute-commit fix + non-zero exit on merge failure + refused-fork surfacing in dry-run/WARN). Refused forks = WARN-log-only (user decision; durable surfacing → IDEA-089 Tier 2). **Phase 4b Codex P1 (FIXED)**: planner originally grouped components by team_id ONLY → unscoped CLI unioned prefix-pairs across seasons; remediated by per-`(team_id, season_id)` partition (`find_duplicate_players` now carries season_id). **KNOWN LIMITATION (documented per user, NOT fixed/NOT an idea)**: unscoped multi-season execute where the SAME dup player_id has DIFFERENT canonicals across seasons commits one guessed cross-season resolution — UNREACHABLE on the live single-season (2026) DB, load path immune, cross-season identity is a Non-Goal. Scorecards: spec-review 10/10/0; post-dev 6 findings/5 fixed/0 dismissed/1 documented. Doc trigger fired (docs-writer refreshed `bb data dedup-players` in operations.md); context-layer 4/6 fired (CLAUDE.md + data-model.md codified by CA). Full-suite 3524 passed/0. COMPLETED + archived 2026-06-30. **Operator follow-up owed**: re-run dedup on live DB, count team_id=196 refused-fork residuals (validates IDEA-089)). Prior: **E-248** (GC API Client Error-Ladder Refactor — wave 3 of the whole-project /simplify sweep, sole HIGH-blast-radius theme H5. Pure zero-behavior-change dedup of the 4 LIVE client verbs (get/get_public/get_paginated/post_json) into one private `_send_with_retries` helper; old `_get_with_retries` subsumed; net −129 lines in client.py. Test-first: E-248-01 pinned a 6-test per-verb characterization suite (anchored on the public verbs, not the private helper); E-248-02 kept it green with ZERO assertion changes (94 passed against the refactored code) — the unchanged suite is the equivalence proof. Dead verbs post()/delete() were deleted in E-246-07 (not here), dissolving the original 5xx-gap. 1 CR integration-review SHOULD FIX (stale comment) remediated; Codex clean. Full-suite 3505 passed/0. No documentation impact; context-layer all six triggers NO (the helper is a localized private seam, not a project-wide convention). COMPLETED + archived 2026-06-30). Prior: **E-247** (Twin-Method & Duplicated-Block Extractions — wave 2 of the whole-project /simplify sweep; 7 stories, each collapsing a twin-method/duplicated-block pattern to one source: loader in-memory/disk twins, reconciliation detection block, public_id→gc_uuid search seam + `is_gc_uuid` helper, credential/auth core (env-merge/profile-check/JWT-decode/proxy-config), reports plays-scope SQL + `_EMPTY_PLAYS_TEAM`/`_utcnow_iso`, renderer/prediction stat-math + dates, API middleware/auth 503-handler/auth-lookup/`get_app_url`. All byte-identical except the ONE sanctioned APP_URL dev-default unification — REVERSED at closure to `baseball.localhost:8001` for auth-origin coherence with the dev WebAuthn host, making the net magic-link change ZERO (the report-link dev-default move is the sole behavior change). HARD GATE held via per-story golden/characterization pytest. **Phase 4b Codex caught a real regression**: E-247-01 dropped the in-memory empty-boxscores early-return, so `canonical_recompute` ran unconditionally and would DELETE+rewrite populated-DB `boxscore_only` aggregates — remediated by restoring the per-path guard + a populated-DB stale-disagreeing characterization test (the fresh-DB golden had no teeth on it). E-247-04/-07 CA SECURITY-CLEAN. Closure gates: full-suite 3499 passed/0; `verify-aggregates` clean (10208 cells, 0 mismatches). Context-layer codified: CLAUDE.md canonical-seam bullets (`is_gc_uuid`/`get_app_url`/`resolve_gc_uuid_by_public_id`) + dev-URL standardized to `baseball.localhost:8001`; data-model.md twin-method-collapse + populated-fixture footgun. COMPLETED + archived 2026-06-30). Prior: **E-246** (Dead-Code Removal & Low-Risk Consolidation — wave 1; canonical `resolve_db_path()`, shared aggregate-parity builders, dead gc_uuid resolver/client verbs removed; full-suite 3441/0, verify-aggregates clean; archived 2026-06-30); **E-242** (dispatch/plan/implement → subagent-framing vocab fix; archived 2026-06-29); **E-245** (high-fidelity play ingestion — annotated pitches + type/velocity, charted-PA denominator, self-game fix; archived 2026-06-29). **Operator follow-up owed (E-245)**: run the live `bb data reload-annotated-pitches` pass + the `bb data fix-self-games` 23→0 run (need creds/live DB; verify team-133 FPS 3.4%→~64%, P-PA→~2.7).

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
- Migrations: numbered SQL (`migrations/NNN_*.sql`), no Alembic, applied at startup. **Next migration: 008** (007 = E-245 `play_events.pitch_type`/`pitch_speed_mph`). Full migration history is reconstructable from `migrations/` + `.claude/rules/data-model.md`.
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
- **IDEA-089** (filed 2026-06-30, E-249): Tier 2 co-occurrence fork disambiguation — use same-game co-occurrence between component terminals to auto-collapse GENUINE same-human forks (Jo/John/Jon) while still refusing true two-human forks (O/Oliver/Owen); E-249 conservatively refuses ALL forks. May add durable operator surfacing of refused forks. PARTIALLY unblocked at E-249 closure: the E-249 dependency cleared but the second blocker (live team_id=196 residual-count validation = the owed operator follow-up) has NOT run. Do not promote until that residual count exists.
- **IDEA-090** (filed 2026-06-30): Codex review/spec-review script modernization (v0.142.4) — 4 cleanups from the CA+SE tooling A/B (KEEP-custom decision made); CA owns skill-side impl when promoted.
- **IDEA-088** (filed 2026-06-29, E-245): per-game sentinel for genuinely no-name unresolvable opponents — shared "Unknown Opponent" stub + `_find_duplicate_game` natural-key could conflate two no-name opponents on same team+date; reviewer awareness-only (AC-2 sanctioned shared stub), unreached today (real 23 self-games resolve by name). DISCARD-able if no-name path never fires in prod.
- **IDEA-087** (filed 2026-06-29, E-245): cause-4 multi-pitcher-boundary attribution drift (+23 BF outlier `e283438c`, NOT a self-game; within-game pitcher-boundary mis-assignment; likely a recon-engine BF-corrector gap). Scoped OUT of E-245.
- **IDEA-086** (filed 2026-06-29, E-245): leverage pitch selection + velocity in scouting — E-245 STORES per-pitch `pitch_type`/`pitch_speed_mph`; future pitch-mix/sequencing/velocity in reports. Scorekeeper-coverage dependent; overlaps IDEA-030.
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
