# E-188-02: One-Time Cleanup of Existing Orphan Stubs

## Epic
[E-188: Eliminate Orphan Team Stubs from Report Generation](epic.md)

## Status
`TODO`

## Description
After this story is complete, a `bb data cleanup-orphans` CLI command exists that identifies and deletes orphan team stubs from prior report generations. The command follows the `--dry-run` (default) / `--execute` pattern used by `bb data dedup` and `bb data repair-opponents`.

## Context
Prior report generations have accumulated orphan team rows in the database. These are tracked teams with UUID-like names, no `team_opponents` links, no `reports` rows, `is_active = 0`, and `source` of `game_loader` or `scouting_loader`. E-188-01 prevents new orphans; this story cleans up existing ones.

## Acceptance Criteria
- [ ] **AC-1**: `bb data cleanup-orphans` (dry-run mode) prints a summary of orphan teams that would be deleted, including team ID, name, source, and season_year.
- [ ] **AC-2**: `bb data cleanup-orphans --execute` deletes orphan teams and their dependent rows in FK-safe order per TN-1, then prints a count of deleted teams.
- [ ] **AC-3**: The command identifies orphans per TN-2 criteria: `membership_type = 'tracked'`, `is_active = 0`, no `team_opponents` rows, no `reports` rows, `source IN ('game_loader', 'scouting_loader')`.
- [ ] **AC-4**: Teams with `team_opponents` links, `reports` rows, `membership_type = 'member'`, or `is_active = 1` are never deleted.
- [ ] **AC-5**: The command logs each deleted team at INFO level and prints a final summary.
- [ ] **AC-6**: Tests cover: (a) dry-run lists orphans without deleting, (b) execute mode deletes orphans, (c) linked teams are preserved.

## Technical Approach
Add a `cleanup-orphans` subcommand to the `bb data` command group in `src/cli/`. The orphan identification logic is based on TN-2 criteria (global scan, not per-report snapshot). The FK-safe deletion order is the same as TN-1. Consider extracting the shared FK-safe deletion logic into a helper that both the generator cleanup (E-188-01) and the CLI command can call.

## Dependencies
- **Blocked by**: E-188-01 (reuses FK-safe deletion logic)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` -- add `cleanup-orphans` subcommand
- `src/reports/generator.py` or `src/db/cleanup.py` -- shared FK-safe deletion helper (if extracted from E-188-01)
- `tests/test_cli_data.py` or `tests/test_cleanup_orphans.py` -- tests for the CLI command

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `--dry-run` / `--execute` pattern is established in `bb data dedup` and `bb data repair-opponents`. Follow the same UX conventions.
- The UUID-like name pattern (`________-____-____-____-____________`) is a supporting signal but not the sole filter -- the TN-2 criteria (no links, inactive, tracked, loader source) are the safety net.
- After running `--execute`, the operator should verify the teams table with `bb status` or a direct SQL query.
