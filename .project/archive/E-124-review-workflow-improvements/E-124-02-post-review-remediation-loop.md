# E-124-02: Post-Review Remediation Loop

## Epic
[E-124: Review Workflow Improvements](epic.md)

## Status
`DONE`

## Description
After this story is complete, the codex-review skill will define a formal remediation loop for post-implementation code review findings: an implementer validates each finding, remediates confirmed issues, and PM records all findings and their dispositions (in the dispatch epic's History section for "and review" chains, or in a standalone remediation log for post-dev reviews). The implement skill's Phase 4 ("and review" chain) will also connect to this remediation loop.

## Context
Post-implementation code reviews currently end at advisory triage -- findings are presented and agents recommend actions, but there is no structured path for an implementer to validate and fix confirmed issues, or for PM to track outcomes. The user wants findings to flow through implementer validation and remediation, with PM recording dispositions in epic artifacts.

## Acceptance Criteria
- [ ] **AC-1**: The codex-review skill's headless path (after Step 4 triage) defines a remediation loop where an implementer validates each finding and remediates confirmed issues. Implementer selection follows AC-7's spawning mechanics (dispatch team reuse vs. routing-table-driven selection), per Technical Notes TN-3.
- [ ] **AC-2**: The remediation loop specifies three finding dispositions: FIXED (with change summary), DISMISSED (with reason), and FALSE POSITIVE (with explanation). The change summary describes what was fixed (files, nature of change) -- not a git commit SHA, since commits happen after team shutdown.
- [ ] **AC-3**: The remediation loop specifies where PM records findings and dispositions for each context: (a) during the "and review" chain, PM records in the dispatch epic's History section; (b) during standalone post-dev reviews, PM records in a remediation log at `/.project/research/codex-review-YYYY-MM-DD-remediation.md` (standalone reviews may not map to a single epic).
- [ ] **AC-4**: `workflow-discipline.md`'s Work Authorization Gate includes a post-review remediation exception: when a code review (whether an "and review" chain on an ACTIVE epic with all stories DONE, or a standalone post-dev review) identifies findings for remediation, the review session's authority substitutes for a story reference. The codex-review skill references this exception (does not declare its own authorization model).
- [ ] **AC-5**: The implement skill's Phase 4 ("and review" chain) connects to the remediation loop -- when the review chain produces findings, they flow through the same validation/remediation/tracking process before proceeding to Phase 5 closure.
- [ ] **AC-6**: The codex-review workflow summary diagram reflects the remediation loop.
- [ ] **AC-7**: The remediation loop specifies spawning mechanics for both contexts: (a) during the "and review" chain, the original implementer on the dispatch team validates and remediates; (b) during standalone post-dev reviews, the main session creates a remediation team using the agent routing table to select the appropriate implementer type(s) for the findings' domains (not hard-coded to SE), plus PM for disposition tracking.
- [ ] **AC-8**: The codex-review skill's anti-pattern #6 ("Do not implement fixes during triage") is updated to clarify that triage remains advisory but a separate remediation phase (authorized by the Work Authorization Gate exception) follows triage for confirmed findings.
- [ ] **AC-9**: The remediation loop explicitly states that remediation fixes are NOT re-reviewed -- the implementer commits fixes and PM records dispositions. If the user wants another review pass, they invoke a separate codex-review.
- [ ] **AC-10**: The Work Authorization Gate exception specifies that remediation is authorized ONLY for findings explicitly routed by the main session from a specific review's output. Implementers cannot self-authorize remediation by citing the exception.

## Technical Approach
Three files need changes. The codex-review skill's headless path currently ends at advisory triage (Step 4). This story extends it with remediation steps (validation, fix, PM tracking). The implement skill's Phase 4 currently just says "chain into the code review workflow" -- it needs to specify that findings from the chained review enter the remediation loop before closure proceeds.

The work authorization exception MUST live in `/.claude/rules/workflow-discipline.md`'s Work Authorization Gate (the structural rule loaded for all agents), not locally in the codex-review skill. If the exception were only in the skill, implementers spawned for remediation would see the structural gate in their ambient context and correctly refuse the work. The codex-review skill references the exception; the gate defines it. See epic Technical Notes TN-3 for details.

## Dependencies
- **Blocked by**: E-124-01 (triage enhancement must be in place before remediation loop builds on it)
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/codex-review/SKILL.md` (headless path Step 4+, workflow summary, anti-pattern #6)
- `.claude/skills/implement/SKILL.md` (Phase 4)
- `.claude/rules/workflow-discipline.md` (Work Authorization Gate -- post-review remediation exception)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing skill structure
- [ ] Code follows project style (see CLAUDE.md)

## Notes
The user's exact words: "And have the original implementor validate the findings and remediate if necessary. Have PM note them in the epic artifacts."
