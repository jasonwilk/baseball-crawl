# IDEA-217: The record header counts games every other surface excludes

## Status
`CANDIDATE` — **live on production and dev, coach-facing, and the header fix is measured to need zero data cleanup.**

## Summary

`_query_record` (`src/reports/generator.py:396-422`) filters games on three things only: `season_id`, the team appearing as home or away, and both scores being non-NULL. Every other surface that counts games requires a **data-bearing, perspective-scoped stat child** — `_query_freshness` (same file, `:589-633`) gates on `EXISTS (player_game_batting … WHERE perspective_team_id = ?) OR EXISTS (player_game_pitching … same)`, and the game logs do the equivalent.

**Confirmed by reading both queries, not relayed.** So the record header counts a strictly wider set than the footer's "Through {date} (N games)" and the game logs beneath it, and a `games` row with scores but no stat rows from our perspective inflates the header alone.

On dev the set difference is **exactly 2 rows, both losses**. Both are genuine bad rows with distinct root causes, filed separately as [[IDEA-218]] and [[IDEA-219]] — but **fixing the header does not depend on either of them being cleaned up**, which is the useful part of this capture.

### The measurement

Adjudicated against GameChanger's own public data by api-scout, so GC is the arbiter rather than two of our environments disagreeing:

| source | record |
|---|---|
| GameChanger, 40 games | 25-15-0 |
| live report header | 25-16 |
| dev report header | 25-17 |

Production carries **one** of the two phantom rows; dev carries both.

**The probe replayed `_query_freshness`'s perspective-scoped `EXISTS` clause into `_query_record` on dev and it yielded the GC-correct record with zero data cleanup.** That is the whole argument for treating the header as its own fixable defect rather than waiting on row-level repair.

## Why It Matters

The win-loss record is the first thing a coach reads on the card, and it is the number they can check against their own memory in two seconds. A header disagreeing with the game log directly underneath it — and with what GameChanger shows — costs trust on the surface where trust is cheapest to lose. `.claude/rules/data-model.md` states the project principle it violates: **one honest count and one honest date everywhere**; two different game numbers on a report erode trust under pre-game pressure.

The deeper reason to fix the query rather than only the rows: **this is a data-bearing-coverage violation of exactly the shape that rule already names.** A completed `games` row can legitimately exist with zero stat rows — an opponent with a public final score and no GameChanger scorebook is the *modal* scouting case, not an edge case. So the header is not merely wrong about two rows today; it is structurally counting a population the rest of the report has already agreed to exclude, and any future row of that shape lands in it silently.

Note the direction: both phantoms are **losses**, so the header currently understates the team. Nothing about the mechanism guarantees that — it counts any scored row, in either direction.

## Rough Timing

**Promote or fold into the next epic touching `src/reports/generator.py`'s query layer.** Small and self-contained: one `WHERE` clause brought into line with a sibling query fifteen functions down the same file, plus a test.

It should be sequenced ahead of, or independently of, the row-cleanup work in [[IDEA-218]] and [[IDEA-219]] — those are genuinely separate problems with their own remedies, and the header is correct after this change whether or not they are ever done.

## Dependencies & Blockers
- [ ] None. The replacement clause already exists in the same module and the replay was executed.

## Open Questions

- **Is the perspective-scoped `EXISTS` the right predicate for a RECORD specifically, or only for coverage?** They are not obviously the same question. A game we genuinely played and lost, whose boxscore was never scored in GameChanger, is a real result the coach would expect counted — and this fix drops it. On the observed data that case does not arise (the excluded rows are both bad rows), but **the fix is being justified by an outcome rather than by an argument, and that gap should be closed before it ships.** Ask baseball-coach: should the record reflect games played, or games we have data for?
- **Should every game-counting surface be routed through one helper?** There are now at least three predicates over `games` in this file that ought to agree. The canonical-seams principle says the second path is the defect; whether a shared helper is worth it here or is over-building for three call sites is a judgment call.
- **Adjacent observation, from reading the query rather than from the audit — a TIE is counted as neither a win nor a loss and is invisible.** `_query_record` sums two CASE expressions on strict `>` and `<`, so equal scores fall through both. GameChanger reports a third component (the team's record is `25-15-0`). **Inert today at zero ties, and NOT part of the audit's finding** — recorded so a future reader does not have to re-derive it, and so nobody "fixes" it as though it were live.

## Notes

Found in the four-agent live-vs-dev report evaluation on 2026-07-26/27. The header discrepancy was the entry point; the two phantom rows were found by taking the set difference between the two predicates and then adjudicating each row against GameChanger.

**Deliberately split from its causes.** [[IDEA-218]] (a dedup natural-key gap) and [[IDEA-219]] (a cross-team mis-attribution at ingest) each survive this fix and each affect surfaces beyond the header, so folding all three into one capture would let whoever picks up the carrier epic do one and consider the matter closed.

**⛔ Row cleanup is out of scope here** and must not be attempted as part of the header fix — the twin needs the canonical `merge_duplicate_game` seam, the phantom needs a deletion, and both are destructive operations on production data requiring their own justification.

Related: [[IDEA-218]] (the twin), [[IDEA-219]] (the phantom), [[IDEA-220]] (a double-load found in the same pass), [[IDEA-221]] (display defects from the same evaluation), [[IDEA-196]] (roster residue on the same production report).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
