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
- **Who works here**: The main session only, with one exception. Agents do NOT work directly in the epic worktree during normal dispatch (Phases 1-3). **Exception**: During Phase 4 post-review remediation (codex review and integration review), implementers are spawned into the epic worktree to apply fixes. At this point all story worktrees are cleaned up and the epic worktree is the only place fixes can land. See the implement skill Phase 4a for the controlled exception details.

## Story Worktree Constraints

If you are an implementing agent in a story worktree, these critical prohibitions apply:

- **No Docker/app CLI**: Do NOT run `docker compose`, `bb data`, `bb creds`, `bb db`, `bb status`, or `bb proxy` commands.
- **No credential/data file access**: `.env` and `data/` do not exist in worktrees. Do NOT attempt to read them.
- **No committing**: Do NOT run `git commit`. The main session produces a single atomic commit at epic closure. You MUST run `git add -A` before reporting completion (stages changes for diff visibility), but do not commit.
- **No branch/worktree management**: Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d/-D`.

Full worktree constraint set (what you can/cannot do, file path conventions) is delivered in your spawn context via the implement skill (`.claude/skills/implement/SKILL.md`).

## Path Check

If your cwd is NOT `/workspaces/baseball-crawl`, you are in a worktree under `/tmp/.worktrees/`. Determine which tier by matching the path pattern:

- **Story worktree** (`baseball-crawl-<random>`, e.g., `baseball-crawl-abc123`): You are an implementing agent during Phase 3 dispatch. The full Story Worktree Constraints above apply.
- **Epic worktree** (`baseball-crawl-E-NNN`, e.g., `baseball-crawl-E-137`): You are an implementing agent during Phase 4 post-review remediation. Your constraints are defined by the Phase 4 spawn context in the implement skill -- not the Story Worktree Constraints above. The key differences: you work on remediation findings (not stories), fixes are not committed (they accumulate for closure merge), and you follow the epic worktree exception rules from Phase 4a.
