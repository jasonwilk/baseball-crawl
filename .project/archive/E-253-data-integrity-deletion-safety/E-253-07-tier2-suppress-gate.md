# E-253-07: Tier-2 Suppress Gate — Skip Enrichment + Template Honesty

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`DONE`

## Description
After this story is complete, when the deterministic "Most Likely Arms" engine returns a suppressed prediction (`confidence == 'suppress'`), the report will show only the honest softened copy — no LLM narrative, no named pitcher — and the LLM call will be skipped entirely (no cost spent). The non-suppress rendering path is unchanged.

## Context
See epic Technical Notes **TN-2** (baseball-coach advisory). Today `_run_tier2_enrichment()` (`generator.py:2214`) fires whenever `pitching_history_rows` is non-empty with no confidence gate, and `enrich_prediction()` (`llm_analysis.py:205`) has no gate either — so a suppressed prediction still calls the LLM. In the template (`src/api/templates/reports/scouting_report.html`), the Tier-2 narrative block (`:606-615`) sits AFTER the `{% endif %}` at `:578` — OUTSIDE the suppress/ranked branch — so a coach sees "Not enough games yet" immediately followed by an AI paragraph that structurally should not exist. `insufficient_data` suppress is the MOST COMMON early-season state, exactly when a coach leans hardest on the report; the narrative launders a low-confidence guess into confident prose (a trust violation).

## Acceptance Criteria
- [ ] **AC-1**: Given a `StarterPrediction` with `confidence == 'suppress'` (reason `insufficient_data` OR `unsupported_level`), when the report is generated, then NO LLM enrichment call is made — the gate is applied at the enrichment call site (`_run_tier2_enrichment` / `enrich_prediction`) so no cost is spent. Proven by a test asserting the LLM client is not invoked on suppress.
- [ ] **AC-2**: Given the same suppressed prediction, when the report renders, then the "Most Likely Arms" section shows ONLY the existing softened suppress copy — no Tier-2 narrative block, no named pitcher. The narrative block is moved inside the non-suppress branch so it cannot render on suppress.
- [ ] **AC-3**: The gate covers BOTH suppress reasons (`insufficient_data` and `unsupported_level`) — verified for each.
- [ ] **AC-4**: Given a non-suppress prediction (ranked candidates), when the report renders, then the ranked arms AND (when a key is configured) the optional Tier-2 narrative render exactly as before — the non-suppress path is unchanged. (baseball-coach offers to review the diff at dispatch to confirm the moved template block does not alter this path.)
- [ ] **AC-5**: Both halves of the fix are present — the skip gate at the call site AND the template block move — since either alone is incomplete (TN-2).

## Technical Approach
See epic Technical Notes **TN-2**. The gate belongs at both the enrichment call site (no LLM cost on suppress) and the template (block moved inside the non-suppress branch). The implementing agent owns the exact gating condition and the template restructuring. baseball-coach is available for an advisory diff review at dispatch.

## Dependencies
- **Blocked by**: E-253-01 (also modifies `src/reports/generator.py`; run E-253-01 first to isolate per-story diffs)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py` (`_run_tier2_enrichment` call-site gate, ~line 2214)
- `src/reports/llm_analysis.py` (`enrich_prediction` confidence gate, ~line 205)
- `src/api/templates/reports/scouting_report.html` (move the narrative block `:606-615` inside the non-suppress branch)
- `tests/` — suppress-skips-LLM test (both reasons) + suppress-renders-no-narrative test + non-suppress-unchanged test

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/display-philosophy.md` ("Discounted is not unavailable"; internal diagnostics stay internal), `.claude/rules/architecture-subsystems.md` (Two-Tier Enrichment Pattern).
