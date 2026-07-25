---
name: measurement-discipline
description: Two validated rules for API measurement work — refuse to answer from adjacent data you already hold, and scope a CAUTION as tightly as a number because a caution propagates where a number gets audited
metadata:
  type: feedback
---

# Measurement discipline (both rules earned on 2026-07-25, E-274)

## Rule 1 — REFUSE to answer from adjacent data you already hold

When asked a question that data in hand *almost* answers, run the real measurement instead of
compressing what you have. Twice in one session this was the difference between a correct
answer and a confident wrong one:

- Asked for a joint distribution over a peer instance's 73-team sweep, I had only their prose
  SUMMARY, not their rows. I re-ran the probe rather than computing a distribution from prose.
- Asked whether `team_season.season` was populated, I held authenticated-endpoint data with a
  flat `season_name` field. The question was about the PUBLIC endpoint's `team_season.season`.
  **Different field, different endpoint, similar name.** I ran 73 fresh public calls.

**Why:** the second one would have been UNDETECTABLE. The field names were close enough that
nobody downstream would have questioned the answer. Confirmed by team-lead as the inverse of
the failure mode that bit others the same day.

**How to apply:** when a requester says "you already have this, just re-slice it," treat that
as a hypothesis to CHECK, not a permission to compress. Verify the field you hold is the field
they asked about — same endpoint, same name, same semantics. "I did not measure that; running
it now" is always an acceptable answer. Cost is minutes; the failure is silent.

## Rule 2 — a CAUTION needs tighter scoping than a NUMBER

**A number invites an audit; a caution does not.** So a wrongly-generalized caution travels
further and lives longer than a wrongly-generalized statistic.

Both of my over-generalizations this session were spring-population properties written as
general rules — "the name always carries the level, so the signals are anti-correlated" and
"`season` is constant within the school family." A single summer team refuted each. The PM had
written the first into an epic behind a *do-not-restore marker*, which turned a scoping error
into a durable one.

**How to apply:** every population-derived claim carries its population IN THE SENTENCE, not
in a footnote — and most of all when phrased as advice. Before writing "never do X" or "X is
always Y," name the population it was measured on. A clean 100% on one population is exactly
where over-generalization hides, because there is no residual to make you look twice.
**Getting a second population is the cheapest possible check and it caught both.**

Related: [[public-team-age-group-level-field]], [[public-team-profile-season-shape]].
