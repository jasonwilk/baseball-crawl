# E-229-09: Tier 2 LLM input contract — locked schema

## Epic
[E-229: Team-Aggregate Defensive Positioning](epic.md)

## Status
`DONE`

## Description
After this story is complete, `src/reports/positioning_llm.py` is updated to consume the E-229 engine output shape: per flagged batter, the input contract carries the batter's deviation values, the team-aggregate context, and the zone_id (instead of E-228's categorical `call_state`). **LLM rationale is render-time in-memory only — no DB persistence** (per Phase 3 iteration 1 CR B1 lock). The output contract (length, structural citation, decision discipline) and the non-fatal failure pattern (LLM unavailable → skip + INFO log; LLM fails mid-call → caught + WARNING log) are preserved from E-228 CX-4 / CX2-3.

## Context
DE round-1 recommended this be a dedicated story: the LLM input schema is a contract that gets harder to change once implementation lands. Locking it before the wiring story (E-229-10) ensures the bundle's rationale layer is well-defined from the start.

E-228's LLM received categorical inputs (`call_state`, `team_state_call`, `direction_shade`, `depth_shade`). E-229 retires those. The new input shape, per epic TN-2 single-source provenance: the LLM reads `batter_positioning` (per-batter row with `zone_id`, `direction_deviation`, `depth_deviation`, `bip_count`, `is_thin`) and `team_position_aggregate` (per-position row with `star_x`, `star_y`, `bip_count`, `is_low_confidence`). The LLM never recomputes the centroid.

E-228 CX2-3 locked the output contract as a three-part observable contract:
- (a) Length 10–50 words / 1–2 sentences with post-processing rules
- (b) Structural-citation requirement (must reference a zone keyword, contact-type keyword, or numeric figure from the Tier 1 input)
- (c) Decision-discipline requirement (must not contradict the row's spatial assignment)

The decision-discipline check changes shape for E-229: "must not contradict the row's spatial assignment" now means "must not suggest a direction that contradicts the batter's `zone_id` or `direction_deviation` sign." The LLM can't say "play him oppo" when the batter's deviation is pull.

## Acceptance Criteria
- [ ] **AC-1**: An input-assembly function in `src/reports/positioning_llm.py` constructs the LLM prompt for a single flagged batter from `(batter_positioning_row, team_position_aggregate_row, batter_metadata)`. The contract is documented in a docstring or module-level constant. The contract includes: jersey, name, position, `zone_id`, `direction_deviation`, `depth_deviation`, `bip_count`, `is_thin`, `team_star_x`, `team_star_y`, `team_bip_count`, `team_is_low_confidence`, plus opponent name and coverage cue.
- [ ] **AC-2**: Output contract preserved from E-228 CX2-3 with the decision-discipline check updated for E-229's spatial output: (a) length 10–50 words / 1–2 sentences; (b) structural citation (must reference a zone keyword like "Zone B" or "in-left", a contact-type keyword if relevant, or a numeric figure from the input); (c) decision discipline (must not contradict `zone_id` / sign of deviation values).
- [ ] **AC-3**: Non-fatal contract preserved from E-228 CX-4: LLM unavailable (`is_llm_available()` returns False) → Tier 2 skipped silently with INFO log; LLM fails mid-call → caught non-fatal with WARNING log; the bundle is still produced without the rationale line.
- [ ] **AC-4**: A validation gate function checks each LLM response against the three-part output contract. Responses that fail validation are logged at WARNING level and **the rationale is dropped for that batter** (returned as None from `generate_rationale()`; the bundle still renders the batter's row without a rationale line). **No DB persistence per CR B1 lock** — the rationale lives only in render-pass memory; the bundle assembler (E-229-08) iterates over flagged batters, calls `generate_rationale()` per batter, and threads the result directly into the template context. There is no `rationale` column on `batter_positioning`; there is no save-to-DB path.
- [ ] **AC-5**: Top-level entry signature: `generate_rationale(batter_row, aggregate_row, batter_metadata) -> Optional[str]`. Returns the validated rationale string on success, or `None` on any failure mode (LLM unavailable, exception, validation rejection). Callers (E-229-08 bundle assembler) use `Optional[str]` semantics: render the rationale line if not None; omit if None.
- [ ] **AC-6**: Tests cover: (a) input-assembly produces the expected contract from a sample batter row + team-aggregate row; (b) output validation accepts a well-formed response and rejects responses that fail length / citation / decision-discipline; (c) `is_llm_available()` False path produces INFO log and returns None; (d) LLM raises exception → caught, WARNING log, returns None; (e) **no DB writes**: a test verifies no INSERT/UPDATE statements are issued by this module against `batter_positioning` or `team_position_aggregate` (grep AC or runtime trace).

## Technical Approach

**Module surface**: modify `src/reports/positioning_llm.py`. The function structure follows E-228's pattern:
- `is_llm_available() -> bool` — unchanged from `src/reports/generator.py` precedent
- `_assemble_llm_input(batter_row, aggregate_row, batter_metadata) -> dict` — new shape per AC-1
- `generate_rationale(batter_row, aggregate_row, batter_metadata) -> Optional[str]` — top-level entry; returns None on validation failure or LLM error
- `_validate_response(response_text, batter_row) -> bool` — three-part check per AC-2; the decision-discipline branch reads `zone_id` and deviation signs and checks the response doesn't contradict

**Decision-discipline check specifics**: parse the response for any of a small set of direction keywords (`left`, `right`, `in`, `deep`, `pull`, `oppo`, `straight`). If the response says "shade right" but the batter's `zone_id` is in the left half (A/B/C), the response fails the gate. The keyword list and the contradiction matrix are documented in a module-level constant.

**Validation logging**: validation failures should log at WARNING with the batter ID and the failure mode (length / no citation / decision contradiction). Operator can audit failures during the calibration pass.

**Prompt shape**: the actual prompt to the LLM should be terse (this is a rationale-narration task, not a reasoning task). Suggested shape: a JSON-like description of the batter and team context, plus a one-paragraph instruction. Lock the prompt template in this story so downstream changes are deliberate.

## Dependencies
- **Blocked by**: E-229-02 (engine output shape is the input contract)
- **Blocks**: E-229-10 (pipeline wiring integrates the LLM step into the bundle generation flow)

## Files to Create or Modify
- `src/reports/positioning_llm.py` — modify (replace E-228's categorical-shape contract with E-229's deviation+aggregate-shape contract)
- `tests/test_positioning_llm.py` — modify (full new coverage for input-assembly, validation, non-fatal paths)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-229-08**: a stable `generate_rationale(batter_row, aggregate_row, batter_metadata) -> Optional[str]` entry point that the bundle assembler calls per flagged batter at render time. Return value threads directly into the template context — no DB roundtrip, no schema column.
- **Produces for E-229-10**: the same entry point integrated into the broader pipeline flow (standalone path + scouting path both run bundle generation, which calls `generate_rationale()` per flagged batter).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The decision-discipline keyword list is a render-layer constant, not engine output. It can be refined during the first-real-opponent calibration pass without breaking the engine.
