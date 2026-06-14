# E-235-02: Restructure `generate_report()` into named stage methods writing the run record

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`DONE`

## Description
After this story is complete, `generate_report()` is organized into named stage methods (crawl, load, gc_uuid, spray, plays, reconciliation, enrichment), each writing its status and counts to a `report_generation_runs` row that is created at the start of generation and finalized at the end. The pipeline's externally-observable behavior is unchanged except for the new run record.

## Context
`generate_report()` is one ≈390-line function with stages already comment-delimited but no per-stage record. This is the keystone restructure (ROADMAP §5 Epic B item 6): it gives every generation an audit trail and is the seam the quality gates (story 03), admin surfacing (story 06), and footer (story 07) build on. The restructure is **refactor-only** — it must preserve stage order, the two-tier fail contract, the snapshot boundary, and cross-stage state exactly. The full restructure constraints, the per-stage counts to write, and the verification requirement are in **epic Technical Notes §TN-2** (with §TN-8 cross-cutting). SE's grounding identified the two cross-stage state seams and the two-tier fail contract as the things most likely to break.

## Acceptance Criteria
- [ ] **AC-1**: `generate_report()` creates a `report_generation_runs` row immediately after the reports row exists (step 3 — the FK requires it; `overall_status='running'`, `started_at` set), updates each stage's status as it runs, and finalizes (`completed`/`failed`, `completed_at`, `error_stage`/`error_message` on failure) at the end. Signals determined before the run row exists (e.g. `identity_match_method` from the step-2 `ensure_team_row` call) are stashed in the generation context and written when the run row is created (§TN-1/§TN-2, SE-F3).
- [ ] **AC-2**: The stages are extracted into named methods/functions carrying cross-stage state (no 8-argument free functions); stage ORDER is unchanged from the current pipeline. Per §TN-2.
- [ ] **AC-3**: The two-tier fail contract is preserved exactly: crawl `errors>0 AND games_crawled==0` is fatal; the load guard fires only on `errors>0 AND loaded==0`; spray, plays, reconciliation, and Tier-2 enrichment failures remain non-fatal (logged, generation continues). Per §TN-2.
- [ ] **AC-4**: The pre-run team-id snapshot boundary (after reports-row creation, before scouting crawl) is preserved; orphan determination still happens post-pipeline (story 04 changes the *mechanism*, not this story). Per §TN-2.
- [ ] **AC-5**: Per-stage counts are written to the run record as PER-GAME distinct-game counts (§TN-2): `completed_games` (M = distinct completed games on the schedule, sourced from `crawl_result.games` — story confirms the exact completed-game field, SE-F4), `completed_games_with_data` (N = distinct completed games WITH data = the `_query_freshness` count, NOT `load_result.loaded` which counts upserted records, SE-F2), `spray_games`, `plays_games_expected`/`plays_games_covered`, `discrepancies_found`/`discrepancies_corrected`, and `enrichment_status` (reusing the existing Tier-2 status from the enrichment site). NULL for M is a last-resort only if the completed-game field genuinely is not exposed.
- [ ] **AC-6**: E-234's golden stat-table test and aggregate-parity test pass UNCHANGED after the restructure (no stat-value or formula drift), and the E-234-04 negative-path tests pass for every path not changed by story 03. The restructure introduces NO behavior change beyond writing the run record. Per §TN-2/§TN-8.
- [ ] **AC-7**: New/updated tests assert the run record is populated correctly for a successful generation and for a non-fatal-degraded generation (e.g. spray fails → `spray_status` reflects failure, generation still completes).

## Technical Approach
Extract the comment-delimited steps (parse/public-fetch/ensure-team/create-report/crawl/load/gc_uuid/spray/plays/reconcile/query-render-save) into named units that share cross-stage state and a run-record handle. A context dataclass / small stateful object is the natural shape but the mechanism is the implementer's choice — the constraint is preserving behavior and avoiding wide positional signatures (§TN-2). Write run-record updates as each stage resolves. Reuse the existing `test_report_generator.py` mock seams; do not hit the network. Run the E-234 guard tests (`tests/test_report_golden.py`, the aggregate-parity test, the negative-path tests) as part of verification.

## Dependencies
- **Blocked by**: E-235-01
- **Blocks**: E-235-03 (directly; the run record it threads is transitively consumed by 04→05→06 and 07 down the chain — see Handoff Context)

## Files to Create or Modify
- `src/reports/generator.py` (restructure `generate_report()`; add the run-record write helpers / context object)
- `tests/test_report_generator.py` (assert run-record population; preserve existing negative-path coverage)
- Possibly a new small module under `src/reports/` if the context object warrants its own file (implementer's choice)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-235-03**: the restructured stages + run-record handle the gates write flags to, and the per-stage `completed_games`/`completed_games_with_data` counts the no-games gate keys off.
- **Produces for E-235-04**: the restructured orphan-determination boundary the concurrency fix replaces.
- **Produces for E-235-06/07**: the populated run record the admin list and footer read.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (E-234 guards green)

## Notes
This is the sharpest refactor in the epic — the restructure constraints in §TN-2 are acceptance criteria, not guidance. If any stat value drifts against the E-234 goldens, stop and treat it as a defect, not an expected change.
