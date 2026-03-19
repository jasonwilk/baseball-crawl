---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

**The main session (user-facing agent) is the spawner and router during dispatch.** It creates teams, spawns all agents (implementers, code-reviewer, and PM), assigns stories, routes completed work through the review and AC verification loop, manages patch-apply merge-back, and runs the closure sequence (atomic commit). The main session orchestrates -- it does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git apply` for merge-back, `git add -A` and `git commit` for the closure atomic commit, `git worktree` and `git branch -D` for worktree cleanup) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

## Team Roles

1. **Main session (spawner + router)** -- Creates the team, assigns stories, routes completion reports, manages patch-apply merge-back and cascade, runs closure (atomic commit). MUST NOT create, modify, or delete any file, or verify ACs. The only direct file operations are git commands (`git apply` for merge-back, `git worktree` and `git branch -D` for worktree cleanup, `git add -A` and `git commit` for the closure atomic commit, `git mv` for archive) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).
2. **Product-manager (status owner + AC verifier)** -- Owns story/epic status transitions and AC verification. Spawned as infrastructure (not in Dispatch Team section). No worktree isolation.
3. **Specialist agents (implementers)** -- Execute assigned stories. Spawned per the epic's Dispatch Team section or the routing table in `/.claude/rules/agent-routing.md`.
4. **Code-reviewer (quality gate)** -- Reviews every code story before DONE. Spawned as infrastructure. No worktree isolation.

## Domain Work During Dispatch

**Litmus test:** If you are inspecting what was built or assessing quality, you are doing domain work. Route it.

Many boundary violations start as "quick checks" that feel like orchestration but are actually domain work. The classification is based on *purpose*, not *tool*: `git log` for merge-back is orchestration; `git log` to verify what an implementer committed is domain work.

**Domain work -- route to the appropriate agent:**
- Reading source or test files to verify implementation claims
- Running `git log`, `git diff`, or `git show` to inspect what was committed (not merge-back mechanics)
- Running `grep` to confirm patterns were added or removed
- Running `pytest` or any test commands
- Assessing whether acceptance criteria are met

**Permitted orchestration -- the main session does these directly:**
- Reading epic and story files for routing decisions
- Git commands for patch-apply merge-back (`git apply`, `git worktree`, `git branch -D`)
- Sending messages to teammates via SendMessage
- Team lifecycle management (spawn, shutdown)
- Git commands for closure atomic commit (`git add -A`, `git commit`)
- Git commands for archive (`git mv`, `git add`, `git commit`)
- Writes to own memory directory

For the procedural protocol on handling completion reports, see the implement skill (`.claude/skills/implement/SKILL.md`, Phase 3 Step 5).

## Dispatch Procedures

The **implement skill** (`.claude/skills/implement/SKILL.md`) is the authoritative source for all dispatch procedures: team creation, story assignment, review loops, merge-back, closure sequence, and edge cases. Load it when the user requests dispatch.

## Agent Routing

See `/.claude/rules/agent-routing.md` for the Agent Selection routing table, Dispatch Team metadata, Agent Hint, Routing Precedence, and Decision Routing.
