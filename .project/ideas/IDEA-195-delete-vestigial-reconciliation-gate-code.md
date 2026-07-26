# IDEA-195: Delete the Vestigial Reconciliation-Ratchet Gate Code

## Status
`CANDIDATE`

## Summary
The reconciliation one-way ratchet gate was retired on 2026-07-26 (the D2 decision, commit `877413e`) and `bb report reconcile-scoreboard` is now a pure diagnostic. Roughly 180 lines of gate machinery in `src/reports/recon_scoreboard.py` still exist, still import, and still run -- a named vestige rather than a suspected one. Delete the gate half; keep the measurement half.

## Why It Matters
Dead code that still *executes* is worse than dead code that merely sits there. This vestige can be invoked, will produce a plausible pass/fail verdict against a baseline nobody maintains, and reports nothing wrong while doing it -- the quiet failure mode, not the loud one. A future reader has no way to tell from the code that the verdict it computes was retired by decision rather than by defect. `.claude/rules/doc-sweep.md` names this exact shape: a prose sweep structurally cannot see code that still parses, so retiring the *claim* left the *executable* standing.

**Delete (verified present 2026-07-26, all in `src/reports/recon_scoreboard.py` unless noted):**
- `evaluate_gate` (line 588), `load_baseline` (570), `write_baseline` (641), `default_baseline_path` (492)
- `GateResult` (536), `GateViolation` (509), `BaselineError` (481)
- `RATCHETED_AXIS_COUNTERS` (472) and its two use sites (561, 623)
- the `--update-baseline` flag, its CLI branch, and its `0/1/3/4` exit-code contract in `src/cli/report.py`
- the gate tests in `tests/test_recon_scoreboard.py`
- the baseline file `.project/baselines/reconciliation-scoreboard.json`

**Keep:** `compute_scoreboard` (350), `to_json_dict` (428), and the stat-definition constants. Those are the diagnostic, and `.claude/rules/canonical-seams.md` records the constants as **code-canonical** -- the E-245 baseline doc mirrors them by hand, so they must not be disturbed by this deletion.

## Rough Timing
Someday. The natural carrier is the next epic that touches `src/reports/recon_scoreboard.py` for any reason -- fold it in rather than planning a deletion epic around it. Nothing breaks while it sits.

## Dependencies & Blockers
- [ ] None. The gate has no live consumer: it is retired by decision, and the diagnostic path does not call it.

## Open Questions
- Does `docs/admin/operations.md` still document the gate as a gate? It matched a live grep for the gate vocabulary and is the one operator-facing surface in the list. Whoever picks this up should read it -- doc reconciliation may be the more valuable half of the change, since an operator following a runbook for a retired gate is a worse outcome than unused code.
- `scripts/reclaim_orphan_reference_data.py` and `tests/test_reclaim_orphan_script.py` also matched the baseline vocabulary. They are almost certainly E-273's own separate baseline convention rather than this gate, but that was **not** confirmed -- check before deleting anything there.

## Notes
Source: filed 2026-07-26 as a pre-approved queue item, alongside the E-072/E-175 triage dispositions. The retirement itself is recorded in CLAUDE.md's Operating Principle section: the scoreboard survives as a standing measurement (run it before and after an ingestion change and compare), and the North Star still binds as direction and judgment -- **retiring the gate did not retire the principle**, so do not read this deletion as licence to stop measuring.

**⚠️ FOOTGUN -- there are TWO ratchets in this repo and they share vocabulary. Only one is retired.**

- **Retired**: the *reconciliation* ratchet -- this one. Baseline `.project/baselines/reconciliation-scoreboard.json`, gate code in `recon_scoreboard.py`, flag `--update-baseline` on `bb report reconcile-scoreboard`.
- **LIVE**: the *context-layer* ratchet -- trigger 7 of `.claude/rules/context-layer-assessment.md`, hook `.claude/hooks/context-ratchet.sh`, baseline `.project/baselines/context-layer-ratchet.json`, also carrying an `--update-baseline` flag. **This one still gates every epic closure and is not in scope here.**

A grep for `--update-baseline`, `baseline`, or "ratchet" hits both. A sweep driven off that vocabulary would delete a live closure gate, and the two baseline JSONs sit **in the same directory** with adjacent names. Scope this deletion by the *file* (`recon_scoreboard.py`, its tests, its own baseline JSON), never by the shared vocabulary. Related: [[IDEA-123]], whose ratchet-false-FAIL failure mode was dissolved by the same retirement.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
