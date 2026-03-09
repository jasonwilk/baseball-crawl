# E-089: Test Scope Discovery Rule

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Add a context-layer rule requiring implementers and the code-reviewer to discover all test files that import from modified modules before declaring test coverage complete. This closes a gap where changes to pre-existing functions can break tests in files outside the story's declared scope.

## Background & Context
During E-085 dispatch, a post-dispatch triage fix modified `check_single_profile()` in `src/gamechanger/credentials.py`. This broke a pre-existing test in `tests/test_check_credentials.py`. The failure went undetected because:

1. The implementing SE ran only story-scoped tests (`test_credentials.py`, `test_cli_creds.py`, etc.) -- the broken test was in a DIFFERENT file (`test_check_credentials.py`).
2. The code-reviewer ran the same scoped test suite -- same blind spot.
3. Only a final full-changeset review caught the regression.

**Root cause**: When implementers or reviewers modify a function that predates the current story, they scope test runs to the story's declared files. But the modified function may be tested in files outside that scope. Neither the SE agent definition, the code-reviewer agent definition, nor the testing rules require broader test discovery when touching pre-existing code.

The code-reviewer's Step 1 currently says: "For large test suites, target changed modules first: `pytest tests/test_<module>.py`." This guidance actively encourages the narrow scope that caused the blind spot.

**Expert consultation (claude-architect)**: CA confirmed the two-story scope (testing.md + SE agent def in story 01, code-reviewer.md in story 02). CA agreed the rule belongs in `testing.md` as a testing concern, with cross-references from agent definitions. No concerns about the grep-based approach for this project's scale.

**Expert consultation (software-engineer)**: SE confirmed grep-for-imports (`grep -rl "<module.path>" tests/`) is the right discovery tool. Key findings incorporated into Technical Notes: (1) grep is preferred over `pytest --collect-only` (faster, more direct), (2) subprocess-based tests are a known gap but benign (they test invocation, not logic), (3) full pytest is too blunt as a hard gate due to pre-existing failure noise, (4) optional 10+ file threshold for considering a full run. SE also identified a drafting ambiguity in E-089-02 AC-3 (resolved -- see story file).

## Goals
- Implementers discover and run all test files that import from modules they modified, not just tests named after the story's files
- The code-reviewer verifies that test scope covers all importers of changed modules as part of its review procedure
- The rule is proportional: grep-based discovery per modified module, not a blanket full-suite requirement

## Non-Goals
- Automated tooling or scripts to perform the discovery (the rule describes the manual grep pattern; tooling can come later if needed)
- Changing the full pytest run policy (full runs remain optional, not mandatory)
- Retroactive test reorganization to consolidate tests by module

## Success Criteria
- `testing.md` contains a test scope discovery rule with a concrete grep pattern
- The SE agent definition references the rule or includes equivalent guidance
- The code-reviewer's review procedure includes a step to verify test scope covers all importers
- An agent modifying `src/gamechanger/credentials.py` would, by following these rules, discover and run `tests/test_check_credentials.py` even if that file is not in the story's "Files to Create or Modify"

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-089-01 | Add test scope discovery rule to testing.md and SE agent definition | TODO | None | - |
| E-089-02 | Update code-reviewer review procedure with test scope verification | TODO | None | - |

## Dispatch Team
- claude-architect

## Technical Notes

### Test Discovery Pattern
The rule should describe a concrete pattern implementers and reviewers can follow:

1. For each source module modified (e.g., `src/gamechanger/credentials.py`), determine the importable module path (e.g., `gamechanger.credentials` or `src.gamechanger.credentials`).
2. Search the test directory for files that import from that module using `grep -rl "<module.path>" tests/` (e.g., `grep -rl "gamechanger.credentials" tests/`). This catches both `from src.gamechanger.credentials import ...` and variant import forms. False positives are harmless (extra tests run); false negatives are the real risk, and grep avoids them. `pytest --collect-only` is not better -- slower, more complex, and does not directly answer "which tests import module X."
3. Run those test files in addition to any story-scoped tests.

The specific rule text and placement details are for the implementing agent (claude-architect) to determine -- the stories describe what the rule must accomplish, not the exact prose.

### Subprocess Edge Case
One category grep misses: subprocess-based tests (e.g., `test_script_entry_points.py` invokes scripts via subprocess that internally import from modified modules). However, these tests check invocation and help-text, not internal logic -- they will still pass when you change a function's behavior. The rule should acknowledge this with a footnote: "subprocess-based tests are discovered by convention, not grep."

### Full pytest Run Guidance
A full `pytest` run is too blunt as a hard gate. Pre-existing failures in unrelated files create noise that muddies the signal. The grep-based targeted approach gives a cleaner signal: "these tests import from modules I changed; they pass or fail because of my changes." Optional guidance: if discovery reveals 10+ files, consider a full run instead of listing them all.

### Affected Files
- `/.claude/rules/testing.md` -- add the test scope discovery rule
- `/.claude/agents/software-engineer.md` -- add a reference or note about broader test discovery
- `/.claude/agents/code-reviewer.md` -- update Step 1 of the Review Procedure to include test scope verification

### Why Not Full pytest?
A full `pytest` run would also catch this, but it is a blunt instrument. The project has 900+ tests and growing. Requiring a full run for every story would slow dispatch and pre-existing failures in unrelated files create noise. The grep-based discovery approach is targeted: it catches exactly the cross-file dependencies that scoped runs miss, without the overhead of running unrelated tests. SE confirmed this assessment: grep gives a cleaner signal ("these tests import from modules I changed") than a full run.

### Frontmatter Glob Consideration
SE noted that `testing.md` currently triggers on `tests/**` and `**/*test*.py` -- but the test scope discovery rule is about modifying *source* modules. Adding `src/**` to the frontmatter glob would ensure the rule auto-loads when agents modify source files without touching test files. This is mitigated by the SE agent def cross-reference (AC-2 of E-089-01), so it's optional -- CA's discretion during implementation.

### Parallel Safety
E-089-01 modifies `testing.md` and `software-engineer.md`. E-089-02 modifies `code-reviewer.md`. No file conflicts -- stories can execute in parallel.

## Open Questions
None remaining. SE consultation resolved the discovery method question (grep-for-imports, leave invocation to the agent).

## History
- 2026-03-09: Created. Prompted by E-085 dispatch regression where a modified function's tests in a separate file went undiscovered.
- 2026-03-09: CA consultation completed (relayed by user). Confirmed two-story scope and testing.md placement.
- 2026-03-09: SE consultation completed (relayed by user). Confirmed grep-for-imports as the right tool, identified subprocess edge case, recommended against full-pytest hard gate, fixed AC-3 drafting ambiguity in E-089-02. Findings incorporated into Technical Notes.
- 2026-03-09: Team refinement session (PM + SE + CA). Both agents confirmed no blocking concerns. SE suggested testing.md frontmatter glob expansion to `src/**` (added to Technical Notes as optional). CA confirmed self-contained Step 1 approach with parenthetical cross-reference to testing.md. Epic set to READY.
