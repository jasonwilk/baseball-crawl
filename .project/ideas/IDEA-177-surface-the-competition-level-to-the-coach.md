# IDEA-177: The report never tells a coach what level it computed — and the Freshman/Reserve collapse is why it should

## Status
`CANDIDATE`

## Summary
**No competition-level value reaches the coach anywhere in the scouting report today.** The engine resolves a league id, uses it to pick a `PitchCountRules` object, and throws it away. Establishing that was the surprise; it was assumed by two separate agents that a level label already rendered somewhere.

Verified by read-only trace (2026-07-25):
- `StarterPrediction` (`src/reports/starter_prediction.py:72-88`) has **no league or level field** — `league` is an argument, never an output.
- `src/reports/generator.py:2432-2447` computes it, passes it, drops it.
- `src/reports/renderer.py:812-813` puts only `starter_prediction` and `enriched_prediction` on the context.
- `src/reports/llm_analysis.py:63` **bans** the vocabulary in the system prompt ("Never use these words… 'Pitch Smart,' 'Legion'…").
- The only coach-visible "level" text is static template prose with nothing interpolated (`src/api/templates/scouting_report.html:660`, `:664`) — a deictic phrase, not a rendered value.

So an internal id can never reach the coach by accident: `_LEAGUE_WARNINGS` prose goes to `data_note`, which the template comment at `:658-659` explicitly bars from rendering, consistent with `.claude/rules/display-philosophy.md`.

## Why It Matters
Two distinct arguments, and they should be evaluated separately rather than bundled:

**1. The honest-label case (the original motivation).** GameChanger's HS enum has no "Reserve" tier, so a Reserve opponent is tagged `high_freshman`. The rest math is genuinely indifferent — both map to `nsaa_subvarsity` — but the *scouting* value is not. Freshman means incoming 9th graders in their first year; Reserve is sophomore-age and plays materially more physical baseball with a more advanced pitch mix. Both baseball-coach instances independently warned against generalizing the rest-rule safety argument into "these are interchangeable." An LSB coach who knows an opponent is reserve-age and reads "Freshman" notices, and it costs credibility in the artifact.

api-scout later measured this: **17 of 73 opponents are Reserve-named, 15 tagged `high_freshman`.** So the ambiguous case is common, not hypothetical — roughly a fifth of the schedule.

**2. The trust-surface case (broader, and arguably stronger).** The report applies a specific league's pitch-count table to produce availability calls a coach acts on, and never says which table. A coach cannot sanity-check a rest number without knowing whether it came from NSAA Varsity, NSAA Sub-Varsity, Legion, NRBL, or a Pitch Smart estimate. That is a bigger gap than the Freshman/Reserve label and it subsumes it.

## Rough Timing
Not urgent; nothing is wrong today, only absent. Promote when either:
- someone is next working on the Most Likely Arms card's coach-facing copy, or
- a coach asks which rules a rest number came from (the trigger that would confirm case 2).

**Do not promote as a "small copy fix."** That framing is what got it removed from E-274 — see below.

## Dependencies & Blockers
- [ ] None hard. Cheaper if the level distinction is preserved through detection first (see Notes).

## Open Questions
- **Which case is being solved — the label or the trust surface?** They imply different designs. The honest Freshman/Reserve label is one conditional string; a "these calls come from the [X] rules" trust line is a new report element with its own copy, placement, and estimate-vs-binding states. Decide before scoping.
- **Where does it go?** There is no team-level header or masthead today, so this is net-new real estate on an artifact that is deliberately dense. baseball-coach and ux-designer both have standing here; ux-designer's charter covers report layout and trust surfaces specifically.
- **What is the copy when the level is an estimate or suppressed?** `is_estimate` and `suppress_reason` already exist as discriminators; per `display-philosophy.md` the raw `data_note` must never be echoed, so this needs its own discriminator-to-copy mapping.
- **Does E-263-02c's operator-picked level change the answer?** If an operator explicitly picks a level, echoing it back is a confirmation rather than a disclosure — possibly a different and easier design.

## Notes
**Removed from E-274 as story E-274-03 (2026-07-25) after its premise was falsified.** It was scoped as "make an existing label honest," which required the label to exist; the trace above showed it does not. Three things changed with that:
1. It became **additive UX on a bench artifact** — a decision with an operator in it, not a mechanical consequence of reading a field.
2. It picked up a `.claude/rules/browser-render-testing.md` obligation (headless-Chromium render+print; a string assertion does not clear that bar).
3. It was only ever SHOULD HAVE — baseball-coach revised its own MUST down once it checked where the label surfaces.

**Implementation shape, from the trace** (three parts, no LLM involvement, all deterministically assertable): preserve the tier distinction through detection — it is lost **twice** today, at `_LEVEL_WORD_PATTERNS` (`:309-312`, `freshman|frosh` and `reserves?` both → `_LEVEL_SUBVARSITY`) and at the DB branch (`:436`, `("jv","freshman","reserve")` → one id); add a coach-facing label field to `StarterPrediction` (**none exists — this is the additive part**); thread it through `renderer.py`'s context; render it.

E-274-01 maps `high_freshman` and `high_junior_varsity` to the same sub-varsity *class*, so it does not preserve the source value either. If preserving it is free when that story is implemented, this idea becomes near-trivial — worth mentioning to that implementer, but **not** as scope.

Precedent for the label wording: E-272's TN-9 handling of the Senior/Junior Legion collapse — engine collapses to one id, display defers or caveats rather than overclaiming.

Related: [[IDEA-171]] (promoted to E-274, the epic this came out of), [[IDEA-079]] (richer predicted-starter narrative — adjacent coach-facing surface).

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
