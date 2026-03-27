# E-167-03: Auto-Merge CLI and Enhanced Duplicate Detection

## Epic
[E-167: Opponent Dedup Prevention and Resolution](epic.md)

## Status
`TODO`

## Description
After this story is complete, the operator can run `bb data dedup` to identify and auto-merge duplicate tracked teams. The command defaults to dry-run (preview only) and requires `--execute` to perform merges. The duplicate detection query is enhanced to also catch NULL-vs-non-NULL season_year pairs.

## Context
There are 34 team names with 2-5 duplicate rows from before the prevention fixes in E-167-01/02. E-155 delivered `merge_teams()` and `find_duplicate_teams()` but no batch workflow. This story adds the CLI entry point and enhances detection to catch the known gap where a stub with NULL season_year and a resolved team with season_year=2026 share the same name.

## Acceptance Criteria
- [ ] **AC-1**: `bb data dedup --dry-run` (the default) prints each duplicate group with: team names, ids, season_year, gc_uuid status, public_id status, game_count, has_stats flag, and the canonical selection (which team would be kept and why). No database changes are made.
- [ ] **AC-2**: `bb data dedup --execute` performs the merges for all safe groups. A safe group meets the safe-merge predicate per TN-5: same name (case-insensitive), same season_year (or both NULL, or one NULL and one non-NULL per the enhanced detection), both tracked, and games_between_teams == 0. Unsafe groups are skipped with a warning explaining why.
- [ ] **AC-3**: The canonical selection heuristic per TN-5 is applied: has_stats > game_count > lowest id. The selection is logged for each group in both dry-run and execute modes.
- [ ] **AC-4**: `find_duplicate_teams()` is enhanced to also return groups where one team has `season_year=NULL` and the other has a non-NULL season_year (same name, case-insensitive, both tracked). These are returned as separate groups from the exact-season_year matches. Cross-match groups MUST NOT include any team that already appears in an exact-match group (non-overlap guarantee).
- [ ] **AC-5**: Groups containing 3+ teams are handled: the command merges pairwise (merge the weakest into the canonical, then re-evaluate). The dry-run output shows the planned merge sequence.
- [ ] **AC-6**: The command prints a summary at the end: N groups found, M merged, K skipped (with reasons).
- [ ] **AC-7**: Tests cover the enhanced detection (NULL-vs-non-NULL season_year), the non-overlap guarantee (cross-match groups exclude teams already in exact-match groups), the canonical selection heuristic, the safe-merge predicate (especially the games-between exclusion), and the dry-run output format.

## Technical Approach
Add a `dedup` command to the `bb data` CLI group in `src/cli/data.py`. The command calls `find_duplicate_teams()` (enhanced) to get groups, then iterates: for each group, call `preview_merge()` to get safety data, apply the safe-merge predicate, select canonical, and either print the preview (dry-run) or call `merge_teams()` (execute). Enhance `find_duplicate_teams()` in `src/db/merge.py` to include NULL-vs-non-NULL season_year pairs -- change the grouping from `COALESCE(season_year, -1)` to a two-pass approach: first exact matches (current behavior), then NULL-vs-non-NULL cross-matches.

## Dependencies
- **Blocked by**: None (uses existing E-155 infrastructure, independent of E-167-01)
- **Blocks**: None

## Files to Create or Modify
- `src/db/merge.py` (modify -- enhance `find_duplicate_teams()`)
- `src/cli/data.py` (modify -- add `dedup` command)
- `tests/test_merge.py` (modify -- test enhanced detection)
- `tests/test_cli_data.py` (modify -- test dedup command)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The `find_duplicate_teams()` enhancement must not break the existing admin merge UI banner, which also calls this function. The banner should show both exact-match and NULL-vs-non-NULL groups.
- The existing `find_duplicate_teams()` query uses `LOWER(name)` grouping. Update it to use `name COLLATE NOCASE` to leverage the new `idx_teams_name_season_year` index from migration 007 (TN-8). `LOWER(name)` would bypass the index.
- For 3+ team groups, the pairwise merge strategy is: sort by canonical heuristic (best first), then merge each remaining team into the canonical one by one. After each merge, the canonical absorbs the duplicate's data.
- The two-pass detection (exact season_year matches first, then NULL-vs-non-NULL cross-matches) must run sequentially. When presenting results, clearly label which groups are exact matches and which are cross-matches (NULL-vs-non-NULL). Ensure cross-match groups do not duplicate teams already covered in exact-match groups.
- The `--execute` flag is deliberately named (not `--yes` or `--force`) to make the intent clear in command history.
