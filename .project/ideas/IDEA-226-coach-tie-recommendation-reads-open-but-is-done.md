# IDEA-226: baseball-coach's tie recommendation reads as open but has shipped

## Status
`CANDIDATE` — **routed to baseball-coach; nobody else may fix it.**

## Summary

`.claude/agent-memory/baseball-coach/` carries a recommendation that the invisible-tie
defect **"SHOULD HAVE been fixed in the same touch."** It has now been acted on:
**E-278-01 shipped it** — `_query_record` returns `{"wins", "losses", "ties"}` and both
coach-facing render sites show three dash-separated integers, with the trailing `-0` always
present and never conditionally suppressed, per baseball-coach's own display-format ruling.

So the section reads as an **open recommendation for completed work**. Found by
code-reviewer's Step 1a invariant audit at E-278 closure; baseball-coach was not on that
dispatch team, and the own-memory carve-out reserves the directory to it.

**SECOND SITE, added 2026-07-28 at the archive rename — a DEAD PATH, not a stale claim.**
`.claude/agent-memory/baseball-coach/idea-217-record-header-consultation.md:93` cites
`epics/E-278-game-identity/epic.md`. That path **no longer resolves**: the epic COMPLETED and
was archived to `.project/archive/E-278-game-identity/epic.md`. It is a **citation** — a
reader is meant to follow it to the evidence behind the ruling — so it should be **repointed**
rather than annotated, unlike the recommendation above.

Both sites are in the same agent's memory and should be fixed in one pass. Note they are
different defect classes and take different fixes: the recommendation above is **stale
content** needing a status annotation; this one is a **broken pointer** needing a new
address. A pass that treats them alike will get one of them wrong.

## Why It Matters

This is the mildest of the three memory-decay findings and it is worth filing for a reason
that is not severity: **an open recommendation is an action item.** The next time
baseball-coach is consulted on record semantics it may re-raise a fix that shipped, costing
a round trip and — worse — inviting someone to "fix" it a second time in a different shape.
A stale *fact* misinforms; a stale *recommendation* solicits work.

There is a related shape already recorded elsewhere in this family: `IDEA-217:49` carried a
caution reading *"so nobody 'fixes' it as though it were live"* about this very tie defect —
**and that caution outlived the fix it was guarding against.** A guard against premature
action is itself a claim with a shelf life.

## Rough Timing

**Next time baseball-coach is spawned for any reason.** Trivially small; should ride whatever
brings the agent back rather than justify its own dispatch.

## Dependencies & Blockers
- [ ] **Requires baseball-coach.** Own-memory carve-out.

## Open Questions

- **Is there anything worth PROMOTING from the ruling rather than just marking it done?**
  E-278 TN-7 is a binding domain ruling with a measured basis — 20 genuine
  completed-and-scored games across 12 of 28 teams carry no stat rows from their own
  perspective, so a stat-row coverage gate on the record would have silently deleted real
  games from twelve coaches' records. **That measurement is more durable than the tie fix**
  and may be worth holding in coach memory as the standing argument against coverage gates
  on outcome-derived numbers, rather than only as a closed recommendation.

## Notes

Found 2026-07-28 by code-reviewer during the E-278 Step 1a invariant audit — reached by
**synonym expansion** (step 2 of `.claude/rules/doc-sweep.md`), not by token grep. Same
defect class as [[IDEA-224]] (data-engineer) and [[IDEA-225]] (api-scout).

The display-format half of the ruling is worth restating in whatever correction lands,
because it is the part most likely to be re-litigated: showing the trailing `-0` matches
GameChanger's **display convention**, and that is a decision about FORMAT only. It is **not**
a decision to match GameChanger's NUMBER — E-278 TN-16 established by execution that a GC
profile record is a raw count of that team's own schedule listings, so on a team with a
double-listing, matching GC would mean reproducing GC's error.

---
Created: 2026-07-28
Last reviewed: 2026-07-28
Review by: 2026-10-26
