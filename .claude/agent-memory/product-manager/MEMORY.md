# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`; open operator obligations in [operator-followups.md](operator-followups.md). Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
**Counters go STALE and have caused real collisions (E-229, IDEA-071). ALWAYS glob the live dirs before assigning ANY number: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/` `ls migrations/`. Trust the filesystem, not these lines.**
- **Next epic: E-275.** Next idea: **IDEA-183**. Next migration: **013**. (174-182 all filed 2026-07-25 during E-274 planning; 178 = the live NRBL/`ngb` shadowing defect, 179 = the live `Under 13`/`Over 18`/`NNO` fall-through — both E-272-adjacent, both awaiting action. 180 = doc-PII gate coverage, 181 = TBD-placeholder `teams` rows, 182 = USSSA/PG rules-engine forms are UNBUILT not unresolvable.)
- **A PROMOTED idea's Notes are not a backlog.** IDEA-066 recorded the USSSA innings-engine extension in its Notes, was promoted to E-218 which shipped only the detection half, and the remainder was silently retired with the idea — unfiled for 3 months (now IDEA-182). At promotion, re-file anything in the idea the epic does not take.
- **Writing `epics/**` or `.project/**` NOW trips a pre-commit doc-PII byte-gate — never paste a real team name.** The gate is live on both trees (`.githooks/pre-commit` `GATE_TREES`), so real identifiers block the planning commit, not review. Use the fictional taxonomy in `.claude/rules/api-docs.md` (`Anytown`/`Springfield`/`Example`) from the first draft; retrofitting is expensive and lossy. E-274's scheme + its re-verifiability cost note is the worked precedent (see its Background & Context). Never truncate or prefix a real name — that is how IDEA-137 grew ~3×.
- Everything E-273 and below is COMPLETED+archived except the open epics listed below — see [archived-epics.md](archived-epics.md) (canonical: `ls /.project/archive/`). CE-1..CE-5 = E-251..E-255.
- Idea descriptions are NOT duplicated here — `/.project/ideas/README.md` is canonical for all statuses and full text. **One triage note worth keeping: IDEA-168 / 171 / 172 all point at `detect_league_level`.** 171 is now PROMOTED (E-274); if E-274 ships, re-triage 168 and 172 against it — 172 in particular has its blast radius shrunk by E-274.

## Active Epics
Only DRAFT/READY/ACTIVE. Full detail lives in each epic file — do not restate it here.
- **E-274 DRAFT (2026-07-25)** — read GC's `age_group` school family as a structured level signal in `detect_league_level`. Promoted from IDEA-171. ONE production file, no schema/migration/crawl (the generator already fetches and passes the value; SE verified all 7 school values are inert today). 3 stories (01 SE core, 02 SE BLOCKED on prevalence + may be ABANDONED, 04 CA pitch-rules ladder). **03 was REMOVED — its premise was falsified (no level label reaches the coach at ALL today); re-filed as IDEA-177. Its tombstone file needs `git rm` before the planning commit.** **OQ-5 CLOSED (season present 73/73, all `"spring"` — premise inverted, IDEA-168 does NOT sequence first). OQ-6 RETRACTED as INVALID — it claimed "no HS-opponent report has ever been generated"; the operator corrected that dozens have, they are just expired/purged out of the DB. Remaining gates: OQ-1 and OQ-2 (coach re-ruling the Reserve veto, its direction refuted 0/17). The operator holds a build/shrink/shelve call given the 4% measured value; not dispatching at all is a legitimate outcome.** Live run off that escalation: 9/9 reports succeeded, zero orphan deletions, and the 3 Reserve teams are the FIRST real exercise of E-272's NRBL path. Trap to carry forward: within the school family `season` is CONSTANT (all spring), so it cannot disambiguate school tiers — this does NOT contradict E-272's season-is-discriminating finding, which came from a mixed-family summer/legion population. **Value proposition — BOTH populations now measured: spring 3 of 73 (4.1%), summer 4 of 134 (3.0%), and 0 of 207 changes move toward LESS rest.** Rates agree; the MECHANISM is the finding. The spring "0 of 73 no-level-word, signals anti-correlated" claim I had marked do-not-restore is **refuted**: summer has 3 school programs playing under a **SPONSOR name** (no school name, no tier word) where `age_group` is the ONLY level signal — all currently `unknown` → card SUPPRESSED, and **unreachable by any name-parsing improvement**. api-scout's read is BUILD, with an honest ceiling (single digits per schedule, concentrated in currently-suppressed cards); what the data refutes is shelving it *as redundant with the name*. Also refuted from the same spring over-generalisation: "`season` is constant within the school family" — summer has 13 school-family teams, so **season and `age_group` are INDEPENDENT axes**. Two durable cautions, both drawn from the same 73, both wrong as properties of the field. **Carries 3 CLOSURE OBLIGATIONS (in the epic's "Closure Obligations" section) that survive even if the epic is ABANDONED** — file them as ideas at closure: (1) **verdict-reason rot** — a consultation/assessment verdict's stated REASON can rot independently of the verdict, so a "is there a verdict per domain/trigger" check passes cleanly; generalizes to the 8-trigger closure assessment and the ratchet exception; (2) consultation PHRASING drives derivation-vs-compression ("what does X say" vs "confirm X"); (3) removing a story mid-planning orphans refs in ≥4 sections. Settled and not to be relitigated: widen the existing recognized-`age_group` step (do NOT add a rung); **allowlist, NOT a closed enum** (exhaustiveness could not be certified); `middle_*`/`elementary`/`college` **TERMINALLY SUPPRESS**; narrow **Reserve-only veto** on the tie-break.
- **E-271 READY (2026-07-21)** — workflow/process redesign from the E-267 audit (P-1..P-10 in `.project/research/E-271-e267-audit-findings.md`), CA-designed, 3 stories. Ratchet ~+35-55L needs an operator-signed exception. Closure obligations: TN-13 Step-1c external-ref recon + its own Closure-Evidence.
- **E-263 READY (2026-07-13; re-confirm by 2026-09-11)** — Deep Scout v1, 11 stories (chain 02a→02c→02b→04). Settled: operator PICKS competition level at submit; the unset path delegates to `detect_league_level`. Dispatch prereq: `git rm` the tombstone `E-263-02-fact-sheet-foundation-sig-001.md`. **Priority unchanged by E-274** (a populated level field raises the inference floor, not the ceiling operator knowledge covers).
- **Demoted READY→DRAFT by the E-255-06 stale gate; re-confirm before re-promoting:** E-174 (`bb creds extract-key`), E-175 (POST /auth import failures), E-072 (proxy-ingestion skill). E-193 + E-073 were archived ABANDONED.

## Open Operator Obligations
Canonical: [operator-followups.md](operator-followups.md). **The live one that will FAIL a closure gate: the context-ratchet baseline is 4 deferrals stale (+972, mostly inherited agent-memory growth).** Frame it to the operator as "stale for N epics," never as "this epic broke the ratchet."

## Pending Process Obligations
- **CR-vs-Codex gap re-measurement** (E-258-04 item 25): **RETIRED 2026-07-13, operator-CONFIRMED** — not a pending obligation. Kept DORMANT + non-self-triggering; pull ONLY on a fresh defect-cited rubric decision. Detail: [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md).

## Strategic Frame (reports-first reframe, 2026-06-12)
- Reports are the SOLE coaching surface (generate for a GC `public_id` + share link). Dashboard/member-sync/tracked-opponent surfaces REMOVED in E-239 (ROADMAP D2, −59k lines). Admin surface = `src/api/routes/reports_admin.py`. Forward feature = morning-of-game scheduled reports (E-240, `bb report morning-run`).
- Permanent non-goals: cross-team player identity, multi-season rollups, longitudinal tracking.
- `docs/ROADMAP.md` authoritative on scope (slices A–E all COMPLETED). `docs/VISION.md` + `vision-signals.md` **curated 2026-07-05** to the reports-first reframe (multi-program *reach* kept but scoped single-season/any-`public_id`, NOT longitudinal). §3 rationales CODIFIED by E-255-03; see [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) (historical).

## Project Context
- baseball-crawl — GameChanger API → SQLite → coaching scouting reports for Lincoln Standing Bear HS.
- Tech: Python end-to-end. FastAPI + Jinja2 (server-rendered HTML). Docker Compose + Cloudflare Tunnel. SQLite (WAL, `./data/app.db`). Production: https://bbstats.ai.
- Operator CLI: `bb` (Typer), `src/cli/`, devcontainer-only. Groups: status, creds, data, db, report.
- Credentials: short-lived, profile-scoped (`_WEB`/`_MOBILE`). Primary: `bb creds setup web`. Rule: `.claude/rules/auth-module.md`.
- See CLAUDE.md for full conventions; `.claude/rules/data-model.md` for schema decisions.

## Key Architectural Decisions
- Storage: SQLite WAL, host-mounted `./data/app.db`, file backup via `scripts/backup_db.py` (no Litestream). Serving: FastAPI + Jinja2, single monolithic app, no TypeScript.
- Migrations: numbered SQL, no Alembic, applied at startup. History is reconstructable from `migrations/` + `.claude/rules/data-model.md` — do not maintain a second copy here.
- Canonical entry points (new INSERT/UPDATE paths MUST route through these): `ensure_team_row()`, `ensure_player_row()`, `cascade_delete_team()`/`cleanup_orphan_teams()`, `reclaim_orphan_reference_data()`, `merge_duplicate_game()`, `search_teams_by_name()`, `_user_is_admin`/`user_is_admin` + `_get_permitted_teams`, `derive_season_id_for_team()`, `resolve_db_path()`, `get_connection()`. CLAUDE.md's Architecture section is canonical for all of them.
- Season aggregates are **query-time-derived** (E-259 dropped the stored `player_season_*` tables). Surviving invariant: every query-time season sum MUST scope by `perspective_team_id` or it double-counts a two-perspective game.
- **Report generation is DESTRUCTIVE on two axes** (E-267 + E-273): reconcile-at-load can hard-delete `games`, and orphan reclamation can hard-delete unreachable `teams`/`players`. Never describe `bb report generate` as read-only or safe to re-run blindly.
- `ip_outs`: innings pitched stored as integer outs (1 IP = 3 outs).
- Auth (E-157): all users = magic link + optional passkey. Admin = `ADMIN_EMAIL` env OR `users.role='admin'`; admins bypass `user_team_access` (E-228) in dev + prod.
- Mobile credentials (E-075): mobile client key CONFIRMED different from web; programmatic mobile refresh blocked.
- Routing (E-030): orchestrator removed; PM is the direct entry point for work definition.

## User Preferences
- Build it right, no rush. Coaches consume reports; the user (operator) runs the system.
- CLAUDE.md + shipped code/comments describe CURRENT implemented reality, not future plans; epics/stories describe future work until done.
- Archived files are frozen historical records — do not modify.

## Key Workflow Contract
- Routing: planning (user → PM); dispatch (user/main session → implementers directly). PM plans, verifies ACs, owns statuses, and closes; main session spawns/routes/merges.
- PM modes: discover, plan, clarify, triage, close, curate.
- Epic lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED). READY/ACTIVE required before dispatch; PM sets READY explicitly. Dispatch authorization is a separate user call.
- Full-suite-green closure gate (E-230): COMPLETED is authored in the worktree and finalizes only after `python -m pytest tests/` reports 0 failed in main at Step 8; a red gate aborts/reverts.
- Closure gates: documentation assessment + **eight**-trigger context-layer assessment (`.claude/rules/context-layer-assessment.md`), both recorded per-epic before archiving.
- Direct-routing exceptions (no PM): api-scout, baseball-coach, claude-architect.
- 9 agents: claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer.

## Ideas Backlog
Canonical: `/.project/ideas/README.md`. Only the promotable/salient few are named here:
- **IDEA-178 (LIVE DEFECT in E-272, most salient):** `ngb=american_legion` shadows NRBL — coaches tag NRBL teams with the accurate governing body, E-272 made recognized `ngb` authoritative above the bracket, so `legion` returns and **NRBL never fires for the teams it was built for**. Benign ONLY because the two curves are byte-identical today. **RULING IS IN (coach, 2026-07-25) → PROMOTABLE, only prioritisation remains:** refine `american_legion` ONLY (usssa/perfect_game stay fully dispositive — genuinely different rule systems); 15U-16U bracket → nrbl, else a summer sub-varsity NAME word → nrbl (this second rung is what a bracket-only fix would miss), else legion; range-form default overridden to binding nrbl ONLY when ngb=american_legion AND a summer sub-varsity name word are both present, WARN-logged. **Do not fold into E-274** — same function, different decision. Durable lesson: a green suite + passing smoke cannot detect an unreachable branch; only ground truth found it.
- **IDEA-078** (SALIENT since E-255 closure): coaching-docs (`docs/coaching/`) reports-first rewrite — the main remaining stale-dashboard doc surface. Consider promoting.
- **IDEA-080** (PROMOTABLE): coach-facing scheduled report delivery (email links the morning of the game) — the natural next slice after E-240.
- **IDEA-084**: scouting-coverage fill to lift probable-starter accuracy (memo `.project/research/scout-coverage-lever.md`).
- **IDEA-089**: Tier 2 co-occurrence fork disambiguation. Blockers cleared but **0 refused forks live** → no pull; promote only if a real refused-fork case surfaces.
- **IDEA-090**: Codex review/spec-review script modernization (CA owns impl when promoted).
- Reframe-adjacent still-CANDIDATE to reassess: IDEA-018, 022, 043. A large DISCARDED set from the D1/D2 reframe is recorded in the README — check there before re-proposing anything dashboard-shaped.

## Topic File Index
- [archived-epics.md](archived-epics.md) — one-line-per-epic milestone index (canonical source: `ls /.project/archive/`)
- [lessons-learned.md](lessons-learned.md) — epic authoring / dependency / process patterns, platform constraints
- [operator-followups.md](operator-followups.md) — open operator obligations; the context-ratchet drift is the live one
- [mcp-research.md](mcp-research.md) — MCP server evaluation findings
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) — fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) — context-layer epics: CA designs stories, PM frames ACs
- [feedback_acceptance_command_surface_scope.md](feedback_acceptance_command_surface_scope.md) — dispatch failure inside an AC's named command/file is in-scope
- [feedback_clean_reread_before_defect.md](feedback_clean_reread_before_defect.md) — clean re-read + quote literal text before reporting any AC defect
- [feedback_dont_rationalize_weak_assertions.md](feedback_dont_rationalize_weak_assertions.md) — apply the delete-the-behavior teeth test; don't rationalize a no-teeth assertion
- [feedback_record_shrinkage_dont_substitute.md](feedback_record_shrinkage_dont_substitute.md) — retiring a gate: verify the property still EXISTS before proposing a replacement
- [feedback_verify_cited_facts_before_approving.md](feedback_verify_cited_facts_before_approving.md) — glob/grep each cited path before approving a prose correction
- [feedback_reverify_idea_before_folding.md](feedback_reverify_idea_before_folding.md) — re-verify a backlog idea's premise still holds before folding it into an epic (E-262: 2 of 4 were stale)
- [feedback_verify_relayed_claims.md](feedback_verify_relayed_claims.md) — a relayed compound claim is verified only in the half the source directly observed; check the other half before scoping work on it (E-274)
- [feedback_ask_dont_infer_from_db.md](feedback_ask_dont_infer_from_db.md) — ASK the operator about history; the DB is current state, not a record (expiry/cleanup/purge erase it). Operator instruction, E-274
- [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) — 2026-07-05 curation §3 rationales; ✅ CODIFIED by E-255-03, now historical
- [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md) — the RETIRED item-25 obligation; see Pending Process Obligations
