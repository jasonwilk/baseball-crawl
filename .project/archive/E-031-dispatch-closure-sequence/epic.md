# E-031: Dispatch Closure Sequence

## Status
`COMPLETED`

## Overview
Codify a mandatory closure sequence for every epic dispatch so that no team is spun down until all work is validated, all statuses are updated, the epic is archived, and a summary is presented to the user. Today the closure step is a single sentence ("shut down teammates and delete the team") which leaves room for incomplete state updates and missing user communication.

## Background & Context
The dispatch pattern (`/.claude/rules/dispatch-pattern.md`) and PM agent definition (`/.claude/agents/product-manager.md`) both describe dispatch closure in minimal terms. In practice, the PM should perform a complete closure sequence before spinning down the team:

1. Validate all story acceptance criteria are met.
2. Update all story statuses, epic status, and History entries.
3. Archive the epic (move from `/epics/` to `/.project/archive/`).
4. Present a clear summary of all changes to the user.
5. After the team is spun down, the system should offer to run the PII scan and commit -- but must NOT commit until the user explicitly approves.

There is also a practical constraint: the PM has no Bash tool and cannot move directories. The closure sequence must account for this by having the PM request archive operations from an implementing agent (or note the limitation for the system layer to handle).

No expert consultation required -- this is a PM-domain workflow refinement affecting only process documentation files.

## Goals
- Every epic dispatch ends with a complete, predictable closure sequence
- The user always receives a summary of what was done before the team disappears
- Archive happens before team shutdown, not after (prevents orphaned epic directories in `/epics/`)
- Commit is never automatic -- user must approve

## Non-Goals
- Changing how stories are dispatched or executed (only the closure step changes)
- Adding new tooling or hooks (this is documentation/process only)
- Changing the archive enforcement hook (E-024) -- that remains a safety net; this makes the PM do it proactively

## Success Criteria
- `dispatch-pattern.md` contains a detailed closure sequence (not a one-liner)
- `product-manager.md` Dispatch Procedure step 11 is expanded to match
- Both files agree on the same closure steps
- The closure sequence addresses: validation, status updates, archiving, user summary, and commit offer

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-031-01 | Expand dispatch closure in rules and PM definition | DONE | None | claude-architect |

## Technical Notes

### Files to Modify
1. `/.claude/rules/dispatch-pattern.md` -- "The Dispatch Flow" step 9
2. `/.claude/agents/product-manager.md` -- "Dispatch Procedure" step 11

### Closure Sequence (Canonical)
The following is the closure sequence that both files must describe. The implementing agent should use this as the source of truth for the content to write.

**Before spinning down the team:**

1. **Validate all work.** For every story in the epic, verify that all acceptance criteria are met. If any criteria are unmet, send the implementer back with specific feedback -- do not proceed to closure until all stories are verified DONE.

2. **Update the epic completely.**
   - All story file statuses updated to `DONE` (already done incrementally, but confirm).
   - Epic Stories table reflects current reality (all rows `DONE`).
   - Epic status updated to `COMPLETED`.
   - History entry added with the completion date and a summary of what was accomplished.
   - Record any notable implementation details, decisions, or deviations in the epic's Technical Notes or History. Keep sensitive information (credentials, tokens, secrets) OUT of epic files.

3. **Archive the epic.** Move the entire epic directory from `/epics/E-NNN-slug/` to `/.project/archive/E-NNN-slug/`. Since the PM has no Bash tool, the PM must request this move from an implementing agent still on the team (before shutting them down), or note the move for the system to execute. The archive must happen before team shutdown.

4. **Update PM memory.** Move the epic from "Active Epics" to "Archived Epics" in MEMORY.md. Note any follow-up work or newly unblocked items.

5. **Review ideas backlog.** Check `/.project/ideas/README.md` for CANDIDATE ideas that may now be unblocked or promoted by the epic's completion.

6. **Present a summary to the user.** Before ending the dispatch, present a clear summary including:
   - Epic ID and title
   - List of stories completed (with brief descriptions)
   - Key artifacts created or modified
   - Any follow-up work identified
   - Any ideas that may now be promotable

**After the team is spun down:**

7. **Offer to scan and commit.** The system (or user-facing agent) should offer to run the PII scan and commit the changes. It must NOT auto-commit -- the user must explicitly approve before any commit happens.

### How This Relates to Existing Content
- The "Completing an epic" checklist in the Atomic Status Update Protocol already covers steps 1-5 conceptually. The dispatch closure sequence makes these explicit in the dispatch flow and adds step 6 (user summary) and step 7 (commit offer).
- The dispatch-pattern.md "Dispatch Flow" step 9 currently says: "When all stories are done, PM marks the epic `COMPLETED`, shuts down teammates, and deletes the team." This must be expanded into the full closure sequence.
- The product-manager.md Dispatch Procedure step 11 currently says: "When all stories are done, follow the 'Completing an epic' checklist in the Atomic Status Update Protocol. Then shut down teammates and delete the team." This must be expanded to include the user summary and commit offer steps.

## Open Questions
- None. The closure sequence is well-defined and the files to modify are clear.

## History
- 2026-03-03: Created. Single-story epic to codify dispatch closure sequence.
- 2026-03-03: COMPLETED. E-031-01 implemented by claude-architect. dispatch-pattern.md step 9 replaced with a 7-step Closure Sequence (steps 9-15). product-manager.md Dispatch Procedure step 11 expanded to sub-steps 11a-11g with the same sequence. Both files are consistent, address the no-Bash-tool constraint, and mandate user approval before commit.
