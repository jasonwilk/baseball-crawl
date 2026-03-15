# E-111: Closure Archive Verification Gate

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add a git-status verification gate after the archive move in the closure sequence, ensuring that both the new files in `/.project/archive/` AND the deletions from `/epics/` are staged before proceeding to team teardown. This prevents ghost unstaged deletions from persisting across conversations.

## Background & Context
During E-109 closure, the epic directory was moved from `epics/E-109-tmux-rename-all-sessions/` to `.project/archive/E-109-tmux-rename-all-sessions/`, and the archive copies were committed. However, the **deletions of the source files from `epics/`** were never staged or committed. This left ghost unstaged deletions in the working tree that persisted across conversations until noticed manually. The same pattern occurred with E-108 (uncommitted modifications sitting in the working tree).

Root cause: the closure sequence (Step 4 in implement SKILL.md / step 13 in dispatch-pattern.md) instructs an implementer to move files, but does not require verification that the move produced a clean working tree. The commit step happens after team teardown (Step 10 / step 19), by which point uncommitted changes can be missed or bundled incorrectly.

No expert consultation required -- the problem, root cause, and affected files are fully understood from the incident. The fix is a targeted addition to existing closure sequence steps, not an architectural change. The implementing agent (claude-architect) owns these files and will determine the right wording and placement.

## Goals
- The archive move step includes a verification gate that confirms both additions and deletions are staged.
- The main session cannot proceed past the archive step with a dirty working tree related to epic files.

## Non-Goals
- Overhauling the closure sequence broadly.
- Moving the commit step earlier (it correctly stays after team teardown for user approval).
- Adding automated commits (the user must still approve commits explicitly).

## Success Criteria
- After applying this epic's changes, a main session following the closure sequence will detect and stage any unstaged archive-related changes before proceeding past the archive step.
- The verification is documented in both `dispatch-pattern.md` and `implement/SKILL.md` so agents following either reference catch the issue.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-111-01 | Add archive verification gate to closure sequence | DONE | None | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Problem Pattern
The archive move (`mv epics/E-NNN-slug/ .project/archive/E-NNN-slug/`) produces two classes of git changes:
1. **New files** in `.project/archive/E-NNN-slug/` (the destination).
2. **Deleted files** in `epics/E-NNN-slug/` (the source).

If the move is done with `mv` (or equivalent), both classes appear as unstaged changes. The implementer or main session may `git add` only the new files (or only the directory they moved TO), leaving the deletions unstaged. The subsequent commit captures the additions but not the deletions.

### Fix Approach
After the archive move, the closure sequence should require verification that `git status` shows no unstaged changes related to the epic directory (both source and destination). The specific mechanism (e.g., `git add` of both paths, `git status --porcelain` check, or explicit `git mv`) is for the implementing agent to determine. The key contract is: the main session must not proceed past the archive step with unstaged epic-related changes.

### Files to Update
Both documents contain the archive step and must be updated consistently:
- `/.claude/rules/dispatch-pattern.md` -- Step 13 (the numbered closure steps) and the Closure Sequence subsection.
- `/.claude/skills/implement/SKILL.md` -- Phase 5 Step 4 and the Workflow Summary diagram.

### Consistency Requirement
The two files describe the same closure sequence from different perspectives (dispatch-pattern.md is the canonical model; implement SKILL.md is the procedural reference). The verification gate must appear in both, using consistent language and the same verification contract.

## Open Questions
None.

## History
- 2026-03-15: Created. Motivated by E-109 and E-108 closure artifacts (unstaged deletions persisting across conversations).
- 2026-03-15: COMPLETED. E-111-01 added archive verification gate to both `dispatch-pattern.md` (step 13) and `implement/SKILL.md` (Phase 5 Step 4). Fix prescribes `git mv` for atomic staging and `git status --porcelain` verification before proceeding. Documentation assessment: no impact (context-layer process files only). Context-layer assessment: (1) new convention — no, (2) architectural decision — no, (3) footgun discovered — yes (codified in this epic's deliverable), (4) agent coordination change — yes (codified in this epic's deliverable), (5) domain knowledge — no, (6) new CLI/workflow — no. No additional codification needed.
