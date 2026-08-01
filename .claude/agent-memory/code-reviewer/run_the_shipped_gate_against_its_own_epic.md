---
name: run-the-shipped-gate-against-its-own-epic
description: MEASURED — when an epic ships a gate/hook/check, execute it against that epic's OWN closure diff; E-279's archive gate exit-1 blocked E-279, and only a known-present control proves the exclusion that bounds the hit list.
metadata:
  type: feedback
---

When an epic ships a **gate** — a pre-commit hook, a check script, a predicate — run it
against **that epic's own closure** before approving the diff. The epic is the gate's
first subject and the one nobody tests it on.

**Why:** E-279 shipped `scripts/check_archive_refs.sh` plus a `.githooks/pre-commit`
trigger keyed on a staged `D` under `epics/E-NNN-` **and** an `A` under
`.project/archive/E-NNN-` for the same ID. E-279's own closure produces exactly that
pair. One command settled it:

```
$ bash scripts/check_archive_refs.sh E-279
[archive-refs: BLOCKED] surviving references to <pre-archive path ELIDED — see below>
                                                                     → EXIT=1
```

**The elision in that transcript is itself the lesson.** My first draft quoted the gate's
output verbatim, which spelled the live path — so **this memory file became a new gate hit
at the moment I wrote it**, in the same pass where I was reviewing that exact defect
class. Caught by running the sweep against my own write before reporting frozen. The
epic's standing operator cost is real and it lands on the author immediately: **write
closure-window memory entries without spelling the pre-archive path in the first place**;
it is cheaper not to create the hit than to sweep it.

The epic's own History said the class was anticipated and **"nobody ran the predicate
against E-279 ITSELF."** The hook documents no override — `git commit --no-verify` is the
only escape and it disables the PII scan too — so the difference between finding this at
integration review and at the commit is *a reword* versus *disabling the safety gate*.

**How to apply:** at any closure/integration pass, ask "does this epic ship a check whose
trigger this epic's own closure satisfies?" If yes, execute it. Reasoning about whether it
will fire is not this check — the trigger conditions are cheap to satisfy accidentally,
and the gate is the only thing that reports honestly.

**The bound, and it is half the value: a raw hit count is worthless until you have proved
the EXCLUSION.** The gate excludes `.project/archive/`, which is what makes the epic's own
`epic.md` hits self-clear at the rename. To verify an exclusion filter, run the instrument
on a case where the excluded thing is **known present** — I used already-archived E-243:
6 hits (proving the traversal ran) while dropping all three `.project/archive/E-243-*`
files a naive `grep -rlIF` sees. **Liveness and relevance are separate properties and one
control can carry both**: non-zero hits prove it ran, the specific absence proves the
filter works. Without that control, "4 remaining sites" is an unexplained number, not a
verified absence — see [[regenerate_the_population_not_the_pair]].

**Do NOT let the gate's red drive a sweep.** E-279's hits split criterion-versus-evidence,
and the epic supplied a third remedy I had not considered: for an EVIDENCE site, **reword
so the line does not SPELL the dead path** — preserving the record without repointing it.
I first read the situation as a two-way dilemma (edit records, or stay blocked) and was
wrong. Related: [[gate_behavior_needs_the_executable]],
[[new_gate_inherits_hook_enumeration]], [[closure_diff_growth_after_integration_review]].
