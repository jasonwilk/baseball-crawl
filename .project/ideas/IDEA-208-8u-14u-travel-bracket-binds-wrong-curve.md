# IDEA-208: The entire 8U-14U travel bracket binds to a 15-18 pitch curve and must suppress instead

## Status
`CANDIDATE` — **live, shipped defect. baseball-coach has RULED (2026-07-25); this is implementation work, not a question awaiting an answer.**

## Summary

`_league_from_age_bracket` (`src/reports/starter_prediction.py`) maps every `\d+U` bracket below 15 — the whole `8U`-`14U` range — to `youth_travel`, and `get_rules_for_league` routes `youth_travel` to `PITCH_SMART_15_18`: a 105-pitch curve whose own constant name says which age band it is calibrated for. The report renders it with `is_estimate=True`, producing an amber badge and a "treat as a directional read" banner.

**baseball-coach's ruling: reclassify the entire below-15U travel bracket from BINDING GUIDELINE ESTIMATE to SUPPRESS, terminal** — identical treatment to `Under 13`, `middle_12U`, `middle_13O`, `elementary` and `college`.

Ruling of record, with full reasoning and its falsifier: the **URGENT CORRECTION** section of `.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`.

## Why It Matters

The argument coach makes is an equal-treatment one, and it is the sharp form: **the same real child gets a different answer depending only on which picker their coach happened to use when creating the team.** `middle_13O` — the school family's name for the same 13-14 age population — already suppresses. A coach who picked `14U` on the travel picker gets a confident 105-pitch number instead. That is not a defensible distinction; it is an artifact of which family was built first.

Coach ruled the labeled estimate **insufficient mitigation**, and the reasoning does not transfer from the usual "never suppress, always contextualize" principle: that principle governs stat rows and sample-size uncertainty, whereas the starter card's suppress state is explicitly carved out as "an honest absence of a projection, not the hiding of present data." There is no uncertainty about this team's age — the bracket is a clean numeric match. It is not "we do not know this team's level, here is a generic guess"; it is "we know exactly what level this is and are knowingly applying a curve we have already ruled does not fit it."

**Audience makes it worse rather than better.** This project now serves real USSSA 8U-14U youth coaches as a core audience, named explicitly in `docs/VISION.md`. A miscalibrated cap silently under-resting a nine-year-old's arm, presented with a routine-looking amber badge, is the shape of harm the under-rest standard exists to prevent.

## Rough Timing

**Promote soon, and note it currently has no epic home** — this is the reason the idea exists rather than a story. It was ruled into E-274's lane on 2026-07-26 (it is a bracket-classification defect, not a name-precedence one, so it was correctly kept out of E-275). But E-274's own scope is the `age_group` **school** family, while this defect lives in the **travel-bracket** branch, and E-274 is under a build/shrink/shelve decision at 4% measured value.

**If E-274 shelves, this goes with it unless it is carried separately.** That is what this capture is for.

Coach's own priority read: live, shipped, and actively serving wrong numbers to a real and growing audience — a materially different risk class from the masked, not-yet-observed ordering defects it has been travelling alongside. Coach explicitly calls the prioritisation a PM/operator call rather than a domain one.

## Dependencies & Blockers

- [ ] **None on the ruling** — it is made, with reasoning and a falsifier recorded.
- [ ] An epic home. Not blocked on E-274; would be better carried with [[IDEA-184]] (see below).

> **⚠️ THE E-274 CONCENTRATION, added 2026-07-27 — this idea is no longer alone in depending on that epic's fate.** [[IDEA-205]] (bare `seniors` misfiring as a Legion signal) was routed out of E-275 on 2026-07-27, and SE established by execution that **its fix belongs to E-274's school-family branch** and is unreachable from any pattern reordering. So **two coach-ruled classifier defects now hang on E-274**, and they hang differently:
>
> - **IDEA-205 fits E-274's scope well** — the fix is reading the school-family `age_group`, which is exactly what that epic is for. Its home is real but **contingent**.
> - **This idea does NOT fit it** — E-274's scope is the `age_group` SCHOOL family while this sits in the travel-bracket branch. It was ruled into that lane on 2026-07-26 and is **already orphaned there**.
>
> **E-274 is under a build / shrink / shelve decision at 4% measured value.** If it shelves, IDEA-205 loses a home it currently appears to have, and this idea's position is unchanged because it never really had one. **Neither should be read as securely homed.** Recorded as an input to the E-274 decision, not as a claim on it.

## Open Questions

- **What does the suppressed case SAY to the coach?** Coach ruled that "recognized value, deliberately no table" must remain distinguishable from "genuinely unrecognized value," and that the mechanism already exists — `_LEAGUE_WARNINGS["usssa"]` is a third tier today, distinct from both a bound table and the bare unknown. Extend that three-way split rather than inventing a two-way one. Note this lands on the same template branch that carries a separate known copy defect (see [[IDEA-184]]), so fixing one without the other moves 8U-14U from a false sentence to a different false sentence.
- **A correct youth table is separate, later work and NOT a prerequisite.** Coach declined to assert Pitch Smart 7-8/9-10/11-12/13-14 breakpoints without a citation pass. Suppression is right independent of whether that table is ever built: we should not keep showing a wrong number while a right one is unbuilt.
- **The rec free-text range form is UNCHANGED by this** and stays on the youth-estimate path — a `Between 13-18` population spans *into* the band the curve is calibrated for, so borrowing it is an imperfect-but-real approximation. An `8U`-`14U` bracket is a confidently 100%-below-15 population with no mixture to hide behind.
- Coach's falsifier, recorded rather than paraphrased: the ruling is wrong if the true sub-15 Pitch Smart curve turns out to require LESS rest per pitch than the 15-18 curve, in which case the harm direction reverses to over-rest. Coach holds moderate-not-citation-grade confidence that younger bands need more rest. It is also wrong if the operator judges a much more strongly worded banner an acceptable middle path — coach flags that as a legitimate product call it did not make.

## Notes

**Near-collision with [[IDEA-184]] — read this before concluding they are the same thing.** They share a root cause and an overlapping population, and **neither fix closes the other**:

- **This idea** is an ENGINE defect: the wrong pitch-rule table is selected. Remedy: suppress.
- **IDEA-184** is a COPY defect: the banner asserts "this level doesn't publish pitch-count rules," which is false for a population that has them. Remedy: rewrite the copy.

Suppressing 8U-14U does not fix the banner — it survives for the other `youth_travel` route, the free-text range form, where IDEA-184 argues the sentence is still false. And rewriting the banner does not fix the engine, which still applies the wrong curve to whoever reaches `is_estimate`. **They should be worked together, and were intended to be**: IDEA-184's operator approval was to co-locate it with the suppression fix, which is why both were re-homed here when that fix moved lanes.

Filed 2026-07-27 on operator ruling, after a case determination established these were two defects rather than one. Split out of E-275 deliberately: E-275 is a pure-logic epic and folding a template surface into it would have imported a ux-designer dependency and a sequencing hazard — the banner's 8U-14U audience is only removed *by this fix*.

Related: [[IDEA-184]] (its paired copy defect — evaluate together, always), [[IDEA-179]] (the rec/travel forms that fall through unparsed — same wrong-band hazard, different mechanism), [[IDEA-177]] (surface the competition level to the coach — the additive trust-surface argument on the same card).

---
Created: 2026-07-27
Last reviewed: 2026-07-27
Review by: 2026-10-25
