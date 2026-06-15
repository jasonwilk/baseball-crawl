# E-236-06: Coach footer Option A — drop season_fallback from degraded line (#4)

## Epic
[E-236: Report Self-Reporting Integrity Hardening](epic.md)

## Status
`DONE`

## Description
After this story is complete, the coach-visible "Data accuracy may be limited" line will fire ONLY on name-only identity matches, not on `season_fallback`. A clean modal team (program_type NULL + good season_year, which triggers `season_fallback`) will no longer show a false degraded-confidence warning. `report_generation_runs.season_fallback` remains as operator-only telemetry. This closes finding #4.

## Context
`degraded_confidence = bool(self.season_fallback or self.identity_match_method == "name_only")` (`generator.py:1930-1933`) → renderer `_build_trust_block` (`renderer.py:551,591-602`) → template `:883-884`. `season_fallback` is a remnant of the abandoned multi-season bridging vision and fires on clean modal data, producing a false coach-facing warning. The fix (Option A) was decided 2026-06-14 (IDEA-077, baseball-coach C2, ROADMAP §4/§6). See epic Technical Notes TN-4. The deeper season_fallback machinery removal is explicitly OUT of scope (epic Non-Goals; Epic D2 / IDEA-077).

## Acceptance Criteria
- [ ] **AC-1**: The coach-visible degraded-line computation (`generator.py:1930-1933`) drops the `season_fallback` term, leaving `degraded_confidence = bool(self.identity_match_method == "name_only")`, per Technical Notes TN-4.
- [ ] **AC-2**: Given clean modal data that sets `season_fallback=True` but a non-name-only identity match, when the report generates, then `degraded_confidence` is `False` and the coach footer shows NO degraded-confidence line.
- [ ] **AC-3**: Given a name-only identity match, when the report generates, then `degraded_confidence` is `True` and the coach footer shows the degraded-confidence line (behavior preserved).
- [ ] **AC-4**: `report_generation_runs.season_fallback` is still written exactly as before (operator-only telemetry, surfaced on `/admin/reports`) — no change to the column or its write.
- [ ] **AC-5**: No renderer/template change is required beyond what the boolean drives (the renderer derives `degraded_line` from the boolean it receives); no new coach-facing content (epic Non-Goals).

## Technical Approach
Single-term change at `generator.py:1930-1933`. Update the tests that assert the season_fallback→degraded_confidence coupling (these are stale-contract tests per testing.md inverse direction — bringing them to the new contract is a MUST-FIX part of this change). Grep `tests/` for assertions encoding the old `season_fallback`-drives-degraded behavior.

## Dependencies
- **Blocked by**: E-236-05
- **Blocks**: E-236-08, E-236-09

## Files to Create or Modify
- `src/reports/generator.py` (modify — degraded_confidence computation at ~1930-1933)
- Footer/trust-block tests (modify — locate via `grep -rl` per testing.md; e.g. `test_report_renderer` / `test_report_generator` asserting degraded_confidence)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Coach C2 / IDEA-077. Small but has a coaching-decision pedigree; kept as its own slice for review clarity.
