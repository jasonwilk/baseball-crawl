# E-219-05: Dedup Simplification Assessment and Cleanup

## Epic
[E-219: Own-Side-Only Boxscore Loading](epic.md)

## Status
`TODO`

## Description
After this story is complete, the dedup infrastructure will be assessed and simplified. Hooks and tools that existed solely to compensate for cross-perspective duplication will be removed or simplified. Components that serve genuine name-variant dedup (e.g., "O" vs "Oliver") will be retained.

## Context
Multiple dedup mechanisms were built across E-215 and E-216 to compensate for cross-perspective player duplication. With the root cause fixed (E-219-01, E-219-02), some of this infrastructure is no longer needed. However, genuine name-variant dedup (prefix-matching first names on the same roster) is a real need unrelated to cross-perspective UUIDs and should be preserved. See TN-7 in the epic for the full list.

## Acceptance Criteria
- [ ] **AC-1**: Each dedup component listed in TN-7 is assessed with a documented verdict: KEEP (serves name-variant dedup), REMOVE (only served cross-perspective cleanup), or SIMPLIFY (partially serves both).
- [ ] **AC-2**: Components with REMOVE verdict are deleted. Components with SIMPLIFY verdict are updated. Components with KEEP verdict are left unchanged.
- [ ] **AC-3**: The `dedup_team_players()` hook in `ScoutingLoader` (line 137-149 of `scouting_loader.py`) is assessed. If it only fires for cross-perspective dupes (which no longer occur after E-219-01), it should be removed. If it also catches name-variant dupes, it should be kept.
- [ ] **AC-4**: The `dedup_team_players()` hook in `trigger.py` post-spray (line 752-762) is assessed with the same criteria as AC-3.
- [ ] **AC-5**: The `bb data dedup-players` CLI command is assessed. If name-variant dedup is still needed as an operator tool, the CLI stays. If the only use case was cross-perspective cleanup, it can be removed.
- [ ] **AC-6**: All existing tests pass after changes. Tests for removed components are removed. Tests for retained components are unchanged.

## Technical Approach
Read each dedup component's implementation and call sites. Trace the detection logic in `find_duplicate_players()` to understand what it catches: prefix-matching first names on the same roster (`team_rosters` join). Cross-perspective phantoms would NOT match this detector (they're not on any roster), so the detector likely serves name-variant dedup only. The hooks in `ScoutingLoader` and `trigger.py` call `dedup_team_players()` which calls `find_duplicate_players()` -- if the detector only catches name variants, the hooks are still useful. See TN-7 in the epic.

## Dependencies
- **Blocked by**: E-219-01, E-219-02, E-219-03
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py` (assess dedup hook)
- `src/pipeline/trigger.py` (assess post-spray dedup hook)
- `src/db/player_dedup.py` (assess detection logic)
- `src/cli/data.py` (assess `dedup-players` CLI)
- `tests/test_player_dedup.py` (update if components removed)
- `tests/test_dedup_integration.py` (update if components removed)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The assessment should be conservative: when in doubt, KEEP. Removing dedup infrastructure that turns out to be needed is worse than keeping unused code.
- The `data-model.md` "merge-every-run cycle" note update is handled by E-219-04 (context-layer story, routed to CA).
