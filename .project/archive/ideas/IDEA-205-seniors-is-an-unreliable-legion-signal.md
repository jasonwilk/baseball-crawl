# IDEA-205: bare `seniors` misfires as a Legion signal on school-family teams

## Status
`CANDIDATE` — **live, pre-existing defect. Observed twice, on the SAME operator network — see the corrected basis below; the earlier "two independent corpora" wording is RETRACTED. Routed out of E-275 explicitly by baseball-coach.**

> ⚠️ **SEVERITY RE-CLASSIFIED 2026-07-27 — read "Why It Matters" before citing this idea's direction.** This file previously classified the defect as **data-accuracy rather than safety**, on the strength of its observed instance. **That classification is wrong for two of the three school-family `age_group` values**, where the defect **under-rests**. The observed instance happens to carry the one value where it errs safe. **Do not cite the mild reading.**

## Summary

`\bseniors\b` is one of four Legion-family patterns in `_LEVEL_WORD_PATTERNS` (`src/reports/starter_prediction.py`) and resolves a name to `legion` season-independently.

**It fires on teams that are not Legion.** api-scout observed a real team with `age_group=high_varsity`, no Legion token and no age bracket, carrying "Seniors" in its name in the ordinary graduating-class sense — resolving `legion` today. This matches a prior "... Seniors 2" case from a separate n=73 probe.

> ⚠️ **CORRECTED 2026-07-27 — "two independent corpora" is RETRACTED and must not be restored.** api-scout narrowed its own claim: **both observations come from the same operator's network**, so independence fails. It also tested and retracted the "sibling squad" inference that had propped the claim up — this corpus holds **no `Seniors 2` at all**, and E-274's instance survives only as an elided string whose program prefix was never persisted, so same-program is **untestable, not merely unproven**. Separately, it is **1 confirmed live misfire, not 4**: of the four `seniors`-without-a-Legion-token names, one is caught by the range regex before the name words ever run and two carry no captured `age_group`.
>
> **What survives is enough, and the argument never needed more.** Two observations establish that the misfire **HAPPENS**; they establish **nothing about how OFTEN**. Coach's ruling rests on "real, not hypothetical," which it has comfortably. Do not re-inflate the evidence to strengthen a conclusion that already holds. Source: `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md`.

No preceding pattern matches such a name, so **pattern order does not change the outcome** — this is independent of any reorder, and E-275's narrowed reorder neither causes nor fixes it.

## Why It Matters

The classifier treats `seniors` as Legion's own division-naming convention. The evidence says it functions as a generic English word in real team names. A high-school team's "Seniors" means the graduating class; Legion's Senior division is a different thing that happens to share a word.

**Consequence is a wrong league label and a wrong rule table on the coach-facing card.** The wrong-label half stands as written: the coach is shown a governing body their team does not play under, with the citation that goes with it.

~~Direction: a school-family team resolving `legion` gets the Legion curve instead of NSAA's, which requires equal-or-more rest at every pitch count — so this fails toward over-rest, a bench day rather than an arm. That makes it a **data-accuracy defect rather than a safety one**, and it should be argued on those terms.~~

> ⚠️ **CORRECTED 2026-07-27 — THE DIRECTION SPLITS BY SCHOOL-FAMILY VALUE. The struck sentence is true of the OBSERVED INSTANCE and false of the DEFECT.** Measured by software-engineer, driven against `src/reports/starter_prediction.py` — not reasoned from the tables:
>
> | `age_group` | correct table | `legion` vs. correct | direction |
> |---|---|---|---|
> | `high_varsity` | `nsaa_varsity` | MORE rest at 46-50, 61-70, 81-90 (81+ unbounded pre-April); less at none | **over-rests — conservative** |
> | `high_junior_varsity`, `high_freshman` | `nsaa_subvarsity` | **LESS rest at 1-45, 51-60, 71-80**; more at none | **UNDER-RESTS — harmful** |
>
> **The one confirmed live instance carries `high_varsity`** — the conservative value. **The identical defect shape on either sub-varsity value under-rests at the very bottom of the range**: a sub-varsity arm that threw ONE pitch is owed a rest day and would be called available immediately. Nothing about the defect prevents that variant; it has simply not been observed, and the observation window is a two-day single-network corpus that bounds nothing.
>
> **SE's framing, which is the sentence to design any restatement against:** *an idea filed as "bare `seniors` over-rests a varsity team" understates it by exactly the two values where it under-rests.*
>
> **So: a data-accuracy defect on one value and an ARM-SAFETY defect on two.** Argue it on the harmful direction. The observed instance's mildness is **EVIDENCE of what was seen**, not a property of the defect — the original error was generalizing the one to the other, in the reassuring direction, inside a safety judgment.
>
> **Note the symmetry that makes the re-classification binding rather than cosmetic.** E-275 ships its precedence reorder precisely because an under-rest path is real, unobserved, and unboundable on this same corpus. This defect's harmful variant sits in the identical evidentiary position. The two cannot be classified differently.

This finding contributes to a decision elsewhere, and **the strength of that contribution was overstated here.**

> ⚠️ **CORRECTED 2026-07-27 at coach's request. This was NOT "the entire basis" for coach's decision** not to promote `seniors`/`juniors` ahead of `\bvarsity\b` in E-275. **Coach attributes the error to its own earlier phrasing** ("confirmed in two independent corpora") rather than to a misreading of it — the overstatement was inherited, not invented here.
>
> **What actually carries that ruling is the PATTERN-FORM argument** (E-275 TN-3, leg 3): `\bseniors\b`/`\bjuniors\b` are **plural-only** patterns, Legion's attested naming leans **singular** (`Senior Legion` is attested; plural `juniors` is unattested across all 2,518 stored bodies), and widening to the singular would manufacture four false Legion signals out of four ordinary `Junior Varsity` teams. That is a claim about English usage and token ambiguity. **It needs no sample size and does not weaken when this idea's misfire count drops.** Coach notes it predates the corpus work entirely — the same concern appears in RULING 4's original falsifier text, written before any name corpus existed.
>
> **This observation's real role is corroborating color, at n=1** — it establishes that the failure mode EXISTS, and nothing about how often. It is genuinely load-bearing for the general principle that *precedence should track signal reliability, not only failure-direction safety*; it is not load-bearing for the narrowing itself.

The co-occurrence question remains unanswerable on the available corpus either way (14 names against coach's 30-50 floor), and neither leg depends on it.

## Rough Timing

Promote when anything next touches the level-word patterns, or on a third observed misfire. It is **observed rather than theoretical**, which distinguishes it from most of the classifier backlog.

> ⚠️ **URGENCY RE-DERIVED 2026-07-27. The previous rating was *"Not urgent — the failure direction is the mild one and the population is small."*** The first clause rested on the direction claim now corrected above and does not survive it: **the direction is the mild one on one of three school-family values and the harmful one on two.** The rating is re-derived rather than edited in place, because a rating that outlives the claim it was derived from is the defect this file has now recorded twice — **and it shares none of that claim's words, so no sweep for the retired reading would have found it.**
>
> **Re-derived rating: not urgent on the OBSERVED population, and not safe to describe as mild.** The population is genuinely small and only the conservative variant has been seen — so this does not jump the queue. But it must not be triaged as an accuracy nicety, and *"the failure direction is the mild one"* must not be restored in any form.

> **⛔ E-275 FIRED THIS TRIGGER ON 2026-07-27 AND PROMOTION WAS DELIBERATELY DECLINED. THE TRIGGER IS NOT SPENT.**
>
> E-275-01 reorders `_LEVEL_WORD_PATTERNS`, which is exactly *"anything next touches the level-word patterns."* Recorded rather than left to expire silently, because the remaining forward trigger — *"a third observed misfire"* — is weak on its own, and the ambiguity flag that might have surfaced a third was cut in the same epic (see [[IDEA-213]]).
>
> **Why declined**, so nobody re-derives it as an oversight: software-engineer established by execution that **no reordering can fix this defect at all.** Only `\bseniors\b` matches such a name, and a single-match name is order-independent by construction — SE drove the most aggressive possible ordering (all four Legion patterns hoisted to the front) and it still resolves `legion`. The school-family `age_group` is inert: it matches neither age regex, and the resolution is identical with no `age_group` at all. **E-275 could not have fixed this by any version of the change it shipped**, coach routed it out explicitly, and pulling it in would have been a scope change to approved work.
>
> **The next work touching these patterns fires this trigger again.** Decline once, on this reasoning; do not read the decline as a standing precedent.

## Dependencies & Blockers
- [ ] None.

## Open Questions
- **What makes the pattern selective enough?** Coach sketched two directions without ruling between them: require an adjacent numeric division marker, or exclude on known school-context co-signals (an `age_group` in the school family, a `classification` value, a co-occurring tier word). The second is more robust and a wider behaviour change.
- **Should `seniors` be a Legion signal at all?** The corpus has 8 `seniors` names and 2 singular `Senior`; how many are genuinely Legion is not established. If most are not, removal beats refinement — but that needs the population characterized first, not assumed.
- **Does the same reasoning reach `juniors`?** It has zero attestations and therefore zero misfires, so there is nothing to observe. See [[IDEA-206]], which argues the pattern may be aimed at the wrong word form entirely.
- ~~Would E-275's ambiguity observability flag surface these?~~ **ANSWERED, and the flag no longer exists — see [[IDEA-213]].** The base flag would **not** have caught these: it fires on a Legion token **beside a tier word**, and this misfire needs none. A **second, disjoint** flag was designed during E-275 planning that *would* catch them (`legion` resolved on `seniors`/`juniors` alone, no corroborating signal). SE measured the two triggers as **disjoint — zero overlap** across all 45 Legion×tier shapes, and the second is the one whose population contains this defect. **Both were cut to [[IDEA-213]] by operator ruling**, on the rule that *a confirmed live defect gets a fix or an explicitly-homed follow-up, never just a log line watching for its shape.* If [[IDEA-213]] is ever promoted, SE's **five**-condition predicate is the one to implement — the naive three-condition form false-positives on `ngb`-sourced and bracket-sourced `legion`.

## Notes

Routed out of E-275 by baseball-coach explicitly, under the same discipline as the operator's MINOR-to-idea policy: it is not a precedence-ordering bug, it exists regardless of any reorder, and fixing it means making the pattern itself more selective — new work, not a guard-test fix.

**WHERE THE FIX BELONGS — E-274's school-family branch, and it is unreachable from any pattern reordering (SE, by execution, 2026-07-27).** The name path governs here only because the school-family `age_group` is **unparsed**: `high_varsity`/`high_junior_varsity`/`high_freshman` match neither `_AGE_BRACKET_RE` nor `_AGE_RANGE_RE`, so `_league_from_age_bracket` returns `None` and the resolution is identical with no `age_group` at all. **Reading that value is E-274's scope, not E-275's** — which is also why no reordering can help (see the decline note under Rough Timing).

**The correct answers are already RULED and merely unimplemented** — coach's **RULING 1** and **E-274 TN-3**: `high_varsity` → spring `nsaa_varsity` / summer `legion`; `high_junior_varsity` and `high_freshman` → spring `nsaa_subvarsity` / summer `nrbl`. So this is not an open design question. It is a ruled answer with no implementation.

> ⚠️ **THE HOME IS CONTINGENT, and that must be visible here rather than inferred.** E-274 is under a **build / shrink / shelve** decision at 4% measured value (E-275 TN-12 flags the same exposure). **If E-274 shelves, this fix has no home** — and this idea then joins [[IDEA-208]], whose capture exists precisely because it was ruled into E-274's lane and orphaned there. **Two coach-ruled classifier defects now depend on E-274's fate.** That is an input to the E-274 decision, not a claim on it.

**Its expected label belongs in E-275's fixture pack Tier 2, not Tier 1.** The current output is a known defect; pinning it as correct in an executed row would lock in the thing this idea exists to fix.

Ruling of record: the **RULING 4 AMENDMENT** in `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`.

Related: [[IDEA-206]] (the `juniors` word-form hypothesis — same pattern family), [[IDEA-172]] (the precedence question this evidence settled), [[IDEA-201]] (the other level-word matcher, which does not share this vocabulary).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
