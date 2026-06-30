# E-247-02: Extract reconciliation per-game detection block

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`DONE`

## Description
After this story is complete, the ~100-line per-game discrepancy-detection block in the reconciliation engine — currently reproduced verbatim for the initial detection and the post-correction re-detection — will exist once as a single detection function that both passes call. This guarantees the dry-run and execute modes cannot silently diverge.

## Context
The sweep's H4 finding: in `src/reconciliation/engine.py`, ~100 lines of per-game detection orchestration (load plays/events index, per-team SQL, 3 check calls, 3 identical SQL strings) are reproduced verbatim at `:190-388` (initial) and `:543-588` (re-detection). A new signal or query change must be applied twice or detection diverges between dry-run and execute mode. The execute path can be expressed as detect→correct→detect over the shared function. The report also notes the two-pass `plays_pitchers` accumulation can fold into one loop. Reconciliation output is covered by existing recon tests, so byte-identical output is verifiable.

## Acceptance Criteria
- [ ] **AC-1**: Given the detection orchestration is duplicated across initial and re-detection, when the story completes, then it exists once as a single detection function returning the per-game discrepancies, and both the dry-run and execute paths call it (the execute path becomes detect→correct→detect).
- [ ] **AC-2**: Given the duplicated SQL strings and the two-pass `plays_pitchers` accumulation, when the story completes, then each SQL string and the accumulation are expressed once.
- [ ] **AC-3**: Given the extraction (HARD GATE — stats integrity, per epic Technical Notes; reconciliation corrects pitcher attribution, so a detection regression silently corrupts stats), when the detection runs in both the dry-run and the execute (detect→correct→detect) paths against representative data, then the detected discrepancies are byte-identical between the two paths and byte-identical to the pre-story output for each mode. This is proven by a golden-fixture/characterization `pytest` test (extend the existing recon tests; add focused coverage for any uncovered mode) — not by inspection. If equivalence cannot be proven, the story is cut/deferred, not shipped.
- [ ] **AC-4**: Given the extraction, when `tests/test_reconciliation.py` (including the AC-3 golden-fixture/characterization test) runs, then it passes. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/reconciliation/engine.py:190-388`, `:543-588`. Extract a single detection function (the sweep suggests `_detect_discrepancies(...) -> list[_Discrepancy]` — illustrative); the execute path becomes detect→correct→detect. Fold the two-pass `plays_pitchers` accumulation into one loop. Output must stay byte-identical — the existing recon tests are the primary verification surface.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reconciliation/engine.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Reconciliation output verified byte-identical across dry-run/execute/summary
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Self-contained to one file. The dry-run/execute divergence risk is exactly what this extraction closes.
