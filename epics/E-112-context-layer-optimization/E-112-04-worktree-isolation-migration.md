# E-112-04: worktree-isolation.md Migration to Dispatch Scope

## Epic
[E-112: Context Layer Optimization](./epic.md)

## Status
`TODO`

## Description
After this story is complete, `worktree-isolation.md` will be a ~5-line stub retaining the three critical prohibition categories (no Docker, no credentials, no branch management) with a pointer to the implement skill for the full constraint set. The implement skill already injects worktree constraints into spawn context during dispatch.

## Context
`worktree-isolation.md` is a universal rule (67 lines) that loads on every interaction, but worktree constraints are only relevant to agents spawned with `isolation: "worktree"` during dispatch. The implement skill already injects the full constraint set into each worktree agent's spawn prompt. The stub serves as a safety net for edge cases where skill injection might be missed. Safety verdict: YELLOW→GREEN with stub.

## Acceptance Criteria
- [ ] **AC-1**: `worktree-isolation.md` is reduced to a ~5-line stub that preserves: (a) the three critical "MUST NOT" categories in one line each (no Docker/app CLI, no credential/data file access, no branch/worktree management), (b) a pointer to the implement skill for the full constraint set, and (c) the "How to Know You Are in a Worktree" cwd check.
- [ ] **AC-2**: The full worktree constraint content (currently in `worktree-isolation.md`) is verifiably present in the implement skill's worktree spawn context.
- [ ] **AC-3**: Any cross-references to `worktree-isolation.md` in other context-layer files are updated to reflect the stub's reduced scope.
- [ ] **AC-4**: All existing tests pass after the changes.

## Technical Approach
Verify the implement skill's worktree spawn prompt contains all constraints from `worktree-isolation.md`, then trim the rule to a stub. The stub retains the highest-severity prohibitions as a defense-in-depth layer -- if the skill injection ever fails, the stub catches the most dangerous actions.

Cross-reference files to check (grep for "worktree-isolation"):
- `.claude/rules/dispatch-pattern.md`
- `.claude/skills/implement/SKILL.md`

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/worktree-isolation.md` (modify -- trim to stub)
- Other files with `worktree-isolation` references (modify as discovered by grep)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] Critical prohibitions remain in the stub as a safety net

## Notes
- The stub is intentionally not empty -- it serves as defense-in-depth for the three most dangerous violation categories (Docker interaction, credential access, branch management)
- Net savings: ~60 lines removed from ambient context
