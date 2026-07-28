---
name: seam-partial-inheritance
description: Declining to reuse a seam is not all-or-nothing — you also decline the parts your reasons never covered. Plus: a value that PARSES is neither absent nor unparseable, so an `except ValueError` fail-closed promise does not cover it.
metadata:
  type: project
---

# Declining a seam declines the parts your reasons never covered

**The rule:** when you decide NOT to reuse a canonical seam, your reasons cover
some of what that seam does and are silent about the rest — and the rest gets
dropped anyway. **Enumerate what the seam actually does, and rule on each part.**
Deciding at the level of "reuse it / don't" throws away the pieces your argument
never mentioned.

**Why (E-278-02, 2026-07-28).** I declined to reuse `derive_local_date` inside a
new `_parse_instant` helper, on two grounds that were both correct:

- a delta is **zone-independent**, so that seam's fail-closed refusal on an
  unresolvable zone would be inherited for nothing (and would have silently
  disabled dedup for rows whose zone GC spelled unusually); and
- (the reviewer's stronger ground) it returns `str | None` — a `"YYYY-MM-DD"`
  string — so **a sub-second delta cannot be computed from its output at all**.
  Reuse was impossible, not merely inadvisable.

Both true. Neither says anything about `derive_local_date`'s naive-datetime
normalization (`if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)`) —
and that one line was the thing I needed. Without it, `_is_same_listing_delta`
**raised `TypeError`** on a naive/aware pair. In the reviewer's framing:
normalization is *the one thing* that helper should have inherited.

**The tell:** an argument of the form "that seam is about X, this is about Y."
It licenses skipping the seam; it does not license skipping the seam's
*incidental hygiene*, which is usually where the hard-won edge cases live.

## A value that PARSES is neither absent nor unparseable

Same incident, and it is why the defect survived a docstring that promised
otherwise. `_parse_instant` caught `ValueError` and the docstring said *"fails
CLOSED: an absent or unparseable instant returns False."*

`datetime.fromisoformat("2026-07-25")` returns `datetime(2026, 7, 25, 0, 0)` —
**a bare date parses cleanly.** So it is neither absent nor unparseable, no
`except ValueError` can see it, the promise never covered it, and the failure
landed one layer later at the subtraction.

**Generalize: a fail-closed promise scoped to "absent or malformed" does not
cover parseable-but-INCOMPATIBLE.** The dangerous input is the one that gets
past the parser and fails on use. Write the guarantee as a property of the
RETURN (here: "returns an aware datetime unconditionally, so arithmetic on two
of these cannot raise") rather than as a list of inputs you thought of.

**Blast radius is worth pricing separately from likelihood.** This shape was
unobserved on the wire (GC renders `...Z`), but `ScoutingLoader`'s per-game loop
has no `try`/`except` around `load_payload`, and `load_payload` commits per
game — so the raise would have left earlier games committed and **abandoned the
rest of that team's scout**. A silent partial crawl, not a wrong number. Cheap
to prevent, expensive to diagnose.

## How both were caught

**By CONSTRUCTING INPUTS, not by reading.** The reviewer built a 7-shape matrix
and ran it; nothing in the code or its docstring looks wrong to a reader,
because the docstring describes the intent accurately and the intent was
incomplete. This is the same detection asymmetry as [[softened-absolutes]] —
execution catches what re-reading cannot, and it catches it from outside the
author's framing.

Companion test to write when a helper claims to be total: run the full
cross-product of every input SHAPE (absent, empty, malformed, bare date, naive,
aware, aware-with-offset) and assert only that it does not raise. Cheap, and it
fails loudly the moment someone re-narrows the guarantee.
