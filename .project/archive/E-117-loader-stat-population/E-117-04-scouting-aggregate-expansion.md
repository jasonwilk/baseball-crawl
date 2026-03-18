# E-117-04: Scouting Loader — Aggregate Query Expansion

## Epic
[E-117: Loader Stat Population](epic.md)

## Status
`DONE`

## Description
After this story is complete, `scouting_loader.py` will compute season aggregates for all game-level stat columns populated by E-117-01, producing richer opponent season stats from boxscore data. This is the only path for opponent season stats — the season-stats API endpoint is Forbidden for non-owned teams.

## Context
`scouting_loader._compute_batting_aggregates` currently sums only: ab, h, doubles, triples, hr, rbi, bb, so, sb. `_compute_pitching_aggregates` sums only: ip_outs, h, er, bb, so. After E-117-01 ships, `player_game_batting` will also have r, tb, hbp, shf, cs, e, and `player_game_pitching` will have r, wp, hbp, pitches, total_strikes, bf. The aggregate queries must be expanded to SUM the new columns that have corresponding `player_season_*` columns. For batting: r, tb, hbp, shf, cs (5 columns — `e` has no season-level column). For pitching: r, wp, hbp, pitches, total_strikes, bf (all 6).

## Acceptance Criteria
- [ ] **AC-1**: `_compute_batting_aggregates` SELECT, tuple unpacking (`for player_id, ... in rows:`), INSERT, and ON CONFLICT UPDATE include 5 new columns: r, tb, hbp, shf, cs. (`e` is excluded — errors exist in `player_game_batting` but have no corresponding column in `player_season_batting`.)
- [ ] **AC-2**: `_compute_pitching_aggregates` SELECT, tuple unpacking (`for player_id, ... in rows:`), INSERT, and ON CONFLICT UPDATE include: r, wp, hbp, pitches, total_strikes, bf.
- [ ] **AC-3**: Scouting-derived season stat rows retain `stat_completeness = 'boxscore_only'`. Do NOT explicitly set `stat_completeness` in the INSERT or ON CONFLICT UPDATE — the schema default handles it, and omitting it preserves the future enrichment path (see epic Technical Notes "Future Enrichment Path").
- [ ] **AC-4**: Test verifies that scouting-derived season batting stats include the newly aggregated columns with correct summed values. At least one test case where a sparse column (e.g., hbp) is non-NULL in some games and NULL in others — verifying SUM ignores NULLs correctly.
- [ ] **AC-5**: Test verifies that scouting-derived season pitching stats include the newly aggregated columns with correct summed values. At least one test case where a sparse column is NULL across all games for a player — verifying the season aggregate is NULL (not 0).
- [ ] **AC-6**: Test verifies rerun idempotency: load boxscores, compute aggregates, then load updated boxscores with changed stat values and recompute. The ON CONFLICT UPDATE must overwrite stale season totals with fresh sums — assert the final row reflects the updated game data, not the original.
- [ ] **AC-7**: All existing tests pass.

## Technical Approach
Refer to epic Technical Notes "Scouting Loader Cascade" for the cascade column list. The aggregate functions use SQL SUM() over player_game_batting/pitching rows grouped by player and season. Extend the SELECT to include new columns, add them to the INSERT and the ON CONFLICT UPDATE SET clause. Both aggregate methods use upserts — new columns must appear in all four places (SELECT, Python tuple unpacking in the `for player_id, ... in rows:` loop, INSERT VALUES, ON CONFLICT UPDATE SET) or reruns will leave stale/NULL season totals. The tuple unpacking is a 4th sync point because Python destructures each row positionally — adding a column to the SELECT without extending the unpacking tuple causes a `ValueError` at runtime.

**NULL handling for sparse aggregates:** Use plain `SUM(col)` (NOT `COALESCE`). When all game-level values for a player are NULL (the stat was never recorded in any boxscore), the season aggregate should be NULL — meaning "no data." This is semantically different from 0, which would mean "zero confirmed occurrences." For example, if a player's `hbp` is NULL in every game (because HBP is a sparse extra that only appears for non-zero values), the season `hbp` should be NULL, not 0. SQL `SUM()` correctly returns NULL when all inputs are NULL, and ignores NULLs when some values are non-NULL.

`shf` is confirmed present in `player_season_batting` (DDL line 246). `e` is NOT present in `player_season_batting` — it only exists in `player_game_batting` (DDL line 176). Include 5 batting cascade columns: r, tb, hbp, shf, cs.

**Test file context (E-120-02):** `tests/test_scouting_loader.py` was updated by E-120-02 (shipped 2026-03-17) with a new `test_aggregate_isolated_per_team` test that verifies per-team aggregate isolation. Existing aggregate tests insert game data using only the original columns (ab, h, doubles, triples, hr, rbi, bb, so, sb for batting; ip_outs, h, er, bb, so for pitching). New test fixtures for E-117-04 must include the expanded columns.

## Non-Goals (Boxscore-Only Scope)
This story aggregates only the counting stats available from boxscores. Advanced stats that require play-by-play parsing are NOT available in boxscore data and MUST NOT be included in these aggregates:
- **Not available from boxscores**: QAB, pitches seen per batter (PS), contact quality (HARD/WEAK/LND), fly balls (FLB), ground balls (GB), swing metrics (SW/SM), full count PAs (FULL), 2-strike counts, 6+ pitch PAs, LOB in big spots (LOBB), and all other advanced batting/pitching stats
- **Available from boxscores**: Only the basic counting stats listed in AC-1 and AC-2
- Achieving advanced stat parity for opponents requires a future play-by-play compilation pipeline (see IDEA-041)

## Dependencies
- **E-116**: COMPLETED (archived 2026-03-17). No longer blocking.
- **Blocked by**: E-117-01 (game loader must populate the columns before they can be aggregated)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py`
- `tests/test_scouting_loader.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
