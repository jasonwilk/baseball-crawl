# E-275 — Planning Record

**Written 2026-07-27 by product-manager, during the E-275 trim pass.**

This file receives material **relocated out of `epics/E-275-classifier-hardening/epic.md`** so the epic specifies work and this file records how the planning session established things. **Nothing here was deleted from the epic — it was moved, and every excision left a pointer.** The governing rule for that trim, set by code-reviewer: *relocate, do not delete; leave a pointer at every excision.*

**What is here is EVIDENCE — a record of what was observed and how.** Do not "tidy" the figures in it. Several are superseded values preserved deliberately, with do-not-restore notes; correcting them destroys the record they exist to be.

**Two routing notes.** The trim audit proposed sending §2 below to `.claude/rules/tool-output-integrity.md` and §4 to `.claude/agent-memory/baseball-coach/`. **PM can write to neither** — the first is claude-architect's domain, the second is another agent's memory directory. Both land here instead. The rule-file codification is proposed separately as **IDEA-214**.

---

## 1. TN-7's axis enumeration — the record of how OQ-1 was answered

**Relocated from epic TN-7.** The epic retains SE's verbatim safety property, the four-item divergence statement and the equal-bands caveat; this is the supporting enumeration. Primary source, with the harness detail: `.project/research/E-275-se-execution-answers-F4-F6-S2-S6.md` §F4.

> **The axis enumeration behind the universal.** `_is_excluded` has **seven** decision branches. Four are cannot-evaluate paths returning NOT-excluded (no appearances; missing `game_date`; unparseable date; negative rest from a future-dated appearance). **Three can exclude**: a null pitch count on the most recent game day, rest-tier compliance, and the consecutive-days rule. **Exactly one of the seven -- rest-tier compliance -- reads the `rules` argument at all**; every other branch reaches the same verdict for every league, confirmed by driving all seven against all six rule constants.

> The null-pitch-count branch is **a third exclusion axis neither this epic nor the review had enumerated.** It excludes, so it belongs in any claim about exclusion behaviour; it is league-blind, so it does not qualify the universal. It was found by reading the branches out of the function rather than by reasoning from the two axes already under discussion.

> **Why the consecutive-days rule structurally cannot be league-gated** -- this is the strongest form and depends on no sample: it reads two module-level constants and does not read the rule set it was handed, and it could not, because `PitchCountRules` declares exactly two fields, `max_pitches` and `rest_tiers`. **There is no consecutive-days field for a league to vary.** Making it league-specific would require a schema change to the dataclass.

> **Carry this caveat -- it is why the scope looked uncertain.** Those constants are named `_NSAA_*` while applying unconditionally to Legion, NRBL and the Pitch Smart estimate, and the function's own docstring says the opposite of the name (*"...for any league"*). **The docstring is the accurate one.** This is the same prose-versus-behaviour defect class the epic already fixes on `_league_from_level_word`'s docstring.

---

## 2. The instrument-failure catalogue — TN-8 items 3 through 6

**Relocated from epic TN-8.** The epic retains items 1-2, which produce the standing rule (*never cite the `_SUMMER_SEASON` comment block as evidence for a behavioural claim*). These four are a process lesson about tool output, not a classifier spec — **the most transferable thing this epic produced, and the most misfiled.** Proposed for codification into `.claude/rules/tool-output-integrity.md` as **IDEA-214**.

Numbering preserved from the epic so citations to "TN-8 item 4" still resolve.

> **Three more instrument failures from this epic's planning, recorded because they are the same class and all three were caught by their own authors.**

> 3. **A grep whose character class silently dropped the most relevant result.** SE's first constant enumeration used `^[A-Z_]+ = PitchCountRules`, which **cannot match `PITCH_SMART_15_18`** -- the class excludes digits. It returned five constants and dropped the single one the question was about. Corrected with `[A-Z0-9_]+`, the set is six. **The result looked complete and was not**, which is the failure mode a count cannot reveal about itself.

> 4. **A counterexample search scoped to a comparison the fix cannot produce.** SE's first pass returned 22 apparent counterexamples to this epic's central safety claim. Every one was `NSAA_SUBVARSITY` -- a table the reorder can never move to or from. Rescoped to the only real transition (`nsaa_varsity → legion`), the count is **0**. In SE's words: *the uncorrected pass produced a number that looked like a refutation of the epic's central safety claim, and the same raw output read without that check supports the opposite conclusion.* **A count is only as good as the population it was computed over, and that population is the part a reviewer cannot see from the number.**

> 5. **PM asserted the contents of its own file from memory.** While flagging a possible figure-crossing in TN-4, PM told two agents that the note contained a second sentence about Legion-token names. It did not. Reading the file first is what caught it. **The epic's own author is not exempt from the rule the epic is built on.**

> **The pattern across all five**: none was caught by re-reading with more care, and every one was caught by *executing* the check differently -- a corrected regex, a rescoped population, an actual read. Four of the five were caught by their own authors, which is the encouraging half; the discouraging half is that none was caught by a reviewer looking at the output.

> **A SIXTH ENTRY, AND IT IS A CLASS RATHER THAN AN INSTANCE -- the one this epic is most likely to reproduce.**

> 6. **A figure correct for the question it was computed against, transplanted to a question that redefined its terms.** Four instances during planning and triage, none of which was *wrong when written*:
>    - SE's **60**-combination blast radius -- a correct measurement of a **four-pattern** reorder, stale the moment coach narrowed the ruling to two. Correct value, superseded question. (Also SE's `ngb` sweep: 36 → 24.)
>    - api-scout's **14** Legion-token-only names -- computed with a tier set that omitted `reserve(s)`; corrected to **9**.
>    - **PM's own near-miss**: about to substitute that corrected **9** into AC-9, where TN-5's trigger set counts `seniors` as *Legion-family* and a bracket as neither. The true figure is **22**. The 9 was right, and right about a different question.
>    - api-scout's **two 22s**, which share only 17 members and are equal in size by arithmetic accident.
>
>    **The rule this yields, and it is stronger than "check your numbers": a figure needs its DEFINING SETS attached, not just its value.** A bare number travels into a context that redefines its terms and is wrong on arrival with nothing to signal it. **In this material a matching count is NOT evidence that two figures are the same quantity** -- there have now been two 14s and two 22s.
>
>    **Every one was caught by RE-DERIVING; not one by re-reading.** Two were caught by someone refusing to restate a figure they could not produce themselves. And the third instance is PM's -- the author of this note, mid-audit, applying the rule this note states. **Awareness of the class confers no immunity; only re-derivation does.**

### 2a. Four more instances, added during the trim pass itself

The catalogue above closed at six. The trim that relocated it produced four more of the same class, which is the point rather than an embarrassment.

7. **A count inside a correct conclusion, not derivable from its own table.** The trim audit's summary read *"Story 01: 13 → 9 ACs, with the cut four relocated."* Its own AC table cuts **three** (AC-3, AC-6, AC-7) and its own KEEP enumeration lists **ten**. The conclusion — absorb the guards into the pack — was right throughout, which is exactly why the figure rode through the audit, a relay, and into a proposal. **Correct value: 13 → 10, three relocated.**

8. **The same error, committed independently by PM in the opposite direction.** PM's proposal said *"13 → 6."* Recount: seven survive. Both errors understated the surviving count — the direction a trim pass is predisposed to err in.

9. **A resolved finding recommended for deletion as though live.** The trim audit named F14's false sentence — *"there is no longer a numeric coincidence to disambiguate"* — as one of two things to *delete outright*, and proposed cutting the paragraph containing it. **F14 had already fully landed**: the sentence survives only inside its own do-not-restore prohibition, and the paragraph proposed for cutting **contains the fix** (the two-22s replacement and the qualification of the 9). Cutting it would have destroyed the record and left the trap live. **Found by reading the literal lines; the recommendation was individually plausible and the epic's History entry — which omits F14 from its accepted-list — is the likely cause.**

10. **A derivation false in a branch it did not enumerate.** PM's four-row table of post-reorder trigger resolutions, sent twice and used as the basis for a recommendation, asserted `seniors`/`juniors` + `varsity` → `nsaa_varsity` unconditionally and cited TN-3. **In summer it resolves `legion`**, via `\bvarsity\b` first-match and the summer branch — wrong on the value *and* wrong on the authority (E-272's season rule governs there). It also named three of five reachable resolutions and silently assumed season-absent / no bracket / no `ngb`. **SE falsified it by driving 1,440 combinations.** The corrected five-ruling form is preserved in **IDEA-213**.

**Items 7-10 sharpen the pattern rather than repeating it: every one sat inside a conclusion that was correct.** Item 9 is the sharpest — a reviewer who had authored the criterion-versus-evidence discipline recommended the exact sweep that discipline forbids, in an audit commissioned to prevent over-trimming.

### 2b. Item 11 — a DISTINCT shape: the two-artifact contradiction, which no single-file read can catch

**This one is not a variant of anything above and deserves its own name.** Every shape in §2 and §2a is findable, in principle, by someone reading one artifact carefully: a bad regex, a mis-scoped population, an unproducible figure, an unenumerated branch. **This one is not.**

[[IDEA-205]] classified the bare-`seniors` misfire as *"a data-accuracy defect rather than a safety one"* on the strength of its observed instance, and rated it *"not urgent — the failure direction is the mild one."* **The epic already carried the fact that falsifies it.** E-275 TN-2 states the table relation directly: *"`NSAA_SUBVARSITY` requires 1 rest day in the 1-30 band where `LEGION` requires 0."* That is exactly why the misfire **under-rests** a `high_junior_varsity` or `high_freshman` team — `legion` is the looser table against sub-varsity, and only the stricter one against varsity.

**Both artifacts were internally consistent and individually correct.** TN-2 was reasoning about a Legion-plus-JV *name*; IDEA-205 was reasoning about a bare-`seniors` *name*. Different scenarios, same underlying table relation, and **nothing in either file pointed at the other.** Six review passes, a spec audit, a trim audit and three agents read both without connecting them. SE found it by driving the resolution against all three school-family `age_group` values — i.e. by **executing the crossing**, not by reading either file again.

**Why it generalises.** A defect can be fully documented across two artifacts and invisible in each, when the connecting step is a *substitution* neither file performs: "the fact TN-2 states about tables A and B" applied to "the scenario IDEA-205 describes." Single-file review cannot catch it by construction, and cross-file review only catches it if someone happens to hold both in mind **for the same quantity**. The reliable detector is the same as everywhere else in this catalogue: **execute the claim across its full input domain** — here, all three values of the axis, rather than the one that was observed.

**Sharpest form: an artifact's severity claim was refuted by a fact its own epic already stated.** If that can happen inside one epic directory, in files written days apart by agents who had read both, then "we documented it" is not the same as "we know it."

---

## 3. TN-4's correction archaeology

**Relocated from epic TN-4.** The epic retains the two-falsifier table, the split sufficiency verdict, the promoted ~13.6% rule-of-three bound, the two-22s disambiguation and **the do-not-restore record**. This is the narrative of how the figures moved.

> **The "second 14" is GONE -- it was wrong.** api-scout re-derived it with an explicitly stated tier set and the correct figure is **9**: of the **22** names carrying a hard Legion token, **9** carry no tier word, no soft token and no bracket. The original 14 omitted `reserve(s)` from its tier set, so the five Legion+`reserves?` names fell into the "no tier word" bucket. **14 = 9 + 5.** Full breakdown of the 22: 9 bare, 5 `reserve(s)`, 4 bracket-only, 3 `seniors`, 1 singular `Senior`, **0 `varsity`**.

> **How that error was made is worth more than the figure.** api-scout's own memory file, two sections below the bad breakdown, warns that a tier set omitting `reserve` makes exactly these five collisions invisible. **It identified the failure mode and then committed it one section earlier in the same document, and the error survived every re-reading.** Only re-deriving with an explicit tier set caught it. Seventh corrected figure this session; none caught by re-reading. If you are checking a count in this epic, **re-derive it -- do not re-read it.**

**⚠️ The `9` answers TN-4's question ONLY.** It is computed over hard-Legion-token names with a tier set counting `seniors` and a `\d+U` bracket AS tier words. It is **not** the figure for the Legion-family/no-tier-word set (that one is **22**, under different sets — preserved in IDEA-213). Substituting one for the other transplants a figure across a definitional boundary; it was nearly done once.

---

## 4. OQ-3's handover to a fresh coach instance

**Relocated from the epic's Open Questions.** This is a briefing written to be consumed once by one agent. **Coach's own rulings file is authoritative over this summary** — item 5 says so itself.

> 1. **The certification scope is NARROW and must stay narrow.** Coach certifies that each row's expected **league** is the coaching-correct answer for a given name/season/bracket combination, and that the **CHANGE-versus-GUARD labels** match its ruling. Coach does **NOT** verify code direction, fail-first behavior, or implementation -- that is SE's and the reviewer's lane.
>
> 2. **Method, not just result. Re-walk the matrix FRESH.** Coach did not read the labels and nod: it traced the actual `_LEVEL_WORD_PATTERNS` match order **by hand** for the discriminating rows -- which pattern matches first under the ruled ordering -- before agreeing a GUARD row was genuinely unchanged. That is the check that catches a mislabeled row; skimming the stated expected value does not. **Re-walk the full matrix rather than diffing against coach's prior certification** -- rows have shifted position and numbering.
>
> 3. **The nuance most likely to be missed** by a successor reading only the story file: **the 14U-bracket rows are coaching-correct as CURRENT BEHAVIOR ONLY.** They sit downstream of coach's separate URGENT CORRECTION ruling (8U-14U should **suppress**, not bind), which is deliberately out of this epic's scope.
>
> 4. **The TN-17 sentinel constraint binds the successor too** -- constructed names, invented tokens, never the `Anytown`/`Springfield` class.
>
> 5. **Trust the FILE over any summary, including coach's own.** `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md` is finalized and coach stands behind it as of 2026-07-27. Where it disagrees with anything coach said in a message thread, **the file wins.** (Coach's fixes there are pointer-style -- original text kept with a dated correction attached -- so a superseded string still present is a correction record, not a live claim.)

**⚠️ The certification this describes has been RESCOPED by the trim and must not be run against the old matrix.** Story 01's bracket and season rows moved into the fixture pack, so coach now certifies story 01's surviving rows **plus** the pack's Tier 1 row labels. The sequencing constraint in OQ-3 still binds: certification is held until all AC-touching changes land, and the trim is the largest of them.

---

## 5. Spec-audit iteration 1 — triage detail

**Relocated from the epic's History entry**, which now carries one sentence and this path. Full findings: `.project/research/E-275-spec-audit-iteration-1.md` (**14 MUST FIX, 13 SHOULD FIX** — re-derived from the body, which is authoritative over any count line in that file, its own included).

**Accepted and landed**: F2, F3, F5, F7, F8, F9, F11 (remainder), **F14**, S3, S4, S5, S7, S8, S9, S10, S11 (remainder), S12, S13 (citations).

> **F14 was omitted from the epic's own accepted-list until the trim pass**, though all three of its suggested fixes had landed. That omission is the likely reason the trim audit later recommended deleting F14's target as though the finding were outstanding. **An incomplete accepted-list is not cosmetic: it invites a second party to re-fix resolved work, and the re-fix here would have destroyed a preserved record.**

**Already resolved before triage, verified against the artifact**: F2, F6 (SE executed and rebuilt the bracket rows as a four-row table — a stronger fix than the audit proposed), F10's TN-4 half, F11's provenance half, S11's tense, S13's substance.

**Partially refuted**: **F1 claim 1 is WRONG** — it rested on `.claude/rules/pii-safety.md`, which is stale; `.githooks/pre-commit` DOES gate `epics/` and `.project/` via `GATE_TREES`. Applying the audit's suggested fix would have written a false sentence into a binding safety note. TN-17 was rewritten to state both halves; the rule-file staleness is **IDEA-211** and TN-10 closure obligation B. F1 claim 2 (the unconfirmed seed claim) accepted in full.

**Routed outside the epic**: F12, F13 (→ IDEA-211, claude-architect).
