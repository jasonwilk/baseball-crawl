# E-259: Query-Time Season Aggregates

## Status
`READY`

## Overview
Retire the stored `player_season_batting` / `player_season_pitching` tables in favor of query-time derivation from the per-game tables. Post-E-239 the stored tables are a materialization of a SUM over ≤35 games × ~15 players, with **zero external readers** and **zero surviving `full`/`supplemented` writers** — so the provenance guard that once protected member rows now only *freezes* legacy rows over fresh recomputes. Retiring them retires the entire parity/footgun apparatus (`aggregate_parity.py`, `bb report verify-aggregates`, six documented footguns, the E-247 wipe-hazard class) and is the highest-value single simplification the audit found.

## Background & Context
This epic executes the audit's one upheld REVISIT decision (`PLATFORM-AUDIT.md` §3), split out of the E-256 stub (CE-6) by user decision on 2026-07-09 — different owner (data-engineer), different risk profile (a read-path SQL cutover with a silent double-count hazard), and a strict ordering constraint.

It discharges a deferred note that lives **inside** the already-COMPLETED roadmap slice Epic C:
- `docs/ROADMAP.md:341` — "The replace-with-views option is DEFERRED until after D2. **Sequencing note: if D2 lands first, revisit and simplify.**" D2 (E-239) landed 2026-06-17; this revisit trigger fired and was never acted on.
- `docs/ROADMAP.md:345` — "**Gate**: Epic A's parity script must run on real data (production DB copy) before cutover; every mismatch is investigated."

Because it discharges a deferred note rather than implementing a §5 slice, and Epic C is already COMPLETED, this epic adds **no `docs/ROADMAP.md` §0 tracking row** and carries **no `## Roadmap` section**. Do not reopen Epic C's slice status.

**Strict ordering: E-259 executes AFTER E-256.** The two epics collide on `_query_batting`/`_query_pitching`; E-256 relocates the pure fetch to `src/api/db.py` as `get_season_batting`/`get_season_pitching` and E-259 rewrites their SQL bodies in place. E-256 also builds the Step 1d closure runtime smoke that E-259 — the highest-risk read-path change in the backlog — most needs. See E-256 Technical Notes §1 and §14 for the seam contract.

## Goals
- Cut `_query_batting`/`_query_pitching` over to query-time derivation from `player_game_*`, with the perspective filter the stored rows carried implicitly (Technical Notes §2).
- Retire every write path: `canonical_recompute`, `ScoutingLoader._compute_season_aggregates`, the player-dedup recompute, the report-generator cascade DELETEs.
- Drop the two tables via a migration that **refuses** on any surviving member row (Technical Notes §3).
- Delete the now-dead parity/validation apparatus and collapse the guards that only existed to protect the stored tables.
- Evict every context-layer reference to the retired command, tables, and functions (the context-layer files + owning-agent memory in Technical Notes §5).

## Non-Goals
- Any change to the golden report output. `tests/test_report_golden.py` is **zero-diff** across this epic (the cutover must be behavior-preserving — Technical Notes §4).
- Cross-season or multi-season aggregation. `season_id` remains the single-season partition key; it is not touched.
- A frozen-archive or export table for the stored rows. Ruled out (Technical Notes §3): the live DB has zero member rows, and DE's position is that a frozen archive is "a stale-data trap dressed as safety."
- Substituting a replacement integrity gate for the retired `verify-aggregates`. There is no such thing post-cutover (Technical Notes §6) — this is a deliberate net shrinkage, not a swap.

## Success Criteria
- `_query_batting`/`_query_pitching` derive from `player_game_*` at query time; no code reads `player_season_*`.
- Migration 011 drops both tables and refuses (aborts, tables intact) if any surviving row has `stat_completeness IN ('full','supplemented')`.
- `bb report verify-aggregates`, `src/reports/aggregate_parity.py`, and `scripts/validate_plays_stats.py` (plus their tests) are gone.
- A two-perspective test proves the query-time readers do NOT double-count (Technical Notes §2).
- Full suite green in the main checkout at closure; golden report zero-diff.

## Prerequisites (pre-dispatch — NOT stories)
E-259 MUST NOT dispatch until all three are satisfied:
0. **E-256 is COMPLETED and merged to main (HARD cross-epic blocker).** E-259's stories assume seams E-256 creates that DO NOT EXIST in the current tree: `get_season_batting`/`get_season_pitching` in `src/api/db.py` (E-256-04 relocates them; today the readers are still `_query_batting`/`_query_pitching` at `generator.py:399`/`:441`), and the Step 1d `verify-aggregates` sub-check in `implement/SKILL.md` + `code-reviewer.md` (E-256-11 adds it; E-259-05 strikes it). Dispatching E-259 before E-256 merges means story 01 rewrites a function that does not exist and story 05 strikes a surface that was never added. The strict-ordering prose (Overview) is now backed by this hard prerequisite and by per-story `Blocked by` annotations on E-259-01 and E-259-05.

The two operator gates below are NOT runnable in an epic worktree (no `.env`, no `data/`):
1. **`bb report verify-aggregates` green on a live-DB copy** — the roadmap cutover gate (`docs/ROADMAP.md:345`); every mismatch investigated before cutover.
2. **E-257's `reconciliation-scoreboard.json` baseline committed** (the owed operator follow-up) — so the surviving fidelity gate has a baseline once `verify-aggregates` retires.

DE has already run the member-row survey: batting `[('boxscore_only', 67)]`, pitching `[('boxscore_only', 48)]` — **zero member rows**, so no data-preservation story is needed. The migration preflight (Technical Notes §3) mechanizes that as a standing guard rather than a one-time observation.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-259-01 | Cut season readers over to query-time derivation | TODO | None | data-engineer |
| E-259-02 | Retire the season-aggregate write paths | TODO | E-259-01 | data-engineer |
| E-259-03 | Migration 011: drop the tables with a refuse-on-member-row preflight | TODO | E-259-02 | data-engineer |
| E-259-04 | Delete the parity and plays-validation apparatus | TODO | E-259-03 | data-engineer |
| E-259-05 | Evict context-layer references (files + owning-agent memory) | TODO | E-259-01, E-259-02, E-259-03, E-259-04 | claude-architect |
| E-259-06 | Update runbooks and admin docs | TODO | E-259-04 | docs-writer |

*(Dependencies column lists INTRA-epic story deps. Every E-259 story is ADDITIONALLY gated on **Prerequisite 0** — E-256 COMPLETED + merged — a hard cross-epic blocker; E-259-01 and E-259-05 name their specific E-256 upstream (E-256-04, E-256-11) in their story `Blocked by` fields. E-259 is NOT dispatchable until E-256 lands.)*

## Dispatch Team
- data-engineer
- claude-architect
- docs-writer

## Technical Notes

### §1. The cutover is behavior-preserving; the golden test is a zero-diff invariant
E-256 (story 04) **already relocated** the pure SQL fetch to `src/api/db.py` as `get_season_batting`/`get_season_pitching(conn, team_id, season_id) -> list[dict]` (returning raw SUM columns), leaving `_query_batting`/`_query_pitching` in `generator.py` as thin presentation wrappers (E-256 Technical Notes §14, DE's relocation contract). **E-259 owns exactly ONE change in the cutover diff: rewrite the SQL body inside `get_season_batting`/`get_season_pitching` in place** — derive from `player_game_*`, add the `perspective_team_id` filter (§2), and reproduce the ORDER BY semantics over the new per-game-SUM projection (§8). No relocation, no presentation change; `_apply_name_cascade`/`_compute_pitching_rates` stay in the reports layer. Because the fetch is already at its final location, E-259's diff is a clean **old-SQL-vs-new-SQL comparison inside one function** — the whole reason E-256 relocated first and option (c) was rejected (the reviewer must see the semantic change side by side). Because the wrappers and their output shape are unchanged, `tests/test_report_golden.py` is **zero-diff** (it exercises the `_query_*` wrappers). **This epic may not touch the golden test to make itself pass.**

### §2. THE #1 HAZARD — the implicit perspective filter (named AC + test, not a review catch)
The stored rows carried perspective scoping **implicitly**: `canonical_recompute` applied `pgb.perspective_team_id = ?` at **WRITE** time (`season_aggregates.py:230-235`). The current reader filters on **neither** `perspective_team_id` **nor** `stat_completeness`. A query-time replacement that omits the perspective filter **silently doubles** a player's season line when a game was loaded from two perspectives — **nothing crashes, nothing errors**. The new `get_season_*` SQL MUST carry the perspective filter, and story 01 MUST include a test that seeds two perspectives for one game and asserts the season line is NOT doubled. This is the single most important AC in the epic.

### §3. Migration 011 refuses rather than archives
The live DB has zero `full`/`supplemented` rows (DE survey above), so no archive/export is built. Instead the DROP migration is **preceded by a preflight that asserts both `player_season_batting` and `player_season_pitching` hold zero rows with `stat_completeness IN ('full','supplemented')` on the DB being migrated, at the moment it is migrated**, and on any non-zero count it **REFUSES the cutover** (aborts, leaving the tables intact) — not archive, not export. DE's reasoning, to record: a frozen archive table is "a stale-data trap dressed as safety"; a resurrected member row means a writer we believed deleted has come back, and the correct response is to **stop and understand that**, not to paper over it. The migration runner is transactional as of E-253, so a refused migration rolls back cleanly. **DE chooses the preflight mechanism** (SQL guard, a Python check in the runner, or a pre-migration gate) — this note specifies the outcome, not the code.

**Rollback framing (honest — DE correction).** The naive "git revert + re-run `canonical_recompute`" rollback does NOT hold: story 02 *deletes* `canonical_recompute` (so it is unavailable after a code revert), and migrations are forward-only with 011 recorded in `_migrations` (so `git revert` does NOT un-drop the tables on an already-migrated DB). The accurate rollback is: on a **dev** DB → `bb db reset` + reload; on an **already-migrated live** DB → git-revert the epic + a NEW recreate-migration (the table DDL is recoverable verbatim from `migrations/001_initial_schema.sql`) + reload. This is fully recoverable — the tables are a pure cache and their DDL survives in 001 — so it is NOT data-loss, but it is not the one-step revert the simpler framing implied. (DE flags this as land-before-ARCHIVE, not a dispatch blocker.)

### §4. Behavior-preserving ⇒ populated, stale-disagreeing characterization fixtures
Per the E-247 lesson (`.claude/rules/data-model.md`, Season-Aggregate Parity): a no-op/equality recompute test has **no teeth on a fresh or empty DB**. Story 01's equality pin (query-time output == prior `canonical_recompute` output) MUST seed a **populated** fixture whose per-game rows produce a known season line, and the two-perspective test (§2) MUST seed a genuinely doubled input. A green test on an empty DB proves nothing.

### §5. Eviction surface: the context-layer files + the owning agents' memory (deletion-side eviction; triggers 3, 4, 6, 7 all fire)
This is not a six-file sweep. **Story 05 (single-CA-assigned) executes items 1–7 and 11** — the CA-owned context-layer files plus CA's OWN memory (item 7). **Items 8–10 (software-engineer, code-reviewer, and data-engineer memory) are NOT story-05 ACs**: per CA's AC-5 ruling a single-assignee story cannot have other agents editing their own dirs within it, so they are a closure Deletion-Side-Eviction obligation the Context-Layer Assessment Gate discharges before archival. E-259-05 AC-6 generalizes the Deletion-Side-Eviction rule (`.claude/rules/context-layer-assessment.md`) so this is enforceable; DE, being on the team, reconciles its four files at closure. The full seed set:
1. `CLAUDE.md` — the `bb report verify-aggregates` Commands entry; the `canonical_recompute` Architecture bullet; **and two more sites**: the `bb data dedup-players` sentence (which mentions the CLI-owned recompute) and any `backfill-appearance-order` footgun telling operators to confirm with `verify-aggregates`.
2. `.claude/rules/data-model.md` — Season-Aggregate Parity section (the entire parity apparatus it documents).
3. `.claude/rules/key-metrics.md` — the GS-derivation sentence citing `canonical_recompute`.
4. `.claude/rules/perspective-provenance.md` — MUST-constraint 3 names `_compute_season_aggregates()`.
5. `.claude/rules/architecture-subsystems.md` — Scouting Pipeline stage 2 + the E-247 twin-method note.
6. `.claude/agents/code-reviewer.md` — its Bug Pattern Checklist uses `player_season_batting` as its worked example. **Edit INSIDE the `BUG-PATTERN-CHECKLIST` delimiters; never touch the markers** — the Codex prompt extracts them verbatim.
7. `.claude/agent-memory/claude-architect/epic-codifications.md`
8. `.claude/agent-memory/software-engineer/testing-gotchas.md`
9. `.claude/agent-memory/code-reviewer/` (the relevant memory)
10. **DE-owned agent-memory (SEED — reconciled at closure by DE per the Deletion-Side-Eviction obligation, grep-and-reconcile not this frozen list; the DE full-dir grep found FOUR files, after CA found one and Codex found a second — a static list has proven incomplete twice):**
    - `season_aggregate_writers.md` — its entire subject is the retiring writer path; strike stale references.
    - `season_tables_are_a_pure_cache.md` — mostly ACTIVE/correct E-259 design basis (it is where §3's "refuse the cutover, a frozen archive is a stale-data trap" language originated), BUT **line 10's rollback advice "rollback is just `git revert` + re-run `canonical_recompute`" is SUPERSEDED** — reconcile it against epic §3's corrected rollback framing (story 02 deletes `canonical_recompute`). Reconcile, do not wholesale-evict.
    - `MEMORY.md` (DE index) — line ~59 "aggregate tables (`player_season_*`) valid when query-time computation is impractical" becomes false post-cutover; plus the index pointers to the two files above.
    - `fixture_seed_not_rollup_consistent.md` — its caution about `seed.sql`'s `player_season_*` rows goes stale once the readers derive from `player_game_*`.
    - **KEEP (do NOT evict):** `schema_drop_test_blast_radius.md` mentions the tables but is **live DROP-test guidance** — cross-reference it in E-259-03, do not strike it.
    DE edits its own memory content per the ownership carve-out.
11. `.claude/skills/implement/SKILL.md` + `.claude/agents/code-reviewer.md` Step 1d — **strike the `verify-aggregates` HARD sub-check E-256 added**, AND strike `verify-aggregates` from `code-reviewer.md`'s **Test-Execution-Constraint enumerated command list** (the E-256-11 carve-out authorizes it there too — else CR keeps an authorization for a deleted command). Record it as deletion-side eviction (Technical Notes §6). This is a PLAIN DELETION, not a substitution.

Doc-sweep discipline applies throughout (`.claude/rules/doc-sweep.md`): token grep + synonym expansion + semantic read. Docs-runbook references route to docs-writer (story 06), not claude-architect.

### §6. Retiring `verify-aggregates` is a plain deletion, NOT a substitution
When story 05 strikes the Step 1d `verify-aggregates` sub-check, it does **not** install a replacement into the vacated slot:
- `reconcile-scoreboard` does not move into the slot — it is **already** a separate, unconditional Step 1d check (check 5), and the golden report test already runs under the Step 1b full-suite gate.
- The check does not become "vacuously true" — it becomes **unrepresentable**: post-cutover the aggregate IS the query, so "stored vs. recomputed" has **no left-hand side**.
- The surviving golden test is a **regression** guard (proves new SQL returns what old SQL returned), not an **integrity** guard (cannot prove either is right) — and that is correct, because post-cutover **no aggregate-integrity property remains** to check.

Record this as the epic's **trigger-7 counterweight**: net context-layer shrinkage is the win, not a hole that wants filling. (PM lesson: `.claude/agent-memory/product-manager/feedback_record_shrinkage_dont_substitute.md`.)

### §7. Additional dead code this epic deletes (beyond the audit's count)
- `scripts/validate_plays_stats.py` (~800 lines) + `tests/test_validate_plays_stats.py` (~1,021 lines) — a reader the audit missed, already a silent no-op because its `fps`/`qab` columns are in the all-NULL set post-E-239. Deleted in story 04.
- `_merge_season_rows` in `src/db/player_dedup.py` dies **entirely** (not just its member-row half), along with `_COMPLETENESS_RANK` at `:473` — three of E-237/E-253's hardest-won guards become unnecessary rather than merely dead, because the mixed-provenance scope they defended cannot exist once no writer produces member rows and no stored table survives. Retired in story 02.
- `merge_player_pair`'s member-row re-point logic (E-237) becomes dead code post-cutover (DE confirmed) — retire it in story 02.

### §8. ORDER BY must be reproduced over the new projection (an E-259 flag, not E-256)
The two fetch functions currently order over **stored aggregate columns**: `get_season_batting` by `(ab+bb+hbp+shf) DESC, last_name ASC`; `get_season_pitching` by `COALESCE(ip_outs,0) DESC, last_name ASC`. E-256's relocation left these byte-unchanged (a pure move). When story 01 rewrites the SQL bodies to derive from `player_game_*`, those ORDER BY columns become **expressions over per-game SUMs** — story 01 MUST reproduce the same ordering semantics over the new projection, or player row order shifts and the golden test breaks. This is named here so it is not discovered mid-cutover. (SE flagged it during the seam resolution.)

## Open Questions
- None. The seam contract, the perspective hazard, the migration-refusal mechanism, the member-row survey, and the eviction surface are all settled. The only gate is the operator Prerequisites above, which are pre-dispatch, not planning-blocking.

## History
- 2026-07-09: Created as a full DRAFT, split out of the E-256 stub (CE-6) by user decision. Expert consultation completed with data-engineer (owner) and claude-architect. **Seam contract = DE's relocation contract** (option (c) rejected): E-256 relocates the pure fetch to `src/api/db.py`; **E-259 rewrites the SQL body in place** inside `get_season_*` (one legible old-vs-new-SQL hunk per function). DE's live-DB member-row survey (zero rows) recorded; migration-refusal preflight mechanizes it. Discharges the `docs/ROADMAP.md:341`/`:345` deferred note without reopening Epic C's slice status.
- 2026-07-09 (internal review + Codex): CR/SE/DE/CA holistics + Codex spec-review incorporated. **P1 cross-epic dependency modeled** — hard "E-256 COMPLETED + merged" Prerequisite 0 added; E-259-01 (←E-256-04 relocation) and E-259-05 (←E-256-11 Step 1d surface) `Blocked by` fields annotated (verified: `get_season_*` absent from `src/api/db.py` today). **Propagation reframe (CA Q2)** — AC-5 rewritten from a static file list to a per-agent grep-and-reconcile obligation; the DE-memory seed grew from 1 (CA) → 2 (Codex) → 4 (PM full-dir grep): `season_aggregate_writers.md`, `season_tables_are_a_pure_cache.md` (line-10 superseded rollback reconciled vs §3), `MEMORY.md`, `fixture_seed_not_rollup_consistent.md`; `schema_drop_test_blast_radius.md` KEPT (live DROP guidance, cross-ref'd in E-259-03). **AC-6 DROPPED (CA Q3)** — trigger-7 shrinkage accounting is the closure Context-Layer Assessment Gate's job; story 05 supplies the eviction tally to PM via Handoff Context, the closure gate writes the verdict. `schema_drop_test_blast_radius.md` referenced in E-259-03.
- 2026-07-09 (Codex round 2, 3 findings incorporated — circuit breaker, no round 3): **P1 E-259-05 AC-5 dispatchability** — the Q2 per-agent grep-and-reconcile made a single-CA-assigned story require DE/SE/code-reviewer to each edit their own dir, which a single-assignee story cannot do. Resolved per CA's user-approved 3-part ruling: (1) story 05 keeps only CA-owned files + CA's own memory (`epic-codifications.md`, AC-5); (2) a NEW AC-6 generalizes the Deletion-Side-Eviction rule in `.claude/rules/context-layer-assessment.md` to grep each agent's own dir (index AND topic files), reconciled by the owning agent — a trigger-8 promotion; (3) the DE/SE/CR memory sweep becomes an archival-blocking closure obligation (DE, on the team, reconciles its four files at closure), stronger than the unenforceable cross-agent AC. §5 preamble reclassified (items 1–7,11 = story 05; items 8–10 = closure). Collision check: no other E-259 story touches `context-layer-assessment.md`. **P3 E-259-03 AC-5** — migration re-glob reworded number-agnostic (`011` is a placeholder for "the next free number"; reconciling the story's own references is NOT part of completion, removing the spec-rewrite dependency). **P3 E-259-05:13** — stale "ten files" neutralized to "the files enumerated in §5" (count-drift-proof, not bumped to eleven). Story count unchanged at 6; E-259-05 AC count 5→6.
- 2026-07-09 (**READY** — review scorecard). Set READY after two Codex iterations plus internal review (circuit breaker — no third round). Review-Scorecard:

  | Pass | Findings | Accepted | Dismissed |
  |---|---|---|---|
  | Internal iter 1 — holistic (SE/DE/CA) + CR spec audit | DE holistic clean (3 refinements); SE/CA incorporated | all | 0 |
  | Codex round 1 | 4 | 4 | 0 (shaped by CA rulings Q2–Q3) |
  | Codex round 2 | 3 | 3 | 0 |
  | **Total (E-259)** | — | — | **0** |

  Notes: the CR spec-audit and SE/DE/CA holistic passes were session-wide (both epics); no dismissal landed on E-259 (the session's 2 dismissals were both E-256 internal-CR). Codex rows are E-259-specific. Story count 6 unchanged across every pass; E-259-05's AC count moved 5→6 in round 2 (the AC-5 dispatchability restructure), not a story add.
- 2026-07-12 (**READY re-confirmed** vs E-256's landed reality — E-256 COMPLETED+merged, commit `2e28b30`): **CLEAN — all 6 cutover premises hold** (Prerequisite 0 satisfied; the pure season-fetch is relocated to `src/api/db.py::get_season_batting`/`get_season_pitching` with `_query_*` wrappers + golden zero-diff bracket intact for E-259-01; the Step 1d closure-smoke surface exists for E-259-05; next migration = 011; the `reconcile-scoreboard` baseline + `verify-aggregates` operator-gate mechanisms exist; DE's zero-member-row survey still governs migration 011's refuse-on-nonzero). **READY clock reset to 2026-07-12** per the stale-READY Freshness Gate.
