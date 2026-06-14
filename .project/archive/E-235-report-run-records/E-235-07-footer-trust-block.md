# E-235-07: Report footer trust block (three severity states)

## Epic
[E-235: Report Run Records, Trust Signals & Quality Gates](../E-235-report-run-records/epic.md)

## Status
`DONE`

## Description
After this story is complete, every generated scouting report carries a footer trust block telling the coach how complete the data is — game coverage (N of M games played), pitch-detail and spray availability, and the generation date — rendered in one of three severity states (quiet / flagged / loud) with a generic degraded-confidence line when an operator data-integrity flag is set.

## Context
Coaches today cannot see how complete a report is (ROADMAP §2). The footer extends the existing game-coverage freshness philosophy (`.claude/rules/display-philosophy.md`: never suppress, always contextualize) into a trust signal. The signal set, the M=games-played-to-date semantic, the three severity tiers, the generic degraded-confidence line, and the operator/coach split are baseball-coach-authoritative and specified in **epic Technical Notes §TN-7**. This story consumes the render `data` dict produced by story 03 (§TN-6) and touches renderer + template only — no `generator.py` code.

## Acceptance Criteria
- [ ] **AC-1**: The report footer renders the signal set from §TN-7: `Through {date} (N of M games) · Pitch detail for {K} games · spray {available/unavailable} · Generated: {date}`, with "Generated" separate from "Through", "Pitch detail" (not "plays data"), M = games played to date, and no "loaded" jargon. When K=0, render `No pitch-detail data` (or `Pitch detail: unavailable`) rather than "Pitch detail for 0 games" (COACH-2, §TN-7).
- [ ] **AC-2**: Coverage severity is keyed off coverage % (N/M) ALONE — quiet (≥80%), flagged (50–79%), loud (<50%) — per §TN-7. (Coverage severity and the degraded-confidence line are independent signals; this AC covers coverage only.)
- [ ] **AC-3**: The degraded-confidence line `⚠️ Data accuracy may be limited. Contact your operator to verify before the game.` is shown whenever `degraded_confidence` is true, in ALL THREE coverage states (including quiet and loud) — NOT gated on the coverage state (COACH-1, §TN-7). It does NOT expose the specific operator flags (season fallback / name-only match); only the fact of degraded confidence surfaces.
- [ ] **AC-4**: The footer consumes the render `data` inputs threaded by story 03 (M, N, K, spray availability, generated date, `degraded_confidence`); this story makes NO `generator.py` change. If M is NULL (unavailable per Open Questions), the footer degrades gracefully to N + the freshness date without a broken ratio.
- [ ] **AC-5**: Tests assert each of the three severity states renders for representative coverage values and that the degraded-confidence line appears when and only when `degraded_confidence` is true, without leaking the specific flags.

## Technical Approach
Add the trust-block section to `src/api/templates/reports/scouting_report.html` and any supporting logic in `src/reports/renderer.py`, driven by the `data` keys from story 03. Choose the visual treatment for quiet/flagged/loud (the ACs fix the content and the state thresholds, not the markup). Follow the standalone-report JS conventions if any client-side enhancement is used (`var`, class targeting, graceful degradation — `.claude/rules/architecture-subsystems.md`). Reports are frozen self-contained HTML, so the trust block is baked at generation time. Use existing renderer tests (`test_report_renderer.py` / `test_report_rendering.py`) as the pattern.

## Dependencies
- **Blocked by**: E-235-03
- **Blocks**: None

## Files to Create or Modify
- `src/reports/renderer.py` (trust-block render logic / data shaping)
- `src/api/templates/reports/scouting_report.html` (footer trust block markup)
- `tests/` (renderer tests for the three states + the degraded-confidence line)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Content and severity thresholds are coach-authoritative (§TN-7) — do not editorialize the wording. The no-completed-games message (a separate terminal outcome) is rendered by story 03's gate, not this footer; this footer applies to reports that have games.
