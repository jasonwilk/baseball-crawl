---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

**The main session (user-facing agent) is the spawner and router during dispatch.** It creates the epic worktree, creates teams, spawns all agents (implementers, code-reviewer, and PM -- all working in the epic worktree), assigns stories serially, routes completed work through the review and AC verification loop, manages the staging boundary between stories (`git add -A` after each story passes review), and runs the closure merge sequence (epic worktree → main). The main session orchestrates -- it does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git worktree add/remove` for epic worktree lifecycle, `git diff`/`git apply` for closure merge from epic worktree to main, `git mv` for archive rename during closure, `git add -A` for staging boundary and closure commit, a single `git commit` for the atomic closure commit, `git branch -D` for branch cleanup) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

## Team Roles

1. **Main session (spawner + router)** -- Creates the epic worktree, creates the team, assigns stories serially, routes completion reports, manages the staging boundary (`git add -A` after each story passes review), runs the closure merge sequence (epic worktree → main). MUST NOT create, modify, or delete any file, or verify ACs. The only direct file operations are git commands (`git worktree add/remove` for epic worktree lifecycle, `git diff`/`git apply` for closure merge, `git mv` for archive rename during closure, `git add -A` for staging boundary and closure commit, a single `git commit` for the atomic closure commit, `git branch -D`) and writes to its own memory directory.
2. **Product-manager (status owner + AC verifier)** -- Owns story/epic status transitions and AC verification. Works in the epic worktree during dispatch. Spawned as infrastructure (not in Dispatch Team section).
3. **Specialist agents (implementers)** -- Execute assigned stories in the epic worktree. Spawned per the epic's Dispatch Team section or the routing table in `/.claude/rules/agent-routing.md`.
4. **Code-reviewer (quality gate)** -- Reviews every code story before DONE. Reviews via `git diff` in the epic worktree (unstaged = current story). Spawned as infrastructure.

**Nobody verifies the orchestrator's sequencing unless someone is named to.** Every ARTIFACT role here has a verifier -- the implementer has the code-reviewer, the acceptance criteria have PM -- but the orchestrator's own PROCEDURE has none, which is how E-276 lost a whole review phase and then five closure steps in a single epic while able to quote both. When a navigator or sub-lead is present, **checking the orchestrator's sequencing is an explicit part of that role**: does the phase we are entering have its precondition satisfied, and did the last one actually finish? This is not hypothetical -- the navigator independently flagged an un-removed worktree before the operator asked. With no navigator, the Step 12 terminal gate is the only backstop, which is why it reads repository state instead of accepting a report.

Both PM and code-reviewer must approve before the staging boundary advances. PM is authoritative on ACs -- see the implement skill for disagreement resolution.

**Concurrency under load (advisory).** When the harness emits load/capacity notices during dispatch, prefer serializing agent activity (fewer simultaneously-active agents) until the notices clear -- this is the output-integrity cross-check/retry/escalate discipline applied to dispatch concurrency, not a numeric cap or a config setting.

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
- Epic worktree creation (`git worktree add -b epic/E-NNN /tmp/.worktrees/baseball-crawl-E-NNN`)
- Staging boundary: `git add -A` in the epic worktree after each story passes review
- Sending messages to teammates via SendMessage
- Team lifecycle management (spawn, shutdown)
- Closure merge sequence: epic worktree → main (`git diff --binary --cached main` in epic worktree, `git apply --check --3way` dry-run in main, `git apply --3way` in main, `git mv` for archive rename, `git add -A`, single `git commit` for the atomic closure commit)
- Epic worktree cleanup after closure commit (`git worktree remove`, `git branch -D epic/E-NNN`)
- Writes to own memory directory

For the procedural protocol on handling completion reports, see the implement skill (`.claude/skills/implement/SKILL.md`, Phase 3 Step 5).

## Briefs, Channels, and Context

**A brief is a relay; the durable artifact wins.** Every inter-agent brief, handoff note, or kickoff prompt is a SUMMARY of something committed elsewhere -- an epic file, a story, a research artifact. The receiver verifies the brief against that artifact before acting, and where they conflict **the artifact wins and the brief is wrong**. This is not distrust of the sender: a brief is written at one moment and read at another, and the gap is where the defect lives. In E-276's planning the hub shipped 9 relay defects; the ones that were caught were caught by exactly this check (a PM catch, and a code-reviewer refuting the brief before review), and E-267's handoff incident is the same shape with a 45-second gap. State the relay status explicitly when you write a brief, so the receiver knows to check.

**Spawn prompts name the delivery channel.** Any named-agent spawn states where the result goes -- "deliver via SendMessage to `<target>`" -- and how big it should be. Without it, agents finish the work and go idle holding the answer: 8 of 10 spawns in one audited session, 6 of 8 in another, and the analyst studying the pattern then reproduced it on itself. A plain-text final message is not delivery; only the tool call is.

**Report context pressure, and drain before you are forced to.** Long-lived teammates state context health when it becomes material -- one word is enough. A "low" report means: finish the task in hand, flush state to a durable artifact, and stop. Work restarts cleanly from the committed record on a fresh instance; it does not restart cleanly from a summary of a summary. In E-276 a PM drained deliberately across three generations and the work survived; the 2026-07-25 session that pushed on instead degraded.

**A compaction boundary is a session boundary.** After any auto-compact, re-read the authoritative artifacts -- the epic file, the story statuses -- BEFORE asserting any prior state or briefing any agent. Post-compact assertions about pre-compact state are reconstructions from a summary, and they are structurally unverifiable from memory: in E-276 the hub auto-compacted at 21:21:42Z and its next two relay defects were both post-compact assertions of pre-compact state, one of which handed a PM a false "the design is settled" premise. This is file-wins applied to your own past. The companion move is to flush state to the durable artifact *before* the pressure peaks, so that what compaction summarizes is already secondary to something on disk.

## Dispatch Procedures

The **implement skill** (`.claude/skills/implement/SKILL.md`) is the authoritative source for all dispatch procedures: team creation, story assignment, review loops, staging boundary, closure sequence, and edge cases. Load it when the user requests dispatch.

## Agent Routing

See `/.claude/rules/agent-routing.md` for the Agent Selection routing table, Dispatch Team metadata, Agent Hint, Routing Precedence, and Decision Routing.
