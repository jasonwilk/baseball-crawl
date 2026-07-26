---
name: inventory-frame-omits-the-primitives-own-tests
description: A churn/regression inventory drawn over CONSUMER test files systematically omits the shared primitive's OWN test file — recompute the inventory from the changed SYMBOL, and check whether a headline test count equals the consumer files exactly.
metadata:
  type: feedback
---

When a spec claims "N existing tests stay green, only mechanical churn at M call sites", **recompute the inventory from the changed SYMBOL (`grep -rl <module>` / `grep -rn "<func>("` across all of `tests/`), never from the story's file list** — and then check whether the headline N equals the consumer files *exactly*. If it does, that equality IS the frame, and whatever it excludes is where the unsatisfiable AC lives.

**Why:** E-276 (spec audit, 2026-07-25) changed `crawl_is_authoritative`'s semantics (a vacuous-permit rule). Its inventory named three grain-level test files and "9 direct call sites", and the epic's headline was "the 72 existing reconcile tests stay green with no assertion changed". Collection showed the three grain files hold 34+20+18 = **exactly 72** — so the primitive's own `tests/test_reconcile_at_load.py` (19 tests, 13 direct calls to the changed function) was outside every frame in the document. That file asserts `crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=0) is False`, which is precisely the input the change inverts. Two ACs were unsatisfiable as written and nobody had looked, through four expert passes, because the primitive is not a "grain" and the inventory was organised by grain.

The same frame recurred twice more in one document: a divergence probe reported "295 player-line + 153 game-grain calls, 0 divergences" and the conclusion was stated for *all* existing tests — reading the probe source showed it patched only two of three grains; and a parameter sweep's "222 diverging shapes" turned out (by its own author's later retraction) to be a function of the sweep bounds, where the bound-free answer was 3.

**How to apply:**

1. On any spec claiming a bounded blast radius, run the discovery yourself and diff YOUR list against the claimed one. Cheapest decisive check: `pytest <claimed files> --collect-only -q` and compare the total to the spec's headline number. An exact match is a signal, not a reassurance.
2. Consumer-organised inventories (by grain, by route, by caller) drop the shared thing they all consume. Ask explicitly: *what does the changed symbol's own test file assert about it?*
3. Treat a reported measurement as scoped to the population that was instrumented — **read the probe/plugin source for what it patches**, not the sentence reporting it. "0 divergences across the three files" was true and covered two of three grains.
4. A count from a parameter sweep is a claim about the sweep's bounds. Demand the bound-free characterization (the derived inequality), which is smaller, complete, and unattackable.
5. **Establish the UNIT of each number before comparing two sweeps: shapes, or combinations?** A constraint that bounds the shape space (`a < b <= 2` gives pre-load roster `p <= 3`) says NOTHING about how many swept parameter combinations realise those shapes, because the other axes — new-id count, churn count, live size — still range freely. So a count and a characterization are different units and are not comparable, and two sweeps that disagree are usually answering two questions. Name the populations and the units; do not reconcile the numbers.

   **I got this exactly backwards first, and the correction is the memory.** I wrote here that "a count that SCALES with the sweep range cannot be carrying a constraint that would hard-bound it", called it decisive, and it was relayed twice as settling the E-276 20-vs-222 gap. It is FALSE — a category error between shape-count and combination-count. DE's four counts fit `c(n) = (3n-2)(n-1)/2` exactly at n = 4, 5, 9, 13 → 15, 26, 100, 222, so a cap-carrying sweep demonstrably can scale with range.

   **The counterexample was in my own hands while I wrote the rule.** In the same session I read SE's sweep, confirmed from its source that it applies the cap (`cap_ok` in both sides of the divergence test), executed it, and reported that its count moved 20 → 26 → 44 across ranges while its shape set stayed byte-identical at 3. That IS a cap-carrying sweep whose count scales with range. I verified the negation and generalised the rule anyway, because I was pointing the rule at a different sweep than the one I was looking at. **When you state a general rule, test it against the case in front of you before the case you are arguing about.**

   Two second-order notes. Refuting the inference does NOT establish the positive claim it was used against — "DE's sweep carried the cap" remains unresolved, and asserting it would be the fourth wrong account of one disagreement. And this arrived as the *correction of a correction*: see `.claude/rules/tool-output-integrity.md` ("a verdict's stated REASON rots independently of the verdict"; the retraction case). The verdict — no number ships — was right through all three accounts, which is exactly why nobody re-opened the reason.

Companion to [[ratio_gate_population_claims]] (my own falsified population claim) and [[closure_diff_growth_after_integration_review]] (re-measure at the gate rather than trusting the earlier scope).
