# E-274-01: School-family level branch in `detect_league_level`

## Epic
[E-274: Read GameChanger's `age_group` as a structured level signal](epic.md)

## Status
`TODO`

## Description

After this story is complete, `detect_league_level` reads the school family of GameChanger's `age_group` field as a structured level signal. An opponent carrying `high_varsity` / `high_junior_varsity` / `high_freshman` resolves to a real league — even when its team name carries no level word at all, which today reaches `unknown` and suppresses the Most Likely Arms card. The four school values that sit outside our rule tables (`middle_12U`, `middle_13O`, `elementary`, `college`) terminally suppress rather than falling through, and a value the matcher does not recognize behaves exactly as it does today while emitting an operator-visible WARN.

## Context

This is the whole of the epic's value and the whole of its safety surface, in one function. It is deliberately **not** split into "add the mapping" and "add the guard" stories: a branch that maps the HS values without the terminal suppression would ship the under-resting hazard described in the epic's Technical Notes TN-3, and a branch without the Reserve veto (TN-4) would move a currently-safe case into the under-resting direction. Neither is a safe increment, so they land together.

The signal already arrives. `src/reports/generator.py:1689` assigns `self.age_group_from_api` and `:2434` passes it into `detect_league_level` — no plumbing, no schema, no new request. Software-engineer verified the field is **inert today**: all seven school values currently produce results byte-identical to `age_group=None`.

Authoritative specs for this story, all in the epic file: **TN-1** (what the field is and the live evidence behind it), **TN-2** (precedence — widen the existing recognized-`age_group` step, do not add a rung), **TN-3** (the value-by-value mapping table and why the four suppressions must be terminal), **TN-4** (the Reserve veto and the verbatim accepted-risk sentence), **TN-5** (the value set is OPEN — allowlist with a visible unknown fallback, and three things not to reuse), **TN-6** (season interaction, the decided season-absent case, and **an AC trap: within the school family `season` is CONSTANT — all 73 live opponents are `"spring"`, so it carries zero discriminating information for separating school tiers and a test using it that way silently does nothing.** The spring/summer parametrization in AC-1/AC-2 below is a deliberate *synthetic* exercise of the mapping; do not try to validate it against live data), **TN-8** (test strategy, the two fixture traps, and the guard tests to keep green).

Cross-references worth loading as deferred context: `/workspaces/baseball-crawl/.claude/rules/pitch-rules.md` ("Season as a Classification Axis") for the precedence ladder this extends, and `/workspaces/baseball-crawl/docs/api/endpoints/get-public-teams-public_id.md` → `## The age_group level field` for the field's provenance and the live evidence. **Cite the endpoint doc, not api-scout's agent-memory** — api-scout asked for this explicitly; the memory files are working notes and were rewritten mid-discovery.

## Acceptance Criteria

- [ ] **AC-1**: Given an empty `ngb` and a team name carrying **no** level word, when `age_group` is `high_freshman` or `high_junior_varsity`, then the resolved league is `nsaa_subvarsity` for a spring season and `nrbl` for a summer season — where the same inputs resolve `unknown` today. This is the epic's primary value case; cover both season values, not one.
- [ ] **AC-2**: Given the same conditions, when `age_group` is `high_varsity`, then the resolved league is `nsaa_varsity` for spring and `legion` for summer, per the mapping table in Technical Notes TN-3.
- [ ] **AC-3**: Given `age_group` is `middle_12U`, `middle_13O`, `elementary`, or `college`, then the card suppresses **terminally** for each of the four — the team name is not consulted and the result is not `youth_travel`. A test proves terminality by pairing each value with a team name that WOULD otherwise resolve a league (e.g. a name containing "Varsity"), per Technical Notes TN-3.
- [ ] **AC-4**: Given one of the four suppressing values from AC-3, then the operator-visible note distinguishes a deliberate out-of-scope level from an undetected league — it is not the generic "league not detected" copy. Per `.claude/rules/display-philosophy.md`, the raw engine note is operator-facing and is never echoed to the coach.
- [ ] **AC-5**: Given ANY team-name level word that disagrees with the structured value on tier — **including** "Reserve"/"Reserves" against `age_group == "high_varsity"` — then `age_group` wins and a WARN is logged. **There is NO Reserve carve-out and none is to be added**, per Technical Notes TN-4 (baseball-coach re-ruled and dropped it on 0-of-17 evidence; an earlier draft of this story specified a veto — do not implement it). The test asserts the *absence* of the special case: a Reserve-named team tagged `high_varsity` resolves the varsity family, not sub-varsity. Put the reasoning in the docstring so a future maintainer does not read it as a missing guard.
- [ ] **AC-6**: Given a non-empty `age_group` that matches **no** family — school, travel bracket, or recreational range — then the resolution falls through to the team-name path exactly as it does today and no exception is raised. Cover both a plausible future value (`"high_sophomore"`) and the existing `"High School"` literal; the plausible one is what a future maintainer will recognize as the real scenario.
- [ ] **AC-7**: Given the AC-6 fall-through, a WARN is emitted, and a miss that **looks school-family** (`high_*` / `middle_*` / `college`-adjacent) is logged distinguishably from an arbitrary unrecognized string — the former is evidence GameChanger shipped a new enum value we owe a decision on, and the message should say so. The predicate is scoped to "matched **no family**" so brackets and the recreational form never reach it, per Technical Notes TN-5. **Resolution is identical in both cases; only the log differs** — an undecided value must never pick a rest table.
- [ ] **AC-8**: `high_sophomore` on a team named "…Sophomore" continues to resolve `nsaa_subvarsity` via the existing `\bsophomore\b` name pattern, unchanged by this story. This is the concrete case a `high_*` prefix match would have broken (Technical Notes TN-5) — pin it so nobody reintroduces prefix matching later.
- [ ] **AC-9**: Given a recognized `ngb` or a populated DB `program_type`/`classification`, then the school-family branch does not change the result — the precedence order in Technical Notes TN-2 holds, and `age_group` outranks only team-name-derived signals. A test covers a recognized `ngb` winning over a school value, and a school value winning over a `\d+U` bracket appearing in the **team name**.
- [ ] **AC-10**: The two guard tests named in Technical Notes TN-8 (`test_age_group_high_school_falls_through`, `test_age_group_high_school_still_falls_through_with_range_fix`) remain green with their **assertions unmodified**, and are **renamed** to describe the property they actually pin (unrecognized-value fall-through) rather than "the high school case."
- [ ] **AC-12**: The epic's Technical Notes TN-10 baseline ("70 of 73 already agree", 3 movers) is a **simulation of the function**, run with `program_type=None` / `classification=None` / `season='spring'` — not a measurement of the pipeline. Confirm the **real call-site inputs** at `src/reports/generator.py:2432-2447`: specifically whether a tracked opponent can arrive with a non-null `program_type` or `classification`, which would short-circuit the ladder earlier and shift the baseline. Report the finding; if it diverges from TN-10, say so rather than adjusting the epic's numbers silently.
- [ ] **AC-11**: The full suite is green, and the five `starter_prediction` importer files named in Technical Notes TN-8 pass. If any pre-existing assertion outside AC-10 must change to make this story pass, that is a design-review trigger per TN-8 — stop and report it rather than updating the assertion.

## Technical Approach

Widen the existing recognized-`age_group` step in `detect_league_level` so the three `age_group` families are handled as one mutually-exclusive chain over that single field, keeping the whole step ahead of every team-name-derived signal and behind DB fields and a recognized `ngb` (TN-2). **Add the school branch; leave the travel-bracket and recreational-range branches alone** — api-scout verified both work today, so this is additive, not a rewrite of the chain. **Put the school check first** in the chain: order is immaterial for correctness (the vocabularies are disjoint and no school value matches either existing regex) but school-first keeps `middle_12U`'s terminal suppression from depending on another branch's regex continuing not to match it (TN-2). Resolve a school value to a level **class**, then let the existing season logic pick the family, so the season axis is reused rather than duplicated (TN-3, TN-6). The four out-of-scope values must terminate the function rather than fall through (TN-3), and need a league identifier that `get_rules_for_league` does not recognize plus a level-specific warning entry alongside the existing ones.

Three things Technical Notes TN-5 rules out, each for a stated reason: do not reuse `_LEVEL_WORD_PATTERNS` against the `age_group` value, do not feed `age_group` to `_nsaa_level_from_name`, and do not adopt a `high_*` prefix match. The value set is **open**, not closed, so the matcher must fail visibly on values we have not decided about rather than absorbing them.

Carry the verbatim accepted-risk sentence from TN-4 as a code comment on the veto. Per `.claude/rules/tool-output-integrity.md`, any prose you write asserting how this code behaves is a claim to resolve against the repo — and the closing generalization of a safety comment is exactly where this project has repeatedly shipped false statements.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-274-02, E-274-04

## Files to Create or Modify
- `src/reports/starter_prediction.py` (modify — the school-family branch, the level-class mapping, the terminal suppression identifiers and their warning entries, the Reserve veto, the unmatched-family WARN)
- `tests/test_league_detection.py` (modify — the new parametrized coverage; the two guard-test renames per AC-8)

Does NOT modify `src/reports/generator.py` (the signal is already fetched and already passed), any migration, any template, or `_LEVEL_WORD_PATTERNS`' ordering (that is IDEA-172, explicitly out of scope per the epic's TN-7).

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-274-02**: the school-value → level-class mapping that story reuses for the tier decision inside the recognized-`nsaa` branch.
- **Produces for E-274-04**: the shipped precedence ladder and school-value mapping that `.claude/rules/pitch-rules.md` must be reconciled to. Report any divergence between what this story ships and what the epic's TN-2/TN-3/TN-5 specify — E-274-04 documents the former, not the latter.

Not a deliverable, but worth knowing: **IDEA-177** (the removed story 03, surfacing the competition level to the coach) would become near-trivial if this story cheaply preserved *which* school value a sub-varsity resolution came from, rather than collapsing `high_freshman` and `high_junior_varsity` into one class with no trace. If that is free, taking it is welcome; if it costs anything, do not — it is explicitly out of scope and must not be smuggled in.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] No new migration; no new crawling; no change to any rest-rule table or rest-day value

## Notes

Two fixture traps from Technical Notes TN-8 apply directly to this story and neither is hypothetical:

1. Both e2e fixtures already carry `age_group: "high_varsity"` next to a name that also says "Varsity", so structured and name agree and the e2e suite stays green **while being structurally unable to discriminate whether this branch works.** Do not let e2e green count as coverage for this story.
2. `tests/test_report_generator.py:3066-3080` builds the signal set by direct attribute assignment, bypassing the real fetch. Setting `age_group_from_api` there while leaving `season=None` would produce a passing test asserting a behavior the live path essentially cannot reach — a test that quietly contradicts the epic's own recorded rationale in TN-6. If you add generator-level coverage, set `season_from_api` to a value the same payload would have carried, or write it as a pure-function test and label it as such.

`middle_12U` does **not** currently match `\b(\d+)U\b` — `_` is a word character, so there is no boundary before the digits. That underscore trap is currently *protecting* it. IDEA-171's own recommended fix (normalize `_`→space before matching) would break that protection and route a middle-school team to the 15-18 Pitch Smart curve. This is why AC-3 requires terminality: the hazard is created by the fix, not by the status quo, and a non-terminal suppression would let it survive its own fix.
