# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`. Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
- **Next available epic number: E-272** (ALWAYS glob `/epics/` + `/.project/archive/` before assigning). READY awaiting operator dispatch (full detail in each epic file): **E-270** (2026-07-21; E-267 reconcile-at-load + purge hardening, 6 stories, `MAX_GAME_RETIREMENTS=2`; closure obl: docs-writer reconciles `operations.md §867-886`); **E-271** (2026-07-21; workflow/process redesign, P-1..P-10 `.project/research/E-271-e267-audit-findings.md`, CA-designed, 3 stories 01 implement-skill→02 code-reviewer + 03 disjoint; ratchet ~+35-55L operator-signed exception; closure obls: TN-13 Step-1c external-ref recon + own Closure-Evidence); **E-263** (Deep Scout v1, 2026-07-13, re-confirm by 2026-09-11 — see Active Epics below). Everything E-269 and below COMPLETED+archived — see [archived-epics.md](archived-epics.md) (canonical `ls /.project/archive/`). CE-1..CE-5 = E-251..E-255.
- **Next available idea number: IDEA-163** (ALWAYS glob `.project/ideas/` — counter goes stale; full descriptions + all statuses in `/.project/ideas/README.md`). Newest: 160=MAX_GAME_RETIREMENTS cap [E-270-01], 161=main-session durable record surface [E-271 CR S-2], 162=Step-1a-vs-1d diff-read tension [E-271 CA Codex-triage]. Promotions: 140→E-267, 141→E-265, 153→E-268; 010/022/105/107/111/113/114/117/118/122/123/126/127/128→E-262.
- Memory numbers go STALE and have caused real collisions (E-229, IDEA-071). Before assigning ANY epic/story/idea number, ALWAYS glob the live dirs: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/`. Trust the filesystem, not these counters.

## Active Epics
Only DRAFT/READY/ACTIVE epics. Full details in the epic file under `/epics/`.
- **E-263 READY (2026-07-13; scope-refined 2026-07-18; re-confirm by 2026-09-11)**: Deep Scout v1 — 9 MUST signals → 4 coach sections, query-time-derived (no migration/crawl), 11 stories (chain 02a→02c→02b→04). Settled (no relitigate): operator PICKS competition level at submit (admin dropdown + `bb report generate` flag; unset→badged Pitch Smart 15-18) — NO team-name inference; gap = operator INPUT + `detect_league_level`. Dispatch prereq: `git rm` tombstone `E-263-02-fact-sheet-foundation-sig-001.md`. All detail/OQ rulings canonical in the epic file. IDEA-131=catalog; 132-135=v2 backlog.
- **Still-open (demoted READY→DRAFT by E-255-06 stale gate; re-confirm before re-promote):** E-174 (`bb creds extract-key`), E-175 (POST /auth import failures), E-072 (proxy-ingestion skill). E-193 + E-073 archived ABANDONED by E-255-06.

Recently completed (2026-07), full per-epic detail in [archived-epics.md](archived-epics.md) (canonical `ls /.project/archive/`): E-267 reconcile-at-load + `bb db purge-scouting` (**reports now DESTRUCTIVE**; the Fable no-continuity review caught a LIVE data-loss defect 12 story-rounds + Codex missed — the reason E-271 exists), E-268 CC-2 score-misattribution fix, E-269 PM READY-gate hardening, E-266/E-265 pitcher outings, E-264 ERA basis, E-262 housekeeping, E-261 game-dedup fidelity, E-260..E-242 (E-259 query-time aggregates, E-257 recon scoreboard, E-258 review-system, E-255..E-251=CE-5..CE-1, E-250 cross-season de-scope, E-245 play ingestion).
- **Operator follow-ups — nearly all DISCHARGED at the 2026-07-12 sweep** (canonical: `.project/research/2026-07-12-program-endgame-sweep.md` §4). **Still open:** (1) PROD backup at next deploy (migration 011); (2) record `FEATURE_PREDICTED_STARTER` promote-to-default decision (audit residual #12); (3) E-262 closure context-ratchet `--update-baseline` re-snapshot (operator-signed); (4) E-262 closure IDEA-137 corpus-wide docs/api doc-PII sweep. Do NOT re-add `backfill-appearance-order` [E-256-02] or `canonical_recompute`/`verify-aggregates` [E-259] — retired.

## Pending Process Obligations
- **CR-vs-Codex gap re-measurement** (E-258-04 item 25): **RETIRED 2026-07-13, operator-CONFIRMED** — NOT a pending obligation (pre-E-251 cohort permanently unanswerable + E-260 meta-freeze proportionality; interim tally ran, structural CR-misses dominate). Corrected forward design kept DORMANT + non-self-triggering; pull ONLY on a fresh defect-cited rubric decision. Detail: [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md).

## Strategic Frame (reports-first reframe, 2026-06-12)
- Reports are the SOLE coaching surface (generate for a GC `public_id` + share link). Dashboard/member-sync/tracked-opponent surfaces REMOVED in E-239 (ROADMAP D2, −59k lines). Admin surface = `src/api/routes/reports_admin.py`. Forward feature = morning-of-game scheduled reports (E-240, `bb report morning-run`).
- Permanent non-goals: cross-team player identity, multi-season rollups, longitudinal tracking.
- `docs/ROADMAP.md` authoritative on scope (slices A–E all COMPLETED). `docs/VISION.md`+`vision-signals.md` **curated 2026-07-05** to the reports-first reframe (multi-program *reach* kept but scoped single-season/any-public_id, NOT longitudinal). §3 context-budget/memory-lifecycle rationales CODIFIED by E-255-03; see [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) (historical).

## Project Context
- baseball-crawl — GameChanger API → SQLite → coaching scouting reports for Lincoln Standing Bear HS.
- Tech: Python end-to-end. FastAPI + Jinja2 (server-rendered HTML). Docker Compose + Cloudflare Tunnel. SQLite (WAL, `./data/app.db`). Production: https://bbstats.ai.
- Operator CLI: `bb` (Typer), `src/cli/`, devcontainer-only. Key groups: status, creds, data, db, report.
- Credentials: short-lived, profile-scoped (`_WEB`/`_MOBILE`). Primary: `bb creds setup web`. Auth-module rule: `.claude/rules/auth-module.md`.
- See CLAUDE.md for full conventions; `.claude/rules/data-model.md` for schema decisions.

## Key Architectural Decisions
- Storage: SQLite WAL, host-mounted `./data/app.db`, file backup via `scripts/backup_db.py` (no Litestream).
- Serving: FastAPI + Jinja2, single monolithic app, no TypeScript.
- Migrations: numbered SQL (`migrations/NNN_*.sql`), no Alembic, applied at startup. **Next migration: 013** (008 = E-250 identity/opponent/season_type drop; 009 = E-253 spray `chart_type` UNIQUE table rebuild; 010 = E-253 game-dedup partial UNIQUE on `game_stream_id`; 011 = E-259 drop of the stored `player_season_batting`/`player_season_pitching` tables, refuse-on-member-row preflight; 012 = E-264 add bare-nullable `teams.innings_per_game` ERA basis). ALWAYS glob `ls migrations/` before assigning a number — this counter goes stale. Full migration history is reconstructable from `migrations/` + `.claude/rules/data-model.md`.
- Canonical entry points (new INSERT/UPDATE paths MUST route through these): `ensure_team_row()` (`src/db/teams.py`), `ensure_player_row()` (`src/db/players.py`), `cascade_delete_team()`/`cleanup_orphan_teams()` (`src/reports/lifecycle.py`), `search_teams_by_name()` (`src/gamechanger/search.py`), `_user_is_admin`/`user_is_admin` + `_get_permitted_teams` (`src/api/auth.py`), `derive_season_id_for_team()`. (`canonical_recompute` retired by E-259 — the stored season-aggregate tables were dropped and the season line is now derived at query time by `get_season_batting`/`get_season_pitching` in `src/api/db.py`.)
- Season-aggregate provenance (E-259 update): the stored `player_season_*` tables are DROPPED — season totals are query-time-derived, so there is no stored aggregate to own/drift. The surviving invariant is the **perspective filter**: every query-time season sum MUST scope by `perspective_team_id` or it double-counts a two-perspective game (the #1 cutover hazard; see `.claude/rules/perspective-provenance.md` MC-3). Every per-player stat INSERT still carries `perspective_team_id`. (Pre-E-259 there was a `full`/`supplemented` member-authoritative vs `boxscore_only` recompute-owned split; moot now — no `full`/`supplemented` writer survived E-239, every row is `boxscore_only`.)
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
- Closure gates: documentation assessment (`.claude/rules/documentation.md`) + **eight**-trigger context-layer assessment (`.claude/rules/context-layer-assessment.md` — E-255-03 added trigger 7 = context-growth counterweight, trigger 8 = reusable-behavioral-lesson closure gate + the Learning-Loop Lifecycle), both recorded per-epic before archiving.
- Direct-routing exceptions (no PM): api-scout, baseball-coach, claude-architect.
- 9 agents: claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer.

## Ideas Backlog
Canonical list: `/.project/ideas/README.md`. Notable recent / promotable:
- **IDEA-089** (E-249): Tier 2 co-occurrence fork disambiguation (auto-collapse genuine same-human forks Jo/John/Jon while still refusing true two-human forks; E-249 refuses ALL). Both blockers cleared but **0 refused forks live** (2026-07-12 sweep) → NO current pull; keep parked, promote only if a real refused-fork case surfaces.
- **IDEA-090** (filed 2026-06-30): Codex review/spec-review script modernization (v0.142.4) — 4 cleanups from the CA+SE tooling A/B (KEEP-custom decision made); CA owns skill-side impl when promoted.
- **IDEA-084** (E-243): scouting-coverage fill to lift probable-starter accuracy (bounded follow-on epic candidate; memo `.project/research/scout-coverage-lever.md`).
- E-243/E-245 niche follow-ons (full detail in README): **086** (pitch-type/velocity in scouting, overlaps 030), **085** (richer LLM data-block translations), **083** (per-arm IP-proxy estimate marker), **088** (no-name opponent sentinel, DISCARD-able), **087** (multi-pitcher-boundary BF drift, recon-engine gap).
- **IDEA-080** (E-240, PROMOTABLE): coach-facing scheduled report delivery (email links the morning of the game) — natural next slice after E-240.
- **IDEA-079**: reliably rich predicted-starter/bullpen LLM narrative.
- **IDEA-078** (SALIENT next candidate as of E-255 closure): coaching-docs (`docs/coaching/`) reports-first rewrite — E-255 truth-swept the context layer + admin/developer docs + own-memory but did NOT touch `docs/coaching/`, so it is now the main remaining stale-dashboard doc surface. Consider promoting.
- DISCARDED from the D1/D2 + reports-first reframe (target surfaces removed): IDEA-033/034/035/036/042/052/064 (034 discarded 2026-07-08 in E-255-06; the rest 2026-06-16) + IDEA-012 (crawl orchestration, E-255-06). Still-CANDIDATE reframe-adjacent to reassess: IDEA-018, 022, 043.

## Topic File Index
- [archived-epics.md](archived-epics.md) — one-line-per-epic milestone index (canonical source: `ls /.project/archive/`)
- [lessons-learned.md](lessons-learned.md) — epic authoring / dependency / process patterns, platform constraints
- [mcp-research.md](mcp-research.md) — MCP server evaluation findings
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) — fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) — context-layer epics: CA designs stories, PM frames ACs
- [feedback_acceptance_command_surface_scope.md](feedback_acceptance_command_surface_scope.md) — dispatch failure inside an AC's named command/file is in-scope
- [feedback_clean_reread_before_defect.md](feedback_clean_reread_before_defect.md) — clean re-read + quote literal text before reporting any AC defect
- [feedback_dont_rationalize_weak_assertions.md](feedback_dont_rationalize_weak_assertions.md) — apply the delete-the-behavior teeth test; don't rationalize a no-teeth assertion
- [feedback_record_shrinkage_dont_substitute.md](feedback_record_shrinkage_dont_substitute.md) — retiring a gate: verify the property still EXISTS before proposing a replacement; plain deletion + trigger-7 offset beats fake symmetry
- [feedback_verify_cited_facts_before_approving.md](feedback_verify_cited_facts_before_approving.md) — when AC-verifying a prose correction, glob/grep each cited path + cross-check id/routing tokens vs the canonical (R-01) artifact before approving (E-255 trigger-8 lesson)
- [feedback_reverify_idea_before_folding.md](feedback_reverify_idea_before_folding.md) — before folding a backlog idea into a housekeeping epic, re-verify its target files still exist AND still show the defect (E-262: 2-of-4 docs-story premises were stale, fixed by unrelated epics before promotion)
- [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) — 2026-07-05 curation §3 rationales (roster refocus, context budget, memory lifecycle) — ✅ CODIFIED by E-255-03 (context-growth counterweight = trigger 7, Learning-Loop Lifecycle = trigger 8, ux/docs-writer charter refocus); handoff is now historical
- [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md) — deferred item-25 obligation (E-258-04): re-tally CR-vs-Codex gap once ≥5 epics close under the canonical Review Scorecard schema; NOT yet run (count=4 of 5 as of the 2026-07-12 sweep) — see Pending Process Obligations
