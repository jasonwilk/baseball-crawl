---
name: enumerate-backwards-from-the-cited-artifact
description: A broken cross-artifact edge is invisible when enumerated forward from the consumer; walk OUTWARD from the TN/idea/table and check for the inbound reference. E-276 F1/F2.
metadata:
  type: feedback
---

When auditing cross-artifact edges, enumerate **outward from the cited artifact** (a Technical Note, an idea file, an inventory table) and check whether the inbound reference it claims actually exists — do not only walk forward from the consumer.

**Why:** forward enumeration structurally cannot see this class. A consumer that never cites X looks complete: nothing in it is missing, stale, or self-contradictory. The defect lives only in the relation, and only the cited end knows it is supposed to be cited. This is also why the author of a spec cannot find it in their own work — they walk their own consumers.

Two instances, E-276 (2026-07-25):
- **TN-19** carried `Read by: … Cited by story 03 AC-6 and AC-7`. `grep -c "TN-19"` across all five story files returned **0**. Both ends were individually correct; the epic's own reading guide ("read only the TNs your story cites by number") made the note unreachable from the one story touching the constant it governs. The epic's banner even stated the note had been promoted into a numbered TN *so a story could cite it*.
- **IDEA-189** named E-276 four times ("routed out of E-276 deliberately"); the epic said only "captured as an idea" with no number, and was the only one of five E-276-filed ideas with no reciprocal `[[link]]`.

**Enumerating an edge backward is NOT verifying it backward — they are two separate greps.** This is the refinement that matters, and it splits the class in two:

| | edge ABSENT (IDEA-189 shape) | edge PRESENT and FALSE (TN-19 shape) |
|---|---|---|
| what failed | **discovery** | **verification** |
| forward walk | cannot see it — no link to walk | **does not miss it; the edge is on the list** |
| the grep | grep the **target population** for the source's id (`E-276` across every idea file) | grep the **named consumer** for the citing artifact's id (`TN-19` in story 03) |

> **The test is "does the target contain the source's NAME?" — one grep — NOT "does the target say something sensible?", which no amount of careful reading substitutes for.**

E-276's own edge-walk *did* enumerate `TN-19 → 03 AC-6/AC-7` backward. It then verified the SOURCE end (TN-19 names real ACs; those ACs carry their requirements soundly) and marked the both-ends check done. Its recorded mechanism: *"A one-way citation is not an edge. A both-ends check that walks one end is indistinguishable from a passing one — and its ✅ forecloses the re-check. An unverified edge is safer than a wrongly-verified one."*

**THIRD CLASS the name test cannot reach: the edge exists, the name resolves, and the claim about the target's CONTENT is false.** E-276 F4 — story 05 AC-9 and IDEA-187 both said the DE memory file's per-grain paragraph sat "at the bottom" / "in the last third"; it is at line 21 of 35. Every name resolved. Only opening the target and counting settles it. So: grep for discovery, grep for the name, **open the file for the claim** — and note that a fix to this class is a SWEEP, not an edit (F4's repair corrected the two artifacts named in the finding and left three copies live, including the index row and the entry stating the actionable edit).

**MY OWN FALSE CLEAN, and it is a new grep-narrowing member: a character-class EXCLUSION silently narrows across prose.** Sweeping F4 I used `(per-grain (shape|scope)|…)[^|]{0,200}(at the bottom|last third|…)` and reported **ZERO surviving**. The `[^|]` was meant to keep a match inside one table cell; this repo's prose uses `|` freely, so the pattern stopped matching across any sentence containing one — which is exactly where the live copy sat. **The clean was an artifact of my own regex.** Distinct from the markup/line-break/case/inflection members: nothing moved, and the exclusion was deliberate and looked careful. Sweep with **simple unanchored patterns, one term per invocation, no exclusions**, then read the hits. Corollary already learned the hard way: a hit that appears in your output under a *different* grep still has to be opened — I had the live copy in an earlier result and did not read it.

**A count of live copies is a count over the sites you checked.** In E-276 three parties undercounted the same claim (3, 4, and 4) and it closed only when someone refused to check the forwarded list and swept the claim's FORMS instead. Report "N copies live" as a property of your sweep, never of the claim — the seventh host, and easy to commit inside a finding about unverified claims.

**How to apply:**
1. For each TN / idea / inventory that names its consumers, grep the consumers for the source's own identifier. A zero is the finding.
2. Independently regenerate exhaustive-class claims ("two residuals were routed out", "both files should be kept") by listing the directory — never by reading the claim's own enumeration. E-276's Non-Goals said three ideas; five existed. Its banner said two research files; five existed.
3. Check the *inventory* for duplicate rows, not just missing ones — a table three consumers treat as complete is as damaged by double-counting as by omission.
4. Pre-register the fix criterion before re-verifying: a claim like "Cited by story 03" can be fixed at either end, and deleting the claim makes the epic self-consistent while leaving the routing gap open. Decide which counts as fixed *before* seeing the fix.

Companion to [[check_reachability_before_adjudicating_direction]] (the cheapest decisive check is the one nobody runs) and [[inventory_frame_omits_the_primitives_own_tests]] (recompute the inventory from the changed symbol, not from the frame handed to you).
