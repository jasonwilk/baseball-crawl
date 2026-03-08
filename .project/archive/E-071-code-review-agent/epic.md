# E-071: Code Review Agent

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add a dedicated code-reviewer agent to the dispatch workflow that automatically reviews every implementer's work before stories are marked DONE. The reviewer operates in a loop: implementer completes -> reviewer examines changes against ACs + conventions + rubric -> findings routed back to implementer -> fixes applied -> reviewer re-reviews -> until clean or circuit breaker triggers. This replaces the main session's rubber-stamp AC verification with adversarial code review as the quality gate.

## Background & Context
E-064 exposed a recurring pattern: implementing agents mark stories DONE, the main session rubber-stamps verification, and subtle misses linger until an external review (codex or manual) catches them. Specific pain points from E-064-01:

1. `DATABASE_PATH` was still cwd-relative (violating AC-4) -- passed 21 ACs, 125+ tests, marked DONE
2. `.parent.parent.parent` used instead of `.parents[N]` convention -- pre-existing pattern not caught
3. `_check_single_profile` alias retained instead of public `check_single_profile` -- fragile coupling persisted
4. Bare `print()` in dry-run paths -- convention violation lingered
5. Smoke test only covered `bb --help`, not real subcommands -- test coverage gap

All of these were found by codex review or manual review AFTER the story was marked DONE. The current workflow has no per-story quality gate between implementer completion and DONE status.

**Expert consultation**: Claude-architect consulted (2026-03-07). Recommended: new first-class agent (sonnet), persistent reviewer per epic, embedded rubric, structured findings format, circuit breaker at 2 rounds, Read/Glob/Grep/Bash only (no Write/Edit). Full assessment in Technical Notes.

## Goals
- Every implementer's work is reviewed by a dedicated code-reviewer agent before the story is marked DONE
- The reviewer verifies both acceptance criteria satisfaction AND code quality/convention compliance
- The review loop operates automatically within the dispatch workflow (not user-triggered)
- A circuit breaker prevents infinite review loops (max 2 rounds, then escalate to user)

## Non-Goals
- Replacing the existing codex review (Phase 4 "and review" modifier) -- it stays as Layer 2 defense in depth
- Replacing the review-epic skill -- it stays for post-epic manual reviews
- Having the reviewer write code or fix issues -- it finds, implementer fixes
- Reviewing context-layer-only stories (pure `.claude/rules/` or agent def edits with no code)

## Success Criteria
- A new code-reviewer agent definition exists with embedded rubric
- The implement skill's dispatch flow includes the review loop between implementer completion and DONE
- dispatch-pattern.md documents the review step and the code-reviewer role
- CLAUDE.md Agent Ecosystem table includes code-reviewer
- The agent has Read/Glob/Grep/Bash tools only (no Write/Edit)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-071-01 | Create code-reviewer agent definition | DONE | None | claude-architect |
| E-071-02 | Integrate review loop into dispatch workflow | DONE | E-071-01 | claude-architect |

## Dispatch Team
- claude-architect

## Technical Notes

### CA Assessment (2026-03-07)

**Architecture**: New first-class agent at `.claude/agents/code-reviewer.md`. Sonnet-class model. Separation of concerns is the design driver -- reviewer must have an adversarial/skeptical stance distinct from the implementer's constructive stance. Cost is bounded because sonnet doing focused reads, not opus deep reasoning.

**Dispatch flow insertion**: Between implementer completion and DONE status. Currently (implement SKILL.md Phase 3 Step 5): implementer reports completion -> main session verifies ACs -> marks DONE. New flow: implementer reports completion -> main session sends work to code-reviewer -> reviewer examines -> findings or approval -> if findings: route to implementer, loop -> when approved: main session marks DONE.

**Reviewer scope**: Verifies BOTH code quality AND acceptance criteria. Replaces the main session's rubber-stamp AC verification. Main session still does mechanical status updates.

**Persistence model**: One persistent reviewer per epic. Spawned at team creation alongside implementers. Stays for the duration of the epic. Every story gets reviewed. Per-story spawn is wasteful; complexity threshold reintroduces the rubber-stamp problem.

**Tools**: Read, Glob, Grep, Bash only. NO Write/Edit. The reviewer finds issues; the implementer fixes them. This enforces separation of concerns.

**Circuit breaker**: Max 2 review rounds per story. If the 2nd review still has MUST FIX findings, escalate to user with the findings summary. Do not loop indefinitely.

**Structured findings format** (CA-recommended):

```
## Review: E-NNN-SS [Story Title]

### MUST FIX (blocks DONE)
- [file:line] Description of issue. Why it matters.

### SHOULD FIX (recommended, does not block DONE)
- [file:line] Description of issue.

### AC VERIFICATION
- [ ] AC-1: [verdict] [evidence]
- [ ] AC-2: [verdict] [evidence]
...

### APPROVED / NOT APPROVED
[verdict with summary]
```

**Two-layer defense in depth** (CA-confirmed):
- Layer 1 (NEW): In-dispatch code review -- per-story, before DONE, code-reviewer agent (sonnet, fast, automatic)
- Layer 2 (EXISTING): Post-epic codex review -- after all stories DONE, before closure, codex external tool (optional, user-triggered via "and review")
- Both stay. review-epic skill and "and review" modifier unchanged.

### Review Rubric Priorities (embedded in agent def)

Incorporates the existing codex review rubric priorities plus project conventions:

1. **AC verification** -- does the code satisfy every acceptance criterion? Check each one explicitly.
2. **Bugs and regressions** -- logic errors, off-by-ones, wrong defaults, silent failures
3. **Missing or inadequate tests** -- untested code paths, tests that don't actually verify the AC they claim to
4. **Credential and security risks** -- credentials in code/logs/test fixtures, SQL injection, insecure defaults
5. **Schema drift** -- database writes that don't match current migration state
6. **Convention violations** -- CLAUDE.md style rules, `.claude/rules/python-style.md`, `.claude/rules/testing.md`, import boundaries, path conventions
7. **Planning/implementation mismatch** -- code that contradicts epic Technical Notes or deviates from the story's described approach

### Files to Change

| File | Change |
|------|--------|
| `.claude/agents/code-reviewer.md` | NEW -- agent definition with embedded rubric |
| `.claude/agents/claude-architect.md` | Update valid color enum (add `magenta`), update agent count ("eight" -> "nine") |
| `.claude/skills/implement/SKILL.md` | Modify Phase 2 (spawn reviewer) + Phase 3 Step 5 (review loop) |
| `.claude/rules/dispatch-pattern.md` | Add code-reviewer to routing table, document review loop in dispatch flow |
| `.claude/rules/workflow-discipline.md` | Update Workflow Routing Rule to reflect reviewer role in AC verification |
| `CLAUDE.md` | Add code-reviewer to Agent Ecosystem table + How Agents Collaborate |

### Interaction with Existing Dispatch Team Metadata

The code-reviewer is NOT listed in epics' Dispatch Team sections. It is automatically spawned for every dispatch that includes implementing agents. The implement skill handles this -- the Dispatch Team section lists only implementers and domain experts.

### Design Decisions (Refinement 2026-03-08)

**D1 -- Files-changed mechanism**: Implementers include a `## Files Changed` section in their completion SendMessage (absolute paths, with `modified`/`new`/`deleted`/`renamed` annotations). This is the primary scope for review. The reviewer cross-references against the story's "Files to Create or Modify" section to flag missing or unexpected files. `git diff --name-only` is advisory context only -- it is repo-wide and may include changes from parallel stories or miss untracked new files, so it cannot serve as a per-story scope tool. The implement SKILL.md must include a completion report template specifying this format.

**D2 -- SHOULD FIX routing**: SHOULD FIX findings go to epic History during closure only. They are never relayed to implementers during the fix loop. The fix loop is exclusively for MUST FIX items. Guardrail: if a finding violates a documented convention (CLAUDE.md, python-style.md, testing.md), the reviewer must classify it as MUST FIX, not SHOULD FIX. SHOULD FIX is reserved for genuinely optional improvements. SHOULD FIX findings cannot be escalated to MUST FIX between rounds unless new evidence emerges in the implementer's fix attempt.

**D3 -- Test execution**: Required, not optional. The reviewer runs `pytest` as step 1 before reading changed files. Test failures are automatic MUST FIX findings -- no judgment call needed. The reviewer does NOT debug failures; it flags them with the test name and failure output. For large test suites, the reviewer may target changed modules first (`pytest tests/test_<module>.py`), but defaults to running all tests.

### Context Window Mitigation

Each review assignment is self-contained. The reviewer does not retain findings from previous reviews in context. It reads the story file and changed files fresh for every assignment. If the reviewer's context window fills on a large epic (8+ stories), the main session may shut down and respawn the reviewer -- no state is lost because reviews are independent.

### Context-Layer-Only Story Skip

Stories that modify ONLY context-layer files (`.claude/agents/`, `.claude/rules/`, `.claude/skills/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/agent-memory/`, `CLAUDE.md`) and no Python code are skipped by the reviewer. The main session marks these stories DONE directly after verifying acceptance criteria itself. The reviewer is a code quality gate -- context-layer edits are reviewed by the architect's own expertise.

## Open Questions
- None

## History
- 2026-03-08: COMPLETED. Both stories implemented by claude-architect. E-071-01: created code-reviewer agent definition at `.claude/agents/code-reviewer.md` with embedded rubric, adversarial stance, structured findings format, circuit breaker, and Read/Glob/Grep/Bash tool restriction. E-071-02: integrated review loop into implement SKILL.md (Phase 2 spawn, Phase 3 review loop, Phase 5 simplified validation, anti-patterns), dispatch-pattern.md (three-role team, updated flow, routing table), workflow-discipline.md (reviewer-based AC verification), CLAUDE.md (ecosystem table, collaboration section), and claude-architect.md (nine agents). Both stories context-layer-only; main session verified ACs directly. No documentation impact. Context-layer assessment: this epic IS the context-layer change -- all artifacts are already codified.
- 2026-03-08: Codex spec review triage (6 findings: 3 P1, 3 P2). Refined 5, dismissed 1. Key changes: (1) Files Changed format expanded with `(deleted)` and `(renamed)` annotations. (2) Circuit breaker "accept the risk" reframed as explicit user override to resolve contradiction with anti-patterns. (3) Added workflow-discipline.md and claude-architect.md to E-071-02 scope (hidden file dependencies). (4) git diff demoted from per-story backstop to advisory context -- implementer's Files Changed + story's Files to Create or Modify is the primary scope mechanism. (5) `white` color enum addition scoped to E-071-01. (6) Dismissed docs/UX review path finding -- context-layer skip condition covers non-code stories adequately.
- 2026-03-08: Refinement complete. Three design decisions resolved (D1: dual files-changed mechanism, D2: SHOULD FIX to History only, D3: pytest required). Context window mitigation and context-layer skip condition added. Stories updated with all findings from CA/PM/SE review.
- 2026-03-07: Created. CA consulted: new first-class agent (sonnet), persistent per-epic, embedded rubric, circuit breaker, Read/Glob/Grep/Bash only.
