# E-137: Epic-Level Worktree Isolation

## Status
`COMPLETED`

## Overview
Isolate each dispatched epic's changes into a dedicated git worktree so that story merge-back, code review, and atomic commits are scoped to exactly the current epic's changes. Today, all story patches accumulate in the shared main checkout, contaminating commits with unrelated files from PM planning, stale artifacts, and cross-story bleed.

## Background & Context
Evidence from git history shows structural contamination in every dispatch:

- **Commit `8b1a59d` (E-127-04)**: A ~5-file nav template story swept in 4 E-100 codex review files + `key_extractor.py` from parallel story E-127-02. 25 files changed.
- **Commit `c73b6dc` (E-130)**: Swept in 4 E-136 story/epic files from concurrent PM planning work. Commit message admits: "Also includes: E-136 epic spec."

Three contamination vectors exist in the current design:
1. **Intra-epic story cross-contamination**: Story patches land in the main checkout during Phase 3. The closure `git add -A` captures everything, including stale patches from earlier stories.
2. **PM planning pollution**: PM runs without worktree isolation, writing epic/story files to the main checkout during dispatch. These files get swept into whichever epic's commit happens next.
3. **Stale working tree artifacts**: Codex review artifacts, research files, or detritus from prior interactions accumulate and get captured.

The root cause: `git add -A` at closure has no mechanism to scope to "only this epic's files." An epic-level worktree provides that scope structurally.

This epic also simplifies the review finding triage model per user feedback: all valid findings get fixed regardless of size, and the only valid dismissal reason is that a finding is incorrect (false positive, misunderstanding, or targets untouched code).

Expert consultation: claude-architect (context-layer architecture), software-engineer (git mechanics validation), data-engineer (migration serialization).

## Goals
- Every dispatched epic's atomic commit contains exactly and only that epic's changes
- Story merge-back targets the epic worktree, not the shared main checkout
- Code review (per-story CR and post-epic codex review) sees only the current epic's diff
- Triage model simplified: fix all valid findings regardless of size; dismiss only invalid findings (false positives, misunderstandings, untouched code)
- PM planning and other main-checkout activity never contaminates epic commits

## Non-Goals
- Parallel epic dispatch across multiple sessions (enabled as a bonus, not the primary goal)
- Full dispatch pipeline automation (Epic E-138)
- Changes to per-story worktree creation (Agent tool `isolation: "worktree"` is unchanged)
- Schema or application code changes

## Success Criteria
- A dispatched epic's closure commit contains no files outside that epic's story scope
- PM writing to `epics/` during dispatch does not appear in the epic's diff
- Codex review run against the epic worktree sees only that epic's changes
- The triage model has no "correct but not worth fixing" category -- valid findings are fixed regardless of size; only invalid findings are dismissed

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-137-01 | Epic worktree lifecycle + triage simplification | DONE | None | - |
| E-137-02 | Update dispatch-pattern rule | DONE | E-137-01 | - |
| E-137-03 | Update worktree-isolation rule | DONE | E-137-01 | - |
| E-137-04 | Update workflow-discipline rule | DONE | E-137-01 | - |
| E-137-05 | Update code-reviewer agent definition | DONE | E-137-01 | - |
| E-137-06 | Update PM agent definition | DONE | E-137-01 | - |
| E-137-07 | Update codex-review skill | DONE | E-137-01 | - |
| E-137-08 | Context-layer story exception documentation | DONE | E-137-01 | - |
| E-137-09 | Context-layer hygiene review | DONE | E-137-02, E-137-03, E-137-04, E-137-05, E-137-06, E-137-07, E-137-08 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Platform Constraint — Agent Tool Worktrees
The Agent tool's `isolation: "worktree"` parameter creates worktrees that always branch from the repository's main HEAD. This is a platform feature — we cannot make story worktrees branch from the epic worktree. Story worktrees continue to branch from main. The epic worktree is created manually via `git worktree add` at dispatch start, and story patches are applied to it (not to the main checkout) during merge-back.

### TN-2: Epic Worktree Conventions
- **Path**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (e.g., `/tmp/.worktrees/baseball-crawl-E-137/`)
- **Branch**: `epic/E-NNN` (e.g., `epic/E-137`)
- **Created**: Phase 2, before team creation. `git worktree add /tmp/.worktrees/baseball-crawl-E-NNN epic/E-NNN`
- **Destroyed**: Phase 5, after merge-to-main succeeds. `git worktree remove <path> && git branch -D epic/E-NNN`
- The main session stores the epic worktree path and passes it to PM and code-reviewer in their spawn context.

### TN-3: Story Merge-Back Target Change
Current: `cd /workspaces/baseball-crawl && git apply --3way /tmp/E-NNN-SS.patch`
New: `cd /tmp/.worktrees/baseball-crawl-E-NNN && git apply --3way /tmp/E-NNN-SS.patch`

Story patches are generated identically (`git diff --binary --cached main > patch`). Only the apply target changes. After applying, stage in the epic worktree: `cd <epic-worktree> && git add -A`.

### TN-4: Closure Merge Sequence
Replaces the current `git add -A && git commit` in Phase 5 Step 10:

1. In epic worktree: `cd <epic-worktree> && git add -A` (stage all accumulated story patches)
2. Generate epic patch: `git diff --binary --cached main > /tmp/E-NNN-epic.patch`
3. Dry-run in main checkout: `cd /workspaces/baseball-crawl && git apply --check --3way /tmp/E-NNN-epic.patch`
4. If dry-run succeeds: apply for real (`git apply --3way /tmp/E-NNN-epic.patch`)
5. PII scan on applied changes (pre-commit hook)
6. Present staged changes summary to user, wait for explicit approval
7. `git commit` with conventional message: `feat(E-NNN): <epic title>`
8. Cleanup: `git worktree remove <epic-worktree-path> && git branch -D epic/E-NNN`

If dry-run fails (conflict with main): present conflict report to user with affected files. Options: (a) resolve manually, (b) abort.

### TN-5: Context-Layer Stories Stay in Main Checkout
Stories that modify ONLY context-layer files (`.claude/`, `CLAUDE.md`) continue to run in the main checkout without worktree isolation. Their changes are NOT part of the epic worktree's diff and are NOT included in the epic's atomic commit.

**Commit ordering**: Context-layer changes remain UNCOMMITTED in the main checkout throughout dispatch. They are committed AFTER the epic's atomic commit completes — never before. This preserves a stable diff base: all story patches and the final epic patch are generated against the same `main` HEAD that existed when the epic worktree was created. Committing context-layer changes to main mid-dispatch would shift the diff base and break the epic-scoped diff guarantee.

**Closure sequence**: Phase 5 checks for uncommitted context-layer changes after the epic commit succeeds. If found, they are committed in a separate commit (e.g., `chore(E-NNN): context-layer updates`). If the epic commit fails or is aborted, context-layer changes remain uncommitted for the user to handle.

Mixed stories (context-layer + code) run in a worktree per existing routing rules. Their patches merge to the epic worktree like any other story.

### TN-6: Triage Simplification
Current model: MUST FIX → fix; SHOULD FIX → main session triages into accept track (route to implementer) or dismiss track (present to user for confirmation). The dismiss track allows "correct but not worth fixing" as a valid reason.

New model: The team still judges whether each finding is valid (correct analysis of the code) or invalid (false positive, misunderstanding, targets untouched code). What changes is the response to valid findings:
- **Valid finding** → fix it, regardless of size or cosmetic nature. "Correct but too small to fix" is no longer a valid dismissal reason.
- **Invalid finding** → dismiss with explanation. No user confirmation needed.

The distinction between MUST FIX and SHOULD FIX is preserved in the code-reviewer's output format (it signals severity), but the handling for valid findings collapses: any valid finding gets routed to the implementer. The "correct but not worth fixing" dismiss category is eliminated. The main session no longer presents dismiss-track items to the user for confirmation — the only dismissals are invalidity judgments made by the team.

### TN-7: Migration Serialization
Migration stories (`migrations/`) must never run concurrently (existing rule). Additionally, at closure merge time, the main session scans the epic worktree's patch for migration file additions. If new migration files are present and main has added migrations since the epic worktree branched, flag a potential numbering conflict to the user before applying.

### TN-8: PM and Code-Reviewer Spawn Context
Both PM and code-reviewer run without worktree isolation (existing behavior). Their spawn context is updated to include the epic worktree path so they can:
- PM: reference the epic worktree when verifying ACs (knows where accumulated changes live)
- Code-reviewer: use the epic worktree path for integration-level diffs when assigned post-epic review (Epic E-138)

### TN-9: Codex Review Worktree Awareness
The codex-review skill and `scripts/codex-review.sh` must support running against the epic worktree. In `uncommitted` mode (default), the script should accept an optional `--workdir` parameter or be invoked from the epic worktree directory. The diff is `git diff main` from the epic worktree, producing exactly the epic's changes.

## Open Questions
- None remaining (resolved during consultation).

## History
- 2026-03-19: Created during parallel-epic-design consultation team. PM, CA, SE, and DE contributed analysis. User validated two-epic plan (E-137 infrastructure, E-138 pipeline).
- 2026-03-19: Codex spec review completed -- all findings fixed during refinement. User approved plan. Status set to READY.
- 2026-03-19: Epic COMPLETED. All 9 stories DONE across 3 waves. Wave 1: E-137-01 rewrote the implement skill with epic worktree lifecycle, closure merge sequence (epic worktree → main), and simplified triage model (fix all valid findings, dismiss only invalid). Wave 2: E-137-02 through E-137-08 aligned all dependent context-layer files (dispatch-pattern, worktree-isolation, workflow-discipline rules; code-reviewer and PM agent definitions; codex-review skill and script with --workdir support; context-layer exception documentation). Wave 3: E-137-09 hygiene review found and fixed 2 stale triage language references in code-reviewer.md. Key artifacts: implement skill fully rewritten for epic worktree model, codex-review.sh enhanced with --workdir parameter, hygiene audit log at /.project/research/E-137-09-hygiene-audit.md.
