# IDEA-229: The PM memory index is over budget, and the discipline that slipped is not "write less"

## Status
`CANDIDATE` — **measured, bounded, and not urgent. Deliberately deferred from E-278's closure rather than fixed at the commit boundary.**

## Summary

`.claude/agent-memory/product-manager/MEMORY.md` is **19.6KB**, against a **24.4KB read limit**
and a **~17KB target** stated in the file's own header. Surfaced by a `PostToolUse` hook during
E-278's closure.

**Nothing is truncating today.** The failure mode when it does is serious and silent: `MEMORY.md`
is loaded into context every PM session, and content past the limit is dropped without any
signal — so the first symptom would be a PM acting on an index it believes it has read in full.

## Why It Matters — and why the obvious fix is the wrong one

**The file is at 19.6KB partly BECAUSE E-278 pushed real findings into it.** The growth is not
padding; it is material that earned its place. So "write less" is the wrong remedy and would cost
more than it saves.

**The discipline that actually slipped is the index/topic-file split.** `MEMORY.md` is an INDEX —
one line per entry, detail in topic files in the same directory. During E-278's closure the PM
twice wrote *paragraphs* into it: a numbering-state entry that grew into a multi-sentence
explanation, and a topic-file pointer that absorbed the content it was supposed to point at.
**Both were corrected in the same session, and they are named here because "which discipline
slipped" is more useful to a successor than a size number.** A compaction that does not restore
that split will simply re-grow.

`.claude/rules/context-layer-guard.md` already states the rule ("MEMORY.md is an index, not a
memory store"), so this is a compliance drift rather than a missing convention.

## Rough Timing

**Next PM session that is not at a commit boundary.** Focused work, not boundary churn.

**Deliberately deferred from E-278 closure**, and the reasoning is worth preserving because it
cuts against the *other* deferral decision made the same hour: dead path references created by
the archive rename WERE fixed in-closure ([[IDEA-228]]), because **the closure created them**.
The index size was not created by the closure and does not belong to it — a ~2.5KB restructure
riding an operator approval it was not part of is precisely the late scope growth the whole
closure had been refusing. **Same principle, opposite conclusions, because the origin differs.**

## Dependencies & Blockers
- [ ] None. PM owns this file under the own-memory carve-out.

## Open Questions

- **What is the right steady-state size?** The ~17KB target predates several epics' worth of
  accumulated topic files. Whether the number is still right, or whether the index has simply
  outgrown a flat list and wants sectioning, is worth deciding once rather than trimming toward
  a figure nobody has re-examined.
- **Does anything else in `.claude/agent-memory/` have the same drift?** This was found by a hook
  on one file during one edit, which is not a survey. The ratchet measures total growth across the
  subtree but says nothing about index-versus-topic-file placement within it — and `.claude/agent-memory`
  is **+1672** of the standing pre-existing overhang, which is its own open question (E-278 trigger 7).

## Notes

Surfaced 2026-07-28 by a `PostToolUse` hook during E-278 closure, on a PM edit to the numbering
state. **Recorded with its measurement so a successor does not re-derive whether it matters:
19.6KB current / 24.4KB read limit / ~17KB target.**

The PM's own contribution to the overage was corrected immediately and separately — that part
needed no decision, and separating it from the general compaction is what made the deferral
decidable rather than a blanket "not now."

Related: [[IDEA-228]] (deferred the opposite way, same hour, on the origin-of-the-defect
principle), [[IDEA-224]]/[[IDEA-225]]/[[IDEA-226]] (agent-memory content decay — a different
problem in the same tree), [[IDEA-204]] (agent-memory sits outside automated gate coverage).

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
