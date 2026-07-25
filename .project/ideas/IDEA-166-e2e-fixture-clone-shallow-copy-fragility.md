# IDEA-166: The E2E fixture clone is a shallow copy — safe today, by unwritten conditions

## Status
`CANDIDATE`

## Summary
`TestGenerateReportDestructiveReconcile._schedule` (`tests/test_report_generator.py`) builds two extra completed games by `dict(clone_src)` — a SHALLOW copy of a committed fixture game. The clones therefore share nested objects with their source by reference; the `score` dict is the notable one. This is correct today for two reasons that are nowhere written down: nothing in the pipeline or the test MUTATES a nested payload object, and `_load` re-reads the fixture from disk on every call so the sharing never spans runs. A plausible future edit — giving each cloned game its own score to assert per-game records, or any in-place payload tweak — turns the sharing into silent cross-contamination between games that are supposed to be independent.

## Why It Matters
The test is E-270's proof that report generation's destructive path actually fires end-to-end, and its whole design principle is that a fixture must not let an assertion pass for the wrong reason. Cross-contaminated game payloads are exactly that failure: two games would move together, and a per-game assertion would be measuring one object twice. The fix is trivial (`copy.deepcopy`, or building the nested dicts explicitly); the cost of NOT capturing it is that the next person to touch the fixture has no way to know the constraint exists.

## Rough Timing
No urgency — reviewed and ruled no-action for E-270-03 by code-reviewer, and PM did not reopen it. Natural trigger: the first edit to `_schedule` or its clones, particularly one that varies scores, records, or any nested field per game. Cheapest moment to act is whenever someone is already in that fixture.

## Dependencies & Blockers
- [ ] None. A self-contained test-fixture change.

## Open Questions
- Is a `deepcopy` in the clone loop enough, or should the fixture builder be explicit about which fields are per-game so the independence is visible rather than implied?
- Does the same shallow-copy pattern appear in the other fixture-driven E2E tests (`tests/test_report_e2e.py`, `tests/test_report_e2e_degraded.py`), which draw on the same `tests/fixtures/e2e/` payloads?

## Notes
Raised by `se` during E-270-03 review (2026-07-24) and marked no-action for that story by `cr`; captured at team-lead's request so the REASONING survives the review thread rather than the conclusion alone. The safety conditions (nothing mutates nested payload objects; `_load` re-reads per call) are the part worth keeping — they are what a future editor would violate without noticing. Related: E-270 (E-270-03, epic TN-6), [[IDEA-165]].

---
Created: 2026-07-24
Last reviewed: 2026-07-24
Review by: 2026-10-22 (90 days)
