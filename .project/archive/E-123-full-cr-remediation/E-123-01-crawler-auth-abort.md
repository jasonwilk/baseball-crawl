# E-123-01: Crawler CredentialExpiredError Propagation

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, all four remaining crawlers (schedule, roster, game_stats, player_stats) will immediately abort their `crawl_all()` loops when a `CredentialExpiredError` is raised, instead of catching it in the generic `except Exception` handler and continuing to log errors for every subsequent team. This extends the same pattern that E-122-01 applies to the scouting crawler.

## Context
CR3-C1 confirmed that four crawlers silently swallow `CredentialExpiredError` because their `crawl_all()` loops use a blanket `except Exception` catch-all. When credentials expire mid-crawl, the operator sees N error log lines (one per remaining team) instead of a single abort. The scouting crawler and opponent crawler already handle this correctly. See `/.project/research/full-code-review/cr3-verified.md` (C-1) for line numbers and evidence.

## Acceptance Criteria
- [ ] **AC-1**: `schedule.py` `crawl_all()` re-raises `CredentialExpiredError` before the generic `except Exception` handler
- [ ] **AC-2**: `roster.py` `crawl_all()` re-raises `CredentialExpiredError` before the generic `except Exception` handler
- [ ] **AC-3**: `game_stats.py` `crawl_all()` re-raises `CredentialExpiredError` before the generic `except Exception` handler
- [ ] **AC-4**: `player_stats.py` `crawl_all()` re-raises `CredentialExpiredError` before the generic `except Exception` handler
- [ ] **AC-5**: Each modified crawler has a test confirming that `CredentialExpiredError` propagates out of `crawl_all()` (not swallowed)
- [ ] **AC-6**: All existing tests pass

## Technical Approach
Read each crawler's `crawl_all()` method and the existing `except Exception` handler. Add a preceding `except CredentialExpiredError: raise` clause. The `CredentialExpiredError` import already exists in some crawlers (check each); add it where missing. Write a test per crawler that mocks the client to raise `CredentialExpiredError` and asserts it propagates. See TN-1 in the epic for the pattern and line numbers.

## Dependencies
- **Blocked by**: E-122-01 (scouting crawler auth abort -- this story covers only the 4 non-scouting crawlers; E-122-01 covers scouting.py)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/crawlers/schedule.py`
- `src/gamechanger/crawlers/roster.py`
- `src/gamechanger/crawlers/game_stats.py`
- `src/gamechanger/crawlers/player_stats.py`
- `tests/test_crawlers/test_schedule_crawler.py` (or equivalent test location)
- `tests/test_crawlers/test_roster_crawler.py` (or equivalent test location)
- `tests/test_crawlers/test_game_stats_crawler.py` (or equivalent test location)
- `tests/test_crawlers/test_player_stats_crawler.py` (or equivalent test location)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The opponent crawler (`opponent.py:263-271`) already handles this correctly -- use it as a reference pattern.
- E-122-01 applies the same fix to `scouting.py` -- do not modify scouting.py in this story.
