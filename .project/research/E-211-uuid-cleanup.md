# E-211: UUID Contamination Data Cleanup Procedure

## Purpose

One-time operator procedure to clean up data contaminated by the opponent-perspective
UUID bug fixed in E-211-01 and E-211-02. Three pipeline paths previously stored
boxscore-derived opponent-perspective UUIDs as `gc_uuid` on tracked team rows,
causing duplicate players and missing spray charts in standalone reports.

**Known affected team**: Waverly Vikings Varsity (team 93) -- confirmed wrong
`gc_uuid = 18bf858f...` (opponent-perspective); correct `gc_uuid = 370cb40c...`
(from `POST /search`). One opponent-perspective game created ~20 duplicate player
records.

## Prerequisites

- E-211-01 deployed (pipeline no longer contaminates gc_uuid)
- E-211-02 deployed (report generator always search-resolves for tracked teams)
- Database backup taken before running any cleanup SQL

## Phase 1: NULL Contaminated gc_uuids

### 1a. Identify contaminated tracked teams

All tracked teams with a `gc_uuid` AND a `public_id` are candidates. The
`public_id` ensures the search resolver can re-resolve the correct gc_uuid
later. Teams without `public_id` cannot be re-resolved and are left untouched.

```sql
-- REVIEW: Tracked teams with gc_uuid that will be NULLed
SELECT id, name, gc_uuid, public_id, season_year
FROM teams
WHERE membership_type = 'tracked'
  AND gc_uuid IS NOT NULL
  AND public_id IS NOT NULL
ORDER BY id;
```

### 1b. NULL the gc_uuids

```sql
-- EXECUTE: NULL gc_uuid on tracked teams (member teams untouched)
UPDATE teams
SET gc_uuid = NULL
WHERE membership_type = 'tracked'
  AND gc_uuid IS NOT NULL
  AND public_id IS NOT NULL;
```

Verify:

```sql
-- VERIFY: No tracked team with public_id should have gc_uuid set
SELECT COUNT(*) AS remaining
FROM teams
WHERE membership_type = 'tracked'
  AND gc_uuid IS NOT NULL
  AND public_id IS NOT NULL;
-- Expected: 0
```

## Phase 2: Remove Opponent-Perspective Game Data

Opponent-perspective games are games where the scouted team appears as an
opponent in another team's boxscore, not in the scouted team's own schedule.
These games were loaded because the old plays query used a broad
`WHERE home_team_id = ? OR away_team_id = ?` that picked up cross-pipeline games.

### 2a. Identify the scouted team's own games (filesystem)

For each affected tracked team, list the `game_id`s from boxscore filenames
in the team's scouting directory. These are the legitimate games from the
team's own schedule.

```bash
# List game_ids from boxscore files (each filename stem = event_id = game_id)
ls data/raw/{CRAWL_SEASON_ID}/scouting/{PUBLIC_ID}/boxscores/*.json \
  | xargs -n1 basename | sed 's/\.json$//' | sort
```

Example for Waverly (public_id = `8O8bTolVfb9A`, crawl_season_id = `2026-spring-hs`):

```bash
ls data/raw/2026-spring-hs/scouting/8O8bTolVfb9A/boxscores/*.json \
  | xargs -n1 basename | sed 's/\.json$//' | sort
```

### 2b. Identify opponent-perspective games (SQL)

Use the filesystem game list from step 2a to find games in the DB that involve
the scouted team but are NOT in the team's own boxscore files. Replace
`{TEAM_ID}`, `{SEASON_ID}`, and the `IN (...)` list with the actual values.

**Important**: The `season_id` filter must match the crawl season used in
step 2a. The boxscore file list is season-specific; without the season filter,
games from other seasons would be falsely classified as contaminated.

```sql
-- REVIEW: Games involving the scouted team that are NOT in its own schedule.
-- These are opponent-perspective games loaded by other teams' pipelines.
SELECT game_id, home_team_id, away_team_id, game_date, season_id
FROM games
WHERE (home_team_id = {TEAM_ID} OR away_team_id = {TEAM_ID})
  AND season_id = '{SEASON_ID}'
  AND game_id NOT IN (
    -- Paste game_ids from step 2a, one per line, quoted:
    -- 'game-id-1',
    -- 'game-id-2',
    -- ...
  )
ORDER BY game_date;
```

Save the resulting `game_id` list -- these are the opponent-perspective games
whose data will be deleted.

### 2c. Delete opponent-perspective game data (FK-safe order)

Delete all downstream data from the opponent-perspective games. The order
respects FK constraints (children before parents).

**Replace `{OPP_GAME_IDS}` with the comma-separated quoted game_ids from step 2b.**

```sql
-- Step 1: play_events (child of plays)
DELETE FROM play_events
WHERE play_id IN (
  SELECT id FROM plays WHERE game_id IN ({OPP_GAME_IDS})
);

-- Step 2: plays
DELETE FROM plays
WHERE game_id IN ({OPP_GAME_IDS});

-- Step 3: player_game_batting
DELETE FROM player_game_batting
WHERE game_id IN ({OPP_GAME_IDS});

-- Step 4: player_game_pitching
DELETE FROM player_game_pitching
WHERE game_id IN ({OPP_GAME_IDS});

-- Step 5: spray_charts
DELETE FROM spray_charts
WHERE game_id IN ({OPP_GAME_IDS});

-- Step 6: reconciliation_discrepancies
DELETE FROM reconciliation_discrepancies
WHERE game_id IN ({OPP_GAME_IDS});
```

After game-scoped data is deleted, clean up aggregate and roster rows for
orphaned players. These are players who only existed because of the
opponent-perspective game data.

```sql
-- Step 7: player_season_batting (orphaned rows for affected team)
DELETE FROM player_season_batting
WHERE team_id = {TEAM_ID}
  AND player_id NOT IN (
    SELECT DISTINCT player_id FROM player_game_batting WHERE team_id = {TEAM_ID}
  );

-- Step 8: player_season_pitching (orphaned rows for affected team)
DELETE FROM player_season_pitching
WHERE team_id = {TEAM_ID}
  AND player_id NOT IN (
    SELECT DISTINCT player_id FROM player_game_pitching WHERE team_id = {TEAM_ID}
  );

-- Step 9: team_rosters (orphaned roster entries for affected team)
DELETE FROM team_rosters
WHERE team_id = {TEAM_ID}
  AND player_id NOT IN (
    SELECT DISTINCT player_id FROM player_game_batting WHERE team_id = {TEAM_ID}
    UNION
    SELECT DISTINCT player_id FROM player_game_pitching WHERE team_id = {TEAM_ID}
  );

-- Step 10: players (orphaned -- no remaining rows in any stat table)
DELETE FROM players
WHERE player_id NOT IN (SELECT DISTINCT player_id FROM player_game_batting)
  AND player_id NOT IN (SELECT DISTINCT player_id FROM player_game_pitching)
  AND player_id NOT IN (SELECT DISTINCT player_id FROM team_rosters)
  AND player_id NOT IN (SELECT DISTINCT batter_id FROM plays)
  AND player_id NOT IN (
    SELECT DISTINCT pitcher_id FROM plays WHERE pitcher_id IS NOT NULL
  );
```

### 2d. Remove stale plays JSON files

After deleting opponent-perspective game data from the DB, remove the
corresponding plays JSON files from disk to prevent the PlaysLoader from
re-loading them on future runs.

```bash
# For each opponent-perspective game_id from step 2b:
rm -v data/raw/{CRAWL_SEASON_ID}/scouting/{PUBLIC_ID}/plays/{OPP_GAME_ID}.json
```

Example for Waverly with one opponent-perspective game `game-opp-123`:

```bash
rm -v data/raw/2026-spring-hs/scouting/8O8bTolVfb9A/plays/game-opp-123.json
```

## Phase 3: Verification

### 3a. All tracked team gc_uuids are NULL (post-Phase 1, pre-re-resolution)

```sql
-- VERIFY: Every tracked team with public_id should have gc_uuid = NULL
-- after Phase 1. This confirms the NULLing was applied correctly.
SELECT id, name, gc_uuid, public_id
FROM teams
WHERE membership_type = 'tracked'
  AND gc_uuid IS NOT NULL
  AND public_id IS NOT NULL;
-- Expected: 0 rows
```

After Phase 4 re-resolution, verify the new gc_uuids are canonical (from
`POST /search`), not opponent-perspective. The best check is to confirm
no tracked team's gc_uuid matches any opponent key from boxscore files.
This can be spot-checked for known cases (e.g., Waverly should have
`370cb40c...`, not `18bf858f...`):

```sql
-- SPOT-CHECK: Verify Waverly's gc_uuid was correctly re-resolved
SELECT id, name, gc_uuid FROM teams WHERE id = 93;
-- gc_uuid should be 370cb40c... (from POST /search), not 18bf858f... (opponent key)
```

### 3b. No orphaned data remains from opponent-perspective games

```sql
-- VERIFY: No plays remain for deleted opponent-perspective games
SELECT COUNT(*) FROM plays WHERE game_id IN ({OPP_GAME_IDS});
-- Expected: 0

-- VERIFY: No orphaned play_events (play_id references a nonexistent play)
SELECT COUNT(*) FROM play_events
WHERE play_id NOT IN (SELECT id FROM plays);
-- Expected: 0

-- VERIFY: No orphaned player_game_batting for deleted games
SELECT COUNT(*) FROM player_game_batting WHERE game_id IN ({OPP_GAME_IDS});
-- Expected: 0

-- VERIFY: No orphaned player_game_pitching for deleted games
SELECT COUNT(*) FROM player_game_pitching WHERE game_id IN ({OPP_GAME_IDS});
-- Expected: 0
```

### 3c. Affected team player count is reasonable

```sql
-- VERIFY: Check player count for affected team (should decrease after cleanup)
SELECT COUNT(DISTINCT player_id) AS player_count
FROM team_rosters
WHERE team_id = {TEAM_ID};
```

## Phase 4: Re-Resolution and Pipeline Re-Run

After cleanup, re-run the scouting pipeline to re-resolve gc_uuids via
`POST /search` and regenerate clean data.

```bash
# Re-run full scouting pipeline for all tracked teams
bb data scout
```

This will:
1. Re-resolve `gc_uuid` via `POST /search` for all tracked teams with `public_id`
2. Re-crawl schedules, rosters, and boxscores
3. Re-load all data with correct team identifiers
4. Re-crawl spray charts using the correct gc_uuid
5. Re-crawl and load plays data scoped to the team's own schedule

### Post-pipeline verification

```sql
-- VERIFY: gc_uuid re-resolved for tracked teams
SELECT id, name, gc_uuid, public_id
FROM teams
WHERE membership_type = 'tracked'
  AND public_id IS NOT NULL
ORDER BY id;
-- gc_uuid should now be populated with canonical UUIDs from POST /search
```

### Catch name-variation duplicates

The E-211-01 fix uses name+season_year dedup (step 3 of `ensure_team_row`)
instead of gc_uuid matching. This may occasionally create duplicate team rows
when opponent names vary slightly across games (e.g., "Waverly" vs "Waverly
Vikings"). Run the dedup tool to catch and merge these:

```bash
# Dry run first to review
bb data dedup

# Execute merges if needed
bb data dedup --execute
```

## Summary of Commands

```bash
# 1. Backup database
cp data/app.db data/app.db.bak-e211

# 2. Run Phase 1 and Phase 2 SQL in sqlite3
sqlite3 data/app.db < cleanup.sql   # or paste interactively

# 3. Remove stale plays JSON files (Phase 2d)
# rm -v data/raw/.../plays/{opp_game_id}.json

# 4. Re-run scouting pipeline
bb data scout

# 5. Check for name-variation duplicates
bb data dedup

# 6. Verify results (Phase 3 queries)
```
