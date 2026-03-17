# E-123-06: Scouting Run Status Lifecycle Fix

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the scouting run status lifecycle will correctly transition from `"running"` to `"completed"` after a successful crawl, so that the freshness gating check (`_is_scouted_recently`) works as intended and teams are not re-scouted every run.

## Context
CR3-C2 confirmed that `src/gamechanger/crawlers/scouting.py:182` writes `status='running'` after crawl completion. The freshness check at line 436 requires `status = 'completed'`. If the load step (external CLI) fails or is skipped, status stays `'running'` and freshness gating never engages -- causing the same team to be re-scouted on every run, wasting API calls. See `/.project/research/full-code-review/cr3-verified.md` (C-2) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: After a successful crawl phase, the scouting run status is set to `"completed"` so that `_is_scouted_recently()` recognizes it
- [ ] **AC-2**: A team that was scouted recently (within freshness window) is skipped on the next run
- [ ] **AC-3**: A team whose scouting run failed retains a status that does NOT trigger freshness gating (so it gets retried)
- [ ] **AC-4**: A test verifies that freshness gating correctly skips recently-scouted teams
- [ ] **AC-5**: All existing tests pass

## Technical Approach
Read the scouting crawler's status lifecycle: `_upsert_run_start`, `_upsert_run_end`, and `_is_scouted_recently`. Determine the correct point to set `"completed"` -- likely after the crawl data is fully written (but before the load step, which is a separate CLI command). The crawl and load are separate operations; the crawl step should mark its own completion. See TN-6 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/scouting.py`
- `tests/test_scouting_crawler.py` (existing file -- update status assertions that currently expect `"running"`)
- `tests/test_scouting_loader.py` (or new test file for scouting crawler status)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- E-122-01 modifies `scouting.py` for auth abort. If both stories are dispatched in the same wave, file conflict is possible. However, E-122-01 touches `_fetch_boxscores` exception handling while this story touches `_upsert_run_end` and `_is_scouted_recently` -- different functions, low conflict risk.
