# E-114-03: UX Guard — Disable Member Radio Without gc_uuid

## Epic
[E-114: E-100 Codex Review Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, the add-team confirm page prevents operators from selecting "Member" when gc_uuid is unavailable (bridge returned 403), since member teams without gc_uuid cannot be crawled.

## Context
The confirm page offers the "Member" radio unconditionally. Creating a member team with gc_uuid=None is not a correctness bug -- crawlers fail loudly when they encounter it -- but it creates an operator-error path that is easily preventable at the UI level. Both CR and SE confirmed this is a P2 UX improvement, not a data integrity issue.

## Acceptance Criteria
- [ ] **AC-1**: On the confirm page, the "Member" radio input is disabled when `gc_uuid_status` is not `'found'`. The "Tracked" radio remains the default and is always enabled.
- [ ] **AC-2**: A visual indicator (warning text, tooltip, or similar) explains why the Member option is unavailable when disabled. The message communicates that member teams require a GameChanger UUID for crawling.
- [ ] **AC-3**: When `gc_uuid_status` is `'found'`, the Member radio is enabled and works as before.
- [ ] **AC-4**: A test verifies that the confirm page renders the Member radio as disabled when gc_uuid_status is 'forbidden'.
- [ ] **AC-5**: Existing admin route tests continue to pass.

## Technical Approach
Modify the Jinja2 template `confirm_team.html` to conditionally disable the member radio based on `gc_uuid_status`. Add a brief inline warning message. The template already receives `gc_uuid_status` in its context.

Context files to read:
- `/workspaces/baseball-crawl/src/api/templates/admin/confirm_team.html`
- `/workspaces/baseball-crawl/tests/test_admin_teams.py`

## Dependencies
- **Blocked by**: E-114-02 (shared test file)
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/admin/confirm_team.html` (modified)
- `tests/test_admin_teams.py` (modified -- new test case)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
