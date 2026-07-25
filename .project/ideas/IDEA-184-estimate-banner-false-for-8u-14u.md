# IDEA-184: The "this level doesn't publish pitch-count rules" banner is factually FALSE for 8U-14U

## Status
`CANDIDATE` — **SCOPE FOR E-275 STORY 01** (the 8U-14U suppression fix), not free-standing work. Operator has approved folding it in. Filed here because E-275 does not exist yet and this must survive until it is planned. **Do not promote independently.**

## Summary

`src/api/templates/reports/scouting_report.html` line 664, verified verbatim:

> `This level doesn't publish pitch-count rules, so rest and availability use a standard youth pitch-count guide. Treat as a directional read, not a hard rule.`

It renders whenever `starter_prediction.is_estimate` is true (template line 663) — which is the `youth_travel` league, and per `_league_from_age_bracket`'s own docstring (`src/reports/starter_prediction.py:334-342`) an unmapped bracket is *"14U and below"*. So this sentence is shown for the **entire 8U-14U range**.

**The sentence is false for that population**, and the repo's own rule file is the witness. `.claude/rules/pitch-rules.md:180` states that `youth_travel` is routed to *"the USA Baseball Pitch Smart 15-18 curve (the `PITCH_SMART_15_18` constant: max 105, tiers 30/45/60/80/105)"*. That is self-refuting on its face: **the guide the banner invokes as a substitute for missing rules is itself age-banded, and the constant is named for the band we are applying.** Pitch Smart publishes guidance for the younger bands too. We are not lacking a rule — we are applying the wrong band of the very guide we cite.

**Direction, not figures.** Younger Pitch Smart bands are stricter than 15-18 (lower daily max, lower per-tier breakpoints). The specific breakpoint numbers circulating in E-274's TN-3 are baseball-coach's recall from an environment with **no web access**, and E-274 OQ-3(b) explicitly bars printing them as cited fact. State the direction; do not print a table until someone has a citation.

**One attribution correction to the finding as relayed.** It was cited to me as *"`.claude/rules/pitch-rules.md` line 163 documents youth daily maxima of 50 (7U-8U) to 95 (13U-14U)."* The numbers are real and line 163 does say that — but that line sits under **`## Perfect Game (7U-14U)` → `### Rules (Outs + Pitches)`**, so it is Perfect Game's published schedule, not a generic youth guide and not Pitch Smart. It still supports the core claim (those age groups demonstrably have published pitch-count rules), but it should be cited as Perfect Game's. The stronger argument does not need it at all: the self-refutation above rests entirely on `PITCH_SMART_15_18` being a named band.

## Why It Matters

**It is not merely insufficient — it is inaccurate in the reassuring direction, on the youngest arms.** baseball-coach ruled the caveat *insufficient* ("a softened badge doesn't change that the number is wrong-band, not merely imprecise"). This is a step worse. A coach reading "this level doesn't publish pitch-count rules" reasonably concludes that **none exist** and that our estimate is the best guidance available. The truth is the opposite: a stricter published rule exists for that age, and we are showing a looser one — 105 max where the age-appropriate band is materially lower.

That combination is the problem. A wrong number with an honest caveat invites scrutiny. A wrong number with a caveat that **explains away the possibility of a better answer** actively suppresses it.

This is the coach-facing surface of the same defect E-275 story 01 fixes in the engine; the engine picks the wrong band, and this sentence tells the coach no right band exists.

## Rough Timing

**Fold into E-275 story 01 when that epic is planned.** No independent schedule. The suppression fix removes this banner's 8U-14U audience, so the two belong in one change — but see the trap below before assuming that closes it.

## Dependencies & Blockers
- [ ] E-275 does not exist yet. This capture is the holding pattern; re-read it at E-275 planning.

## Open Questions

- **What is the copy for the SURVIVING `is_estimate` case?** This is the trap, and it is the reason this is a capture rather than a footnote on the suppression story. Once 8U-14U suppresses, the banner still renders for the other `youth_travel` route: the **free-text age-range form** (`.claude/rules/pitch-rules.md:180`; the IDEA-126 estimate path), e.g. `"Between 13 - 18"`. **The sentence is arguably wrong there too** — a 13-18 range straddles bands that do publish rules, so "this level doesn't publish pitch-count rules" is still false, just less starkly. **Whoever does story 01 must decide this copy deliberately rather than assume the problem left with the suppressed population.**
- **Does the suppressed 8U-14U case need its own copy?** It will fall to the `suppress_reason` branch at template line 660, which is where the *other* known copy defect lives (see cross-references). Fixing one and not the other would move 8U-14U from a false sentence to a different false sentence.
- **Is "directional read, not a hard rule" salvageable?** The second half of the banner is honest about confidence even where the first half is false about availability. A minimal fix might keep the hedge and replace only the false premise — cheaper than new copy, and it preserves what the sentence gets right.

## Notes

**Two distinct copy defects in the same suppress/estimate region, found independently by two agents.** Cross-linked rather than restated:
- **This one, template line 664** — the `is_estimate` banner asserts no published rules exist for a population that has them.
- **Template line 660** — the `unsupported_level` suppress branch says *"this team's level doesn't have pitch-count rules we can apply"*, which asserts we know the level; genuinely-unknown teams get the same sentence. Found by ux-designer, designed in `/workspaces/baseball-crawl/.project/research/2026-07-25-uxd-competition-level-disclosure-design.md`.

That both were found in the same small region by different agents looking for different things is worth noting on its own: this block's copy has never been audited as a set, only patched per-branch.

Ruling of record: baseball-coach's URGENT CORRECTION section in `/workspaces/baseball-crawl/.claude/agent-memory/baseball-coach/e275-classifier-hardening-rulings.md`.

Related: [[IDEA-177]] (surface the competition level to the coach — the *additive* trust-surface argument; this idea is the complementary *subtractive* one, removing a false claim, and the two should be evaluated together at E-275 planning since they touch the same card), [[IDEA-179]] (rec-family `Under 13` / `Over 18` forms reaching adult tables — the same wrong-band hazard on a different family), [[IDEA-126]] (the free-text range form that becomes this banner's surviving audience).

Found 2026-07-25; verified against the template, `_league_from_age_bracket`'s docstring, and `.claude/rules/pitch-rules.md` rather than relayed.

---
Created: 2026-07-25
Last reviewed: 2026-07-25
Review by: 2026-10-23
