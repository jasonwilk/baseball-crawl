# IDEA-128: perspective-provenance.md public-scorebook caveats

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-05, context-layer truth & staleness).

## Summary
api-scout flagged two corrections to the `.claude/rules/perspective-provenance.md` "Perspective-Specific vs. Stable Fields" table during E-261 review: (1) the "Stable" row asserts scores are stable across perspectives, but two independently-kept public scorebooks of the same game CAN disagree by a run (E-261 observed 12-4 vs 12-5) — the row needs a public-scorebook caveat; (2) the "Uncertain: public games `id`" row should be promoted to definitively perspective-specific (post-E-239 the public path is the sole populator, where `event_id`/`id` is per-perspective, byte-identical to `game_stream_id`). Both are context-layer (rule) edits owned by claude-architect.

## Why It Matters
The rule is the canonical field-classification reference agents consult when assessing new endpoints or loaders. The stale "scores stable" classification directly contradicted an E-261 load-bearing fact and would mislead future dedup/aggregation work into trusting cross-perspective score equality. The "Uncertain" public-`id` row is now resolvable to a definite answer, removing a decision agents currently have to re-derive.

## Rough Timing
Low-urgency cleanup. Natural trigger: the next context-layer epic that touches `perspective-provenance.md`, or a claude-architect context-layer sweep. E-261 itself must NOT edit the rule (out of scope — it is a code bug-fix epic).

## Dependencies & Blockers
- [ ] None hard. E-261's live 12-4/12-5 observation is the evidence for correction (1); if a second independent observation lands, upgrade the caveat from "credible-but-single-observation" to a stated property.

## Open Questions
- Correction (1): phrase as a hard caveat ("public-scorebook scores may disagree by a run across perspectives") or keep it soft pending a second observation? (E-261's api-scout call was "credible-but-single-observation.")
- Does promoting the public `id` row to perspective-specific ripple into any other rule text that currently treats it as uncertain?

## Notes
Surfaced by api-scout during the E-261 (Cross-Perspective Game-Dedup Fidelity) Codex spec-review consultation, 2026-07-12. Relayed by the main session; captured here so the rule corrections are not lost. Related: E-261 Background Defect B (the 12-4/12-5 observation) and its History api-scout entry. claude-architect owns the eventual edit.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
