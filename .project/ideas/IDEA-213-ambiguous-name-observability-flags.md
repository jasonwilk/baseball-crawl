# IDEA-213: two disjoint observability flags for ambiguous league-name resolution

## Status
`CANDIDATE` — **fully specified, cut from E-275 by operator ruling 2026-07-27. Not abandoned: this is a complete design parked for want of a consumer, not an open question.**

> **Read this before promoting.** Two flags are specified here, they fire on **disjoint** populations, and they are **not** variants of one another. Promoting one does not give you the other. An earlier framing called the second a "widening" of the first; SE measured that they overlap on **nothing**, and that framing hid an option the operator was never offered — cut the first and keep the second.

## Summary

`detect_league_level` (`src/reports/starter_prediction.py`) resolves a team name to a pitch-count rule table with no record of having made an ambiguous call. Two observability-only records were designed for E-275 and cut before dispatch.

**FLAG A — the ambiguity flag.** Fires when a name carries a **Legion-family signal beside a generic-tier signal**. Emits one record; never changes the resolved league.

**FLAG B — the unsupported-signal flag.** Fires when a `legion` resolution rests on `seniors`/`juniors` **alone**, with no corroborating signal. Catches the defect in [[IDEA-205]].

**They are disjoint. SE measured it across all 45 Legion×tier name shapes:**

```
both fire: 0     A only: 40     B only: 2     neither: 3
```

A fires on names **with** a tier word; B fires on names **without** one. **B's population contains the only confirmed live defect; A's does not.**

## Why It Matters

**Neither flag detects a defect that exists today** — that is why they were cut, and it is the thing to re-check before promoting rather than to assume has changed.

**Flag A's day-one output is five records on a settled question.** TN-5's re-derivation against the 563-name corpus: exactly **5** real names fire, and all five are Legion + `reserve(s)`. E-275 TN-6 adjudicates that shape in full, both season branches traced against the sourced tables — *"No ruling change and no code fix."* So A would emit five requests for a human to sanity-check five names a human had already sanity-checked. **A's honest value is prospective**: it detects the *arrival* of the reorder-relevant shape in a population where that shape has never been seen. It is not, as E-275 TN-5 originally claimed, *"the widest reach in this epic"* or *"the only part that produces new information about the live population."* Both were overclaims and the second is close to backwards on day-one behaviour.

**Flag B addresses a confirmed live defect — and the operator ruled that a log line is not an acceptable answer to one.** The governing rule, verbatim: *"A confirmed live defect gets a fix or an explicitly-homed follow-up, never just a log line watching for its shape."* [[IDEA-205]] is that homed follow-up. **B was cut for that reason, not for lack of value** — and SE's severity re-classification (the defect **under-rests** on two of three school-family values) strengthens the ruling rather than weakening it: a more serious defect is *less* acceptably answered by observability, not more.

## The specifications

### Flag A — trigger, as a DERIVED RULE and not a word list

Coach's ruling, 2026-07-27. The requirement was never *"trigger on these five literal strings"*:

> **Trigger when a name carries any Legion-family signal beside any generic-tier signal THE CLASSIFIER ITSELF RECOGNIZES** — regardless of which patterns were reordered and regardless of which pattern won.

- **Legion-family side**: the Legion-family entries of `_LEVEL_WORD_PATTERNS` — currently `legion`/`american legion`, `post N`, `seniors`, `juniors`.
- **Generic-tier side**: the sub-varsity and varsity entries, **including every alternate spelling those patterns already accept** — currently `varsity`, `jv`/`junior varsity`, `freshman`/**`frosh`**, `reserve(s)`, `sophomore`.

> **`frosh` was missing from the hand-written list, and its absence is the whole argument for stating this as a derived rule.** Coach ruled it belongs — *"a coach would read 'Post 12 Frosh' as exactly as ambiguous as 'Post 12 Freshman'"* — and called the omission a gap in its own original list rather than a relay error: it was naming the tier CONCEPT without checking the classifier's recognized alternates. `_LEVEL_WORD_PATTERNS` matches `\bfreshman\b|\bfrosh\b` as **one pattern**, so `frosh` was already a tier word the classifier knew and the trigger did not.
>
> **The general point, which coach considers the more important half of the ruling:** a hand-transcribed second list drifts the moment the first one changes — the copy-drifts-and-nobody-updates-it failure the canonical-seams discipline exists to prevent, showing up in a spec artifact rather than in code. **The five words are the CURRENT MEMBERSHIP of a rule, not the rule.** If `_LEVEL_WORD_PATTERNS` changes, **re-derive this set.** Corroborating: `junior varsity` is covered today only incidentally, because `\bvarsity\b` matches inside it — luck, not design, and a second reason not to trust a transcribed list.

**Contract**: matches `_log_bracket_season_disagreement` — log, never change the resolved value. Emit at that function's log level (an unspecified level is not assertable by a test).

### Flag A — what it ALSO fires on, which its E-275 spec never disclosed

SE drove **1,440 combinations** (5 Legion-family × 8 tier literal spellings = 40 base, crossed with season, bracket and `ngb`), with a positive control asserting every literal spelling matched its intended pattern first.

- **Bracket-bearing names fire.** The trigger is name-token based and the exclusion criterion excludes only *Legion-token-without-tier-word* and *tier-word-without-Legion-token*. **A bracket is not an exclusion.** So a bracket-bearing name with both tokens fires — and resolves by bracket floor (`14U → youth_travel`, `16U → nrbl`, `18U → legion`) uniformly across every Legion token, tier token and season. **Resolution never in doubt; flag fires anyway.**
- **`ngb`-bearing names fire.** `ngb=["american_legion"]` → `legion` on all 40 combinations; `ngb=["nsaa"]` → `nsaa_varsity` on 5 and `nsaa_subvarsity` on 35, via `_nsaa_level_from_name`'s separate substring matcher. **Also never in doubt.**

**This is noise on top of the five day-one firings, and it dilutes A's only surviving justification** — an arrival signal buried in firings that carry no information. **An open question below asks coach whether the trigger should exclude bracket- and `ngb`-decided names.** It is coach's ruling to change, not an implementer's.

### Flag B — the predicate needs FIVE conditions, not three

**The naive three-condition form is WRONG and SE found it by executing rather than reasoning.** Conditions `league == legion`, `seniors|juniors present`, `no hard Legion token` admit `legion` reached from a **non-name** source:

```
naive 3-condition predicate:
  'Quorrin Seniors' + ngb=["american_legion"]   -> FIRES   *** false positive
  'Quorrin 18U Seniors'                          -> FIRES   *** false positive
```

**The correct predicate adds two: `ngb` empty, and no bracket in the name or in `age_group`.** Verified clean on eight shapes — fires on the live misfire (with and without `age_group=high_varsity`) and on the `juniors` sibling; silent on `ngb`-sourced, bracket-sourced, hard-token, and has-a-tier-word cases.

**Cost**: one additional condition block at the same call site. **No signature change** — `_league_from_level_word` need not return which pattern won; the predicate needs only the returned league plus two regex scans of the name.

### The PREDICATE / CONTENT split — only one half carries an open decision

**State this explicitly to whoever promotes, so they do not treat the whole thing as unspecified.**

| | status |
|---|---|
| **WHEN it fires** — both predicates above | **SETTLED by SE's execution.** Implement as written. |
| **WHAT it emits** — the record's content | **OPEN.** See the logging decision below. |

### The logging decision — DEFAULT IS A SHAPE SUMMARY

**Operator lean, 2026-07-27: on promotion the default is a SHAPE SUMMARY, not the raw team name. Raw names would need their own affirmative ruling at promotion time.**

**The reasoning, recorded because the conclusion does not survive without it:**

> *"Names already appear in reports"* **understates the difference.** Reports are an **access-gated product surface**. Application logs get copied, pasted into issues, and shipped to wherever logs go. **New surface class, stricter default.**

> **One argument was made and rejected; recorded so it is not re-made as novel.** Team-lead offered *"team names already appear in reports, so this adds no new exposure class"* as the rationale for approving raw names. **It was wrong, and wrong in the reassuring direction inside a safety-adjacent decision.** The two surfaces are not equivalent, and **treating an existing exposure as licensing a new one** is the move that needs naming. A future reader who finds only *"default: shape summary"* will meet the reports comparison on their own — it is the obvious argument — and may talk themselves out of the default.

**E-275 status: N/A — no flag ships, so no names reach any log.** The decision becomes live only on promotion.

## Acceptance criteria as specified for E-275 (Flag A) — carried verbatim in substance

- **A-1 (CHANGE — discriminates; no such record exists today)**: a name carrying any Legion-family token beside any generic tier word emits **exactly one** observability record identifying the name as ambiguous, at the same log level as `_log_bracket_season_disagreement`. Trigger scope is the derived rule above and is **independent of which patterns were reordered and of which pattern won** — `"Trandive Seniors Varsity"` and `"Morvath Legion Reserves"` must both fire even though neither's resolution changes.
- **A-2 (GUARD — constrains precision)**: a name carrying a Legion-family token but no tier word, or a tier word but no Legion-family token, emits **no** record. **Catches** an over-broad trigger firing on the Legion token alone, which would fire on **22 of the 27** Legion-family names in the corpus and drown the signal. Only **5** should fire.
- **A-3 (GUARD — observability only)**: for any name that emits the record, the league returned is identical to what is returned with logging disabled. **Catches** a flag wired as a resolution branch rather than a log. *(Coupling: this can only be made to fail first if its test also asserts emission, which is A-1's job. Keep them separate.)*

> **⚠️ A-2's figure comes with its DEFINING SETS, and that is not decoration.** 22 = names carrying ≥1 of {`legion`, `american legion`, `post \d+`, `\bseniors\b`, `\bjuniors\b`} and NONE of {`\bvarsity\b`, `\bjv\b`/`junior varsity`, `\bfreshman\b`/`\bfrosh\b`, `\breserves?\b`, `\bsophomore\b`}, denominator 563. Composition: 17 hard-token names with no tier word + 5 soft-`seniors`-only names; brackets present on 6 of the 22, since a bracket is not a tier word under this rule. Source: `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md` §"AC-9 / TN-5 trigger-set counts".
>
> **There are TWO different 22s and they share only 17 members.** E-275 TN-4's 22 = hard-Legion-token names. This one = any Legion-family token, no tier word. TN-4's includes the 5 Legion+`reserve` names this excludes; this includes the 5 soft-`seniors`-only names TN-4's excludes. **Disjoint by 5 in each direction, equal in size by arithmetic accident.** A matching count is NOT evidence that two figures are the same quantity.

> ### ⚠️ WHY A-2 AND A-3 ARE GUARDS AND CANNOT BE DEMONSTRATED FAIL-FIRST
>
> **Carried from E-275 story 01, where it prevented an impossible Definition-of-Done demand. It is the most reusable thing in this file.**
>
> *"No such record exists today"* is true of **A-1** and **false of A-2 and A-3 for the very same reason**: **absence-of-feature makes an EMISSION assertion discriminate and an ABSENCE assertion vacuous.** One sentence, opposite consequences. Against pre-change code A-2 passes trivially (no record is emitted for any name, so certainly not for these) and A-3 holds vacuously (its antecedent is never satisfied). **Demanding a fail-first demonstration for either is impossible, and a DoD that demands one either stalls or gets waved through** — which is worse than not demanding it. Each therefore names the wrong implementation it catches instead.
>
> This nearly went out with the flags during E-275's trim: it sat in a **section header** above the ACs rather than inside a note or an AC, so it was attached to a *structure* rather than to *content*. **Excisions attached to a structure lose things that excisions attached to content do not.**

## The corrected five-ruling derivation — supersedes a four-row table

**Whoever promotes will want to know whether A's firings land on resolutions anyone has ruled on.** The answer is yes, but it takes **five** rulings. A four-row version of this table circulated during E-275 planning and **was false in the summer branch**; SE falsified it by execution.

| trigger combination | season-absent / spring | summer | governed by |
|---|---|---|---|
| hard Legion + `varsity` | `legion` | `legion` | E-275's reorder |
| hard Legion + sub-varsity | `nsaa_subvarsity` | `nrbl` | E-275 TN-2 |
| `seniors`/`juniors` + `varsity` | `nsaa_varsity` | **`legion`** | E-272's season rule — **NOT TN-3** |
| `seniors`/`juniors` + sub-varsity | `nsaa_subvarsity` | `nrbl` | sub-varsity precedes all |
| any of the above + bracket | by bracket floor | by bracket floor | the bracket ladder |

> **Two defects in the superseded version, both worth carrying.** It asserted `seniors`/`juniors` + `varsity` → `nsaa_varsity` **unconditionally** and cited **TN-3** as authority. In summer it resolves **`legion`**, via `\bvarsity\b` winning first-match and the summer branch mapping varsity into the Legion family — so the row was **wrong on the value and wrong on the authority**. It also named **three of five** reachable resolutions (`nrbl` and `youth_travel` missing) and silently assumed season-absent / no bracket / no `ngb`.
>
> **The conclusion survived; the premise did not.** That is the shape a correct conclusion shields from review, and it took execution to find — not re-reading.

## Rough Timing

**Promote when anything next touches the level-word patterns** — the same trigger [[IDEA-205]] carries, and for the same reason: this is observability *over* those patterns and its trigger set must be re-derived whenever their membership changes.

**Promote FLAG B sooner if** [[IDEA-205]]'s fix is deferred again and the operator wants visibility in the meantime — but note that the operator has already ruled once that a log line is not an acceptable answer to that defect, so this needs an affirmative reversal, not a silent revival.

**Do NOT promote Flag A on the strength of E-275 TN-5's original claims.** They were overclaims and are corrected above.

## Dependencies & Blockers
- [ ] None technical. Both predicates are settled by execution.
- [ ] **The record's CONTENT carries an open decision** — default is a shape summary; raw names need an affirmative ruling.
- [ ] **Flag A has an unresolved coach question** (below) that changes its trigger.

## Open Questions

- **Should Flag A's trigger exclude names where a BRACKET or a recognized `ngb` decides the resolution?** In those cases the name-token ambiguity has no effect on the outcome, so the firing carries no information. Narrowing would make A fire exactly where ambiguity matters. **This is coach's call, not an implementer's** — the trigger is coach's ruling (*"any Legion-family signal beside any generic-tier signal the classifier itself recognizes"*), and narrowing it changes that ruling. SE would need to confirm cost.
- **Is Flag A worth having at all once its arrival signal is priced honestly?** Its day-one output is five records on a closed question and its prospective value is diluted by the bracket/`ngb` classes above. **Flag B is the one with a defect behind it.** If only one is ever built, the case for B is stronger — and that combination was never on the table during E-275 because the two were framed as one trigger and its widening.
- **Who reads it?** Neither flag has a consumer. Nothing surfaces these records, alerts on them, or reports them. An observability record nobody reads produces no observability, and this is the question to answer *before* promotion rather than after.

## Notes

**Cut from E-275 by operator ruling, 2026-07-27**, after the epic's value ordering was corrected for the third time to: (1) fixture pack + constant tripwire, (2) the precedence reorder, (3) the flags. The flags ranked last and were the epic's only new runtime code path.

**Sentinel constraint binds anything written here** (E-275 TN-17): constructed names from invented tokens only — `Wexlom`, `Quorrin`, `Trandive`, `Vaskeld`, `Zibbet`, `Morvath`. **Never** the `Anytown`/`Springfield`/`Example` taxonomy, and never a real team or place name. See [[IDEA-203]].

Related: [[IDEA-205]] (the defect Flag B catches, and the reason B was cut), [[IDEA-206]] (the `juniors` word-form hypothesis — the same pattern family), [[IDEA-172]] (the precedence question E-275 shipped), [[IDEA-201]] (the other level-word matcher, which does not share this vocabulary).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
