# E-263-07: Tonight's Game Plan section (SIG-005 two-branch, deterministic)

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, the report opens with a "Tonight's Game Plan" section (Technical Notes TN-5 Section 1) — the headline the coach reads first — that synthesizes the loss-forensics blueprint (SIG-005) into a deterministic two-branch plan conditioned on the probable starter. This is the section that directly fixes the 2026-07-12 live-validation miss.

## Context
Per Technical Notes TN-4 and the design-doc §8, the report's one systemic miss was a season-average blueprint that was never joined to the probable starter; the correct plan is two-branch ("if he's wild (his norm) → work counts/take walks; if he locates → he can't miss bats, put it in play and run"). Per Technical Notes TN-5, this section is deterministic (templated), NOT LLM-narrated — the LLM two-pass synthesis is a v2 non-goal; both branches are driven by fact-sheet values (the "wild" branch keyed on the starter's season strike%, the "locates" branch on his whiff rate, both from SIG-004). The scoped self-scout callout (our own starter's first-inning line) is deferred to v2 with the `--vs` matchup context (Technical Notes TN-6) — it is NOT in this section for v1. This story depends on SIG-001 (E-263-02b) and SIG-004 (E-263-04).

## Acceptance Criteria
- [ ] **AC-1**: The report renders a Tonight's Game Plan section at the top (Technical Notes TN-5 Section 1), placed per the E-263-01 layout spec, within the ≤3-bullet / ≤600-word / 60-second-read budget. It fills the pre-created blueprint stub module + Game Plan stub partial from E-263-02a.
- [ ] **AC-2**: SIG-005 loss-forensics blueprint is computed by per-loss counting across the opponent's **data-bearing** loss set — losses WITH charted `play_events` (who scored first, walks drawn, steals taken, when the losing pitcher was pulled), NOT all losses from `games` (a scouted opponent's scored-but-empty losses are the modal case — SE-F2 / the data-bearing-coverage principle). The raw-count denominator MUST match the reconstruction set ("3 of their 4 charted losses"), never a percentage below 5 losses (Technical Notes TN-2).
- [ ] **AC-3**: The blueprint is conditioned on SIG-001's probable starter and rendered as a DETERMINISTIC two-branch plan per Technical Notes TN-4/TN-5 — both branches populated from fact-sheet values (the "wild" branch on SIG-004 strike%, the "locates" branch on SIG-004 whiff%), NOT from an LLM call. A test proves the two branches reflect the starter's own strike%/whiff numbers. **Brand-new-arm edge case (Technical Notes TN-4):** when SIG-004 is `no_data` (0 prior IP this season), the section renders the two-branch STRUCTURE in generic/hedged read-and-adjust language rather than data-driven branches — a test covers the `no_data` starter path.
- [ ] **AC-4**: When SIG-001 resolves to "committee" (Technical Notes TN-4), the Game Plan renders the budget-constrained committee shape from Technical Notes TN-5 §1: a 2-arm committee → one compressed bullet per arm (both branches folded into one line); a 3+-arm committee → ONE composite bullet naming all eligible arms with a generic-but-actionable instruction — never per-arm branches that blow the ≤3-bullet budget. (Full per-arm detail lives in Who's Pitching, E-263-04.)
- [ ] **AC-5**: The section strips cleanly to instruction voice with no LLM dependency; if the OpenRouter key is absent the section renders identically (it is deterministic — this section does NOT call the LLM).
- [ ] **AC-6**: When `FEATURE_PREDICTED_STARTER` is OFF (SIG-001 absent — per Technical Notes TN-4), the Game Plan renders a LOUD, visible degraded/warning state (not a silent empty card), consistent with E-263-02b AC-5 and the report-run honesty mechanism. A test covers the flag-off path.

## Technical Approach
Fill the pre-created blueprint stub module under `src/reports/deep_scout/` (from E-263-02a) computing SIG-005 (per-loss counting over the DATA-BEARING loss set — losses with charted `play_events`, per AC-2 — for the first-run/BB/SB/pitching-change sequence, perspective-scoped per Technical Notes TN-3) and the deterministic two-branch templated plan driven by the SIG-001 + SIG-004 facts (incl. whiff%) from the fact sheet. Fill the Game Plan stub partial, reusing the shared trust-surface partial from E-263-02a. Do NOT add an LLM call — the two-branch plan is templated from fact-sheet values (the LLM narrative pass is a v2 non-goal per the epic). The self-scout callout is NOT built here in v1 (deferred to v2 with the `--vs` context).

## Dependencies
- **Blocked by**: E-263-02a (fact-sheet framework + blueprint stub + partial), E-263-02b (SIG-001), E-263-04 (SIG-004 incl. whiff% for the two-branch plan)
- **Blocks**: None

## Files to Create or Modify
- `src/reports/deep_scout/<blueprint module>.py` (modify — fill the SIG-005 + two-branch synthesis builder stub from E-263-02a)
- `src/api/templates/reports/deep_scout/<game-plan partial>.html` (modify — fill the Tonight's Game Plan stub partial from E-263-02a)
- `tests/test_deep_scout_blueprint.py` (new — data-bearing loss set, raw-count below 5 charted losses, two-branch reflects starter strike%/whiff%, committee 2-arm vs 3+-composite shape, no LLM dependency)

Does NOT edit `scouting_report.html` or the assembler — E-263-02a owns those seams per Technical Notes TN-9.

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This section is the epic's headline value (the #1-miss fix) and it ships deterministically — no LLM. Keep the two-branch logic driven by fact-sheet values so it is fully unit-testable. Depends on E-263-04 for the pitching facts it conditions on.
