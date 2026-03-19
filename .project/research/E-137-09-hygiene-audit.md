# E-137-09: Context-Layer Hygiene Audit

**Date**: 2026-03-19
**Auditor**: claude-architect
**Scope**: All files modified by E-137 stories 01-08

## Files Audited

1. `.claude/skills/implement/SKILL.md` (E-137-01, E-137-08)
2. `.claude/rules/dispatch-pattern.md` (E-137-02)
3. `.claude/rules/worktree-isolation.md` (E-137-03)
4. `.claude/rules/workflow-discipline.md` (E-137-04)
5. `.claude/agents/code-reviewer.md` (E-137-05)
6. `.claude/agents/product-manager.md` (E-137-06)
7. `.claude/skills/codex-review/SKILL.md` (E-137-07)
8. `scripts/codex-review.sh` (E-137-07)

## Audit Methodology

Cross-reference search across all 8 files for:
- AC-2: Merge-back target references (epic worktree vs main checkout)
- AC-3: Triage model language (old accept/dismiss tracks vs new valid/invalid classification)
- AC-4: Closure sequence references (epic worktree → main merge vs old `git add -A`)
- AC-5: Epic worktree path convention (`/tmp/.worktrees/baseball-crawl-E-NNN/`) and branch convention (`epic/E-NNN`)

## Findings

### Finding 1: code-reviewer.md — Old triage language in SHOULD FIX header (AC-3)

**File**: `.claude/agents/code-reviewer.md`, line 196
**Before**: `### SHOULD FIX (triaged by main session -- each item is either accepted for fixing or dismissed with reason)`
**After**: `### SHOULD FIX (triaged by main session -- valid items are fixed, invalid items are dismissed)`
**Reason**: The old "accepted for fixing or dismissed with reason" framing implies a bilateral accept/dismiss track model. The new model classifies findings as valid (fix) or invalid (dismiss).
**Status**: FIXED

### Finding 2: code-reviewer.md — Old triage language in anti-pattern #6 (AC-3)

**File**: `.claude/agents/code-reviewer.md`, line 275
**Before**: `The main session may accept SHOULD FIX items and route them to the implementer for fixing -- that is the main session's triage authority, not a reclassification by the reviewer.`
**After**: `The main session classifies all findings (MUST FIX and SHOULD FIX) as valid or invalid -- valid findings are routed to the implementer for fixing regardless of severity, and invalid findings are dismissed. This is the main session's triage authority, not a reclassification by the reviewer.`
**Reason**: Same as Finding 1 — language aligned with the simplified valid/invalid model from TN-6.
**Status**: FIXED

## Clean Checks (No Issues Found)

### AC-2: Merge-back mechanics
- Searched for "main checkout" near "merge-back", "apply", or "git apply" across all files.
- All merge-back references consistently describe the epic worktree as the target.
- The only `git apply` to main checkout is in the closure merge sequence (Step 10), which is correct.

### AC-4: Closure sequence
- All files reference the epic worktree → main closure merge sequence.
- `git add -A` references in dispatch-pattern.md and workflow-discipline.md are in the permitted-operations lists (enumerating what git commands the main session may run), not describing the old closure model. These are correct.
- worktree-isolation.md references "atomic commit at epic closure" — correct.
- code-reviewer.md references "atomic commit at closure" — correct.

### AC-5: Path and branch conventions
- All references use `/tmp/.worktrees/baseball-crawl-E-NNN/` (with trailing slash in path descriptions, without in commands). Consistent.
- All branch references use `epic/E-NNN`. Consistent.
- codex-review skill uses example path `/tmp/.worktrees/baseball-crawl-E-137` (without trailing slash in command example). Consistent with command-line usage.

## Summary

| Check | Result | Findings |
|-------|--------|----------|
| AC-2: Merge-back target | CLEAN | No residual main-checkout-as-merge-target references |
| AC-3: Triage model | 2 FINDINGS FIXED | code-reviewer.md had old accept/dismiss language |
| AC-4: Closure sequence | CLEAN | No residual old closure model references |
| AC-5: Path/branch conventions | CLEAN | Consistent everywhere |
