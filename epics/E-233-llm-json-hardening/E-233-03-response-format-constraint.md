# E-233-03: Constrain the request — `response_format` pass-through + canonical code-default slug

## Epic
[E-233: LLM JSON Hardening (Reports Tier-2 Enrichment)](../E-233-llm-json-hardening/epic.md)

## Status
`TODO`

## Description
After this story is complete, `query_openrouter` will accept an additive, optional `response_format` parameter that callers can use to request constrained JSON output, `enrich_prediction` will opt into it, and the code-default model slug in `openrouter.py` will use OpenRouter's canonical form. This is the belt-and-suspenders request-side defense layered on top of the E-233-01/02 parser baseline.

## Context
`query_openrouter()` (`src/llm/openrouter.py`) currently sends no `response_format`, so nothing constrains the model toward bare JSON. Many models honor `response_format={"type":"json_object"}`, but support is model-dependent and additive — it is never assumed sufficient, so the TN-1 parser remains the baseline (a model that ignores the hint must still be handled). This story also standardizes the fragile hyphenated/dated code-default slug to OpenRouter's canonical dotted form (the `.env` is operator-owned and out of scope). api-scout confirmed (2026-06-08) that `anthropic/*` models honor `response_format` (handled, not dropped) at two levels — `json_object` and `json_schema`+`strict:true`. SE concurred (2026-06-08) on `json_object` as the locked baseline (no json_schema upgrade — shape is already covered defense-in-depth by `enrich_prediction`'s field validation + the S1 parser + S2 retry). Prefill is NOT used (not stackable, not echoed). All design questions for this story are resolved.

## Acceptance Criteria
- [ ] **AC-1**: `query_openrouter` accepts an optional, additive `response_format` parameter defaulting to `None`. When `None`, the key is OMITTED from the request body entirely — the *presence/absence of the `response_format` key* is unchanged from today for callers that do not pass it. When provided, it is included in the request body. Per Technical Notes TN-7 (SE pass-through note). (Note: this story ALSO changes `_DEFAULT_MODEL` via AC-4, which independently alters the default-model fallback and its existing test at `tests/test_openrouter.py:109` — see AC-4; that is an intended change, distinct from the response_format key behavior.)
- [ ] **AC-2**: A test asserts the wire format — when the parameter is provided, it appears in the request body; when omitted, it does not — by patching httpx (the `tests/test_openrouter.py` wire-format seam per TN-6; this is the ONE assertion that legitimately patches the transport layer, because it must inspect the actual request body).
- [ ] **AC-3**: `enrich_prediction` opts into the constrained-output request using `response_format={"type":"json_object"}` per Technical Notes TN-7 (LOCKED — SE concurred; no json_schema upgrade). The value is passed at the single invocation point introduced by E-233-02 (AC-8), so it rides BOTH the initial call and the TN-3 retry (F-C). The existing system-prompt JSON instruction is retained, since json_object guarantees valid JSON but not the prompt's intent. Prefill is not used.
- [ ] **AC-4**: The code-default model literal `_DEFAULT_MODEL` at `src/llm/openrouter.py:26` is set to `anthropic/claude-haiku-4.5` (api-scout-verified live id supporting `response_format`) per TN-5. This is a concrete literal change — no live `GET /api/v1/models` call at implement time and no escape hatch (the current dated default does not resolve to any live id). The `.env` is not modified.
- [ ] **AC-5**: The TN-1 parser path remains the baseline — a test confirms that even with `response_format` requested, a fenced/prose response still parses correctly (i.e., the request constraint does not replace the parser). Per TN-7.

## Technical Approach
Add an optional `response_format` pass-through parameter to `query_openrouter` defaulting to `None`; merge it into the request body only when supplied and OMIT the key entirely when `None`, preserving the exact existing body shape so current callers/tests are unaffected. Have `enrich_prediction` pass `{"type":"json_object"}` (per TN-7) through the single invocation point from E-233-02 (AC-8) so it applies to the initial call and the retry alike (F-C). Set the `_DEFAULT_MODEL` literal at `src/llm/openrouter.py:26` to `anthropic/claude-haiku-4.5` (api-scout-verified — no live call needed; single-source per TN-5, do not reintroduce a second default literal). See epic Technical Notes TN-5, TN-6, TN-7.

## Dependencies
- **Blocked by**: E-233-02 (shares `src/reports/llm_analysis.py`; serialize the edits per TN-8)
- **Blocks**: None

## Files to Create or Modify
- `src/llm/openrouter.py`
- `src/reports/llm_analysis.py`
- `tests/test_openrouter.py`
- `tests/test_llm_analysis.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
api-scout's findings (2026-06-08) are incorporated: `response_format` is honored for `anthropic/*` (json_object + json_schema/strict); prefill supported but not used (not stackable, not echoed — implementer note only); the dated code-default haiku slug does not resolve to any live id, so AC-4 sets the default to the verified literal `anthropic/claude-haiku-4.5` (concrete change, no live call). SE concurred (2026-06-08) on json_object as the locked baseline — no remaining design TBDs. The OpenRouter "Response Healing" plugin is out of scope (we build our own parser).
