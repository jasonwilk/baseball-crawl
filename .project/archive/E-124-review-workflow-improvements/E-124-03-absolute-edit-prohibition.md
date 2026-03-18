# E-124-03: Absolute Main-Session Edit Prohibition

## Epic
[E-124: Review Workflow Improvements](epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill, dispatch-pattern rule, and workflow-discipline rule will all state an absolute prohibition: the main session MUST NOT create, modify, or delete any file. The only file operations the main session performs directly are git operations (merge, mv, add, commit) and writes to its own memory directory. All other file edits are dispatched to the appropriate agent. No exception language for "trivial" fixes, doc edits, or one-liners.

## Context
Multiple context-layer files currently say the main session "MUST NOT write code" or "MUST NOT write or modify application/test code." The word "code" creates ambiguity that has led to the main session occasionally making "trivial" edits (doc fixes, one-liners) instead of routing to agents. The prohibition needs to be absolute and cover all file types.

## Acceptance Criteria
- [ ] **AC-1**: The implement skill's anti-patterns #1 and #13 use absolute language prohibiting all file creation, modification, and deletion -- not just "code" or "application/test code," per Technical Notes TN-4.
- [ ] **AC-2**: All main-session prohibition language in `dispatch-pattern.md` uses the same absolute language -- including the opening paragraph ("does not...write code") and Team Roles item 1 ("MUST NOT write code"). The implementer must scan comprehensively.
- [ ] **AC-3**: `workflow-discipline.md` Workflow Routing Rule's "MUST NOT" list uses the same absolute language.
- [ ] **AC-4**: All three files explicitly state that the main session's only direct file operations are git commands (`git merge`, `git mv`, `git add`, `git commit`, and similar VCS operations) and writes to its own memory directory (`/home/vscode/.claude/projects/*/memory/`).
- [ ] **AC-5**: No "trivial fix" exception language remains anywhere in the modified files.
- [ ] **AC-6**: All instances of weak "code"-scoped prohibition language in the implement skill are tightened -- including but not limited to the Purpose section ("does not...write code") and workflow summary diagram ("main session NEVER fixes code itself"). The implementer must scan comprehensively.
- [ ] **AC-7**: All instances of weak "code"-scoped prohibition language in `dispatch-pattern.md` and `workflow-discipline.md` are tightened. The implementer must scan each file comprehensively, not just the locations named in other ACs.

## Technical Approach
This is a language-tightening story across three files. The current wording uses "code" or "application/test code" which leaves room for interpretation. Replace with absolute language covering all file types. The git-operations carve-out must be explicit so the main session can still perform merge-back, archive moves, and commits.

Scan each file for all instances of the weaker language and replace consistently. Known locations (not exhaustive -- scan comprehensively):
- Implement skill: Anti-patterns #1 ("Do not implement stories yourself"), #13 ("Do not apply code fixes yourself" / "NEVER writes or modifies application/test code"), Purpose section ("does not...write code"), workflow summary diagram ("main session NEVER fixes code itself")
- `dispatch-pattern.md`: Opening paragraph ("does not...write code") and Team Roles item 1 ("MUST NOT write code")
- `workflow-discipline.md`: Workflow Routing Rule "MUST NOT" list ("write or modify application/test code")

## Dependencies
- **Blocked by**: None
- **Blocks**: E-124-01

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (anti-patterns #1, #13, and any other relevant wording)
- `.claude/rules/dispatch-pattern.md` (opening paragraph and Team Roles section)
- `.claude/rules/workflow-discipline.md` (Workflow Routing Rule section)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] No regressions in existing skill/rule structure
- [ ] Code follows project style (see CLAUDE.md)
- [ ] Consistent language across all three files

## Notes
The pattern to fix: anywhere "write code" or "modify application/test code" appears as a main-session prohibition, replace with "create, modify, or delete any file" plus the two carve-outs (git operations and own memory directory).
