---
name: idea-217-record-header-consultation
description: Ruling on IDEA-217 -- record header must count games PLAYED (score-based), never gated behind stat-row EXISTS; asymmetric-detectability and diagnostic-value arguments
metadata:
  type: project
---

# IDEA-217: record header semantics ruling (2026-07-27)

## The question

`_query_record` (`src/reports/generator.py:396-422`) counts any completed game with
non-NULL scores. Every other game-counting surface on the report (`_query_freshness`,
game logs) additionally requires a data-bearing stat row from our own perspective
(`perspective_team_id` EXISTS on `player_game_batting`/`player_game_pitching`). Two bad
rows (a dedup twin, IDEA-218; a cross-team misattribution, IDEA-219) inflated the header
to 25-16 (prod) / 25-17 (dev) against GameChanger's own 25-15-0. Replaying the
data-bearing predicate into the record query fixes it with zero data cleanup, but would
also drop a genuinely played-and-lost game that GameChanger never got a scorebook for --
the modal shape for a scouted opponent, and (per the "any GameChanger team" reports-first
scope) a real possibility for the report's *subject* team too, not just an opponent.

## Ruling: games PLAYED, not games with DATA. Do not adopt the EXISTS gate for the record.

Reasoning, strongest arguments first:

1. **Asymmetric detectability.** An over-counted record (today's bug: two extra losses)
   is a *visible*, cross-checkable discrepancy -- it disagrees with the footer/game-log
   count directly below it, which is exactly how this defect was found in the first
   place. An under-counted record (a genuine loss silently dropped because nobody
   charted it) leaves **no trace anywhere on the page** -- header, footer, and game log
   would all agree, and all be wrong relative to ground truth. A coach or operator can
   catch and question the first kind of error; nobody can catch the second kind by
   looking at the report. Design for the failure mode nobody can see.

2. **The record is not a rate stat.** OBP/K/9/etc. are undefined without per-PA data --
   there is no "OBP" if no plate appearances were recorded, so the coverage gate is
   correct for those. A win or loss is derivable from the final score alone; a coach
   knows they lost 5-3 with or without a box score. Importing a stat-coverage
   requirement onto a fact that never needed one is a category error, not a
   consistency fix.

3. **The header/footer disagreement is valuable telemetry, not just tolerable
   inconsistency.** IDEA-217 itself was discovered *because* the record and the
   data-bearing count diverged. Homogenizing both queries onto the same predicate
   destroys that live self-check for every future phantom/duplicate/misattributed game
   -- a future bad row of this shape would then pass through both surfaces silently,
   with no visible mismatch to alert anyone. This is the same principle as keeping
   `bb report reconcile-scoreboard` a diagnostic rather than folding it into a gate
   (`.claude/rules/canonical-seams.md`, Reconciliation-scoreboard conventions) --
   divergence measured on purpose beats divergence engineered away.

4. **Directionality is not guaranteed.** Both current phantom rows happen to be losses
   (header currently looks worse than reality). A future phantom could just as easily be
   a win, and the "fix" would then be masking an inflated record instead of a deflated
   one -- the coverage gate doesn't reliably point in the safe direction either way.

## On the cleanup-independence framing in IDEA-217

IDEA-217 explicitly and correctly splits row cleanup (IDEA-218 twin via
`merge_duplicate_game`, IDEA-219 misattribution) out of the header-fix decision --
both are destructive ops needing their own justification, and the header question is a
semantics question independent of when/whether they land. I agree with keeping them
split. Where I differ from the "ship the EXISTS gate now, zero cleanup needed" framing:
that convenience is what makes the coverage-gate proposal attractive, but it's the wrong
lever. **The actual fix for a wrong number today is removing the two bad rows** (the
scoped, separate work), not narrowing what "played" means project-wide to paper over
them. Narrowing the definition fixes today's two rows by coincidence and creates a
durable blind spot for every future one.

## Ties (adjacent, inert)

`_query_record`'s CASE pair uses strict `>`/`<`, so an equal score is counted as neither
a win nor a loss (GC reports a third component: `25-15-0`). Zero ties in current data,
not part of this ruling's live cost, but SHOULD HAVE fixed in the same touch if the query
is being edited for the ties reason alone -- cheap, same file, avoids a silent
undercount-of-total-games the day a tie actually occurs.

## On a shared game-counting helper (IDEA-217's second open question)

Do not unify `_query_record` and `_query_freshness` behind one predicate. They measure
different things on purpose (played vs. data-bearing coverage) -- a shared helper should,
if built at all, take the predicate as a parameter rather than force one answer. Whether
that's worth building for two-three call sites is an engineering/over-engineering call,
not a coaching one.

See [[e257_reconciliation_scoreboard_review]] for the precedent on treating a
divergence signal as diagnostic rather than something to gate away.

## Update (2026-07-27): the ruling is now data-validated, not just argued

E-278 (the epic this idea fed) measured OQ-2 -- the frequency question I flagged as
missing evidence when I made this ruling. Per `epics/E-278-game-identity/epic.md`
("OQ-2 -- ANSWERED"): genuine own-team unscored games are real and material across the
project's any-`public_id` population -- present on a meaningful fraction of subject
teams, at a per-team rate the epic records as a low-double-digit-percent range of a
team's own completed games, with most of those cases carrying plays data from the
*opposing* perspective only (played and charted by someone, just not by the subject
team). Had the EXISTS-gate proposal shipped, that population would have silently
vanished from real coaches' records. Read the epic file for the exact current figures
rather than trusting a restated number here -- this note exists to record that the
prediction ("LSB near-zero, other programs not") held, not to carry the count forward.
Consequence for future rulings: **the additive coverage-visibility signal I proposed as
a SHOULD/NICE HAVE now has real material to describe, not a null set** -- whether it
earns a story is PM's call, not a re-litigation of this ruling.
