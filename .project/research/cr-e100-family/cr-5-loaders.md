# CR-5: Loaders Review

**Files reviewed:**
- `src/gamechanger/loaders/game_loader.py`
- `src/gamechanger/loaders/roster.py`
- `src/gamechanger/loaders/scouting_loader.py`
- `src/gamechanger/loaders/season_stats_loader.py`

**Cross-referenced:** `migrations/001_initial_schema.sql`, `src/gamechanger/types.py`, `src/gamechanger/loaders/__init__.py`

---

## Critical Issues

### 1. game_loader: Pitching main stat `R` (runs allowed) silently discarded despite schema column

**File:** `src/gamechanger/loaders/game_loader.py:99-100`

`_PITCHING_SKIP_DEBUG = {"R"}` with comment `# "R" is not in the schema.` -- but `player_game_pitching` **does** have `r INTEGER` (schema line 198: `r INTEGER,  -- total runs allowed`). The boxscore main stats provide `R` and the loader skips it with an incorrect comment. This is data loss on every game load.

### 2. game_loader: Pitching extras `WP`, `HBP`, `BF` silently discarded despite schema columns

**File:** `src/gamechanger/loaders/game_loader.py:102`

`_PITCHING_EXTRAS_SKIP_DEBUG = {"WP", "HBP", "#P", "TS", "BF", "HR"}` with comment `# Pitching extras not in schema:`. Three of these ARE in the `player_game_pitching` schema:
- `WP` -> `wp INTEGER` (schema line 203)
- `HBP` -> `hbp INTEGER` (schema line 204)
- `BF` -> `bf INTEGER` (schema line 207)

These are NOT in the CLAUDE.md "schema-ready, not yet populated" list (which only covers `pitches`/`total_strikes`), so they appear to be regular columns that should be populated. Available boxscore data is being silently discarded on every game load.

**Note:** `#P` (pitches) and `TS` (total_strikes) are explicitly listed in CLAUDE.md as "schema-ready, not yet populated" enriched stat columns, so skipping those is intentional. `HR` correctly has no column in `player_game_pitching` per the schema comment "Excluded: HR allowed."

### 3. scouting_loader: Double I/O on every boxscore file for UUID opportunism

**File:** `src/gamechanger/loaders/scouting_loader.py:436-462`

`_record_uuid_from_boxscore_path()` re-reads and re-parses every boxscore JSON file that `GameLoader.load_file()` already read and parsed. For a team with 30 games, this doubles the file I/O for boxscores. The GameLoader already calls `_ensure_team_row()` for opponent UUIDs during normal loading (line 423), making this "safety net" both redundant and wasteful.

---

## Warnings

### 1. game_loader: `_PlayerPitching.hr` field is dead code

**File:** `src/gamechanger/loaders/game_loader.py:159`

The `_PlayerPitching` dataclass defines `hr: int = 0` but the `_upsert_pitching` method (lines 884-907) never includes `hr` in the INSERT statement, and no code sets it. The field should be removed to avoid confusion.

### 2. game_loader: `_ensure_team_row` uses gc_uuid as team name

**File:** `src/gamechanger/loaders/game_loader.py:947-949`

When creating a stub team row for an opponent, the gc_uuid is used as the `name` column value: `VALUES (?, 'tracked', ?, 0)", (gc_uuid, gc_uuid)`. This produces UUID strings as team names in the database, which will display poorly in any UI. The same pattern appears in `roster.py:328-332` and `season_stats_loader.py:400-404`.

### 3. scouting_loader: Aggregate overwrites on partial load

**File:** `src/gamechanger/loaders/scouting_loader.py:121`

`_compute_season_aggregates()` runs unconditionally after boxscore loading, even if some boxscores had errors. The aggregates use `ON CONFLICT DO UPDATE`, so a partial load will overwrite previously correct season totals with incomplete sums. If a re-load succeeds with fewer games than before (e.g., a boxscore file was deleted), the aggregates silently shrink.

### 4. Duplicated `_ensure_team_row` / `_ensure_season_row` across three loaders

**Files:** `game_loader.py:934-980`, `roster.py:316-372`, `season_stats_loader.py:388-439`

Three nearly identical copies of `_ensure_team_row()` and `_ensure_season_row()` exist across game_loader, roster, and season_stats_loader. These are candidates for extraction to a shared helper. The scouting_loader avoids this by using its own `_ensure_season_row` and delegating team handling to the caller/GameLoader.

---

## Minor Issues

### 1. Inconsistent upsert strategy: roster.py docstring vs. implementation

**File:** `src/gamechanger/loaders/roster.py:8-9`

Module docstring says "Upserts are performed via `INSERT OR REPLACE` (players) and `INSERT OR IGNORE` (team_rosters)." But the actual implementation uses `ON CONFLICT DO UPDATE` for both (lines 274-283 for players, lines 299-308 for team_rosters). The docstring is stale.

### 2. scouting_loader: Schema comment contradiction about HR in boxscore extras

The schema comment on `player_game_pitching` says "Excluded: HR allowed (not present in boxscore pitching extras)." But `game_loader.py:102` lists `HR` in `_PITCHING_EXTRAS_SKIP_DEBUG`, implying HR IS present in boxscore extras and explicitly skipped. One of these is wrong -- either HR appears in extras (schema comment is wrong) or it doesn't (loader skip is unnecessary).

### 3. Unused import in scouting_loader

**File:** `src/gamechanger/loaders/scouting_loader.py:47`

`from typing import Any` is imported but never used in any type annotation in the file.

---

## Observations

### Positive patterns

1. **TeamRef adherence**: `game_loader` correctly uses `self._team_ref.id` for own-team FK inserts (line 415). `scouting_loader` correctly receives `team_id: int` and builds a `TeamRef` via DB lookup (lines 113, 129-144). No phantom team creation from `gc_uuid=None`.

2. **Phantom team prevention**: `game_loader._detect_team_keys()` (lines 529-541) properly handles `gc_uuid=None` case by logging a warning and leaving `own_key=None`, rather than crashing or creating a phantom row.

3. **Idempotency**: All upserts use `ON CONFLICT` clauses correctly. Re-running any loader produces the same database state.

4. **SQL safety**: All queries use parameterized `?` placeholders. No SQL injection risk.

5. **IP-to-ip_outs conversion**: Both `game_loader` (line 709) and `season_stats_loader` (lines 57-72) correctly convert decimal IP to integer outs via `round(ip * 3)`.

6. **Scouting aggregation correctness**: The season aggregate queries in `scouting_loader` (lines 342-430) correctly JOIN `games` to access `season_id` (which isn't on `player_game_batting`/`player_game_pitching` directly), and filter by both `team_id` AND `season_id` -- no cross-scope data leakage.

7. **public_id type guard**: `scouting_loader.load_team()` receives `team_id: int` directly (not a public_id), so the guard against `None` public_id is the caller's responsibility. The `_build_team_ref()` method (line 129) gracefully handles missing DB rows by returning a TeamRef with null identifiers.

### Deferred enriched columns (intentional, not a finding)

`pitches` (#P) and `total_strikes` (TS) on `player_game_pitching` are listed in CLAUDE.md as "schema-ready, not yet populated." The loader correctly skips these for now, though they ARE available in boxscore extras and could be populated when a future story addresses enrichment.
