# IDEA-117: Scope multi-agent-patterns:24's bare "Never summarize" to the dispatch context block

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-05, context-layer truth & staleness).

## Summary
`.claude/skills/multi-agent-patterns/SKILL.md:24` reads "Pass original content at every relay point. Never summarize." Its next line (`:26`) correctly scopes it to the dispatch context block (Main Session → Implementing Agent: full story file text + full epic Technical Notes), but the bare `:24` sentence, read alone, looks like a blanket verbatim-relay mandate — the exact over-broad reading E-260 removed elsewhere. Scope `:24` to the dispatch context block in place, mirroring how E-260-04 scoped `context-fundamentals/SKILL.md:203`.

## Why It Matters
E-260 deleted the finding-relay verbatim mandate but deliberately RETAINED the dispatch-context-block verbatim mandate (passing the story file + Technical Notes to a spawned agent). `multi-agent-patterns:24` is that retained-class instruction — correct in substance, but its bare phrasing could be re-cited as license for the expensive live-agent relay E-260 exists to stop. Scoping it removes the ambiguity and keeps the context layer internally consistent with the E-260-04 treatment.

## Rough Timing
Low-urgency consistency cleanup. Whenever the context layer is next touched near this file, or a batch of E-260 follow-ups is picked up.

## Dependencies & Blockers
- [ ] None (pure prose scoping)

## Open Questions
- Delete vs. scope: a one-clause scope (as E-260-04 did at :203) is likely cleaner than deletion, since the dispatch-context-block intent is legitimate.

## Notes
Surfaced during E-260-01 AC-5 verification (PM independent grep). Ruled OUT of E-260-01 scope at the time (retained-class mandate, not an orphan of a deleted rule); captured here for a consistency pass. CA owns `.claude/skills/`.

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
