# E-034: Codex Review Integration

## Status
`COMPLETED`

## Overview
Add two lightweight, repeatable workflows for invoking OpenAI Codex as a review assistant inside this repo: (1) code review of repository changes, and (2) spec review of PM-authored epics and stories before marking them READY. Checked-in rubrics and thin shell wrappers give developers and agents a one-command path to project-aware Codex review, without creating a second source of truth or a drifting context layer.

## Background & Context
Codex is already installed in the devcontainer (`npm i -g @openai/codex` via postCreateCommand). The `codex review` CLI supports reviewing uncommitted changes, branch diffs, and individual commits. What was missing was a stable review rubric and wrapper.

During refinement, the scope broadened to include a second review lane: spec review of planning artifacts. The PM frequently authors epics and stories that benefit from external review before the READY gate -- checking for ambiguous ACs, dependency errors, file conflicts, sizing problems, and routing mistakes. This is a distinct review type from code review (different evaluation criteria, different invocation pattern, different CLI mode).

**Expert consultation:** claude-architect consulted (2026-03-03). Recommendations:
- Two separate rubrics (code vs. spec) -- different evaluation criteria should not be conflated.
- Two separate helper scripts -- different CLI modes (`codex review` for diffs, `codex exec` or equivalent for directory-based spec analysis).
- Runtime context injection correctly rejected for code review, intentionally relaxed for spec review (PM provides a small ephemeral note about intent/uncertainties).
- PM workflow integration belongs in `product-manager.md` as an optional refinement step, not a mandatory gate.
- CLAUDE.md documents only the user-facing commands.
- No skill file needed -- rubric + script + a few PM workflow lines is simpler and sufficient.
- `context-fundamentals` skill was consulted to verify the stable-vs-ephemeral split: rubrics are stable repo-owned context; the PM's runtime note is ephemeral one-shot context assembled at invocation time.

## Goals
- A single command (`scripts/codex-review.sh`) invokes Codex code review with a stable, project-aware rubric
- A single command (`scripts/codex-spec-review.sh`) invokes Codex spec review on an epic directory with a stable, planning-focused rubric
- Both rubrics are checked into the repo so they are versioned, reviewable, and shared
- Model selection is delegated to the user's Codex configuration (no model names in repo files)
- The code-review workflow supports three review scopes: uncommitted changes, branch diff, and single commit
- The spec-review workflow accepts an epic directory path and an optional runtime note
- The PM workflow includes an optional Codex spec-review step before setting an epic to READY

## Non-Goals
- No Codex-specific Claude skill (rubric + script is sufficient)
- No Codex memory system or evolving project worldview
- No model names hard-coded in rubrics or scripts
- No application code changes
- No automated integration into pre-commit hooks or CI (can be added later if needed)
- No mandatory gate -- spec review is optional, not required before READY
- No persistent Codex context or multi-turn review sessions

## Success Criteria
1. Running `scripts/codex-review.sh uncommitted` invokes `codex review` with the code-review rubric as instructions
2. Running `scripts/codex-review.sh base main` invokes `codex review` for a branch diff
3. Running `scripts/codex-review.sh commit <sha>` invokes `codex review` for a specific commit
4. The code-review rubric is version-controlled at `.project/codex-review.md`
5. Running `scripts/codex-spec-review.sh /path/to/epic/dir` invokes Codex with the spec-review rubric and the target epic's planning artifacts
6. The spec-review rubric is version-controlled at `.project/codex-spec-review.md`
7. The spec-review helper supports an optional runtime note for PM context handoff
8. CLAUDE.md's Commands section references both review scripts
9. The PM agent definition includes an optional Codex spec-review step in its refinement workflow
10. No model names appear in any rubric or script

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-034-01 | Create code-review rubric and shell wrapper | DONE | None | general-dev |
| E-034-02 | Add CLAUDE.md Commands entries for Codex review | DONE | E-034-01, E-034-03 | claude-architect |
| E-034-03 | Create spec-review rubric and shell wrapper | DONE | None | general-dev |
| E-034-04 | Integrate optional Codex spec-review step into PM workflow | DONE | E-034-03 | claude-architect |

## Technical Notes

### Lane A: Code Review (E-034-01, unchanged from original design)

#### Codex CLI Invocation
The `codex review` command is provided by the `@openai/codex` npm package, already installed in the devcontainer. Suggested invocation patterns:
- `codex review --uncommitted` -- review uncommitted changes
- `codex review --base <branch>` -- review diff against a base branch
- `codex review --commit <sha>` -- review a specific commit

**Important:** The implementing agent MUST verify the actual `codex review` CLI syntax at implementation time by running `codex review --help` or equivalent. The flags above come from Codex's own recommendation but have not been verified against the installed CLI version. If the actual flags differ, adapt the script accordingly.

#### Code-Review Rubric Content Principles
The rubric should:
1. Tell Codex to read `CLAUDE.md` first for project conventions
2. Tell Codex to read story/epic files when reviewing story-tied changes
3. Prioritize: bugs, regressions, missing tests, security/credential risks, schema drift, implementation vs. planning doc mismatch
4. Be concise and actionable -- no verbose prose
5. Require explicit "no findings" statement when the review is clean

#### Runtime Context for Code Review
No runtime context injection. The rubric tells Codex to read CLAUDE.md and story files itself. This keeps the code-review path simple and self-contained.

### Lane B: Spec Review (E-034-03, new)

#### Spec-Review CLI Mode
Spec review is NOT a diff-centric operation -- it reviews planning artifacts (epic and story markdown files) against project workflow contracts. The implementing agent MUST verify the actual installed Codex CLI to determine the correct invocation for this use case. Likely candidates:
- `codex exec` with a prompt that includes the rubric + file contents
- `codex` with appropriate flags for non-diff review

The implementing agent should run `codex --help` and explore available subcommands to find the best fit. If no non-diff mode exists, the helper should assemble a prompt and pipe it to the most appropriate Codex CLI entry point.

#### Spec-Review Rubric Content Principles
The spec-review rubric evaluates planning quality, not code quality. It should instruct Codex to check for:
1. Ambiguous or untestable acceptance criteria
2. Missing dependencies or incorrect sequencing
3. File conflicts that invalidate "parallel-safe" claims
4. Stories that are too large or not vertically sliced
5. Mismatched agent routing (context-layer files routed to wrong agent type)
6. Mismatch between epic claims and current repo reality
7. Missing expert consultation where PM workflow would normally require it
8. Unclear Definition of Done for implementing agents
9. Weak distinction between implemented reality and planned future state
10. Explicit "no findings" statement when the spec is clean

The rubric should tell Codex to read `CLAUDE.md`, `/.claude/rules/workflow-discipline.md`, `/.claude/rules/dispatch-pattern.md`, and the PM agent definition at `/.claude/agents/product-manager.md` for project workflow context.

#### Runtime Context for Spec Review
Unlike code review, spec review benefits from a small ephemeral runtime note from the PM. The helper script accepts an optional `--note` flag (or reads from a file path) containing:
- What the epic is trying to accomplish (one sentence)
- What changed in the latest draft (if applicable)
- What the PM is unsure about or wants Codex to focus on

This note is assembled at invocation time and included in the Codex prompt. It is NOT persisted -- no Codex memory system, no accumulating context files.

#### How the PM Uses Spec Review
The PM cannot run scripts directly (no Bash tool). During epic refinement, the PM may request a Codex spec review by dispatching to a `general-dev` agent with:
1. The target epic directory path
2. An optional short note summarizing intent and uncertainties
The `general-dev` agent runs the helper, returns the Codex output, and the PM incorporates findings into the epic before setting READY.

### Lane C: Workflow Integration (E-034-04, new)

#### PM Agent Definition Change
Add an optional step to the PM's refinement workflow in `/.claude/agents/product-manager.md`. The addition should be minimal -- a few lines noting that before setting an epic to READY, the PM may optionally request a Codex spec review. This is NOT a mandatory gate. The PM decides when it is useful.

Placement: In or near the "Quality Checklist" section, as an optional final step before setting READY.

#### CLAUDE.md Change (E-034-02)
Add entries to the Commands section for both `scripts/codex-review.sh` and `scripts/codex-spec-review.sh`. Follow the existing style (one-line descriptions). Do not document the PM workflow in CLAUDE.md -- that belongs in the PM agent definition.

### Model Selection
Model selection is explicitly NOT part of any rubric or script. The user's local Codex configuration handles model choice. No model names in repo files.

### File Organization
- Code-review rubric: `.project/codex-review.md`
- Spec-review rubric: `.project/codex-spec-review.md`
- Code-review script: `scripts/codex-review.sh`
- Spec-review script: `scripts/codex-spec-review.sh`

### What Was Accepted, Modified, and Rejected from Codex Input
- **Accepted:** Two-lane design (code review + spec review), separate rubrics, separate helpers, ephemeral runtime note for spec review, `.project/` location for rubrics, `scripts/` location for helpers, model-agnostic design, optional (not mandatory) PM workflow step
- **Modified:** Removed runtime context injection for code review only (kept for spec review where it is justified). E-034-02 now depends on both E-034-01 and E-034-03 to document implemented reality.
- **Rejected:** Codex-specific Claude skill (unnecessary layer), Codex memory system (violates core principle), mandatory gate (too heavy for current project scale)

## Open Questions
- None. The two-lane design is well-defined and each story is self-contained.

## History
- 2026-03-03: Created. Design input from Codex evaluated against project principles. Accepted core shape (rubric + wrapper), rejected skill and memory system. Two stories, parallel-safe.
- 2026-03-03: Refined. Broadened scope to include spec review of planning artifacts. Added two new stories (E-034-03 for spec-review rubric + helper, E-034-04 for PM workflow integration). Revised E-034-02 to depend on both implementation stories. claude-architect consulted; context-fundamentals skill consulted for stable-vs-ephemeral split. Epic remains READY -- all stories have testable ACs and no open design questions.
- 2026-03-03: Dispatch started. E-034-01 and E-034-03 dispatched in parallel (no file conflicts). E-034-02 and E-034-04 remain TODO pending dependencies.
- 2026-03-03: COMPLETED. All 4 stories verified DONE. Artifacts: `.project/codex-review.md` (code-review rubric), `scripts/codex-review.sh` (code-review wrapper), `.project/codex-spec-review.md` (spec-review rubric), `scripts/codex-spec-review.sh` (spec-review wrapper), CLAUDE.md Commands section updated, PM agent def updated with optional spec-review step. No documentation impact beyond the CLAUDE.md and PM agent def changes already included in the epic scope.
