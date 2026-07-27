# E-275: Classifier Hardening -- Legion Precedence, Constant Tripwire, Ground-Truth Fixture Pack

## Status
`DRAFT`

## Overview

`detect_league_level()` picks the pitch-count rule table a coach sees on the probable-starter card. One new instrument and two hardening changes, in **descending** order of durable value -- the first item is worth the most:

1. **A ground-truth fixture pack** -- operator-labeled input shapes, each carrying the league a human says is correct, executed as a test and appended to over time. Both classifier defects found in the last month were found ONLY by ground truth; a green suite and two closure reviews caught neither.
2. **A divergence tripwire** on the three byte-identical pitch-count constants, pinned to literal values so that a change to any one is caught independently. Grouped with the pack: same story, same instrument class, and it closes two gaps SE measured rather than the vacuous one originally proposed.
3. **A narrowed precedence fix** promoting `legion`/`american legion` and `post \d+` ahead of `\bvarsity\b`, closing a masked under-rest path.

> **⚠️ THIS VALUE ORDERING HAS BEEN CORRECTED THREE TIMES. Do not restore an earlier one, and do not trust a summary of this epic that disagrees with it.** It was first written *ascending* (making the tripwire the most valuable item, which inverted the epic's own Background); then corrected to descending with an observability flag ranked second; then corrected again when the flag's day-one output was measured and it fell below the reorder. **The flag was subsequently cut entirely** (Non-Goals; [[IDEA-213]]). A reader who inherits a stale ordering mis-prioritises everything downstream, which is exactly what happened twice.

## Background & Context

**Origin.** Promoted from IDEA-172, via the spec-seeded handoff at `/tmp/.worktrees/baseball-crawl-E-275/.project/research/2026-07-26-fable-audit/handoff-P2v2-classifier-spec-seed.md`. That seed is a RELAY, and this epic supersedes it wherever they disagree -- five of its claims were falsified against the repo during planning (recorded in TN-11).

**The defect.** `_LEVEL_WORD_PATTERNS` (`src/reports/starter_prediction.py`) is scanned in list order and the first match wins. `\bvarsity\b` sits ahead of every Legion-explicit pattern, so a name carrying BOTH an explicit Legion token and the generic word "Varsity" resolves off "Varsity". When the season token is anything other than `summer`, that lands on `nsaa_varsity` -- which requires strictly less rest than `legion` at **four** places, not three: the bands 46-50, 61-70 and 81-90 post-April, **plus every count from 81 upward without an upper bound pre-April**. An explicitly Legion-named team is served the less conservative table.

> **Why the count is spelled out here rather than left at "three bands."** This sentence read *"at three pitch bands"* until 2026-07-27. That form drops the pre-April item **and matches, exactly, the comment block TN-8 forbids citing as evidence** -- so the epic's headline statement of its own defect agreed with the forbidden source and disagreed with the measured one. TN-7 carries SE's verbatim; use it wherever the divergence is stated. *(Propagated from TN-7 during spec-audit triage; SE has been asked to confirm TN-7's verbatim is final.)*

**The measurement that reframed this epic, and the reason the value ordering above is inverted from the original proposal.** api-scout ran the fix against a real corpus of **563 distinct team names harvested from 1,754 JSON-parseable response bodies (2,518 stored bodies, out of 16,665 logged requests), captured across 4 proxy sessions on 2026-03-11 and 2026-03-12** (`proxy/data/sessions/`). **The reorder changes zero of 563 names**, under both the original four-pattern move and the narrowed two-pattern move. "Legion Varsity" occurs zero times and reads as a constructed example. `\bjuniors\b` is unattested across all 2,518 stored bodies.

**The honest bound on that measurement, which belongs next to it rather than in a footnote.** This is one operator's ordinary browsing over a **two-day window**, not a broad or varied capture. Of 24 session directories, 12 carry a request log and only **4 store response bodies at all** -- one logs 5,872 requests and contributes zero names. So "the core fix changes nothing observable" is well-evidenced *for what was browsed on those two days* and is not a claim about the whole population. If this epic's scope is priced on that sentence, this is the limit someone will eventually ask about, and it should be visible now rather than then.

*(Provenance figures corrected 2026-07-27. An earlier draft said "2,518 raw response bodies across 12 capture sessions" -- the session count was 3x too high, because it counted sessions carrying a log rather than sessions carrying usable data, and 2,518 is the stored-body count rather than the harvest basis. Both were api-scout's figures, self-corrected.)*

That does not falsify the defect -- it is real in the code and the direction is right -- but it changes it from *actively mis-serving reports* to *reachable but unobserved*. The epic was scoped when the seed framed it as "live, under-rest direction." It is live in the sense that the code path exists and would fire; it is not live in the sense that any coach is seeing a wrong number today. **The fixture pack and the observability flag, not the reorder, are what this epic is actually worth.** Stated here so that neither a reviewer nor a future reader mistakes a green fixture pack for evidence of real-world impact.

**Two independent instruments reached "this changes nothing observable", and the independence is real this time.**

- **api-scout, from the DATA side**: the triggering name shape does not occur -- **0 of 563** -- where the name path *is* reachable.
- **SE, from the CODE side**: the name path is **unreachable whenever `ngb` is recognized** -- 792 combinations across 11 `ngb` values, **24 changed under the narrowed ruling, every one an `ngb`-empty row**. Cite the zero-on-recognized-`ngb` result rather than the raw count: the count is an artifact of SE's sentinel corpus, the zero is a property of the code.

Different instruments, opposite directions, neither derived from the other. **The contrast is worth stating because this epic has already had one independence claim collapse under checking** -- the `seniors` misfire's "two independent corpora" turned out to be two observations on one operator network (TN-3, leg 2). That one failed on a shared source; this one has none.

**Blast radius under the NARROWED two-pattern ruling: 36 changed combinations of 12,096, 3 distinct names** (`American Legion Varsity`, `Legion Varsity`, `Post 77 Varsity`), one transition only, `nsaa_varsity → legion`. **⚠️ Every blast-radius figure measured before the narrowing assumed all FOUR patterns moved and is now wrong -- the four-pattern figures were 60 changed / 5 names, and the four-pattern `ngb` figure was 36.** Neither stale figure appears anywhere in this epic; do not reintroduce them.

**Why the reorder is still worth doing anyway:** it is a two-entry list move, the failure direction is confirmed safe **on the measured curve** (TN-7), and it removes a hazard that is masked rather than absent -- the mask is the season signal, and season signals drift.

## Goals

- Close the `varsity`-shadows-Legion precedence path for the two well-attested Legion patterns.
- Establish a durable, append-only ground-truth fixture pack as the standing instrument for classifier correctness.
- Make a deliberate divergence of the three byte-identical pitch-count constants fail loudly, and fail with its downstream consequence named.

## Non-Goals

- **This epic does not claim to change any currently-observed report.** Every discriminating acceptance criterion is necessarily synthetic, because the real corpus contains no instance of the targeted shape. See TN-9.
- The four adjacent MINORs from the seed (`_parse_ngb` case asymmetry, case-sensitive `classification` compare, substring-vs-word-boundary matcher divergence, the weak `test_legion_ngb_beats_14u_bracket`) -- captured as ideas, not built. Operator ruling.
- The 8U-14U travel-bracket suppression defect (coach's URGENT CORRECTION) -- E-274's lane. See TN-12.
- Promoting `seniors`/`juniors`. Deliberately excluded on evidence; see TN-3.
- **The ambiguous-name observability flag, and the second, disjoint flag proposed alongside it.** Both cut by operator ruling 2026-07-27 and relocated **in full** to `.project/ideas/IDEA-213-ambiguous-name-observability-flags.md` -- specifications, SE's five-condition predicate, the disjointness measurement, and the logging decision (default: a **shape summary**, not the raw team name). **Cut, not abandoned.** The governing rule: *a confirmed live defect gets a fix or an explicitly-homed follow-up, never just a log line watching for its shape.*
- Fixing the bare-`seniors`-misfires-on-a-school-team defect. Real, pre-existing, and **structurally unreachable from this epic**: SE established by execution that only `\bseniors\b` matches such a name, and a single-match name is order-independent by construction -- the most aggressive possible reordering still resolves `legion`. The fix belongs to **E-274's school-family branch**, where the correct resolutions are already ruled and merely unimplemented. Homed in **[[IDEA-205]]**, whose severity classification was corrected 2026-07-27: it **under-rests** on `high_junior_varsity` and `high_freshman`, and errs safe only on `high_varsity` -- the value the one observed instance happens to carry.
- Implementing an `NNO` age-bracket form (`18O`), `little_league` ngb recognition, or the rec-family `Under 13`/`Over 18` rulings. Ruled by coach, not implemented, recorded in the pack's Tier 2.
- Any change to `max_pitches` semantics or any assertion that a daily cap is enforced. See TN-8.

## Success Criteria

- A name carrying `legion` or `post N` beside `varsity` resolves `legion` in every season branch, where today it resolves `nsaa_varsity` in all non-summer branches.
- The fixture pack executes green, and each of its CHANGE rows fails against pre-fix code.
- Each of `LEGION`, `NRBL` and `PITCH_SMART_15_18` is pinned such that a change to any ONE of them fails a test independently of the other two.
- **The safety property is asserted in BOTH stories, each scoped to what that story builds**: no name's post-fix league (E-275-01) and no fixture row's post-fix league (E-275-02) requires strictly less rest than its pre-fix league at any pitch count -- **and at least one requires strictly MORE**, so the pair cannot be satisfied by a no-op. TN-7's scope is RESOLVED; the universal stands unhedged and is no longer pending.
- **Closure obligation A (TN-10)**: `.claude/rules/pitch-rules.md`'s NRBL section states the IDEA-178 shadow consequence -- that `ngb=american_legion` resolves before the NRBL branch is reachable.
- **Closure obligation B (TN-10)**: `.claude/rules/pii-safety.md`'s "Coverage footgun" section no longer asserts that `epics/**` and `.project/**` are ungated, and IDEA-102's status is re-checked against `.githooks/pre-commit`.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-275-01 | Narrow Legion precedence fix and docstring correction | TODO | None | - |
| E-275-02 | Constant divergence tripwire and the ground-truth fixture pack | TODO | E-275-01 | - |

## Dispatch Team

- software-engineer

Both stories are Python implementation and test work confined to `src/reports/starter_prediction.py` and `tests/`. No context-layer path is modified during dispatch -- the one context-layer edit this epic identifies is deferred to a named closure obligation (TN-10), which routes to claude-architect through the standing Context-Layer Assessment Gate rather than through the dispatch team.

## Technical Notes

### TN-1: The pattern list and what moves

`_LEVEL_WORD_PATTERNS` is a list of `(compiled pattern, level class)` pairs scanned in order; first match wins. It currently holds nine entries: four sub-varsity patterns (`junior varsity|jv`, `freshman|frosh`, `reserves?`, `sophomore`), then `varsity`, then four Legion-family patterns (`american legion|legion`, `post \d+`, `seniors`, `juniors`).

**Exactly two entries move**: `american legion|legion` and `post \d+`, to positions immediately ahead of `varsity`. The four sub-varsity patterns stay ahead of everything. `seniors` and `juniors` stay where they are, behind `varsity`.

**There are FOUR Legion-family patterns, not three.** The seed says three in two places. The code, RULING 4 and IDEA-172 all say four. Anything derived from the seed's count is wrong.

### TN-2: Why the sub-varsity patterns do not move, and why that is deliberate

The reorder is scoped to the varsity boundary only. Extending it downward -- promoting Legion patterns ahead of `jv`/`freshman`/`reserves?`/`sophomore` -- would be **actively harmful in every non-summer branch, not merely unnecessary**: it would flip a currently-conservative resolution to a less-conservative one and manufacture a new masked under-rest risk in the exact spot this epic exists to remove one from. A Legion-plus-JV name resolves to the sub-varsity class today; `NSAA_SUBVARSITY` requires 1 rest day in the 1-30 band where `LEGION` requires 0.

**State the non-summer scope, do not drop it.** In the **summer** branch a Legion-plus-sub-varsity name resolves `nrbl`, which per TN-6 is byte-identical to `LEGION` -- so there the rest numbers do not move and the harm is zero, label only. The conclusion is unaffected, because TN-15 establishes non-summer as the live shape. But a reader who checks the summer branch, finds no harm, and sees this note claiming harm unconditionally has been handed a reason to distrust a note whose whole job is to stop the asymmetry being read as an oversight.

**Scope correctly stopped at the boundary where the fix direction reverses.** A future reader who sees the asymmetry as an oversight is the failure mode this note prevents.

Supporting intuition, explicitly NOT the reason and not load-bearing: unlike "varsity", a pure tier label carrying no age information, the sub-varsity words describe roster composition and suggest a younger arm population that may be better served by stricter numbers regardless of governing body. Coach has not checked this against any name sample.

### TN-3: Why `seniors` and `juniors` are NOT promoted -- carried by PATTERN FORM, not by safety and not by misfire frequency

This is the reason. Do not write the safety-direction argument here; coach has retired it for this purpose.

**⚠️ THE THREE LEGS ARE ORDERED DELIBERATELY, AND THE ORDER IS COACH'S (2026-07-27).** An earlier draft led with the misfire evidence and buried pattern form last. **Coach re-ordered it: leg 1 is retired, leg 2 is corroborating color at n=1, and leg 3 is what actually carries the ruling.** Restore the old order and the narrowing appears to rest on a single observation, which is the one thing it must not appear to rest on.

**LEG 3 -- PATTERN FORM. This is the reason the narrowing stands, and it needs no sample size at all.** These two patterns are **plural-only** (`\bseniors\b`, `\bjuniors\b`), and plural is not the form Legion naming actually takes. `\bjuniors\b` is unattested across all 2,518 stored bodies. Singular `Senior Legion` **is** attested. Widening the patterns to the singular would take co-occurrence from 0 to 4 -- and **all four are `Junior Varsity`**, where "Junior" is half a tier phrase rather than a Legion division name, so widening would manufacture four false Legion signals out of four ordinary JV teams. **The weakness is in these patterns themselves, not in their position in the list.** Reordering them answers the wrong question about them.

> **Why this leg cannot be attacked on statistical power, unlike the other two.** It is a claim about English usage and token ambiguity -- a plural pattern set against singular attested usage, and one plural word (`seniors`) that carries an ordinary graduating-class meaning competing with the Legion sense. **It does not weaken when the misfire count drops.** Coach notes this leg **predates the corpus work entirely** -- the same concern is in RULING 4's original falsifier text, written before any name corpus existed. The corpus **sharpened** it with concrete form; it did not replace it with a frequency count.

**LEG 2 -- THE MISFIRE. Corroborating color at n=1, and it must be described at its true strength.** One confirmed live instance: a real school-family team (`age_group=high_varsity`, no Legion token, no age bracket) carrying "Seniors" in the graduating-class sense resolves `legion` today. **ONE observation on ONE operator network, not independently replicated** -- api-scout retracted its own "two independent corpora" claim and the sibling-squad reasoning that propped it up; **do not restore either.** **This establishes that the failure mode EXISTS and nothing about how OFTEN.** Full basis, corrections and the corrected severity: **[[IDEA-205]]**.

The general point leg 2 supports: **precedence should track signal reliability, not only failure-direction safety.** Promoting a demonstrated-unreliable signal ahead of a clean one (`varsity`: 31 names, zero known misfires) is the wrong call even when the wrong-guess cost is mild.

**LEG 1 -- SAFETY DIRECTION. RETIRED for this purpose; recorded so nobody re-derives it as new.** The original ruling held `seniors`/`juniors` back on it: `legion` requires equal-or-more rest than `nsaa_varsity` at every pitch count, so a wrong promotion **never under-rests**.

> **"Never under-rests" is NOT interchangeable with "fails toward over-rest."** The first asserts the absence of the bad direction; the second asserts a positive one, and the positive claim is **false across most of the range**, because in the equal bands nothing changes at all. A one-word substitution here leaves a false claim standing -- exactly how someone in a hurry would execute this edit.
>
> **⚠️ And do NOT carry leg 1's direction claim over to the bare-`seniors` misfire, which is a different scenario with a different answer.** There the comparison is against `NSAA_SUBVARSITY` on two of three school-family values, and `legion` **under-rests** those. [[IDEA-205]] made exactly that over-generalisation and was corrected 2026-07-27.

`juniors` has no misfire evidence and no attested co-occurrence either way. It is held with `seniors` as a judgment call, stated as one: they are one lexical family, and leg 3 applies to `juniors` more strongly than to `seniors`, not less -- the plural form is unattested entirely.

Source and follow-ups, cited so a future reader who wants to revisit the narrowing finds the real reason instead of re-fighting the co-occurrence question TN-4 says cannot be answered: `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md`, §"The zero is LOAD-BEARING on the patterns being plural-only" and §"Provenance and skew bound"; **IDEA-205** (`seniors` is an unreliable Legion signal) and **IDEA-206** (the `juniors` pattern may target the wrong word form).

> **CONSTRAINT ON ANY AC DERIVED FROM THIS NOTE.** Leg 2 is one instance, one network. **That establishes the misfire HAPPENS and nothing about how OFTEN.** Leg 3, which carries the ruling, needs no rate at all. **No acceptance criterion may imply or depend on a rate**, and none currently does -- this constraint exists to keep it that way.

### TN-4: TWO falsifiers, two denominators -- one ran, one cannot be run

There are **two different falsifiers** here and an earlier draft of this note conflated them. Keeping them apart is the whole point of this section.

| Falsifier | Question | Denominator | Result |
|---|---|---|---|
| Coach's original, **bare-token** | Do real non-Legion names carry `seniors`/`juniors` at all? | **14** | Pool is below coach's floor of 30 -- **CANNOT BE RUN** |
| PM's narrowed, **co-occurrence** | Do real names carry a Legion token *and* a tier word together? | **563** | **0 hits** |

The **14** is the senior/junior token pool: 8 `seniors` (plural) + 2 `Senior` (singular) + 4 `Junior` (singular) + 0 `juniors` (plural), out of 563 total names. No name carries both a senior\* and a junior\* token, so the union is a clean sum. Coach's 30-50 sufficiency bar was set for this bare-token framing and **does not travel to the co-occurrence narrowing**, which sits on the full 563.

**The "second 14" is GONE -- it was wrong; the correct figure is 9.** Of the **22** names carrying a hard Legion token: 9 bare, 5 `reserve(s)`, 4 bracket-only, 3 `seniors`, 1 singular `Senior`, **0 `varsity`**. *(How that error was made -- api-scout's own memory file warned against the exact omission it then committed one section earlier, and only re-derivation caught it -- is recorded in `.project/research/E-275-planning-record.md` §3, with the full narrative.)*

> **⚠️ THE 9 ANSWERS *THIS NOTE'S* QUESTION AND IS NOT THE OTHER 22-DENOMINATOR FIGURE.** It is computed over hard-Legion-token names with a tier set that counts `seniors` and a `\d+U` bracket AS tier words. The other set counts `seniors` as *Legion-family* and a bracket as neither, and its figure is **22**. Substituting 9 there would transplant a figure across a definitional boundary -- it was nearly done. **Both sets are now stated together in the absorbed block below**; this note previously pointed at E-275-01 AC-9, which no longer exists.

**The two 14s dissolved, and TWO 22s replaced them -- so this note's job is not finished, only relocated.** The colliding pair is now **this note's own denominator** (22 = hard-Legion-token names) and **AC-9's** (22 = any TN-5 Legion-family token, no tier word). They share **17 members**: this note's includes the 5 Legion+`reserve` names the other excludes, and the other includes the 5 soft-`seniors`-only names this note's excludes. Disjoint by 5 in each direction, equal in size by accident. The senior/junior token pool (14 of 563) in the table above is the only surviving 14.

> **THE SECOND 22, ABSORBED HERE 2026-07-27 because its previous home was cut.** It lived in E-275-01 AC-9, which went to [[IDEA-213]] with the observability flag; this note pointed at it and the pointer would now dangle. **It belongs here anyway** -- the spec audit's F14 said so at the time: *"the disambiguation landed in the consumer and not in the note that owns the concern."*
>
> **The other 22** = names carrying ≥1 of {`legion`, `american legion`, `post \d+`, `\bseniors\b`, `\bjuniors\b`} and NONE of {`\bvarsity\b`, `\bjv\b`/`junior varsity`, `\bfreshman\b`/`\bfrosh\b`, `\breserves?\b`, `\bsophomore\b`}, denominator 563. Composition: 17 hard-token names with no tier word + 5 soft-`seniors`-only names; brackets present on 6 of them, since a bracket is not a tier word under that set.
>
> **In this material a matching count is NOT evidence that two figures are the same quantity** -- there have now been two 14s (dissolved when one became 9) and two 22s. **And the `9` above answers THIS note's question only**: it counts `seniors` and a `\d+U` bracket AS tier words, where the other set counts `seniors` as *Legion-family* and a bracket as neither. Substituting one for the other transplants a figure across a definitional boundary; it was nearly done once.

> **Do not restore the sentence that used to close this paragraph** -- *"there is no longer a numeric coincidence to disambiguate."* It was false when written: the replacement collision already existed. It sat in the closing position of a note whose own warning block, two paragraphs above, says to re-derive rather than re-read.

> **If you are checking a count in this epic, re-derive it -- do not re-read it.** Every corrected figure here was caught by executing the check differently; not one by careful re-reading. The worked instances are in `.project/research/E-275-planning-record.md` §2.

**⚠️ THE ~13.6% BOUND IS THE FIGURE THIS EPIC'S SCOPE DECISION RESTS ON. Do not trim it, and do not let `0 of 563` be quoted in its place.** With **22** Legion-token names observed and **zero** carrying `varsity`, the rule-of-three 95% upper bound on the co-naming rate among Legion-named teams is **~13.6%**. So `0 of 563` does **not** mean *this does not happen* -- it means the true rate could be anything up to roughly **one in seven Legion-named teams**, and this corpus cannot distinguish those. Read against TN-9's skew bound (one operator's network, one region, a two-day window, 313 of 563 names from a single endpoint), "unobserved" carries far less weight than the bare zero suggests. **This is why the reorder ships despite changing nothing observable.**

**Split sufficiency verdict -- never write an unqualified "the sample was sufficient".** api-scout narrowed its own verdict: the corpus **is** sufficient to settle the `legion`/`post N` question (the zero-overlap null above is informative) and **insufficient** to settle the `seniors`/`juniors` one. Note the shape of that: **the sample is well-powered on exactly the half coach considers low-risk, and underpowered on exactly the half coach is worried about.** Coach's requested stratification by season is unavailable at any sample size here -- `season` is absent on all 14, because opponent and search payloads carry no `team_season`.

**`reserve` is NOT in the co-occurrence tier set**, so the 5 Legion + `reserves?` collisions (TN-6) are invisible under the 0/563 framing. They are real and they are the only Legion-versus-tier-word collision in the corpus. **Do not let "0 co-occurrences" be read as "no such collisions exist."**

Both RULING 4 and IDEA-172 point at an "18-team sample" as the place to run this check. **That sample does not exist as a name corpus** -- it was an `age_group`-population probe of `membership_type='tracked'` opponents, and `docs/api/endpoints/get-public-teams-public_id.md` already records its population as a *sampling artifact* (cited by content rather than by line, per S10). **Both references have already been corrected** -- past tense, and the corrections are readable at three anchors rather than pending as work: the dated correction kept as a pointer in `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`, the struck-through inline correction in IDEA-172, and api-scout's blunter third (*"Do not send anyone there again"*) under the "18-team sample is a MISNOMER" heading of the corpus note.

**Citable source for every corpus figure in this epic**: `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md`. This is the artifact OQ-4 asked for, it exists, and it is where a re-derivation starts. Prefer it over any figure restated in this epic -- the epic is a relay of it, and this note records seven figures that did not survive checking.

### TN-5: The observability flag -- CUT, relocated to IDEA-213

**RELOCATED IN FULL to `.project/ideas/IDEA-213-ambiguous-name-observability-flags.md`** when both flags were cut by operator ruling, 2026-07-27. The note number is retained rather than reused, so citations to "TN-5" from archived messages and from the trim audit still land somewhere true.

**What went with it, named so nobody rebuilds it from scratch:** the derived-rule trigger framing and coach's `frosh` ruling (*"a hand-transcribed second list drifts the moment the first one changes"* -- the canonical-seams discipline reaching a spec artifact); api-scout's re-derived **5**-name day-one measurement and the warning that the `0` and the `5` answer different questions and must never be merged; and the raw-team-names-in-logs decision, which the operator has since given a **default of a shape summary**, on the ground that reports are an access-gated product surface while application logs get copied, pasted into issues and shipped onward -- a **new surface class, stricter default**.

**Two of this note's claims did not survive measurement and are corrected in IDEA-213, not here:** *"the widest reach in this epic"* and *"the only part of this epic that produces new information about the live population."* The flag's five day-one firings are all Legion+`reserve(s)` -- the one shape **TN-6 has definitively closed** -- so its day-one output was an alert on a settled question, and SE later measured that bracket-bearing and `ngb`-bearing names fire too, with resolutions never in doubt.

### TN-6: Legion + `reserves?` is closed, not open

5 of 563 real names carry a Legion token together with `\breserves?\b`. `reserves?` sits at priority 3, ahead of `varsity` and ahead of the Legion patterns in BOTH the current and the narrowed order, so these resolve to the sub-varsity class either way and the reorder does not touch them. Coach has traced both season branches against the sourced tables: summer resolves `nrbl` (byte-identical to `LEGION`, so identical rest numbers, label differs only); spring or season-absent resolves `nsaa_subvarsity`, which is equal-or-stricter than `LEGION` at every count. **No ruling change and no code fix.** These names are a GUARD row in the pack, not a defect.

### TN-7: The safety property -- RESOLVED, universal stands unhedged

**Scope resolved 2026-07-27.** SE enumerated every exclusion axis by execution; no axis diverges, so the property below is a universal and is **not** to be hedged or rest-tier-scoped.

**The property is pinned in THREE places, and all three must be checked together** -- an earlier draft of this line pointed at a single AC, and an earlier draft still pointed at the *wrong* AC (`E-275-01 AC-9`, which carries no pending marker of any kind, so a reviewer following the pointer would land on an AC with nothing pending, conclude the finalization had happened, and let the real one ship unresolved):

| location | scope |
|---|---|
| **E-275-01 AC-12** + its non-vacuity companion **AC-13** | every **name** this story resolves |
| **E-275-02 AC-10** | every **fixture row** the pack builds |
| this note | the measured curve both assert against |

Story 01 cannot verify a fixture-row-scoped property -- E-275-02 builds the rows and is blocked by story 01, so at story 01's DoD there are zero of them and the assertion is vacuous. That is why the property is scoped twice rather than stated once.

**The property**: no **name** (story 01) and no **fixture row** (story 02) may have a post-fix league requiring strictly less rest than its pre-fix league, at any pitch count -- **and at least one must require strictly MORE**, because the "never less" half alone is vacuously satisfiable by a no-op and certifies nothing on its own. Both halves, in both scopes.

**SE's measured statement, verbatim -- use this wording, not a paraphrase:**

> The reorder can never make the engine less conservative for an affected team. At every pitch count 1-130, LEGION requires at least as much rest as either NSAA Varsity table, and less at none -- so an arm that today is called available can only become unavailable, never the reverse. The direction is one-way, but the margin is **not uniform**: LEGION is strictly stricter at 46-50, 61-70 and 81-90 (one day more at each, and 81-and-above unbounded against the pre-April table), and **exactly equal everywhere else**. So the correct claim is *never under-rests*, not *over-rests*.

**⚠️ THE DIVERGENCE IS FOUR ITEMS, NOT THREE -- and the three-band form traces to the comment block TN-8 forbids citing.** SE measured it; use this verbatim wherever the divergence is stated:

> `nsaa_varsity` requires strictly less rest than `legion` at three pitch bands post-April -- 46-50, 61-70 and 81-90, one day less at each -- and pre-April at those same two lower bands plus **every count from 81 upward without an upper bound**, because `NSAA_PRE_APRIL` has no tier above 90 and `_is_excluded` clamps any count past the top tier to that tier's rest days rather than excluding. At no pitch count in 1-130 does either NSAA table require more rest than `legion`.

**Do not write the range as `81-105`.** That upper bound comes from Legion's top tier, and Legion clamps too, so the gap never closes -- SE tested to 130 and it persists. Coach's amendment says "plus the top tier pre-April", which is directionally right but still sounds bounded; **do not inherit that phrasing unchecked.** This is a missing-enumeration-member in a safety figure, which is the defect class this epic has now produced three times.

**The equal bands are load-bearing and this qualifier must travel with the claim:**

> Because a third of the range is equal rather than stricter, the reorder carries no safety cushion there. A future edit that loosens LEGION by a single day in any equal band would flip the relation straight to under-resting with nothing absorbing it, so this universal is a statement about the tables as they stand today, not a structural guarantee.

**The axis enumeration behind the universal is RELOCATED** to `.project/research/E-275-planning-record.md` §1, with the primary execution record in `.project/research/E-275-se-execution-answers-F4-F6-S2-S6.md` §F4. Its one load-bearing conclusion, kept here: **of `_is_excluded`'s seven decision branches, exactly one -- rest-tier compliance -- reads the `rules` argument at all**, so every other branch reaches the same verdict for every league and the universal is not axis-limited. The consecutive-days rule **structurally cannot** be league-gated: `PitchCountRules` declares exactly two fields, so there is no consecutive-days field for a league to vary.

**What the property catches that no per-name row does**: a plausible misreading of the ruling that moves the Legion patterns to the FRONT of the whole list rather than just ahead of `varsity`, flipping a Legion-plus-sub-varsity name from the conservative sub-varsity table to Legion's looser one and dropping the 1-30 band from 1 rest day to 0. Coach has confirmed the property is the right encoding of the coaching standard and is not over-constraining.

### TN-8: Provenance -- one unverified comment produced two defects in this epic's planning

The comment block **preceding `_SUMMER_SEASON`** in `src/reports/starter_prediction.py` describes the season-default's safety characteristics. It is prose, it does not execute, and no test checks it. (Anchored by symbol deliberately: an earlier draft cited `:280-290`, and that range was already slightly wrong -- the block starts earlier and its safety text begins before the cited range. Two of this epic's source citations have already drifted; that is what TN-11 exists to record.)

During planning it produced two false claims that reached two separate agents:

1. **The daily-cap claim.** Both PM and baseball-coach independently reported that `nsaa_varsity` "permits more pitches post-April (110 vs 105)" as a *safety* difference. `max_pitches` is **never consulted by the exclusion gate** -- its only live use is a display string. **This is ONE inherited sentence read twice, not two separate errors.** Neither agent derived it; both took it from this comment and then appeared to corroborate each other. The cap clause is dropped **entirely** from the mechanism -- not demoted to constants-level color, because a reader can infer enforced behavior from adjacent prose.

2. **The season-default reasoning**, which coach and PM likewise both read and both cited before it was flagged.

**Rule for this epic: state the mechanism as rest-day requirements only, sourced to SE's measured curve. Never cite the comment block as evidence for a behavioral claim.** The general form of this lesson is already in `.claude/rules/tool-output-integrity.md` ("A claim you RELAY is a claim you AUTHOR"); this is a worked instance where two readers of one sentence looked like independent confirmation.

**EIGHT further instrument failures from this epic's planning and trim are RELOCATED to `.project/research/E-275-planning-record.md` §2** (items 3-6 there, plus four more the trim pass itself produced). They are a process lesson about tool output rather than a classifier spec, and they are the most transferable thing this epic produced -- **misfiled here, not worthless.** Item numbering is preserved there, so a citation to "TN-8 item 4" still resolves.

**The two rules they yield, kept here because ACs depend on them:**

- **A figure needs its DEFINING SETS attached, not just its value.** A bare number travels into a context that redefines its terms and is wrong on arrival with nothing to signal it. **In this material a matching count is NOT evidence that two figures are the same quantity** -- there have been two 14s and two 22s (TN-4).
- **Every corrected figure in this epic was caught by RE-DERIVING; not one by re-reading.** **Awareness of the class confers no immunity; only re-derivation does** -- the catalogue includes two instances committed by the authors of the rule against them, hours after writing it. Proposed for codification into `.claude/rules/tool-output-integrity.md` as **[[IDEA-214]]**, which is where it belongs and where PM cannot put it.

### TN-9: Every discriminating AC is synthetic, and that is acceptable here

The real corpus contains no instance of the shape the reorder targets, so the fail-first rows can only be built from constructed sentinel names. This is legitimate for a masked defect -- the point is that the code path is reachable, not that it currently fires -- but it must be explicit, or a green pack reads as evidence of real-world impact. It is not.

**And say which corpus.** "The real corpus contains no instance" is true of *this* corpus: **one program's network, one region, a two-day window (2026-03-11 to 2026-03-12), four contributing sessions**, with `/teams/{id}/opponents` alone supplying 313 of the 563 names. That skew bounds every conclusion drawn from the corpus, this note's included. Stating it does not weaken the finding -- TN-9's whole job is to stop a reader over-reading the pack's greenness, and an unbounded "the real corpus" is exactly the over-reading it exists to prevent. Source: `.claude/agent-memory/api-scout/proxy-corpus-team-name-sample.md`.

### TN-10: Named closure obligations -- TWO specific, pre-identified edits

**These are specific, pre-identified edits. They must not be lost inside a generic "CA will assess at closure."**

**Why each obligation names its own trigger:** the Context-Layer Assessment **gate** runs unconditionally, but the **dispatch** is conditional on someone judging a trigger to fire. With no trigger named and no artifact that goes red, both obligations would evaporate on a green suite and a clean closure. Success Criteria carries a checkable line for each.

**Obligation A -- the divergence-consequence sentence.**

- **Target file**: `.claude/rules/pitch-rules.md`, the NRBL section.
- **The gap**: that section explains why `NRBL` is a distinct constant from `LEGION` -- so that a change to one does not silently move the other. It protects against the constants being coupled **by accident**. It says nothing about what breaks downstream when they are decoupled **on purpose**.
- **What the sentence must establish**: that `ngb=american_legion` resolves before the NRBL branch is reachable, so if the two curves ever deliberately diverge, NRBL-eligible teams would be served the Legion curve regardless of which constant was edited. That is the IDEA-178 shadow, and it is benign today only because the curves are identical.
- **Trigger it fires**: **3 (footgun, failure mode, or boundary discovered)** -- an unreachable branch that a future editor of either constant would trip over. Secondarily 5 (domain knowledge that should influence future decisions).

**Obligation B -- the stale PII coverage claim (found 2026-07-27 during spec-audit triage).**

- **Target file**: `.claude/rules/pii-safety.md`, §"Coverage footgun -- planning/idea/epic artifacts are UNGATED (IDEA-102)".
- **The gap**: that section states `epics/**` and `.project/**` are ungated and that the doc-PII byte-gate is *"scoped to `docs/api/` only"*. `.githooks/pre-commit` gates both trees via its `GATE_TREES` loop. The rule is stale, and it names IDEA-102 as tracking a coverage extension that appears to have landed.
- **Why it is not merely tidy**: the spec audit read the rule file, concluded these trees are ungated, and proposed writing that into this epic as a binding safety constraint. A stale safety rule produced a false finding on its first contact with a reviewer. IDEA-102's own status needs re-checking.
- **Trigger it fires**: **3 (footgun/boundary)** and **1 (an operational constraint future work should follow)**.
- **Owner**: claude-architect (`.claude/rules/**` per the ownership table). PM does not edit it.

**Why both are deferred rather than put in a story**: they are context-layer paths, which route to claude-architect, and the dispatch team is software-engineer only. Spinning up a fourth agent during dispatch to place two sentences is not warranted. **Both are executable without this conversation** -- everything needed is above.

### TN-11: Seed claims falsified during planning -- do not restore them

The handoff seed is a relay. These five were checked against the repo and the repo won:

1. **"Add a tripwire asserting LEGION and NRBL byte-equal."** Such tests ALREADY EXIST -- `tests/test_league_detection.py::TestNrblRules::test_nrbl_is_distinct_constant_from_legion` and `TestGetRulesForLeague::test_pitch_smart_is_distinct_constant_from_legion`. They are **relative-only** (they assert the constants equal each other), which is why story 02 still has real work: a drift affecting all three equally passes them. The remedy is literal pins, not a duplicate pairwise test.
2. **"Three Legion patterns."** There are four.
3. **The docstring cite `:368`.** The sentence is in `_league_from_level_word`'s docstring; `:368` is code.
4. **The `_nsaa_level_from_name` cite `:523`.** Wrong when written. Find it by symbol -- an earlier draft of this item answered a bad line number with another line number (`:518`), which rots the same way. **The `:368` and `:523` in items 3 and 4 are EVIDENCE and must not be re-anchored**: they record what the seed cited and are the proof of its falsification, so they are supposed to point at the wrong place.
5. **"`pitch-rules.md:134` names the risk."** It names the *divergence* risk, not the IDEA-178 *shadow* risk. See TN-10.

Also corrected: the seed proposes shadow ACs "in both seasons" as fail-first. **The summer half cannot fail first** -- with `season="summer"` a shadow name already resolves `legion` today via the varsity branch. Summer rows are GUARDs.

### TN-12: The E-274 boundary, and a flag the operator should see

The 8U-14U travel-bracket suppression defect (coach's URGENT CORRECTION) is **out of this epic**, ruled to E-274's lane. Recorded, not acted on.

**Flagged for the operator, not for this epic to solve**: coach characterizes that defect as live, shipped, and actively serving wrong numbers to a growing youth audience -- a materially different risk class from this epic's masked-and-unobserved ordering edge case. E-274's own scope is the `age_group` SCHOOL family, while this defect sits in the travel-bracket branch, and E-274 is itself under a build/shrink/shelve decision. If E-274 shelves, this defect has no home. That is a roadmap call, not an E-275 action.

### TN-13: The docstring correction, and a grep trap around it

`_league_from_level_word`'s docstring asserts that Legion-specific words are season-independent. That is true **per matched pattern** and false **per name**: a name carrying both a Legion token and a preceding tier word never reaches the Legion branch. The narrowed reorder makes it true for `varsity` collisions and leaves it false for sub-varsity collisions, so the docstring still needs correcting after the fix.

> **GREP TRAP -- read this before reporting the sentence missing.** The claim wraps across a line break in the source, so a grep for its literal phrase returns **zero matches**. The sentence IS present. Cite it by symbol (`_league_from_level_word`'s docstring), never by line number and never by contiguous phrase. A reviewer verifying by grep will otherwise report a false "sentence absent" defect.

### TN-14: Word order in the name is irrelevant

The matcher loops over pattern index, not name position. "Legion Varsity" and "Varsity Legion" behave identically. **No acceptance criterion may be phrased around a Legion token appearing first in the name** -- such an AC would pass for the wrong reason.

### TN-15: The masking condition is "not summer", not "absent"

`_is_summer_season` returns true only for a token normalizing to exactly `summer`. Every other value -- `spring`, `fall`, empty string, an unrecognized token, or `None` -- takes the shadowed path. **`spring` is the live shape** and needs its own coverage; season-absent is not a special case, it is one member of a class.

### TN-16: Fixture pack structure -- two tiers

**Tier 1 (executes).** Shapes whose human-correct label matches implemented behavior. Append-only regression lock. Every row is labeled CHANGE (fails pre-fix, passes post-fix) or GUARD (passes both; must not move), and every row additionally declares whether its expected value is a CRITERION or EVIDENCE (E-275-02 AC-9).

**The six Tier 1 shape families implemented today.** This is the list E-275-02 AC-5 cites, and it lives here rather than in the AC because this note is where a future contributor appending a row will look. **Note that Tier 2 below also has six members -- the two lists are different, and a reader chasing a citation can land on the wrong one without noticing.**

1. Mapped travel brackets, across their bins.
2. The free-text age-range form.
3. The recognized `ngb` values, including one genuinely unmapped `ngb` string that exercises the generic-unknown copy.
4. The name-word conflict shapes from E-275-01, across all four non-summer season values plus summer.
5. The bracket-versus-name-word conflict shapes.
6. The no-signal fallthrough.

**Tier 2 (recorded, NOT asserted).** Shapes coach has ruled but the code does not implement, carried as a data block with a citation to the ruling that set the label -- so whoever implements one later finds the expected answer waiting instead of re-deriving it. Members: `18O`/`NNO`; rec-family `Under 13` and `Over 18`; `little_league` ngb; the school ladder (E-274's territory); and the bare-`seniors`-on-a-school-team misfire, whose current output is a known defect and must NOT be pinned as correct in Tier 1.

**Rejected alternative, recorded so it stays reviewable**: making Tier 2 self-announcing by asserting each pending shape still returns its current *wrong* value, so the test fails exactly when someone implements the ruling. It works, but it pins known-wrong behavior in an executable to detect a future fix. Rejected as over-built -- the rulings are already durably recorded in `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md` with full reasoning, and that is what actually protects them.

### TN-17: Sentinel naming -- binding constraint

Every name in the fixture pack and in every acceptance criterion MUST be a constructed sentinel built from invented tokens. **Never a real team name, real place name, or real `public_id`.** This binds `epics/**`, `.project/**` **and the fixture pack in `tests/`** -- see the scope note below, which is where an implementer is most likely to go wrong.

**What actually gates these trees -- stated both ways round, because an earlier draft of this note stated only the reassuring half.** `.githooks/pre-commit` runs two mechanisms in sequence. The pattern scanner (`src/safety/pii_scanner.py`) carries `epics/` and `.project/` in `SKIP_PATHS` and cannot regex-detect NAMES at all. The doc-PII byte-gate then greps those same two trees: the hook builds `GATE_TREES` from any staged path under `epics` or `.project`, snapshots the index, and blocks the commit on a non-zero exit.

> So: a real identifier **already on** the denylist (`secrets/pii-denylist.txt`) does block the planning commit. A **novel** real name, not on the denylist, is caught by **nobody** -- and the gate passes non-blocking in example mode (exit `3`) where the real denylist is absent. **Author discipline is the only control for anything the denylist does not already name.** Both halves must travel together; either alone misleads.

> ⚠️ **Do not re-derive this from the rule file.** `.claude/rules/pii-safety.md` §"Coverage footgun" says these trees are UNGATED and that the byte-gate is scoped to `docs/api/` only. **That section is stale against `.githooks/pre-commit`** -- it also names IDEA-102 as tracking the coverage extension, which appears to have landed without the rule being updated. The spec audit reached the rule file's conclusion and it was wrong. Read the hook. (Filed as an idea; flagged for the closure context-layer assessment.)

**Why invented tokens rather than the standard taxonomy.** Because they have **no collision surface at all** -- **not** because the prescribed `Anytown`/`Springfield`/`Example` taxonomy is known-blocked. The seed's report that the byte-gate blocked a sentinel of that class is **unconfirmed and nobody has reproduced it**; see [[IDEA-203]] (the diagnostic, routed to claude-architect) and [[IDEA-204]] (the adjacent agent-memory gap).

**Scope note -- this binds `tests/` too, and the surrounding style there is NOT the standard.** The fixture pack lives in `tests/test_league_detection.py`, which is outside both gated trees and already carries real place names and at least one real-sponsor-shaped team name in its existing fixtures. An implementer told to follow surrounding style will do exactly the wrong thing. Those fixtures are pre-existing; they are not the standard and must not be extended.

**CERTIFICATION OF RECORD (2026-07-27).** `epics` PASS REAL exit 0; `.project` PASS REAL exit 0; 36 patterns.

> **Obtained by running the gate manually from the MAIN checkout against the worktree paths -- NOT by the pre-commit hook.** The worktree has no `secrets/` directory, so a gate run from inside it lands in **EXAMPLE mode (exit 3)**, which is non-blocking: a planning commit made from the worktree would print the INCONCLUSIVE line, then the ordinary "passed" line, and **certify nothing**. Verified the same day by running it both ways and getting opposite epistemic status from the same command. See IDEA-211.

Sentinels used in this epic: `Wexlom`, `Quorrin`, `Trandive`, `Vaskeld`, `Zibbet`, `Morvath`. Extend with equally invented tokens; do not substitute anything that reads like a real place.

## Open Questions

**Every OQ states BOTH branches.** OQ-1 was the only one that did, and the others were resolvable-in-principle with no stated consequence for the disconfirming answer -- which is how an OQ gets closed by whichever answer arrived rather than by the answer being adequate.

- ~~**OQ-1**: SE's report on the consecutive-days exclusion axis and any other exclusion axis.~~ **RESOLVED 2026-07-27.** SE enumerated all seven `_is_excluded` branches by execution; exactly one reads the `rules` argument, so the universal stands **unhedged**. TN-7 carries the verbatim. *(Disconfirming branch, recorded because TN-7 required it be stated rather than achieved by deletion: had any axis diverged, TN-7's property would have been rest-tier-scoped and TN-3's retirement of the safety-direction argument would have been wrong, taking story 01's AC-12 and coach's ruling basis with it.)*
- **OQ-2 (blocks READY -- status CONTESTED, confirm with SE)**: SE's verbatim tripwire shape -- literal pins per constant plus pairwise -- for E-275-02. **SE has measured the two gaps (Gap A tandem-edit, Gap B declared-cap) and named M7 as the fail-first discriminator; what is unconfirmed is whether the verbatim pin SHAPE has landed.** E-275-02's Technical Approach still reads *"is being supplied"* and still forbids beginning AC-1/AC-2 before it lands. A handover note says all four OQs are resolved; the story file disagrees, and **the file wins until SE says otherwise**. *(Disconfirming branch: if SE's shape differs from "literal pins plus retained pairwise" -- e.g. a single parametrized table, or a snapshot -- AC-1 and AC-2 are re-specified before dispatch, not adapted during it.)*
- **OQ-3 (blocks READY)**: coach's confirmation of the CHANGE/GUARD matrix in E-275-01. The matrix was derived by PM from RULING 4 AMENDMENT because the relay pointed at a matrix in coach's rulings file that **does not exist there** (file verified section-by-section). It needs coach's certification of the coaching labels and SE's re-confirmation of each row's fail-first direction, since the `seniors`/`juniors` rows changed role from CHANGE to GUARD under the narrowing.
  - **Sequencing, and it is binding.** F5, F6 and S1 of the spec audit all change AC content. **Coach's certification is held until those land** -- otherwise coach certifies a matrix that is about to move, which is the exact re-work loop OQ-3 exists to prevent. Coach's earlier certification is therefore PROVISIONAL and is not the certification this OQ asks for.
  - **Disconfirming branch**: a row that fails certification is re-labeled or dropped. **If a CHANGE row becomes a GUARD, the epic returns to DRAFT for AC rework** rather than shipping a fail-first list that cannot fail first -- which is precisely what F5 found had already happened once.

  - **⚠️ RESCOPED BY THE TRIM, 2026-07-27. Do NOT run this certification against the pre-trim matrix.** Story 01's summer, `reserves?` and bracket rows moved into the fixture pack, so coach now certifies **story 01's four surviving rows (AC-1, AC-2, AC-4, AC-5) plus the pack's Tier 1 row labels.** The sequencing clause above still binds and the trim is the largest AC-touching change yet, so certification is held until the trim lands -- which it now has.
  - **The full handover briefing for the fresh coach instance is RELOCATED** to `.project/research/E-275-planning-record.md` §4. It is a briefing written to be consumed once by one agent, and coach's own rulings file is authoritative over it in any case.
  - **✅ ONE OBLIGATION IN THAT BRIEFING IS DISCHARGED, not carried forward.** It recorded that the 14U bracket row's evidence-versus-criterion clause was **under-scoped** -- written when the table had two rows, saying "the 14U row" where there were two and omitting the 16U row. **The trim replaced the prose clause with E-275-02 AC-9's per-row CRITERION/EVIDENCE marking**, which covers every row individually and **cannot go stale as rows are appended.** That is a stronger fix than widening the sentence, and it retires the staleness class rather than resetting it.
- ~~**OQ-4**: api-scout's corpus provenance line in a citable form.~~ **RESOLVED 2026-07-27, and it was not a formatting check -- it corrected two figures and a mislabel.** Session count 12 → **4**; harvest basis 2,518 stored bodies → **1,754 parseable**; capture window narrowed to **two days**. TN-4's 14 was attributed to the wrong falsifier (it is the bare-token pool, not the co-occurrence one). Background and TN-4 are updated; the split sufficiency verdict replaces any unqualified "the sample was sufficient".

## History
- 2026-07-26: Created (DRAFT). Planned from the spec-seeded handoff with baseball-coach (D1 + the narrowing amendment), software-engineer (classifier execution) and api-scout (real-corpus evidence) consulted during formation.
- 2026-07-27: **Spec audit iteration 1 triaged and incorporated** -- **14 MUST FIX, 13 SHOULD FIX**. Full findings and the triage detail: `.project/research/E-275-spec-audit-iteration-1.md` and `.project/research/E-275-planning-record.md` §5.

  > **⚠️ TWO CORRECTIONS TO THIS ENTRY, MADE DURING THE TRIM PASS, AND BOTH HAD CONSEQUENCES.**
  >
  > **(1) The count read "11 MUST FIX, 13 SHOULD FIX".** The audit body enumerates **F1-F14** and **S1-S13**. Re-derived from the body, which that file states is authoritative over any count line **including its own** -- it records its count line having been wrong twice already.
  >
  > **(2) F14 was MISSING from the accepted-and-landed list although all three of its fixes had landed.** That omission is the likely cause of a real downstream defect: the later trim audit recommended **deleting F14's target as though the finding were outstanding**, and the paragraph it proposed cutting *contains F14's fix* -- the two-22s replacement and the qualification of the `9`. Cutting it would have destroyed a preserved record and left the trap live. **An incomplete accepted-list is not cosmetic: it invites a second party to re-fix resolved work, and here the re-fix would have been destructive.**

- 2026-07-27: **Trim pass.** Scope reduced against "simple first, complexity as needed" after the epic reached 385 lines of specification over a two-entry list move. **The observability flags were cut** (→ IDEA-213), **three guard ACs relocated** from E-275-01 into the pack, and ~150 lines of planning record moved to `.project/research/E-275-planning-record.md`. **No specified code was removed except the flags, and no rule was removed.** Governing constraint, code-reviewer's: *relocate, do not delete; leave a pointer at every excision.* Trim audit: `.project/research/E-275-trim-audit.md`. Status stays **DRAFT**.
