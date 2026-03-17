# E-124-02: Post-Review Remediation Loop

## Epic
[E-124: Review Workflow Improvements](epic.md)

## Status
`TODO`

## Description
After this story is complete, the codex-review skill will define a formal remediation loop for post-implementation code review findings: an implementer validates each finding, remediates confirmed issues, and PM records all findings and their dispositions in the epic's History section. The implement skill's Phase 4 ("and review" chain) will also connect to this remediation loop.

## Context
Post-implementation code reviews currently end at advisory triage -- findings are presented and agents recommend actions, but there is no structured path for an implementer to validate and fix confirmed issues, or for PM to track outcomes. The user wants findings to flow through implementer validation and remediation, with PM recording dispositions in epic artifacts.

## Acceptance Criteria
- [ ] **AC-1**: The codex-review skill's headless path (after Step 4 triage) defines a remediation loop where an SE validates each finding and remediates confirmed issues, per Technical Notes TN-3.
- [ ] **AC-2**: The remediation loop specifies three finding dispositions: FIXED (with commit ref), DISMISSED (with reason), and FALSE POSITIVE (with explanation).
- [ ] **AC-3**: The remediation loop specifies that PM records all findings and their dispositions in the epic's History section.
- [ ] **AC-4**: The codex-review skill clarifies the work authorization path for post-epic remediation (findings from a completed epic's review are remediated under the review's authority, not requiring a separate story).
- [ ] **AC-5**: The implement skill's Phase 4 ("and review" chain) connects to the remediation loop -- when the review chain produces findings, they flow through the same validation/remediation/tracking process before proceeding to Phase 5 closure.
- [ ] **AC-6**: The codex-review workflow summary diagram reflects the remediation loop.

## Technical Approach
Two files need changes. The codex-review skill's headless path currently ends at advisory triage (Step 4). This story extends it with remediation steps (validation, fix, PM tracking). The implement skill's Phase 4 currently just says "chain into the code review workflow" -- it needs to specify that findings from the chained review enter the remediation loop before closure proceeds.

The work authorization question is important: the codex-review skill currently says implementation requires a story reference. The remediation loop is post-epic, so it needs a different authorization model -- remediation is authorized by the review itself, not a story.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/codex-review/SKILL.md` (headless path Step 4+, workflow summary)
- `.claude/skills/implement/SKILL.md` (Phase 4)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing skill structure
- [ ] Code follows project style (see CLAUDE.md)

## Notes
The user's exact words: "And have the original implementor validate the findings and remediate if necessary. Have PM note them in the epic artifacts."
