# IDEA-228: The closure sequence has no window in which archive-rename fallout can be fixed

## Status
`CANDIDATE` — **a sequencing gap in `.claude/skills/implement/SKILL.md`, hit for real at E-278 closure.**

## Summary

**Three conditions in the closure sequence are jointly unsatisfiable, and they only collide
when an archive rename leaves references behind — which is the normal case, not an edge one.**

1. **Sub-step 6's archive rename** moves `epics/E-NNN-slug/` to `.project/archive/E-NNN-slug/`,
   which **breaks every reference to the old path in files OUTSIDE the archive** — agent
   memory, ideas, research notes.
2. Those files are **agent-owned**. The orchestrator must not edit them: its only direct file
   operations are git commands (`.claude/rules/dispatch-pattern.md`).
3. **`.claude/hooks/worktree-guard.sh` blocks the owning agent from the main checkout for as
   long as the epic worktree exists** — and worktree removal is **step 9, AFTER the commit**.

**So the window in which those fixes must land does not exist.** The rename happens in the
main checkout; the owning agent is locked out of the main checkout until after the commit;
and the orchestrator cannot make the edits on the agent's behalf.

**Editing the worktree copy does not work either** — by sub-step 6 the patch has already been
applied to main, the worktree is clean, and it still holds the pre-rename layout. Any edit
there is orphaned, because there is no second patch coming to carry it across.

## ⚠️ Why this goes unnoticed

**The Step 12 terminal gate passes cleanly either way. Nothing in it checks for outbound
references to the renamed path.** At E-278 it was caught only because code-reviewer suggested
looking for exactly this class at the approval gate — a judgement call, not a gate. Absent
that suggestion, the epic would have committed with three dead pointers, one of them in a file
whose own next sentence reads *"it is a frozen record to cite and never edit"* — **an
instruction that is correct while its address is dead.**

## What worked at E-278, and the two alternatives that are worse

**The workaround that worked** (operator-visible, ~one turn): **remove the epic worktree
early, keeping BOTH the branch and the generated patch file** — `git worktree remove` at
sub-step 6 rather than step 9, with `git branch -D` still deferred to after the commit. The
guard drops to mode 2, the owning agent fixes its own files in main, then the orchestrator
re-stages once. **The revert path is unaffected**: it is `git apply -R --3way` in the main
checkout, which never needed the worktree, and the retained branch plus patch file hold it
doubly.

**Two alternatives, both rated worse at the time and recorded so they are not re-proposed:**
- **Defer to a follow-up commit** — ships a known-dead pointer, and the epic's own closure
  diff is the artifact the operator approves. A defect knowingly shipped past an approval gate
  is worse than one caught before it.
- **Route the edits to a freshly spawned agent** — adds a spawn at the commit boundary for
  three one-line edits, which is exactly the late scope growth that goes wrong.

## Why It Matters

The fallout is small and the failure mode is not: a broken pointer in agent memory is followed
by an agent that has no reason to doubt it, finds nothing, and re-derives what the pointer was
put there to preserve. That is the same class as [[IDEA-224]]/[[IDEA-225]]/[[IDEA-226]] —
claims stranded in files nobody re-reads — arriving by a different route.

It also has a **structural** quality the others lack: those three are content that *went* stale,
while this one is **created by the closure procedure itself, every time, by design.** A rename
that is otherwise correct manufactures the defect.

## Rough Timing

**Promote when claude-architect is next spawned for any reason.** Same disposition as
[[IDEA-224]] through [[IDEA-227]]. Deliberately not urgent: the workaround is known, cheap and
now recorded, so the cost of the gap is one flagged turn per closure rather than a defect —
**provided somebody looks.** That proviso is the part worth fixing.

## Dependencies & Blockers
- [ ] **Requires claude-architect** — the target is `.claude/skills/implement/SKILL.md` and
      possibly `.claude/rules/dispatch-pattern.md`; PM can write neither.

## Open Questions

- **Sequence change, or a gate?** Two shapes. **(a)** Move worktree removal before the archive
  rename, keeping branch deletion after the commit — cheap, and it is what worked. **(b)** Add
  an outbound-reference check to the closure gate — `grep -rn "epics/E-NNN-" ` outside the
  archive after the rename, with any hit routed to its owning agent. **(b) is the one that
  survives someone not thinking to look**, which is the actual failure. They are not exclusive
  and CA should weigh both.
- **Does anything else break on the rename besides path strings?** E-278 only checked the
  literal old path. **A reference that names the epic without spelling the path would not have
  been found** — the same non-token blind spot `.claude/rules/doc-sweep.md` step 2 exists for.

## Notes

Hit at E-278 closure, 2026-07-28, between the archive rename and the operator approval gate.
Not a mistake by any participant — the orchestrator sequenced correctly, PM owned the files
correctly, and the hook did exactly what it is for. **All three behaved correctly and the
outcome was still a deadlock**, which is the signature of a procedural gap rather than an
error.

Related: [[IDEA-224]], [[IDEA-225]], [[IDEA-226]] (stranded claims, different route);
[[IDEA-227]] (lessons stranded in completion reports, filed the same day).

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
