# E-243-03: Surface ranked "most likely arms" + reframe wording

## Epic
[E-243: Make the Probable-Starter Analysis Useful on Game Morning](epic.md)

## Status
`DONE`

## Description
After this story, the probable-starter section of every report with sufficient data shows a ranked list of the likely arms — up to 3, as many genuine candidates as exist (a single arm when only one genuine candidate exists), each with start-share, days rest, and rest-eligibility — instead of the all-or-nothing "name one starter or show a blank/committee card." The section wording is reframed from "Predicted Starter" toward "Most Likely Arms," and the leading "true committee situation" hedge is gone. This is the core presentation fix and the heart of the user's request.

## Context
The engine already computes a ranked `top_candidates` list, but the template only surfaces it in the "low"-confidence branch; the "high"/"moderate" branches name a single arm and the "suppress" branch shows nothing. The engine names a single pick only 3.6% of games and is wrong 85% of those, so the binary gate is the wrong UX. Surfacing the ranked list always yields an honest ~40% top-2 and matches how a coach thinks ("it'll be one of these two"). This story consumes the discounted-tier rest classification from E-243-01 (for the per-arm eligibility field) and the youth/travel estimate marker from E-243-02 (to label estimated predictions). ux-designer owns the card layout and copy; software-engineer implements the engine output enrichment and the template.

- [ ] **AC-1**: Given an opponent with ≥4 games of pitching data (any non-suppressed confidence state), when the report renders, then the probable-starter section shows the ranked list of likely arms — **up to 3, i.e. as many genuine candidates as the engine produced** — never hidden behind the confidence gate and never a blank card with only a committee hedge. The reframe surfaces the real ranked candidates; it does NOT fabricate phantom arms to reach a count.
- [ ] **AC-1b**: Given an engine result with exactly one genuine candidate (`len(candidates) == 1`, e.g. a team with only one real starter — `starter_prediction.py:994`), when the report renders, then the section shows that single ranked arm plus the unavailable sub-block — NOT a fabricated second/third arm, and NOT the old single-name "high confidence" card framing.
- [ ] **AC-2**: Each likely-arm line displays the arm's start-share grounded in games (e.g. "8 of 30 starts (27%)", where `start_share_pct = round(games_started / total_team_games * 100)`, per CLAUDE.md Data Philosophy — games, not a bare percent), days rest, and a **two-valued** rest-eligibility (`available` or `discounted`) read from the candidate's attached rest-state (E-243-01). Handedness ("(RHP)"/"(LHP)") is shown when `throws` is present and omitted silently when absent. Sample-size context is shown as badges, not suppression (per `.claude/rules/display-philosophy.md`).
- [ ] **AC-3**: Hard-excluded (unavailable) arms — which are NOT in `top_candidates` — render in their own "Unavailable today (and why)" sub-block, fed by a new additive engine output field `unavailable_arms: list[{name, reason}]` that surfaces the engine's existing exclusion reasons (per Technical Notes TN-5). Per-line eligibility on the ranked list is therefore never "unavailable" — that state lives only in this sub-block.
- [ ] **AC-4**: The section heading and body copy no longer present a single "predicted starter" as the primary framing, and no rendered state opens with a "true committee situation"-style hedge. The reframed wording ("Most Likely Arms") and layout come from the ux-designer card spec at `epics/E-243-probable-starter-usefulness/E-243-03-card-spec.md`.
- [ ] **AC-5**: Given a youth/travel prediction with `is_estimate == True` (from E-243-02), the section labels it per the ratified estimate treatment (Technical Notes TN-5): the heading stays "Most Likely Arms" (unchanged across estimate and non-estimate), and the estimate signal is carried entirely by an amber "Estimated rest" badge plus a one-line plain-English banner ("This level doesn't publish pitch-count rules, so rest and availability use a standard youth pitch-count guide. Treat as a directional read, not a hard rule."). The no-jargon rule is **absolute** (no carve-out): "Pitch Smart" / "Legion" / "USA Baseball" / "soft prior" never appear in the rendered report — they live only in the engine, the coach-model doc, and LLM-internal prompt context. The badge appears ONLY on estimates (its absence signals full confidence); the word is "estimate", not "uncertain".
- [ ] **AC-6**: Given an opponent with too few games (the engine's `suppress` data-note states), when the report renders, then the section shows the honest suppress-state copy from the ux-designer spec ("Not enough games yet to project likely arms — rest data still accumulating") rather than a fabricated ranked list.
- [ ] **AC-7**: The rest/availability table and bullpen-order rows that already render below the prediction continue to render unchanged.
- [ ] **AC-8**: Template/rendering tests assert: (a) a multi-candidate prediction renders ≥2 ranked arms with games-grounded start-share, days-rest, and two-valued eligibility for each, with excluded arms in the `unavailable_arms` sub-block; (b) a one-candidate prediction (per AC-1b) renders exactly that one ranked arm plus the unavailable block (no fabricated extra arms); and (c) none of the previously single-name-only or blank states occur for a data-sufficient opponent.
- [ ] **AC-9**: No regression in existing report-rendering tests; assertions encoding the old confidence-tier card branches are updated to the new contract.

## Technical Approach
Two coordinated changes per Technical Notes TN-5. **(a) Engine** (`src/reports/starter_prediction.py`): enrich each `top_candidates` entry with the display fields the card needs — `start_share_pct` (`round(games_started / total_team_games * 100)`), days rest and `rest_eligibility` (read from E-243-01's attached rest-state), and pass `profile['throws']` through as an optional handedness field; and add the new additive `unavailable_arms: list[{name, reason}]` output field surfacing the engine's existing exclusion reasons (the hard-excluded arms that are absent from `top_candidates`). This engine-surface change is owned by E-243-03 (not E-243-01), and is available because E-243-03 runs after E-243-01/-02 on the same file. **(b) Template** (`src/api/templates/reports/scouting_report.html`): replace the confidence-tier-driven card branches so the ranked list renders for all non-suppressed states, render the `unavailable_arms` sub-block, and apply the reframed wording and estimate treatment.

The concrete design is the **ux-designer card spec at `epics/E-243-probable-starter-usefulness/E-243-03-card-spec.md`** — wireframe + field hierarchy + CSS (in the report's pt-unit idiom, NOT Tailwind) + suppress-state copy. SE reads that file directly and implements against it (it replaces the earlier vague "coordinate" / in-review-message reference). Preserve the existing rest/availability table, bullpen line, and Tier-2 narrative block below. Follow `.claude/rules/jinja-safety.md` (escape user-controlled values) and `.claude/rules/display-philosophy.md` (contextualize, never suppress).

## Dependencies
- **Blocked by**: E-243-02; ux-designer card spec persisted at `epics/E-243-probable-starter-usefulness/E-243-03-card-spec.md` (input artifact — must exist before SE implements the template)
- **Blocks**: E-243-04

## Files to Create or Modify
- `src/reports/starter_prediction.py`
- `src/api/templates/reports/scouting_report.html`
- `tests/test_starter_prediction.py`
- Report-rendering test(s) covering the predicted-starter card (the implementer discovers the exact file(s) per `.claude/rules/testing.md` test-scope discovery)
- `epics/E-243-probable-starter-usefulness/E-243-03-card-spec.md` (read-only INPUT — authored by ux-designer, consumed by SE; not modified by this story)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] ux-designer card design applied (layout + copy)

## Notes
The ux-designer card spec (wireframe + field hierarchy + CSS + suppress-state copy) is persisted at `epics/E-243-probable-starter-usefulness/E-243-03-card-spec.md` and is the authoritative design input — the SE implements against it rather than re-deriving layout. The `predicted_starter`/`alternative`/`confidence` fields on the engine output may remain for backward compatibility, but the card must no longer gate the ranked list behind them.

**CR-F6 (advisory — long-pass risk):** this is the heaviest single story in the epic — engine enrichment + new `unavailable_arms` field + a full template rewrite of the four confidence branches + tests. It is one coherent feature and should NOT be split, but the implementer should expect a long pass and stage the work (engine fields first, then template, then tests).
