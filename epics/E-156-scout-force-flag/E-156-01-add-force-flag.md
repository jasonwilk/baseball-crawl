# E-156-01: Add --force Flag to Scout CLI Command

## Epic
[E-156: Add --force Flag to bb data scout](epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb data scout --force` will bypass the 24-hour freshness check and re-scout all opponents regardless of when they were last scouted. The flag passes through to the existing `ScoutingCrawler` constructor's `freshness_hours` parameter. Default behavior (without `--force`) is unchanged.

## Context
The `ScoutingCrawler` already accepts `freshness_hours` but the CLI doesn't expose it. The production change adds a Typer boolean option to `src/cli/data.py` and threads the value through to the constructor; the test changes add dry-run and live-path tests to `tests/test_cli_scout.py`. Single-team mode (`--team`) already bypasses freshness by calling `scout_team()` directly, so `--force` only affects the all-teams `scout_all()` path.

## Acceptance Criteria
- [ ] **AC-1**: `bb data scout --help` shows a `--force` option with a description indicating it bypasses the freshness check
- [ ] **AC-2**: Given opponents scouted within the last 24 hours, when `bb data scout --force` is run, then all opponents are re-scouted (none skipped for freshness)
- [ ] **AC-3**: Given opponents scouted within the last 24 hours, when `bb data scout` is run (without `--force`), then recently-scouted opponents are skipped (existing behavior preserved)
- [ ] **AC-4**: `bb data scout --force --dry-run` output includes an indication that force mode is active

## Technical Approach
The production change is in `src/cli/data.py`; the test addition is in `tests/test_cli_scout.py`. The `scout` command gets a new `--force` boolean option (Typer `bool`, default `False`, per project CLI conventions). When `True`, the `_scout_live` function passes `freshness_hours=0` to the `ScoutingCrawler` constructor. The `_scout_dry_run` function reports force mode in its output. The `ScoutingCrawler` class itself requires no changes -- it already supports `freshness_hours=0` which makes `_is_scouted_recently()` return `False` for all opponents.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` -- add `--force` option to `scout()`, thread through to `_scout_live()` and `_scout_dry_run()`
- `tests/test_cli_scout.py` -- add tests for `--force` flag: dry-run output, live-path `freshness_hours` pass-through (follows established pattern in file)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] AC-1 verified by code inspection (Typer option present with help text)
- [ ] AC-2 verified by test: `--force` causes `ScoutingCrawler` to be constructed with `freshness_hours=0` (live-path test, follows pattern at `test_cli_scout.py` lines 107-157)
- [ ] AC-3 verified by test: without `--force`, `ScoutingCrawler` is constructed with default `freshness_hours` (24) (live-path test, same pattern)
- [ ] AC-4 verified by test: `--force --dry-run` output includes force indication
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `--team` flag already bypasses freshness, so `--force --team` is harmless but redundant.
