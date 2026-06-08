# E-233-04: Operator-detectable Tier-2 generation status (Medium observability)

## Epic
[E-233: LLM JSON Hardening (Reports Tier-2 Enrichment)](../E-233-llm-json-hardening/epic.md)

## Status
`DONE`

## Description
After this story is complete, report generation will emit a structured status distinguishing the three Tier-2 outcomes — `success`, `unavailable-no-key`, and `failed` — so an operator can detect when AI analysis was dropped rather than it vanishing silently. This addresses the "worse half" of the bug: today, silent Tier-2 loss is invisible.

## Context
The Tier-2 enrichment site is `src/reports/generator.py:~1183-1209`: an `if is_llm_available():` branch wrapping `enrich_prediction` in a broad `try/except` that logs a WARNING and continues with Tier-1. The three outcomes are all observable here — key-absent (branch skipped), success (returned), and failure (except). This story makes those outcomes a structured, distinguishable signal at log/operator level. Per the user's decision, observability is **Medium**: log/operator-detectable only — NO coach-visible report label and NO `renderer.py`/template changes.

## Acceptance Criteria
- [ ] **AC-1**: Report generation emits a structured status distinguishing the three outcomes in Technical Notes TN-4 — `success`, `unavailable-no-key`, `failed` — at the Tier-2 enrichment site in `src/reports/generator.py`. The `failed` status is cause-agnostic (read from the `except` branch, not the exception type) per TN-4.
- [ ] **AC-2**: The `failed` status preserves the existing WARNING (per TN-2) with `exc_info` carrying the specific cause (parse failure after retry, transport error, or — once E-233-03 lands — a `response_format`-400); the status itself does not encode the cause, per TN-4.
- [ ] **AC-3**: The observability is log/operator-level only — no coach-visible report label is added, and `renderer.py` and report templates are NOT modified. Per epic Non-Goals.
- [ ] **AC-4**: Each of the three outcomes is asserted in a test (e.g., success path, no-API-key path, and parse-failure-after-retry path) per TN-6.
- [ ] **AC-5**: The non-fatal contract (TN-2) is unchanged — on failure the report still renders with the Tier-1 prediction.

## Technical Approach
At the Tier-2 enrichment block in `src/reports/generator.py`, emit a distinguishable structured status for each of the three branches: the `else`/skipped branch (`unavailable-no-key`), the successful return (`success`), and the `except` (`failed`). The mechanism (structured logger fields, a small status value/enum, or equivalent) is the implementer's call so long as the three outcomes are distinguishable and testable. To make AC-4's three-outcome assertions testable without heavy whole-pipeline mocking, the implementer is encouraged to extract the enrichment decision into a small helper in `generator.py` (e.g. `_run_tier2_enrichment(...) -> tuple[EnrichedPrediction | None, status]`) that AC-4's tests can target directly (F-E) — generator.py only, still no `renderer.py`/template change. Preserve and clarify the existing WARNING on failure. See epic Technical Notes TN-2, TN-4, TN-6.

## Dependencies
- **Blocked by**: E-233-02 only (the enrichment/`failed`-status branch is finalized in E-233-02; the cause-agnostic `failed` status means NO dependency on E-233-03 — the response_format-400 case lands in the same branch automatically, per TN-8; no file conflict with 02/03)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/generator.py`
- `tests/test_report_generator.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Scope deliberately excludes coach-visible labeling (the "Full" observability option) per the user's Medium decision. The report continues to show the unlabeled Tier-1 fallback exactly as today; only the operator-facing signal is added.
