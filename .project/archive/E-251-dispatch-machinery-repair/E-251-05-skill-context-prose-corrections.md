# E-251-05: Skill/context prose corrections (codex-review closure→Phase 5, plan glob, filesystem-context, context-fundamentals)

## Epic
[E-251: Dispatch-Machinery Repair](../E-251-dispatch-machinery-repair/epic.md)

## Status
`DONE`

## Description
After this story is complete, four stale-prose / citation defects in the skill and context-fundamentals files are corrected: the codex-review skill's closure step routes to Phase 5 (not a re-entry into or reordering of Phase 4a/4b), the plan skill's artifact-staging step stages file-form research artifacts, filesystem-context no longer teaches the obsolete PM-dispatches-implementers model, and context-fundamentals no longer cites a nonexistent CLAUDE.md "Workflow" section.

## Context
These are four independent audit findings (§2 LOW "Context layer" + MEDIUM) that misdirect agents following the skills literally: an inverted phase reference sends the codex-review closure step to the wrong phase, a trailing-slash glob silently drops file-form research artifacts from the READY staging commit, a stale dispatch-model description contradicts the current main-session-spawns model, and a dangling citation points at a CLAUDE.md section that does not exist. Per epic TN-6.

## Acceptance Criteria
- [ ] **AC-1** (codex-review closure destination): the codex-review skill's closure step (audit cites Step 7 / ~line 151) routes control to **Phase 5 (closure)** after the Codex pass. A literal 4a/4b swap is WRONG (CA design-review correction 2026-07-04): Phase 4a = CR, Phase 4b = Codex, and the codex-review skill IS the Codex (4b) pass — after it, control proceeds to Phase 5 (closure), NEVER back to a CR phase. The step is rewritten so its destination is Phase 5, not a re-entry into (or reordering of) 4a/4b.
- [ ] **AC-2** (plan-skill glob): the plan skill's Step 2a artifact-staging step stages research artifacts saved as a single FILE (not only directory-form artifacts) — the trailing-slash directory glob that silently skipped file-form artifacts is replaced so a file-form research artifact is included in the READY staging commit.
- [ ] **AC-3** (filesystem-context dispatch model): `.claude/skills/filesystem-context/SKILL.md` no longer describes the obsolete "PM dispatches implementers" model; it reflects the current model where the main session spawns and routes during dispatch and PM owns statuses + AC verification (consistent with `.claude/rules/dispatch-pattern.md`). Scope covers the FULL span of the obsolete model in that file — per CA's design review (2026-07-04) it appears at ~lines 42, 95, 99-112, and 190, plus stale "Task tool" phrasing — not a single occurrence. (The `multi-agent-patterns` skill echoes the same obsolete PM-dispatch chain but is OUT OF SCOPE here — noted for the CE-5 truth sweep.)
- [ ] **AC-4** (context-fundamentals citation): `.claude/skills/context-fundamentals/SKILL.md` no longer cites a nonexistent CLAUDE.md "Workflow" section; the citation is corrected or removed so it points at content that actually exists.
- [ ] **AC-5**: Each correction is verified against the CURRENT state of the referenced files (per epic TN-1, cited line numbers may have drifted); the code-reviewer confirms each cross-reference now resolves to real, correctly-ordered content.

## Technical Approach
Per epic TN-6. Four localized prose/glob edits across `.claude/skills/codex-review/SKILL.md`, `.claude/skills/plan/SKILL.md`, `.claude/skills/filesystem-context/SKILL.md`, and `.claude/skills/context-fundamentals/SKILL.md`. CA locates the current occurrences and determines the precise wording. These are accuracy fixes, not workflow-policy changes.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/codex-review/SKILL.md` — correct the closure-step destination to Phase 5 (not a 4a/4b reorder)
- `.claude/skills/plan/SKILL.md` — stage file-form research artifacts in Step 2a
- `.claude/skills/filesystem-context/SKILL.md` — update to the current dispatch model
- `.claude/skills/context-fundamentals/SKILL.md` — fix the phantom CLAUDE.md "Workflow" citation

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Self-contained fixes (audit file is uncommitted). Audit refs: §2 LOW "Context layer" — "codex-review Step 7 inverts Phase 4a/4b; filesystem-context teaches the obsolete PM-dispatches model; context-fundamentals cites a nonexistent CLAUDE.md 'Workflow' section; plan skill Step 2a's trailing-slash glob never stages file-form research artifacts"; §5 Quick Wins ("codex-review line 151; plan-skill trailing slash").
