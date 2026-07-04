# E-251-03: Remove software-engineer.md status-ownership contradiction

## Epic
[E-251: Dispatch-Machinery Repair](../E-251-dispatch-machinery-repair/epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/agents/software-engineer.md` no longer instructs the SE to update story statuses, resolving its self-contradiction. The file becomes internally consistent with the never-own-statuses rule stated later in the same file and in the agent ecosystem (PM owns status transitions during dispatch).

## Context
This is an audit §2 MEDIUM finding. The SE definition contradicts itself: an early work-procedure section (audit cites ~L80-81, "steps 5-6") tells the SE to update story statuses, while a later section (~L157) and the agent-ecosystem rule both say implementers NEVER own status transitions. During dispatch the PM is the status owner (see `.claude/agent-memory/product-manager/feedback_pm_owns_statuses.md`). The contradiction can cause an SE to flip statuses that the PM owns. Per epic TN-4.

## Acceptance Criteria
- [ ] **AC-1**: `.claude/agents/software-engineer.md` contains no instruction directing the SE to set, update, or transition story or epic statuses (the audit-identified steps 5-6 of the work procedure are removed).
- [ ] **AC-2**: The file is internally consistent: the surviving text agrees with the later never-own-statuses statement (~L157) and with the agent-ecosystem convention that PM owns statuses during dispatch. No dangling reference points at a deleted step, and any step numbering left by the removal is corrected.
- [ ] **AC-3**: No SE responsibility that is legitimately the SE's (implementation, testing, completion reporting to the main session / PM) is accidentally removed — only the status-ownership instruction is excised.

## Technical Approach
Per epic TN-4. CA locates the status-update steps in the work procedure and deletes them, fixing any resulting step numbering, and confirms the remaining text is consistent with the never-own-statuses rule elsewhere in the file. Guidance, not mandate on exact wording — CA owns the edit.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agents/software-engineer.md` — delete the story-status-update steps; reconcile numbering and surrounding prose

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Self-contained fix (audit file is uncommitted). Audit ref: §2 MEDIUM "software-engineer.md contradicts itself on story-status ownership" (L80-81 vs L157); §5 Quick Wins ("delete SE Work-Authorization steps 5-6").
