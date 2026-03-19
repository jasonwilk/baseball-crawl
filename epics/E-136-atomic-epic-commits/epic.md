# E-136: Atomic Epic Commits

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Replace the current multi-commit dispatch workflow (implementer commits + merge commits per story) with a single atomic commit per epic. Implementers stage but do not commit, merge-back uses patch-apply instead of git merge, and closure produces one commit containing all epic changes.

## Background & Context
During epic dispatch, implementers commit multiple times in their worktrees (initial commit, review fix commits), and merge-back creates merge commits via `git merge --no-ff`. This results in many commits for a single epic. The user wants ONE atomic commit for the entire epic -- all code, all artifacts, one commit.

CA previously designed and implemented these changes (subsequently reverted because the user wanted a proper epic). CA's design used file-copy (cp/rm based on `## Files Changed` manifest) for merge-back. SE consultation identified `git diff --binary` + `git apply` as a cleaner mechanism that handles permissions, symlinks, binary files, and deletions atomically. Both CA and SE agree implementers should `git add -A` (stage everything) but NOT commit, enabling `git diff --cached main` for code review.

**Expert consultation completed:**
- **claude-architect**: Confirmed file-copy approach feasibility, recommended `git add -A` staging convention for implementers, identified `git checkout -- . && git clean -fd` as recovery mechanism.
- **software-engineer**: Recommended `git diff --binary main > changes.patch` + `git apply changes.patch` over cp/rm for merge-back. Identified `git diff --cached main` as the correct review diff command. Flagged symlink/permission concerns with cp-based approaches.

## Goals
- Every dispatched epic produces exactly one commit containing all story changes
- Implementers work in worktrees without committing, preserving isolation
- Code review works on staged (uncommitted) changes via `git diff --cached`
- Merge-back uses patch-apply for correct handling of all file operations
- PII scanning covers all changes in one pass at closure

## Non-Goals
- Changing the worktree isolation model (implementers still get isolated worktrees)
- Changing the code-reviewer's review rubric or AC verification process
- Changing how context-layer-only stories (no worktree) are handled during dispatch
- Per-story commit messages or commit metadata preservation
- Squash-merge or rebase workflows

## Success Criteria
- The implement skill describes the atomic commit workflow end-to-end
- Implementers are told to stage (`git add -A`) but not commit
- Code-reviewer instructions use `git diff --cached` instead of `git diff main..HEAD`
- Merge-back uses `git diff --binary` + `git apply` instead of `git merge --no-ff`
- Closure produces a single commit with user approval
- Worktree isolation rules prohibit `git commit`
- Dispatch pattern overview reflects the new approach

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-136-01 | Update implement skill for atomic commits | TODO | None | - |
| E-136-02 | Update dispatch pattern overview | TODO | None | - |
| E-136-03 | Add no-committing prohibition to worktree isolation | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Implementer Staging Convention
Implementers run `git add -A` to stage all changes (new files, modifications, deletions) but do NOT run `git commit`. This makes all changes visible via `git diff --cached` while keeping HEAD pointing at main. The `## Files Changed` manifest in the implementer's completion report remains the authoritative scope for review.

### TN-2: Code Review Diff Command
The code-reviewer runs `git diff --cached` from the worktree to see all staged changes. For comparison against main specifically: `git diff --cached main`. This replaces `git diff main..HEAD` which shows nothing when there are no commits. New files are visible because they are staged. The `## Files Changed` manifest cross-references the diff output.

### TN-3: Merge-Back via Patch-Apply
Replace `git merge --no-ff <branch>` with a patch-apply sequence:

1. **In the worktree**: `git diff --binary --cached main > /tmp/E-NNN-SS.patch`
2. **In the main checkout**: `git apply /tmp/E-NNN-SS.patch`
3. **On success**: Remove the worktree (`git worktree remove <path>`), delete the branch (`git branch -D <branch>`). Do NOT stage yet -- changes accumulate unstaged in the main checkout until closure.
4. **On failure** (conflict): The story remains IN_PROGRESS. The worktree stays active. Escalate to the user with conflict details. Recovery in main checkout: `git checkout -- . && git clean -fd` to reset, then retry after conflict resolution.

Key properties of `git diff --binary`:
- Handles new files, modifications, deletions, and renames
- Preserves file permissions (executable bits)
- Handles binary files (images, compiled assets)
- Handles symlinks correctly
- Purpose-built for this exact use case

### TN-4: Closure Atomic Commit
After all stories are DONE and all assessments complete (documentation, context-layer), the closure sequence produces ONE commit:

1. `git add -A` to stage all accumulated changes
2. Run PII scanner on staged files (pre-commit hook covers this)
3. Present the commit to the user for approval
4. `git commit` with a conventional commit message: `feat(E-NNN): <epic title>`

The user must explicitly approve before commit. If PII scan catches issues, nothing is committed -- the atomic approach makes this safer than partial commits.

### TN-5: Worktree Cleanup Changes
Since implementers do not commit:
- No branches to merge (worktree branches have no commits beyond main)
- `git branch -D` (force delete) replaces `git branch -d` (safe delete) since branches are unmerged
- Worktree removal is the same: `git worktree remove <path>`
- Closure worktree verification checks that no worktrees remain, not that branches are merged

### TN-6: Context-Layer Story Handling
Context-layer-only stories (no worktree isolation) are unaffected by the merge-back changes. They run in the main checkout, and their changes accumulate there naturally. The atomic commit at closure captures them alongside worktree story changes.

### TN-7: What Does NOT Change
- Worktree isolation model (implementers still get isolated worktrees)
- Story assignment and context blocks (except the commit prohibition)
- Code-reviewer rubric and PM AC verification process
- Phase 4 optional review chain
- Documentation and context-layer assessments
- Epic archival process

## Open Questions
None -- all questions resolved via CA and SE consultation.

## History
- 2026-03-19: Created. Replaces abandoned E-135 (which was abandoned because the user wanted a proper epic, not a direct CA fix). CA and SE consultation completed via team-lead relay.
