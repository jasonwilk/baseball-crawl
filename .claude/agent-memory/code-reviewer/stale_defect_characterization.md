---
name: stale-defect-characterization
description: After a redesign narrows the code, re-verify any claim that the ORIGINAL defect still persists — a round-1 characterization survives into round 2 unexamined.
metadata:
  type: feedback
---

When a round-2 redesign narrows scoping, do NOT carry forward a round-1 description of what the
defect does. Re-derive the harm against the NEW code before writing it down, even when the sentence
is incidental to the verdict.

**Why:** E-267-03. In round 1 the player-line grain was scoped by `(game_id, perspective_team_id)`
only, and stale lines genuinely did inflate `get_season_batting` / `get_season_pitching`. Round 2
added a `team_id` predicate. I approved the redesign, then described the residual "uncovered rows"
case as stale lines that "keep SUMming into" those readers — carrying the round-1 harm forward
verbatim. False: both readers bind the SAME `team_id` param to BOTH `player_game_*.team_id` and
`.perspective_team_id` (`src/api/db.py:501-503,516` / `:569-571,584`), so they only ever return rows
where `team_id == perspective_team_id == the requested team`. Opponent-block rows have
`team_id != perspective_team_id` by construction and are invisible to every season aggregate,
stale or not. PM's ruling was right and my sentence contradicted it.

Aggravating detail worth remembering: I had ALREADY read the correct WHERE clauses into context (in a
supplement answering a different question) and still did not reconcile them against my earlier
sentence. Having the right facts in context is not the same as re-checking the claim.

**How to apply:** two triggers. (1) Any sentence of the form "X still happens / persists / keeps
doing Y" written AFTER a fix — treat as a claim needing fresh evidence, not as retained context.
(2) Anywhere I credit someone else for verifying rather than asserting, check that the same standard
holds for my own adjacent claims in that report. Quote the literal WHERE clause and walk the
parameter binding positionally; a column appearing in a query says nothing about what it is bound to.

Related: [[ratio-gate-population-claims]] (the other case where my hand-derived claim was falsified),
[[tool-gotchas]].
