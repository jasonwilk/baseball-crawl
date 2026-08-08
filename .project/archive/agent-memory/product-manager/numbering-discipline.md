# Numbering Discipline — why a glob is necessary and never sufficient

Reference material for claiming an epic, story, idea, or migration number. `MEMORY.md` carries the one-line rule; this file carries the worked instances, because each one failed a *different* way and a reader who knows only one will repeat the other two.

## The rule

**Glob the live dirs — and then ask, if any other thread may be live.**

```
ls /epics/  ls /.project/archive/  ls /.project/ideas/  ls migrations/
grep -rn "E-NNN" .claude/agent-memory/ .project/research/
```

A glob is authoritative **against a stale memory counter**. It is not authoritative against anything that has not landed on disk yet, and there are three of those.

## Disk lags reality in three directions

**1. A stale counter in this memory file.** The oldest and most ordinary failure. The "next number" line in `MEMORY.md` has gone stale **four times**, and once **by two within a single session, written by a PM who had just corrected it**. Awareness of the class confers no immunity — only the glob does. Collisions of record: E-229 and IDEA-071, in one session.

**2. An unmerged branch consumes numbers a glob of main reports FREE.** During E-275 planning, IDEA-201-214 lived only on the committed-but-unmerged `epic/E-275` branch. A glob of `main` reported all fourteen free and was **wrong**. At E-277 closure a "safe gap" of 210-211 was proposed on exactly that reasoning and **would have collided**; refusing to guess across the boundary cost one message. *(This instance is now CLOSED — the fourteen files were extracted into main on 2026-07-27 — but the shape recurs with the next long-lived branch.)*

**3. A concurrent thread's reservation is not on disk at all — the expensive one.** In E-275 planning PM globbed **correctly** (IDEA-197 *was* the highest on disk), assigned 198-207, and collided anyway: a sibling thread running in its own isolated worktree had reserved 198-200. Nothing was done wrong and the collision happened regardless, because a reservation held in another agent's context is invisible to every check available.

**Cost of that one: a ten-file renumber to 201-210, requiring `git mv`, which PM cannot run (no Bash).** So it could not even be self-serviced — it had to be handed back. That asymmetry is the argument for asking: the check costs one message, the recovery costs a renumber someone else has to perform.

**4. A number can be reserved in PROSE before any directory exists.** E-275 itself was reserved this way — ~18 references across `baseball-coach` and `ux-designer` memory and `.project/research/` named the number while `epics/` held nothing. Cheaper to skip a number than to renumber, so **grep the memory and research trees, not just the live dirs**.

## The operator ruling

**"Numbers are allocated here, never guessed."**

It rests on premises 2 and 3 above. **Premise 2 dissolved on 2026-07-27; premise 3 did not**, and premise 3 alone is sufficient to keep the ruling standing. Retiring an operator ruling is an escalation class in any case — surface a dissolved premise, never self-authorize the retirement.

> ⚠️ **Recorded because I got this wrong.** On 2026-07-27 I reported to the team that the ruling's premise had dissolved, having checked only the branch-divergence half. That was true of one premise and false as a statement about the ruling. The correction came from reading the E-275 branch's own PM memory, which held the concurrent-reservation lesson my copy lacked. **A ruling with two premises does not become retirable when one of them closes** — enumerate them before reporting on any of them.

---
Last updated: 2026-07-27
