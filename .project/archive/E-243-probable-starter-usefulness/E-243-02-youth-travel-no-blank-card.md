# E-243-02: Stop blank cards for youth/travel opponents

## Epic
[E-243: Make the Probable-Starter Analysis Useful on Game Morning](epic.md)

## Status
`DONE`

## Description
After this story, an opponent whose team name resolves to youth/travel (e.g., "GI Home Federal 18U") renders a probable-starter prediction labeled as an estimate, instead of a suppressed/blank card. The engine applies a pitch-count rule set (the USA Baseball Pitch Smart 15-18 soft prior) for youth/travel competition levels rather than returning the `suppress` no-rules path, and tags the result so downstream presentation can mark it as an estimate.

## Context
The backtest found 7 of 17 real opponents got no prediction at all: their team name resolved to `youth_travel` (the `\d+U` keyword), and `get_rules_for_league()` returns `None` for that level, which forces `confidence="suppress"` and a blank card. `league-pitch-rules.md` and `.claude/rules/pitch-rules.md` both designate the Pitch Smart 15-18 curve as the soft prior for unknown leagues — the same curve already encoded as `LEGION` in the engine. Applying it as a *labeled estimate* stops the blank cards without building a true innings-based USSSA rules engine (out of scope, epic Non-Goals). This story modifies `starter_prediction.py` after E-243-01 (shared file, epic TN-7).

## Acceptance Criteria
- [ ] **AC-1**: Given an opponent whose detected league/level is `youth_travel` and which has ≥4 games of pitching data, when the prediction is computed, then the engine produces a ranked prediction (not `confidence="suppress"` with the no-rules warning), using the Pitch Smart 15-18 pitch-count curve for the rest/eligibility gate (per Technical Notes TN-4).
- [ ] **AC-2**: The prediction output carries an additive `is_estimate: bool` field (default `False`) on `StarterPrediction`, set `True` for the youth/travel fallback, so the card (E-243-03) and LLM (E-243-04) can label it as not a binding league rule.
- [ ] **AC-3**: Given an opponent whose detected league/level is `nsaa_varsity`, `nsaa_subvarsity`, or `legion`, when the prediction is computed, then behavior is unchanged from before this story and `is_estimate` is `False`.
- [ ] **AC-4**: Given an opponent whose detected league/level is `unknown` (no level signal at all), when the prediction is computed, then it remains suppressed (coach + DE ratified scoping the fallback to `youth_travel` only — epic Open Question now closed).
- [ ] **AC-5**: A unit test asserts a `youth_travel` team with sufficient data yields a non-suppressed ranked prediction with `is_estimate == True`, and an `nsaa_varsity` team is unaffected (`is_estimate == False`).
- [ ] **AC-6**: No regression in existing suppress-path tests. The current youth_travel/unsupported-league suppress assertions live in `tests/test_league_detection.py` (NOT `tests/test_starter_prediction.py`) — that file is the one whose existing assertions must be updated for the youth_travel-now-falls-back behavior; the genuinely-unsupported-league (`usssa`/`perfect_game`/`unknown`) suppress assertions there must still pass.
- [ ] **AC-7**: A unit test (in `tests/test_league_detection.py`, alongside the related suppress assertions) asserts a `youth_travel` team with **fewer than 4 games** STILL suppresses — the min-games gate must keep firing after the league gate is lifted for `youth_travel` (the two gates are independent).

## Technical Approach
Route `youth_travel` to a pitch-count rule set instead of the `None`/suppress path in `get_rules_for_league()`, and set `is_estimate=True` on the prediction output. Define a **distinct named constant** (e.g. `PITCH_SMART_15_18`) holding the same tiers as the engine's existing `LEGION` rules — do NOT have `youth_travel` reference the `LEGION` constant literally, so a future Legion-only change cannot silently move the youth/travel estimate. The rest thresholds must match the Pitch Smart 15-18 curve in `.claude/rules/pitch-rules.md` (`league-pitch-rules.md` L73 confirms the Legion Senior/Junior curve IS this curve). Do NOT add USSSA/Perfect Game innings-based or outs-based rule units (epic Non-Goals). The team-name → level detection (`detect_league_level`) already classifies these teams as `youth_travel`; this story changes only what happens for that level.

**Domain caveat (record as rationale, do not over-state in code comments):** the Pitch Smart curve we apply is the 17-18 sub-bracket; the 15-16 bracket differs at the top tier, and youth/travel teams skew younger, so this curve tends to *under-rest* them — e.g. 70 pitches → 3 days rest under the 15-18 curve vs. 4 days under 13-14. baseball-coach confirmed (M1 cycle) this directional bias makes the estimate label (E-243-03/04) **load-bearing** — it carries real decision weight and MUST NOT be softened to a boilerplate disclaimer; the coach must read it as a directional estimate, not a hard rule.

## Dependencies
- **Blocked by**: E-243-01
- **Blocks**: E-243-03

## Files to Create or Modify
- `src/reports/starter_prediction.py`
- `tests/test_starter_prediction.py`
- `tests/test_league_detection.py` (existing youth_travel/unsupported-league suppress assertions live here — update for the fallback behavior; add the AC-7 <4-games-suppress test here)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-243-03 and E-243-04**: the estimate marker on the prediction output, which the card and LLM narration use to label youth/travel predictions as estimates.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The reflection of this fallback into the context-layer rule docs (`.claude/rules/pitch-rules.md` noting youth/travel now uses the Pitch Smart soft prior in the engine) is handled at epic closure via the context-layer assessment (claude-architect), not in this code story. baseball-coach and data-engineer **ratified** the Pitch Smart fallback choice in the Phase 3 review cycle (`youth_travel` falls back; `unknown` stays suppressed; the directional under-rest caveat above is recorded).
