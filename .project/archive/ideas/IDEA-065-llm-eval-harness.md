# IDEA-065: LLM Starter Prediction Evaluation Harness

## Status
`CANDIDATE`

## Summary
A developer evaluation harness (`scripts/eval_llm_starter.py`) that tests the LLM starter prediction (E-212 Tier 2) against known game outcomes. Calls real production code (`enrich_prediction()` from `src/reports/llm_analysis.py`) with fixture data representing teams with known rotation patterns. Supports model comparison (run the same fixtures against different `OPENROUTER_MODEL` values and compare output quality). A dev tool for prompt tuning, not a CI test.

## Why It Matters
The LLM tier produces narrative analysis that cannot be unit-tested for quality -- only for structural correctness (valid JSON, required fields present). The evaluation harness lets the operator assess whether the LLM's narrative is actually useful for coaching decisions: Does it identify the right matchup factors? Does it calibrate tone to confidence tier (per coach: narrative most valuable at moderate confidence)? Does it avoid manufacturing predictions at low confidence? Model comparison support enables cost/quality tradeoff analysis (e.g., Haiku vs. Sonnet for this use case).

## Rough Timing
After E-212 ships -- specifically after E-212-03 (LLM client + analysis module) is complete. The harness consumes E-212-03's `enrich_prediction()` function and E-212-02's `StarterPrediction` dataclass. E-212-02 should create reusable test fixtures (parametrized rotation patterns, edge cases) that this harness can consume directly rather than duplicating fixture data.

## Dependencies & Blockers
- [x] E-212-02 complete (provides `StarterPrediction` dataclass + test fixtures)
- [ ] E-212-03 complete (provides `enrich_prediction()` function)
- [ ] `OPENROUTER_API_KEY` configured in dev `.env`

## Open Questions
- Should the harness output a structured comparison report (e.g., markdown table of model vs. fixture vs. output quality scores)? Or just print narrative output for manual review?
- Should fixture data include the actual game outcome (who actually started) for accuracy measurement? This would enable a "prediction accuracy" metric but requires curated ground-truth data.
- How many fixtures are needed for meaningful evaluation? Minimum viable: 5 rotation patterns (ace-dominant, 2-man, 3-man, committee, suppress). Ideal: 10+ with real team data from the database.

## Notes
- This is a dev/operator tool, NOT a CI test. It makes real API calls to OpenRouter (costs money, requires credentials, non-deterministic output).
- Per SE consultation: the harness should call real production code, not a mock. The point is evaluating the actual prompt + model combination, not testing the HTTP client.
- The `scripts/` location follows the project convention for operator tools (not `src/` -- per import boundary rule).
- Related: E-212-02's test fixtures (parametrized rotation patterns in `tests/test_starter_prediction.py`) should be structured so this harness can import and reuse them. The fixture data format (pitcher profiles + pitching history dicts) is the same input shape for both the deterministic engine tests and the LLM evaluation.

---
Created: 2026-04-04
Last reviewed: 2026-04-04
Review by: 2026-07-03
