# E-068-03: Add Vision Signal Review to Dispatch Closure Sequence

## Epic
[E-068: Vision Stewardship](epic.md)

## Status
`DONE`

## Description
After this story is complete, the dispatch closure sequence will include a new advisory step that reviews accumulated vision signals after the ideas backlog review. When unprocessed signals exist, the step mentions them in the summary and asks the user if they want to "curate the vision." This is a prompt, not a blocking gate -- it does not prevent archival.

## Context
The dispatch closure sequence already reviews the ideas backlog (Step 14 in `dispatch-pattern.md`). Vision signal review is a natural companion -- both are about surfacing accumulated insights at a natural checkpoint. However, unlike the documentation and context-layer assessment gates, this step is advisory. It prompts the user but does not block the closure flow. The step needs to appear in two authoritative files: `dispatch-pattern.md` (the canonical closure sequence) and `implement/SKILL.md` (which agents follow during dispatch).

## Acceptance Criteria
- [ ] **AC-1**: `/.claude/rules/dispatch-pattern.md` contains a new step in the Closure Sequence between the current ideas backlog review (Step 14) and the summary (Step 15). The step instructs the main session to check whether `docs/vision-signals.md` contains any entries beyond its header section (any content after the `## Signals` heading counts as unprocessed) and mention them in the closure summary if any exist.
- [ ] **AC-2**: The new step explicitly states it is advisory, not blocking -- the closure sequence proceeds regardless of whether the user chooses to curate.
- [ ] **AC-3**: The new step uses the phrase "curate the vision" when prompting the user (this epic introduces this trigger phrase).
- [ ] **AC-4**: Steps after the new insertion are renumbered correctly (the summary, team teardown, and commit offer steps all shift by one).
- [ ] **AC-5**: `/.claude/skills/implement/SKILL.md` is updated with the corresponding vision signal review step in its closure/post-dispatch phase, matching the position and semantics from `dispatch-pattern.md`.

## Technical Approach
Two files need edits. In `dispatch-pattern.md`, add a new step after the current Step 14 (ideas backlog review). The step should check whether `docs/vision-signals.md` has any entries after the `## Signals` heading (content beyond the header = unprocessed signals), and if so, include a note in the closure summary offering vision curation. Renumber Steps 15-17 to 16-18. In `implement/SKILL.md`, add the matching step in the closure phase at the corresponding position.

The step text should be brief and parallel in structure to the ideas backlog review step.

## Dependencies
- **Blocked by**: E-068-01
- **Blocks**: E-068-05

## Files to Create or Modify
- `.claude/rules/dispatch-pattern.md`
- `.claude/skills/implement/SKILL.md`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Step numbering is correct within each file after insertion (each file uses its own numbering convention)
- [ ] No regressions in existing tests

## Notes
Read both files fully before editing to understand the current step numbering and ensure the new step fits naturally into the flow. The implement skill may use slightly different step numbering than dispatch-pattern.md -- match each file's own convention.
