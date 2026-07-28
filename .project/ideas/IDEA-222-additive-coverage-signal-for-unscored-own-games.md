# IDEA-222: An additive coverage signal for a team's own unscored games

## Status
`CANDIDATE`

## Summary
A team's record correctly counts games it PLAYED, including games its own
scorekeeper never charted — but the report gives a coach no way to see that some
of those games carry no stat data from their own perspective. An additive
coverage signal would say so honestly, without removing the games from the
record. This is the constructive half of a fix that was correctly rejected in its
subtractive form.

## Why It Matters

E-278 considered adding a stat-row `EXISTS` gate to the record query, which would
have made these games invisible to the header. baseball-coach rejected it: the
record reflects games PLAYED, not games we have DATA for, and a win or loss is
derivable from a final score alone.

**The measurement behind that ruling is the material worth keeping, and it is
larger than anyone predicted.** de-epicA measured the live corpus: **20 genuine
cases across 12 of 28 subject teams**, at per-team rates of **2.4%-15.8%** of a
team's own completed games. **17 of the 20 have plays recorded from the OPPOSING
perspective** — the game was played and charted by somebody, just not by this
team. Had the gate shipped, twenty real games with real final scores would have
silently vanished from twelve coaches' records.

So the coverage signal has real material to describe — between 2% and 16% of a
team's own games — rather than a null set. That is what makes it worth building
eventually: a coach reading a record has no way today to tell a fully-charted
season from one with a sixth of its games uncharted, and both render identically.

**Two methodology notes worth more than the number**, because either would cost a
future session a wrong answer:

1. **The obvious narrow framing returns 1 and is wrong.** Restricting the query
   to games carrying a `game_perspectives` row systematically excludes the
   population being counted, because that row is written *after* stat data loads.
2. **10 of the raw 30 were duplicate artifacts.** An uncollapsed twin necessarily
   produces two such entries, since each row holds one side's stats — so the raw
   count must be de-duplicated before it means anything.

## Rough Timing

No urgency. Reasonable triggers: a coach asks why a record looks fuller than the
stats behind it; the reports surface grows a data-completeness or trust element
that this would naturally join; or E-278's fixes land and the duplicate-artifact
share of the raw count changes enough to be worth re-measuring.

## Dependencies & Blockers

- [ ] None technical. The measurement exists and the record semantics are settled
      (E-278 TN-7, binding coach ruling).
- [ ] Needs a product decision on the surface, not more investigation — whether a
      coverage signal belongs on the report at all, and where.

## Open Questions

- Does a coach actually want this surfaced, or is it operator-facing? The
  operator-vs-coach honesty split in `.claude/rules/architecture-subsystems.md`
  (Reports Package) is the relevant precedent — per-stage degradation surfaces to
  operators only, never the coach footer.
- If coach-facing, does it join the existing "Through [date] (N games)" freshness
  line rather than becoming a second number? `.claude/rules/data-model.md` is
  emphatic that two different game counts on one report erode trust, and the
  data-bearing-coverage principle already governs that line.
- Is the right signal per-team, per-game, or a single season-level note?
- Should the 17-of-20 fact (charted from the opposing perspective) be used —
  i.e. can the report say the game *is* charted, just not by this team?

## Notes

Captured at baseball-coach's request during E-278 planning review: the OQ-2
measurement lives in `epics/E-278-game-identity/epic.md`, which archives with the
epic, and the 20-cases-across-12-teams figure is real measured material a future
session would otherwise re-derive.

Deliberately NOT a story in E-278 — that epic fixes defects, and this is additive
capability. It is the constructive counterpart to the rejected `EXISTS` gate:
same underlying observation, opposite treatment. **Do not let a future reader
mistake this for a re-proposal of the gate** — the ruling that the record counts
games PLAYED is binding and this idea does not disturb it.

Related: [[IDEA-217]] (the record-header defect that started E-278).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
