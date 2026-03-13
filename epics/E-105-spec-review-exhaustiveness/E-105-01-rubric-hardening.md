# E-105-01: Spec Review Rubric Hardening

## Epic
[E-105: Spec Review Exhaustiveness](epic.md)

## Status
`TODO`

## Description
After this story is complete, the spec review rubric at `.project/codex-spec-review.md` catches consistency, propagation, and surface area errors that caused E-072's multi-round drift. Reviewers build a facts table before checking individual items, and re-reviews are scoped to changes only.

## Context
The current rubric has 9 categories that check surface-level properties (AC clarity, dependencies, routing, sizing). It does not check whether values are consistent across files, whether edits have propagated to all locations, or whether ACs are unnecessarily restating Technical Notes. These gaps meant E-072's spec review missed drift that required 3 additional rounds to fix. See epic Technical Notes for category definitions and methodology details.

## Acceptance Criteria
- [ ] **AC-1**: The rubric contains categories 10 (Internal Consistency), 11 (Propagation Completeness), and 12 (Specification Surface Area) per the definitions in epic Technical Notes "Category Definitions."
- [ ] **AC-2**: The rubric's Setup or Evaluation Checklist section instructs reviewers to build a facts table (per epic Technical Notes "Complete Model Methodology") before evaluating individual checklist items.
- [ ] **AC-3**: The rubric contains a "Re-Review Protocol" section that scopes round 2+ reviews to changes only, per epic Technical Notes "Re-Review Scoping."
- [ ] **AC-4**: Existing categories 1-9 are unchanged (no regressions to current rubric coverage).

## Technical Approach
Read `.project/codex-spec-review.md` in full. Add three new category sections (10, 11, 12) following the existing format. Add the facts-table methodology instruction near the top (after Setup, before the first category). Add a Re-Review Protocol section after the existing categories. Reference the epic Technical Notes for the content of each addition -- the implementer should read those sections and translate them into rubric-appropriate language (imperative instructions to a reviewer, not descriptive prose).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.project/codex-spec-review.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No accidental modifications to files outside the rubric

## Notes
- The rubric is used by both Codex (headless) and human reviewers. Keep language tool-agnostic.
- The "Reporting" section at the bottom should remain as-is -- it already covers finding format and priority ratings.
