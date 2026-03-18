---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

**The main session (user-facing agent) is the spawner and router during dispatch.** It creates teams, spawns all agents (implementers, code-reviewer, and PM), assigns stories, routes completed work through the review and AC verification loop, manages merge-back, and runs the closure sequence. The main session orchestrates -- it does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git merge`, `git mv`, `git add`, `git commit`) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

## Team Roles

1. **Main session (spawner + router)** -- Creates the team, assigns stories, routes completion reports, manages merge-back and cascade, runs closure. MUST NOT create, modify, or delete any file, or verify ACs. The only direct file operations are git commands (`git merge`, `git mv`, `git add`, `git commit`) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).
2. **Product-manager (status owner + AC verifier)** -- Owns story/epic status transitions and AC verification. Spawned as infrastructure (not in Dispatch Team section). No worktree isolation.
3. **Specialist agents (implementers)** -- Execute assigned stories. Spawned per the epic's Dispatch Team section or the routing table in `/.claude/rules/agent-routing.md`.
4. **Code-reviewer (quality gate)** -- Reviews every code story before DONE. Spawned as infrastructure. No worktree isolation.

## Dispatch Procedures

The **implement skill** (`.claude/skills/implement/SKILL.md`) is the authoritative source for all dispatch procedures: team creation, story assignment, review loops, merge-back, closure sequence, and edge cases. Load it when the user requests dispatch.

## Agent Routing

See `/.claude/rules/agent-routing.md` for the Agent Selection routing table, Dispatch Team metadata, Agent Hint, Routing Precedence, and Decision Routing.
