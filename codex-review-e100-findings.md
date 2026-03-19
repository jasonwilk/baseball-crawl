# Code Review Findings: E-100 + E-114 + E-115

Date: 2026-03-16

## Summary
Two implementation issues remain in the current state. The first is a real runtime regression: `bb data load` still defaults to YAML config, but the game loader now requires an INTEGER `TeamRef.id`, so the default path writes `team_id=0` and fails foreign-key checks. The second is silent data loss: the game, season-stats, and scouting loaders still populate only a narrow legacy subset of stats even though the current schema includes many more endpoint-backed columns.

## Priority 1: Bugs and Regressions
- `src/pipeline/load.py:71`, `src/pipeline/load.py:74`, `src/gamechanger/config.py:78`, `src/gamechanger/config.py:120`, `src/cli/data.py:133`, `src/gamechanger/loaders/game_loader.py:415`: the default `bb data load` path is broken for game ingestion. `bb data load` defaults to `--source yaml`, `load_config()` leaves `TeamEntry.internal_id` unset unless a DB path is provided, and `_run_game_loader()` then constructs `TeamRef(id=team.internal_id or 0, ...)`. Since `GameLoader` now uses `self._team_ref.id` directly for the owning team FK, game loads from YAML-configured teams attempt to write `teams.id=0` and fail with foreign-key errors instead of loading data.
- `src/gamechanger/loaders/game_loader.py:71`, `src/gamechanger/loaders/game_loader.py:78`, `src/gamechanger/loaders/game_loader.py:82`, `src/gamechanger/loaders/game_loader.py:89`, `src/gamechanger/loaders/game_loader.py:99`, `src/gamechanger/loaders/game_loader.py:102`, `src/gamechanger/loaders/game_loader.py:133`, `src/gamechanger/loaders/game_loader.py:149`, `src/gamechanger/loaders/game_loader.py:620`, `src/gamechanger/loaders/game_loader.py:624`, `src/gamechanger/loaders/game_loader.py:632`, `src/gamechanger/loaders/game_loader.py:699`, `src/gamechanger/loaders/game_loader.py:710`, `src/gamechanger/loaders/game_loader.py:842`, `src/gamechanger/loaders/game_loader.py:886`, `src/gamechanger/loaders/season_stats_loader.py:257`, `src/gamechanger/loaders/season_stats_loader.py:321`, `src/gamechanger/loaders/scouting_loader.py:342`, `src/gamechanger/loaders/scouting_loader.py:366`, `src/gamechanger/loaders/scouting_loader.py:396`, `src/gamechanger/loaders/scouting_loader.py:414`, `migrations/001_initial_schema.sql:150`, `migrations/001_initial_schema.sql:187`, `migrations/001_initial_schema.sql:218`, `migrations/001_initial_schema.sql:292`: the loaders still drop many endpoint-backed columns that exist in the live schema. Examples: `player_game_batting.r/hbp/cs/e`, `player_game_pitching.r/wp/hbp/pitches/total_strikes/bf`, `player_season_batting.pa/singles/r/hbp/shf/...`, and `player_season_pitching.bf/bk/wp/hbp/...` are defined in `001_initial_schema.sql`, but the current loader mappings either log them as “not in schema” or never include them in `INSERT ... ON CONFLICT` statements. The result is silent partial ingestion and permanently NULL data in columns that the schema says should be backed by the API payloads.

## Priority 2: Missing Tests
- `tests/test_scripts/test_load_orchestrator.py:196`, `tests/test_scripts/test_load_orchestrator.py:214`: there is no coverage for the owning team’s INTEGER PK in the YAML load path. The game-loader wiring test asserts `season_id` and `owned_team_ref.gc_uuid`, but never asserts a valid `owned_team_ref.id` or exercises the real loader against YAML-sourced config. That gap allowed the `TeamRef(id=0)` regression above to ship.
- `tests/test_loaders/test_game_loader.py:6`, `tests/test_loaders/test_game_loader.py:8`, `tests/test_loaders/test_game_loader.py:300`, `tests/test_loaders/test_game_loader.py:309`, `tests/test_loaders/test_game_loader.py:316`, `tests/test_loaders/test_game_loader.py:325`, `tests/test_loaders/test_season_stats_loader.py:6`, `tests/test_loaders/test_season_stats_loader.py:206`, `tests/test_loaders/test_season_stats_loader.py:217`, `tests/test_loaders/test_season_stats_loader.py:255`, `tests/test_loaders/test_season_stats_loader.py:268`, `tests/test_scouting_loader.py:247`, `tests/test_scouting_loader.py:257`, `tests/test_scouting_loader.py:530`, `tests/test_scouting_loader.py:541`: the loader tests only assert a minimal stat subset, not the full set of columns that the schema now exposes. There is no test that verifies boxscore `R/HBP/CS/E/WP/#P/TS/BF` or season-stats `PA/1B/HBP/SHF/BK/BF/...` persist into the corresponding tables, so the silent data drops above are currently invisible to the test suite.

## Priority 3: Credential and Security Risks
None

## Priority 4: Schema Drift
None

## Priority 5: Planning/Implementation Mismatch
None

## Priority 6: Style and Convention Violations
- `src/api/db.py:23`, `src/api/db.py:34`: `src/api/db.py` still resolves its default database path from `./data/app.db` via `Path(raw).resolve()`, which is cwd-relative. `CLAUDE.md` explicitly requires `src/` modules to derive repo-root-relative paths from `Path(__file__).resolve().parents[N]` rather than the current working directory. This is a convention violation and can point the app at the wrong database when the process is launched outside the repo root.

## Cross-Cutting Concerns
- No `is_owned`, `owned_teams`, `_generate_opponent_team_id`, `_resolve_team_ids` legacy usage, or stale `display_name` / `user.is_admin` template references remained in the requested implementation files.
- The reviewed SQL writes in `src/` use parameter binding rather than string interpolation. I did not find a SQL injection issue in the requested files.
- The reviewed inline test schemas include the production partial unique indexes for `teams.gc_uuid` and `teams.public_id`.
- `rg -n "xfail" tests` returned no matches.
- The dashboard/admin template implementation matches E-114’s shipped `user.email` / `admin_user.email` convention; the review brief’s `user.username` wording appears to be stale, not a code defect.

## E-115 Story Review
The E-115 epic and both story files are complete and internally consistent. Their acceptance criteria are concrete, the referenced source files and routes exist, and I did not find stale pre-E-100 concepts in the story definitions themselves.
