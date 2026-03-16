# E-112-04: worktree-isolation.md Migration to Dispatch Scope

## Epic
[E-112: Context Layer Optimization](./epic.md)

## Status
`TODO`

## Description
After this story is complete, `worktree-isolation.md` will be a ~5-line stub retaining the three critical prohibition categories (no Docker, no credentials, no branch management) with a pointer to the implement skill for the full constraint set. The implement skill will inline the full worktree constraints directly into each worktree agent's spawn context, replacing the current reference to the rule file.

## Context
`worktree-isolation.md` is a universal rule (67 lines) that loads on every interaction, but worktree constraints are only relevant to agents spawned with `isolation: "worktree"` during dispatch. The implement skill currently references the rule file by path in its spawn context template (Phase 3 Step 4: "Review `.claude/rules/worktree-isolation.md` for constraints...") rather than inlining the constraints. This story inlines the full constraint set into the skill's spawn template first, then stubs the rule. The stub serves as a defense-in-depth safety net. Safety verdict: YELLOW→GREEN with inline-first approach.

**Key finding from validation (2026-03-15)**: The original assumption that "the implement skill already injects the full constraint set" was false -- the skill references the rule file. This revised story corrects the implementation path: inline constraints in the skill FIRST, then stub the rule.

## Acceptance Criteria
- [ ] **AC-1**: The implement skill's worktree spawn context (Phase 3 Step 4) inlines the full worktree constraint set directly in the spawn template, replacing the current "Review `.claude/rules/worktree-isolation.md`" reference. The inlined constraints must include all categories from the current rule: no Docker interaction, no app/credential/database CLI commands, no proxy commands, no credential or data file access, no context-layer modifications (unless assigned), no branch or worktree management, what agents CAN do (run tests, read/write source, use git for inspection), and file paths in reports convention.
- [ ] **AC-2**: `worktree-isolation.md` is reduced to a ~5-line stub that preserves: (a) the three critical "MUST NOT" categories in one line each (no Docker/app CLI, no credential/data file access, no branch/worktree management), (b) a pointer to the implement skill for the full constraint set, and (c) the "How to Know You Are in a Worktree" cwd check.
- [ ] **AC-3**: Any cross-references to `worktree-isolation.md` in other context-layer files are updated to reflect the stub's reduced scope.
- [ ] **AC-4**: All existing tests pass after the changes.

## Technical Approach
This story has a strict ordering requirement: inline constraints in the implement skill FIRST, then stub the rule. This ensures no moment where worktree agents lack their full constraint set.

Steps:
1. Read the full constraint set from `worktree-isolation.md`.
2. Inline it into the implement skill's Phase 3 Step 4 spawn context template, replacing the "Review `.claude/rules/worktree-isolation.md`" paragraph with the actual constraints.
3. Verify the skill's spawn context now contains every constraint from the rule file.
4. Reduce `worktree-isolation.md` to a stub.
5. Update cross-references.

Cross-reference files to check (grep for "worktree-isolation"):
- `.claude/rules/dispatch-pattern.md` (will be a stub after E-112-03, but check)
- `.claude/skills/implement/SKILL.md`

## Dependencies
- **Blocked by**: None (serialized with E-112-03 per execution constraints; both edit the implement skill but in different sections)
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (modify -- inline worktree constraints in spawn context)
- `.claude/rules/worktree-isolation.md` (modify -- trim to stub)
- Other files with `worktree-isolation` references (modify as discovered by grep)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing tests
- [ ] Critical prohibitions remain in the stub as a safety net
- [ ] Worktree agents receive the full constraint set via the skill's spawn context (not via rule file reference)

## Notes
- The stub is intentionally not empty -- it serves as defense-in-depth for the three most dangerous violation categories (Docker interaction, credential access, branch management). If an agent somehow enters a worktree without going through the implement skill, the stub catches the critical violations.
- The implement skill is dispatch-scoped (~535 lines, loaded only during dispatch). Adding ~40 lines of worktree constraints adds 0 ambient cost.
- The current spawn context says "Review `.claude/rules/worktree-isolation.md` for constraints" -- this reference pattern is a design smell (relay hop). Inlining is direct delivery, consistent with the skill's approach to other context (full story text, full Technical Notes, full spawn instructions).
- Net savings: ~60 lines removed from ambient context.
