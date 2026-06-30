# E-246: Dead-Code Removal & Low-Risk Consolidation

## Status
`READY`
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
| E-246-01 | Delete dead 3-tier gc_uuid resolver and its test | TODO | None | - |
| E-246-02 | Remove dead/vestigial code (crawlers, API, signing, parser) | TODO | None | - |
| E-246-03 | Consolidate DB-path resolution cascade to one canonical source | TODO | None | - |
| E-246-04 | Hoist aggregate-parity SUM projections into shared builders | TODO | None | - |
| E-246-05 | Collapse spray play_type→contact→marker mapping to one source | TODO | None | - |
| E-246-06 | Dedup low-risk CLI/safety constants, predicates, printers | TODO | E-246-03 | - |
| E-246-07 | Delete dead GameChangerClient verbs (post, delete) | TODO | None | - |

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

## History
- 2026-06-29: Created (READY). Scoped from the whole-project code-quality sweep as the low-risk first wave; H2/H4/H3-consolidate/M4/M5/M6/M3 → E-247, H5 → E-248.
- 2026-06-29: User sign-offs resolved — H3 confirmed delete; DATABASE_PATH approved; parity gate set to blocking pre-closure (`bb report verify-aggregates` must be clean before the closure commit). Updated ahead of Codex spec review.
- 2026-06-29: Codex spec-review findings incorporated — added omitted test files to story file lists; reframed behavior-change accounting (one change + one operator gate); named exact proof artifacts (spray semantic assertions; aggregate golden-fixture); recorded DE consultation rationale; moved per-story full-suite ACs to module-local surfaces (full-suite-green stays the closure gate).
- 2026-06-30: Added **E-246-07** (delete dead GC client verbs `post()`/`delete()`) per the user-delegated Option-A scope fork — api-scout grep-verified the verbs are dead (only-caller follow/unfollow path removed in E-239 + banned). Cross-epic ordering: E-246 before E-248 (shared `client.py`/`test_client.py`).
