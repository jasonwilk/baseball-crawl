---
name: feedback-record-shrinkage-dont-substitute
description: "When an epic retires a gate/check, do not manufacture a replacement to preserve symmetry — verify a property still EXISTS to check, and if not, record honest shrinkage as the trigger-7 offset."
metadata:
  type: feedback
---

When an epic retires a gate, check, or command, do NOT reach for a "clean semantic swap" that installs some other artifact into the vacated slot. First ask whether the property being checked still **exists**. If it does not, the correct move is a **plain deletion** plus an honest record that the checkable surface shrank.

**Why:** In E-259 planning I proposed that retiring `bb report verify-aggregates` be framed as a "clean semantic swap" substituting `bb report reconcile-scoreboard` into its slot. **Both DE and CA overruled it**, on three independent grounds:
- `reconcile-scoreboard` does not *move into* the vacated slot — it was already there (a separate, unconditional check). Nothing was substituted.
- The check does not become *vacuously true* (my word); it becomes **unrepresentable** — post-cutover there is no left-hand side. Stored-vs-recomputed has no meaning once the aggregate IS the query.
- The remaining golden-report test is a **regression** guard, not an **integrity** guard: it proves new SQL returns what old SQL returned, and cannot prove either is right. Presenting it as a replacement integrity check overstates it.

The pull toward substitution is an aesthetic one — a deleted gate *feels* like a hole that wants filling, and "swap" sounds more defensible to a reviewer than "we now check less." But net context-layer shrinkage is a legitimate, *desirable* outcome: it is precisely what context-layer-assessment **trigger 7** (context-growth counterweight) asks epics to produce. Manufacturing a replacement converts a real offset into fake symmetry and leaves a misleading record.

**How to apply:** Any epic that deletes a command, rule, hook, gate, or checklist item:
1. Ask: does the property this checked still exist post-change? If no → plain deletion.
2. Do not describe the deletion as a swap/substitution unless something genuinely *moves* into the slot. "Already present and unconditional" is not a substitution.
3. Distinguish **regression** guards (this behaves as it did) from **integrity** guards (this is correct). Never let one stand in for the other in an AC or a Technical Note.
4. Record the shrinkage as the trigger-7 offset in the epic's History. That is the win, not something to apologize for.

Deletion-side eviction is invoked by triggers **7 AND 8** (I mis-attributed it to 8 alone; CA corrected this). Related: [[feedback_dont_rationalize_weak_assertions]] — the same instinct to rationalize a check into looking stronger than it is. See also [[feedback_verify_cited_facts_before_approving]].
