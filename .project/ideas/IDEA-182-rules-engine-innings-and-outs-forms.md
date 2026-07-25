# IDEA-182: USSSA and Perfect Game are UNBUILT, not unresolvable — the rules engine has no innings-based or outs+pitches form

## Status
`CANDIDATE`

## Summary

`PitchCountRules` can express exactly one shape of rule: **pitch count → rest days**. USSSA and Perfect Game do not use that shape, so their cards suppress — and the reason has been quietly mis-stated as "no defensible table exists," when in fact **the published regulations are already written down in our own rule file.**

Verified against `.claude/rules/pitch-rules.md`:

| body | unit | status in that file |
|---|---|---|
| NSAA Varsity / Sub-Varsity, Legion, NRBL | pitch count → rest days | **implemented** as frozen `PitchCountRules` sets |
| USSSA (7U–18U) | **innings** | full rules present (`## USSSA (Youth Travel, 7U-18U)`): 3 innings max to pitch next day; 1-day max 6 innings (7U–12U) / 7 innings (13U–14U); mandatory rest if >3 innings in a day. Marked *"Reference data only -- not yet implemented in engine."* |
| Perfect Game (7U–14U) | **outs + pitches** | rules present (`## Perfect Game (7U-14U)`). Additionally *"not yet represented in schema (no `program_type` value exists for PG tournaments)."* |

The rule file states the blocker directly: these *"use fundamentally different units (innings, outs) that would require **structural engine extension** (a code change, not just new thresholds)"*, and `get_rules_for_league()` returns `None` for `usssa` / `perfect_game` / `unknown`, so the card suppresses with softened copy.

**The correction that makes this worth filing:** `usssa` and `perfect_game` are *recognized* `ngb` values — they resolve to a league id successfully and then hit a `None` rule set. So the classifier is doing its job and the engine has nowhere to put the answer. The E-274 / IDEA-178 discussions repeatedly described these as teams for which "there is no defensible table" or which are "genuinely different rule systems we cannot express." The first half is false — the tables exist and are cited. Only the *engine* is missing. **Unbuilt, not unresolvable.**

## Why It Matters

Framing drives priority, and the wrong framing has been suppressing this twice over:

1. **"No defensible table" reads as a dead end; "unbuilt" reads as a backlog item.** The former invites nobody to do anything. Being precise about which half is missing is the whole value of this capture.
2. **It is being used as a load-bearing justification elsewhere.** IDEA-178's ruling keeps `usssa`/`perfect_game` **fully dispositive** on the grounds that they are genuinely different rule systems — which is correct and should stand. But the adjacent inference "so nothing can be done for those teams" does not follow, and the two should not travel together.

Coaching value is real but bounded: a suppressed card for a USSSA or PG opponent means **no Most Likely Arms section at all** for that opponent. Whether that population matters depends on how many such opponents LSB actually faces — the E-274 session put it at roughly 8 teams among those probed, which is small and should be re-measured rather than trusted.

Honest severity: this is **additive capability**, not a defect. Nothing produces a wrong number today — suppression is the correct behavior for a rule form the engine cannot express, and per `display-philosophy.md` the softened copy already handles it. There is no live hazard here, which is exactly why it has sat unbuilt.

## Rough Timing

Not next. Triggers:
- LSB's schedule picks up enough USSSA / PG opponents that suppressed cards become a felt gap (measure first).
- Someone is already inside `starter_prediction.py`'s rule-set layer for another reason — the marginal cost of a second rule *form* is far lower than a standalone epic.
- The platform's multi-program reach (per `docs/VISION.md`, single-season, any `public_id`) brings in a travel-ball coach, for whom USSSA is the *primary* rule system rather than an edge.

## Dependencies & Blockers
- [ ] **Measure the population first.** ~8 teams is a session anecdote, not a measurement. If it is single digits and static, this stays parked.
- [ ] Perfect Game additionally needs a schema decision — no `program_type` value exists for PG tournaments, so it is strictly more work than USSSA and should not be bundled by default.

## Open Questions

- **One polymorphic rule type or several?** A `PitchCountRules` sibling per unit (innings, outs+pitches) is simple and duplicative; a unified "workload → rest" abstraction over a unit enum is tidier and risks bending the three shipped, frozen pitch-count sets. Those sets are a rest-safety surface and the frozen-constant pattern is deliberate — **prefer additive siblings over refactoring what works.**
- **Is a tournament rule form even the same kind of object?** Perfect Game rules are *tournament*-scoped, not season-scoped. IDEA-066 asked this in 2026-04 and it was never answered: do we apply a team's home-league rules at all times, or does a tournament context override? A per-game rule context is a much larger change than a new rule dataclass.
- **Does an innings-based rule have the data it needs?** Rest math needs innings pitched per outing; `ip_outs` stores integer outs, so innings are derivable — but whether *appearance-level* innings are reliably present for a scouted opponent is unchecked, and an engine that cannot be fed is worse than a suppressed card.
- **Should the suppression copy name the reason?** Today USSSA/PG suppress with the same softened copy as "league not detected," which conflates "we could not tell" with "we know exactly which rules apply and cannot compute them yet." Adjacent to [[IDEA-177]]'s trust-surface argument, and cheaper than the engine work.

## Notes

Surfaced as baseball-coach's **Ruling 3** during the 2026-07-25 E-274 / IDEA-178 session, correcting the session handoff's characterization of these teams as unresolvable. PM verified the substance directly against `.claude/rules/pitch-rules.md` (the table, the `## USSSA` / `## Perfect Game` sections, and the `get_rules_for_league()` note) rather than relaying it — the rule file confirms both the published regulations and the structural-extension blocker.

**Why this is not already filed, which is the interesting part.** [[IDEA-066]] (League/Level Detection) noted in its own Notes, back in 2026-04, that *"USSSA requires structural engine extension (innings-based)"* — and IDEA-066 was **PROMOTED to E-218**, which shipped the *detection* half only. So the engine-extension half rode into a promoted idea, was never in that epic's scope, and left no live candidate behind when the idea closed. A grep of the ideas ledger for `PitchCountRules` / `innings-based` / `rules engine` returns nothing. **Durable shape worth noting: a promoted idea's Notes are not a backlog** — anything in them that the epic does not take needs re-filing at promotion, or it is silently retired with the idea.

Related: [[IDEA-066]] (PROMOTED → E-218; the ancestor that mentioned this in passing), [[IDEA-178]] (its ruling keeps `usssa`/`perfect_game` fully dispositive — correct, and independent of this), [[IDEA-179]] (rec-family forms falling through to adult tables — a *defect*, where this is a *gap*), [[IDEA-177]] (suppression-copy / trust-surface overlap).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
