# E-233-02: Harden `enrich_prediction` — defensive parse + one retry + dedup default model

## Epic
[E-233: LLM JSON Hardening (Reports Tier-2 Enrichment)](../E-233-llm-json-hardening/epic.md)

## Status
`TODO`

## Description
After this story is complete, `enrich_prediction` will parse the LLM response through the E-233-01 defensive helper instead of a bare `json.loads`, retry exactly once on a parse failure, and stop re-defaulting the model. The result: fenced/prose-wrapped responses that previously dropped Tier-2 now succeed, genuinely-bad responses still degrade cleanly to Tier-1, and the default-model literal lives in exactly one place.

## Context
This is the core remediation. `src/reports/llm_analysis.py:259` currently does `parsed = json.loads(content)` directly — the exact line that raised the production `LLMError`. This story replaces that with the E-233-01 helper, adds the single retry (epic TN-3), and folds in the latent duplicate-default-model fix the software-engineer flagged (the default literal is duplicated at `openrouter.py:26` and `llm_analysis.py:230` and can drift). The existing non-fatal contract (TN-2) must be preserved exactly — `enrich_prediction` still raises `LLMError` on unrecoverable input so the generator's fallback fires.

## Acceptance Criteria
- [ ] **AC-1**: `enrich_prediction` extracts the response JSON via the E-233-01 helper `extract_json_object` (no bare `json.loads` of LLM content remains in `llm_analysis.py`). Domain validation is retained after extraction: `narrative` must be a **non-empty** str (a deliberate tightening per F-G — see Notes), `bullpen_sequence` optional.
- [ ] **AC-2**: On a parse failure from the helper, `enrich_prediction` retries the LLM call exactly once with `temperature=0`, then re-extracts, per Technical Notes TN-3. No retry occurs on HTTP/transport errors (those already raise `LLMError`).
- [ ] **AC-3**: If extraction still fails after the single retry, `enrich_prediction` raises `LLMError`, preserving the non-fatal contract per TN-2 (caught by the generator, WARNING logged, report renders Tier-1).
- [ ] **AC-4**: A fenced or prose-wrapped response that previously failed now produces a correct `EnrichedPrediction` (verified via a test that patches `query_openrouter` to return fenced content — the enrich_prediction-path seam per TN-6, NOT httpx).
- [ ] **AC-5**: The default model literal no longer appears in `llm_analysis.py`; `query_openrouter` owns the default per TN-5. `EnrichedPrediction.model_used` is read from the OpenRouter response body (`response["model"]`, with a safe fallback if absent) — NOT imported from the shared constant (per TN-5 F-A, importing the constant is wrong when `OPENROUTER_MODEL` is set). A test asserts `model_used` derives from the mocked response, not from env or the constant.
- [ ] **AC-6**: The explicit `max_tokens=512` override at the enrichment call site is removed so the call uses `query_openrouter`'s default (already 1024 — per F-H this is the accurate framing of the intended bump). No truncation-repair logic is added.
- [ ] **AC-7**: Tests cover the retry path (first response unparseable → second parseable → success), retry-exhaustion (→ `LLMError`), and the single-source default (model resolution comes from one place), by patching `query_openrouter` per TN-6 (the enrich_prediction-path seam — `src.reports.llm_analysis.query_openrouter`, NOT httpx).
- [ ] **AC-8**: All `query_openrouter` invocations within `enrich_prediction` (the initial call and the TN-3 retry) go through a single local invocation point that shares identical kwargs and varies only `temperature`, so a future `response_format` (E-233-03) rides every call including the retry. Per Technical Notes TN-3 (F-C).

## Technical Approach
Replace the bare `json.loads(content)` at `src/reports/llm_analysis.py:259` with a call to `extract_json_object` (E-233-01), which already raises `LLMError` on failure. Factor the `query_openrouter` invocation into a single local helper/closure and wrap it in a one-retry loop per TN-3 (retry with `temperature=0`) so the initial and retry calls share identical kwargs (F-C) — this is the seam E-233-03 hooks `response_format` into. For the dedup (TN-5), stop passing a hardcoded default at `llm_analysis.py:230` — let `query_openrouter` resolve the default and read the model actually used for `model_used` from the response body (`response["model"]`, safe fallback if absent); do NOT import the shared constant (F-A). Remove the `max_tokens=512` override at the call site (default is already 1024 — F-H). After relocating the parse and removing the env-default line, remove the now-unused `import os` and `import json` from `llm_analysis.py` (F-D). Keep all domain validation intact. See epic Technical Notes TN-2, TN-3, TN-5, TN-6.

## Dependencies
- **Blocked by**: E-233-01
- **Blocks**: E-233-03, E-233-04

## Files to Create or Modify
- `src/reports/llm_analysis.py`
- `tests/test_llm_analysis.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-233-03**: the retry-aware `enrich_prediction` that E-233-03 will further extend to pass `response_format`; the single-source default-model resolution E-233-03's canonical slug change must remain consistent with.
- **Produces for E-233-04**: the retry loop and the `LLMError`-raising enrichment branch that E-233-04 surfaces (from the generator `except`) as its cause-agnostic `failed` status.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The retry loop lives in `enrich_prediction`, not `query_openrouter` — `query_openrouter` stays a single HTTP call per invocation (TN-3).

**Deliberate behavior change (F-G):** AC-1's non-empty `narrative` requirement tightens today's isinstance-only check (`llm_analysis.py:268`, where an empty string currently passes). After this story an empty narrative triggers Tier-1 fallback. This is intended (an empty narrative is useless to a coach), not incidental.
