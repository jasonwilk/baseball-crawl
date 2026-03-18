# E-124: Review Workflow Improvements

## Status
`READY`
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
| E-124-03 | Absolute main-session edit prohibition | TODO | None | - |
| E-124-01 | User-in-the-loop finding triage | TODO | E-124-03 | - |
| E-124-02 | Post-review remediation loop | TODO | E-124-01 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: File Impact Map

All three stories modify context-layer files. The file impact map below shows which files each story touches and where overlap exists.

| File | E-124-01 | E-124-02 | E-124-03 |
|------|----------|----------|----------|
| `.claude/skills/implement/SKILL.md` | Phase 3 Step 5 item 3 (triage); workflow summary diagram | Phase 4 (review chain) | Anti-patterns, Purpose section, workflow summary |
| `.claude/skills/codex-review/SKILL.md` | -- | Headless path Step 4+ (advisory triage -> remediation); workflow summary; anti-pattern #6 | -- |
| `.claude/rules/dispatch-pattern.md` | -- | -- | Opening paragraph, Team Roles section |
| `.claude/rules/workflow-discipline.md` | -- | Work Authorization Gate (post-review remediation exception) | Workflow Routing Rule section |

**Serialization note**: All three stories touch `.claude/skills/implement/SKILL.md` in different sections, and E-124-02 and E-124-03 both touch `.claude/rules/workflow-discipline.md` (different sections: Work Authorization Gate vs. Workflow Routing Rule). Because context-layer stories run in the main checkout without worktree isolation, and all three route to the same implementer (claude-architect), parallel execution would cause edit-tool conflicts. Stories MUST be serialized: **E-124-03 -> E-124-01 -> E-124-02**.

Rationale: E-124-03 establishes the absolute language foundation first. E-124-01 builds the triage enhancement on clean language. E-124-02 is the largest and most complex, benefiting from stable file content after the other two are complete.

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
2. **Remediation**: Confirmed findings are fixed by the implementer. The implementer works in the main checkout (not a worktree -- all story branches are already merged by this point).
3. **PM artifact tracking**: PM records all findings with their dispositions: FIXED (with change summary -- files and nature of change, not a git commit SHA since commits happen after team shutdown), DISMISSED (with reason), or FALSE POSITIVE (with explanation). Recording location depends on context: for the "and review" chain, PM writes to the dispatch epic's History section; for standalone post-dev reviews (which may not map to a single epic), PM writes to `/.project/research/codex-review-YYYY-MM-DD-remediation.md`.

This also affects the implement skill's Phase 4 ("and review" chain): when the review chain produces findings, the same remediation loop applies before proceeding to Phase 5 closure.

**Work authorization**: The codex-review skill currently says "Implementation requires a story reference per the Work Authorization Gate." The remediation loop is a special case -- findings from a code review (whether an "and review" chain on an ACTIVE epic with all stories DONE, or a standalone post-dev review) are remediated under the review session's authority, not a separate story. The authorization exception MUST live in `workflow-discipline.md`'s Work Authorization Gate (the structural rule loaded for all agents), not locally in the codex-review skill. If the exception were only in the skill, implementers spawned for remediation would see the structural gate in their ambient context and correctly refuse the work. The codex-review skill references the exception; the gate defines it.

**Spawning mechanics**: For the "and review" chain, the dispatch team is still active -- the original implementer validates and remediates findings. For standalone post-dev reviews, no dispatch team exists. The main session creates a remediation team using the agent routing table (`.claude/rules/agent-routing.md`) to select the appropriate implementer type(s) for the findings' domains, plus PM for disposition tracking. The codex-review skill must specify both paths.

**Anti-pattern reconciliation**: The codex-review skill's anti-pattern #6 currently says "Do not implement fixes during triage. Triage is advisory." This remains true -- triage is advisory. But the new remediation phase AFTER triage does authorize implementation. Anti-pattern #6 must be updated to clarify the boundary: triage recommends, remediation implements (under the Work Authorization Gate exception).

**No re-review for remediation**: Remediation fixes are small targeted changes driven by specific review findings. They are NOT re-reviewed by Codex or the code-reviewer. The implementer makes fixes and PM records dispositions (with change summaries, not commit SHAs -- commits happen after team shutdown). If the user wants another review pass after remediation, they invoke a separate codex-review. This keeps the loop finite.

**Routing authority**: The Work Authorization Gate exception must specify that remediation is authorized ONLY for findings explicitly routed by the main session from a specific review's output. The implementer cannot self-authorize remediation by citing the exception. This prevents the exception from being used to bypass the gate for unrelated work.

### TN-4: Absolute Edit Prohibition (Improvement 3)

**Current language**: Multiple places say the main session "MUST NOT write code" or "MUST NOT write or modify application/test code." The word "code" creates ambiguity -- does it include docs? Config? Context-layer files during non-dispatch work?

**New language**: The prohibition must be absolute and cover all file types. The main session MUST NOT create, modify, or delete any file directly. The only file operations the main session performs are: (1) git operations (`git merge`, `git mv` for archive moves, `git add`, `git commit`, and similar VCS commands), and (2) writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`). All other file edits are dispatched to the appropriate agent.

Files to update:
- Implement skill: Anti-patterns #1 and #13, Purpose section ("does not...write code"), workflow summary diagram ("main session NEVER fixes code itself"), and any other instance of weak "code"-scoped language. The implementer must scan comprehensively -- the locations above are known instances, not an exhaustive list.
- `dispatch-pattern.md`: Opening paragraph ("does not...write code") and Team Roles item 1 ("MUST NOT write code")
- `workflow-discipline.md`: Workflow Routing Rule "MUST NOT" list ("write or modify application/test code")

## Open Questions
- None remaining after CA consultation.

## History
- 2026-03-17: Created. Three review workflow improvements identified from operational experience.
- 2026-03-17: Refined after claude-architect consultation. Key changes: (1) serialized stories E-124-03 -> E-124-01 -> E-124-02 (no worktree isolation + same file + same implementer = edit conflicts); (2) added `workflow-discipline.md` to E-124-02 scope (Work Authorization Gate needs post-review remediation exception -- structural rule, not skill-local); (3) expanded E-124-03 to comprehensively scan for weak "code" language beyond anti-patterns #1/#13; (4) updated file impact map and overlap note.
- 2026-03-17: Second refinement pass (PM). Architect consultation attempted but no response received -- PM proceeded with own judgment on AC quality. Key changes: (1) E-124-03: broadened AC-2 to cover all weak language in dispatch-pattern.md including opening paragraph (line 8), not just Team Roles item 1; added AC-7 for comprehensive scanning of dispatch-pattern.md and workflow-discipline.md (AC-6 only covered implement skill); updated Technical Approach and Files to Modify accordingly. (2) E-124-02: fixed AC-4 scoping gap -- changed "completed epic" to "after all stories in the epic are DONE" to cover both standalone reviews and "and review" chains; improved AC-1 precision to match TN-3 (original implementer preference, not just "an SE"); added AC-7 for spawning mechanics (dispatch team reuse vs. new remediation team); added TN-3 spawning mechanics paragraph. (3) Updated file impact map for dispatch-pattern.md (opening paragraph + Team Roles). Serialization order E-124-03 -> E-124-01 -> E-124-02 confirmed still correct.
- 2026-03-17: Second refinement pass continued (PM + architect). Architect delivered adversarial review with 10 findings. Four incorporated: (1) E-124-03: added memory directory carve-out to AC-4, Description, and TN-4 -- without this, the main session couldn't update its own memory since workflow-discipline.md applies to all interactions, not just dispatch (Finding G, HIGH). (2) E-124-02: added AC-8 requiring codex-review anti-pattern #6 update -- current language "Do not implement fixes during triage" would contradict the new remediation phase (Finding B, HIGH). (3) E-124-02: added AC-9 explicitly stating no re-review for remediation fixes -- keeps the loop finite (Finding D, MEDIUM). (4) E-124-02: added AC-10 requiring routing authority scoping in the Work Authorization Gate exception -- prevents implementers from self-authorizing remediation (Finding J, MEDIUM). Updated file impact map (codex-review anti-pattern #6) and TN-3 (added anti-pattern reconciliation, no-re-review, and routing authority paragraphs). Findings A and F were already addressed by PM's earlier changes. Findings C, E, H skipped (low severity, context-obvious).
- 2026-03-18: Spec review refinement pass (PM). Addressed four findings (3 P1, 1 P3). (1) P1 -- standalone remediation epic targeting: E-124-02 AC-3 split into two recording paths -- "and review" chain writes to the dispatch epic's History section, standalone reviews write to `/.project/research/codex-review-YYYY-MM-DD-remediation.md` since standalone reviews may not map to a single epic. TN-3 updated to match. (2) P1 -- standalone remediation hard-codes SE: E-124-02 AC-7 changed from "SE + PM" to routing-table-driven implementer selection plus PM. TN-3 spawning mechanics updated to match. (3) P1 -- FIXED disposition requires commit ref but commits happen after team shutdown: E-124-02 AC-2 changed "commit ref" to "change summary" (files and nature of change, not a git SHA). TN-3 artifact tracking and no-re-review paragraphs updated for consistency. (4) P3 -- TN-1 stale scope: removed "Team Roles wording" from implement/SKILL.md row in file impact map (Team Roles is in dispatch-pattern.md, which already has its own row covering that scope).
