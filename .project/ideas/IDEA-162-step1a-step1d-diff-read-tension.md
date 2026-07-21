# IDEA-162: Reconcile the Step-1a vs Step-1d diff-read tension in the implement skill

## Status
`CANDIDATE`

## Summary
The implement skill's closure passes disagree on whether the main session may read the diff. Step 1a (~`.claude/skills/implement/SKILL.md:408`) treats "is there a NOT NULL / FK migration in the diff?" as a decision the main session evaluates; Step 1d (~:470) routes a diff-stat read through the main session as a domain-work violation (it must go to a reviewer). Both cannot be the rule: either the main session may read the diff for a mechanical fact or it may not.

## Why It Matters
`dispatch-pattern.md:27` classifies diff/grep inspection as ROUTED domain work — the main session is barred from reading source to verify claims. Step 1d honors that; Step 1a's permissive reading contradicts it. E-271's Autonomy Gate (item 2) deliberately takes the conservative side (field reads permitted, diff reads routed to CR) and does NOT resolve this pre-existing tension — the gate simply must not lean on Step 1a's permissive reading. Left unreconciled, the two passes give a future implementer conflicting guidance about the same action.

## Why It Is an Idea, Not Part of E-271
Not P-cited: it is a pre-existing inconsistency the E-267 audit did not flag, so it falls outside E-271's defect-cited meta-freeze scope (surfaced by claude-architect during the E-271 Codex triage, 2026-07-21). Resolving it means choosing which pass is right (likely Step 1d — diff reads route to CR, consistent with dispatch-pattern.md and E-271's Autonomy Gate) and rewording the other, which is its own small context-layer change that should cite this as its defect once picked up.

## Timing / Blockers
- No hard blocker. Natural to fold into a future context-layer hygiene pass, or to pick up right after E-271 lands (E-271's Autonomy Gate establishes the field-read-vs-diff-read line this reconciliation would extend to Step 1a).

## Notes
- Source: claude-architect design review during E-271 Codex triage (2026-07-21) — flagged OUT of E-271 scope, endorsed as an idea by the operator-facing session.
- Related: E-271 item 2 (Autonomy Gate — the field-read-vs-diff-read boundary this would extend), `.claude/rules/dispatch-pattern.md:27` (the barred-domain-work principle).

---
Created: 2026-07-21
Last reviewed: 2026-07-21
Review by: 2026-10-19
