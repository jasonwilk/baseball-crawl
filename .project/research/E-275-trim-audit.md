# E-275 Trim Audit — scope pass against "Simple first. Complexity as needed."

**Date**: 2026-07-27 · **Auditor**: code-reviewer · **Reference**: `073a336` on `epic/E-275`
**Read**: current files on disk, including F14's target and all post-triage growth. Nothing edited.

## Headline

**Recommendation: option (b) — ship the two-pattern reorder, cut the apparatus around it.** I do not recommend (c), and §2 gives the number that decides it.

The measurements that frame everything below:

| | lines | share |
|---|---|---|
| `epic.md` total | 385 | |
| — Technical Notes | **272** | **71%** |
| — everything else (Overview, Background, Goals, Non-Goals, Success Criteria, Stories, Dispatch, OQ, History) | 113 | 29% |
| `E-275-01` | 131 (13 ACs) | |
| `E-275-02` | 108 (10 ACs) | |

**The code this specifies is a two-entry move in a list literal, one docstring sentence, one logging call, and a test module.** 624 lines of spec, 23 acceptance criteria, and 17 Technical Notes stand on top of it.

**The concentration is not evenly spread and that is the useful finding.** Four notes — TN-7 (40), TN-8 (34), TN-4 (29), TN-3 (26) — are **129 lines, 47% of all Technical Notes**, and every one of them grew tonight. None of the four specifies work. All four record how the planning session established something.

---

## 1. Load-bearing versus ballast

The distinction I applied: **load-bearing** = an implementer or reviewer makes a different decision without it. **Ballast** = true, often valuable, but its value is to a reader of *this planning session* rather than to someone building or checking the work. Ballast is not waste — it is misfiled.

### 1a. Technical Notes

| TN | lines | verdict |
|---|---|---|
| **TN-1** what moves | 8 | **LOAD-BEARING.** The spec of the change. Cannot shrink. |
| **TN-2** sub-varsity doesn't move | 10 | **LOAD-BEARING.** Prevents the front-move — the single most likely wrong implementation. |
| **TN-3** why not `seniors`/`juniors` | 26 | **MIXED → ~10.** LEG 3 (pattern form: plural-only patterns against singular attested usage) is the load-bearing reason and needs no sample size. LEG 1/LEG 2 and the "cannot be attacked on statistical power" block are the *argument's history*. Keep LEG 3 and one line that the safety-direction argument was retired; relocate the rest. |
| **TN-4** two falsifiers | 29 | **MIXED → ~12.** The two-falsifier table and the **split sufficiency verdict** are load-bearing — they are what bounds the epic's central claim. The "second 14 is GONE" narrative and the how-that-error-was-made block are a correction record. **Cutting that paragraph resolves F14 for free**, since F14 is a false sentence inside it. |
| **TN-5** the flag | 21 | **LOAD-BEARING → ~16.** The derived-rule framing and the `frosh` lesson are the note's point and generalize (it is the canonical-seams principle in a spec artifact). The `junior varsity`-is-luck corroboration can go. |
| **TN-6** Legion+reserve closed | 4 | **LOAD-BEARING.** Four lines covering the only real collision in the corpus. |
| **TN-7** safety property | **40** | **MIXED → ~15. Largest single trim.** Keep SE's verbatim property, the four-item divergence statement, and the **equal-bands caveat** (a third of the range has no cushion — that is a live constraint on future edits). The seven-branch axis enumeration, the "third exclusion axis nobody had enumerated", and the `_NSAA_*`-naming caveat are a **research record of how OQ-1 was answered**. Relocate to the research artifact; leave a one-line pointer. |
| **TN-8** provenance | **34** | **MIXED → ~10. Highest ballast density in the epic.** Items 1–2 are load-bearing: they produce the standing rule *never cite the comment block as evidence*. Items **3, 4, 5 and 6 are a catalogue of this session's own instrument failures** — a corrupted regex character class, a mis-scoped counterexample population, PM asserting its own file from memory, and the figure-transplant class. Genuinely valuable and **misfiled**: they are a process lesson about tool output, not a classifier spec. They belong in `.claude/rules/tool-output-integrity.md` (which already owns this exact material) or the research artifact. |
| **TN-9** synthetic ACs + corpus bound | 6 | **LOAD-BEARING.** Six lines doing the most work per line in the epic. |
| **TN-10** closure obligations | 23 | **MOSTLY LOAD-BEARING → ~16.** Both obligations and their named triggers stay. The "why naming the trigger matters" preamble was my F8 and has done its job — one line now suffices. |
| **TN-11** falsified seed claims | 12 | **LOAD-BEARING.** A do-not-restore list, and item 4 carries the criterion-vs-evidence rule for citations. |
| **TN-12** E-274 boundary | 6 | **LOAD-BEARING.** An operator-facing risk flag with no other home. |
| **TN-13** docstring + grep trap | 6 | **LOAD-BEARING.** The grep trap already fired on a real reviewer; six lines is cheap insurance. |
| **TN-14** word order | 4 | **LOAD-BEARING.** Prevents an AC that passes for the wrong reason. |
| **TN-15** not-summer vs absent | 4 | **LOAD-BEARING.** Defines the season class every AC uses. |
| **TN-16** pack structure | 17 | **LOAD-BEARING.** This is the durable deliverable's spec. The rejected-alternative paragraph is worth its four lines — it stops the idea being re-proposed. |
| **TN-17** sentinels | 20 | **MOSTLY LOAD-BEARING → ~14.** The constraint, the both-halves gate statement, the `tests/` scope note and the certification of record all stay. The "why invented tokens rather than the taxonomy" paragraph can compress to one sentence plus the IDEA-203 pointer. |

**TN subtotal: 272 → ~155.**

### 1b. Outside the Technical Notes

- **The OQ-3 handover block to a fresh coach instance (~20 lines)** — **BALLAST in this location.** It is a briefing for one agent, written to be consumed once. It belongs in the coach rulings file (which item 5 of the block itself says is authoritative). Leave a two-line pointer.
- **The History entry for 2026-07-27 (~15 lines in one line)** — **BALLAST.** A complete triage record of the spec audit, living in the epic. `.project/research/E-275-spec-audit-iteration-1.md` already holds it in fuller form. Reduce to one sentence plus the path.
- **Background's provenance-correction footnote** — keep. It is short and it is the record of a corrected figure.

### 1c. Acceptance criteria

**Story 01 (13 ACs) is where the AC ballast is, and the cause is duplication with the fixture pack.** TN-16's Tier 1 families 4 and 5 are *"the name-word conflict shapes from E-275-01, across all four non-summer season values plus summer"* and *"the bracket-versus-name-word conflict shapes"* — which is AC-1 through AC-7 restated. PM2 already ruled **absorption** (S7). **The ruling has not been applied to the AC list.**

| AC | verdict |
|---|---|
| AC-1, AC-2 | **KEEP.** The only two rows that fail against current code. This is the change. |
| AC-3 | **CUT** → pack GUARD row. |
| AC-4 | **KEEP.** The role-flip guard. It caught a broken fail-first list once and the original ruling still says four patterns. |
| AC-5 | **KEEP.** Catches the front-move — the most likely wrong implementation, and the one TN-2 exists for. |
| AC-6, AC-7 | **CUT** → pack rows. AC-7's four-row table is excellent work and belongs in the pack, where bracket-bin coverage lives, not in the reorder story. |
| AC-8, AC-9, AC-10 | **KEEP all three.** The flag is the epic's highest-value component (§3) and these are its whole spec. |
| AC-11 | **KEEP.** One-line docstring fix, real defect. |
| AC-12, AC-13 | **KEEP both.** Cheap, and AC-13's non-vacuity companion is what stops AC-12 being satisfied by a no-op. |

**Story 01: 13 → 9 ACs**, with the cut four relocated rather than deleted.

**Story 02 (10 ACs): keep all ten.** This is the durable deliverable and it is not over-specified. It absorbs four rows.

### 1d. On the request not to spare what the lead asked for

I did not, and the honest finding is that **the growth is not uniformly the lead's.** The four heaviest notes divide as: TN-8's failure catalogue and TN-7's axis enumeration are *records of work done by SE and api-scout*, added because the work was genuinely surprising; TN-4's and TN-3's growth is PM defending figures against a moving triage. What the lead's message-by-message requests produced is mostly the **traps-for-the-next-reader**, and those have the best hit rate in the epic — the grep trap, the role-flip warning, the two-22s block and the evidence-vs-criterion clauses are all load-bearing and all cheap.

**The ballast is concentrated in a different place than the brief assumed: it is the correction records, not the traps.**

---

## 2. What shape should the reorder take? — **(b), and (c) is a misread of the evidence**

### The number that decides it

`0 of 563` is the figure everyone reaches for, and it is the wrong one. The right one is already in TN-4: with 22 Legion-token names observed and zero carrying `varsity`, the **rule-of-three 95% upper bound on the co-naming rate among Legion-named teams is ~13.6%.**

**`0 of 563` does not mean "this does not happen." It means the true rate could be anything up to about one in seven Legion-named teams**, and the corpus cannot distinguish those. Add TN-9's bound — one operator's network, one region, a two-day window, 313 of 563 names from a single endpoint — and "unobserved" is carrying far less weight than the Background's framing suggests.

The consequence when it does occur is an arm called available that should not be: `nsaa_varsity` under-rests relative to `legion` at 46–50, 61–70 and 81–90, and at every count from 81 upward unbounded pre-April.

### Against (c) — and one factual correction to how (c) is framed

The brief describes (c) as *"keep the fixture pack as the instrument that would catch it if the population changes."* **The fixture pack cannot do that.** It is a static set of constructed synthetic rows; TN-9 says so explicitly. It does not observe live data and nothing in it fires when a real name of the targeted shape appears in production. Under (c) the defect would be caught by **the observability flag, or by nobody** — and the flag fires today only on the 5 Legion+`reserve` names, which is a *different* shape the reorder does not touch. To serve as the reorder's trigger, the flag's record must let a human distinguish a varsity collision from a reserve one. It logs the raw name, so it can — but that becomes a load-bearing requirement rather than a nice-to-have.

So (c) is not "no code change, same detection." It is "no code change, detection contingent on a human reading a log line." Against a ~13.6% upper bound on an arm-safety exposure, I do not recommend it.

### Against (a)

The apparatus is disproportionate. Seven of story 01's ACs are synthetic guards duplicating pack rows, on a two-line change whose direction is measured one-way safe.

### The recommendation

**Ship the reorder. Cut the ceremony, not the code.** The code change is two entries in a list literal; the expensive part was never the change, it was the 13-AC verification structure around it. Deleting the code leaves a latent arm-safety path that will need re-planning later — and re-planning costs more than the two lines.

Concretely: story 01 keeps AC-1, AC-2 (the change), AC-4, AC-5 (the two guards catching the two realistic wrong implementations), AC-8/9/10 (the flag), AC-11, AC-12, AC-13. AC-3, AC-6 and AC-7 move into the pack as GUARD rows, where they are cheaper and better placed.

**One caveat that must travel with the recommendation.** TN-7's equal-bands finding means the reorder has **no safety cushion across roughly a third of the pitch range** — it is exactly equal there. The one-way guarantee is a statement about today's tables, not a structural property. That does not change the recommendation; it does mean the guarantee must not be restated later as though the reorder is inherently safe.

---

## 3. What survives if the reorder is cut

Recorded so the option stays costed, not because I recommend it.

**Orphaned**: TN-1, TN-2, TN-3, TN-14, TN-15 entirely; TN-13 partly (the docstring still needs correcting, but to describe *current* behavior); AC-1 through AC-7, AC-11, AC-12, AC-13; **OQ-3 in full** (it certifies the CHANGE/GUARD matrix); IDEA-172's promotion path.

**More important, and the lead's instinct is right — for a sharper reason than stated**:

- **The observability flag (TN-5, AC-8/9/10) becomes the epic's entire live-population value, and its only detection mechanism.** Not merely "more valuable": under (c) it is the *sole* thing that would ever tell anyone the population had changed. That promotes two currently-soft items to hard requirements: the record must distinguish which tier word collided (so a varsity collision is legible as the reorder's trigger), and the operator's ruling on logging raw team names must be obtained, because the flag stops being optional.
- **TN-9 flips role** — from "don't over-read the pack" to the *justification for not acting*. It would then need the 13.6% bound stated in it directly, not left in TN-4, because that number is what a future reader will re-litigate.
- **TN-16 / the pack** is unaffected and becomes the epic's headline.
- **The tripwire** is entirely independent and unaffected in every option.

---

## 4. What must not be cut

A trim is a sweep, and this session's record on sweeps is poor. **The governing rule for the trimmer: relocate, do not delete. Leave a pointer at every excision.** Everything I marked ballast above is *misfiled*, not worthless — TN-8's failure catalogue in particular is the most transferable thing this epic produced.

Apply the criterion-vs-evidence cut to the trim itself. **Protected:**

1. **Every EVIDENCE-class figure**, already enumerated in the iteration-1 audit §0.3: TN-4's 14 (bare-token pool), AC-7's 14U `youth_travel` value, TN-11's `:368`/`:523`, `0 of 563`. These record what was observed. Editing them destroys the record.
2. **The criterion-versus-evidence rule itself**, in all four places it now lives — TN-11 item 4, AC-7's evidence clause, TN-16's per-row CRITERION/EVIDENCE declaration, E-275-02 AC-9. It is the most reusable thing here and it is exactly what a tidying pass would flatten.
3. **AC-4's role-flip warning.** It caught a broken fail-first AC list, and RULING 4's original text still says four patterns, so the trap is live for any future reader.
4. **The GUARD/CHANGE fail-first analysis** in story 01's AC-9/AC-10 preamble — *"absence-of-feature makes an emission assertion discriminate and an absence assertion vacuous."* One sentence preventing an impossible DoD demand.
5. **TN-13's grep trap.** Already fired on a real reviewer.
6. **TN-5's derived-rule framing and `frosh`.** The specific instance is minor; the principle (a hand-transcribed second list drifts) is the canonical-seams discipline reaching a spec artifact.
7. **SE's verbatim measured statement and the four-item divergence**, including *"do not write the range as 81-105"* and the equal-bands caveat. Three attempts have already understated this figure.
8. **TN-17's both-halves gate statement and the certification of record**, including that a worktree run lands in example mode and certifies nothing. Cutting either half restores the one-sided version that produced a false audit finding.
9. **The 13.6% upper bound.** It currently sits in one clause of TN-4's sufficiency paragraph. It is the number the scope decision rests on and it should be promoted, not trimmed.

**Two things I would delete outright rather than relocate**, because they are actively wrong rather than misfiled:

- **TN-4's *"there is no longer a numeric coincidence to disambiguate"*** — F14. False; the two 22s are live and one of them is TN-4's own denominator.
- **The History entry's count** *"11 MUST FIX, 13 SHOULD FIX"* — the audit now carries 14 MUST FIX (F14 added). Re-derive from the artifact rather than restating.

---

## 5. Net effect

| | now | after trim | change |
|---|---|---|---|
| `epic.md` | 385 | ~230 | −40% |
| Technical Notes | 272 | ~155 | −43% |
| Story 01 ACs | 13 | 9 | 4 relocated |
| Story 02 ACs | 10 | 10 | +4 absorbed |
| Code shipped | reorder + docstring + flag + tests | **unchanged** | — |

**Nothing in this trim removes a single line of specified code, and nothing removes a rule.** It relocates roughly 150 lines of planning-session record into the two artifacts built to hold it — `.project/research/` and `.claude/rules/tool-output-integrity.md` — and it applies a duplication ruling PM2 already made but did not execute.

**Context health: tight.** Every figure above was re-derived from the files at `073a336`, not restated from my iteration-1 audit.

---

## 6. Addendum — the IDEA-205 input, and what it does and does not change

Read from `IDEA-205` directly, not from the relay. **It changes the flag's justification. It does not change the flag's design, and it does not change §2.**

### 6a. Verified: the flag does miss the observed misfire

IDEA-205's own open question: *"that flag fires on a Legion token **beside a tier word**, and this misfire needs no tier word. A name carrying bare 'Seniors' and nothing else is exactly the shape the flag will not catch."* Independently confirmed inside the epic — TN-5's re-derivation states **0 of the 5 soft-`seniors`-only names carry any tier word at all**. The relay is correct on the fact.

### 6b. One correction I owe, and one point the relay omits

**(1) ⛔ ATTRIBUTION CORRECTED 2026-07-27 — the error here was mine, and it is this session's signature defect.**

> **What this section originally said**: *"The relay carries a strength IDEA-205 has retracted. It says the misfire was observed 'in two independent corpora.'"*
>
> **That is false, and team-lead checked its own sent text rather than its memory of it.** The relay said *"the flag would not catch the **one confirmed live misfire** this epic actually observed"* — **singular, and already at the retracted-down strength.** It did not carry "two independent corpora" or "observed twice."
>
> The phrase was team-lead's earlier in the session, in a message to coach, **while it was still coach's own live claim and before api-scout retracted it**. So the phrase is real and it was team-lead's; it was simply not in the message I was reading when I attributed it.
>
> **I asserted what a document said without re-opening the document.** Individually plausible, wrong on checking — the same shape as the six other instances this epic has catalogued (TN-8 items 3-6), and the second time I have produced it tonight after F1 claim 1. Recorded rather than quietly fixed, because a corrected record of who said what is the point of TN-8's catalogue and I do not get an exemption from it.

**The substantive finding is unaffected and stands on its own**, independent of who said what: the phrase **IS** retracted by IDEA-205 and **must not be restored** — both observations are from the **same operator's network**, the propping "sibling squad" inference was tested and withdrawn, and it is **1 confirmed live misfire, not 4**. IDEA-205's own summary: *"Two observations establish that the misfire HAPPENS; they establish nothing about how OFTEN."*

**And the epic is clean of it.** I swept `epic.md` and both stories for the retracted phrasing. **No residue.** TN-3 leg 2 states it correctly at n=1-on-one-network, carries the do-not-cite-the-sibling-reasoning warning, and adds a constraint I would have proposed if it were absent: *"No acceptance criterion may imply or depend on a rate."* Background's only use of "independent" cites the collapse deliberately, as a contrast. **Nothing to fix — that sweep is the useful half of this section, and it never depended on the attribution.**

**(2) The two defects fail in OPPOSITE directions — this the relay genuinely did omit, and team-lead has accepted it as the point that changes the conclusion.** This is the reframing that keeps a true observation from becoming a wrong conclusion:

| | direction | class | observed? |
|---|---|---|---|
| **Reorder defect** | **UNDER-**rest | arm safety | 0 instances; ~13.6% upper bound |
| **Bare-`seniors` misfire** | **OVER-**rest | data accuracy — IDEA-205: *"a bench day rather than an arm … a data-accuracy defect rather than a safety one"* | 1 instance, 1 network |

So "the flag misses the epic's only observed defect" is true — **and the observed defect is the milder class.** The flag is aimed at the severe-but-unobserved shape. That is not a mis-aim; **it is the same posture as the reorder itself**, and the epic is at least consistent.

### 6c. Answering the question plainly: is the flag aimed at the wrong shape?

**No. It is correctly aimed and wrongly described.** The criticism kills TN-5's *claims*, not the flag's design — and it kills them twice over:

1. It misses the one observed misfire (6a).
2. **Its five day-one firings are all Legion + `reserve(s)` — the one shape TN-6 has definitively CLOSED** ("No ruling change and no code fix… resolves to the safe side in every season branch"). **Firing five times on an adjudicated-benign condition is not "new information about the live population."** It is an alert on a settled question.

So TN-5's *"the widest reach in this epic"* and *"the only part of this epic that produces new information about the live population"* are both overclaims, and the second is close to backwards on day-one behaviour. **The flag's honest value is prospective**: it detects the **arrival** of the reorder-relevant shape in a population where that shape has never been seen. That is real, it is worth having, and it is a different claim from the one TN-5 makes. It must be rewritten whichever option is chosen.

### 6d. The alternative trigger — recommend WIDEN, not swap, and route the decision

A trigger on *a `legion` resolution resting on `seniors`/`juniors` alone, with no corroborating signal* would catch the observed misfire. Weighing it:

**Against**: coach routed this defect out of E-275 explicitly; Non-Goals excludes it; it addresses the milder class; and IDEA-205's own open questions say the fix direction is unsettled (*"removal beats refinement — but that needs the population characterized first, not assumed"*).

**For**: a **detector is not a fix** — the Non-Goal excludes making the pattern more selective, which is the expensive part, not observing it. It appears implementable as one more condition on the same logging call (**SE to confirm; I am not asserting implementation cost from reading**). And decisively, **IDEA-205's own timing rule is *"promote when anything next touches the level-word patterns"* — which is exactly what E-275-01 does.** By the idea's own criterion this is the moment.

**Recommendation: widen the trigger to cover both shapes, as observability only, and route the call to coach and the operator** — it touches a deliberately de-scoped area and is not mine to settle. If declined, TN-5 is rewritten anyway per 6c.

### 6e. Effect on the recommendation and the value ordering

**§2 is unchanged.** The reorder recommendation rests on under-rest and the ~13.6% bound; the flag question does not touch it.

**The value ordering changes, and this is the third time it has needed correcting.** Honest order: **(1) fixture pack + tripwire, (2) the reorder, (3) the flag.** The flag drops below the reorder because its present-day output is five alerts on a closed question while the reorder addresses an arm-safety path with a wide confidence interval.

**Does the flag still belong in this epic?** **Yes, as a small rider.** It is independent of the reorder, it is one logging call plus three ACs, and cutting it costs a re-plan later worth more than the rider. But under option (c) the calculus inverts: as §3 notes, the flag would become the *sole* detector, and 6c shows what it would then be detecting — arrivals, not the defect already on file. **That makes (c) weaker than it first appears, not stronger**, and is a second independent reason to prefer (b).
