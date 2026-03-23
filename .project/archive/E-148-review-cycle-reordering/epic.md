# E-148: Review Cycle Reordering for Plan and Implement Skills

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Reorder the review phases in both the plan and implement skills so that cheap, fast internal reviews (code-reviewer spec audit + holistic team review) run before expensive external reviews (Codex), and add atomic commit discipline so that ALL session artifacts (epic files, agent memory, vision signals) are captured in a single commit per workflow pass. E-147 demonstrated that internal reviews find more practical implementation issues (wrong function names, missing code paths, form flow gaps) while Codex finds rubric-level issues (AC testability, dependency declarations). Running internal reviews first cleans up mechanical and feasibility issues so Codex runs as a systematic final validation pass on an already-clean spec.

## Background & Context
During E-147 planning, the review process ran in the current order: Codex spec review first (2 iterations, 8 findings accepted), then code-reviewer and holistic team reviews (4 passes, 14 findings accepted), then a final Codex pass (4 findings, 2 dismissed). The internal reviews found different and often more practical issues than Codex -- wrong function signatures, missing API calls, inverted phase labels, form flow gaps. Codex found rubric-level issues like AC testability and dependency declarations.

The ordering is backwards. Internal reviews are fast (already-spawned agents, no external API call, no timeout risk) and catch the issues that make Codex findings noisy. Codex should run last as a systematic rubric-based validation on an already-clean spec.

The same principle applies to the implement skill's optional review chain: the code-reviewer integration review (fast, cross-story interactions) should run before the Codex code review (systematic rubric validation).

Architect consultation occurred for all three stories. The architect's pre-planning analysis (`.claude/agent-memory/claude-architect/review-cycle-reordering.md`) provides the approved direction and E-147 evidence for review reordering (E-148-01, E-148-02). The atomic session commit approach (E-148-03) was designed by the architect via live team consultation during epic expansion -- there is no pre-existing artifact for that design; the design is captured in TN-8 and TN-10.

## Goals
- Internal reviews (CR spec audit + holistic team review) run before Codex in the plan skill's review phases
- CR integration review runs before Codex code review in the implement skill's optional review chain
- Review scorecard table is recorded in epic History at both READY gate (planning) and closure (implementation) for convergence visibility
- User retains judgment over when to advance from internal review tier to Codex tier
- Both plan and implement skills have explicit commit steps that capture ALL session artifacts (epic files + agent memory + vision signals + research + ideas) rather than leaving ancillary files uncommitted

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
- Plan skill Phase 5 includes a new Step 2a (atomic planning commit) that stages all session artifacts per TN-8 and commits with user approval
- Implement skill Phase 5 includes a new Step 7a (ancillary file sweep) that commits main-checkout session artifacts before the closure merge, clearing the way for the clean-tree preflight
- Commit messages follow the convention in TN-10

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-148-01 | Restructure plan skill review phases | DONE | None | - |
| E-148-02 | Reorder implement skill review phases and add scorecard | DONE | E-148-01 | - |
| E-148-03 | Atomic session commits for plan and implement skills | DONE | E-148-01, E-148-02 | - |

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
- Phase 5 closure merge mechanics in the implement skill (Step 8 patch generation, dry-run, apply, user approval -- unchanged)
- Phase 5 archive commit in the implement skill (Step 11 -- unchanged)
- Phase 5 clean-tree preflight in the implement skill (Step 8 -- unchanged, serves as safety net after Step 7a sweep)

Note: Phase 5 compound dispatch handoff logic in the plan skill requires a minor update to handle CR already being on the team (spawned during Phase 3). This is not "unchanged" -- see E-148-01 AC-8. E-148-03 adds new steps (plan skill Step 2a, implement skill Step 7a) but does not modify existing steps.

### TN-8: Recognized Session Artifact Categories

Both skills produce artifacts beyond their primary outputs. These are the recognized path patterns for atomic commit steps.

**Planning commit (plan skill Step 2a) -- stages from main checkout:**
- `epics/E-NNN-slug/` (epic and story files)
- `.claude/agent-memory/` (all agent memory updates from the planning session)
- `docs/vision-signals.md` (if modified)
- `.project/research/E-NNN-*` (research artifacts, if any)
- `.project/ideas/` (if any ideas captured during session)

During planning, all agents work in the main checkout, so all session artifacts are here.

**Ancillary sweep (implement skill Step 7a) -- stages from main checkout:**
- `docs/vision-signals.md` (if captured by the main session during dispatch)
- `.claude/agent-memory/` (leftover planning artifacts not committed by Step 2a, if any)
- `.project/ideas/` (if any ideas captured by the main session during dispatch)

During dispatch, agents work in the epic worktree. Agent memory writes made by dispatch agents go to the worktree and are captured by the closure merge patch (Step 8). Step 7a only sweeps main-checkout changes -- typically vision signals from the main session or leftovers from prior sessions. Most dispatch runs will have a clean main checkout if the plan skill's Step 2a committed properly.

**Not staged by either step (separate existing commits):**
- Implementation code -- existing closure merge (Step 8, worktree patch, includes dispatch agent memory writes)
- Archive moves + PM dispatch memory update -- existing archive commit (Step 11)

**File enumeration (both steps):** Use `git status --porcelain` (without `-uall` per CLAUDE.md) for modified/staged files. For untracked files in mixed directories (e.g., `.claude/agent-memory/`), use `git ls-files --others --exclude-standard -- <path>` to enumerate individual files without the memory risks of `-uall`. This is scoped to specific recognized paths, not the whole repo.

**Staging precision (both steps):**
- **Wholly-owned directories** (`epics/E-NNN-slug/`, `.project/research/E-NNN-*`): `git add <directory>` is acceptable because the entire directory is a session artifact.
- **Mixed directories** (`.claude/agent-memory/`, `.project/ideas/`): Stage individual files only -- enumerate with `git ls-files --others --exclude-standard -- <path>` for untracked files, `git diff --name-only -- <path>` for modified files, then `git add` each matching file.
- **Single files** (`docs/vision-signals.md`): `git add <file>` directly.

**Classification (both steps):** Files matching recognized patterns are staged and committed. Files NOT matching any recognized pattern are reported to the user and the step waits for instructions -- preserving safety behavior against pre-existing dirty state or unrelated edits.

### TN-10: Commit Message Convention

| Workflow Gate | Commit Message | Scope |
|---|---|---|
| Plan READY gate (Step 2a) | `feat(E-NNN): plan <epic title> (READY)` | Epic files + all session artifacts |
| Implement pre-closure (Step 7a) | `chore(E-NNN): session artifacts` | Main checkout ancillary files only |
| Implement closure (Step 8) | `feat(E-NNN): <epic title>` | Implementation code (worktree patch) -- **existing, unchanged** |
| Implement archive (Step 11) | `chore(E-NNN): archive epic` | Archive move -- **existing, unchanged** |

The `feat` prefix for plan commits is intentional: creating the epic IS the feature deliverable of the planning workflow. The `chore` prefix for dispatch session artifacts is correct because they're housekeeping alongside the real deliverable (the implementation code).

## Open Questions
None -- direction approved by user, architect analysis comprehensive.

## History
- 2026-03-22: Created. Based on E-147 planning experience and architect analysis.
- 2026-03-22: Expanded with E-148-03 (atomic session commits). Architect designed the approach; PM framed ACs. Dependencies restructured to fully serial chain (01→02→03).
- 2026-03-22: READY. 11 review passes (6 internal iterations, 4 Codex iterations, 1 async Codex). 25 findings, 25 accepted, 0 dismissed.
- 2026-03-22: COMPLETED. All 3 stories implemented by claude-architect and verified by PM. Restructured plan skill review phases (internal review cycle before Codex), reordered implement skill review chain (CR integration before Codex), added review scorecard pattern to both skills, and added atomic session commit steps (plan Step 2a, implement Step 7a) to capture all session artifacts.

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Codex code review | 3 | 3 | 0 |
| **Total** | **3** | **3** | **0** |

All 3 stories were context-layer-only (skill files). Per-story code review was skipped; PM verified ACs alone. Post-implementation Codex code review found 3 P1 logic bugs (Step 7a/Step 8 revert regression, cr_spawned flag race, findings routing gap) -- all accepted and remediated.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic (PM + Architect) | 5 | 5 | 0 |
| Internal iteration 2 -- CR + Holistic | 0 | 0 | 0 |
| Codex iteration 1 | 3 | 3 | 0 |
| Internal iteration 3 -- CR + Holistic | 2 | 2 | 0 |
| Internal iteration 4 -- CR + Holistic | 0 | 0 | 0 |
| Codex iteration 2 | 5 | 5 | 0 |
| Internal iteration 5 -- CR + Holistic | 0 | 0 | 0 |
| Codex iteration 3 | 4 | 4 | 0 |
| Codex iteration 4 (async) | 2 | 2 | 0 |
| Internal iteration 6 -- CR + Holistic + SE | 0 | 0 | 0 |
| **Total** | **25** | **25** | **0** |
