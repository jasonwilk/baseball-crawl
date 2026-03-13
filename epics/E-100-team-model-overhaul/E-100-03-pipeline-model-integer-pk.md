# E-100-03: Pipeline — is_owned → membership_type + TeamRef + INTEGER PK

## Epic
[E-100: Team Model Overhaul](epic.md)

## Status
`TODO`

## Description
After this story is complete, all pipeline code (crawlers, loaders, config, CLI) will use `membership_type` instead of `is_owned`, `classification` instead of `level`, and INTEGER team references instead of TEXT `team_id`. A `TeamRef` dataclass will separate internal DB identity from external GC identifiers. `CrawlConfig` will rename `owned_teams` to `member_teams` with `internal_id: int` populated from the DB. All stub-INSERT patterns in crawlers/loaders will use the INTEGER PK + `lastrowid` pattern. The season slug derivation will accept a configurable suffix.

## Context
With the clean schema rewrite (E-100-01) and the data layer migration (E-100-02), the pipeline code must be updated to: (1) rename is_owned→membership_type and owned_teams→member_teams, (2) use INTEGER team references for all DB operations, and (3) use `gc_uuid`/`public_id` for API operations via the TeamRef pattern. SE's blast radius analysis identified ~8 `is_owned` sites plus 6 files with stub-INSERT patterns that need the `lastrowid` refactor.

## Acceptance Criteria
- [ ] **AC-1**: `TeamRef` dataclass exists with fields: `id: int`, `gc_uuid: str`, `public_id: str | None`.
- [ ] **AC-2**: `CrawlConfig.owned_teams` is renamed to `CrawlConfig.member_teams`. `TeamEntry` gains `internal_id: int | None` field. `TeamEntry.is_owned` is removed.
- [ ] **AC-3**: `load_config_from_db()` queries `WHERE is_active=1 AND membership_type='member'` and populates `TeamEntry.internal_id` from `teams.id`.
- [ ] **AC-4**: `load_config()` (YAML path) populates `internal_id` via a DB lookup before returning — callers always receive resolved `TeamEntry` objects.
- [ ] **AC-5**: All crawler stub-INSERT statements that previously wrote `is_owned=0` now write `membership_type='tracked'` and let SQLite auto-assign the INTEGER PK. The resulting `lastrowid` (or lookup by `gc_uuid`/`public_id`) is used for subsequent FK references.
- [ ] **AC-6**: `src/gamechanger/crawlers/scouting.py`, `opponent.py`, `opponent_resolver.py` use INTEGER team references for DB operations and GC identifiers for API calls.
- [ ] **AC-7**: `src/gamechanger/loaders/game_loader.py`, `roster.py`, `season_stats_loader.py`, `scouting_loader.py` use INTEGER team references for all FK INSERT/SELECT operations.
- [ ] **AC-8**: `_derive_season_id()` in `scouting.py` accepts a `season_suffix: str` parameter (default `"spring-hs"`), threaded through `ScoutingCrawler.__init__()`.
- [ ] **AC-9**: `src/api/db.py` functions that reference `is_owned` are updated to use `membership_type` (if any were missed by E-100-02).
- [ ] **AC-10**: `src/cli/data.py` references to `is_owned` or `owned_teams` are updated.
- [ ] **AC-11**: All existing tests pass. Tests that reference `is_owned` or `owned_teams` in setup/assertions are updated.
- [ ] **AC-12**: `load_config()` (YAML path) still works — the YAML key `owned_teams` maps to `member_teams` (backward-compatible parsing or key renamed with a note).

## Technical Approach
Refer to the epic Technical Notes "TeamRef Pattern", "CrawlConfig Changes", and "Season Slug Parameterization" sections. The stub-INSERT pattern: (1) check if team exists by `gc_uuid` or `public_id` (UNIQUE columns), (2) if not, INSERT with auto-assigned INTEGER PK, (3) capture the ID via `lastrowid` or SELECT, (4) use that INTEGER ID for all FK references. This story does NOT modify `src/api/routes/` or `src/api/templates/` — those are handled by E-100-04 and E-100-05.

## Dependencies
- **Blocked by**: E-100-02 (needs db.py/auth.py to accept INTEGER team references)
- **Blocks**: E-100-06

## Files to Create or Modify
- `src/gamechanger/config.py`
- `src/gamechanger/types.py` (CREATE — TeamRef dataclass)
- `src/gamechanger/crawlers/scouting.py`
- `src/gamechanger/crawlers/opponent.py`
- `src/gamechanger/crawlers/opponent_resolver.py`
- `src/gamechanger/loaders/game_loader.py`
- `src/gamechanger/loaders/roster.py`
- `src/gamechanger/loaders/season_stats_loader.py`
- `src/gamechanger/loaders/scouting_loader.py`
- `src/cli/data.py`
- `config/teams.yaml` (if YAML key renamed)
- `tests/test_config.py`
- `tests/test_scouting_crawler.py`
- `tests/test_scouting_loader.py`
- `tests/test_cli_data.py`
- `tests/test_cli_scout.py`

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-100-06**: All pipeline code uses `membership_type` and INTEGER team references. The add-team flow can rely on these being the standard patterns.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The YAML config (`config/teams.yaml`) currently uses `owned_teams` as the key. The implementer should choose the simpler approach: rename the YAML key to `member_teams` (config file has known contents) or accept both keys with deprecation alias.
- `src/gamechanger/bridge.py` does NOT need changes — it's already correctly scoped and doesn't reference `is_owned`.
