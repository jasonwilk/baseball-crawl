# IDEA-207: `little_league` is not in `_NGB_MAP` and dead-ends to generic unknown

## Status
`CANDIDATE` — **baseball-coach has RULED (RULING 2). Implementation work, not an open question.**

## Summary

`detect_league_level`'s Priority 2 block iterates `_NGB_PRIORITY` (`nsaa`, `nfhs`, `american_legion`, `usssa`, `perfect_game`) looking for a match. When a team's only `ngb` value is `little_league`, nothing matches and the block falls through to `return "unknown"` — **before** the empty-`ngb` region (age bracket, name-word ladder) ever runs.

So a `little_league` team gets the same bare `"League not detected -- pitch count rules cannot be applied"` warning as a garbage or typo'd `ngb` value: indistinguishable, in the coach-facing copy, from "we have no idea what this is."

**Coach's ruling: recognize it, do not leave it dead-ending, do not build its rule table yet.** Add `little_league` to `_NGB_MAP` mapping to its own league id, which `get_rules_for_league()` returns `None` for (same as `usssa`/`perfect_game`), with its own `_LEAGUE_WARNINGS` entry — "Little League pitch rules not yet supported".

## Why It Matters

This is a **different failure mode from USSSA and Perfect Game**, which is the point. Those two are in `_NGB_MAP`, resolve to a real league id, and hit a "not yet supported" warning — a third tier that already exists in the code, distinct from both a bound table and generic unknown. `little_league` gets none of that.

Little League Baseball is a real, well-known governing body with published, age-tiered pitch-count regulations. Telling a coach we cannot identify their league, when we can and simply have not encoded its rules, is a worse answer than telling them the rules are unsupported — and it is worse in the direction that discourages them from looking further.

Coach ruled more generally that "recognized value, deliberately no table" and "genuinely unrecognized value" **must remain distinguishable to a coach**: the first is a coaching-informative fact they can act on, the second is a system limitation that says nothing about the opponent. Collapsing both into one message is a real loss. This is one instance of that principle; the same ruling applies to every suppress-terminal value.

## Rough Timing

**Fold into the next epic touching the `ngb` block.** Small — a map entry, a warning string, and a test. It was recorded as a Tier 2 (ruled-but-unimplemented) row in E-275's fixture pack rather than built, because E-275's scope is fix-only and an executed row asserting the ruled label would have been red against the full-suite-green closure gate.

**Coach explicitly did NOT rule on the rule table itself.** Building it is separate, lower-priority work (n=2 observed teams) and must cite Little League International's official regulations before any number is printed as fact — same discipline as every other numeric claim in coach's rulings file.

## Dependencies & Blockers
- [ ] None on the ruling.

## Open Questions
- Coach's falsifier, recorded rather than paraphrased: this framing is overstated if the 2 observed `little_league` teams turn out to be mislabeled noise rather than a real ongoing population — though the map entry is strictly better than today's dead end either way. It would also be wrong in the unlikely case that Little League's regulations numerically coincide with an existing table, which would argue for aliasing rather than a distinct constant; given Little League's younger core age range coach thinks that unlikely but did not check.
- **Are there other unmapped `ngb` values dead-ending the same way?** `little_league` was found because someone looked at one value. The `ngb` vocabulary is not known exhaustively the way the `age_group` vocabulary now is — see [[IDEA-179]]'s note that the create-team vocabulary was established by running every UI value through the classifier. **The same exhaustive treatment has not been done for `ngb`**, and that is probably the higher-value move than fixing this one value.
- Does the fall-through ordering itself deserve a look? An unrecognized `ngb` short-circuits to `unknown` before the age-bracket ladder runs, so a team with an unmapped `ngb` **and** a perfectly good `14U` bracket gets nothing. That is a broader behaviour question than this ruling covers.

## Notes

Ruling of record: **RULING 2** in `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`.

Filed separately from [[IDEA-179]] after checking: that idea covers the unparsed `age_group` **forms** (`Under 13`, `Over 18`, `NNO`) and its blocker has also now cleared, but this is an `ngb` **value**, a different field on a different priority tier with a different remedy. They are natural companions for one epic and should not be merged into one capture.

Related: [[IDEA-179]] (the ruled-and-now-unblocked `age_group` forms — the natural companion), [[IDEA-178]] (`ngb=american_legion` shadows NRBL — same block, different defect), [[IDEA-182]] (the innings/outs rules-engine extension USSSA and Perfect Game need — the reason those two are recognized-but-unsupported).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
