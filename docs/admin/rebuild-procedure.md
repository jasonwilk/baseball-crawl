# Clean-Slate Rebuild Procedure (E-220)

This guide covers wiping and rebuilding the database under the perspective-aware architecture introduced in E-220. After this procedure, every stat row carries `perspective_team_id` and reports are generated on demand from the `bb report generate` pipeline.

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
| `data/raw/{season}/scouting/` | Yes | Stale disk-cached scouting files from pre-E-239 runs |
| `data/reports/` | Yes | Reports regenerated from fresh data |

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

## Step 3: Wipe Legacy Cache and Reports

Remove any stale disk-cached files from pre-E-239 pipeline runs, and clear generated reports so they can be regenerated on demand.

```bash
# Remove stale scouting directories (legacy pipeline artifacts)
find data/raw/*/scouting -mindepth 1 -delete 2>/dev/null
rmdir data/raw/*/scouting 2>/dev/null

# Remove generated reports (regenerated on demand after rebuild)
rm -rf data/reports/*
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

## Step 5: Regenerate Reports

Regenerate scouting reports as needed:

```bash
bb report generate <public_id>
```

Each generation crawls the team's schedule and boxscores and produces perspective-aware stat rows.

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

> **Note (E-259):** this section previously included a "No double-counted aggregates" query that diffed the stored `player_season_batting.games_tracked` column against a per-perspective game count. The stored `player_season_*` tables were dropped in migration 011 -- the season line is now derived at query time from `player_game_batting` / `player_game_pitching` (`src.api.db.get_season_batting` / `get_season_pitching`), so there is no separate stored copy left to double-count or drift. The check is removed as meaningless rather than replaced.

---

## Troubleshooting

- **Credentials expired during report generation**: Run `bb creds setup web` to refresh, then re-run `bb report generate <public_id>`.
- **Reports show "No data available"**: Verify credentials are valid (`bb creds check`) and that the `public_id` is correct before regenerating reports.

---

*Last updated: 2026-07-12 | Source: E-259 (E-259-06: removed the "(d) No double-counted aggregates" verification query -- the stored `player_season_*` tables it checked were dropped in migration 011), E-220 (original), E-239 (removed Steps 5/6 member-sync and scout, updated to reports-first)*
