# E-233: LLM JSON Hardening (Reports Tier-2 Enrichment)

## Status
`READY`

## Overview
Standalone report generation intermittently loses its Tier-2 LLM "predicted starter" narrative because the JSON parser does a bare `json.loads` that cannot tolerate the markdown code fences or surrounding prose that capable models occasionally emit even when instructed not to. Failures degrade silently to the Tier-1 deterministic prediction with no operator-visible signal. This epic hardens the parser (model-agnostic), constrains the request, adds a single retry, and makes the silent degradation operator-detectable — so coaches stop getting inconsistent reports for invisible reasons.

## Background & Context
On 2026-06-08, standalone report generation for `public_id=hLEgTDs1BZX8` raised `LLMError: LLM response is not valid JSON: Expecting value: line 3 column 1 (char 2)` at `src/reports/llm_analysis.py:259`. The OpenRouter HTTP call returned 200 OK — the model answered; the reply just was not bare JSON. The "char 2 after two leading newlines" signature is a ```json markdown code fence: the model fenced its JSON despite the system prompt explicitly forbidding markdown and code fences. The behavior is intermittent (clean the large majority of the time, fenced occasionally; longer/complex prompts — real reports inject full pitcher and NSAA rest tables — appear to make the lapse more likely).

Root cause was verified by reproduction, not inferred. The defect is in the parser, not the model: `src/reports/llm_analysis.py:259` does a bare `json.loads(content)` with no fence-stripping and no preamble tolerance, and `query_openrouter()` in `src/llm/openrouter.py` sends no `response_format` to constrain output. A model swap (Opus 4.6 → 4.8 stress-tested 12/12 clean JSON) is explicitly NOT a fix — 12/12 clean is consistent with a low fence rate, not proof the fence is gone, and any capable model can fence. The parser must be robust regardless of model.

The silent-degradation behavior is arguably the worse half of the bug: nobody knows when AI analysis goes missing. The report already renders differently on failure (no narrative div, no "AI-assisted analysis" annotation) — but that absence is unlabeled, so neither operator nor coach knows Tier-2 was supposed to be present.

Expert input incorporated during discovery:
- **software-engineer**: three independent failure surfaces (no `response_format`; bare `json.loads`; no retry), a pure `extract_json_object` helper kept HTTP-free for parametrized testing, and a latent duplicate-default-model bug (the default model literal appears in both `src/llm/openrouter.py:26` and `src/reports/llm_analysis.py:230` and can drift).
- **api-scout** (resolved 2026-06-08): `response_format` is honored for `anthropic/*` (both `json_object` and `json_schema`+`strict`; `opus-4.8` qualifies); assistant-prefill is supported but not stackable with JSON mode and not echoed (so not used); the dated code-default haiku slug does not resolve to any live id, so the default is replaced with the verified literal `anthropic/claude-haiku-4.5` (see TN-5). Incorporated into TN-5 and TN-7.
- **baseball-coach** (consulted 2026-06-08, on the two coach-facing changes): CONCURRED, no AC changes. Change 1 (empty `narrative` → Tier-1 fallback, S2 AC-1) validated as unambiguously correct — an empty "AI analysis" box on a game-day report is worse than none (a coach can't tell whether the system broke or had nothing to say); Tier-1 is always actionable. Change 2 (no coach-visible label, Medium observability, S4 AC-3) accepted given the user's appetite choice — coaches don't care about system internals. **Flag for the record (not a reason to reverse now):** if Tier-2 becomes a regular part of coach pre-game workflow, silent disappearance on LLM-failure days could erode trust in report consistency; keep Tier-1 quality high so Tier-2 reads as "bonus context," and revisit the no-label decision at that point. Captured as a vision signal.

Scope confirmed with the user: reports flow only; observability is operator/log-level (Medium), not coach-visible; truncation-repair is a non-goal; the duplicate-default dedup and a minimal code-default slug standardization are in scope.

## Goals
- The Tier-2 JSON parse tolerates the real-world response shapes capable models emit: bare JSON, ```json fenced, fence-without-language-tag, leading prose, and trailing prose — all parse to the correct dataclass.
- A genuinely unparseable response (after one retry) still degrades to Tier-1 cleanly: no crash, WARNING logged, report still renders. The existing non-fatal contract is preserved.
- The request is constrained with `response_format` (additive, model-dependent) as a belt-and-suspenders defense on top of the parser baseline.
- Silent Tier-2 loss becomes operator-detectable via a structured generation status (success / unavailable-no-key / failed).
- The default model is defined in exactly one place; the code default uses the canonical OpenRouter slug.

## Non-Goals
- Coach-visible report-side labeling of Tier-2 absence (renderer/template changes). Observability is operator/log-level only.
- Truncation-detection or partial-JSON-repair logic. A truncated response is treated as legitimately unparseable → fallback + status signal.
- Changing `.env` model slugs (worktrees have no `.env`; operator owns `.env`).
- Any change to the dashboard/opponent flow — it does not use Tier-2 enrichment.
- Replacing or re-tuning the LLM model as the fix (model swap is explicitly not the remedy).
- Multi-retry / exponential backoff. Exactly one retry.

## Success Criteria
- All five real-world response shapes (TN-1) parse to the correct `EnrichedPrediction`; a genuinely unparseable response after retry degrades to Tier-1 with a WARNING and no crash.
- `query_openrouter` sends `response_format` per TN-7 and the wire format is asserted in a test.
- The default model literal appears in exactly one source location (TN-5).
- A structured generation status (TN-4) is emitted for each of the three outcomes and asserted in tests.
- All new/changed behavior is covered by tests at the seam appropriate to each (per TN-6): the S1 helper tests are pure/no-HTTP; the `enrich_prediction`-path tests patch `query_openrouter`; only the S3 wire-format assertion patches httpx. The full suite is green at closure.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-233-01 | Pure model-agnostic JSON-extraction helper in `src/llm/` | TODO | None | - |
| E-233-02 | Harden `enrich_prediction`: defensive parse + one retry + dedup default model | TODO | E-233-01 | - |
| E-233-03 | Constrain the request: `response_format` pass-through + canonical code-default slug | TODO | E-233-02 | - |
| E-233-04 | Operator-detectable Tier-2 generation status (Medium observability) | TODO | E-233-02 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Defensive parse contract (the model-agnostic baseline)
A pure helper with the locked interface `extract_json_object(content: str) -> dict` (no HTTP, no env access) accepts the raw LLM `content` string and returns a parsed `dict`. It must recover JSON from these five confirmed real-world shapes, all of which must parse to the correct object:
1. Bare JSON (`{...}`)
2. ```json fenced (triple-backtick with a `json` language tag)
3. Fenced without a language tag (triple-backtick, no tag)
4. Leading prose before the JSON (e.g., "Here is the analysis:\n{...}")
5. Trailing prose after the JSON

On input it cannot recover (prose-only, empty string, `None`, or truncated/mid-object JSON), it raises `LLMError` (the exception already defined in `src/llm/openrouter.py`) — so callers need no mapping and the Tier-1 fallback path (TN-2) still fires. It must guard against unhandled errors (e.g., `json.loads(None)` raises `TypeError`); those are caught and re-raised as `LLMError`. The helper does NOT perform domain validation (presence/type of `narrative`, `bullpen_sequence`) — that remains in `enrich_prediction`. Separation of concerns: `src/llm/` owns *extraction* (get a dict out of messy text); `llm_analysis.py` owns *domain validation*.

**String-aware extraction (F-F):** when isolating the JSON object from surrounding prose, brace-matching MUST be string-aware — a `{` or `}` inside a JSON string value (e.g., inside the narrative text) must not break the balance. The required outcome is correct extraction when a string value contains literal braces; the mechanism (counting braces only outside string literals, or trial-parsing trimmed candidates) is the implementer's call. A fixture whose `narrative` contains a brace is required (TN-6).

Smart-quote-delimited JSON is a known rare mode. It is acceptable for the helper to either normalize-and-parse it OR clean-fail it — implementer's call — but the chosen behavior MUST be covered by a test. Do not crash on it.

### TN-2: Non-fatal contract (must be preserved)
Tier-2 enrichment is optional. A genuinely unparseable response (after the retry in TN-3) must result in: `LLMError` raised by `enrich_prediction`, caught by the existing broad `except` at `src/reports/generator.py:~1203`, a WARNING logged, and the report rendered with the Tier-1 deterministic prediction. No crash, no HTTP retry storm, report still produced.

### TN-3: Retry policy
Exactly one retry on parse failure. Sequence: call `query_openrouter` → run the TN-1 extraction → on extraction failure, retry the call ONCE with `temperature=0` (to reduce output variance) → run TN-1 extraction again → if still failing, raise `LLMError` (→ TN-2 fallback). One retry only; no exponential backoff; no retry on HTTP/transport errors (those already raise `LLMError` from `query_openrouter`). The retry loop lives in `enrich_prediction`; `query_openrouter` remains a single HTTP call per invocation.

**Single invocation point (F-C):** factor the `query_openrouter` call inside `enrich_prediction` into ONE local helper/closure so the initial call and the retry share identical kwargs (`model`, `max_tokens`, and — once E-233-03 lands — `response_format`), varying ONLY `temperature`. Every `query_openrouter` invocation within `enrich_prediction`, including this retry, MUST carry the same `response_format`; the retry must not silently drop the JSON constraint.

### TN-4: Operator observability (Medium — log/operator-detectable only)
Emit a structured generation status distinguishing the three Tier-2 outcomes, observable at the report-generation site (`src/reports/generator.py`):
- `success` — enrichment returned an `EnrichedPrediction`.
- `unavailable-no-key` — `is_llm_available()` was False (Tier-2 skipped; not a failure).
- `failed` — `enrich_prediction` raised `LLMError` for ANY reason: a parse failure after the TN-3 retry, an HTTP/transport error (not retried), or — once E-233-03 lands — a `response_format`-400. This status is **cause-agnostic**: it is read from the generator's `except` branch (`except Exception` at `src/reports/generator.py:~1203`), NOT from the exception type. The preserved WARNING (with `exc_info`) carries the specific cause for log triage. (SE-confirmed: a per-cause status would force `enrich_prediction` to signal the reason upward — real complexity against "simple first" for a Medium/operator-observability goal.)
This is log/operator-level only. NO coach-visible report label, NO renderer.py or template changes. The exact log/status mechanism (structured logger fields vs. a small status value) is the implementer's call, but each of the three outcomes must be distinguishable and asserted in a test.

### TN-5: Single-source default model + canonical slug
The default model literal must exist in exactly one source location. Today it is duplicated: `_DEFAULT_MODEL` at `src/llm/openrouter.py:26` and a hardcoded literal in `enrich_prediction` at `src/reports/llm_analysis.py:230`. After this epic, `llm_analysis.py` MUST NOT re-default the model — `query_openrouter` owns the default.

**`model_used` source (F-A):** `EnrichedPrediction.model_used` MUST reflect the model actually used. Because `query_openrouter` resolves `model or OPENROUTER_MODEL or _DEFAULT_MODEL` (`src/llm/openrouter.py:65`), importing the shared constant would be WRONG whenever `OPENROUTER_MODEL` is set (the constant ≠ the model used). Therefore `model_used` MUST be read from the OpenRouter response body (`response["model"]`), with a safe fallback if that field is absent. Importing the constant is NOT an acceptable mechanism. A test asserts `model_used` derives from the mocked response, not from env or the constant.

**Canonical slug (F-B, api-scout-verified):** Set `_DEFAULT_MODEL` at `src/llm/openrouter.py:26` to the literal `anthropic/claude-haiku-4.5`. api-scout confirmed (live `GET /api/v1/models`) this is a live, stable generation id whose `supported_parameters` includes `response_format`. The current dated default `anthropic/claude-haiku-4-5-20251001` does NOT resolve to any live id (wrong separator `4-5` vs `4.5` and wrong token order) — a latent broken string that only "works" because production overrides via `OPENROUTER_MODEL` (dotted `opus-4.8`). This is a concrete literal change: NO live API call at implement time (the epic worktree has no `.env`/creds/guaranteed network) and NO "leave untouched" escape hatch. `.env` is out of scope.

### TN-6: Testing conventions
- The TN-1 helper is tested directly with `pytest.mark.parametrize` over the five must-parse shapes — plus a sixth must-parse fixture whose `narrative` value contains literal braces (`{`/`}`) to verify string-aware extraction (F-F) — and the clean-fail cases (prose-only, empty string, `None`, truncated/mid-object) and the smart-quote case. No HTTP.
- Mock at the level appropriate to the assertion (do not introduce real OpenRouter calls): the **wire-format** assertion (`response_format` present/absent in the request body, E-233-03 AC-2) must patch at the httpx transport layer — the pattern in `tests/test_openrouter.py` (which patches `httpx`); the **retry/extract path** inside `enrich_prediction` (E-233-02) is tested by patching `query_openrouter` to return canned responses — the pattern in `tests/test_llm_analysis.py` (which patches `src.reports.llm_analysis.query_openrouter`, NOT `httpx`).
- Error-path test: retry exhaustion still raises `LLMError` and the generator's fallback produces a Tier-1 report (TN-2).
- Observability test: each of the three TN-4 outcomes emits the distinguishable status.
- Follow `.claude/rules/testing.md` test-scope discovery: run all test files importing from any module changed.

### TN-7: response_format request constraint (E-233-03)
api-scout confirmed (live `GET /api/v1/models`): `anthropic/*` models honor `response_format` — it is handled, not silently dropped. Two levels exist: `{"type":"json_object"}` (guarantees valid JSON, no shape guarantee, still requires the prompt's JSON instruction) and `{"type":"json_schema","json_schema":{...,"strict":true}}` (enforces an exact shape; Anthropic Opus 4.1+; `opus-4.8` qualifies).

`query_openrouter` gains an additive, optional pass-through parameter so callers can request constrained JSON output. Default behavior (parameter omitted) is unchanged — existing callers and tests are unaffected. `enrich_prediction` opts in.

**Decision (LOCKED — SE concurred 2026-06-08):** Use `response_format={"type":"json_object"}`; do NOT upgrade to `json_schema`+`strict`. Rationale per "simple first": the observed production failure is *fencing* (a valid-JSON-but-wrapped failure, not shape drift), which `json_object` eliminates at the API level; shape enforcement is already held defense-in-depth by `enrich_prediction`'s existing field validation (the `narrative` presence/type check at `src/reports/llm_analysis.py:264-274`) plus the S1 parser and S2 retry. A strict schema adds model-coupled complexity for a guarantee we already have, against "simple first" and the user's named choice. **Pass-through shape (SE implementation note):** `response_format` is an optional parameter on `query_openrouter` defaulting to `None`; when `None`, the key is OMITTED from the request body entirely, so non-JSON callers and models that do not support it are never forced into it.

**Prefill: NOT used.** api-scout confirmed prefill is supported but is NOT stackable with `response_format`, and a prefilled `{` is not echoed (caller must prepend it). Since `response_format` is confirmed for our model, prefill adds complexity for no marginal gain. (Gotcha captured as a note only.)

`response_format` is model-dependent and additive — never assumed sufficient. The enforcement mechanism is undocumented (inferred server-side translation), so the TN-1 parser (S1) and TN-3 retry (S2) REMAIN the model-agnostic baseline and defense-in-depth; S3 must not weaken or remove them. A model that ignores `response_format`, or an unsupported model that 400s on it, still degrades to Tier-1 via the existing non-fatal path (TN-2).

### TN-8: File-touch ordering
`E-233-02` and `E-233-03` both modify `src/reports/llm_analysis.py`; `E-233-03` also modifies `src/llm/openrouter.py`. To serialize the shared-file edits, `E-233-03` is blocked by `E-233-02`. `E-233-04` modifies `src/reports/generator.py` only (no conflict with 02/03) but is blocked by `E-233-02` because the enrichment/`failed`-status branch it instruments is finalized in `E-233-02`. `E-233-04` is **NOT** blocked by `E-233-03`: the `failed` status is cause-agnostic (read from the generator `except` branch, not the exception type — TN-4), so the `response_format`-400 failure mode introduced by `E-233-03` lands in the same `failed` branch automatically with no `E-233-04` code change. Execution order: 01 → 02 → (03, 04).

## Open Questions
- **api-scout (RESOLVED 2026-06-08):** `response_format` IS honored for `anthropic/*` (json_object + json_schema/strict both available; opus-4.8 qualifies). Prefill supported but not stackable and not echoed → not used. Slug: the dated code-default haiku slug does not resolve to any live id; the default is set to the verified literal `anthropic/claude-haiku-4.5` (TN-5/F-B, a concrete change with no live call). Incorporated into TN-5 and TN-7.
- **SE (RESOLVED 2026-06-08):** SE concurred with `json_object` as the baseline; no upgrade to `json_schema`+`strict`. Shape enforcement is already covered defense-in-depth by `enrich_prediction`'s field validation + S1 parser + S2 retry. TN-7 locked. No open design questions remain.
- **Closure-time context-layer assessment:** If `response_format` is now sent and/or the default slug changes, the LLM Package note in `.claude/rules/architecture-subsystems.md` (and possibly the OpenRouter exception note in `.claude/rules/http-discipline.md`) may need a one-line update. Evaluate at closure per the context-layer assessment gate; not a story.

## History
- 2026-06-08: Created (DRAFT). Discovery complete; problem statement, constraints, and scope forks resolved with the user (Q4=Medium observability; helper placement, max_tokens bump, one-retry, dedup-default, minimal slug-standardization all approved). E-233-03's `response_format` behavior ACs and canonical slug held TBD pending api-scout.
- 2026-06-08: api-scout Q1 resolved. `response_format` confirmed honored for `anthropic/*` (json_object + json_schema/strict; opus-4.8 qualifies); prefill supported but not used; dated haiku code-default slug not found live → slug change gated on live verification. TN-5, TN-7, and E-233-03 ACs finalized around json_object + leave-untouched-if-unverifiable slug.
- 2026-06-08: SE concurred on json_object as the locked baseline (no json_schema upgrade); shape covered defense-in-depth by existing field validation + S1 parser + S2 retry. SE pass-through note added to TN-7 (`response_format` default `None` omits the key). TN-7 LOCKED. All design TBDs cleared; epic is complete and ready for Phase 3 spec review.
- 2026-06-08: Phase 4 Codex spec review (5 findings) — ALL 5 ACCEPTED and incorporated. C1 (P1, SE-confirmed): failure-status taxonomy collapsed to cause-agnostic `{success, unavailable-no-key, failed}` — `failed` = `enrich_prediction` raised `LLMError` for any reason, read from the generator `except` branch (cause in WARNING `exc_info`, not the status); S4 stays blocked-by-S2-only with no S3 ordering dependency (TN-3/TN-4/TN-8, S4 AC-1/AC-2). C2 (P1): purged stale live-verify/escape-hatch slug language from Background/Open Questions/S3 Notes (History append-only, superseded) — earlier "sweep clean" claim was wrong; corrected via literal re-read per the clean-reread discipline. C3 (P2): S3 AC-1 "unchanged" narrowed to the response_format-key presence, with the `_DEFAULT_MODEL`/test-fallback change called out. C4 (P2): S1 AC-7 adds the mid-object fixture. C5 (P3): TN-6 patch-target reference corrected (httpx in test_openrouter.py; query_openrouter in test_llm_analysis.py). Final consistency sweep clean.
- 2026-06-08: Phase 3 internal review complete (CR + SE + api-scout, 8 deduplicated findings). ALL 8 ACCEPTED and incorporated: F-A (`model_used` from `response["model"]`, not the constant — TN-5/S2 AC-5); F-B (slug fixed to verified literal `anthropic/claude-haiku-4.5`, live-verify AC replaced — the dated default was a broken string — TN-5/S3 AC-4); F-C (response_format rides initial+retry via a single invocation point — TN-3/S2 AC-8/S3 AC-3); F-D (remove now-unused `import os`/`import json` — S2); F-E (extract `_run_tier2_enrichment` helper for testability — S4); F-F (lock `extract_json_object(content: str) -> dict` + `LLMError`; string-aware brace extraction + None/brace fixtures — TN-1/TN-6/S1); F-G (non-empty narrative flagged deliberate — S2 Notes); F-H (AC-6 reworded to "remove the 512 override"; default already 1024 — S2). Post-incorporation consistency sweep clean. Refinement complete. (Note: this Phase-3 entry precedes the Phase-4 entry above it chronologically; both are same-day 2026-06-08.)
- 2026-06-08: Phase 4 Codex iteration 2 (final/circuit-breaker) — 2 emergent P2 findings, both ACCEPTED. D2: the C5 test-seam correction had not propagated — aligned S2 AC-4/AC-7 (patch `query_openrouter`), S3 AC-2 (explicitly patch httpx for the wire-format assertion), and the epic Success Criterion (L42, layered seam) with TN-6; S1 stays pure/no-HTTP. D1: baseball-coach consulted on the two coach-facing changes (empty-narrative→Tier-1 fallback; operator-only/no-coach-label) — coach CONCURRED, NO AC changes; consulted-experts list updated (Background), and coach's forward-looking trust-erosion flag captured as a vision signal in `docs/vision-signals.md`. Final consistency sweep clean. Epic FINAL.
- 2026-06-08: Set to **READY** (user-approved). All review rounds closed; review scorecard below.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 5 | 5 | 0 |
| Internal iteration 1 — Holistic team (SE) | 7 | 7 | 0 |
| Internal iteration 1 — Holistic team (api-scout) | 0 | 0 | 0 |
| (Phase 3 deduplicated total) | 8 | 8 | 0 |
| Codex iteration 1 | 5 | 5 | 0 |
| Codex iteration 2 | 2 | 2 | 0 |
| **Total** | **15** | **15** | **0** |

Phase 3 operative total is the deduplicated count of 8 unified findings (F-A…F-H); the raw per-reviewer counts (CR=5 + SE=7 + api-scout=0) deduplicated to those 8. Total = 8 (Phase 3 dedup) + 5 (Codex iter 1) + 2 (Codex iter 2) = 15, all accepted, none dismissed.
