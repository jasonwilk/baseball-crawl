# E-096: Resolve All Review Findings During Stories

## Status
`DRAFT`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Change the dispatch review loop so that every code-reviewer finding is resolved (fixed or dismissed) during the story, rather than deferring SHOULD FIX items to epic History. The current pattern creates a class of acknowledged-but-never-addressed debt. If a finding should be fixed, fix it before the story closes. If it should not be fixed, dismiss it with a reason. No limbo.

## Background & Context
User feedback (2026-03-11):

> "I don't want you to act on *all* feedback, but I think you don't act on enough. I see you deferring cosmetic changes, for instance. Or things that are already tracked as 'should fix'. If you're tracking them as 'should fix', then why aren't we fixing them in the first place? If it needs fixed, fix it before somebody points it out. It shouldn't make it through the story without being fixed if it's tracked and you think that it should be. And for cosmetic, why defer it? You either agree with it or you don't. If you agree with it, then fix it. If you don't agree with it...don't fix it. But don't defer it because it's superficial. Work with the reviewer to come to a resolution state and act on that state."

The current review loop has a structural flaw: the main session only relays MUST FIX findings to implementers and records SHOULD FIX findings in epic History for "later." In practice, "later" means "never" -- the SHOULD FIX items accumulate as acknowledged debt across every epic (see archived epics listing multiple SHOULD FIX items that were never addressed). The main session also avoids engaging with cosmetic findings, deferring them as low-priority rather than making a fix/dismiss decision.

The fix requires changes to three context-layer files that define the review loop behavior:
- `.claude/agents/code-reviewer.md` -- finding categories and structured format
- `.claude/rules/dispatch-pattern.md` -- review routing and finding handling
- `.claude/skills/implement/SKILL.md` -- Phase 3 review step behavior

Additionally, the user suggests exploring whether Codex could be used conversationally (not just batch review) to discuss findings. This is speculative and needs a research spike before any planning.

**Expert consultation required**: claude-architect (context-layer changes affecting dispatch workflow). Consultation pending -- epic remains DRAFT.

## Goals
- Every review finding reaches a terminal state (FIXED or DISMISSED) during the story -- no deferral to epic History
- The main session actively triages ALL findings with the reviewer, not just MUST FIX items
- The code-reviewer's finding categories reflect the new resolution model
- Evaluate whether interactive Codex conversations are feasible for review discussions

## Non-Goals
- Changing the 2-round circuit breaker (that stays)
- Changing which findings are MUST FIX vs SHOULD FIX in the reviewer's rubric (the classification is unchanged -- what changes is how SHOULD FIX items are handled after classification)
- Changing the code-reviewer's adversarial stance or review procedure
- Implementing Codex interactive review (that depends on the research spike outcome)

## Success Criteria
- The dispatch-pattern, implement skill, and code-reviewer agent def all describe the same resolution-first model
- No mention of "record SHOULD FIX in epic History" or "defer" in any of the three files
- Every finding category has a clear path to a terminal state (FIXED or DISMISSED)
- The research spike produces a clear feasibility answer for interactive Codex review

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-096-R-01 | Research: Interactive Codex Review Conversation | TODO | None | - |
| E-096-01 | Revise code-reviewer finding categories and output format | TODO | None | - |
| E-096-02 | Update dispatch review loop in dispatch-pattern and implement skill | TODO | E-096-01 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### Current Behavior (What Changes)

**Code-reviewer** (`code-reviewer.md`):
- Findings classified as MUST FIX or SHOULD FIX
- MUST FIX: "blocks DONE"
- SHOULD FIX: "recommended, does not block DONE"
- Anti-pattern 6: "Never escalate a SHOULD FIX to MUST FIX between rounds"

**Dispatch-pattern** (`dispatch-pattern.md`), Step 6/7:
- APPROVED: "Any SHOULD FIX findings from the reviewer are recorded in the epic's History section during closure -- they are NOT relayed to the implementer."
- NOT APPROVED: "Route ONLY the MUST FIX findings to the implementer... Do NOT include SHOULD FIX items in the feedback to implementers."

**Implement skill** (`SKILL.md`), Phase 3 Step 5:
- Point 3: "SHOULD FIX -> epic History"
- Point 4: "Route ONLY the MUST FIX findings... Do NOT include SHOULD FIX items"
- Anti-pattern 10: "Do not relay SHOULD FIX findings to implementers."

### Target Behavior (What It Becomes)

The code-reviewer continues to classify findings as MUST FIX or SHOULD FIX -- the classification rubric is unchanged. What changes is what happens AFTER classification:

1. **MUST FIX findings**: Behavior unchanged. Routed to implementer. Must be fixed before DONE.

2. **SHOULD FIX findings**: The main session triages each one with the reviewer:
   - **AGREE (fix it)**: Route to implementer alongside MUST FIX items. Implementer fixes it.
   - **DISAGREE (dismiss it)**: Record a one-line dismissal reason. Finding is closed. Not recorded as deferred debt.

3. **No deferral category exists.** Every finding ends in one of three terminal states: FIXED, DISMISSED, or escalated to user (circuit breaker). There is no "record for later" path.

4. **The main session's triage role**: After receiving the reviewer's findings, the main session reads ALL findings (not just MUST FIX) and decides which SHOULD FIX items to accept vs dismiss. This is a judgment call -- the main session acts as the product voice, weighing the cost of fixing against the cost of dismissing. The triage adds a small amount of coordinator work per review but eliminates the deferred debt pattern entirely.

### Triage Heuristics for the Main Session

The main session should apply these heuristics when triaging SHOULD FIX items:

- **Convention alignment**: If a SHOULD FIX item moves code closer to documented conventions, accept it.
- **Small fix, clear value**: If the fix is a few lines and the improvement is obvious, accept it.
- **Subjective style preference**: If the reviewer and the codebase conventions don't mandate a particular style, dismiss it with reason.
- **Out-of-scope cleanup**: If the finding is about pre-existing code not modified by the story, dismiss it (scope guardrail applies).
- **When uncertain**: Accept it. The bias should be toward fixing, not deferring.

### Codex Interactive Review (Research)

The user suggested testing whether Codex can be used conversationally during review -- e.g., the main session asks Codex a question about a finding and gets a response, rather than running a batch review script. This is distinct from the existing `codex review` batch workflow. The research spike should determine:
1. Can `codex exec` or similar accept a question and return an answer interactively?
2. Is the response quality sufficient for nuanced review discussions?
3. What are the latency and cost implications?

This research is independent of the main stories -- the resolution-first model does not depend on Codex interactive review.

## Open Questions
- **CA consultation pending**: What is the right way to structure the triage step in the review loop? Should it be a new explicit step, or folded into the existing APPROVED/NOT APPROVED handling? CA should advise on the structural approach before stories are finalized.
- **Codex interactive feasibility**: Unknown until research spike completes. If feasible, a follow-up epic could integrate it.

## History
- 2026-03-11: Created. DRAFT pending claude-architect consultation on context-layer approach.
