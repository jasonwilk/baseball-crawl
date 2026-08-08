# IDEA-133: Deep Scout v2 LLM two-pass synthesis (model-eval-gated)

## Status
`CANDIDATE`

<!--
Status definitions:
  CANDIDATE  -- Active idea, worth revisiting. Default status for new ideas.
  PROMOTED   -- Became an epic. Record which one in the Notes section.
  DEFERRED   -- Deliberately set aside. Include a reason and a re-review date.
  DISCARDED  -- Decided against. Include a reason so we don't re-propose it.
-->

## Summary
The v2 LLM two-pass synthesis for Deep Scout: pass 1 turns the deterministic fact sheet into a narrated coach memo; pass 2 translates the memo into player-facing materials under the ethics rails (team-tendency/number-only, never a named opposing minor next to a weakness). E-263 (Deep Scout v1) ships the Game Plan deterministically (templated); this idea is the LLM-narrated upgrade on top of the same fact sheet. **Hard operator prerequisite: the prose work MUST be preceded by a model-eval step — "test models with evals before the prose." The synthesis slice does not start until candidate models are eval'd.**

## Why It Matters
The design doc (§6) frames the fact-sheet → coach-memo → player-materials two-pass as the richer consumption layer (60-second locker-room script, laminate-ready One Card). E-263 proved the deterministic layer is the product and shipped it first; the LLM narrative is the polish. The operator's 2026-07-13 requirement is that model selection be evidence-based (evals) rather than picking a model and writing prompts against it — a live-model narrative that hedges, invents, or leaks a named minor is worse than the deterministic card. The model-eval gate prices that risk in before any prose lands.

## Rough Timing
After E-263 (Deep Scout v1) ships the deterministic fact sheet + sections. Promote when the operator wants the narrated memo / player materials AND is ready to run the model-eval step. Likely pairs with or follows IDEA-132 (the matchup paradigm), since the player-materials pass and the ethics-split anonymization layer are most valuable once matchup context exists.

## Dependencies & Blockers
- [ ] E-263 (Deep Scout v1) ships the fact-sheet spine + per-signal ethics tiers (the v1 fact sheet already carries the ethics tier so the player-materials pass has no rework)
- [ ] **Model-eval step complete** (operator-required gate) — candidate models eval'd before prompt/prose work begins
- [ ] The v2 player-facing One Card / role-card artifacts (the second output surface the player-materials pass feeds)

## Open Questions
- What does the model-eval harness measure (jargon leakage, hallucinated numbers, ethics-rail violations naming a minor, adherence to fact-sheet-only numbers, word budgets)?
- Which existing infra is reused (`src/llm/openrouter.py`, `extract_json_object`, `response_format`, the Two-Tier non-fatal pattern) vs net-new?
- Does the coach-memo pass replace or sit beside the existing Most Likely Arms `enrich_prediction()` narrative?
- Overlap with IDEA-079 (rich predicted-starter/bullpen LLM narrative) and IDEA-085 (richer LLM data-block translations) — consolidate or keep distinct?

## Notes
- Companion: `.project/research/deep-scout-design-2026-07-12.md` §6 (prompt architecture — compute-don't-prompt, floors upstream, two-pass, word budgets, ethics rails).
- E-263 Non-Goals record this deferral + the model-eval prerequisite; this idea is the tracked home so the gate isn't lost.
- Related: IDEA-079, IDEA-085 (LLM-narrative-adjacent).

---
Created: 2026-07-13
Last reviewed: 2026-07-13
Review by: 2026-10-11
