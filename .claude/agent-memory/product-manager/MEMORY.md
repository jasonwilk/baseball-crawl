# Product Manager -- Agent Memory

This is an INDEX. Detailed per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`; open operator obligations in [operator-followups.md](operator-followups.md). Keep this file lean (< 17KB) — move detail to topic files, one line per entry here.

## Numbering State
**Counters go STALE and have caused real collisions (E-229, IDEA-071). ALWAYS glob the live dirs before assigning ANY number: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/` `ls migrations/`. Trust the filesystem, not these lines.**
- **Next epic: E-279 · next migration: 013 · next idea: 224.** (E-278 planned to READY 2026-07-28; IDEA-222 and IDEA-223 filed during it. No migration.)
- **⚠️ GLOB, THEN ASK IF ANOTHER THREAD MAY BE LIVE — and grep `.claude/agent-memory/` + `.project/research/` for `E-NNN` too.** A glob is authoritative against a stale counter and against **nothing else**: an unmerged branch, a concurrent thread's reservation, and a prose reservation all consume numbers it reports free. **The operator ruling *"numbers are allocated here, never guessed"* STANDS — it has two premises, only one dissolved on 2026-07-27, and I reported it retirable before checking both.** Worked instances, costs, and that correction: [numbering-discipline.md](numbering-discipline.md).
- **The 217+ reservation is CONSUMED** by 217-221 (the live-vs-dev report audit package). 195-221 verified contiguous: file + index row for every number. **E-275 the EPIC NUMBER is no longer reserved-but-uncreated — the epic EXISTS** (see Active Epics); **IDEA-184 remains pre-approved scope for its story 01.**
- **A PROMOTED idea's Notes are not a backlog.** IDEA-066's USSSA innings-engine remainder was silently retired with the idea when E-218 shipped only the detection half — unfiled for 3 months (now IDEA-182). At promotion, re-file whatever the epic does not take.
- **Writing `epics/**` or `.project/**` trips a pre-commit doc-PII byte-gate — never paste a real team name.** Live on both trees (`.githooks/pre-commit` `GATE_TREES`), so real identifiers block the planning commit, not review. Never truncate or prefix a real name (that is how IDEA-137 grew ~3×). **⚠️ Do NOT reflexively reach for the `Anytown`/`Springfield`/`Example` taxonomy in `.claude/rules/api-docs.md` — [[IDEA-203]] records that the gate has reportedly BLOCKED sentinels of exactly that class** (premise unconfirmed). E-275 built sentinels from invented tokens instead (`Wexlom`, `Quorrin`, `Trandive`…); prefer invented tokens, which have no collision surface. Companion [[IDEA-204]], [[IDEA-211]].
- Everything E-273 and below is COMPLETED+archived except the open epics below — see [archived-epics.md](archived-epics.md) (canonical: `ls /.project/archive/`). CE-1..CE-5 = E-251..E-255.
- Idea descriptions are NOT duplicated here — `/.project/ideas/README.md` is canonical. **One triage note: IDEA-168 / 171 / 172 all point at `detect_league_level`.** 171 is PROMOTED (E-274); if E-274 ships, re-triage 168 and 172 against it (172's blast radius shrinks).

## Active Epics
Only DRAFT/READY/ACTIVE. Full detail lives in each epic file — do not restate it here.
- **E-278 READY (2026-07-28)** — game identity / date derivation. **Order FIXED 04 → 02 → 01 → 05. Two date mechanisms of OPPOSITE polarity; GC's own record is NOT ground truth.** Detail + the reusable process findings: [e278-game-identity.md](e278-game-identity.md). Ideas out: [[IDEA-222]], [[IDEA-223]].
- **E-275 DRAFT (2026-07-27)** — classifier hardening; epic file is canonical, prefer pointing. 2 SE stories (01 Legion precedence fix, 02 tripwire + append-only ground-truth pack). **Value order is DESCENDING — pack first, reorder last; corrected THREE times, do not restore an earlier one.** The reorder changes **0 of 563** real names — it ships on the **~13.6% rule-of-three bound**, never on the bare zero. **Two OQs block READY** (OQ-2 tripwire pin shape — *the story file wins over any handover note*; OQ-3 fresh-coach CHANGE/GUARD certification). Closure obligations in TN-10. Ideas out: [[IDEA-201]]/[[IDEA-202]]/[[IDEA-209]]/[[IDEA-210]]/[[IDEA-213]]/[[IDEA-214]].
- **E-274 DRAFT (2026-07-25)** — read GC's `age_group` school family as a structured level signal in `detect_league_level`. ONE production file, no schema/migration/crawl. 3 stories (01 SE core, 02 BLOCKED + may be ABANDONED, 04 CA pitch-rules ladder); **03 REMOVED, premise falsified, re-filed as IDEA-177 — tombstone needs `git rm`.** **Gates open (OQ-1, OQ-2); the operator holds a build/shrink/shelve call at 4% measured value and not dispatching is legitimate.** Measured on both populations (spring 3/73, summer 4/134, **0 of 207 move toward LESS rest**); the MECHANISM is the finding. **Two coach-ruled classifier defects hang on its fate — [[IDEA-205]] and [[IDEA-208]].** Detail + closure obligations surviving ABANDONMENT: [e274-age-group-level-signal.md](e274-age-group-level-signal.md).
- **E-271 READY (2026-07-21)** — workflow/process redesign from the E-267 audit (P-1..P-10 in `.project/research/E-271-e267-audit-findings.md`), CA-designed, 3 stories. Ratchet ~+35-55L needs an operator-signed exception. Closure obligations: TN-13 Step-1c external-ref recon + its own Closure-Evidence.
- **E-263 READY (2026-07-13; re-confirm by 2026-09-11)** — Deep Scout v1, 11 stories (chain 02a→02c→02b→04). Settled: operator PICKS competition level at submit; unset delegates to `detect_league_level`. Dispatch prereq: `git rm` the tombstone `E-263-02-fact-sheet-foundation-sig-001.md`. **Priority unchanged by E-274.**
- **E-174 DRAFT (kept 2026-07-26)** — asset-chunk fallback for the GC client-key extractor. `extract_client_key()` is also Step 1/3 of `_setup_web()` (`src/cli/creds.py:986`), not just the `bb creds extract-key` diagnostic (**3** docs / 15 refs). **⛔ NO PROBE DISPATCHED, NONE PENDING — do NOT frame it as awaiting one.** Operator steer: refine before building; four months without breakage outweighs structure-derived fragility ([feedback_refine_before_building_no_urgency_framing.md](feedback_refine_before_building_no_urgency_framing.md)). **The spec may exceed the problem.**
- **2026-07-26 triage of the three oldest epics: E-072 + E-175 ABANDONED, E-174 KEPT** ([archived-epics.md](archived-epics.md); takeaways in [lessons-learned.md](lessons-learned.md)) — **read the epic's own Status block before accepting any framing of its state**, and **a correct conclusion shields its false premise from review**.

## Open Operator Obligations
Canonical: [operator-followups.md](operator-followups.md). **⚰ The ratchet-baseline obligation is DISCHARGED** — the operator re-snapshotted at `625940e` (2026-07-27) and E-277 closed at **+445 against the CURRENT baseline, zero inherited**. The old "4 deferrals stale / +972 inherited" framing is FALSE and must not be reused. **Never tell the operator their baseline is stale without measuring it; the inherited share may legitimately be zero.**

## Pending Process Obligations
- **CR-vs-Codex gap re-measurement** (E-258-04 item 25): **RETIRED 2026-07-13, operator-CONFIRMED.** Dormant + non-self-triggering; pull ONLY on a fresh defect-cited rubric decision. Detail: [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md).

## Strategic Frame (reports-first reframe, 2026-06-12)
- Reports are the SOLE coaching surface (generate for a GC `public_id` + share link). Dashboard/member-sync/tracked-opponent surfaces REMOVED in E-239 (ROADMAP D2, −59k lines). Admin surface = `src/api/routes/reports_admin.py`. Forward feature = morning-of-game scheduled reports (E-240, `bb report morning-run`).
- Permanent non-goals: cross-team player identity, multi-season rollups, longitudinal tracking.
- `docs/ROADMAP.md` authoritative on scope (slices A–E all COMPLETED). `docs/VISION.md` + `vision-signals.md` **curated 2026-07-05** to the reframe (multi-program *reach* kept but scoped single-season/any-`public_id`, NOT longitudinal). §3 rationales CODIFIED by E-255-03; see [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) (historical).

## Project Context
- baseball-crawl — GameChanger API → SQLite → coaching scouting reports for Lincoln Standing Bear HS.
- Tech: Python end-to-end. FastAPI + Jinja2 (server-rendered HTML). Docker Compose + Cloudflare Tunnel. SQLite (WAL, `./data/app.db`). Production: https://bbstats.ai.
- Operator CLI: `bb` (Typer), `src/cli/`, devcontainer-only. Groups: status, creds, data, db, report.
- Credentials: short-lived, profile-scoped (`_WEB`/`_MOBILE`). Primary: `bb creds setup web`. Rule: `.claude/rules/auth-module.md`.
- See CLAUDE.md for full conventions; `.claude/rules/data-model.md` for schema decisions.

## Key Architectural Decisions
- Storage: SQLite WAL, host-mounted `./data/app.db`, file backup via `scripts/backup_db.py` (no Litestream). Serving: FastAPI + Jinja2, single monolithic app, no TypeScript.
- Migrations: numbered SQL, no Alembic, applied at startup. History is reconstructable from `migrations/` + `.claude/rules/data-model.md` — do not keep a second copy here.
- Canonical entry points (new INSERT/UPDATE paths MUST route through these): `ensure_team_row()`, `ensure_player_row()`, `cascade_delete_team()`/`cleanup_orphan_teams()`, `reclaim_orphan_reference_data()`, `merge_duplicate_game()`, `search_teams_by_name()`, `_user_is_admin`/`user_is_admin` + `_get_permitted_teams`, `derive_season_id_for_team()`, `resolve_db_path()`, `get_connection()`. `.claude/rules/canonical-seams.md` is canonical for all of them.
- Season aggregates are **query-time-derived** (E-259 dropped the stored `player_season_*` tables). Surviving invariant: every query-time season sum MUST scope by `perspective_team_id` or it double-counts a two-perspective game.
- **Report generation is DESTRUCTIVE on two axes** (E-267 + E-273): reconcile-at-load can hard-delete `games`, orphan reclamation can hard-delete unreachable `teams`/`players`. Never describe `bb report generate` as read-only or safe to re-run blindly.
- `ip_outs`: innings pitched stored as integer outs (1 IP = 3 outs), rendered in thirds — the fractional digit is only ever `.0`/`.1`/`.2` (see [[IDEA-221]], where a render path emitted an impossible `5.3`).
- Auth (E-157): all users = magic link + optional passkey. Admin = `ADMIN_EMAIL` env OR `users.role='admin'`; admins bypass `user_team_access` (E-228) in dev + prod.
- Mobile credentials (E-075): mobile client key CONFIRMED different from web; programmatic mobile refresh blocked.
- Routing (E-030): orchestrator removed; PM is the direct entry point for work definition.

## User Preferences
- Build it right, no rush. Coaches consume reports; the user (operator) runs the system.
- CLAUDE.md + shipped code/comments describe CURRENT implemented reality, not future plans; epics/stories describe future work until done.
- Archived files are frozen historical records — do not modify.

## Key Workflow Contract
- Routing: planning (user → PM); dispatch (user/main session → implementers directly). PM plans, verifies ACs, owns statuses, closes; main session spawns/routes/merges.
- PM modes: discover, plan, clarify, triage, close, curate.
- Epic lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED). READY/ACTIVE required before dispatch; PM sets READY explicitly. Dispatch authorization is a separate user call.
- Full-suite-green closure gate (E-230): COMPLETED is authored in the worktree and finalizes only after `python -m pytest tests/` reports 0 failed in main at Step 8; a red gate aborts/reverts.
- Closure gates: documentation assessment + **eight**-trigger context-layer assessment (`.claude/rules/context-layer-assessment.md`), both recorded per-epic before archiving.
- Direct-routing exceptions (no PM): api-scout, baseball-coach, claude-architect.
- 9 agents: claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer.

## Ideas Backlog
Canonical: `/.project/ideas/README.md` (full text + all statuses). Only the salient few are named here:
- **IDEA-178 — PROMOTABLE, coach ruling IN, only prioritisation remains.** `ngb=american_legion` shadows NRBL, so **NRBL never fires for the teams it was built for**; benign only because the curves are byte-identical today. **Do not fold into E-274** — same function, different decision. Lesson: a green suite cannot detect an unreachable branch; only ground truth found it.
- **Report-audit cluster (2026-07-27, IDEA-217-221)**, from the four-agent live-vs-dev evaluation. **217 is the promotable one** — the record header counts games no other surface counts, and the replayed fix yields the GC-correct record with **zero data cleanup**. **218/219** are its two row-level causes (dedup natural-key gap; cross-team mis-attribution) — destructive to clean, neither blocking 217. **220** is filed with its premise contested (doubled plays are probably by design). **221** is render-path formatting divergence; only the illegal `5.3` IP has a coaching consequence.
- **IDEA-196 (LIVE, prod only):** a phantom `"Unknown"` roster stub + a transposed surname; **a full generation healed neither.** Durable code fact: `ensure_player_row` overwrites only on a **strictly longer** name, so an equal-length misspelling is **permanently sticky by design**. Promote on the operator wanting prod fixed, or **a second stub anywhere**.
- **Client/creds hygiene — all THREE together: [[IDEA-193]] + [[IDEA-194]]** (`credential_parser.py`) **and [[IDEA-197]]** (`client.py`/`morning_run.py`). One family: *the error path tells the operator something false*. **193 is cheap, needs no epic, and must not wait on 194.**
- **PII/doc-gate cluster — [[IDEA-203]] + [[IDEA-204]] + [[IDEA-211]], all CA, evaluate together.** What the gate wrongly blocks; what it never sees (agent-memory: **15 files / 33 lines / 6 dirs, measured** — ⛔ no redaction authorized, and re-running it pulls identifiers into context); a stale rule file that already produced a false audit finding.
- **IDEA-078** (SALIENT since E-255): `docs/coaching/` reports-first rewrite. **IDEA-080** (PROMOTABLE): coach-facing scheduled report delivery, the next slice after E-240. **IDEA-084**: scouting-coverage fill. **IDEA-089**: Tier 2 fork disambiguation — **0 refused forks live**, promote only on a real case. **IDEA-090**: Codex script modernization (CA owns impl).
- Reframe-adjacent still-CANDIDATE: IDEA-018, 022, 043. A large DISCARDED set from the D1/D2 reframe is in the README — check before re-proposing anything dashboard-shaped.

## Topic File Index
- [archived-epics.md](archived-epics.md) — one-line-per-epic milestone index (canonical: `ls /.project/archive/`)
- [lessons-learned.md](lessons-learned.md) — epic authoring / dependency / process patterns, platform constraints
- [operator-followups.md](operator-followups.md) — open operator obligations. **§3 (context-ratchet drift) is RESOLVED 2026-07-27; do not act on it or reuse its "stale for N epics" framing**
- [mcp-research.md](mcp-research.md) — MCP server evaluation findings
- [numbering-discipline.md](numbering-discipline.md) — why a glob is necessary and never sufficient: the three off-disk ways a number gets consumed, their costs, and the operator ruling's two premises
- [e276-health-gate-triage.md](e276-health-gate-triage.md) — **E-276 COMPLETED. Read before any reconcile-at-load work.** Three decisions that get re-litigated if unread: roster has **NO floor at all**; player-line is **diagnostic only**; the headline fix is true for **ONE RUN** — a refusal still WRITES. Plus the signed ratchet exception that **is not precedent**.
- [e274-age-group-level-signal.md](e274-age-group-level-signal.md) — E-274's scope, open gates, measured value, closure obligations, two refuted over-generalisations
- [e277-planning-state.md](e277-planning-state.md) — **E-277 PLANNING-PHASE record only, superseded on state.** Triage record, six facts not derivable from the files, the sharpest awareness-is-no-immunity case recorded here.
- [e278-game-identity.md](e278-game-identity.md) — E-278's fixed story order, the two opposite-polarity date mechanisms, why GC's record is not ground truth, and the **three-leg consistency sweep** (prose summarizing a structure is the leg everyone misses)
- [e277-reclamation-followups.md](e277-reclamation-followups.md) — **E-277 dispatch state + process findings not in the epic file.** The three things a successor is most likely to destroy (story 02's AC-5b ORDER; the deliberately weaker two-measurement claim; the UNMEASURED live-shape question). Epic TN-15 is canonical for the findings.
- [feedback_decide_and_disclose.md](feedback_decide_and_disclose.md) — **operator moved PM to decide-and-disclose (2026-07-27): decide in your own domain and LOG the reason; only four classes escalate** (scope change, destructive/irreversible, PII/security, override of a standing rule or prior ruling). The log is the deliverable, not a permission request.
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) — fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) — context-layer epics: CA designs stories, PM frames ACs
- [feedback_acceptance_command_surface_scope.md](feedback_acceptance_command_surface_scope.md) — dispatch failure inside an AC's named command/file is in-scope
- [feedback_clean_reread_before_defect.md](feedback_clean_reread_before_defect.md) — clean re-read + quote literal text before reporting any AC defect
- [feedback_dont_rationalize_weak_assertions.md](feedback_dont_rationalize_weak_assertions.md) — apply the delete-the-behavior teeth test; don't rationalize a no-teeth assertion
- [feedback_refine_before_building_no_urgency_framing.md](feedback_refine_before_building_no_urgency_framing.md) — refine before building; don't attach urgency to a structure-derived finding the operator's lived experience contradicts (E-174)
- [feedback_record_shrinkage_dont_substitute.md](feedback_record_shrinkage_dont_substitute.md) — retiring a gate: verify the property still EXISTS before proposing a replacement
- [feedback_verify_cited_facts_before_approving.md](feedback_verify_cited_facts_before_approving.md) — glob/grep each cited path before approving a prose correction
- [feedback_reverify_idea_before_folding.md](feedback_reverify_idea_before_folding.md) — re-verify a backlog idea's premise before folding it into an epic (E-262: 2 of 4 were stale)
- [feedback_verify_relayed_claims.md](feedback_verify_relayed_claims.md) — a relayed compound claim is verified only in the half the source directly observed; check the other half before scoping work on it (E-274)
- [feedback_ask_dont_infer_from_db.md](feedback_ask_dont_infer_from_db.md) — ASK the operator about history; the DB is current state, not a record. Operator instruction, E-274
- [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) — 2026-07-05 curation §3 rationales; ✅ CODIFIED by E-255-03, historical
- [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md) — the RETIRED item-25 obligation; see Pending Process Obligations
