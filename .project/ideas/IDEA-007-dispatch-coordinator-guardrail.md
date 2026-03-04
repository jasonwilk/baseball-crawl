# IDEA-007: Dispatch Coordinator Guardrail -- Prevent Team-Lead-as-PM Bypass

## Status
`CANDIDATE`

## Summary
Add an explicit rule preventing the team lead (or any non-PM agent) from creating dispatch teams and marking stories IN_PROGRESS directly. The PM must always be the first agent spawned in a dispatch, and it must be the one to create the team and dispatch implementers.

## Why It Matters
During E-037 dispatch, the team lead bypassed the PM by directly creating the dispatch team, marking all four stories IN_PROGRESS, and spawning implementing agents. The PM was only brought in after the fact as a verification agent rather than as the standing coordinator from the start. This violates the dispatch-pattern.md contract where PM is the coordinator throughout the full lifecycle.

The consequences of this bypass:
- PM loses visibility into the dispatch setup phase (story eligibility checks, READY gate verification, dependency validation)
- Status updates may be made without the PM's atomic update protocol (story file + epic table + memory)
- The "telephone game" problem re-emerges: the team lead is relaying context that should flow directly from PM to implementers
- If the team lead misroutes a story (e.g., context-layer story to general-purpose), the PM has no chance to catch it

## Rough Timing
Promote when the next multi-story dispatch is planned. This is a low-cost fix (rule file update) with high value for workflow correctness.

## Dependencies & Blockers
- [ ] None -- this is a process/rule change, not a code change

## Open Questions
- Should the guardrail be a rule file update to `dispatch-pattern.md` and/or `workflow-discipline.md`, or a new standalone rule?
- Should it be reinforced in the team lead's own instructions (if any exist), or is the dispatch-pattern.md rule sufficient?
- Is there a way to make this structurally enforced (e.g., team creation only via PM) vs. just documented?

## Notes
- Root cause from E-037: team lead acted as PM instead of spawning PM first. The fix is to make explicit that "start epic E-NNN" from the user should result in: user -> team lead -> spawn PM -> PM creates team and dispatches. The team lead's role is to relay the user's intent to PM, not to execute the dispatch itself.
- Related: E-015 (Fix Agent Dispatch) established the dispatch pattern. This idea strengthens the enforcement of that pattern.
- Likely a single-story epic routed to claude-architect (context-layer files).

---
Created: 2026-03-04
Last reviewed: 2026-03-04
Review by: 2026-06-02
