# E-148: Review Cycle Reordering for Plan and Implement Skills

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Reorder the review phases in both the plan and implement skills so that cheap, fast internal reviews (code-reviewer spec audit + holistic team review) run before expensive external reviews (Codex). E-147 demonstrated that internal reviews find more practical implementation issues (wrong function names, missing code paths, form flow gaps) while Codex finds rubric-level issues (AC testability, dependency declarations). Running internal reviews first cleans up mechanical and feasibility issues so Codex runs as a systematic final validation pass on an already-clean spec.

## Background & Context
During E-147 planning, the review process ran in the current order: Codex spec review first (2 iterations, 8 findings accepted), then code-reviewer and holistic team reviews (4 passes, 14 findings accepted), then a final Codex pass (4 findings, 2 dismissed). The internal reviews found different and often more practical issues than Codex -- wrong function signatures, missing API calls, inverted phase labels, form flow gaps. Codex found rubric-level issues like AC testability and dependency declarations.

The ordering is backwards. Internal reviews are fast (already-spawned agents, no external API call, no timeout risk) and catch the issues that make Codex findings noisy. Codex should run last as a systematic rubric-based validation on an already-clean spec.

The same principle applies to the implement skill's optional review chain: the code-reviewer integration review (fast, cross-story interactions) should run before the Codex code review (systematic rubric validation).

No expert consultation required -- this is a pure process/workflow change to context-layer files. The architect's analysis (`.claude/agent-memory/claude-architect/review-cycle-reordering.md`) provides the approved direction and E-147 evidence.

## Goals
- Internal reviews (CR spec audit + holistic team review) run before Codex in the plan skill's review phases
- CR integration review runs before Codex code review in the implement skill's optional review chain
- Review scorecard table is recorded in epic History at both READY gate (planning) and closure (implementation) for convergence visibility
- User retains judgment over when to advance from internal review tier to Codex tier

## Non-Goals
- Changes to the code-reviewer agent definition (spec review rubric is delivered via assignment message, not codified in the agent definition)
- Changes to per-story code review during dispatch (Phase 3 Step 5 of implement skill stays unchanged)
- Changes to the codex-spec-review or codex-review skills themselves
- Adding automated tier advancement gates (user judgment, not automatic)

## Success Criteria
- Plan skill Phase 3 is an internal review cycle (CR spec audit + holistic team review) with a 3-iteration circuit breaker
- Plan skill Phase 4 is a Codex validation pass with a 2-iteration circuit breaker
- User explicitly decides when to advance from Phase 3 to Phase 4
- Implement skill Phase 4a is CR integration review; Phase 4b is Codex code review (swapped from current)
- Review scorecard table appears in epic History at READY gate and at closure
- All existing edge cases (timeout, codex not installed, clean review, circuit breaker) are preserved

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-148-01 | Restructure plan skill review phases | TODO | None | - |
| E-148-02 | Reorder implement skill review phases and add scorecard | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: E-147 Evidence

| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex iteration 1 | 5 | 5 | 0 |
| Codex iteration 2 | 3 | 3 | 0 |
| Code-reviewer pass 1 | 4 | 4 | 0 |
| Holistic team review 1 | 6 | 6 | 0 |
| Code-reviewer pass 2 | 2 | 2 | 0 |
| Holistic team review 2 | 2 | 2 | 0 |
| Codex iteration 3 | 4 | 2 | 2 |
| **Total** | **26** | **24** | **2** |

Key insight: CR and team reviews found different (often more practical) issues than Codex. Internal reviews should clean up mechanical issues before Codex runs its systematic rubric pass.

### TN-2: Internal Review Cycle Mechanism (Plan Skill Phase 3)

The internal review cycle has two sub-passes per iteration:

**Sub-pass A -- CR spec audit**: The main session spawns a code-reviewer (if not already spawned) and sends it the epic directory for spec-focused review. The assignment message provides spec-review criteria (not the code-focused rubric from the CR agent definition). Criteria for spec audit: AC testability and specificity, dependency correctness (file conflicts, missing deps), story sizing, Technical Notes completeness, file ownership conflicts between stories, interface definitions for inter-story dependencies.

**Sub-pass B -- Holistic team review**: The main session sends the epic to each planning team agent (PM and domain experts already spawned in Phase 0) asking each to review from their domain perspective. Examples: baseball-coach reviews coaching data accuracy, data-engineer reviews schema feasibility, software-engineer reviews implementation feasibility. PM collects feedback from all reviewers, triages, and reports back.

Both sub-passes run within each iteration. PM triages findings from both, incorporates accepted findings, runs consistency sweep. The iteration loop is: review → triage → incorporate → consistency sweep → user decides (another iteration or advance to Codex).

### TN-3: Tier Advancement

Phase 3 (internal) and Phase 4 (Codex) are separate phases with an explicit user decision point between them. After each Phase 3 iteration, the user sees options:
- (a) Run another internal review iteration (if circuit breaker not reached)
- (b) Advance to Codex validation (Phase 4)
- (c) Proceed directly to READY (Phase 5) -- skip Codex entirely

This is a judgment call. The user advances when internal findings have quieted down. There is no automatic gate.

### TN-4: Circuit Breakers

**Plan skill**:
- Phase 3 (internal): 3 iterations max. If 3rd iteration still has findings, user chooses: fix and mark READY, advance to Codex (Phase 4), continue (reset), or leave as DRAFT.
- Phase 4 (Codex): 2 iterations max. Same circuit breaker options as current Phase 3.

**Implement skill**:
- Phase 4a (CR integration): 2 rounds max (unchanged from current Phase 4b).
- Phase 4b (Codex code review): 2 rounds max (unchanged from current Phase 4a).

### TN-5: Review Scorecard Format

Recorded in epic History at READY gate and at closure:

```
### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | N | N | N |
| Internal iteration 1 -- Holistic team | N | N | N |
| Internal iteration 2 -- CR spec audit | N | N | N |
| Codex iteration 1 | N | N | N |
| **Total** | **N** | **N** | **N** |
```

**Implementation scorecard** (at closure):

```
### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-NNN-01 | N | N | N |
| Per-story CR -- E-NNN-02 | N | N | N |
| CR integration review | N | N | N |
| Codex code review | N | N | N |
| **Total** | **N** | **N** | **N** |
```

Per-story CR rows show aggregated finding totals across all review rounds for that story (e.g., if round 1 had 3 MUST FIX and round 2 had 1, the row shows 4 findings total). Phase 4a/4b rows show findings from integration and Codex reviews respectively.

Only rows for review passes that actually ran are included. If Codex was skipped, no Codex rows appear.

PM reconstructs the scorecard from triage summaries at the gate (READY or closure). No running counters are needed during iterations -- the triage summary from each iteration (planning) or each story's review loop (implementation) contains the finding counts.

### TN-6: Existing Edge Cases to Preserve

All existing edge cases from the current plan and implement skills must be preserved in the restructured phases:
- Codex timeout (exit 124) → prompt-generation fallback
- Codex not installed → prompt-generation fallback or skip
- Clean review (no findings) → skip refinement, advance. For Phase 3: a clean internal iteration still presents tier advancement options (user may want another round, advance to Codex, or proceed to READY)
- Circuit breaker firing → user decides
- User pastes async findings → enter triage
- No uncommitted changes for review (implement skill) → skip
- PM-only planning team (no domain experts beyond PM): Sub-pass B (holistic team review) degrades to PM self-review -- PM reviews from its own perspective without broadcasting. Sub-pass A (CR spec audit) runs normally.
- CR spawn failure during Phase 3: Escalate to user with options -- (a) retry spawn, (b) skip CR sub-pass for this iteration (holistic team review only), (c) abort internal review and advance to Codex or READY.

### TN-7: What Does NOT Change

- Phase 0 (Team Formation), Phase 1 (Discovery), Phase 2 (Planning) in the plan skill
- Per-story code review in Phase 3 Step 5 of the implement skill
- The codex-spec-review and codex-review skills themselves
- The code-reviewer agent definition
- Phase 5 closure sequence in the implement skill (except adding scorecard)

Note: Phase 5 compound dispatch handoff logic in the plan skill requires a minor update to handle CR already being on the team (spawned during Phase 3). This is not "unchanged" -- see E-148-01 AC-8.

## Open Questions
None -- direction approved by user, architect analysis comprehensive.

## History
- 2026-03-22: Created. Based on E-147 planning experience and architect analysis.
- 2026-03-22: READY. 2 review rounds (1 internal, 1 Codex). 12 findings, 12 accepted, 0 dismissed.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR + Holistic | 9 | 9 | 0 |
| Internal iteration 2 -- CR + Holistic | 0 | 0 | 0 |
| Codex iteration 1 | 3 | 3 | 0 |
| **Total** | **12** | **12** | **0** |
