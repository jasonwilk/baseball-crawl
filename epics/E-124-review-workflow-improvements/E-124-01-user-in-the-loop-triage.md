# E-124-01: User-in-the-Loop Finding Triage

## Epic
[E-124: Review Workflow Improvements](epic.md)

## Status
`TODO`

## Description
After this story is complete, the main session will present each finding it intends to dismiss to the user with a plain-English explanation, and wait for user confirmation before closing it. Findings the main session intends to accept/fix will proceed immediately to the implementer without waiting. This gives the user visibility and veto power over dismissals while not slowing down the fix cycle.

## Context
During dispatch, the main session triages SHOULD FIX findings (Phase 3, Step 5, item 3 of the implement skill). Currently, dismissals happen silently with only a one-line reason recorded. The user wants to weigh in on every dismissal decision while accepted findings continue flowing immediately.

## Acceptance Criteria
- [ ] **AC-1**: The implement skill's triage procedure (Phase 3, Step 5, item 3) describes two tracks: an accept track (routed to implementer immediately, no user wait) and a dismiss track (presented to user with reasoning, requires user confirmation before closing), per Technical Notes TN-2.
- [ ] **AC-2**: The triage procedure specifies that if the user vetoes a dismissal, the finding moves to the accept track and is routed to the implementer.
- [ ] **AC-3**: The workflow summary diagram in the implement skill reflects the user-confirmation step for dismissals.
- [ ] **AC-4**: No other triage behavior is changed -- MUST FIX findings still route to the implementer unconditionally, and the circuit breaker is unaffected.

## Technical Approach
The implement skill's Phase 3, Step 5, item 3 currently describes a binary accept/dismiss decision made entirely by the main session. This story changes the dismiss path to require user confirmation. The accept path is unchanged. The workflow summary ASCII diagram at the end of the skill also references triage and should reflect the new user-confirmation step.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (Phase 3, Step 5 item 3; workflow summary diagram)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing skill structure
- [ ] Code follows project style (see CLAUDE.md)

## Notes
The user's exact words: "For each finding that you intend to dismiss/defer, please tell me why in plain english and let me weigh in. For findings that you intend to accept/fix, go ahead and proceed."
