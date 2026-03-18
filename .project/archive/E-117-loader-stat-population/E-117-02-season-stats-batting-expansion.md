# E-117-02: Season Stats Loader — Batting Column Expansion (Member Teams)

## Epic
[E-117: Loader Stat Population](epic.md)

## Status
`TODO`

## Description
After this story is complete, `season_stats_loader.py` will populate all 37 confirmed batting columns from the season-stats API endpoint's offense section into `player_season_batting`, and set `stat_completeness = 'full'` for API-sourced rows.

## Context
The season_stats_loader currently maps only 10 batting columns (gp, ab, h, doubles, triples, hr, rbi, bb, so, sb) from the API response. The schema has 47 batting stat columns total. The remaining 37 are confirmed in the season-stats endpoint documentation but the loader never reads them. The mapping pattern is already established — this story extends it to full coverage.

**Scope: member teams only.** The season-stats API endpoint (`GET /teams/{team_id}/season-stats`) returns Forbidden for non-owned (opponent) teams. Opponents get season stats via the scouting pipeline (E-117-04), which aggregates boxscore data.

## Acceptance Criteria
- [ ] **AC-1**: The batting upsert in `season_stats_loader.py` includes all 22 standard batting columns: pa, singles, r, sol, hbp, shb, shf, gidp, roe, fc, ci, pik, cs, tb, xbh, lob, three_out_lob, ob, gshr, two_out_rbi, hrisp, abrisp (in addition to the existing 10).
- [ ] **AC-2**: The batting upsert includes all 15 advanced batting columns: qab, hard, weak, lnd, flb, gb, ps, sw, sm, inp, full, two_strikes, two_s_plus_3, six_plus, lobb.
- [ ] **AC-3**: API response keys are mapped to schema column names per `docs/gamechanger-stat-glossary.md` (API Field Name Mapping table). Each `offense.get("KEY")` call uses the correct API abbreviation.
- [ ] **AC-4**: Rows upserted by season_stats_loader have `stat_completeness = 'full'` (per epic Technical Notes "stat_completeness Provenance").
- [ ] **AC-5**: Test fixture includes realistic non-zero values for a representative sample of the 37 new columns (at minimum: pa, singles, r, hbp, tb, xbh, and 3+ advanced stats).
- [ ] **AC-6**: Test asserts exact stored values for every newly added column on at least one player row.
- [ ] **AC-7**: Test asserts `stat_completeness = 'full'` for the loaded row.
- [ ] **AC-8**: All existing tests pass.

## Technical Approach
Refer to epic Technical Notes "Column Inventory" (player_season_batting section) for the complete column list. Refer to `docs/gamechanger-stat-glossary.md` (API Field Name Mapping table, Batting sections) for API key → schema column name mapping. Key non-obvious mappings: `1B` → singles, `SOL` → sol, `SHB` → shb, `SHF` → shf, `2OUTRBI` → two_out_rbi, `3OUTLOB` → three_out_lob, `HARD` → hard, `LND` → lnd, `FLB` → flb, `2STRIKES` → two_strikes, `2S+3` → two_s_plus_3, `6+` → six_plus, `LOBB` → lobb. The existing loader pattern uses `offense.get("KEY")` — extend this to all 37 columns. The INSERT and ON CONFLICT UPDATE statements must include all new columns.

For response structure, see `docs/api/endpoints/get-teams-team_id-season-stats.md`. Batting stats live under `stats_data.players.<uuid>.stats.offense`. Test fixtures should use realistic data shaped from this response structure.

## Dependencies
- **E-116**: COMPLETED (archived 2026-03-17). No longer blocking.
- **Blocks**: E-117-03 (shared file: `season_stats_loader.py`)

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
