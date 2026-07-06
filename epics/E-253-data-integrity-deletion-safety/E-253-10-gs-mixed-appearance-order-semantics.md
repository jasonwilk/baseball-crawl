# E-253-10: GS Mixed-`appearance_order` Semantics — Pin + Operator Check

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`TODO`

## Description
After this story is complete, the documented GS (games-started) aggregation semantics on mixed `appearance_order` data will be pinned by a characterization test, and the operator remediation path for any legacy NULL-`appearance_order` rows on the live DB will be documented and recorded as a follow-up. This discharges the audit's Watch-List "check once during CE-3" mandate.

## Context
Audit Watch-List item (`season_aggregates.py:122`). The GS aggregation uses `CASE WHEN MAX(pgp.appearance_order) IS NULL THEN NULL ELSE SUM(CASE WHEN appearance_order = 1 THEN 1 ELSE 0 END) END`. In a MIXED scope (some rows have `appearance_order` populated, some are legacy NULL), `MAX(...)` is non-NULL, so the ELSE branch runs and NULL rows contribute 0 — i.e., legacy NULL rows count as definite NON-starts and can silently undercount served GS. The finding notes the semantics are documented as intentional and the pipeline self-heals at generation time, but if legacy NULL rows exist on the live DB, served GS can undercount until a recompute runs. The remediation path already exists: `bb data backfill-appearance-order` (populates NULL `appearance_order` from cached boxscore JSON) followed by `canonical_recompute()` / `bb report verify-aggregates`.

## Acceptance Criteria
- [ ] **AC-1**: A characterization test pins the documented mixed-`appearance_order` GS semantics: on a populated fixture where a scope holds BOTH populated (`appearance_order = 1`) and legacy NULL rows, the test asserts the current CASE behavior (NULL rows contribute 0 to GS in a mixed scope) so a future refactor cannot silently change it without failing the test. The fixture must be populated and stale-disagreeing per `.claude/rules/data-model.md` ("Idempotent-recompute characterization tests need a populated, stale-disagreeing fixture").
- [ ] **AC-2**: Given AC-1's test reveals the documented semantics are wrong for the coaching use case, the implementer STOPS and flags PM rather than changing the aggregation behavior under this story (a scope change) — verified by the story shipping with no production change to the `season_aggregates.py` GS CASE unless PM has authorized a scope change.

<!-- P1 (Codex iter-1): the operator-remediation-doc and live-DB-check items are NOT code-verifiable story ACs.
     They now live in Handoff Context (below) and the epic Success Criteria / closure follow-ups, where they are
     actually actioned. This keeps E-253-10 a clean SE slice (the semantics pin + test). -->


## Technical Approach
This is a low-risk pinning + documentation story. The implementing agent writes the characterization test against the existing `season_aggregates.py` GS CASE (no behavior change — the semantics are intentional) and documents the operator remediation. If the test reveals the documented semantics are actually wrong for the coaching use case, STOP and flag to PM — do not change the aggregation behavior under this story (that would be a scope change).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/` — GS mixed-`appearance_order` characterization test
- (No production code change expected — the semantics are documented as intentional.)

## Agent Hint
software-engineer

## Handoff Context
- **Operator remediation path (for the epic close / operator runbook)**: if legacy NULL `appearance_order` rows exist on the live DB, run `bb data backfill-appearance-order` then recompute (`canonical_recompute` / `bb report verify-aggregates`). (Moved here from a story AC per P1 — it is documentation, not a code-verifiable deliverable.)
- **Produces for the epic close**: an operator follow-up owed — live-DB check for legacy NULL `appearance_order` rows and GS undercount; remediate per the path above if found. This is the Watch-List "check once during CE-3" discharge; record it in the epic completion summary (already captured in epic Success Criteria).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/data-model.md` (Appearance order; Season-Aggregate Parity — characterization-test-needs-populated-fixture), `.claude/rules/key-metrics.md` (GS/GR — the NULL-safe CASE and GS coaching priority).
