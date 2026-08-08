# IDEA-215: `ReclaimResult`'s docstring describes intent, not outcome

## Status
`CANDIDATE`

## Summary
`ReclaimResult`'s class docstring in `src/reports/lifecycle.py` says its three count
fields *"count the rows removed."* **All three are computed BEFORE the deletes and
describe the INTENDED target, not the observed outcome.** Correct the docstring; do not
touch the fields.

## Why It Matters

**Three fields, TWO failure modes — not three, and not one.** This distinction is the
whole reason a blanket correction is unsafe:

- **`teams_deleted` and `players_deleted` are SET SIZES.** They are assigned
  `len(team_ids)` and `len(player_ids)` — the cardinality of the computed orphan id
  set. **A set size cannot go red on an under-delete**: if the DELETE removes fewer rows
  than the set contains, the field still reports the set's size. This is exactly the
  vacuity E-277 story 03 surfaced against AC-1, one layer over.
- **`roster_rows_deleted` is a REAL `COUNT(*)`** — `_orphan_roster_row_count(conn)` —
  but it is taken **before** the team tier deletes those rows, under a comment that says
  so. It is an accurate count of a population that is about to be removed, not a
  measurement that it was.

**So the tempting one-line fix is FALSE.** *"These are set sizes"* is true of two fields
and **wrong about `roster_rows_deleted`**, which is a genuine query. The accurate
unifying sentence is about **timing and intent**, not about mechanism: all three are
computed pre-delete and report what the sweep set out to remove.

This is a **prose defect in a safety-adjacent surface**. `reclaim_orphan_reference_data`
hard-deletes `teams`, `players` and `team_rosters`; a reader auditing whether a sweep
did what it claimed will reach for these fields, and the docstring tells them the fields
answer a question they do not answer.

## Rough Timing

**Fold-in, no epic of its own.** The next story or epic that touches `lifecycle.py`
docstrings takes it. There is no urgency: the fields are correct for what they are, the
counts are right in ordinary operation, and nothing miscomputes.

## Dependencies & Blockers
- [ ] None. Independently actionable, and small.

## Open Questions
- Is a docstring correction sufficient, or should `teams_deleted` / `players_deleted`
  become real post-delete rowcounts? **Prefer the docstring.** Changing the quantity is
  a behavioural change to a shipped result object with an exit-code consumer
  (`scripts/reclaim_orphan_reference_data.py` keys on `deferred`, not on counts), and
  E-277 deliberately declined to make that change on the strength of a review finding.
  **This idea is NOT authority for a rowcount change** — if someone wants one, it needs
  its own justification.

## Notes

**⚠ TWO HAZARDS FOR WHOEVER PICKS THIS UP. Both cost real time in E-277 and neither is
visible from the docstring itself.**

1. **THE PHRASE WRAPS. `grep "count the rows removed"` RETURNS EMPTY.** In the source,
   `count the` ends one line and `rows removed` begins the next, so no contiguous match
   exists. **Discriminate by the `ReclaimResult` symbol, not by the sentence.** A
   searcher who greps the phrase and finds nothing will conclude the defect is already
   fixed. This is the same line-wrap inversion recorded in
   `.claude/rules/tool-output-integrity.md` — the failure mode there is an EMPTY that
   trips the cross-check reflex, and here it would read as "already done."
2. **The "three fields wrong in three different ways" framing that circulated during
   E-277 closure is an OVER-COUNT and was corrected at the point of filing.** It is two
   modes across three fields. Recorded because the wrong framing is the more memorable
   one, and it would send someone hunting for a third distinction that does not exist.

Surfaced during E-277 (2026-07-27) as a fold-in candidate. **Deliberately NOT folded
into story 03**: no AC covered it, `cr4` had already approved that story against its
ACs, and widening the diff after approval would have voided the scope the approval
covered. Filed rather than built, on that reasoning.

Related: `.claude/rules/canonical-seams.md` (reclamation seam);
`.project/ideas/IDEA-198-two-unsynced-team-pin-enumerations.md` is a DIFFERENT problem in
the same module — pin-enumeration drift, not docstring accuracy — and the two were
deliberately kept as separate files so neither is buried under the other's title.

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
