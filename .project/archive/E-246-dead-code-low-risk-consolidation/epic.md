# E-246: Dead-Code Removal & Low-Risk Consolidation

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Delete grep-confirmed dead code left behind by removed surfaces (E-239 member-sync/opponents, E-241 compound season slugs) and consolidate a handful of low-risk hand-copied blocks into single canonical sources. This is the low-risk, high-value first wave of a whole-project maintainability sweep: every change here is either a deletion of code with zero importers or a byte-identical consolidation, with exactly one intended behavior change (E-246-03 makes `cli/data.py` honor `DATABASE_PATH`) plus one operator gate (the blocking pre-closure parity check).

## Background & Context
A whole-project code-quality sweep over all of `src/` (~29k lines, 11 subsystems) surfaced 13 deduplicated maintainability themes. The sweep found a healthy codebase: no correctness bugs and no hot-path efficiency problems (all efficiency findings are N=1/offline). The themes cluster into two patterns: (1) "twin-method / copy-pasted block" where the correct fix pattern already exists elsewhere and several copies have already silently drifted; (2) dead-code residue from removed surfaces. This epic takes the lowest-risk subset — dead-code deletions plus trivial consolidations — so it can be shipped quickly with a light review burden, independent of the higher-risk structural work in E-247 and E-248.

The full triage report is the evidence base; each story below preserves the report's `file:line` locations and "drift already happening" notes. Two pre-existing ideas are effectively promoted into this epic: IDEA-046 (resolver duplicate gc_uuid) and IDEA-081 (post-E241 dead-code/stale-example sweep).

**E-246-07 added during Codex spec-review triage (Option A scope fork).** api-scout verified that the GC client's `post()` and `delete()` verbs are dead (zero production callers; only-caller follow/unfollow path removed in E-239, now banned). The user delegated the scope decision to PM, who chose to delete them as dead code here (E-246-07) rather than refactor them in E-248 — keeping the cleanup in this epic's dead-code domain and shrinking the HIGH-blast-radius E-248 refactor to 4 live verbs. Full rationale + api-scout's consult note are recorded in the E-248 epic Background.

**Expert consultation.** The one DB/ETL-domain story, E-246-04 (aggregate-parity SUM-projection hoist), is owned and implemented by **data-engineer** (on this epic's Dispatch Team). No separate advisory consultation was required: the change is a byte-identical hoist of an existing projection into a shared source within the already-canonical `canonical_recompute` function — it adds no column, changes no query semantics, and is gated by both an in-dispatch golden-fixture proof and the blocking pre-closure `verify-aggregates` parity check (see Technical Notes). **baseball-coach** was not consulted because no story changes a stat definition — every consolidation is a byte-identical/algebraically-equal refactor. **api-scout**: no GC-API surface in this epic (the dead gc_uuid resolver in E-246-01 is deleted, not exercised).

This epic implements no `docs/ROADMAP.md` §5 slice — it is internal maintainability work, so the Roadmap reference convention does not apply.

## Goals
- Delete the dead 3-tier gc_uuid resolver and its test (zero importers, grep-confirmed; its Tier-1/2 data sources were removed in E-239).
- Delete the two dead GameChanger API client verbs `post()` and `delete()` and their tests (zero production callers; only-caller follow/unfollow path removed in E-239 — see E-246-07). This shrinks E-248's refactor surface from 6 verbs to 4.
- Delete all grep-confirmed dead/vestigial code across crawlers, API helpers, signing, and the plays parser; correct now-stale crawler docstrings to the in-memory contract.
- Collapse the 5×-duplicated DB-path resolution cascade to a single canonical source, fixing the operator-visible inconsistency where `cli/data.py` silently ignores `DATABASE_PATH`.
- Hoist the season-aggregate SUM projections into shared builders so the `verify-aggregates` parity check can never silently sum a stale column subset.
- Collapse the spray-chart play_type→contact→marker vocabulary (encoded in 3 parallel places) to a single source so legend and markers cannot desync.
- Consolidate the low-risk CLI/safety constant/predicate/printer duplications.

## Non-Goals
- The twin-method loader/reconciliation extractions (H2, H4) — E-247.
- The live public_id→gc_uuid search-seam consolidation and `is_uuid()` helper (H3 consolidation half) — E-247.
- The GC API client error-ladder refactor (H5) — E-248.
- Any change to stat definitions, report output content, or query results beyond byte-identical refactors.
- Wiring freshness gating back in (the dead `freshness_hours`/`_is_scouted_recently` path) — out of scope; this epic deletes the dead code and its tests-only callers.

## Success Criteria
- **Stats integrity (HARD GATE — outranks everything else in this epic):** no story regresses stats collection or accuracy. The sole stat-bearing story (E-246-04, aggregate-parity SQL) proves byte-identical query output via a golden-fixture/characterization test under `pytest` (the implementer's in-dispatch gate), AND `bb report verify-aggregates` MUST be run clean by the operator in the devcontainer **before the closure commit** — a non-clean result **blocks closure**. See Technical Notes "Stats Integrity — HARD GATE" and "Closure Gate (blocking)."
- Every grep-confirmed-dead symbol named in the stories is removed and a fresh grep across `src/` and `tests/` returns zero references.
- The DB-path cascade resolves through one canonical function; `cli/data.py` commands honor `DATABASE_PATH` (verified by test).
- The aggregate-parity check and `canonical_recompute` share the same SUM-projection source; `bb report verify-aggregates` output is unchanged on existing data.
- Spray-chart markers and legend derive from one shared table.
- `python -m pytest tests/` reports 0 failed in the main checkout after all stories land.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-246-01 | Delete dead 3-tier gc_uuid resolver and its test | DONE | None | SE |
| E-246-02 | Remove dead/vestigial code (crawlers, API, signing, parser) | DONE | None | SE |
| E-246-03 | Consolidate DB-path resolution cascade to one canonical source | DONE | None | SE |
| E-246-04 | Hoist aggregate-parity SUM projections into shared builders | DONE | None | DE |
| E-246-05 | Collapse spray play_type→contact→marker mapping to one source | DONE | None | SE |
| E-246-06 | Dedup low-risk CLI/safety constants, predicates, printers | DONE | E-246-03 | SE |
| E-246-07 | Delete dead GameChangerClient verbs (post, delete) | DONE | None | SE |

## Dispatch Team
- software-engineer
- data-engineer

## Technical Notes

### Stats Integrity — HARD GATE (non-negotiable, outranks the cleanup)
No change in this epic may regress stats collection or accuracy. This constraint outranks the cleanup itself: if a theme cannot be made provably stat-equivalent, it is **cut or deferred — never shipped on faith.** It binds to the project north-star ("always get closer to byte-identical play ingestion" — a cleanup must never move a stat away from the boxscore) and is enforced at three levels:
1. **Per-story proof (in-worktree):** every stat-bearing story proves output equivalence with a golden-fixture or characterization test that runs under `pytest` — not visual inspection, not "looks equivalent." The test pins the pre-change output and passes against the post-change code.
2. **Full-suite-green closure gate:** `python -m pytest tests/` reports 0 failed in the main checkout at closure (the standing closure gate).
3. **Blocking pre-closure parity gate (operator):** before the closure commit, the operator runs `bb report verify-aggregates` in the devcontainer; it MUST return clean (no per-cell mismatches). A non-clean result **blocks closure** — the closure commit MUST NOT proceed until parity is clean. The `bb` CLI and `data/` are unavailable in epic worktrees, so this is an operator/closure-sequence gate, not an in-dispatch implementer AC. See "Closure Gate (blocking)" below.

### Closure Gate (blocking)
This epic's closure commit MUST NOT proceed until BOTH hold: (a) the full pytest suite is green in the main checkout (standing gate), and (b) the operator has run `bb report verify-aggregates` in the devcontainer and it returned clean. (b) is the user's explicit, non-negotiable parity gate — a non-clean `verify-aggregates` blocks closure regardless of green tests. The operator runs (b) against the merged main checkout (where `data/` and the `bb` CLI exist) before the atomic closure commit; record the clean result in the epic History at closure.

**Stat surface per story:**
- **Stat-bearing (concentrate verification here):** E-246-04 (H1 aggregate-parity SQL — touches season-aggregate denominators).
- **Stat-adjacent (low surface, confirm unchanged):** E-246-02 (M2) removes a redundant `strikes < 2` guard in the plays parser and an unreachable `None` branch in signing — both must be proven unreachable/redundant so parser/signing output is unchanged (AC-4 of that story).
- **Pure-mechanical, zero stat surface (fast-track):** E-246-01 (dead-resolver deletion, grep-confirmed unreferenced), E-246-03 (DB-path resolution), E-246-05 (spray markers — visual only), E-246-06 (CLI/safety printers), E-246-07 (dead client-verb deletion — the verbs are never called in the collection path; grep-confirmed dead). Triage may fast-track these on grep/byte-identical-output evidence.

### Evidence base
The triage report (whole-project code-quality sweep) is the source of every `file:line` location and "drift already happening" note in this epic's stories. Treat those locations as starting points, not exhaustive — the implementing agent must re-confirm each via a fresh grep before acting (per the tool-output-integrity clean-reread discipline), because line numbers may have shifted.

### No-behavior-change constraint and its one exception
This epic has exactly **one intended behavior change** plus **one operator gate** — nothing else:
1. **Behavior change — E-246-03 (M1)**: making `cli/data.py` commands honor `DATABASE_PATH` is an intended behavior change — today those commands silently ignore it while `cli/report.py` honors it. (The `APP_URL` default change is a separate theme in E-247, not here.)
2. **Operator gate (not a behavior change) — the blocking pre-closure parity check**: the operator runs `bb report verify-aggregates` clean before the closure commit (see "Closure Gate (blocking)"). This is a process gate, not a change to runtime behavior.

For every other change, the implementing agent must verify behavior is preserved — for deletions, by confirming zero importers/callers via grep; for consolidations, by confirming output is byte-identical (existing tests, or a before/after comparison where no test exists).

### Reuse the canonical helpers
Where a canonical helper already exists, route the consolidated code through it rather than inventing a parallel one. The sweep's suggested helper shapes are illustrative starting points; the implementing agent owns the final shape. Do not re-derive a column set or projection that a canonical function already owns.

### Story sequencing
E-246-06 (L1) and E-246-03 (M1) both touch `src/cli/data.py`; E-246-06 is therefore blocked by E-246-03. All other stories are file-disjoint and execute serially in any order.

### Cross-epic overlap (with E-247 and E-248)
- **E-247** overlaps on `src/gamechanger/crawlers/opponents.py` (E-246-02 here removes dead `import json`/`data_root` plumbing and corrects a stale docstring; E-247-03 there consolidates `resolve_own_team_gc_uuid` — different regions). Dispatch **E-246 before E-247** so this cleanup lands first and E-247-03 rebases onto it.
- **E-248** overlaps on `src/gamechanger/client.py` + `tests/test_client.py` (E-246-07 here deletes the dead `post()`/`delete()` verbs and their tests; E-248 refactors the surviving 4 live verbs in the same files). Dispatch **E-246 before E-248** so the dead verbs are gone before E-248 pins/refactors the survivors (see E-248 Technical Notes "Cross-epic ordering").
- Net ordering: **E-246 first**, then E-247 and E-248 (E-247 and E-248 are file-disjoint from each other).

## Open Questions
All pre-dispatch sign-offs are resolved (user decisions, 2026-06-29). None remain open.
- **[RESOLVED] H3 deletion (E-246-01) — CONFIRMED DELETE.** The user confirmed deleting the dead 343-line resolver + ~900-line test rather than retaining as reference; git history retains the code. The story keeps its fresh-grep re-confirmation as the pre-delete safety check.
- **[RESOLVED] DATABASE_PATH behavior change (E-246-03) — APPROVED.** The user approved `bb data` commands newly honoring `DATABASE_PATH`. Proceed as intended; note for operators at closure.
- **[RESOLVED] Parity gate — BLOCKING PRE-CLOSURE.** The user chose to make `bb report verify-aggregates` a blocking pre-closure operator gate (see Technical Notes "Closure Gate (blocking)").

## Review Scorecard
| Review stage | Outcome |
|--------------|---------|
| Per-story CR — E-246-01 | APPROVED round-1; 1 SHOULD FIX (stale `gc_uuid_resolver` ref in `.claude/rules/gc-uuid-bridge.md`) → fixed by claude-architect in-dispatch |
| Per-story CR — E-246-02 | APPROVED round-1; 0 findings |
| Per-story CR — E-246-03 | APPROVED round-1; 0 findings (api/db.py relative-path nuance ruled functionally inert) |
| Per-story CR — E-246-04 (HARD GATE) | APPROVED round-1; 0 findings (adversarial golden-oracle verification) |
| Per-story CR — E-246-05 | APPROVED round-1; 0 findings |
| Per-story CR — E-246-06 | APPROVED round-1; 0 findings (security-relevant pii_scanner gate branch-equivalence verified) |
| Per-story CR — E-246-07 | APPROVED round-1; 0 findings |
| Phase 4a CR integration review | APPROVED; 0 findings |
| Phase 4b Codex review | 1 found / 1 accepted (remediated in-dispatch, CR byte-preservation APPROVED) / 0 dismissed |

Totals: per-story 1 SHOULD FIX (E-246-01, fixed) + 0 MUST FIX across all 7 stories; integration 0; Codex 1 found / 1 accepted / 0 dismissed.

## History
- 2026-06-29: Created (READY). Scoped from the whole-project code-quality sweep as the low-risk first wave; H2/H4/H3-consolidate/M4/M5/M6/M3 → E-247, H5 → E-248.
- 2026-06-29: User sign-offs resolved — H3 confirmed delete; DATABASE_PATH approved; parity gate set to blocking pre-closure (`bb report verify-aggregates` must be clean before the closure commit). Updated ahead of Codex spec review.
- 2026-06-29: Codex spec-review findings incorporated — added omitted test files to story file lists; reframed behavior-change accounting (one change + one operator gate); named exact proof artifacts (spray semantic assertions; aggregate golden-fixture); recorded DE consultation rationale; moved per-story full-suite ACs to module-local surfaces (full-suite-green stays the closure gate).
- 2026-06-30: Added **E-246-07** (delete dead GC client verbs `post()`/`delete()`) per the user-delegated Option-A scope fork — api-scout grep-verified the verbs are dead (only-caller follow/unfollow path removed in E-239 + banned). Cross-epic ordering: E-246 before E-248 (shared `client.py`/`test_client.py`).
- 2026-06-30: All 7 stories DONE (E-246-01 — E-246-07); each AC-verified by PM and approved by code-reviewer (no MUST FIX across the epic).
- 2026-06-30: **Phase 4b Codex review scorecard — 1 found, 1 accepted (remediated in-dispatch), 0 dismissed.** Finding (on E-246-04): `aggregate_parity.py` kept a SECOND manual column list (`_BATTING_COLUMNS:77`/`_PITCHING_COLUMNS:98`, the `diff_columns` mapping) separate from the shared `*_RECOMPUTE_KEYS` the story hoisted — `_check_table` only diffs columns in `diff_columns`, so a future column added to the single source would be recomputed but silently NOT compared, leaving AC-3's "no second edit site" true only for the SUM projection, not end-to-end. DE + CR confirmed VALID; no current integrity gap (`diff_columns` set == `RECOMPUTE_KEYS` today; tests pass) — latent/future hazard, CR ruled SHOULD FIX (hard-gate-adjacent). Triaged to fix in-epic. Remediation routed to DE: derive `_BATTING_COLUMNS`/`_PITCHING_COLUMNS` from `*_RECOMPUTE_KEYS` (special-casing the `gp`/`gp_pitcher`→`games_tracked` stored alias), byte-preserving the current tuples (cells_compared stays 74), plus a guard test pinning the `diff_columns` == `RECOMPUTE_KEYS[1:]` single-source invariant. DE remediated; CR byte-preservation verification APPROVED (byte-preserving, `cells_compared` still 74); AC-3 now fully (end-to-end, literally) satisfied — no second edit site remains.
- 2026-06-30: **Phase 4a CR integration review — APPROVED, 0 findings** (repo-wide surface-removal sweep clean, no cross-story clobbering, no import cycles).
- 2026-06-30: **Closure assessments (Phase 5).**
  - **Documentation assessment** (per `.claude/rules/documentation.md`): triggers 1-4 = no; trigger 5 (changes how users interact) = no mandatory impact. The sole behavior change (E-246-03: `bb data` now honors `DATABASE_PATH`) is consistency-restoring (matches `bb report`) and production-unaffected (production uses an absolute `DATABASE_PATH`; absolute values are unchanged). No existing doc documented the prior inconsistency, so none is made stale. CLAUDE.md does not document per-command `DATABASE_PATH` resolution. **Verdict: No documentation impact** (optional one-line operator note in `docs/admin/operations.md` is a nice-to-have, deferred to operator discretion).
  - **Context-layer assessment** (per `.claude/rules/context-layer-assessment.md`, six triggers): **(1) New convention/canonical helper — YES.** `resolve_db_path()` (`src/db/paths.py`) is a new canonical entry point (single source of the `override → DATABASE_PATH → default` cascade; all 5 modules delegate); CLAUDE.md's Architecture canonical-helpers list should add it ("new DB-path resolution MUST route through it"). The shared aggregate-parity builders/keys (`batting_recompute_select`/`pitching_recompute_select` + `*_RECOMPUTE_KEYS`) are a related single-source convention. **(2) Architectural decision — no** (no new technology/integration choice beyond the #1 helper). **(3) Footgun/failure mode — YES.** The Phase 4b finding revealed the aggregate-parity seam's second-edit-site trap (a column list separate from the shared projection silently uncompared); now fixed + guard-tested, but `.claude/rules/data-model.md` (Season-Aggregate Parity) warrants a one-line note that the parity check shares BOTH the projection AND the compared-column list with `canonical_recompute` — never reintroduce a separate column list. **(4) Agent behavior/routing/coordination — no.** **(5) Domain knowledge — no.** **(6) New CLI command/workflow — no** (no new `bb` subcommand/script/skill; the `bb data` `DATABASE_PATH` behavior change is covered by #1). Triggers 1 and 3 are YES → claude-architect codification required before archival. The earlier "rule references a now-deleted module" item (gc-uuid-bridge.md) fired during E-246-01 and was remediated in-dispatch; a fresh sweep of `.claude/` + CLAUDE.md confirms no other stale references to any deleted symbol.
- 2026-06-30: **Completed (Phase 5).** Delivered the low-risk first wave of the whole-project maintainability sweep: deleted the dead 3-tier gc_uuid resolver + test (01), the dead/vestigial crawler/API/signing/parser residue (02), and the dead GC client verbs `post()`/`delete()` + tests (07, shrinking E-248 to 4 live verbs); consolidated the 5×-duplicated DB-path cascade into canonical `resolve_db_path()` with `bb data` now honoring `DATABASE_PATH` (03), the aggregate-parity SUM projections + compared-column list into shared builders/keys (04, HARD GATE, byte-identical), the spray play_type→marker vocabulary into one table (05), and the low-risk CLI/safety constant/predicate/printer duplications (06). Zero stat-definition changes; all refactors byte-identical/algebraically-equal. COMPLETED status flip is authored during closure staging (Step 8) so it rides the closure patch under the full-suite-green gate; the blocking pre-closure operator `bb report verify-aggregates` clean run is required before the closure commit.
