# IDEA-175: Consultation prompts should name the epic's team roster

## Status
`CANDIDATE`

## Summary
During E-274 planning, PM sent three domain consultations to `scout`, `coach`, and `SE` — the **retired E-272 instances** — instead of `scout2`, `coach2`, `SE2`, the agents actually on the E-274 team. Two of the retired instances were resumed by the messages and answered anyway; one never responded. The result was a stalled discovery round, two competing baseball-coach rulings that team-lead had to reconcile by hand, and an agent (`SE`) that reported it **had no way to know it was off-team** — the consultation read as an entirely normal request.

The proposed guard is `SE`'s own: **a consultation spawn or message prompt should name the epic's team roster**, so both sender and recipient can detect a mismatch.

## Why It Matters
The failure is **structural, not inattention**, which is what makes it worth a durable fix rather than a note to be more careful:

- **Agent-type names are reused across back-to-back epics.** `baseball-coach` is `coach` on one epic and `coach2` on the next. Nothing in an agent's own context tells it which epic's team it belongs to.
- **A resumed agent cannot self-detect the mismatch.** It has full prior context, the question is squarely in its domain, and answering is the cooperative thing to do. Every local signal says "respond."
- **The sender cannot see the roster either** unless someone tells them. PM had no list of team member names — the spawn happened in the main session.

The sharpest cost was not the delay. It was **two instances of one agent issuing independent domain rulings** with equal standing and no principled basis for preferring either. Here they happened to agree on everything substantive, and the retired instance even surfaced a safety item (`middle_*`/`elementary`/`college` must suppress) the current one had not addressed — so the accident was net-positive this time. That is luck, not a property of the mechanism. Had they diverged on a rest-rule call, PM would have had to adjudicate between two authorities it has no standing to rank.

## Rough Timing
Cheap and correct; promote whenever context-layer work is next being done, or immediately if a second collision occurs. The trigger to watch for: any epic planned within a short window of a prior epic that used the same agent types — which, given how this project sequences work, is close to every epic.

## Dependencies & Blockers
- [ ] None. Context-layer wording change; no code.

## Open Questions
- **Where does the roster belong?** Candidates: the spawn prompt (main session already knows the roster), the epic's `## Dispatch Team` section (already exists but lists agent *types*, not instance names), or a line in the consultation-mode convention in `.claude/rules/workflow-discipline.md`. The instance-name-vs-type distinction is the crux — `## Dispatch Team` saying "baseball-coach" does not disambiguate `coach` from `coach2`.
- **Should a resumed off-team agent refuse, or answer and flag?** Refusing risks a false negative that blocks legitimate work; answering-and-flagging is safer but does not prevent the competing-rulings problem, since two flagged answers are still two answers.
- Is there a cheaper structural fix — e.g. never reusing a bare agent-type name for a new instance, so the collision cannot occur? That moves the problem to naming discipline at spawn time, which is one place rather than every prompt.
- Does this interact with [[IDEA-161]] (main-session durable record surface)? Both concern orchestration state that exists only in the main session's head and is invisible to the agents affected by it.

## Notes
Surfaced by `SE` (the retired E-272 instance) during E-274 discovery, 2026-07-25, and endorsed by team-lead, who identified the root cause as spawning the new team without telling PM the names and called the collision foreseeable.

Worth recording alongside it: PM's handling was correct and is the behavior to preserve — when the consultations went unanswered, PM escalated to the main session under the Anti-Fabrication Rule (`.claude/rules/agent-team-compliance.md`, Pattern 3) rather than answering the rest-rule questions on the experts' behalf. The guard proposed here reduces how often that escalation is needed; it does not replace it.

Related: [[IDEA-161]] (orchestrator behavior leaves no durable trace), [[IDEA-173]] (dispatch send-cap instrumentation — same family of orchestration-mechanics gaps).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
