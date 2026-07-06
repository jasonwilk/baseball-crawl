# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`. Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
- **Next available epic number: E-257** (E-251 created+READY 2026-07-04 = CE-1; E-252–E-256 created as DRAFT stubs 2026-07-04 = CE-2–CE-6 from the platform audit)
- **Next available idea number: IDEA-093** (IDEA-091 + IDEA-092 created 2026-07-03 during E-250 planning)
- Memory numbers go STALE and have caused real collisions (E-229, IDEA-071). Before assigning ANY epic/story/idea number, ALWAYS glob the live dirs: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/`. Trust the filesystem, not these counters.

## Active Epics
Only READY/ACTIVE epics. Full details in the epic file under `/epics/`.
- **Platform audit program (2026-07-03)**: adversarial full-platform audit at `PLATFORM-AUDIT.md` (repo root, deliberately UNCOMMITTED — do not commit/modify). User-approved work program CE-1..CE-6 → epics **E-251..E-256**. Sequence: **E-251 (CE-1) COMPLETED + archived 2026-07-05** (was dispatched FIRST), then curate-the-vision, then **E-250 COMPLETED + archived 2026-07-05**, then E-252 (CE-2) → E-253 (CE-3, incl. the F-H1 deletion guard the E-250-02 TN-5 amendment deferred + resume E-245 recon scoreboard) → E-254 (CE-4) → E-255 (CE-5) → E-256 (CE-6, last, incl. query-time-aggregate cutover needing PM/user sign-off). E-252 READY 2026-07-05 (10 stories; internal review iter-1 [17 findings] + Codex iter-1 [5 findings] all incorporated, 0 dismissed; awaiting separate user dispatch authorization — plan-only trigger, NOT dispatched): F-H2 slot-wipe, per-team isolation + systemic-429 escalation, summary-email guarantee, 429 client cap (60s), operating-tz seam (CE-2 INTRODUCES it, CE-3 reuses), get_connection() busy_timeout=30000+synchronous=NORMAL factory, write-txn/slot-lifecycle, stuck-generating reaper, team_resolver hardening, + E-252-10 report-serve 500-vs-404 race (user-added beyond the stub's Absorbed set). Expert-designed w/ DE+api-scout+SE. GAP A (CLI factory-routing owned by E-252-06), GAP B (04=scouting.py not morning_run.py) resolved. GC 429 is UNOBSERVED (designed-not-tuned). **E-253 (CE-3) READY 2026-07-06** (see its own line below); E-254..E-256 remain DRAFT capture stubs (scope + absorbed findings + owners + sequence), NOT refined — refine to READY before dispatch. PM-docket items needing user decisions: aggregate-cutover epic sign-off, ux-designer/docs-writer charter fate, stale-READY re-confirmation rule, backup-scheduling as required deploy step. E-250 was amended 2026-07-04 pre-dispatch (TN-5 F-H1 caveat + scouting `_ensure_season_row` fold into E-250-02), then dispatched + completed 2026-07-05.
- **E-072** (READY): Proxy Session Ingestion Skill
- **E-073** (READY): API Documentation Validation Sweep
- **E-174** (READY): Fix Key Extractor to Search Asset Chunks
- **E-175** (READY): Fix `bb creds import` for POST /auth Curl Commands
- **E-193** (READY): Browser Automation Infrastructure
- **E-252** (READY, CE-2): Scheduled-Reports Reliability (Cron-Grade Morning-Run) — 10 stories; awaiting user dispatch authorization
- **E-253** (READY, CE-3): Data-Integrity & Deletion Safety — 11 stories (SE=8, DE=3, coach-advisory on Tier-2); absorbs F-H1 (HIGH) + 6 med + 7 low + GS Watch-List. Headline **E-253-01 F-H1 shared-game deletion guard** (discharges the E-250-02 TN-5 deferred guard, lifts the operator no-deletions hold). DE: spray `chart_type` UNIQUE **mig 009** (table rebuild, verify-by-regen), migration-runner atomicity, game-dedup partial UNIQUE **mig 010** (gated `game_stream_id IS NOT NULL`, doubleheader-safe). SE: game_date operating-tz derivation + `derive_local_date` relocation (**blockedBy E-252**, reuses E-252-05 seam via `ZoneInfo.key`) + 3-tier backfill subcommand, stat-key drift canary (core keys = `_BATTING_MAIN`/`_PITCHING_MAIN`+IP, batting+pitching only) + 0-0 coercion, Tier-2 suppress gate, player-dedup Unicode-fold/LIKE-escape/boxscore_only-scope, reconcile atomicity + perspective partition, GS mixed-`appearance_order` pin. "Align, don't build" the E-245 scoreboard (Non-Goal; canary+reconcile designed scoreboard-compatible). Expert-designed (SE/DE/coach). Reviews: internal iter-1 (CR 4 + holistic 4) + Codex iter-1 (2) → **8 accepted / 2 dismissed**. Closure items owed: data-model.md ~16% coverage-claim correction, `derive_local_date` relocation note, new `bb data` backfill subcommand (all CA/docs at closure); operator follow-ups: game_date backfill run, GS legacy-NULL live-DB check. Awaiting user dispatch authorization. **Migration NEXT after E-253 = 011.**

Recently completed epics are one-line-indexed in [archived-epics.md](archived-epics.md) (canonical: `ls /.project/archive/`). Most recent (all 2026-07-05 unless noted): **E-250** Root Cross-Season/Multi-Season De-Scope (migration 008 drops `gc_athlete_profile_id`+`team_opponents`+`season_type`; dedup season-scoped; `ensure_season_row` fail-loud + scouting fold; cleanup guards 4→2 w/ F-H1 caveat → shared-game guard owned by CE-3/E-253; context-layer+docs+API-doc de-scope; `PlayerTeamSeason` purged from all loaded context+agent-memory; E-104 archived ABANDONED; **API-doc-fidelity principle** codified → [[feedback-api-doc-endpoint-fidelity]]; token-grep de-scope gap lesson → [[feedback-descope-grep-gap]]; full-suite 3526/0; **Migration NEXT=009**); **E-251** Dispatch-Machinery Repair (CE-1, dispatched FIRST; F-H5 closure-reset + abort-path fixes, F-H4 routing-by-name, hook hardening); **E-249** Player-Dedup connected-components (no-cross-merge); **E-248/247/246** /simplify sweep waves 3/2/1; **E-245** high-fidelity play ingestion; **E-242** subagent-framing vocab.
- **Operator follow-ups owed** (need creds/live DB): **E-245** — run `bb data reload-annotated-pitches` + `bb data fix-self-games` (23→0; verify team-133 FPS 3.4%→~64%, P-PA→~2.7); **E-249** — re-run dedup on live DB, count team_id=196 refused-fork residuals (validates IDEA-089).

## Strategic Frame (reports-first reframe, 2026-06-12)
- Reports are the SOLE coaching surface (generate report for a GC `public_id` + share link). Dashboard / member-sync / tracked-opponent surfaces were REMOVED in E-239 (ROADMAP D2, −59k lines). Admin surface = `src/api/routes/reports_admin.py`.
- Forward feature shipped: morning-of-game scheduled reports (E-240, `bb report morning-run`).
- Permanent non-goals: cross-team player identity, multi-season rollups, longitudinal tracking.
- `docs/ROADMAP.md` is authoritative on scope (slices A–E all COMPLETED: A=E-234, B=E-235, B2=E-236, C=E-237, D1=E-238, D2=E-239, E=E-240). `docs/VISION.md` + `docs/vision-signals.md` were **curated 2026-07-05** and now reflect the reports-first reframe: VISION rewritten (Layers 3/4/5 replaced with Scouting Reports + tools-hub; Explicit Non-Goals added barring cross-season/cross-team machinery; multi-program *reach* kept PROMINENT per Jason's D2 but scoped single-season/any-public_id only, NOT longitudinal). 29 signals cleared, 15 kept parked. §3 roster-review/context-budget/memory-lifecycle rationales captured for CE-5 — see [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md).

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
- [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) — 2026-07-05 curation §3 rationales (roster refocus, context budget, memory lifecycle) for CE-5 claude-architect to codify
