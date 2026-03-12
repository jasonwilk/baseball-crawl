# E-096: Resolve All Review Findings During Stories

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Change the dispatch review loop so that every code-reviewer finding is resolved (fixed or dismissed) during the story, rather than deferring SHOULD FIX items to epic History. The current pattern creates a class of acknowledged-but-never-addressed debt. If a finding should be fixed, fix it before the story closes. If it should not be fixed, dismiss it with a reason. No limbo.

## Background & Context
User feedback (2026-03-11):

> "I don't want you to act on *all* feedback, but I think you don't act on enough. I see you deferring cosmetic changes, for instance. Or things that are already tracked as 'should fix'. If you're tracking them as 'should fix', then why aren't we fixing them in the first place? If it needs fixed, fix it before somebody points it out. It shouldn't make it through the story without being fixed if it's tracked and you think that it should be. And for cosmetic, why defer it? You either agree with it or you don't. If you agree with it, then fix it. If you don't agree with it...don't fix it. But don't defer it because it's superficial. Work with the reviewer to come to a resolution state and act on that state."

The current review loop has a structural flaw: the main session only relays MUST FIX findings to implementers and records SHOULD FIX findings in epic History for "later." In practice, "later" means "never" -- the SHOULD FIX items accumulate as acknowledged debt across every epic (see archived epics listing multiple SHOULD FIX items that were never addressed). The main session also avoids engaging with cosmetic findings, deferring them as low-priority rather than making a fix/dismiss decision.

The fix requires changes to four context-layer files that define the review loop behavior:
- `.claude/agents/code-reviewer.md` -- finding categories and structured format
- `.claude/rules/dispatch-pattern.md` -- review routing and finding handling
- `.claude/skills/implement/SKILL.md` -- Phase 3 review step behavior
- `CLAUDE.md` -- Agent Ecosystem code-reviewer description

Additionally, the user suggests exploring whether Codex could be used conversationally (not just batch review) to discuss findings. This is speculative and needs a research spike before any planning.

**Expert consultation complete**: claude-architect confirmed four-file scope, recommended folding triage into existing APPROVED/NOT APPROVED handling (no new step), and validated the structural approach.

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
- The dispatch-pattern, implement skill, code-reviewer agent def, and CLAUDE.md all describe the same resolution-first model
- No mention of "record SHOULD FIX in epic History" or "defer" in any of the four files
- Every finding category has a clear path to a terminal state (FIXED or DISMISSED)
- The research spike produces a clear feasibility answer for interactive Codex review

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-096-R-01 | Research: Interactive Codex Review Conversation | DONE | None | claude-architect |
| E-096-01 | Revise code-reviewer finding categories and output format | DONE | None | claude-architect |
| E-096-02 | Update dispatch review loop in dispatch-pattern and implement skill | DONE | E-096-01 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### Current Behavior (What Changes)

**Code-reviewer** (`code-reviewer.md`):
- Findings classified as MUST FIX or SHOULD FIX
- MUST FIX: "blocks DONE"
- SHOULD FIX: "recommended, does not block DONE"
- Anti-pattern 6: "Never escalate a SHOULD FIX to MUST FIX between rounds"

**Dispatch-pattern** (`dispatch-pattern.md`), Step 7:
- Describes routing MUST FIX items to the implementer but is silent on SHOULD FIX handling -- no explicit deferral or triage guidance exists. Needs a small addition for the triage step.

**Implement skill** (`SKILL.md`), Phase 3 Step 5:
- Point 3: "SHOULD FIX -> epic History"
- Point 4: "Route ONLY the MUST FIX findings... Do NOT include SHOULD FIX items"
- APPROVED path (line 214): "Any SHOULD FIX findings from the reviewer are recorded in the epic's History section during closure -- they are NOT relayed to the implementer."
- NOT APPROVED path (line 216): "Route ONLY the MUST FIX findings to the implementer... Do NOT include SHOULD FIX items in the feedback to implementers."
- Anti-pattern 10: "Do not relay SHOULD FIX findings to implementers."

**CLAUDE.md** (Agent Ecosystem section, line 450):
- "SHOULD FIX findings are recorded in epic History during closure, not relayed to implementers."

### Target Behavior (What It Becomes)

The code-reviewer continues to classify findings as MUST FIX or SHOULD FIX -- the classification rubric is unchanged. What changes is what happens AFTER classification:

1. **MUST FIX findings**: Behavior unchanged. Routed to implementer. Must be fixed before DONE.

2. **SHOULD FIX findings**: The main session triages each one with the reviewer:
   - **AGREE (fix it)**: Route to implementer alongside MUST FIX items. Implementer fixes it.
   - **DISAGREE (dismiss it)**: Record a one-line dismissal reason. Finding is closed. Not recorded as deferred debt.

3. **No deferral category exists.** Every finding ends in one of three terminal states: FIXED, DISMISSED, or escalated to user (circuit breaker). There is no "record for later" path.

4. **The main session's triage role**: After receiving the reviewer's findings, the main session reads ALL findings (not just MUST FIX) and decides which SHOULD FIX items to accept vs dismiss. This is a judgment call -- the main session acts as the product voice, weighing the cost of fixing against the cost of dismissing. The triage adds a small amount of coordinator work per review but eliminates the deferred debt pattern entirely.

### Triage Heuristics for the Main Session

- For each SHOULD FIX: if the main session agrees it improves the code, accept it (route to implementer). If not, dismiss with a one-line reason.
- When uncertain, accept -- bias toward fixing.
- Findings about pre-existing code not modified by the story should be dismissed (scope guardrail).

### Codex Interactive Review (Research)

The user suggested testing whether Codex can be used conversationally during review -- e.g., the main session asks Codex a question about a finding and gets a response, rather than running a batch review script. This is distinct from the existing `codex review` batch workflow. The research spike should determine:
1. Can `codex exec` or similar accept a question and return an answer interactively?
2. Is the response quality sufficient for nuanced review discussions?
3. What are the latency and cost implications?

This research is independent of the main stories -- the resolution-first model does not depend on Codex interactive review.

## Open Questions
- **Codex interactive feasibility**: Unknown until research spike completes. If feasible, a follow-up epic could integrate it.

### Resolved
- **Triage step structure** (resolved via CA consultation): Fold triage into the existing APPROVED/NOT APPROVED handling -- no new step number needed. After receiving findings, the main session triages ALL findings before any merge/status decisions.

## History
- 2026-03-11: Created. DRAFT pending claude-architect consultation on context-layer approach.
- 2026-03-11: Refinement session (PM, SE, CA). CA consultation complete. PM caught misattribution of SHOULD FIX deferral text to dispatch-pattern.md (actually in SKILL.md); SE verified line-by-line. Corrections: misattributions fixed, CLAUDE.md added as fourth target file, triage heuristics simplified, open question resolved (fold triage into existing APPROVED/NOT APPROVED handling). Set READY.
- 2026-03-12: Dispatch completed. All 3 stories DONE. E-096-01: Updated code-reviewer.md SHOULD FIX header and anti-pattern 6 to reflect resolution-first model. E-096-02: Updated dispatch-pattern.md (triage step in Step 7), implement SKILL.md (triage in Phase 3 Step 5, anti-pattern 10, workflow diagram), and CLAUDE.md (Agent Ecosystem description). E-096-R-01: Research spike found interactive Codex review is technically feasible (codex exec --ephemeral + resume pattern) but recommends DEFER -- integration not justified until resolution-first model is in production and real triage cases emerge. No documentation impact. Context-layer assessment: all changes were the epic's direct deliverables (context-layer files were the target), no additional codification needed.
