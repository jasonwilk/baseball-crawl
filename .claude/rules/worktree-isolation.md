---
paths:
  - "**"
---

# Worktree Isolation -- Safety Net

If your cwd is NOT `/workspaces/baseball-crawl` (e.g., `/tmp/.worktrees/baseball-crawl-*/`), you are in a worktree. These critical prohibitions apply:

- **No Docker/app CLI**: Do NOT run `docker compose`, `bb data`, `bb creds`, `bb db`, `bb status`, or `bb proxy` commands.
- **No credential/data file access**: `.env` and `data/` do not exist in worktrees. Do NOT attempt to read them.
- **No branch/worktree management**: Do NOT run `git merge`, `git rebase`, `git worktree remove`, or `git branch -d`.

Full worktree constraint set (what you can/cannot do, file path conventions) is delivered in your spawn context via the implement skill (`.claude/skills/implement/SKILL.md`).
