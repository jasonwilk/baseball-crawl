# IDEA-027: Unified Team Lifecycle

## Status
`CANDIDATE`

## Summary
Refinement and dispatch should use the same team with no teardown between phases. Agents come online for consultation during refinement, then the same team dispatches implementation, reviews code, and handles follow-up fixes -- all in one continuous session. The current separation between "refinement team" and "dispatch team" creates unnecessary overhead and context loss.

## Why It Matters
The current model creates two team lifecycles per epic: one for refinement (ad-hoc consultation spawns) and one for dispatch (implement skill team creation). This means:
- Agents consulted during refinement lose their context when the team is torn down
- The dispatch team starts cold, re-reading epic files that refinement agents already internalized
- Follow-up routing is awkward: if code-reviewer finds a context-layer problem, there's no clean path to dispatch it to claude-architect within the same team

A unified lifecycle (consult → refine → dispatch → review → fix) keeps agents warm across all phases and enables natural follow-up routing.

## Rough Timing
After E-112 (context layer optimization) is complete. E-112 establishes the implement skill as the single source of truth for dispatch procedures -- a unified lifecycle would extend that skill with a refinement phase.

## Dependencies & Blockers
- [ ] E-112 must be complete (implement skill is the dispatch procedure source of truth)
- [ ] Need to understand interaction with `workflow-discipline.md`'s Dispatch Authorization Gate (currently assumes planning and dispatch are separate user actions)
- [ ] Need to understand interaction with the consultation mode constraint (agents transition from consultation to implementation within the same team)

## Open Questions
- How does the Dispatch Authorization Gate work when the team is already running? The user still authorizes dispatch explicitly, but the team doesn't need to be created -- it's already active.
- How do agents transition from consultation mode to implementation mode? The consultation mode constraint is activated by a phrase in the spawn prompt -- but the agent is already spawned.
- Should the implement skill gain a "Phase -1: Refinement" that handles expert consultation before dispatch? Or should this be a separate skill that chains into the implement skill?
- What happens to the team if the user pauses between refinement and dispatch (e.g., overnight)? Agent context windows may fill or sessions may time out.

## Notes
- User feedback (2026-03-15): "Refinement and dispatch use the same team; no teardown between phases."
- The E-112 validation session demonstrated the pain: CA was consulted during refinement, but decisions were initially routed through PM instead of directly to CA. A unified team with clear decision routing would have prevented this.
- Related to the Decision Routing table being added to `agent-routing.md` in E-112-03 -- that table documents *who owns which decisions*, which is a prerequisite for correct routing within a unified team.

---
Created: 2026-03-15
Last reviewed: 2026-03-15
Review by: 2026-06-15
