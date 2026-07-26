# IDEA-190: Replace the vacuous-permit calibration paragraph with an executable caller-set pin

## Status
`CANDIDATE`

## Summary

`crawl_is_authoritative`'s `permit_empty_prior` Args entry carries a **calibration paragraph** about which grains reach `prior_count == 0`. That paragraph has now been **wrong twice, in opposite directions, about the same question**, inside a single epic:

1. It overstated that **no** grain reaches `prior_count == 0` in production ("applying it unconditionally would not widen anything").
2. E-276 then falsified it from the other side — story 02 made the **game** grain reach that input, and story 03 **removed the roster floor** entirely.

Software-engineer proposed replacing the prose guarantee with an executable one:

> `crawl_is_authoritative` has exactly N callers in `src/`, and every one passes `permit_empty_prior=True`.

An AST walk over `src/db/reconcile_at_load.py` collecting `Call` nodes for that name, asserting the caller set and that each carries the keyword. **~25 lines, test-only, no production change.** SE reports it **would have failed on both previous versions of the paragraph.**

## Why It Matters

**This is not a cosmetic prose problem.** The paragraph is a *safety calibration*: a future editor who acts on the stale version removes story 01's opt-in guard, which is why code-reviewer rated the current instance a MUST FIX rather than a nicety.

**And the failure mode is the one this project has the most evidence about**: a claim that is true when written, falsified by a change elsewhere, and unmodified — so no sweep finds it and re-reading confirms it. A twice-rotted paragraph guarding a live safety property is the strongest available candidate for converting prose into a check.

## Rough Timing

**Promote when anything next touches `crawl_is_authoritative`'s caller set or that calibration paragraph** — that is exactly when the pin pays, and exactly when someone already has the context. Also promote if a third rot of the same paragraph is found.

No urgency otherwise: the paragraph is correct as of 2026-07-26, and the pin guards against a future edit rather than a present defect.

## Dependencies & Blockers

- [ ] None. The caller set is stable once E-276 closes; the test needs the post-epic set, not the mid-dispatch one.

## Open Questions

- **Is an AST walk the right instrument, or is a simpler grep-based assertion enough?** SE proposed AST; nobody has compared. An AST walk is precise but is itself code that can rot against a syntax change.
- **Should the pin assert the caller COUNT, or only that every caller passes the keyword?** A count is a hardcoded number over a growing population — **the exact defect E-276 hit four times** (`4207`, "Both prose sites", "plus one this story adds", TN-13's roster row). **Prefer the universally-quantified form with no count.** This question is nearly self-answering and is recorded so the answer is not re-derived.
- **Does the pin belong beside the primitive's tests or in a structural/meta test file?** The codebase has precedent for both.

## Notes

**Deliberately NOT taken into E-276, and the reasoning should survive** — this was a scope call, not an oversight:

- **Story 03 was mid-review at the circuit breaker**; adding scope would have invalidated an in-flight review and forced a third round.
- **Story 04 is a clean single-purpose slice** (one run-2 id-churn variant in the existing end-to-end class). A structural AST test is a different file, a different kind of test and a different subject; bolting it on would give that story two unrelated deliverables.
- **Story 05 is context-layer prose, routed to claude-architect** — the wrong agent and the wrong tree for a `tests/` file.
- **A sixth story for ~25 lines is thin**, and "simple first" argues against manufacturing one to host work no acceptance criterion requires.

**⚠️ And the strongest argument FOR taking it in-epic does not survive checking, which is why it is recorded here.** It was proposed as serving E-276's fifth goal — *"leave the gate's invariant stated in a form that would catch this defect rather than pass it."* **Read literally, that goal's subject is the gate's INVARIANT** (the population/timing claim TN-10 restates). **This pin guards a caller-configuration calibration, which is adjacent to that invariant rather than an instance of it.** So the pin does not discharge goal 5, and E-276 should not be recorded as having left goal 5 undischarged for want of it. *(If the operator wants goal 5 itself pinned executably, that is a different and larger question than this idea.)*

**Credit**: proposed by software-engineer during E-276-03 round 2, which **correctly did not add it** — the round was scoped to the AC-9 sites plus the hardening, and this is neither. Restraint plus a written proposal is the behaviour that makes an idea like this survivable.

Related: [[IDEA-187]] (the same invariant stated in a superseded form in another artifact) and [[IDEA-189]] — all three concern a claim about this gate that outlived the code it described.

---
Created: 2026-07-26
Last reviewed: 2026-07-26
Review by: 2026-10-24
