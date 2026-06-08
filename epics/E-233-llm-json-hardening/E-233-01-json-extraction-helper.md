# E-233-01: Pure model-agnostic JSON-extraction helper in `src/llm/`

## Epic
[E-233: LLM JSON Hardening (Reports Tier-2 Enrichment)](../E-233-llm-json-hardening/epic.md)

## Status
`TODO`

## Description
After this story is complete, `src/llm/` will contain a pure, HTTP-free helper that extracts a JSON object (`dict`) from a raw LLM `content` string, recovering JSON from the real-world response shapes capable models emit (bare, fenced, prose-wrapped). This is the model-agnostic baseline defense against the silent Tier-2 loss documented in the epic; it is the foundation E-233-02 wires into `enrich_prediction`.

## Context
The production failure (epic Background) was a ```json markdown code fence the model emitted despite the prompt forbidding it. The current parse is a bare `json.loads(content)` with no tolerance for fences or prose. This story builds the reusable extraction primitive. It lives in `src/llm/` (not in `llm_analysis.py`) because "get a dict out of messy LLM text" is a domain-agnostic concern reusable by any future Tier-2 integration, and keeping it pure makes it parametrize-testable with no HTTP. Domain validation (the `narrative`/`bullpen_sequence` field checks) stays in `enrich_prediction` and is out of scope here.

## Acceptance Criteria
- [ ] **AC-1**: A new pure function with the locked interface `extract_json_object(content: str) -> dict` in `src/llm/` accepts a raw `content` string and returns a parsed `dict`. It performs no HTTP and no environment access. Per TN-1.
- [ ] **AC-2**: The function recovers JSON from all five must-parse shapes in Technical Notes TN-1 (bare, ```json fenced, fence-without-tag, leading prose, trailing prose), each returning the correct `dict`.
- [ ] **AC-3**: On unrecoverable input (prose-only, empty string, `None`, truncated/mid-object JSON), the function raises `LLMError` (the exception defined in `src/llm/openrouter.py`) per TN-1, so callers need no mapping and the Tier-1 fallback (TN-2) fires. It does not propagate an unhandled error (e.g., `json.loads(None)`'s `TypeError` is caught and re-raised as `LLMError`).
- [ ] **AC-4**: The function performs extraction only — it does NOT validate domain fields (`narrative`, `bullpen_sequence`). Per TN-1.
- [ ] **AC-5**: Brace-matching is string-aware per TN-1: a response whose `narrative` value contains literal `{`/`}` still extracts correctly, verified by a dedicated must-parse fixture.
- [ ] **AC-6**: Smart-quote-delimited JSON has a defined, tested outcome (normalize-and-parse OR clean-fail per TN-1) and does not crash.
- [ ] **AC-7**: A new test file covers all of the above using `pytest.mark.parametrize` over the must-parse shapes (including the brace-in-narrative case) and the clean-fail cases — prose-only, empty string, `None`, truncated, AND mid-object/unbalanced partial `{…}` (matching AC-3 and TN-6) — with no HTTP (TN-6).

## Technical Approach
Add the pure function `extract_json_object(content: str) -> dict` to `src/llm/` (a new small module such as `src/llm/json_extract.py` is the natural home; the implementer may instead place it in an existing `src/llm/` module if cleaner). The function should handle, in a robust order, stripping surrounding whitespace, removing markdown code fences, and isolating the JSON object before `json.loads`. Isolation must be string-aware so braces inside a string value (e.g., in the narrative) do not break balance — count braces only outside string literals, or trial-parse trimmed candidates. Keep it free of HTTP and env access so it tests as a pure function. Raise the existing `LLMError` from `src/llm/openrouter.py` on unrecoverable input (importing `LLMError` from `openrouter` introduces no cycle, since `openrouter` does not import this module). See epic Technical Notes TN-1, TN-2, TN-6.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-233-02

## Files to Create or Modify
- `src/llm/json_extract.py` (new — or an existing `src/llm/` module if the implementer prefers; if new, ensure it is importable consistent with the package)
- `tests/test_llm_json_extract.py` (new)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-233-02**: the pure `extract_json_object(content: str) -> dict` helper that `enrich_prediction` will call by name in place of its bare `json.loads`; it raises `LLMError` directly on failure, so E-233-02 needs no mapping.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The helper is intentionally domain-agnostic so future two-tier LLM integrations (per `.claude/rules/architecture-subsystems.md` Two-Tier Enrichment) can reuse it. There is exactly one content-JSON consumer today (`enrich_prediction`), confirmed during discovery.
