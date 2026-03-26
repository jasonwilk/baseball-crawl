---
paths:
  - "**"
---

# Worktree Isolation

If your cwd is NOT `/workspaces/baseball-crawl` (e.g., `/tmp/.worktrees/baseball-crawl-E-NNN/`), you are in an epic worktree.

## Epic Worktree

- **Path pattern**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (epic ID suffix, e.g., `baseball-crawl-E-137`)
- **Branch**: `epic/E-NNN`
- **Purpose**: Single shared workspace where all agents (implementers, PM, code-reviewer) work during dispatch. Stories execute serially; the staging boundary protocol (`git add -A` after each story passes review) isolates per-story changes.
- **Who works here**: All agents during dispatch. The main session manages the worktree lifecycle and staging boundary.

## Hook Enforcement

A PreToolUse hook (`.claude/hooks/worktree-guard.sh`) guards Write and Edit operations on the main checkout. Two modes:

1. **Dispatch active** (epic worktree at `/tmp/.worktrees/baseball-crawl-E-*` exists): Blocks ALL Write/Edit to `/workspaces/baseball-crawl/` except `.claude/agent-memory/*`. This fails closed -- new paths are automatically protected without hook updates.
2. **No dispatch** (no epic worktree): Blocks Write/Edit to implementation paths only (`src/`, `tests/`, `migrations/`, `scripts/`). All other main-checkout writes are allowed.

Worktree writes (`/tmp/.worktrees/...`) always pass unconditionally in both modes. The hook intercepts Write and Edit tool calls only (not Bash commands), so git operations are unaffected.

## Epic Worktree Constraints

- **No Docker/app CLI**: Do NOT run `docker compose`, `bb data`, `bb creds`, `bb db`, `bb status`, or `bb proxy` commands.
- **No credential/data access**: `.env` and `data/` do not exist in worktrees.
- **No committing**: Do NOT run `git commit`. The main session produces a single atomic commit at epic closure.
- **No branch management**: Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d/-D`.
- **No cd to main**: Stay in the epic worktree. Do NOT `cd /workspaces/baseball-crawl`.
- **Use absolute paths**: All file operations use absolute paths under the epic worktree.

Full constraint set (including Bash write prohibitions and pytest limitation) is delivered in your spawn context via the implement skill (`.claude/skills/implement/SKILL.md`).
