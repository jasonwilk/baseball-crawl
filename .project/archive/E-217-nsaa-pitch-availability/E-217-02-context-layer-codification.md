# E-217-02: Context-Layer Pitch Rules Codification

## Epic
[E-217: NSAA Pitch Count Availability Rules](epic.md)

## Status
`DONE`

## Description
After this story is complete, pitching availability rules for all known leagues (NSAA, American Legion, USSSA, Perfect Game) will be codified in a dedicated context-layer rule file (`.claude/rules/pitch-rules.md`) that agents and the LLM can reference. The informal heuristics in `.claude/rules/key-metrics.md` will be updated to reference the authoritative rule file instead.

## Context
The platform serves teams across multiple leagues (NSAA HS, American Legion, USSSA travel ball, Perfect Game tournaments), each with different pitching rules. Currently the rules exist only as ad-hoc constants in `src/reports/starter_prediction.py` and informal text in `.claude/rules/key-metrics.md`. The user wants ALL known league rules codified as structured reference data so the LLM Tier 2 prompt can reference the correct rules for any team, and so agents working on pitching features have a single authoritative source. Only NSAA is implemented in the engine (E-217-01); this story provides the complete reference landscape.

## Acceptance Criteria
- [ ] **AC-1**: A new rule file `.claude/rules/pitch-rules.md` exists with the following exact `paths:` frontmatter:
  ```yaml
  paths:
    - "src/reports/starter_prediction.py"
    - "src/reports/llm_analysis.py"
    - "src/api/db.py"
    - "src/api/routes/dashboard.py"
    - "src/api/templates/dashboard/opponent_detail.html"
    - "src/api/templates/dashboard/opponent_print.html"
    - "src/api/templates/reports/**"
  ```
- [ ] **AC-2**: The rule file contains the complete NSAA section: rest requirement tables (pre-April 1 and post-April 1), the consecutive-days rule (counts individual appearances, not days), the doubleheader pitch aggregation rule (same-day pitches combined for rest-tier lookup), calendar-day counting convention, and applicability scope (Nebraska HS: freshman, reserve, jv, varsity).
- [ ] **AC-3**: The rule file contains reference sections for American Legion (pitch-count-based: max 105/day, rest tiers, same-day limit, 8am-8am day), USSSA (innings-based: max innings/day by age, mandatory rest thresholds), and Perfect Game (outs + pitches: daily max by age, tournament caps, mandatory rest). These are documented as reference data for the LLM and future engine implementation.
- [ ] **AC-4**: The rule file includes a "How the Engine Should Use These Rules" section describing how agents implementing pitching features should consume these rules: Tier 1 (deterministic lookup in Python code -- currently NSAA only), Tier 2 (agent injects the correct league's rest table into the LLM prompt based on team classification -- the rule file is agent reference data, not read at runtime), Display (show NSAA-required rest alongside actual rest). Includes a league-to-team-classification mapping table that bridges `programs.program_type` values (hs/usssa/legion) and `teams.classification` values to league rule sets. Perfect Game is noted as "not yet represented in schema" (no `program_type` value exists for PG tournaments).
- [ ] **AC-5**: The rule file includes a structural note: NSAA and Legion are pitch-count-based (same data model, different thresholds -- adding Legion is a data change). USSSA and Perfect Game use different units (innings, outs) requiring structural engine extension (a code change).
- [ ] **AC-6**: The "Predicted starter" bullet in `.claude/rules/key-metrics.md` (line 28) replaces both informal threshold references -- "pitched within 1 day" AND "75+ pitches with <4 days rest" -- with a reference to `.claude/rules/pitch-rules.md`. The 10+ day gap heuristic ("availability unknown") is preserved (it is a coaching heuristic, not a league rule). All other coaching heuristics (rotation patterns, deviation rate, confidence signals) are preserved.
- [ ] **AC-7**: The NSAA rest tier values in the rule file match the epic Technical Notes tables exactly (pre-April: 1-30/0d, 31-50/1d, 51-70/2d, 71-90/3d, max 90; post-April: 1-30/0d, 31-50/1d, 51-70/2d, 71-90/3d, 91-110/4d, max 110).

## Technical Approach
Create a new rule file at `.claude/rules/pitch-rules.md` covering all known league rule sets. Structure: overview with league-to-classification mapping table, then per-league sections (NSAA first and most detailed as the implemented rule set, then Legion, USSSA, Perfect Game as reference data). Each section includes: applicability, rule tables, additional constraints, and structural notes. Include engine usage guidance (Tier 1/Tier 2/Display). Update the predicted-starter bullet in key-metrics.md to replace ad-hoc threshold language with a reference to the new file.

The `paths:` frontmatter scopes to files where pitching rules are relevant: `src/reports/starter_prediction.py`, `src/reports/llm_analysis.py`, `src/api/db.py`, `src/api/routes/dashboard.py`, and report/dashboard templates.

The league rule values come from the epic Technical Notes (NSAA) and the multi-league landscape section. For Legion, USSSA, and Perfect Game rules, use the values provided in the epic Technical Notes. If any values are uncertain, note them with "[verify]" rather than omitting.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/pitch-rules.md` -- create new rule file (all leagues)
- `.claude/rules/key-metrics.md` -- update "Predicted starter" bullet to reference rule file

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- context-layer only)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The two stories in this epic are independent -- no shared files, no dependency ordering.
- The NSAA rest tier values must match the epic Technical Notes tables exactly. If the implementing agent discovers discrepancies, flag to PM before proceeding.
- Legion, USSSA, and Perfect Game rule values come from the multi-league landscape in epic Technical Notes. These are reference data (not implemented in code) so exact precision is less critical than for NSAA, but values should still be accurate. Mark uncertain values with "[verify]".
- The file is named `pitch-rules.md` (not `nsaa-pitch-rules.md`) because it covers all leagues.
