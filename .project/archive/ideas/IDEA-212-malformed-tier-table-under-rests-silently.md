# IDEA-212: A gap between rest tiers yields ZERO required rest, silently

## Status
`CANDIDATE` — **LATENT, not live. Verified by execution across all six shipped tables (SE, 2026-07-27): every one is contiguous, so no shipped table has the gap today.**

## Summary

`_is_excluded` selects a rest tier by looping the table, with a `for/else` fall-through that guards only `total_pitches > max_tier.max_pitches` — **the TOP tier**. A pitch count landing in a **mid-table gap** satisfies neither the loop nor the fall-through, so `required_rest` keeps its initialiser of **0**.

SE executed it, narrowing LEGION's third tier to 46-55:

```
counts 56-60, GAPPED table      -> [0, 0, 0, 0, 0] days required   SILENT ZERO
counts 56-60, well-formed table -> [2, 2, 2, 2, 2] days required
```

**A malformed tier table under-rests silently rather than erroring.** A tier-boundary typo yields a zero-rest recommendation on a real arm, with a green suite and no exception.

**Benign contrast, so the fix does not over-reach**: `p=0` and negative counts also match no tier and correctly yield 0, because the fall-through's `total_pitches > 0` guard covers them. Only a *mid-table* gap is the defect.

### Epistemic status of "no shipped table has the gap"

**Measured, not assumed.** Coach believed it; SE verified it by execution across all six constants — first tier starts at 1, and every `max_pitches + 1` equals the next `min_pitches`. Those are different epistemic states and the distinction is the reason this is a capture rather than an incident. **If a future check finds a live gap, this stops being capture-for-later and becomes urgent.**

## Why It Matters

**Coach's argument, which explains the severity to someone who has not read coach's rulings file:** a gap producing zero required rest is wrong in a way that looks **identical to a confident, correct "no rest needed" answer**. No badge, no warning, nothing for a coach to notice.

Coach contrasts this with the **suppression discipline** running through every ruling it has made: the entire point of that discipline is that an absence of data should LOOK like an absence, never like a confident zero. **A silently-under-resting gap is the exact failure that discipline exists to make structurally impossible, and it currently is not.**

It also runs against the project's standing direction on under-rest: the failure is in the one direction this codebase treats as unacceptable.

**Why story 02's pins do not close it.** The pins detect a *changed value* on the two constants that get them. They do not defend the **gate**, which will keep accepting a malformed table from any source — including tables that do not exist yet. That is a different fix in kind, and it is why this is not folded into E-275-02.

**What story 02's framing SHOULD carry, though**: on `NRBL` and `PITCH_SMART_15_18`, which lack literal pins today, those pins are the only thing standing between a typo and a zero-rest recommendation. "Add literal pins for two constants" undersells the story.

## Recommended Shape

**Coach's recommendation**: a data-integrity guard at table-definition time — assert every shipped table's tiers are **contiguous with no gaps**, as a load-time check or a dedicated test enumerating all constants — rather than trusting each future table addition to get its breakpoints right by hand.

**SE's alternative, which is stronger and worth weighing against it**: make the *gate* refuse an unmatched count rather than defaulting to 0. That defends against malformed tables from any source, including ones not yet written, where a contiguity test defends only the constants it enumerates.

They are not exclusive; the contiguity assertion is cheaper and the gate change is more general.

## Rough Timing

**Coach's timing argument, which is the strongest part of the case:** this project is about to grow its table count as further governing bodies are built out, so a defense against hand-written breakpoints **earns its cost NOW rather than after the next table lands.** Coach is explicit that it is not urgent — no shipped table has the gap — but wants it written down before the next table is added, not after.

Natural carrier: the next epic adding a governing body's rule table, or any epic touching `_is_excluded`.

## Dependencies & Blockers
- None. Latent, and no shipped table exhibits it.

## Open Questions
- **Contiguity assertion, or a refusing gate?** See Recommended Shape. The second is more general; the first is cheaper and more obvious to a future contributor.
- **Should the guard also assert the first tier starts at 1?** SE's audit checked this property, but nothing enforces it, and a table starting at 2 would leave a 1-pitch hole with the same silent-zero result.
- **Is `required_rest = 0` the right initialiser at all?** A sentinel that cannot be mistaken for a real answer would make the failure loud without any table-shape check.

## Notes

Found 2026-07-27 by software-engineer while executing spec-audit finding S6 (identifying which `max_pitches` the exclusion gate reads) — a defect found beside the question rather than by it. **Not a spec-audit finding**; it is new work discovered during triage and must not be counted in the audit's accept/dismiss tally.

Filed separately from E-275 on the argument that this is a property of the exclusion gate that outlives the epic and applies to every rule table, present and future. SE, coach and team-lead independently reached the same conclusion.

**Numbering note**: this was twice referred to in-session as "IDEA-211". 211 was already taken by [[IDEA-211]] (the stale `pii-safety.md` coverage claim), filed earlier the same day. This is 212; next free is 213.

Sibling: both this and the `apps[-1]` ordering hazard below are **the exclusion gate trusting the shape of its input** without checking it.

### Two adjacent captures recorded here rather than lost in a message

1. **`_is_excluded` takes `apps[-1]` as the most recent appearance — LIST order, not DATE order.** If `build_pitcher_profiles` ever yields an unsorted `appearances` list, the wrong day is treated as most-recent and the rest calculation anchors to it. SE observed this incidentally: a `None`-pitch appearance dated *after* the last list element had its null ignored, because `apps[-1]` pointed at the earlier date. **SE did not chase whether the producer guarantees sort order** — that is the open question, and it decides whether this is live or latent.
2. **Whether Legion's published regulations actually contain the 2-in-3 consecutive-days rule the engine applies to them.** The engine applies it uniformly to Legion, NRBL and the Pitch Smart estimate (TN-7 establishes it *structurally cannot* be league-gated). Uniform application makes E-275's safety claim clean, but may be **over-strict for Legion** — the opposite direction from E-275's defect, hence not urgent. **Coach's domain, and coach has not been asked.**

Domain: SE (+ baseball-coach for the suppression-discipline framing).

Related: [[IDEA-178]], [[IDEA-211]].

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
