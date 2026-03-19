---
paths:
  - "**"
---

# Worktree Isolation -- Safety Net

If your cwd is NOT `/workspaces/baseball-crawl` (e.g., `/tmp/.worktrees/baseball-crawl-*/`), you are in a worktree. Two worktree tiers exist, with different roles and constraints.

## Two Worktree Tiers

### Story-level worktrees (agent workspace)

- **Path pattern**: `/tmp/.worktrees/baseball-crawl-*/` (random suffix, e.g., `baseball-crawl-abc123`)
- **Purpose**: Isolated copy of the repo where an implementing agent works on a single story. Created automatically when an agent is spawned with `isolation: "worktree"`.
- **Who works here**: The implementing agent assigned to the story.

### Epic-level worktree (patch accumulation)

- **Path pattern**: `/tmp/.worktrees/baseball-crawl-E-NNN/` (epic ID suffix, e.g., `baseball-crawl-E-137`)
- **Branch**: `epic/E-NNN`
- **Purpose**: Accumulation point where the main session applies story patches via `git apply` during dispatch. All story patches merge here before the final closure merge to main.
- **Who works here**: The main session only. Agents do NOT work directly in the epic worktree -- it is managed exclusively by the main session for patch accumulation and closure merge.

## Story Worktree Constraints

If you are an implementing agent in a story worktree, these critical prohibitions apply:

- **No Docker/app CLI**: Do NOT run `docker compose`, `bb data`, `bb creds`, `bb db`, `bb status`, or `bb proxy` commands.
- **No credential/data file access**: `.env` and `data/` do not exist in worktrees. Do NOT attempt to read them.
- **No committing**: Do NOT run `git commit`. The main session produces a single atomic commit at epic closure. You MUST run `git add -A` before reporting completion (stages changes for diff visibility), but do not commit.
- **No branch/worktree management**: Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d/-D`.

Full worktree constraint set (what you can/cannot do, file path conventions) is delivered in your spawn context via the implement skill (`.claude/skills/implement/SKILL.md`).

## Path Check

The main checkout path check (`cwd is NOT /workspaces/baseball-crawl`) still correctly identifies story worktrees, since both story worktrees and epic worktrees are outside the main checkout under `/tmp/.worktrees/`. If you are an agent and your cwd is not the main checkout, you are in a story worktree and the constraints above apply.
