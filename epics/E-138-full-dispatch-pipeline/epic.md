# E-138: Full Dispatch Pipeline

## Status
`DRAFT`

## Overview
Automate the full post-dispatch pipeline — codex review, code-reviewer integration review, remediation, and commit — into a single "and review" modifier on the dispatch trigger. Today this requires 4+ manual interactions; the pipeline absorbs them all while gracefully degrading when the diff is too large for headless codex review.

## Background & Context
Jason's current workflow after dispatch completes:

```
[All stories DONE]
  → manually invoke "codex review"
  → read findings, decide on remediation
  → manually invoke code-reviewer
  → read findings, remediate
  → manually invoke "commit"
```

His desired workflow:

```
"implement E-NNN and review"
  → [everything happens automatically]
  → approve commit
```

The "and review" modifier exists in the implement skill (Phase 4) but currently only chains codex-review. Jason has never used it — his pattern is explicit separate interactions. This epic deepens "and review" to mean the full pipeline, making it worth using.

Key constraint from Jason: "it will only flow smoothly if the changes are small enough for codex to review without timing out. Otherwise we have to revert to a codex prompt that I can run async." This requires a graceful degradation path: headless → timeout/too-large → generate prompt → pause → user pastes findings → resume.

Also incorporates Jason's triage feedback (implemented in E-137): all real findings get fixed. No dismiss track for real issues.

Expert consultation: claude-architect (skill architecture), software-engineer (script changes), product-manager (pipeline UX).

Depends on E-137 (epic-level worktree isolation) for clean epic-scoped diffs.

## Goals
- "and review" triggers the full pipeline: codex review → remediate → code-reviewer integration review → remediate → commit
- Graceful degradation when codex review times out or diff is too large
- Post-epic code-reviewer integration review catches cross-story issues that per-story CR misses
- Operator approves commit at the end — no automatic commits
- Pipeline runs within a single session with no persistent state requirements

## Non-Goals
- New trigger phrases or modifiers (deepening "and review" only)
- Changes to per-story code review during dispatch (Phase 3 — unchanged)
- Parallel epic dispatch automation
- Codex installation, configuration, or version management

## Success Criteria
- "implement E-NNN and review" produces a reviewed, remediated, operator-approved commit without manual intermediate steps
- When codex times out, the operator receives a prompt to run async and can resume the pipeline by pasting findings
- The code-reviewer integration pass reviews the full epic diff (not individual story diffs)
- The commit contains exactly the epic's changes (via E-137's epic worktree). Note: context-layer-only stories (per E-137 TN-5) are committed separately after the epic commit. The pipeline reviews and commits the epic worktree diff; context-layer changes follow the E-137 commit ordering contract.

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-138-01 | Codex review with graceful degradation | TODO | None (E-137 is epic-level dep) | - |
| E-138-02 | Post-codex code-reviewer integration pass | TODO | E-138-01 | - |
| E-138-03 | Automated commit gate | TODO | E-138-02 | - |

## Dispatch Team
- claude-architect

## Technical Notes

### TN-1: Pipeline Flow
The full "and review" pipeline replaces the current Phase 4 and modifies Phase 5:

```
All stories DONE (Phase 3 complete)
  │
  ▼
Phase 4a: Codex Review
  ├── Headless attempt (invoke codex-review.sh --workdir <epic-worktree>)
  │     ├── Success + findings → triage + remediate
  │     ├── Success + clean → skip to Phase 4b
  │     └── Timeout (exit 124) or failure → fall to prompt path
  └── Prompt path (graceful degradation)
        ├── Generate codex review prompt with epic-worktree diff
        ├── Present to user: "Pipeline paused. Run this prompt async, paste findings when ready (or 'skip')."
        ├── Wait for user input
        └── Resume: triage + remediate (or skip)
  │
  ▼
Phase 4b: Code-Reviewer Integration Review (NEW)
  ├── Route full epic diff to code-reviewer
  ├── CR reviews integrated changes for cross-story issues
  ├── Findings → remediate via implementer (2-round circuit breaker)
  └── Clean → proceed
  │
  ▼
Phase 5: Closure (modified)
  ├── Epic worktree → main merge (from E-137)
  ├── PII scan
  ├── Present commit summary
  ├── User approval
  └── Atomic commit
```

### TN-2: Graceful Degradation Mechanics
The codex-review script already has a 10-minute timeout (exit code 124). Rather than pre-measuring diff size, the pipeline tries headless first and falls to prompt-generation on timeout or error. This is simpler than a size-based branch and handles edge cases (codex API outages, rate limits) automatically.

The "pause" is simply waiting for user input — the session context holds the pipeline position. No persistent state, no resume tokens, no external state files.

When the user returns with findings, they paste the codex output. The pipeline parses it using the same format as headless output and resumes the triage/remediation flow.

"Skip" is a valid input that advances the pipeline to Phase 4b without codex findings.

### TN-3: Integration Review vs. Story Review
Per-story CR (Phase 3) reviews each story's changes in isolation — it catches story-level bugs, AC violations, and code quality issues. The integration review (Phase 4b) reviews the FULL epic diff — it catches cross-story interactions, naming inconsistencies, import conflicts, and architectural issues that only appear when stories are combined.

The code-reviewer's context block for integration review includes:
- The full epic diff (`git diff main` from the epic worktree)
- A story manifest: list of story IDs and titles with brief descriptions of what each did
- The epic's Technical Notes
- The epic's Goals and Success Criteria sections (for epic-level verification)

For large epics (8+ stories), the diff may exceed the CR's context window. The skill handles this by organizing the diff summary by story and letting the CR request specific file contents.

### TN-4: Circuit Breaker
Both codex remediation (Phase 4a) and CR remediation (Phase 4b) use the 2-round circuit breaker. If round 2 still has MUST FIX findings, escalate to the user with the standard options (fix, retry, override, abandon).

### TN-5: Remediation Authorization
Both codex and CR remediation are authorized by the post-review remediation exception in `workflow-discipline.md`'s Work Authorization Gate. No new authorization model needed.

### TN-6: Codex Prompt Bug Fix
The current codex-review prompt references the rubric by file path (`Rubric: /workspaces/baseball-crawl/.project/codex-review.md`) and expects codex to read it via repository access. When codex runs in `--ephemeral` mode, it may not have file access. The prompt should include an explicit instruction for codex to read the file, or the script should embed the rubric content directly. This fix is folded into E-138-01.

### TN-7: Epic-Level Dependency
This epic depends on E-137 (epic-level worktree isolation). All diffs are generated from the epic worktree. If E-137 is not complete, the pipeline falls back to the contaminated main checkout behavior — which defeats the purpose. E-137 must be dispatched and committed before E-138.

## Open Questions
- None remaining (resolved during consultation).

## History
- 2026-03-19: Created during parallel-epic-design consultation team. PM, CA, SE contributed analysis. User validated two-epic plan (E-137 infrastructure, E-138 pipeline).
