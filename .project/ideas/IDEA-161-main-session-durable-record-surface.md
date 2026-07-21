# IDEA-161: A durable record surface for the main session

## Status
`CANDIDATE`

## Summary
The main session (dispatch orchestrator) has no durable, repo-visible record surface for its own process behavior. Its only write target is its own memory directory; its decisions, escalations, and failures leave no trace in the epic record. When a main-session process failure occurs, it exists only in the operator's account — as happened with the E-267 over-escalation incident ("told twice to stop"), which the independent audit could NOT find anywhere in the repo (P-10, `.project/research/E-271-e267-audit-findings.md`).

## Why It Matters
P-10 has two halves. E-271's Autonomy Gate (item 2) addresses the DECISION-RULE half — it gives the main session a decide-first test so it stops over-escalating. But nothing closes the RECORD-SURFACE half: even with a decision rule, a main-session misstep still leaves no durable trace, so the next audit is again blind to it. Every other agent's behavior is inspectable (implementers via the diff, PM/CR via the epic and review artifacts); the orchestrator is the one role whose process is invisible after the fact.

## Why It Is an Idea, Not (Yet) an Epic
The mechanism is unscoped. Options span from lightweight (a per-epic orchestration-decision log appended to the epic History at closure) to heavier (a structured dispatch-event trail). Choosing one needs design — what to record, where it lives without bloating the epic, whether it rides the closure patch, and how it avoids becoming ceremony that manufactures false confidence (the exact E-267 failure). It also brushes the context-ratchet / meta-freeze boundary. Not ready for testable ACs.

## Timing / Blockers
- No hard blocker. Revisit after E-271 lands (its Autonomy Gate is the decision-rule complement) and after at least one dispatch runs under the new gate, so a real "what would we have wanted recorded" example exists rather than a hypothetical.

## Open Questions
- What is the minimum record that would have made the E-267 over-escalation incident visible to the audit?
- Does it live in the epic History (operator-visible, rides the closure patch) or a separate trail?
- How does it avoid becoming the false-confidence ceremony the E-271 redesign is removing?

## Notes
- Source: CR spec-audit finding S-2 on E-271 (2026-07-21) — the P-10 citation must not be read as full closure; the record-surface half is explicitly out of E-271's scope (epic TN-3).
- Related: E-271 (Autonomy Gate = the decision-rule half); P-10 in `.project/research/E-271-e267-audit-findings.md`.

---
Created: 2026-07-21
Last reviewed: 2026-07-21
Review by: 2026-10-19
