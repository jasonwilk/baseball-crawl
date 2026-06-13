# IDEA-076: Spray-Value Regression Guard

## Status
`CANDIDATE`

## Summary
Epic A's regression guards value-cover stat outputs for batting, pitching, and plays (the E-234-05 E2E hand-tallies an FPS% oracle), but **spray-chart values are not regression-guarded anywhere** — they get only a shape/no-crash check. Add a spray-value oracle (e.g. hand-tallied spray-zone hit counts from a recorded game) to the E2E or as a dedicated guard, so a future refactor that breaks spray-zone computation fails a test.

## Why It Matters
The reports-first reframe (ROADMAP Epic A) makes "we did not regress reports" a green/red test result before Epics B–E touch the protected core. Spray charts are part of the report surface, yet no guard pins their computed values:
- Story E-234-01's golden test captures EMPTY spray results (seed.sql has no spray rows) — explicitly a shape/no-crash guard, deferring spray value coverage to E-234-05.
- Story E-234-05's E2E was expected (TN-1 prose) to be "the value guard for spray/plays," but its actual AC-1 named-stat set is W-L + batting + pitching + a plays-derived stat. The delivered test value-guards plays (FPS%) and treats spray as shape/no-crash only (the spray fixtures were trimmed 184KB→11.6KB / 252KB→13.4KB; the test asserts `spray_rows > 0` and notes "Spray values are NOT oracle-guarded").
- Net: a refactor in Epics B–E that silently broke spray-zone aggregation would NOT be caught by any Epic A guard. This is the one gap in the otherwise-complete reports value-regression net.

## Rough Timing
Before any epic that refactors the spray subsystem (`src/charts/spray.py`, the spray loader, or spray query path). No urgency if those subsystems are not on the near-term refactor path; promote when a protected-core epic is about to touch spray.

## Dependencies & Blockers
- [ ] E-234 (Report Regression Guards) complete — provides the E2E harness (`tests/test_report_e2e.py`) and the `tests/fixtures/e2e/` bundle this would extend.
- [ ] A recorded game-set with non-trivial spray data (the E-234-05 spray fixtures were trimmed; a value oracle may need richer/curated spray payloads).

## Open Questions
- What is the right spray-value oracle? Candidates: per-zone hit counts, pull/center/oppo distribution, or hot/cold zone classifications — pick the lowest-maintenance stable value.
- Extend the existing E-234-05 E2E (add spray assertions + a spray oracle to the README), or build a dedicated golden-style spray guard against a seeded fixture?
- Do the trimmed E-234-05 spray fixtures retain enough rows to compute a meaningful oracle, or is a fresh curated spray payload needed?

## Notes
- Source observation: E-234-05 AC verification (PM), 2026-06-13. ACs passed as written; this captures the consciously-accepted scope gap (team-lead decision: accept story 05 as-is + capture this idea).
- Reference: E-234 (ROADMAP Epic A — regression guards for the reports flow); story E-234-05 (E2E), story E-234-01 (golden, TN-1 spray deferral).
- Related spray ideas: IDEA-048 (fielder zones), IDEA-049 (pull/center/oppo), IDEA-050 (hot/cold zones), IDEA-051 (title stats) — those are spray *features*; this is a spray *regression guard*.

---
Created: 2026-06-13
Last reviewed: 2026-06-13
Review by: 2026-09-11 (90 days from created)
