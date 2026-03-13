# E-082-03: Add a Codex RTK smoke-check utility

## Epic
[E-082: Codex RTK Project-Level Integration](epic.md)

## Status
`DONE`

## Description
After this story is complete, the repo will provide a concrete smoke-check path that confirms the project-local RTK binary is present and usable from the project context. The check gives the operator a fast way to verify the Codex RTK lane without relying on host-global setup or manual guesswork.

## Context
Project-local tools need fast verification. Once RTK is installed into a repo-local directory, the operator needs a repeatable way to confirm it is present, executable, and capable of running at least one supported command from inside the workspace. This should be a small smoke test, not a benchmark suite.

## Acceptance Criteria
- [ ] **AC-1**: The repo provides a smoke-check command or script that verifies the project-local RTK binary exists and is executable.
- [ ] **AC-2**: The smoke check verifies `rtk --version` succeeds and `rtk git status` produces output without error from within the repo context.
- [ ] **AC-3**: The smoke check exits nonzero when the project-local RTK binary is missing or unusable.
- [ ] **AC-4**: The smoke check does not require host-global PATH setup or a host `~/.codex` mount.
- [ ] **AC-5**: The smoke check does not print secrets, proxy credentials, or auth artifacts.
- [ ] **AC-6**: Automated tests cover the smoke-check path or its command-resolution logic without requiring live network access.

## Technical Approach
This should be a thin Python utility plus tests so the command-resolution logic is easy to exercise under pytest. The key is deterministic verification of the project-local binary path and one representative RTK command. Keep it offline and self-contained.

## Dependencies
- **Blocked by**: E-082-01
- **Blocks**: E-082-04

## Files to Create or Modify
- `scripts/check_codex_rtk.py`
- `tests/test_check_codex_rtk.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-082-04**: The exact smoke-check command and expected outcomes that the documentation must describe.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The smoke check is deterministic and offline-safe
- [ ] Tests cover failure and success paths without live network calls

## Notes
- Keep the smoke check small. It is a presence/operability check, not a performance test.
