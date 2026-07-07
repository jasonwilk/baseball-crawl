# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`. Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
- **Next available epic number: E-258** (E-251 created+READY 2026-07-04 = CE-1; E-252–E-256 created as DRAFT stubs 2026-07-04 = CE-2–CE-6 from the platform audit; **E-257 created as DRAFT stub 2026-07-06** = reconciliation-scoreboard productization, DE-owned, dropped-thread from E-245 closure / E-253 planning, NOT a CE item — sequence before/alongside E-256)
- **Next available idea number: IDEA-103** (IDEA-101 + IDEA-102 created 2026-07-07 at E-254 dispatch: 101 = `bb db reset` `.lower()`-only whitespace-bypass [from a CR SHOULD-FIX; canonical `is_production()` now exists], 102 = committed-artifact PII gap [planning/idea/epic files are UNGATED — the pre-commit scanner has `epics/`+`.project/` in SKIP_PATHS & can't detect names, and the byte-gate covers only `docs/api/`; surfaced by a Codex P1 near-miss where a real name was captured into a committed idea file]. IDEA-100 created 2026-07-06 = stat_completeness guard; IDEA-097..099 at E-252 closure; IDEA-093..096 during E-254 planning/review [095 + 096 both UPDATED at E-254 dispatch])
- Memory numbers go STALE and have caused real collisions (E-229, IDEA-071). Before assigning ANY epic/story/idea number, ALWAYS glob the live dirs: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/`. Trust the filesystem, not these counters.

## Active Epics
Only READY/ACTIVE epics. Full details in the epic file under `/epics/`.
- **Platform audit program (2026-07-03)**: adversarial full-platform audit at `PLATFORM-AUDIT.md` (repo root, deliberately UNCOMMITTED — do not commit/modify). User-approved work program CE-1..CE-6 → epics **E-251..E-256**. Sequence: **E-251 (CE-1) COMPLETED + archived 2026-07-05** (was dispatched FIRST), then curate-the-vision, then **E-250 COMPLETED + archived 2026-07-05**, then **E-252 (CE-2) COMPLETED + archived 2026-07-06** → E-253 (CE-3, incl. the F-H1 deletion guard the E-250-02 TN-5 amendment deferred + resume E-245 recon scoreboard) → E-254 (CE-4) → E-255 (CE-5) → E-256 (CE-6, last, incl. query-time-aggregate cutover needing PM/user sign-off). **E-252 (CE-2), E-253 (CE-3), E-254 (CE-4) all COMPLETED + archived** (2026-07-06/07; full detail in [archived-epics.md](archived-epics.md) + the epic files — key seams: E-252 get_connection() busy_timeout factory + is_production() + operating-tz `src/util/timezone.py`; E-253 migrations 009+010, F-H1 deletion guard, `derive_local_date`; E-254 canonical is_production()/validate_app_env + F-H3 PII scanner + doc byte-gate); **E-255 (CE-5) READY 2026-07-07** (refined from stub: R-01 pre-dispatch fact-spike + dispatched set 01–09; 6 domain docket-confirmations + 1 internal review [CR spec audit + 6 holistic] + 3 Codex iterations, ALL findings folded; NOT yet dispatched — "plan with review", dispatch is separate authorization); E-256 remains a DRAFT capture stub, NOT refined — refine to READY before dispatch. E-255-resolved PM-docket decisions (Jason 2026-07-07): **ux-designer/docs-writer charter fate → REPURPOSE both (retire neither)**; **stale-READY ~60-day rule → SKIP (not adopted)**; E-193 → archive ABANDONED + E-073 → archive/shrink (04 owns docs/api) + E-072/174/175 → one-time triage, all executed by E-255-06 at dispatch. Still-open PM-docket items: aggregate-cutover epic sign-off (CE-6), backup-scheduling as required deploy step. E-250 was amended 2026-07-04 pre-dispatch (TN-5 F-H1 caveat + scouting `_ensure_season_row` fold into E-250-02), then dispatched + completed 2026-07-05.
- **E-255** (READY 2026-07-07, CE-5): Truth Sweep — Context Layer, API Docs, Runbooks. R-01 pre-dispatch fact-spike (proxy-first, main-checkout) + Step-0 runbook `git mv` into docs/admin/, then dispatched set 01–09 (CA rules/charters/§3-codification, api-scout endpoint docs, docs-writer runbooks, PM hygiene, coach/DE/ux own-memory sweeps). Not a ROADMAP §5 slice → no §0 planning-commit owed.
- **E-072** (READY): Proxy Session Ingestion Skill — ⚠️ stale-READY, E-255-06 triages disposition at E-255 dispatch
- **E-073** (READY): API Documentation Validation Sweep — ⚠️ Jason decided archive/shrink (E-255-04 owns docs/api corrections); E-255-06 executes
- **E-174** (READY): Fix Key Extractor to Search Asset Chunks — ⚠️ stale-READY, E-255-06 triages
- **E-175** (READY): Fix `bb creds import` for POST /auth Curl Commands — ⚠️ stale-READY, E-255-06 triages
- **E-193** (READY→ABANDONED pending): Browser Automation Infrastructure — Jason decided archive ABANDONED (dashboard premise deleted, agent-browser never installed); E-255-06 executes the archive

Recently completed epics are one-line-indexed in [archived-epics.md](archived-epics.md) (canonical: `ls /.project/archive/`). Most recent (full per-epic detail in [archived-epics.md](archived-epics.md)): **E-254** (2026-07-07, CE-4) Security & PII Hardening — canonical `is_production()`/`validate_app_env()`, magic-link GET/POST split, auth hardening (passkey single-use, atomic KIND_LOGIN cap), F-H3 PII scanner (fail-closed) + endpoint-doc byte-gate `scripts/check_doc_pii.sh`; ideas 093-096 + 101/102; next=011. **E-253** (2026-07-06, CE-3) Data-Integrity & Deletion Safety — F-H1 shared-game deletion guard (lifted the operator no-report-deletions hold, discharged the E-250-02 TN-5 deferred guard), migrations 009 (spray chart_type UNIQUE) + 010 (game-dedup partial UNIQUE), `game_date` operating-tz derivation + `derive_local_date` in `src/util/timezone.py`, `bb data backfill-game-dates`; next=011; IDEA follow-ups on live-DB apply. **E-252** (2026-07-06, CE-2) Scheduled-Reports Reliability — get_connection() busy_timeout factory + commit-before-network + reserve-before-generate, F-H2 slot-wipe, per-team isolation + systemic-429, guaranteed summary heartbeat + is_production() seam, operating-tz seam, reaper, report-serve 404 race; IDEA-097/098/099. **E-250** Root Cross-Season/Multi-Season De-Scope (migration 008 drops `gc_athlete_profile_id`+`team_opponents`+`season_type`; dedup season-scoped; `ensure_season_row` fail-loud + scouting fold; cleanup guards 4→2 w/ F-H1 caveat → shared-game guard owned by CE-3/E-253; context-layer+docs+API-doc de-scope; `PlayerTeamSeason` purged from all loaded context+agent-memory; E-104 archived ABANDONED; **API-doc-fidelity principle** codified → [[feedback-api-doc-endpoint-fidelity]]; token-grep de-scope gap lesson → [[feedback-descope-grep-gap]]; full-suite 3526/0; **Migration NEXT=009**); **E-251** Dispatch-Machinery Repair (CE-1, dispatched FIRST; F-H5 closure-reset + abort-path fixes, F-H4 routing-by-name, hook hardening); **E-249** Player-Dedup connected-components (no-cross-merge); **E-248/247/246** /simplify sweep waves 3/2/1; **E-245** high-fidelity play ingestion; **E-242** subagent-framing vocab.
- **Operator follow-ups owed** (need creds/live DB): **E-245** — run `bb data reload-annotated-pitches` + `bb data fix-self-games` (23→0; verify team-133 FPS 3.4%→~64%, P-PA→~2.7); **E-249** — re-run dedup on live DB, count team_id=196 refused-fork residuals (validates IDEA-089); **E-253** (3) — (a) mig-010 apply may fail-and-rollback cleanly if the live DB already holds two rows sharing one non-null `game_stream_id` → surfaces a real duplicate for cleanup; (b) check live DB for legacy NULL `appearance_order` rows → if found, `bb data backfill-appearance-order` → `canonical_recompute` → `bb report verify-aggregates` (GS Watch-List discharge); (c) run `bb data backfill-game-dates --execute` to correct historical UTC-mis-derived `game_date` values.

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
- Migrations: numbered SQL (`migrations/NNN_*.sql`), no Alembic, applied at startup. **Next migration: 011** (008 = E-250 identity/opponent/season_type drop; 009 = E-253 spray `chart_type` UNIQUE table rebuild; 010 = E-253 game-dedup partial UNIQUE on `game_stream_id`). ALWAYS glob `ls migrations/` before assigning a number — this counter goes stale. Full migration history is reconstructable from `migrations/` + `.claude/rules/data-model.md`.
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
