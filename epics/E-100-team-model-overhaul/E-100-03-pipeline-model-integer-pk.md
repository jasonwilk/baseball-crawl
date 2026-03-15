# E-100-03: Pipeline — membership_type + TeamRef + INTEGER PK

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`DONE`

## Description
After this story is complete, all pipeline code (crawlers, loaders, config, CLI) will use `membership_type` instead of `is_owned`, `classification` instead of `level`, and INTEGER team references instead of TEXT `team_id`. A `TeamRef` dataclass will separate internal DB identity from external GC identifiers. `CrawlConfig` will rename `owned_teams` to `member_teams`. All stub-INSERT patterns will use INTEGER PK. The season slug derivation will accept a configurable suffix.

## Context
With the clean schema (E-100-01) and the data layer migration (E-100-02), the pipeline code must be updated. SE's blast radius analysis identified ~8 `is_owned` sites plus 6 files with stub-INSERT patterns. Fresh-start simplification: no backward-compatible parsing, no placeholder rename pattern — clean break.

## Acceptance Criteria
- [x] **AC-1**: `TeamRef` dataclass exists with fields: `id: int`, `gc_uuid: str | None`, `public_id: str | None`.
- [x] **AC-2**: `CrawlConfig.owned_teams` is renamed to `CrawlConfig.member_teams`. `TeamEntry` gains `internal_id: int | None` field. `TeamEntry.is_owned` is removed. `TeamEntry.level` is renamed to `TeamEntry.classification`.
- [x] **AC-3**: `load_config_from_db()` queries `WHERE is_active=1 AND membership_type='member'`, SELECTs `classification` (not `level`), and populates `TeamEntry.internal_id` from `teams.id` and `TeamEntry.classification` from `teams.classification`.
- [x] **AC-4**: `load_config()` (YAML path) populates `internal_id` via a DB lookup before returning.
- [x] **AC-5**: All crawler stub-INSERT statements write `membership_type='tracked'` and let SQLite auto-assign INTEGER PK. The resulting ID is used for subsequent FK references.
- [x] **AC-6**: Scouting crawler, opponent crawler, and opponent_resolver use INTEGER team references for DB operations and GC identifiers for API calls.
- [x] **AC-7**: All loaders (game_loader, roster, season_stats_loader, scouting_loader) use INTEGER team references for FK INSERT/SELECT operations.
- [x] **AC-8**: `_derive_season_id()` in `scouting.py` accepts a `season_suffix: str` parameter (default `"spring-hs"`), threaded through `ScoutingCrawler.__init__()`.
- [x] **AC-9**: `src/cli/data.py` references to `is_owned` or `owned_teams` are updated.
- [x] **AC-10**: All existing pipeline tests pass. Tests that referenced `is_owned`, `owned_teams`, or `level` are updated to use `membership_type`, `member_teams`, and `classification` respectively.
- [x] **AC-11**: `load_config()` (YAML path) still works. YAML keys renamed: `owned_teams` to `member_teams`, `level` to `classification` per-entry (clean break — no backward-compat mapping).

## Technical Approach
Refer to the epic Technical Notes "TeamRef Pattern", "CrawlConfig Changes", and "Season Slug Parameterization" sections. The stub-INSERT pattern: check if team exists by `gc_uuid` or `public_id` (UNIQUE columns), INSERT if not, capture the ID, use that INTEGER ID for all FK references. This story does NOT modify `src/api/routes/` or `src/api/templates/`.

## Dependencies
- **Blocked by**: E-100-02 (needs db.py/auth.py to accept INTEGER team references)
- **Blocks**: E-100-06

## Files to Create or Modify
- `src/gamechanger/config.py`
- `src/gamechanger/types.py` (CREATE — TeamRef dataclass)
- `src/gamechanger/crawlers/scouting.py`
- `src/gamechanger/crawlers/opponent.py`
- `src/gamechanger/crawlers/opponent_resolver.py`
- `src/gamechanger/crawlers/roster.py` (references `owned_teams`)
- `src/gamechanger/crawlers/game_stats.py` (references `owned_teams`)
- `src/gamechanger/crawlers/schedule.py` (references `owned_teams`)
- `src/gamechanger/crawlers/player_stats.py` (references `owned_teams`)
- `src/gamechanger/loaders/game_loader.py`
- `src/gamechanger/loaders/roster.py`
- `src/gamechanger/loaders/season_stats_loader.py`
- `src/gamechanger/loaders/scouting_loader.py`
- `src/pipeline/crawl.py` (references `config.owned_teams`)
- `src/pipeline/load.py` (references `config.owned_teams`)
- `src/pipeline/bootstrap.py` (references `config.owned_teams`)
- `src/cli/data.py` (references `is_owned` and `config.owned_teams`)
- `config/teams.yaml` (RENAME `owned_teams` key to `member_teams`, `level` to `classification` per entry)
- `tests/test_config.py`
- `tests/test_scouting_crawler.py`
- `tests/test_scouting_loader.py`
- `tests/test_cli_data.py`
- `tests/test_cli_scout.py`
- `tests/test_scripts/test_crawl_orchestrator.py` (references `config.owned_teams`)
- `tests/test_scripts/test_load_orchestrator.py` (references `config.owned_teams`)
- `tests/test_bootstrap.py` (references `CrawlConfig(owned_teams=...)`)
- `tests/test_crawlers/test_opponent_resolver.py` (references `is_owned`, `owned_teams`)
- `tests/test_crawlers/test_opponent_crawler.py` (references `is_owned`, `owned_teams`)
- `tests/test_crawlers/test_game_stats_crawler.py` (references `owned_teams`)
- `tests/test_crawlers/test_schedule_crawler.py` (references `owned_teams`)
- `tests/test_crawlers/test_player_stats_crawler.py` (references `owned_teams`)
- `tests/test_crawlers/test_roster_crawler.py` (references `owned_teams`)
- `tests/test_loaders/test_season_stats_loader.py` (references `is_owned`)
- `tests/test_loaders/test_roster_loader.py` (references `is_owned`)
- `tests/test_loaders/test_game_loader.py` (references `owned_team_id`)

## Agent Hint
software-engineer

## Definition of Done
- [x] All acceptance criteria pass
- [x] Tests written and passing
- [x] Code follows project style (see CLAUDE.md)

## Notes
- `src/gamechanger/bridge.py` does NOT need changes — already correctly scoped, no `is_owned` references.
- `GameLoader.__init__` must change from `owned_team_id: str` to accept a `TeamRef` (or equivalent integer + uuid parameters). This cascades to `ScoutingLoader.load_team()`.
- `INSERT OR IGNORE` with AUTOINCREMENT: `lastrowid` returns 0 when IGNORE fires. Use a follow-up SELECT to get the existing row's `id`.
