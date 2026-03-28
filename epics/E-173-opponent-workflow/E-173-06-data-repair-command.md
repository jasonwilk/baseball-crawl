# E-173-06: One-Time Opponent Data Repair Command

## Epic
[E-173: Fix Opponent Scouting Workflow End-to-End](epic.md)

## Status
`TODO`

## Description
After this story is complete, a `bb data repair-opponents` CLI command exists that propagates all existing `opponent_links` resolutions to `team_opponents` and activates resolved teams. This fixes the data disconnect for opponents that were resolved before E-173-01 shipped.

## Context
E-173-01 fixes the forward flow -- new resolutions will propagate correctly. But opponents already resolved (like Lincoln East Freshman, team 44) still have stale `team_opponents` rows pointing to the wrong stub team. This one-time repair command back-fills the missing propagation for all existing resolved `opponent_links` rows.

## Acceptance Criteria
- [ ] **AC-1**: A CLI command `bb data repair-opponents` exists under the `bb data` group.
- [ ] **AC-2**: The command queries all `opponent_links` rows where `resolved_team_id IS NOT NULL` and, for each, upserts a `team_opponents` row and sets `teams.is_active = 1` on the resolved team, per TN-6.
- [ ] **AC-3**: The command is idempotent: running it multiple times produces the same result with no errors or duplicates.
- [ ] **AC-4**: The command prints a summary: number of `team_opponents` rows created, number updated (stub replaced), number of teams activated, number of game/stat rows reassigned (from FK reassignment per AC-7), and number already correct (no-op).
- [ ] **AC-5**: The command runs in `--dry-run` mode by default (reports what it would do without writing). `--execute` flag applies changes.
- [ ] **AC-6**: Tests verify the repair logic: given a resolved `opponent_links` row with no corresponding `team_opponents` row, the repair creates one. Given a `team_opponents` row pointing to the wrong stub, the repair updates it.
- [ ] **AC-7**: When a `team_opponents` row is updated from a stub to the resolved team, all FK references to the old stub are reassigned to the resolved team (games, per-game stats, season stats, spray charts, rosters), consistent with E-173-01's `finalize_opponent_resolution()` behavior. The dedup guard from AC-9 of E-173-01 applies (skip rows where the resolved team already has matching data).

## Technical Approach
The repair logic is essentially a batch version of the `finalize_opponent_resolution()` function from E-173-01. It can reuse that function directly (loop over resolved `opponent_links` rows and call it for each) or use a bulk SQL approach for efficiency. The CLI command follows the existing `bb data dedup` pattern (dry-run by default, `--execute` to apply). The command belongs in `src/cli/data.py` under the existing data command group.

## Dependencies
- **Blocked by**: E-173-01 (reuses `finalize_opponent_resolution()` for consistent repair logic including game row reassignment)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` -- add `repair_opponents` command to the data group
- `tests/test_cli_data.py` or `tests/test_repair_opponents.py` -- test repair logic with dry-run and execute modes

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The repair command imports and reuses `finalize_opponent_resolution()` from E-173-01 for consistent behavior including game row reassignment.
- The dry-run output should be clear enough that the operator can review before running with `--execute`. Include team names, not just IDs.
- This command is expected to be run once after deployment. It may be useful again if future bugs cause drift, so keep it in the CLI permanently rather than as a throwaway script.
