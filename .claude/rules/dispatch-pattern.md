---
paths:
  - "**"
---

# Dispatch Pattern -- Agent Teams

**The main session (user-facing agent) is the spawner and router during dispatch.** It creates the epic worktree, creates teams, spawns all agents (implementers, code-reviewer, and PM -- all working in the epic worktree), assigns stories serially, routes completed work through the review and AC verification loop, freezes each story's review surface on its completion report (`git add -A && git write-tree`) and advances the staging boundary once both verdicts approve, and runs the closure merge sequence (epic worktree → main). The main session orchestrates -- it does not own statuses, verify ACs, or create, modify, or delete any file. The main session's only direct file operations are git commands (`git worktree add/remove` for epic worktree lifecycle, `git diff`/`git apply` for closure merge from epic worktree to main, `git mv` for the archive rename **in the epic worktree** at closure, `git add -A` for staging boundary and closure commit, a single `git commit` for the atomic closure commit, `git branch -D` for branch cleanup) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).

## Team Roles

1. **Main session (spawner + router)** -- Creates the epic worktree, creates the team, assigns stories serially, routes completion reports, freezes the review surface on each completion report (`git add -A && git write-tree`) and advances the staging boundary once both verdicts approve, runs the closure merge sequence (epic worktree → main). MUST NOT create, modify, or delete any file, or verify ACs. The only direct file operations are git commands (`git worktree add/remove` for epic worktree lifecycle, `git diff`/`git apply` for closure merge, `git mv` for the archive rename **in the epic worktree** at closure, `git add -A` for staging boundary and closure commit, a single `git commit` for the atomic closure commit, `git branch -D`) and writes to its own memory directory.
2. **Product-manager (status owner + AC verifier)** -- Owns story/epic status transitions and AC verification. Works in the epic worktree during dispatch. Spawned as infrastructure (not in Dispatch Team section).
3. **Specialist agents (implementers)** -- Execute assigned stories in the epic worktree. Spawned per the epic's Dispatch Team section or the routing table in `/.claude/rules/agent-routing.md`.
4. **Code-reviewer (quality gate)** -- Reviews every code story before DONE. Reviews a **frozen tree**, not working-directory state: the main session freezes the story on the completion report and the review runs against the diff between that tree and the previous story's. Spawned as infrastructure.

**Nobody verifies the orchestrator's sequencing unless someone is named to.** Every ARTIFACT role here has a verifier -- the implementer has the code-reviewer, the acceptance criteria have PM -- but the orchestrator's own PROCEDURE has none, which is how E-276 lost a whole review phase and then five closure steps in a single epic while able to quote both. When a navigator or sub-lead is present, **checking the orchestrator's sequencing is an explicit part of that role**: does the phase we are entering have its precondition satisfied, and did the last one actually finish? This is not hypothetical -- the navigator independently flagged an un-removed worktree before the operator asked. With no navigator, the Step 12 terminal gate is the only backstop, which is why it reads repository state instead of accepting a report.

Both PM and code-reviewer must approve before the staging boundary advances. PM is authoritative on ACs -- see the implement skill for disagreement resolution.

**Each issues exactly ONE verdict per frozen state** -- PM the AC verdict, code-reviewer the review verdict -- **and neither is re-askable about a tree it has already ruled on.** A remediation produces a new frozen tree, so reviewing that is a first verdict on a different artifact rather than a second on the same one. **Dual approval is not what this bound retired; re-issuance is.** Both approvers stay; each approves once.

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
- Freezing the review surface on the completion report (`git add -A && git write-tree`), and advancing the staging boundary once both verdicts approve -- the freeze is what stages, so the boundary confirms the approved tree rather than staging afresh
- Sending messages to teammates via SendMessage
- Team lifecycle management (spawn, shutdown)
- Closure merge sequence: epic worktree → main (**in the epic worktree**: `git mv` for the archive rename, then `git add -A`, then `git diff --binary --cached $(git merge-base epic/E-NNN main)`; **then in main**: `git apply --check --3way` dry-run, `git apply --3way`, `git add -A`, single `git commit` for the atomic closure commit). **The diff base is the MERGE BASE, never bare `main`** — `main` moves while an epic runs, so a `main`-based patch silently reverts commits nobody in this epic touched. **The archive rename happens in the WORKTREE before the patch is generated, so it rides the patch**; there is no separate main-checkout rename. See the implement skill Step 8 for the full sequence.
- Epic worktree cleanup after closure commit (`git worktree remove`, `git branch -D epic/E-NNN`)
- Running the archive-reference check script at closure and routing its hits to their owning agents — running a deterministic script and reading an exit code is repository state, not content judgement; **ruling on the hits is domain work and MUST be routed**
- Writes to own memory directory

For the procedural protocol on handling completion reports, see the implement skill (`.claude/skills/implement/SKILL.md`, Phase 3 Step 5).

## Briefs, Channels, and Context

**A brief is a relay; the durable artifact wins.** Every inter-agent brief, handoff note, or kickoff prompt is a SUMMARY of something committed elsewhere -- an epic file, a story, a research artifact. The receiver verifies the brief against that artifact before acting, and where they conflict **the artifact wins and the brief is wrong**. This is not distrust of the sender: a brief is written at one moment and read at another, and the gap is where the defect lives. In E-276's planning the hub shipped 9 relay defects; the ones that were caught were caught by exactly this check (a PM catch, and a code-reviewer refuting the brief before review), and E-267's handoff incident is the same shape with a 45-second gap. State the relay status explicitly when you write a brief, so the receiver knows to check.

**Spawn prompts name the delivery channel.** Any named-agent spawn states where the result goes -- "deliver via SendMessage to `<target>`" -- and how big it should be. Without it, agents finish the work and go idle holding the answer: 8 of 10 spawns in one audited session, 6 of 8 in another, and the analyst studying the pattern then reproduced it on itself. A plain-text final message is not delivery; only the tool call is.

**Report context pressure, and drain before you are forced to.** Long-lived teammates state context health when it becomes material -- one word is enough. A "low" report means: finish the task in hand, flush state to a durable artifact, and stop. Work restarts cleanly from the committed record on a fresh instance; it does not restart cleanly from a summary of a summary. In E-276 a PM drained deliberately across three generations and the work survived; the 2026-07-25 session that pushed on instead degraded.

**A compaction boundary is a session boundary.** After any auto-compact, re-read the authoritative artifacts -- the epic file, the story statuses -- BEFORE asserting any prior state or briefing any agent. Post-compact assertions about pre-compact state are reconstructions from a summary, and they are structurally unverifiable from memory: in E-276 the hub auto-compacted at 21:21:42Z and its next two relay defects were both post-compact assertions of pre-compact state, one of which handed a PM a false "the design is settled" premise. This is file-wins applied to your own past. The companion move is to flush state to the durable artifact *before* the pressure peaks, so that what compaction summarizes is already secondary to something on disk.

**Effect in the artifact is a receipt; the tool's own success response is not.** **Verify delivery by looking for the change your message should have caused, not by the send succeeding** -- across an E-277 dispatch success receipts were worthless, and the one check that worked was a reviewer counting its own LANDED findings and inferring which reports had arrived.

⚠ **The bound is half the rule, and without it this fails silently on the cases that matter most: it reaches ACTIONABLE findings only.** A question, a ruling, a hold instruction or a status report **causes no artifact effect**, so its delivery is unverifiable by this method and by any other we have -- and those are exactly the classes that went missing. **A technique that looks general and fails silently on the un-actionable case is worse than none.**

For a story's own review surface the freeze now supplies a mechanical substitute -- the frozen tree SHA is an address both parties can cite, so "which state did you rule on" has an answer that does not depend on a receipt. **That covers the dispatch case only.** It does nothing for the un-actionable classes above, which remain unverifiable and are why the bound stays.

**Before adjudicating a persistent disagreement, check whether the parties are answering the SAME QUESTION.** Two careful agents disputed one sentence for several rounds, each conceding to the other in turn, because three positions answered three different questions -- *is the text ambiguous* (about the text), *which reading did the author hold* (about the author), *is the count right under that reading* (arithmetic given a reading). **They cannot contradict each other.** Checking for a shared question is cheaper than deciding who is right, and it dissolved that one. **Corollary: mutual concession must not decide a record** -- when each party argues the other's case, the record is set by whoever spoke last, which is uncorrelated with truth. **Record the account that explains all the evidence, including each party's own errors, not the last position stated.** And the individual form: **conceding is not automatically the rigorous move.** Yielding a correct position because yielding feels disciplined is a way of being wrong that looks like being careful -- the mirror of this repo's usual failure, which is why instincts trained on that one miss it. **Ask: am I yielding to evidence, or to the fact that yielding looks rigorous?**

## Dispatch Procedures

The **implement skill** (`.claude/skills/implement/SKILL.md`) is the authoritative source for all dispatch procedures: team creation, story assignment, review loops, staging boundary, closure sequence, and edge cases. Load it when the user requests dispatch.

## Agent Routing

See `/.claude/rules/agent-routing.md` for the Agent Selection routing table, Dispatch Team metadata, Agent Hint, Routing Precedence, and Decision Routing.
