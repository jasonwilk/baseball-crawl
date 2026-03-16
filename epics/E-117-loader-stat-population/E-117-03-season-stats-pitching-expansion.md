# E-117-03: Season Stats Loader — Pitching Column Expansion (Member Teams)

## Epic
[E-117: Loader Stat Population](epic.md)

## Status
`TODO`

## Description
After this story is complete, `season_stats_loader.py` will populate all 15 confirmed and 23 optimistic pitching columns from the season-stats API endpoint's defense section into `player_season_pitching`, and set `stat_completeness = 'full'` for API-sourced rows.

## Context
The season_stats_loader currently maps only 9 pitching columns (gp_pitcher, ip_outs, h, er, bb, so, hr, pitches, total_strikes). The schema has 47+ pitching stat columns. The remaining columns include 15 confirmed-in-endpoint and 23 "expected in API but not yet confirmed in endpoint doc." Per DE recommendation, all 38 should be mapped optimistically via `defense.get("KEY")` — if the API omits a field, `None` flows to NULL (correct behavior for nullable columns).

**Scope: member teams only.** The season-stats API endpoint returns Forbidden for non-owned (opponent) teams. Opponents get season stats via the scouting pipeline (E-117-04).

## Acceptance Criteria
- [ ] **AC-1**: The pitching upsert includes all 15 confirmed-in-endpoint columns: gs, bf, bk, wp, hbp, svo, sb, cs, go, ao, loo, zero_bb_inn, inn_123, fps, lbfpn (in addition to the existing 9).
- [ ] **AC-2**: The pitching upsert includes all 23 optimistic columns: gp, w, l, sv, bs, r, sol, lob, pik, total_balls, lt_3, first_2_out, lt_13, bbs, lobb, lobbs, sm, sw, weak, hard, lnd, fb, gb. Note: `gp` (games played, all roles) will likely be NULL because `GP` lives in the API's `general` section, not `defense` — `defense.get("GP")` returns None. This is expected and acceptable (see epic Technical Notes "GP vs GP:P ambiguity"). Do NOT source `gp` from `general` — cross-section mapping is a different architectural pattern for a follow-up.
- [ ] **AC-3**: API response keys are mapped to schema column names per `docs/gamechanger-stat-glossary.md` (API Field Name Mapping table). Each `defense.get("KEY")` call uses the correct API abbreviation.
- [ ] **AC-4**: Rows upserted by season_stats_loader have `stat_completeness = 'full'` (per epic Technical Notes "stat_completeness Provenance").
- [ ] **AC-5**: Test fixture includes realistic non-zero values for a representative sample of the new columns (at minimum: gs, bf, wp, hbp, w, l, sv, and 3+ other confirmed columns).
- [ ] **AC-6**: Test asserts exact stored values for every newly added confirmed column on at least one player row.
- [ ] **AC-7**: Test asserts that optimistic columns are populated when present in the API response, and NULL when absent. At least one test case with an optimistic field present, one with it absent.
- [ ] **AC-8**: Test specifically verifies the TB→total_balls mapping: fixture includes `"TB": <non-zero value>` in the defense dict, and the test asserts that `total_balls` (not `tb`) is populated with the correct value. This guards the critical disambiguation (TB = "Total Balls" in pitching context).
- [ ] **AC-9**: Test asserts `stat_completeness = 'full'` for the loaded row.
- [ ] **AC-10**: All existing tests pass.

## Technical Approach
Refer to epic Technical Notes "Column Inventory" (player_season_pitching section) for the complete column list. Refer to `docs/gamechanger-stat-glossary.md` (API Field Name Mapping table, Pitching sections) for API key → schema column name mapping. Key non-obvious mappings: `GP:P` → gp_pitcher (already mapped), `#P` → pitches (already mapped), `TS` → total_strikes (already mapped), **`TB` → total_balls** (CRITICAL: in pitching context, TB = "Total Balls", NOT "Total Bases"), `0BBINN` → zero_bb_inn, `123INN` → inn_123, `LBFPN` → lbfpn, `1ST2OUT` → first_2_out, `<13` → lt_13, `<3` → lt_3, `SOL` → sol, `BBS` → bbs, `LOBB` → lobb, `LOBBS` → lobbs, `LOO` → loo, `WEAK` → weak, `HARD` → hard, `LND` → lnd, `FB` → fb.

The existing loader pattern uses `defense.get("KEY")` — extend to all 38 columns. For optimistic columns, use the same `defense.get()` pattern — `None` when absent is the correct nullable behavior. See IDEA-040 for future api-scout investigation of which optimistic columns the API actually returns.

**GP mapping note:** The optimistic `gp` column (games played, all roles) is distinct from `gp_pitcher` (games pitched, already mapped from `GP:P`). In the API response, `GP` appears in the `general` section, not `defense`. Using `defense.get("GP")` will likely return None — this is acceptable (nullable column). See epic Technical Notes "GP vs GP:P ambiguity."

For response structure, see `docs/api/endpoints/get-teams-team_id-season-stats.md`. Pitching stats live under `stats_data.players.<uuid>.stats.defense` (co-mingled with fielding stats — use only the pitching fields). Test fixtures should use realistic data shaped from this response structure.

## Dependencies
- **Blocked by**: E-116 (TeamRef YAML fix), E-117-02 (shared file: `season_stats_loader.py` and `test_season_stats_loader.py`)
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/season_stats_loader.py`
- `tests/test_loaders/test_season_stats_loader.py`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- E-117-02 and E-117-03 both modify `season_stats_loader.py` and `test_season_stats_loader.py`. Although the batting and pitching upserts are separate methods, they share the same file — parallel worktree execution would cause merge conflicts. E-117-03 is sequenced after E-117-02 for this reason.
