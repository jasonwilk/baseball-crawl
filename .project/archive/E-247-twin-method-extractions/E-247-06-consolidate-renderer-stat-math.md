# E-247-06: Consolidate reports renderer/prediction stat math & dates

## Epic
[E-247: Twin-Method & Duplicated-Block Extractions](epic.md)

## Status
`DONE`

## Description
After this story is complete, the duplicated stat math and date formatting in the reports renderer and starter-prediction modules — inline total-bases computed three ways, a copy-pasted K/9-alternative search loop, and a re-implemented short-date formatter — will each be expressed once.

## Context
The sweep's M6 finding:
- Total bases is computed inline 3× with two algebraically-equal formulas (`src/reports/renderer.py:195-203`, `:358-366`, `:426-428`, `:489-497`, `:692-699`).
- A K/9-alternative search loop is copy-pasted across the high-confidence and moderate-confidence branches (`src/reports/starter_prediction.py:1201-1237`, `:656-698`).
- `_format_short_date` re-implements the imported `api.helpers.format_date` (`renderer.py`).
- Minor re-parses/recomputes (last-appearance locals computed repeatedly; `_pa` recomputed instead of reusing the cached value).

These are reuse consolidations with no behavior change — the two total-bases formulas are algebraically equal, and the short-date formatter already has a canonical equivalent.

## Acceptance Criteria
- [ ] **AC-1**: Given total bases is computed inline with two allegedly algebraically-equal formulas across ~5 sites (HARD GATE — stats integrity, per epic Technical Notes), when the story completes, then a single total-bases helper is the source and all sites use it. The two formulas MUST be **proven equal across all inputs/call sites — not assumed** — by a golden-fixture/characterization `pytest` test asserting identical values at every former site (including any edge inputs where the two formulas could diverge). If they are not provably equal everywhere, surface the discrepancy as a finding rather than collapsing them.
- [ ] **AC-2**: Given the K/9-alternative search loop is copy-pasted across two confidence branches, when the story completes, then it is one shared helper called by both branches, producing identical results.
- [ ] **AC-3**: Given `_format_short_date` re-implements `api.helpers.format_date`, when the story completes, then `_format_short_date` is removed and the imported `format_date` is used, producing identical formatted dates.
- [ ] **AC-4**: Given the rendered report, when it is generated for representative data via a golden-fixture/characterization `pytest` test before and after the story, then the report output (stat values and formatted dates) is byte-identical. Proven by test, not inspection.
- [ ] **AC-5**: Given the consolidations, when the renderer/prediction test modules (`tests/test_report_rendering.py`, `tests/test_starter_prediction.py`), including the AC-4 golden-fixture render test, run, then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate — Technical Notes "Closure Gate (blocking)" — not a per-story AC, because the whole-suite run is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/reports/renderer.py:195-203`, `:358-366`, `:426-428`, `:489-497`, `:692-699`; `src/reports/starter_prediction.py:1201-1237`, `:656-698`. The sweep suggests `_total_bases(player)`, `_find_k9_alternative(...)`, using imported `format_date` and deleting `_format_short_date`, computing last-appearance locals once, and reusing cached `_pa` (illustrative). Because the two total-bases formulas are algebraically equal, confirm the chosen single formula produces the same value at every site. Rendered output must be byte-identical.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/reports/renderer.py`
- `src/reports/starter_prediction.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rendered report verified byte-identical (stats + dates)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
File-disjoint from the other E-247 stories. If the two total-bases formulas ever produced different values on edge inputs, that would be a latent bug — confirm they are truly equal at every call site before collapsing.
