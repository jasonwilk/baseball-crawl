# Product Manager -- Agent Memory

This is an INDEX. Per-epic history lives in [archived-epics.md](archived-epics.md); reusable patterns in [lessons-learned.md](lessons-learned.md); ideas in `/.project/ideas/README.md`; operator obligations in [operator-followups.md](operator-followups.md). **Keep this file lean (< 17KB) — one line per entry, move detail to topic files.** ⚠️ **The discipline that slips is the index/topic split, not the size** ([[IDEA-229]]): when an index line grows into a paragraph, the content belongs in a topic file. Compacted 2026-08-02 at E-280 closure (22KB → here) by moving detail out, not by deleting it.

## Numbering State
**Counters go STALE and have caused real collisions (E-229, IDEA-071). ALWAYS glob the live dirs before assigning ANY number: `ls /epics/` `ls /.project/archive/` `ls /.project/ideas/` `ls migrations/`. Trust the filesystem, not these lines** — this counter has been falsified by its own author at least three times.
- **Next epic: E-281 · next migration: 013 · next idea: 235.** (**E-280 CONSUMED** — context-layer healing, closed 2026-08-02; its story numbers **03 and 05 are RETIRED-not-reused** and **09 was consumed mid-dispatch** by a split of 06. **IDEA-234 CONSUMED** at E-280 closure.) **Globbed at closure 2026-08-02: live `epics/` max is E-280, `.project/archive/` max is E-279, ideas max 233 in BOTH the worktree and the main checkout.** ⚠️ **This line briefly read "E-282 · E-281 CONSUMED" — a number its author invented while compacting. Caught by globbing, which is the only thing that catches it; the counter is exactly as untrustworthy as the warning above says, including when I am the one writing it.**
- **⚠️ GLOB, THEN ASK IF ANOTHER THREAD MAY BE LIVE — and grep `.claude/agent-memory/` + `.project/research/` for `E-NNN` too.** A glob is authoritative against a stale counter and against **nothing else**: an unmerged branch, a concurrent thread's reservation, and a prose reservation all consume numbers it reports free. **The operator ruling *"numbers are allocated here, never guessed"* STANDS.** Detail: [numbering-discipline.md](numbering-discipline.md).
- **A PROMOTED idea's Notes are not a backlog.** IDEA-066's USSSA remainder was silently retired with the idea when E-218 shipped only half — unfiled for 3 months (now IDEA-182). At promotion, re-file whatever the epic does not take.
- **Writing `epics/**` or `.project/**` trips a pre-commit doc-PII byte-gate — never paste a real team name.** Live on both trees, so real identifiers block the planning commit, not review. Never truncate or prefix a real name (that is how IDEA-137 grew ~3×). **⚠️ Do NOT reach for the `Anytown`/`Springfield`/`Example` taxonomy in `.claude/rules/api-docs.md`** — [[IDEA-203]] records the gate reportedly blocking sentinels of that class (premise unconfirmed). **Prefer invented tokens** (`Wexlom`, `Quorrin`…), which have no collision surface.
- Everything E-273 and below is COMPLETED+archived except the open epics below — [archived-epics.md](archived-epics.md) (canonical: `ls /.project/archive/`). CE-1..CE-5 = E-251..E-255.
- **Triage note: IDEA-168 / 171 / 172 all point at `detect_league_level`.** 171 is PROMOTED (E-274); if E-274 ships, re-triage 168 and 172 against it (172's blast radius shrinks).

## Active Epics
Only DRAFT/READY/ACTIVE. Full detail lives in each epic file — do not restate it here.
- **E-275 DRAFT (2026-07-27)** — classifier hardening; epic file is canonical. 2 SE stories (01 Legion precedence fix, 02 tripwire + append-only ground-truth pack). **Value order is DESCENDING — pack first, reorder last; corrected THREE times, do not restore an earlier one.** The reorder changes **0 of 563** real names — it ships on the **~13.6% rule-of-three bound**, never on the bare zero. **Two OQs block READY** (OQ-2 tripwire pin shape — *the story file wins over any handover note*; OQ-3 fresh-coach CHANGE/GUARD certification).
- **E-274 DRAFT (2026-07-25)** — GC `age_group` as a level signal in `detect_league_level`. ONE production file, no schema/migration/crawl. **Gates open; the operator holds a build/shrink/shelve call at 4% measured value and not dispatching is legitimate.** Measured both populations (**0 of 207 move toward LESS rest**); the MECHANISM is the finding. Two coach-ruled defects hang on its fate ([[IDEA-205]], [[IDEA-208]]). Detail: [e274-age-group-level-signal.md](e274-age-group-level-signal.md).
- **E-271 DRAFT** (demoted from READY 2026-08-02 by operator ruling at E-280 OQ-A; PM executed the flip + dated History entry). Workflow/process redesign from the E-267 audit, CA-designed, 3 stories. **Re-refine against the POST-E-280 layer, do not repair in place** — its grounds are enumerated in its own 2026-08-02 History entry; read that, not this line.
- **E-263 READY (2026-07-13; re-confirm by 2026-09-11)** — Deep Scout v1, 11 stories (chain 02a→02c→02b→04). Settled: operator PICKS competition level at submit; unset delegates to `detect_league_level`. Dispatch prereq: `git rm` the tombstone `E-263-02-fact-sheet-foundation-sig-001.md`.
- **E-174 DRAFT (kept 2026-07-26)** — asset-chunk fallback for the GC client-key extractor. `extract_client_key()` is also Step 1/3 of `_setup_web()`, not just the `bb creds extract-key` diagnostic. **⛔ NO PROBE DISPATCHED, NONE PENDING — do NOT frame it as awaiting one.** Operator steer: refine before building; four months without breakage outweighs structure-derived fragility. **The spec may exceed the problem.**
- **2026-07-26 triage of the three oldest epics: E-072 + E-175 ABANDONED, E-174 KEPT** — **read the epic's own Status block before accepting any framing of its state**, and **a correct conclusion shields its false premise from review**.

## Open Operator Obligations
Canonical: [operator-followups.md](operator-followups.md).
- ✅ **RATCHET — DISSOLVED, not discharged.** The operator retired the context-layer size GATE outright (E-280): no baselines, offsets, exceptions or re-snapshot; `context-ratchet.sh` survives as an on-demand diagnostic and E-280-08 retired the prose. **Do NOT restore any earlier form of this line, and do not re-open the E-261/E-262 attribution question.** Two things still true and worth carrying: never tell the operator their baseline is stale without measuring it; and the gate fell for a **structural** reason — an unregistered diagnostic accruing continuously and charged to whichever epic closes next **fails an epic by construction** if it closes more than about a day after a snapshot (+286 in 22h33m).
- ⚠️ **E-279 doc gate FIRES and is UNRESOLVED** — the archive-reference gate in `.githooks/pre-commit` can refuse the OPERATOR's commit (`[archive-refs: BLOCKED]`), and the only override is `--no-verify`, **which also disables the PII scan.** `docs/admin/operations.md` is owed a docs-writer pass. Recorded as **FIRING, not satisfied**.
- ⚠️ **`docs/admin/agent-guide.md` is owed a docs-writer pass** (raised at E-280 closure, doc triggers 3+5): 7 agents listed against **9** on disk (`ux-designer` and `code-reviewer` absent), three model rows wrong, and line 84 claims *"The PM creates an Agent Team, spawns implementing agents"* — which `dispatch-pattern.md` contradicts outright. Last updated 2026-03-04.

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
- Closure gates: documentation assessment + the context-layer assessment, both recorded per-epic with **an explicit verdict for EVERY trigger in the numbered list** before archiving. ⚠️ **Do NOT restate the trigger COUNT here or anywhere else** — E-280 removed that restatement from all four sites it lived in precisely because a renumber made them all wrong at once. *(This line said "eight-trigger" until 2026-08-02, when I reintroduced it while compacting this file at E-280's own closure.)*
- **⭐ POST-E-280 (2026-08-02), and these change PM's dispatch behavior — detail in [e280-context-layer-healing.md](e280-context-layer-healing.md):**
  - **Verdicts are ONE-OF-EACH against a FROZEN TREE.** PM issues one AC verdict, CR one review verdict, neither re-askable. **Dual approval SURVIVES; only re-issuance died.** *"pm owns acceptance"* — operator verbatim.
  - **"Unstaged = the current story" is RETIRED.** The review surface is a diff between two tree SHAs.
  - **Review depth is tiered by FILE-PATH CLASS**, never by judgment; unmatched ⇒ tier A.
  - **The size gate is RETIRED**; trigger 7 records a diagnostic reading and routes a "yes" to the periodic pass. **Two cadences counted in EPIC CLOSURES: adversarial audit per THREE, context-layer refinement per FIVE.**
  - **6,000-char report ceiling for long-lived agents** (an ESTIMATE, a tail guard — there is no measured inflation). **`code-reviewer` is EXCLUDED** on a documented model literalism failure mode.
- Direct-routing exceptions (no PM): api-scout, baseball-coach, claude-architect.
- 9 agents: claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer, code-reviewer.

## Ideas Backlog
**Canonical: `/.project/ideas/README.md` (full text + all statuses). Do NOT duplicate descriptions here** — only the few needing a standing steer:
- **IDEA-178 — PROMOTABLE, coach ruling IN, only prioritisation remains.** `ngb=american_legion` shadows NRBL, so **NRBL never fires for the teams it was built for**; benign only because the curves are byte-identical today. **Do not fold into E-274** — same function, different decision. Lesson: a green suite cannot detect an unreachable branch; only ground truth found it.
- **Report-audit cluster (IDEA-217-221).** **217 is the promotable one** — the record header counts games no other surface counts, and the replayed fix yields the GC-correct record with **zero data cleanup**. 218/219 are its row-level causes (destructive to clean, neither blocking 217); 220's premise is contested; 221 matters only for the illegal `5.3` IP.
- **IDEA-196 (LIVE, prod only):** a phantom `"Unknown"` roster stub + a transposed surname; **a full generation healed neither.** Durable code fact: `ensure_player_row` overwrites only on a **strictly longer** name, so an equal-length misspelling is **permanently sticky by design**. Promote on the operator wanting prod fixed, or a second stub anywhere.
- **Client/creds hygiene — all THREE together: [[IDEA-193]] + [[IDEA-194]] + [[IDEA-197]].** One family: *the error path tells the operator something false*. **193 is cheap, needs no epic, and must not wait on 194.**
- **PII/doc-gate cluster — [[IDEA-203]] + [[IDEA-204]] + [[IDEA-211]], all CA, evaluate together.** ⛔ No redaction authorized, and re-running the agent-memory measurement pulls identifiers into context.
- **Off-team memory reconciliation, resolution-triggered on the owner's next spawn:** [[IDEA-234]] (SE — two files, index row included), [[IDEA-227]], [[IDEA-225]], [[IDEA-226]].
- **IDEA-078** (SALIENT since E-255): `docs/coaching/` reports-first rewrite. **IDEA-080** (PROMOTABLE): coach-facing scheduled report delivery, the next slice after E-240. **IDEA-084**: scouting-coverage fill. **IDEA-089**: 0 refused forks live — promote only on a real case. **IDEA-090**: Codex script modernization (CA owns impl).
- Reframe-adjacent still-CANDIDATE: IDEA-018, 022, 043. A large DISCARDED set from the D1/D2 reframe is in the README — check before re-proposing anything dashboard-shaped.

## Topic File Index
*One line each. If a line here grows into a paragraph, the content belongs in the file it points at.*
- [archived-epics.md](archived-epics.md) — one-line-per-epic milestone index (canonical: `ls /.project/archive/`)
- [lessons-learned.md](lessons-learned.md) — epic authoring / dependency / process patterns, platform constraints
- [operator-followups.md](operator-followups.md) — open operator obligations. **§3 (context-ratchet drift) is RESOLVED; do not act on it or reuse its "stale for N epics" framing**
- [numbering-discipline.md](numbering-discipline.md) — why a glob is necessary and never sufficient
- [e280-context-layer-healing.md](e280-context-layer-healing.md) — **E-280 COMPLETED 2026-08-02.** The post-epic dispatch contract, PM's own mechanised AC defects (RED-narrower-than-body; rationale-broader-than-criterion; first-application calibration), and the AC-1c semantic residual carried open
- [e278-game-identity.md](e278-game-identity.md) — **E-278.** Two opposite-polarity date mechanisms; GC's record is NOT ground truth; the fail-closed-alone-is-a-no-op trap, still LIVE under the renamed field. **Two operator items closure did NOT discharge**
- [e277-reclamation-followups.md](e277-reclamation-followups.md) — **E-277 dispatch state.** The three things a successor is most likely to destroy; epic TN-15 is canonical for the findings
- [e277-planning-state.md](e277-planning-state.md) — **E-277 PLANNING PHASE only, superseded on state.** The sharpest awareness-is-no-immunity case recorded here
- [e276-health-gate-triage.md](e276-health-gate-triage.md) — **E-276. Read before any reconcile-at-load work.** Roster has NO floor; player-line is diagnostic only; the headline fix is true for ONE RUN
- [e274-age-group-level-signal.md](e274-age-group-level-signal.md) — E-274's scope, open gates, measured value, closure obligations surviving abandonment
- [e279-planning-state.md](e279-planning-state.md) — ⚰ **tombstone**; kept only for the E-271 declination, the `ACMR` PII fix that must not be "restored", and IDEA-232
- [mcp-research.md](mcp-research.md) — MCP server evaluation findings
- [project_ce5_curation_handoff.md](project_ce5_curation_handoff.md) — 2026-07-05 curation §3 rationales; ✅ CODIFIED by E-255-03, historical
- [project_cr_codex_gap_remeasurement.md](project_cr_codex_gap_remeasurement.md) — the RETIRED item-25 obligation
- [feedback_decide_and_disclose.md](feedback_decide_and_disclose.md) — **decide in your own domain and LOG the reason; only four classes escalate** (scope change, destructive/irreversible, PII/security, override of a standing rule or ruling)
- [feedback_fix_all_real_findings.md](feedback_fix_all_real_findings.md) — fix all real review findings, dismiss only false positives
- [feedback_domain_expert_designs.md](feedback_domain_expert_designs.md) — context-layer epics: CA designs stories, PM frames ACs
- [feedback_acceptance_command_surface_scope.md](feedback_acceptance_command_surface_scope.md) — dispatch failure inside an AC's named command/file is in-scope
- [feedback_clean_reread_before_defect.md](feedback_clean_reread_before_defect.md) — clean re-read + quote literal text before reporting any AC defect
- [feedback_dont_rationalize_weak_assertions.md](feedback_dont_rationalize_weak_assertions.md) — apply the delete-the-behavior teeth test
- [feedback_refine_before_building_no_urgency_framing.md](feedback_refine_before_building_no_urgency_framing.md) — refine before building; don't attach urgency to a structure-derived finding the operator's experience contradicts
- [feedback_record_shrinkage_dont_substitute.md](feedback_record_shrinkage_dont_substitute.md) — retiring a gate: verify the property still EXISTS before proposing a replacement
- [feedback_verify_cited_facts_before_approving.md](feedback_verify_cited_facts_before_approving.md) — glob/grep each cited path before approving a prose correction
- [feedback_reverify_idea_before_folding.md](feedback_reverify_idea_before_folding.md) — re-verify a backlog idea's premise before folding it into an epic
- [feedback_verify_relayed_claims.md](feedback_verify_relayed_claims.md) — a relayed compound claim is verified only in the half the source directly observed
- [feedback_ask_dont_infer_from_db.md](feedback_ask_dont_infer_from_db.md) — ASK the operator about history; the DB is current state, not a record
