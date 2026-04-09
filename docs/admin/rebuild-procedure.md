# Clean-Slate Rebuild Procedure (E-220)

This guide covers wiping and rebuilding the database under the perspective-aware architecture introduced in E-220. After this procedure, every stat row carries `perspective_team_id` and the scouting pipeline operates fully in-memory (no files in `data/raw/{season}/scouting/`).

**This is a manual procedure. No automation script is provided.**

> **WARNING: E-220 is not an in-place upgrade.** The database schema was rewritten. You MUST wipe `data/app.db` before restarting the application. If you skip the wipe step, migrations will silently leave your database with the pre-E-220 schema and the application will fail at startup with a schema assertion error.

---

## Prerequisites

- Valid GameChanger credentials (`bb creds check` passes)
- Docker Compose stack running (`docker compose up -d`)
- App health check passing: `curl -s http://localhost:8001/health`

---

## What Gets Wiped

| Target | Wiped? | Notes |
|--------|--------|-------|
| `data/app.db` (SQLite database) | Yes | Full schema rebuild via migrations |
| `data/raw/{season}/scouting/` | Yes | Stale disk-cached scouting files |
| `data/raw/{season}/teams/` | **No** | Own-team crawl cache is retained |
| `data/reports/` | Yes | Reports regenerated from fresh data |

**Important**: Own-team data in `data/raw/{season}/teams/` is NOT wiped. This directory contains member-team boxscores, game summaries, and other crawled data that is expensive to re-fetch. The member-team pipeline reads from these files and they remain valid under the new schema.

---

## Step 1: Stop the App

```bash
docker compose stop app
```

---

## Step 2: Wipe the Database

> **DO NOT SKIP THIS STEP.** In-place upgrades are not supported for E-220 schema changes. The migration runner will not detect that `001_initial_schema.sql` was rewritten and will leave your database in a broken state.

```bash
bb db reset
```

This drops `data/app.db`, recreates it, applies all migrations (including E-220's consolidated `001_initial_schema.sql` with `perspective_team_id` columns), and seeds placeholder data.

---

## Step 3: Wipe the Scouting Cache

Remove disk-cached scouting files. The in-memory pipeline (E-220-05/E-220-10) no longer writes to these directories, but stale files from pre-E-220 runs must be cleaned.

```bash
# Remove scouting directories (games.json, roster.json, boxscores/, spray/)
find data/raw/*/scouting -mindepth 1 -delete 2>/dev/null
rmdir data/raw/*/scouting 2>/dev/null

# Remove generated reports (will be regenerated)
rm -rf data/reports/*
```

Verify own-team data is intact:

```bash
ls data/raw/*/teams/
# Should list team UUID directories with games/, spray/, etc.
```

---

## Step 4: Restart the App

```bash
docker compose up -d --build app
```

Verify health:

```bash
curl -s http://localhost:8001/health
```

Expected: `{"status": "ok", "db": "connected"}`.

---

## Step 5: Sync Member Teams

Load own-team data from the retained disk cache:

```bash
bb data crawl
bb data load
```

This populates games, batting, pitching, plays, and spray charts for member teams. All rows will have `perspective_team_id` set to the member team's integer PK.

---

## Step 6: Scout Tracked Opponents

Run the full scouting pipeline for all tracked opponents:

```bash
bb data scout
```

This runs the in-memory scouting pipeline (E-220-05): crawl schedule + roster + boxscores, then load -- all without writing files to `data/raw/`. Spray charts are crawled and loaded in-memory (E-220-10). Season aggregates are computed with perspective filtering (E-220-07).

For a single opponent:

```bash
bb data scout --team <public_id>
```

---

## Step 7: Regenerate Reports

Regenerate scouting reports for tracked opponents:

```bash
bb report generate <public_id>
```

Reports use the in-memory pipeline (E-220-06) and produce perspective-aware stat rows.

---

## Verification Queries

Run these SQL queries against `data/app.db` to verify the rebuild:

### (a) No NULL perspective_team_id

Every stat row must have a non-NULL `perspective_team_id`:

```sql
SELECT 'batting' AS tbl, COUNT(*) AS null_count
FROM player_game_batting WHERE perspective_team_id IS NULL
UNION ALL
SELECT 'pitching', COUNT(*)
FROM player_game_pitching WHERE perspective_team_id IS NULL
UNION ALL
SELECT 'plays', COUNT(*)
FROM plays WHERE perspective_team_id IS NULL
UNION ALL
SELECT 'spray', COUNT(*)
FROM spray_charts WHERE perspective_team_id IS NULL;
```

Expected: all `null_count = 0`.

### (b) game_perspectives has rows per game

Every loaded game should have at least one perspective entry:

```sql
SELECT COUNT(*) AS games_without_perspective
FROM games g
WHERE g.status = 'completed'
  AND NOT EXISTS (
    SELECT 1 FROM game_perspectives gp WHERE gp.game_id = g.game_id
  );
```

Expected: `0` (all completed games have a perspective entry).

### (c) No scouting files in data/raw

```bash
find data/raw/*/scouting -type f 2>/dev/null | wc -l
```

Expected: `0`.

### (d) No double-counted aggregates

Verify that season aggregates match single-perspective game counts:

```sql
-- For each team, games_tracked in season batting should equal
-- the number of distinct games with that perspective.
SELECT psb.player_id, psb.team_id, psb.season_id,
       psb.games_tracked AS agg_games,
       (SELECT COUNT(DISTINCT pgb.game_id)
        FROM player_game_batting pgb
        JOIN games g ON pgb.game_id = g.game_id
        WHERE pgb.player_id = psb.player_id
          AND pgb.team_id = psb.team_id
          AND g.season_id = psb.season_id
          AND pgb.perspective_team_id = psb.team_id) AS actual_games
FROM player_season_batting psb
WHERE psb.games_tracked != (
    SELECT COUNT(DISTINCT pgb2.game_id)
    FROM player_game_batting pgb2
    JOIN games g2 ON pgb2.game_id = g2.game_id
    WHERE pgb2.player_id = psb.player_id
      AND pgb2.team_id = psb.team_id
      AND g2.season_id = psb.season_id
      AND pgb2.perspective_team_id = psb.team_id
);
```

Expected: no rows returned (aggregates match per-perspective game counts).

---

## Troubleshooting

- **Credentials expired during scout**: Run `bb creds setup web` to refresh, then re-run `bb data scout`.
- **Missing member-team data**: If `data/raw/{season}/teams/` was accidentally deleted, re-crawl with `bb data crawl`.
- **Reports show "No data available"**: Verify scouting completed successfully with `bb status` before regenerating reports.
