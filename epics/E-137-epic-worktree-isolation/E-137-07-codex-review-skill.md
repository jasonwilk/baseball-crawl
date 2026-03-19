# E-137-07: Update Codex-Review Skill

## Epic
[E-137: Epic-Level Worktree Isolation](epic.md)

## Status
`TODO`

## Description
After this story is complete, the codex-review skill (`.claude/skills/codex-review/SKILL.md`) and the codex-review script (`scripts/codex-review.sh`) support running against an epic worktree. When invoked during dispatch (the "and review" chain), the diff is generated from the epic worktree against main, producing exactly the epic's changes.

## Context
The codex-review script currently runs in the main checkout and diffs against working tree state (`git diff --cached` + `git diff` + untracked). With epic worktrees, the "and review" chain should diff the epic worktree against main. The script needs a way to target the epic worktree — either via a `--workdir` parameter or by being invoked from the epic worktree directory.

Per TN-9, the skill and script must support epic worktree awareness while maintaining backward compatibility for standalone reviews (which still run from the main checkout).

## Acceptance Criteria
- [ ] **AC-1**: `scripts/codex-review.sh` accepts an optional `--workdir <path>` parameter that, when provided, runs git commands from the specified directory instead of the script's own REPO_ROOT.
- [ ] **AC-2**: When `--workdir` is provided, the `uncommitted` mode generates the diff as `cd <workdir> && git diff main` (staged + unstaged changes in the epic worktree relative to main).
- [ ] **AC-3**: When `--workdir` is NOT provided, the script behaves identically to today (backward compatible).
- [ ] **AC-4**: The codex-review skill's headless path (Step 1) passes `--workdir <epic-worktree-path>` when invoked during the "and review" chain (implement skill Phase 4).
- [ ] **AC-5**: The codex-review skill's prompt-generation path (Step 1) supports `--workdir` for gathering the diff when an epic worktree path is available.
- [ ] **AC-6**: The skill documents how the epic worktree path is obtained (from the implement skill's Phase 4 context, which has the epic worktree path from Phase 2).

## Technical Approach
The `--workdir` parameter is the cleanest approach — it preserves backward compatibility and avoids requiring the caller to `cd` before invoking. The script's `generate_uncommitted_diff` function changes its `cd` target when `--workdir` is set.

The implement skill's Phase 4 already invokes the codex-review skill. It needs to pass the epic worktree path as context. The codex-review skill then passes it to the script via `--workdir`.

## Dependencies
- **Blocked by**: E-137-01
- **Blocks**: E-137-09

## Files to Create or Modify
- `.claude/skills/codex-review/SKILL.md`
- `scripts/codex-review.sh`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Script backward compatible (no `--workdir` = existing behavior)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing codex-review functionality

## Notes
Moderate story. Touches both a context-layer skill file and a script file (mixed story). Per routing precedence, this goes to claude-architect WITH worktree isolation.
