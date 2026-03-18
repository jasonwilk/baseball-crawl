# E-117-01: Game Loader — Full Boxscore Stat Coverage + game_stream_id

## Epic
[E-117: Loader Stat Population](epic.md)

## Status
`TODO`

## Description
After this story is complete, `game_loader.py` will populate all 12 stat columns available from the boxscore endpoint (6 batting + 6 pitching) and thread `game_stream_id` to the `games` table. Stale "not in schema" comments will be corrected.

## Context
E-100-01 added these columns to the DDL but E-100-03 only converted the loaders to INTEGER PKs without expanding stat coverage. The game_loader currently has skip-debug sets (`_BATTING_SKIP_DEBUG`, `_BATTING_EXTRAS_SKIP_DEBUG`, `_PITCHING_SKIP_DEBUG`, `_PITCHING_EXTRAS_SKIP_DEBUG`) that log and drop valid API fields. These sets must be converted to mapping dicts. Additionally, `game_stream_id` is carried by `GameSummaryEntry` but never threaded to `_upsert_game()`.

## Acceptance Criteria
- [ ] **AC-1**: `_PlayerBatting` dataclass includes fields: `r`, `tb`, `hbp`, `shf`, `cs`, `e` (in addition to existing fields).
- [ ] **AC-2**: `_PlayerPitching` dataclass includes fields: `r`, `wp`, `hbp`, `pitches`, `total_strikes`, `bf` (in addition to existing fields).
- [ ] **AC-3**: `_upsert_batting()` INSERT and ON CONFLICT UPDATE include all 6 new batting columns.
- [ ] **AC-4**: `_upsert_pitching()` INSERT and ON CONFLICT UPDATE include all 6 new pitching columns.
- [ ] **AC-5**: The skip-debug sets (`_BATTING_SKIP_DEBUG`, `_BATTING_EXTRAS_SKIP_DEBUG`, `_PITCHING_SKIP_DEBUG`, `_PITCHING_EXTRAS_SKIP_DEBUG`) no longer contain keys that have corresponding schema columns. Keys that genuinely have no schema column (if any remain) may stay in skip sets with accurate comments.
- [ ] **AC-6**: Stale "not in schema" comments for R, TB, and any other columns that now exist in the schema are corrected or removed.
- [ ] **AC-7**: `_upsert_game()` accepts and writes `game_stream_id` to the `games` table. The value is sourced from `GameSummaryEntry.game_stream_id` and threaded through `_upsert_game_and_stats()`.
- [ ] **AC-8**: Test fixture includes non-zero values for all 12 new stat columns.
- [ ] **AC-9**: Test asserts exact stored values for each of the 6 new batting columns on at least one player row. Includes at least one case where a sparse extra (e.g., `hbp`, `cs`, `e`) is zero/absent.
- [ ] **AC-10**: Test asserts exact stored values for each of the 6 new pitching columns on at least one player row. Includes at least one case where a sparse extra (e.g., `wp`, `pitches`) is zero/absent.
- [ ] **AC-11**: Test asserts `games.game_stream_id` is populated for loaded games.
- [ ] **AC-12**: `stat_completeness` is NOT added to `_upsert_batting()` or `_upsert_pitching()` INSERT or ON CONFLICT UPDATE clauses. The schema default ('boxscore_only') handles INSERT. Omitting it from ON CONFLICT UPDATE preserves any future enrichment (e.g., play-by-play pipeline setting 'supplemented'). See epic Technical Notes "Future Enrichment Path."
- [ ] **AC-13**: `_PlayerPitching.hr` field (dead code — no `hr` column in `player_game_pitching` schema, never used in `_upsert_pitching`) is removed from the dataclass. If `HR` appears in `_PITCHING_EXTRAS_SKIP_DEBUG`, it should remain there (HR allowed is genuinely not in the boxscore pitching extras per the schema comment).
- [ ] **AC-14**: All existing tests pass.

## Technical Approach
Refer to epic Technical Notes "Column Inventory" (player_game_batting and player_game_pitching tables) for the exact column list and current loader disposition. Refer to `docs/gamechanger-stat-glossary.md` for API key → schema column name mapping. The glossary's "API Field Name Mapping" table is the authoritative source for translating boxscore response keys to database column names. For boxscore response structure, see `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md`.

**SHF note**: The glossary lists SHF in BATTING_EXTRA but the boxscore endpoint doc does not list SHF in observed batting extras. Use `dict.get("SHF")` — if the API returns it, it gets saved; if not, NULL. Both behaviors are correct for the nullable column.

Test fixtures should use realistic data shaped from actual boxscore API response structures. Reference `docs/api/endpoints/get-game-stream-processing-game_stream_id-boxscore.md` for the extras array format (sparse: `{stat_name, stats: [{player_id, value}]}`). The user has offered a data dump if needed for realistic values.

## Dependencies
- **E-116**: COMPLETED (archived 2026-03-17). No longer blocking.
- **Blocks**: E-117-04 (scouting loader aggregate expansion)

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py`
- `tests/test_loaders/test_game_loader.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-117-04**: After this story ships, `player_game_batting` rows will have `r`, `tb`, `hbp`, `shf`, `cs`, `e` populated and `player_game_pitching` rows will have `r`, `wp`, `hbp`, `pitches`, `total_strikes`, `bf` populated. E-117-04 needs to expand scouting aggregate queries to SUM these columns.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
