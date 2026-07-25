# E-274-04: Reconcile the precedence ladder in `pitch-rules.md`

## Epic
[E-274: Read GameChanger's `age_group` as a structured level signal](epic.md)

## Status
`TODO`

## Description

After this story is complete, `.claude/rules/pitch-rules.md` describes the precedence ladder that actually ships — including the school family of `age_group` as a recognized structured signal, and the school-value → league mapping with its terminal suppressions. The file is the authoritative agent-facing reference for league resolution, and E-274-01 makes its current step 3 incomplete.

## Context

This follows the E-272-04 precedent exactly: E-272 changed `detect_league_level` and carried a dedicated claude-architect story to bring `.claude/rules/pitch-rules.md` to the shipped behavior, rather than leaving it to a closure-gate assessment. Same shape here.

The file's "Season as a Classification Axis" section enumerates a five-step precedence ladder, and step 3 currently reads as though `age_group` contributes only a `\d+U` bracket. After E-274-01 that is wrong in kind, not merely incomplete — the same field carries a school-family level token that outranks every team-name signal, and four of its values terminate in suppression rather than resolving a league.

Authoritative source for what to write: the epic's **TN-2** (the ladder and why the existing step is widened rather than a rung added), **TN-3** (the value-by-value mapping and the terminal suppressions), **TN-5** (the value set is open; unknown values fall through with a WARN). Do not re-derive any of it from the code — write what TN-2/TN-3/TN-5 specify and what E-274-01 actually shipped, and flag any divergence between the two rather than silently documenting the code.

## Acceptance Criteria

- [ ] **AC-1**: `.claude/rules/pitch-rules.md`'s precedence ladder describes the school family as part of the recognized-`age_group` step, matching the epic's Technical Notes TN-2 — including that it outranks every team-name-derived signal and remains behind DB fields and a recognized `ngb`.
- [ ] **AC-2**: The school-value → league mapping is documented per Technical Notes TN-3, including that `middle_12U` / `middle_13O` / `elementary` / `college` **terminally suppress** and specifically do NOT route to the Pitch Smart 15-18 estimate, with the under-resting reason stated.
- [ ] **AC-3**: The **stale "Tier 2: LLM Prompt Injection" paragraph is corrected.** It currently claims the Tier-2 prompt "injects the active league's rest table"; `enrich_prediction`'s own docstring (`src/reports/llm_analysis.py:225`) states the Variant A prompt is self-contained and **no longer injects an NSAA rest table**. Code is authoritative. Verify against the live code rather than the docstring alone, then correct the claim.
- [ ] **AC-4**: The "Display" section is left factually intact but is not left available to be misread as covering a **level** label. It correctly describes the exclusion *reason* string; per OQ-4's trace no competition-level value reaches the coach at all, and that over-extension is what made two agents disagree about a surface that does not exist.
- [ ] **AC-5**: No rest-rule table, tier, cap, or rest-day value in the file is altered. This story documents resolution and prompt behavior only. A reviewer can confirm by diffing that no numeric table row changed.
- [ ] **AC-6**: Every claim added or corrected names a symbol, file, or heading that resolves against the repo, per `.claude/rules/tool-output-integrity.md` ("Prose you AUTHOR is a claim too"). Cite stable anchors — test names, symbols, headings — not line ranges.

## Technical Approach

Bring the file to the shipped behavior after E-274-01 lands, using the epic's TN-2/TN-3/TN-5 as the specification. The doc-sweep discipline in `.claude/rules/doc-sweep.md` applies: a token grep for `age_group` is the starting point, not the check — enumerate how the precedence concept is expressed *without* that token (level word, bracket, "structured signal", the ladder's step numbering) and read the surrounding prose semantically.

AC-3's stale paragraph is included here rather than left standing because this story touches the same file and CA is the owner either way; a second edit to one rule file for a one-paragraph truth fix is waste. Note it is **independently valid** — it is a live falsehood about LLM prompt contents in the rule governing pitch rules, and it is unrelated to `age_group`. If this epic is delayed or abandoned, route AC-3 to claude-architect on its own rather than letting it die with the epic.

Worth recording as context for whoever picks this up: the stale paragraph sits in a file E-272 edited, and neither that epic's doc sweep nor its closure review caught it, because the section was outside the diff.

## Dependencies
- **Blocked by**: E-274-01 (the file must describe what shipped, not what was planned)
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/pitch-rules.md` (modify — the precedence ladder, the school-value mapping and suppressions, the stale Tier-2 paragraph)

Does NOT modify `.claude/agent-memory/baseball-coach/league-pitch-rules.md` — that file is baseball-coach's content to own, and this story's changes are resolution-path documentation rather than rule-table changes. If a change there proves necessary, report it rather than making it.

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No rest-rule numeric value changed
- [ ] Claims verified against the repo, not restated from the epic alone
- [ ] Any divergence found between what TN-2/TN-3/TN-5 specify and what E-274-01 shipped is reported, not silently documented

## Notes

The routing precedence in `.claude/rules/agent-routing.md` puts any story touching `.claude/rules/**` with claude-architect regardless of domain, which is why this is a CA story rather than a software-engineer one even though it documents SE's change.

AC-4 is deliberately conservative. The "Display" section is *correct*; the failure was a reader extending it to a label that does not exist. The fix is to make its scope explicit, not to weaken or remove a true statement — `.claude/rules/api-docs.md`'s factual-record standard has the same spirit even though it governs a different tree.
