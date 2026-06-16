# E-239-04: Delete the Member-Sync Pipeline, Member Crawlers/Loaders, Scripts, `teams.yaml`, `config.py`

## Epic
[E-239: Decouple Pipeline Imports, Then Remove the Unused Surfaces](epic.md)

## Status
`TODO`

## Description
After this story is complete, the member-team sync vertical is gone: the `src/pipeline/*` orchestration, the member-only crawlers and loaders, the wrapper scripts, `teams.yaml`, and `src/gamechanger/config.py` are deleted. Every module deleted here has zero remaining importer (its callers were removed in E-239-01/02/03). The reports protected core and its transitive deps are untouched.

## Context
This is a **callee-deletion** story — it runs after the caller surfaces are gone (admin extraction in 01, dashboard in 02, CLI commands in 03), so each module here has no live importer. The authoritative delete set and the must-survive set are Technical Notes §D (member-sync group) and §E, sourced from the SE artifact §2b/§2c/§6/§7. The reports plays/spray data comes from the scouting crawlers (`scouting.py`/`scouting_spray.py`) and `PlaysLoader`, NOT the member `crawlers/plays.py`/`spray_chart.py` (verified member-only), so those member crawlers are delete-safe while `plays_loader.py`/`game_loader.py` stay.

## Acceptance Criteria
- [ ] **AC-1**: The member-sync deletion set in Technical Notes §D is removed: `src/pipeline/{crawl,load,bootstrap,trigger}.py` (and `src/pipeline/__init__.py` if it becomes empty/dead); member crawlers `crawlers/{roster,schedule,opponent,player_stats,game_stats,plays,spray_chart}.py`; member loaders `loaders/{roster,schedule_loader,season_stats_loader,spray_chart_loader}.py`; `scripts/{crawl,load,bootstrap}.py`; `teams.yaml`. The app starts and `bb --help` works.
- [ ] **AC-2 (preserve)**: The reports transitive deps are untouched and functional: `loaders/game_loader.py`, `loaders/plays_loader.py`, `loaders/backfill.py`, and the scouting crawlers/loaders (`crawlers/scouting.py`, `crawlers/scouting_spray.py`, `loaders/scouting_loader.py`, `loaders/scouting_spray_loader.py`), plus `loaders/__init__.py` (the season-derivation primitive) per Technical Notes §E/§C.
- [ ] **AC-3**: `src/gamechanger/config.py` (and `teams.yaml`) are deleted only after verifying (grep) `config.py` has zero importer outside the deletion set (its sole users are crawl/load/trigger/bootstrap + member-crawler `__main__` blocks per SE §2d); if any surviving/protected module imports it, the deletion is NOT performed and the dependency is flagged to PM.
- [ ] **AC-4**: No surviving module imports any deleted module — verified by grep across `src/`, `scripts/`, `tests/`. Epic A goldens + `bb report verify-aggregates` parity unchanged/green (Technical Notes §A).
- [ ] **AC-5**: Tests handled per the discrimination rule (Technical Notes §F / SE §4): the member crawler/loader test files, `test_bootstrap.py`, `test_trigger.py`, the `test_scripts/test_*_orchestrator.py`, and `test_config.py` (delete only if config.py is confirmed deleted) are removed; `test_game_start_time.py` is ADJUSTED (drop the `ScheduleLoader` assertions, keep `GameLoader`/`ScoutingLoader` coverage); `tests/test_script_entry_points.py` is adjusted if it asserts the deleted scripts exist. Full suite green.

## Technical Approach
Delete the §D member-sync modules + scripts + `teams.yaml`, then `config.py` after the AC-3 importer verification. Run a repo-wide grep (`src/`, `scripts/`, `tests/`) proving no surviving importer remains, treating the §E preserve list as off-limits. Apply the test-discrimination rule per deleted module, including the `test_game_start_time.py` adjust and the `test_script_entry_points.py` check. Do not edit any `.claude/` context-layer file — that is E-239-06. Re-grep live paths per Technical Notes §B.

## Dependencies
- **Blocked by**: E-239-01 (chain 1 — `trigger` app importer gone), E-239-02 (dashboard not a hidden importer), E-239-03 (chain 2 — CLI importers gone)
- **Blocks**: E-239-05, E-239-06

## Files to Create or Modify
- DELETE `src/pipeline/crawl.py`, `load.py`, `bootstrap.py`, `trigger.py` (+ `__init__.py` if empty/dead)
- DELETE `src/gamechanger/crawlers/{roster,schedule,opponent,player_stats,game_stats,plays,spray_chart}.py`
- DELETE `src/gamechanger/loaders/{roster,schedule_loader,season_stats_loader,spray_chart_loader}.py`
- DELETE `scripts/crawl.py`, `scripts/load.py`, `scripts/bootstrap.py`
- DELETE `teams.yaml`
- DELETE `src/gamechanger/config.py` (only after AC-3 importer verification)
- PRESERVE (do not touch): the §E reports transitive deps + scouting modules + season-derivation primitive
- DELETE / ADJUST tests per SE §4 (member crawler/loader tests, `test_bootstrap`, `test_trigger`, `test_scripts/*orchestrator`, `test_config`; adjust `test_game_start_time`, `test_script_entry_points`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-239-05**: `trigger.py` (importer of `opponent_seeder`/`opponent_resolver`) is gone, removing the last pipeline coupling to the opponent-discovery modules.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests deleted/adjusted and passing; import graph grep-clean
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
High-LOC but mechanically uniform deletion + test-scope discovery.

**Data-loss guardrail (epic Technical Notes §H / DE finding S3):** this story deletes `season_stats_loader.py` (the sole `full`/`supplemented` season-row producer). That does NOT make the `full`/`supplemented` provenance guards in `canonical_recompute` (`src/db/season_aggregates.py`) or `aggregate_parity.py` removable — legacy member rows persist in any un-reset production DB, so removing those guards would re-open the E-237 data-loss class. Do NOT touch those guards in this story.
