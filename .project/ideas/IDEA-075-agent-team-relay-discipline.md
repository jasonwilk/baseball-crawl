# IDEA-075: Agent-Team Relay Discipline

## Status
`CANDIDATE`

## Summary
Codify the peer-DM-drop failure mode and the recovery patterns into context-layer rules so the next multi-agent planning team does not re-learn them in real time. Promote "main-session relay only for substantive content" from a default to a hard rule, document the discipline patterns we exercised in E-228 planning (sanity-check inbox vs. live task list before going idle, "ACK FIRST" framing on assignments, tasks-are-the-recovery-channel), and consider whether the plan skill should switch its default assignment channel from SendMessage to TaskCreate.

## Why It Matters
During E-228 planning the peer-to-peer SendMessage relay dropped at least 6 messages in both directions across PM and the main session. PM silently dismissed live iteration-2 assignments as stale echoes; the main session lost PM's responses without realizing it. The user had to intervene with manual hand-relay to get the epic to READY. `.claude/rules/dispatch-pattern.md` already says "main-session relay is the default channel for substantive content; peer-to-peer SendMessage is reserved for lightweight acknowledgments only" — but it is framed as a default, not a hard rule, and the discipline patterns we discovered (sanity-check vs. task list, ack-first framing, tasks as the recovery channel) live only in PM's agent memory (`feedback_relay_dropouts_no_silent_fail.md`) where they help PM but no other agent. The next complex planning team will hit the same wall unless the patterns are promoted to context-layer rules.

## Rough Timing
Before the next multi-agent planning team is spawned. E-228 is the only epic that exercised this in its full form recently; the lesson is freshest now. If we wait until the next planning epic surfaces the same failure, the cost is another mid-session intervention.

## Dependencies & Blockers
- [ ] None. This is a pure context-layer change owned by claude-architect — `.claude/rules/dispatch-pattern.md`, possibly `.claude/skills/plan/SKILL.md`, possibly a new rule under `.claude/rules/`.

## Open Questions
- Should "main-session relay only for substantive content" be promoted from a default to a hard MUST in `dispatch-pattern.md`, or should we keep peer DM allowed for ack-class messages and just add the discipline patterns around silent-fail and recovery?
- Should the plan skill's default channel for assignment hand-offs flip from SendMessage to TaskCreate? Tasks reached PM reliably even when DMs dropped; SendMessage assignments did not. This affects the plan skill's Phase 2/3/4 routing.
- How do we structurally enforce "never silent-fail on inbox state" — is it a rule load on every agent (`paths: "**"`) or a one-liner in the agent-team-compliance rule, or both?
- Does the "ACK FIRST" framing belong in the plan skill (only matters in planning) or in a broader rule (applies to every SendMessage that carries an assignment)?
- Is the same failure mode present in dispatch (the implement skill) or only in planning? E-228 only exercised planning. We may want claude-architect to do a parallel pass on the implement skill before the next dispatch.

## Notes
PM saved the discipline learnings to its own agent memory during E-228 (`.claude/agent-memory/product-manager/feedback_relay_dropouts_no_silent_fail.md`, committed in c0e4fb8). That file is the most concrete artifact we have of the failure mode and the recovery pattern — start the epic by reading it. Memory updates help PM only; this idea is about promoting the patterns to context-layer rules so all agents benefit.

Real-time evidence captured during E-228 planning, all in this session's transcript: PM dismissed live iteration-2 task-assignment events as duplicates of iteration-1 (silent-fail #1); main session's CX-1/CX-2/CX-5 resolution to PM appeared to land but PM kept asking for it (silent-fail #2); PM's CX-5 close-out arrived at the main session but a follow-up did not (drop #3); the (B) Pre-generate assignment had to be re-sent four times across SendMessage and TaskCreate before PM acted on it (drops #4-#7). Hand-relay by the user is what unblocked closure.

Related: E-227 (Closure Workflow Structural Remediation) called out a similar dispatch-degraded state in its History — claude-architect, software-engineer, and PM all entered broken states (silent idle or corrupted output) and the main session had to "limp through" under explicit user authorization. The recovery pattern from E-227 was ad-hoc; this idea is about codifying the pattern so the next time is structural, not heroic.

When promoted, the epic likely has 1-2 stories: one updating `.claude/rules/dispatch-pattern.md` + possibly a new top-level rule, and one updating `.claude/skills/plan/SKILL.md` (channel-default review). Code-reviewer should audit the changes against the actual transcript from this session to verify the patterns codified match the failure modes observed.

---
Created: 2026-05-15
Last reviewed: 2026-05-15
Review by: 2026-08-13 (90 days)
