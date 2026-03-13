# E-105-02: Template and PM Self-Review Gate

## Epic
[E-105: Spec Review Exhaustiveness](epic.md)

## Status
`TODO`

## Description
After this story is complete, story and epic templates discourage AC-level duplication of Technical Notes, and the PM agent definition includes a self-review gate that catches cascade drift before handing back to reviewers.

## Context
E-072's ACs restated Technical Notes content verbatim, creating a sync surface that grew with each edit. The story template has no guidance against this pattern. Additionally, the PM incorporated review findings without a consistency sweep, so fixes in one file introduced drift in another. A post-incorporation self-review gate (grep for changed values) would catch these before the next review round. See epic Technical Notes for the design principle and deliverables.

## Acceptance Criteria
- [ ] **AC-1**: The story template (`.project/templates/story-template.md`) contains guidance in or near the Acceptance Criteria section that ACs should reference Technical Notes sections rather than restating their content, per epic Technical Notes row 6.
- [ ] **AC-2**: The story template contains guidance that ACs with more than 3 sub-clauses should be decomposed or converted to Technical Notes references, per epic Technical Notes row 9.
- [ ] **AC-3**: The epic template (`.project/templates/epic-template.md`) contains a note in the Technical Notes section that Technical Notes are the single source of truth for procedures and constraints -- ACs verify outcomes, per epic Technical Notes row 7.
- [ ] **AC-4**: The PM agent definition (`.claude/agents/product-manager.md`) contains a self-review gate that requires a grep-based consistency sweep after incorporating review findings, before handing back to reviewers, per epic Technical Notes row 8.
- [ ] **AC-5**: Existing template sections and PM agent definition sections are otherwise unchanged (no regressions).

## Technical Approach
Three files to modify. For the story template: add a brief comment/guidance note near the AC section (HTML comment or inline note, matching existing template style). For the epic template: add a brief note in the Technical Notes section comment. For the PM agent definition: add a self-review gate subsection -- the implementer should find the appropriate location (near the Quality Checklist or the refinement workflow) and add the grep sweep instruction. Keep all additions concise -- a few sentences each, not paragraphs.

Reference files:
- `.project/templates/story-template.md`
- `.project/templates/epic-template.md`
- `.claude/agents/product-manager.md` (read the Quality Checklist and refinement sections to find the right insertion point)

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.project/templates/story-template.md` (modify)
- `.project/templates/epic-template.md` (modify)
- `.claude/agents/product-manager.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No accidental modifications to files outside the three listed files

## Notes
- Template changes apply to future epics only -- no need to retrofit existing stories.
- The PM self-review gate is advisory (a checklist item), not a hard enforcement mechanism. The PM is an LLM agent; the gate reminds it to do the sweep, it does not block anything programmatically.
