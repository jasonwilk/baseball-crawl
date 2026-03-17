# E-124: Review Workflow Improvements

## Status
`DRAFT`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Codify three review workflow improvements that close gaps in how the main session handles code review findings during dispatch: (1) user-in-the-loop triage for dismissed findings, (2) a formal post-review remediation loop with PM artifact tracking, and (3) an absolute prohibition on the main session editing any files directly.

## Background & Context
These improvements were identified through operational experience with the dispatch workflow:

1. **Dismissal visibility gap**: During dispatch, the main session triages SHOULD FIX findings by accepting or dismissing them. Dismissals currently happen without user input, meaning the user has no visibility into what was closed or why. The user wants veto power over dismissals while not slowing down the fix cycle for accepted findings.

2. **Post-review remediation gap**: Post-implementation code reviews (the "and review" chain or standalone codex reviews) produce findings via advisory triage, but there is no formal loop where an implementer validates and remediates confirmed issues. PM also has no structured path to record outcomes in epic artifacts.

3. **Main session self-edit drift**: Despite existing anti-patterns stating the main session must not write code, in practice it sometimes makes "trivial" edits (doc fixes, one-liners) instead of routing to the appropriate agent. This needs an absolute, unambiguous prohibition covering all file types.

Expert consultation: claude-architect (context-layer file scope and change sizing). No other expert consultation required -- all three improvements are context-layer process changes within PM and CA's domains.

## Goals
- User has visibility and veto power over every finding dismissal during dispatch triage
- Post-implementation code reviews have a formal remediation loop with implementer validation and PM artifact tracking
- The main session's file-edit prohibition is absolute and covers all file types, not just code

## Non-Goals
- Changing the code-reviewer agent's behavior or rubric
- Modifying the spec-review workflow
- Adding new review tooling or scripts
- Changing how MUST FIX findings are handled (they already route to implementers)

## Success Criteria
- The implement skill's triage section requires user confirmation before any finding is dismissed
- The codex-review skill defines a remediation loop that flows findings through implementer validation and PM artifact tracking
- Every anti-pattern and role description in the implement skill, dispatch-pattern, and workflow-discipline files prohibits main-session file edits without exception language

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-124-01 | User-in-the-loop finding triage | TODO | None | - |
| E-124-02 | Post-review remediation loop | TODO | None | - |
| E-124-03 | Absolute main-session edit prohibition | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: File Impact Map

All three stories modify context-layer files. The file impact map below shows which files each story touches and where overlap exists.

| File | E-124-01 | E-124-02 | E-124-03 |
|------|----------|----------|----------|
| `.claude/skills/implement/SKILL.md` | Phase 3 Step 5 item 3 (triage) | Phase 4 (review chain) | Anti-patterns, Team Roles wording in Phase 2 |
| `.claude/skills/codex-review/SKILL.md` | -- | Headless path Step 4 (advisory triage -> remediation) | -- |
| `.claude/rules/dispatch-pattern.md` | -- | -- | Team Roles section |
| `.claude/rules/workflow-discipline.md` | -- | -- | Workflow Routing Rule section |

**Overlap note**: E-124-01 and E-124-03 both touch `.claude/skills/implement/SKILL.md` but in different sections (triage logic vs. anti-patterns/role descriptions). They can run in parallel because their edits are in non-overlapping sections. E-124-02 also touches the implement skill but in Phase 4, which is separate from both. All three stories are parallelizable.

### TN-2: User-in-the-Loop Triage Procedure (Improvement 1)

**Current behavior** (implement skill, Phase 3, Step 5, item 3): The main session triages each SHOULD FIX finding as accept or dismiss. Dismissals are recorded with a one-line reason and closed immediately.

**New behavior**: The main session splits findings into two tracks:
- **Accept track**: Findings the main session intends to fix. These are routed to the implementer immediately alongside any MUST FIX items. No user confirmation needed.
- **Dismiss track**: Findings the main session intends to dismiss. For each, the main session presents the finding and its dismissal reasoning to the user, then waits for user confirmation before closing. If the user vetoes a dismissal, the finding moves to the accept track.

This applies only to the in-dispatch triage (Phase 3 Step 5). The post-review remediation loop (Improvement 2) has its own user interaction model.

### TN-3: Post-Review Remediation Loop (Improvement 2)

**Current behavior** (codex-review skill, headless path, Step 4): After presenting findings, the skill offers an advisory triage session. A triage team assesses findings and recommends action but does NOT implement changes. Implementation requires a story reference per the Work Authorization Gate.

**New behavior**: After presenting findings and performing triage (whether via triage team or main session), any findings marked for remediation enter a remediation loop:

1. **Validation**: An SE (or the original implementer if still available on the team) validates each finding -- confirming it's a real issue or dismissing it as a false positive.
2. **Remediation**: Confirmed findings are fixed by the implementer. The implementer works in the main checkout (not a worktree -- the epic is already completed/merged).
3. **PM artifact tracking**: PM records all findings in the epic's History section with their dispositions: FIXED (with commit ref), DISMISSED (with reason), or FALSE POSITIVE (with explanation).

This also affects the implement skill's Phase 4 ("and review" chain): when the review chain produces findings, the same remediation loop applies before proceeding to Phase 5 closure.

**Work authorization**: The codex-review skill currently says "Implementation requires a story reference per the Work Authorization Gate." The remediation loop is a special case -- findings from a completed epic's review are remediated under the epic's authority, not a separate story. The skill must clarify this authorization path.

### TN-4: Absolute Edit Prohibition (Improvement 3)

**Current language**: Multiple places say the main session "MUST NOT write code" or "MUST NOT write or modify application/test code." The word "code" creates ambiguity -- does it include docs? Config? Context-layer files during non-dispatch work?

**New language**: The prohibition must be absolute and cover all file types. The main session MUST NOT create, modify, or delete any file directly. The only file operations the main session performs are git operations: `git merge`, `git mv` (for archive moves), `git add`, `git commit`, and similar VCS commands. All other file edits are dispatched to the appropriate agent.

Files to update:
- Implement skill: Anti-patterns #1 and #13, Phase 2 Step 2 spawn context references
- `dispatch-pattern.md`: Team Roles item 1
- `workflow-discipline.md`: Workflow Routing Rule "MUST NOT" list

## Open Questions
- None remaining after CA consultation.

## History
- 2026-03-17: Created. Three review workflow improvements identified from operational experience.
