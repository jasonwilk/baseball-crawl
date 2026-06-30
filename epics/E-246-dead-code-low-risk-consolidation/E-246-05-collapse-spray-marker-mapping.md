# E-246-05: Collapse spray play_type→contact→marker mapping to one source

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the spray-chart vocabulary that maps play_type → contact type → marker/label — currently asserted in three parallel places — will derive from a single shared table, so markers drawn on the chart and the marker shown in the legend can never desync.

## Context
The sweep's M7 finding: in `src/charts/spray.py`, `_PLAY_TYPE_MARKERS` (`:88-98`) and `_CONTACT_TYPE_MAP` (`:162-172`) share an identical 9-key vocabulary, and `_draw_legend` (`:412-431`) re-asserts the same mapping a third time as hardcoded `Line2D` literals. A marker change made in one place but not the others silently desyncs the legend from the plotted points. This is a low-risk, self-contained chart-rendering consolidation.

## Acceptance Criteria
- [ ] **AC-1**: Given the vocabulary is asserted in three places, when the story completes, then there is one play_type→contact map and one contact→(marker, label) table, and both the plotting path and the legend derive from them by composition (no hardcoded marker/label literals remain in `_draw_legend`).
- [ ] **AC-2**: Given the consolidation, when the play_type→marker mapping and the contact→(marker, label) legend table are asserted at the **semantic level** — the same assertion surface as the existing `tests/test_charts/test_spray.py` unit tests (e.g. `_marker_for_play_type(...)` per-play_type assertions near `:132`, and a legend-entry list derived by iterating the shared table) — then the marker for each play_type, and the (marker, label, order) of each legend entry, are identical to the pre-story values. The proof target is these semantic assertions, **NOT raw PNG bytes** (matplotlib output bytes are version-fragile and out of scope).
- [ ] **AC-3**: Given the single source, when the marker or label for a contact type is changed in the shared table, then both the plotted points and the legend reflect it — demonstrated by the shared-table structure.
- [ ] **AC-4**: Given the consolidation, when `tests/test_charts/test_spray.py` runs, then it passes. (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/charts/spray.py:88-98`, `:162-172`, `:412-431`. The legend should be built by iterating the shared contact→(marker, label) table rather than restating literals. Confirm rendered output is unchanged — if an existing test covers spray rendering, rely on it; otherwise compare before/after marker and legend output for a representative input.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/charts/spray.py`
- `tests/test_charts/test_spray.py` (extend — add/adjust the marker+legend equivalence assertion per AC-2; file exists today)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Marker mapping and legend table verified identical at the semantic-assertion level (per AC-2; not PNG bytes)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
Self-contained to one file; no cross-module impact.
