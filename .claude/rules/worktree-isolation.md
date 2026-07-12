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

1. **Dispatch active** (epic worktree at `/tmp/.worktrees/baseball-crawl-E-*` exists): Blocks ALL Write/Edit to `/workspaces/baseball-crawl/` with no exception. This fails closed -- new paths are automatically protected without hook updates.
2. **No dispatch** (no epic worktree): Blocks Write/Edit to implementation paths only (`src/`, `tests/`, `migrations/`, `scripts/`). All other main-checkout writes are allowed.

Worktree writes (`/tmp/.worktrees/...`) always pass unconditionally in both modes. The hook intercepts Write and Edit tool calls only (not Bash commands), so git operations are unaffected.

Note: mode 1 has NO agent-memory carve-out. During dispatch, own-memory writes -- dispatch-time deliverables AND closure-time writes (PM's Active→Archived flip and topic-file flushes, claude-architect's codification) -- go to the WORKTREE copy so they ride the closure patch and appear in the operator-approved diff. Consultation-mode own-memory writes are unaffected: they happen when no worktree exists (mode 2), where the hook does not guard `.claude/agent-memory/`.

## Epic Worktree Constraints

- **No Docker/app CLI**: Do NOT run `docker compose`, `bb data`, `bb creds`, `bb db`, `bb status`, or `bb proxy` commands.
- **No credential/data access**: `.env` and `data/` do not exist in worktrees.
- **No committing**: Do NOT run `git commit`. The main session produces a single atomic commit at epic closure.
- **No branch management**: Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d/-D`.
- **No cd to main**: Stay in the epic worktree. Do NOT `cd /workspaces/baseball-crawl`.
- **Own-memory deliverables go in the worktree**: a dispatched story that writes an agent's own `.claude/agent-memory/<agent>/` files edits the WORKTREE copy, never the main-checkout copy. Since mode 1 no longer carves out agent-memory, a main-checkout own-memory write during dispatch is now hook-denied outright; it also bypasses the per-story staging boundary and trips the Step 8 clean-tree preflight. **The same rule covers closure-time own-memory writes**: PM's Active→Archived `MEMORY.md` flip and topic-file flushes (`archived-epics.md`, `epic-codifications.md`, numbering-state), and claude-architect's closure codification, are authored in the worktree copy at the Step 8 sub-step-3 authoring window so they ride the closure patch.
- **Use absolute paths**: All file operations use absolute paths under the epic worktree.

Full constraint set (including Bash write prohibitions and pytest limitation) is delivered in your spawn context via the implement skill (`.claude/skills/implement/SKILL.md`).
