# E-224-01: Extend Pytest Rule with RTK Guardrails

## Epic
[E-224: RTK/Pytest Interaction Guardrails](epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/rules/pytest-verbose.md` will contain three additional guardrails beyond the existing `-v` requirement: a hard prohibition on `-x`/`--exitfirst`, guidance on verifying RTK-compressed summary lines, and a documented `rtk proxy` bypass path for when full output fidelity is required.

## Context
The existing rule (33 lines) covers only the `-v` flag requirement. The three new sections address RTK interaction issues discovered in E-173 and E-220 where agents reported incorrect test results. CA recommended extending this file rather than creating a new rule — same root cause (RTK/pytest interaction), same `paths: "**"` scope, stays under ~55 lines.

## Acceptance Criteria
- [ ] **AC-1**: The rule contains a section prohibiting `-x`/`--exitfirst` with pytest, explaining that RTK compression hides suite truncation
- [ ] **AC-2**: The rule contains a section on interpreting RTK output, including guidance to sanity-check the summary line test count before reporting results (e.g., if the count seems suspiciously low for the file or suite being tested, investigate before reporting success)
- [ ] **AC-3**: The rule contains a recommendation to use `rtk proxy python -m pytest tests/ -v --timeout=30` when full output fidelity is required (e.g., parsing failure details, debugging output format issues)
- [ ] **AC-4**: The existing `-v` requirement text and "Why" section are preserved unchanged (the CORRECT/WRONG examples may be extended per AC-5)
- [ ] **AC-5**: The CORRECT/WRONG code examples are updated to include `-x` as a WRONG example
- [ ] **AC-6**: The rule file remains under 60 lines total

## Technical Approach
Extend `.claude/rules/pytest-verbose.md` with new sections after the existing content. The file's `paths: "**"` frontmatter and existing structure stay intact. Add the `-x` prohibition, an "Interpreting RTK Output" section for summary verification, and an "RTK Bypass" section for the `rtk proxy` recommendation. Update the CORRECT/WRONG examples to show `-x` as prohibited.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/pytest-verbose.md` (modify)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Rule file is well-structured and readable
- [ ] No regressions to existing `-v` content
