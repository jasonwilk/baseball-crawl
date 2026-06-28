# E-243-04: Re-point Tier-2 LLM narration; drop the no-predict guideline

## Epic
[E-243: Make the Probable-Starter Analysis Useful on Game Morning](epic.md)

## Status
`DONE`

## Description
After this story, the optional Tier-2 LLM narration leads with the named most-likely arm and a concrete rest reason, names the unavailable arms, and uses plain English with no hedge — replacing the hedge-heavy "committee situation" prose. It installs the bake-off-validated "Variant A" prompt, runs the Tier-2 model as `google/gemini-2.5-flash-lite` at temperature 0.0, keeps the LLM data block to pitch count (no decimal IP field), and removes the "do not manufacture a prediction" guideline. This aligns the prose with the reframed deterministic card from E-243-03 and closes the "the narrative is the one thing we didn't validate" gap.

## Context
The Tier-2 system prompt in `src/reports/llm_analysis.py` currently includes the guideline: "At LOW/COMMITTEE confidence: explain the ambiguity honestly. Do not manufacture a prediction." This is the prompt-level cause of the hedge-heavy "committee situation" narration the user dislikes. With E-243-03 surfacing a ranked top-2/3 deterministically, the narration should describe those arms and the rest reasoning, not withhold. Tier-2 is optional and non-fatal (no `OPENROUTER_API_KEY` = silent skip); this story changes the Tier-2 prompt, model, and LLM data block (not the deterministic Tier-1 path or the card's rest table / game log).

## Acceptance Criteria
- [ ] **AC-1**: The Tier-2 system prompt (`_SYSTEM_PROMPT_TEMPLATE` in `src/reports/llm_analysis.py`) no longer contains any instruction to withhold or not manufacture a prediction at low/committee confidence (per Technical Notes TN-6).
- [ ] **AC-2**: The reframed prompt is the **validated "Variant A"** prompt, persisted verbatim at `epics/E-243-probable-starter-usefulness/E-243-04-narration-prompt.md` (the source of truth — the implementation reproduces it rather than re-deriving wording). It leads with the named most-likely arm + a concrete rest reason, names the unavailable arms, uses plain English, and carries no hedge. Variant A scored a perfect 16/16 for the chosen model `google/gemini-2.5-flash-lite` (tied #1 of the 13-model bake-off; field mean ≈15.3), and ≈15.8 mean while beating or tying the regressing Variant B on every model in the temp-0.0 A/B round (A/B evidence in `.project/research/narrative-bakeoff/ab_report.md`). The persisted prompt file also documents the AC-8 deviation: the as-run bake-off block showed `({ip} IP)`, the shipped block drops the decimal IP (pitch-count only). Per Technical Notes TN-6.
- [ ] **AC-3**: Given a youth/travel prediction with `is_estimate == True` (from E-243-02), the `is_estimate` flag is threaded into `_build_user_prompt`/`_format_pitcher_table` and the prompt directs the model toward the ratified estimate framing — conveying the consequence in plain English, e.g., "Rest eligibility is an estimate — this league's pitch-count rules weren't confirmed, so treat timing calls at the margins as approximate" — so the narration does not present it as a binding league rule. The **rendered narrative obeys the same absolute no-jargon rule as the card** (TN-5): "Pitch Smart"/"Legion"/"USA Baseball"/"soft prior" must NOT appear in the model's output prose, even though the prompt context may name the source internally. (Final narration substance is baseball-coach's domain; this AC applies UXD's no-brand-in-rendered-report principle to the output.)
- [ ] **AC-4**: Tier-2 remains optional and non-fatal: with no API key, the report still renders the deterministic card unchanged; an LLM failure remains caught and non-fatal (no change to the existing non-fatal contract).
- [ ] **AC-5**: Existing `tests/` covering `llm_analysis.py` (prompt construction, JSON parsing, non-fatal handling) pass; any assertion that encodes the removed guideline text is updated.
- [ ] **AC-6**: The no-jargon rule (AC-3) is made verifiable, not eyeball-only: (a) a unit test on prompt construction asserts the `is_estimate` consequence framing reaches the prompt AND that the prompt contains no directive instructing the model to emit brand names in its output; and (b) a **REQUIRED** (not optional) manual-verification step — on a sample youth/travel report with the LLM enabled, confirm the rendered narrative contains none of the banned strings ("Pitch Smart" / "Legion" / "USA Baseball" / "soft prior"). The manual step is required because live-model output is not deterministically unit-testable; the prompt-construction test covers the deterministic surface.
- [ ] **AC-7**: The Tier-2 narration runs as **`google/gemini-2.5-flash-lite` at temperature 0.0** (per Technical Notes TN-6 — bake-off winner, validated by an LLM judge AND baseball-coach human review), wired as three SE-verified changes (the reports Tier-2 enrich path is the ONLY production caller of `query_openrouter`/`_DEFAULT_MODEL` — zero blast radius):
  - **(a) Default model** — make gemini the true code default while preserving the `OPENROUTER_MODEL` operator override: set `_DEFAULT_MODEL = "google/gemini-2.5-flash-lite"` at `src/llm/openrouter.py:26`; update the stale module docstring at `openrouter.py:11-12` (currently `anthropic/claude-haiku-4.5`) to gemini (same-file stale-doc fix); update `.env.example:247-248` (the `# Default:` comment and the commented `# OPENROUTER_MODEL=` example value) to gemini, kept commented; and fix the stale assertion in `tests/test_openrouter.py:~98-109` that deletes the env var and asserts the default is `anthropic/claude-haiku-4.5` → assert `google/gemini-2.5-flash-lite` (same-change stale-test fix per `.claude/rules/testing.md`; SE verified the other haiku test hits are mock echoes / explicit-override-path tests, unaffected).
  - **(b) Override preserved** — do NOT hardcode `model="..."` at the enrich call site; `resolved_model = model or env...` must keep honoring `OPENROUTER_MODEL` (hardcoding would silently ignore the override). The tracked code default in (a) — `_DEFAULT_MODEL` + `.env.example` — is what SHIPS the validated model; setting `OPENROUTER_MODEL` in the gitignored `.env` is an OPTIONAL operator override, NOT required for the validated model to ship (this closes the Codex iter-2 ".env gitignored / hidden dependency" finding).
  - **(c) Temperature** — change the hardcoded initial production call `_invoke(0.3)` at `src/reports/llm_analysis.py:282` to `_invoke(0.0)` (the env var does NOT control temperature; the retry at `:287` is already `0.0`). If OpenRouter enforces a temperature floor, use the lowest supported value and comment it.
  The deterministic Tier-1 path is unaffected.
- [ ] **AC-8**: The reframed ranked-arms data block passed to the LLM surfaces **pitch count** and does **NOT introduce a decimal IP field** (SE-verified: there is no decimal-IP field in the current production `_format_pitcher_table` — the decimal "6.3-inning" IP lived only in the bake-off data block; this AC is a GUARD against adding it, per baseball-coach: decimal IP yields "6.3-inning" prose with no coaching payoff, pitch count is the rest-relevant datum). The existing **integer "IP Outs" game-log column** (`llm_analysis.py:131`/`:136`) is OUT OF SCOPE — do not strip it. The deterministic card's rest table and game log are unchanged.

## Technical Approach
Per Technical Notes TN-6: replace `_SYSTEM_PROMPT_TEMPLATE` with the validated Variant A prompt (verbatim source in `.project/research/narrative-bakeoff/`), which removes the "Do not manufacture a prediction" guideline and leads with the named most-likely arm + concrete rest reason. Run the Tier-2 narration as `google/gemini-2.5-flash-lite` (set `OPENROUTER_MODEL` in `.env`) at temperature 0.0 (change the hardcoded `_invoke(0.3)` at `llm_analysis.py:282` to `_invoke(0.0)` — temp is not env-controlled; lowest supported if a floor applies, commented). Keep the LLM data block to pitch count — do NOT introduce a decimal IP field (none exists in production today); leave the integer "IP Outs" game-log column alone. Ensure the estimate context (E-243-02 `is_estimate`) reaches the prompt — the structured block already includes `top_candidates`; pass the estimate marker through. Keep the JSON response contract, the `response_format` hardening, and the retry/extraction baseline unchanged (see `.claude/rules/architecture-subsystems.md` LLM Package). Do not alter the deterministic Tier-1 engine or the card's rest table / game log.

## Dependencies
- **Blocked by**: E-243-03
- **Blocks**: None

## Files to Create or Modify
- `src/reports/llm_analysis.py` (prompt, temperature edit at `:282`)
- `src/llm/openrouter.py` (AC-7a: `_DEFAULT_MODEL` at `:26` + stale module docstring at `:11-12`)
- `.env.example` (AC-7a: `# Default:` comment + commented `# OPENROUTER_MODEL=` example at `:247-248`)
- `tests/test_openrouter.py` (AC-7a: stale default-model assertion at `~:98-109`)
- Test(s) covering `llm_analysis.py` (the implementer discovers the exact file(s) per `.claude/rules/testing.md` test-scope discovery)
- `epics/E-243-probable-starter-usefulness/E-243-04-narration-prompt.md` (read-only INPUT — the verbatim validated Variant A prompt, source of truth for AC-2; authored by SE, consumed not modified)
- `.project/research/narrative-bakeoff/` (read-only INPUT — the A/B evidence; consumed, not modified)
- NOT in this story (closure context-layer item): `.claude/rules/architecture-subsystems.md:92` records the canonical default model as `anthropic/claude-haiku-4.5` and goes stale with AC-7a — claude-architect updates it at closure, not the implementer (see Technical Notes TN-6).

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The narration was validated by the pre-READY narrative bake-off (artifacts in `.project/research/narrative-bakeoff/`): a ~12-model field scored by a GPT-5.1 LLM judge plus baseball-coach human review across 5 scenarios. Variant A won (gemini-2.5-flash-lite, 16/16). This supersedes the earlier "we never eyeballed the narration" open thread.

**REJECTED — do NOT re-attempt "Variant B" (recorded so it isn't re-tried):** an enhanced prompt adding a rotation-slot rationale field + a committee-honesty instruction was tested and REJECTED. It regressed on 2 of 3 models, and (a) its rotation-rationale lever cannot fire because every real opponent classifies as "committee" (no differentiated rotation roles exist — consistent with the backtest's structural-committee finding), and (b) its committee-honesty wording backfired, causing models to reintroduce the banned word "committee." Rotation-rationale is a possible FUTURE enhancement ONLY IF the engine is later changed to emit differentiated per-arm rotation roles AND the committee wording is reworked — out of scope for E-243.

(Bake-off rubric max is 16, not 18 — coach's correction; no rankings changed.)
