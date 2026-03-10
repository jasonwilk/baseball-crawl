# E-093: E-088 Code Review Cleanup

## Status
`COMPLETED`

## Overview
Fix three convention violations and one test bug found during the E-088 post-commit code review (findings #3, #4, #5). Also remove dead code identified in the same review. These are independent quick fixes -- all dispatchable in parallel.

## Background & Context
After E-088 (Opponent Data Model and Resolution) was completed and committed, a code review identified several findings. E-091 covers the AC-level defects (findings #1, #2, #6). This epic covers the remaining convention violations and test bug:
- Two functions exceed the 50-line limit from `.claude/rules/python-style.md`
- A test fails in environments where `DEV_USER_EMAIL` is set
- Dead code left behind after a function was superseded

No expert consultation required -- all findings are straightforward code hygiene fixes with clear remediation paths.

## Goals
- All functions comply with the 50-line limit in `.claude/rules/python-style.md`
- No lazy imports of standard library modules without circular-import justification
- `test_listing_requires_admin` passes regardless of `DEV_USER_EMAIL` env state
- Dead code (`is_duplicate_opponent_public_id`) removed

## Non-Goals
- Refactoring beyond what is needed to fix the specific findings
- Adding new tests for existing functionality (only fix the broken test)
- Addressing E-091 findings (separate epic)

## Success Criteria
- `bulk_create_opponents` in `src/api/db.py` is under 50 lines with imports at module top
- `resolve_opponents` in `src/cli/data.py` is under 50 lines
- `test_listing_requires_admin` passes with and without `DEV_USER_EMAIL` set
- `is_duplicate_opponent_public_id` removed from `src/api/db.py`
- All existing tests pass (`pytest`)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-093-01 | Shrink bulk_create_opponents and fix lazy imports | DONE | None | SE |
| E-093-02 | Shrink resolve_opponents CLI command | DONE | None | SE |
| E-093-03 | Fix test_listing_requires_admin DEV_USER_EMAIL leak and remove dead code | DONE | None | SE |

## Dispatch Team
- software-engineer

## Technical Notes
- **50-line rule**: `.claude/rules/python-style.md` says "Keep functions under 50 lines; extract helpers for complex logic."
- **Pattern for test fix**: `test_admin_teams.py` already uses `"DEV_USER_EMAIL": ""` in `patch.dict` calls -- follow the same pattern.
- **Dead code**: `is_duplicate_opponent_public_id` at `src/api/db.py:976` has zero callers. It was superseded by `get_duplicate_opponent_name` which returns the name for a user-facing error message instead of just a boolean.
- All three stories are fully independent (different files or non-overlapping regions of the same file). Single-wave parallel dispatch.

## Open Questions
- None

## History
- 2026-03-10: Created from E-088 post-commit code review findings #3, #4, #5 plus dead code removal.
- 2026-03-10: Completed. All three stories dispatched in parallel to SE agents (worktree-isolated). Code-reviewer approved all with no MUST FIX findings. One SHOULD FIX noted: long typer.echo line in resolve_opponents (164 chars, cosmetic, no linter rule violated). Documentation assessment: No documentation impact. Context-layer assessment: No context-layer impact (all changes are code hygiene fixes within existing patterns).
