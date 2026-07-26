# E-276-04: End-to-End Churn Regression Through `generate_report()`

## Epic
[E-276: Reconcile-at-Load Health Gate — Capture the Prior Set Before the Run's Own Writes](epic.md)

## Status
`DONE` — 2026-07-26. **Both gates cleared**: code-reviewer APPROVED with **no findings — the first clean review of this dispatch** — and all 5 ACs PM-verified. **Send cost 11**, the cheapest story by a wide margin.

**⛔ THE JERSEY OBSERVATION FROM THIS STORY IS CORROBORATION, NOT COVERAGE.** Its pre-fix run fired story 01's AC-15 diagnostic on 9 victims via the **jersey** half, on real committed payloads. **Nothing in this story asserts it** — if that branch regressed tomorrow, this test would not notice. **MF-1's unit test remains the only thing holding it, and this result MUST NOT be cited as a reason to thin that test.** *(Code-reviewer's explicit instruction, recorded here so it survives the epic.)*

**⛔ SCOPE IS FIXED AND WAS ALREADY RULED ON, 2026-07-26.** An executable caller-set pin for `crawl_is_authoritative` was proposed during story 03 and **deliberately NOT placed here**: it is a structural AST test — a different file, a different kind of test, a different subject — and this story is the epic's cleanest single-purpose slice. **Do not absorb it.** It is [[IDEA-190]]. *(That this story is "test-only" is not a reason to host it — test-only is not a subject.)*

**Read AC-2's TN-18 note before writing any assertion.** At this level the epic's anti-WARN steer **INVERTS**: there is no structural retire record at `generate_report()` level, so a WARN or a seam spy is the only signal separating a genuine refusal from *the reconcile never running for that game* — and "the rows survived" is satisfied by both.

## Description

After this story is complete, the end-to-end destructive-path test class in `tests/test_report_generator.py` covers a second run that re-issues **new** player ids, not only a run that drops rows. That is the only pipeline-level regression test capable of catching this defect at the seam where it actually bit — a routine `bb report generate`.

## Context

The E-270-03 class drives the real `generate_report()` twice with only the HTTP transport faked, so the crawler, the loaders, and all three retire helpers are the real thing. It is the closest thing the suite has to production.

**It is currently passing for the right reason — and that was verified, not assumed.** SE wrote two read-only pytest plugins that snapshot the true pre-upsert prior at each producer and recompute the gate both ways at every reconcile call: **295 player-line calls and 153 game-grain calls across the reconcile test files plus this one, 0 divergences, 240 passed.** The cause is that run 2 is a strict subset of run 1 — it drops a game, a roster player and a line player, and introduces no new ids — so post-upsert prior equals pre-upsert prior and both gates agree.

That same subset property is why this class is **structurally incapable** of catching the defect. `.claude/rules/testing.md` is blunt that annotating a coverage gap is not covering it, and that an accurate scope note substitutes for covering the region because accuracy about a gap reads as management of it. This story closes the region rather than annotating it.

The fixture already exists; what it needs is a run-2 variant that re-issues ids.

## Acceptance Criteria

- [ ] **AC-1**: Given two real `generate_report()` runs where run 2's boxscore re-issues **brand-new** player ids for a game rather than dropping players, when the second generation completes, then the prior lines for that game **survive** — the player-line grain refuses rather than retiring them. Against pre-fix code this test FAILS (the lines are hard-deleted); after E-276-01 it PASSES.

- [ ] **AC-2**: Given the same run, when the result is inspected, then the generation still succeeds and still renders a report — the refusal is a refusal, not a pipeline failure. Assert the returned result object, per Technical Notes TN-12: an absence claim needs proof the mechanism completed cleanly, and the reconcile swallows exceptions into an error count by design, so "the rows survived" is also satisfied by a reconcile that blew up.

      **⚠️ At THIS level the epic's anti-WARN steer INVERTS — see TN-18.** There is no structural retire record at `generate_report()` level, so the WARN (or a spy at the reconcile seam) is the **only** positive signal distinguishing a genuine refusal from *the reconcile never running for that game*. That alternative is live: the E-244 redirect footgun makes a per-game stage keyed off source event ids silently no-op on deduped games, and "rows survived" is satisfied by that too. **A clean result object rules out the blew-up case, not the never-ran case.** Following the epic's dominant instruction here would mean asserting on a record that does not exist.

- [ ] **AC-3**: Given the existing subset-shaped run 2 (the current scenario), when it runs, then its behaviour is unchanged — every existing assertion in the class still holds. The new scenario is additive; per TN-5's deletion-neutrality the existing one cannot move.

      **The basis of that guarantee changed and the citation must not outrun it.** TN-5 is no longer a blanket property proved from a conjunction — it is **structural on this grain, conditional on the named premise `W ⊆ fresh`**, and **deletion-scoped**: *never permits a DELETION today's code refuses*, never *permits whenever today permits*. The player-line grain is one of the two where the premise holds, so AC-3 is sound as written — but **do not restate the guarantee in its blanket form**, which is false on roster.

- [ ] **AC-4**: The new scenario is reachable through the existing fixture's state mechanism rather than a parallel fixture, so the two scenarios share the committed real-shape payloads. A payload the crawler cannot parse aborts before the reconcile and leaves a green, worthless test — the silent-defeat mode the class's own docstring names.

- [ ] **AC-5**: `python -m pytest tests/` reports 0 failed.

## Technical Approach

This is a test-only story. No `src/` file changes.

The class's existing docstring documents its seam (transport-level faking via respx, committed anonymized payloads under `tests/fixtures/e2e/`) and the reasons for it. Follow that seam; do not introduce a hand-built client fake.

Constraints that apply: TN-12 (test design — **in particular driving the real producer**), TN-14 (guardrails — `data/app.db` untouched, no network).

**⚠️ TN-12's "assert the result object rather than a spy" does NOT apply at this level, and this paragraph used to say it did.** That was a direct conflict with AC-2 inside this one story: AC-2 states, per TN-18, that `generate_report()` has no structural retire record at all, so the WARN or a spy is the **only** positive signal distinguishing a genuine refusal from *the reconcile never running for that game*. The result object here rules out the blew-up case, not the never-ran case.

**What survives from TN-12 at this level is the "drive the real producer" half, which is the whole point of this story.** What does not survive is the assertion-target half. Recorded rather than silently edited because an implementer reading the Technical Approach before the ACs would have followed the wrong one — and because a story contradicting itself about its assertion target is exactly the drift the epic's own delegation boundary exists to prevent.

One trap specific to this file, recorded in `.claude/rules/testing.md`: its `db` fixture is disk-backed, and calling `backup()` against a connection on that same path deadlocks SQLite. Fresh connections already see committed rows directly.

A second trap the file itself documents: the synthetic ids in this class keep an all-numeric final segment deliberately, because a ten-digit run bounded by non-digits trips the PII scanner and blocks the commit. Writing an offending id in a **comment** trips it too — describe the shape rather than quoting one.

Reference, read-only and in an ephemeral session scratchpad — reproduce what it demonstrates rather than depending on the path: `/tmp/claude-1000/-workspaces-baseball-crawl/2728098f-4677-4ff3-a474-cda6aed92b4c/scratchpad/divergence_plugin.py`, the probe that established the zero-divergence baseline quoted in Context.

## Dependencies
- **Blocked by**: E-276-01 (the player-line fix this test exercises)
- **Blocks**: None

## Files to Create or Modify
- `tests/test_report_generator.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for**: nothing — this story blocks no other, by design. It is the pipeline-level proof, not an input to anything downstream.
- **Consumes from E-276-01**: the player-line fix and the gate-outcome record (epic TN-11) — noting that on the player-line grain **that record is keyed by `(table, team_id)` rather than scalar**, because the gate is evaluated per block and table. Note this story's assertion steer INVERTS (TN-18): there is no structural retire record at `generate_report()` level, so the WARN or a spy is the only positive signal here — **do not expect to reach the record 01 produces**, keyed or otherwise.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The new churn-shaped scenario demonstrably FAILS against pre-fix code and PASSES after. **AC-3's existing subset-shaped scenario passes under both regimes and must** — it is the no-regression half, and requiring it to fail pre-fix would contradict deletion-neutrality.
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] `data/app.db` untouched; no network

## Notes

This story is separable and is the cleanest candidate to defer if the operator wants to shrink scope at dispatch. The grain-level tests in stories 01-03 already prove the fix; this one proves it at the surface where the defect actually reached live data, which is a different and weaker-to-lose kind of evidence.

Worth stating plainly, though: had this scenario existed before E-267 shipped, the defect would have been caught at the seam rather than three epics later by an independent audit.
