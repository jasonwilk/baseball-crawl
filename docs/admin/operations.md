# Operations

This guide covers deploying, maintaining, and troubleshooting the baseball-crawl production stack.

## Deployment Overview

The production stack runs on a home Linux server and is exposed to the internet via a Cloudflare Tunnel. There is no traditional server management (no Nginx, no Let's Encrypt, no port forwarding).

```
Internet  -->  Cloudflare (SSL, Zero Trust Access)  -->  Cloudflare Tunnel
    -->  Traefik (reverse proxy)  -->  FastAPI app  -->  SQLite (data/app.db)
```

**Services** (defined in `docker-compose.yml`):

| Service | Image | Role |
|---------|-------|------|
| `app` | Built from `Dockerfile` | FastAPI application. Runs migrations on startup, then starts Uvicorn on port 8000. |
| `traefik` | `traefik:v3` | Reverse proxy. Routes by `Host` header using Docker labels. Starts only after the app health check passes. |
| `cloudflared` | `cloudflare/cloudflared:latest` | Cloudflare Tunnel connector. Reads `CLOUDFLARE_TUNNEL_TOKEN` from `.env`. Starts only after the app health check passes. |

**Starting the stack**:

```bash
docker compose up -d
```

**Stopping the stack**:

```bash
docker compose down
```

**Rebuilding after code changes**:

```bash
docker compose up -d --build app
```

For the full Cloudflare Tunnel and Zero Trust Access setup, see [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md).

## Admin Team Management

The admin interface at `/admin/teams` is the primary way to add and manage teams. Access requires an admin account.

### Adding a Team

Adding a team is a two-phase flow.

**Phase 1 -- URL input**: Navigate to `/admin/teams`. Paste a GameChanger team URL or identifier into the URL input field and click **Continue**. No team type selector appears at this step.

**Phase 2 -- Confirm**: The system resolves the team name and location by calling `GET /public/teams/{public_id}` and attempts to discover the team's GameChanger UUID via the reverse bridge endpoint (`GET /teams/public/{public_id}/id`). The confirm page shows:

| Field | Description |
|-------|-------------|
| Team Name | Resolved display name from the public API |
| Public ID | The GC public URL slug |
| GameChanger UUID | Shown as **Discovered** (green badge) if the reverse bridge succeeded, or **Not available (403)** (yellow badge) if it did not |
| Membership | Radio button: **Tracked** (default) or **Member** (Lincoln program team). Member is disabled if no UUID was discovered. |
| Program | Optional dropdown to assign the team to a program (e.g., Lincoln Standing Bear HS) |
| Division | Optional dropdown (High School: varsity/JV/freshman/reserve/legion; Youth/USSSA: 8U--14U) |

Click **Add Team** to save, or **Cancel** to return to the team list. If the team is already in the system, the confirm page shows an error and the **Add Team** button is disabled.

**What the URL parser accepts**:
- Full GameChanger web URL: `https://web.gc.com/teams/{public_id}/any-slug`
- Any URL containing `/teams/{id}` in the path (mobile share links, etc.)
- A bare public ID slug: `a1GFM9Ku0BbF`

Raw UUIDs are not accepted -- the form will return an error asking for a URL or public ID slug instead.

### Team List

The teams page (`/admin/teams`) shows a single flat table of all teams -- member and tracked -- with no section split.

| Column | Contents |
|--------|---------|
| Name | Team display name |
| Program | Assigned program, or `—` if none |
| Division | `classification` value (e.g., varsity, jv, 8U), or `—` if none |
| Membership | **Member** badge (blue) or **Tracked** badge (gray) |
| Opponents | Count of opponent connections; links to `/admin/opponents?team_id={id}` |
| Status | **Active** or **Inactive** |
| Last Synced | Timestamp of the last completed sync, or **Never** if the team has never been synced. If a sync is currently running, the current-job status badge is shown alongside the previous sync timestamp. |
| Actions | Edit link, Activate/Deactivate button, Sync button (eligible teams only), Delete button (inactive teams only) |

### Editing a Team

Click **Edit** on any row to open the edit form at `/admin/teams/{id}/edit` (INTEGER `id`). The form shows Public ID and GameChanger UUID read-only, along with Status and Last Synced. Editable fields:

- **Name**: Team display name
- **Program**: Optional program assignment
- **Division**: Optional classification (same dropdown as Add Team)
- **Membership**: Radio button to toggle between Tracked and Member

### Activating and Deactivating Teams

The **Activate/Deactivate** button on each row calls `POST /admin/teams/{id}/toggle-active`. Active teams (`is_active = 1`) are included when crawling. Deactivated teams are preserved in the database but excluded from crawls and show no Sync button.

### Syncing Team Data

The **Sync** button on each row triggers a data refresh for that team. It calls `POST /admin/teams/{id}/sync`, enqueues the crawl as a background task, and redirects immediately to the teams page with a flash message: "Sync started for [team name]."

The correct pipeline runs automatically based on membership type:
- **Member teams**: Full crawl + load via `crawl.run(source="db", team_ids=[id])` then `load.run(source="db", team_ids=[id])`, followed automatically by opponent discovery (seeds `opponent_links` from the team's cached schedule and opponent data, then runs `OpponentResolver.resolve()` to auto-link known opponents via `progenitor_team_id`).
- **Tracked teams**: Scouting crawler + loader (`ScoutingCrawler.scout_team(public_id)` plus loader step).

Both the crawl and load steps always run -- crawled data stays in `data/raw/` and dashboards remain stale without the load step.

**Sync button eligibility**: The Sync button appears only for active teams that are ready to crawl:
- Active member teams (always eligible).
- Active tracked teams where a `public_id` has been mapped (either auto-resolved or manually connected).
- Inactive teams show no Sync button.
- Unresolved tracked teams (`public_id IS NULL`) show a muted "Unresolved -- map first" indicator instead.

**Last Synced column**: Updated to the current timestamp on each successful sync completion. A status badge on the latest crawl job shows the current run state:

| Badge | Meaning |
|-------|---------|
| ✓ Success (green) | Last sync completed without errors |
| ✗ Failed (red) | Last sync encountered an error |
| Running... (yellow) | Sync is currently in progress; Sync button is disabled |

**Auth token refresh**: Each background sync refreshes the GameChanger access token at the start of the run, before invoking the pipeline. This prevents mid-run authentication failures.

**CLI alternative**: `bb data sync`, `bb data crawl --source db`, and `bb data load --source db` are still available and continue to work for scripting or automation. The UI Sync button is preferred for ad-hoc refreshes.

### Deleting a Team

The **Delete** button appears only on rows where the team is **deactivated** (`is_active = 0`). Active teams do not show a delete option. Clicking Delete shows a browser confirmation dialog with the team name before submitting.

`POST /admin/teams/{id}/delete` checks two preconditions before proceeding:
1. The team is deactivated.
2. No associated data rows exist in: `games`, `player_game_batting`, `player_game_pitching`, `player_season_batting`, `player_season_pitching`, `scouting_runs`, `spray_charts`.

If either check fails, the page redirects to the teams list with an error flash explaining the team has associated data and cannot be deleted. Teams with historical game or stat data should remain deactivated, not deleted.

When deletion proceeds (both checks pass), the operation runs in a single transaction:
1. Clears junction/access rows: `team_opponents`, `team_rosters`, `opponent_links`, `user_team_access`, `coaching_assignments`, `crawl_jobs`.
2. Deletes the `teams` row.

After a successful deletion, the teams list shows a success flash confirming which team was removed.

**Use case**: Removing mis-entered or duplicate tracked teams before any data has been crawled for them. Once data exists, soft-deactivation (`is_active = 0`) is the only option.

### Opponent Discovery (Automatic)

Opponent discovery runs automatically at the end of every member team sync -- there is no separate Discover button. After the crawl and load steps complete, the pipeline seeds `opponent_links` from the team's cached schedule and opponents data, then runs the auto-resolver to link any opponents whose `progenitor_team_id` (a stable GameChanger identifier) is available.

**What gets discovered**: Opponents are seeded as placeholder rows in `opponent_links` (and stub rows in `teams` where needed). The auto-resolver upgrades approximately 86% of these to full records using `progenitor_team_id`. The remaining ~14% appear on the Opponents page as **Needs linking** and require a one-time admin action to find and connect them on GameChanger.

**After a sync**: Navigate to the **Opponents** tab to see which opponents were auto-resolved and which need manual linking.

### Merging Duplicate Teams

When the system detects tracked teams with identical names and the same season year, a **Potential Duplicates** banner appears above the team table on `/admin/teams`. Each duplicate group shows the team names, the number of teams in the group, and a **Resolve** link.

**When duplicates appear**: The banner triggers automatically on page load whenever two or more tracked teams share the same display name and `season_year`. This commonly happens when the same opponent is added twice from different schedule imports.

**Note**: Merging is only available for tracked teams. Member teams cannot be merged -- if you need to combine member teams, correct them individually in GameChanger and re-sync.

#### Running a Merge

**Step 1 -- Open the merge page**: Click **Resolve** on any duplicate group. The merge page at `/admin/teams/merge` shows each team's key details side-by-side:

| Field | What it tells you |
|-------|------------------|
| Name | Display name |
| GameChanger UUID | Whether the GC API UUID is known |
| Public ID | Whether the public URL slug is known |
| Games | Number of game records attached |
| Has Stats | Whether season stats have been loaded |
| Membership | Tracked or Member |
| Season Year | Which season this team belongs to |
| Last Synced | When data was last refreshed |

**Step 2 -- Choose the canonical team**: Select which team to keep using the radio buttons. Default selection favors the team with stats (`has_stats = true`) or the higher game count. Click **Preview Merge** to reload the page with a full directional preview showing:

- Identifier gap-fill: if the canonical team is missing a `gc_uuid` or `public_id` that the duplicate has, those identifiers are carried over automatically.
- Reassignment counts: how many rows in each table will be re-pointed to the canonical team.
- Warnings: games played *between* the two teams (the game record will be reassigned, making it a self-referencing row -- check whether this is expected).
- Blocking issues: shown in a red warning box if present; the **Confirm Merge** button is disabled until resolved.

**Step 3 -- Confirm**: Click **Confirm Merge**. The merge runs atomically -- all foreign key references across 16 columns in 13 tables are reassigned to the canonical team, and the duplicate row is deleted. On success, the teams list shows a flash message:

```
Merged [duplicate name] into [canonical name]. Stats will update on next sync.
```

**Step 4 -- Sync**: A **Sync Now** button appears in the success message. Click it to trigger a data refresh for the canonical team immediately, or let the next scheduled sync handle it.

#### When a Merge Is Blocked

The **Confirm Merge** button is disabled if blocking issues exist. Common causes:

- One of the team IDs no longer exists.
- The two IDs are the same (can't merge a team with itself).
- Either team is a Member team (not permitted).

Resolve the blocking issue (usually by refreshing the page to reload current state), then retry.

#### If 3+ Teams Are in a Group

For groups with three or more duplicates, the merge page lists all teams in the group. Select any two to merge pairwise. After the merge, refresh the teams list -- if duplicates remain, the banner reappears with the remaining group, and you can run another merge.

### Auto-Merging Duplicate Teams via CLI (`bb data dedup`)

`bb data dedup` identifies and auto-merges duplicate tracked teams using the same merge infrastructure as the admin UI. It is useful for clearing a backlog of existing duplicates, or for confirming there are none.

**Dry run (default -- no writes)**:

```bash
bb data dedup
```

Prints all duplicate groups found, the chosen canonical team for each, and whether each pair would be merged or skipped. No database changes are made.

**Execute merges**:

```bash
bb data dedup --execute
```

Performs the merges. Same output as dry run, plus `MERGED` confirmation lines for each completed merge.

**What counts as a duplicate**: Two or more tracked teams with the same name (case-insensitive) and the same `season_year` (or both NULL, or a NULL vs. non-NULL year pair sharing the same name). Member teams are never included.

**Canonical selection** (highest priority wins):
1. Has stats loaded (`has_stats = true`)
2. More games linked (higher `game_count`)
3. Older row (lower `id`)

**Auto-merge safety guard**: A pair is skipped (not merged) if any games exist between the two teams -- teams that played each other are not the same team. Skipped pairs are listed with reasons in the summary output.

**Output format**:

```
[DRY RUN] Found 3 duplicate group(s).

--- Group 1 (2 teams) ---
  id=42  name='Eagle Creek HS'  season_year=2026  games=3  has_stats  gc_uuid  no public_id  << canonical
  id=87  name='Eagle Creek HS'  season_year=None  games=0  no stats  no gc_uuid  no public_id
  Canonical: id=42 (has_stats=True games=3 id=42)
  Would merge id=87 -> id=42

Summary: 3 group(s) found, 3 merged, 0 skipped.
```

**Custom database path**:

```bash
bb data dedup --db /path/to/app.db
```

Defaults to `data/app.db` (or `DATABASE_PATH` env var).

**Note**: After running with `--execute`, sync any affected teams that have scouting data: `bb data scout --team {public_id}` or the **Sync** button on the Teams page.

### Back-Filling Pre-Existing Resolutions (`bb data repair-opponents`)

`bb data repair-opponents` propagates existing `opponent_links` resolutions that were never written through to `team_opponents`. This is a one-time repair command for opponents that were resolved before E-173 was deployed -- any opponent resolved after E-173 is automatically handled at resolution time and does not need this command.

**Dry run (default -- no writes)**:

```bash
bb data repair-opponents
```

Prints each resolved opponent link and what action would be taken. No database changes are made.

**Execute repairs**:

```bash
bb data repair-opponents --execute
```

Performs the repairs atomically. For each resolved `opponent_links` row:
- Upserts a `team_opponents` row linking the member team to the resolved team.
- Sets `is_active = 1` on the resolved team.
- If a stub team exists for the same opponent name, reassigns all FK references from the stub to the resolved team (games, stats, spray charts, rosters).

**Output format**:

```
[DRY RUN] Found 8 resolved opponent link(s) to process.

  CREATE: Eagle Creek HS (our_team=LSB Varsity, resolved_id=44)
  REPLACE stub (team 27): Sunset Ridge HS (our_team=LSB JV, resolved_id=55) + activate
  VERIFY: Millbrook HS (our_team=LSB Varsity, resolved_id=61)

Summary (DRY RUN):
  total to process: 8

Run with --execute to apply changes.
```

After `--execute`, the summary shows counts for `team_opponents` rows created, stub replacements, teams activated, FK reassignments, and no-ops.

**Idempotent**: Safe to run multiple times -- already-correct rows are reported as `VERIFY` and skipped.

**Custom database path**:

```bash
bb data repair-opponents --db /path/to/app.db
```

### Database-Driven Crawl Configuration (CLI)

By default, `scripts/crawl.py` and `scripts/load.py` read team configuration from `config/teams.yaml`. Pass `--source db` to read active member teams directly from the database instead:

```bash
python scripts/crawl.py --source db
python scripts/load.py --source db
```

Also available as `bb data crawl --source db` and `bb data load --source db`.

With `--source db`, both scripts query:
```sql
SELECT id, name, classification, gc_uuid FROM teams WHERE is_active = 1 AND membership_type = 'member'
```

The database path defaults to `./data/app.db` or the `DATABASE_PATH` environment variable.

`config/teams.yaml` remains functional as a bootstrap and seed mechanism. YAML is still the default for the CLI to preserve backward compatibility; the UI Sync button is preferred for per-team ad-hoc refreshes.

### Scouting Opponents via CLI (`bb data scout`)

The `bb data scout` command runs the opponent scouting pipeline from the CLI. It queries `opponent_links` for all tracked teams with a `public_id`, then crawls their schedule (public endpoint), roster, and boxscores (authenticated endpoints -- valid GameChanger credentials must be configured in `.env`) and loads the results into the database.

**Commands**:

```bash
# Scout all opponents with a public_id (skips any scouted within the last 24 hours)
bb data scout

# Scout a single opponent by public_id slug (always runs, regardless of freshness)
bb data scout --team QTiLIb2Lui3b

# Re-scout all opponents, bypassing the 24-hour freshness check
bb data scout --force

# Preview what would be scouted without making any API calls or DB writes
bb data scout --dry-run
```

**What `bb data scout` runs**: Four steps in order:

1. **Scouting crawl** (`ScoutingCrawler`) — fetches schedule, roster, and boxscores for each opponent.
2. **Scouting-spray crawl** (`ScoutingSprayCrawler`) — fetches spray chart data for each scouted opponent.
3. **Scouting load** (`ScoutingLoader`) — aggregates boxscores into season stats and writes to the database.
4. **Scouting-spray load** (`ScoutingSprayLoader`) — writes opponent spray chart coordinate data to the `spray_charts` table.

All four steps run automatically when you run `bb data scout`. You can also run the spray steps individually (see [Scouting Spray Chart Pipeline](#scouting-spray-chart-pipeline-bb-data-crawl---crawler-scouting-spray--bb-data-load---loader-scouting-spray) below).

**Freshness check**: By default, `bb data scout` skips any opponent scouted within the last 24 hours. Use `--force` to override this and re-scout all opponents unconditionally. The `--team` flag always scouts the specified opponent regardless of when it was last scouted -- `--force --team PUBLIC_ID` is valid but redundant.

**Output**: After the crawl phase, the command prints a summary line:

```
Crawl complete: files_written=N files_skipped=N errors=N
```

Followed by a load status line per team:

```
Load complete for QTiLIb2Lui3b (season=2025-spring-hs).
```

If errors occur during crawl or load, the command exits with status code 1.

**UI alternative**: For ad-hoc per-team refreshes, the **Sync** button on the Teams page is preferred. The CLI `bb data scout` command is suited for batch re-scouting, scripting, or forced refreshes across all opponents.

### Spray Chart Pipeline (`bb data crawl --crawler spray-chart` / `bb data load --loader spray-chart`)

The spray chart pipeline populates the `spray_charts` table with ball-in-play coordinate data for both own-team and opponent players. Spray charts are rendered on-the-fly as PNG images and displayed on the player profile page and opponent scouting report.

**Pipeline steps -- run in order:**

```bash
# Step 1: Crawl spray chart data from the GameChanger API
bb data crawl --crawler spray-chart

# Step 2: Load crawled data into the spray_charts table
bb data load --loader spray-chart
```

**What the crawler does**: For each completed game in `data/raw/{season}/teams/{gc_uuid}/game-summaries/`, fetches `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` and writes the full JSON response to `data/raw/{season}/teams/{gc_uuid}/spray/{event_id}.json`. One API call returns spray data for both teams (own team and opponent). Files are skipped if they already exist (existence-only check -- completed game data does not change).

**What the loader does**: Reads each spray JSON file, splits ball-in-play events by player ownership (determined via the `games` and `team_rosters` tables), and inserts rows into `spray_charts` using `INSERT OR IGNORE` keyed on the `event_gc_id` UNIQUE column. This means re-running the loader for the same games is safe -- no duplicate records are created.

**Dependency**: The spray chart crawler reads game-summaries files written by `ScheduleCrawler`. Run the main crawl pipeline first for the team before running the spray crawler.

**Integration with the normal sync**: The Admin UI **Sync** button runs the full member-team pipeline (crawl + load) but does not currently include the spray crawler. Run the spray chart pipeline separately via CLI after a team sync:

```bash
# After a team sync via admin UI or bb data crawl --source db:
bb data crawl --crawler spray-chart
bb data load --loader spray-chart
```

**Selective crawl**: The `--crawler spray-chart` flag targets only the spray crawler, leaving all other crawlers untouched.

**Requirements**: `matplotlib~=3.9` and `numpy~=2.0` are required for chart rendering. These are included in `requirements.txt`. If you added these dependencies after building the Docker image, rebuild before running the load step:

```bash
docker compose up -d --build app
```

**Raw data location**: `data/raw/{season}/teams/{gc_uuid}/spray/{event_id}.json`

**Output**: Crawl and load each print a summary line:

```
Crawl complete: files_written=N files_skipped=N errors=N
Load complete for {gc_uuid} (season={season_id}).
```

### Scouting Spray Chart Pipeline (`bb data crawl --crawler scouting-spray` / `bb data load --loader scouting-spray`)

The scouting spray chart pipeline fetches and loads spray chart coordinate data for **opponent (tracked) teams**. It complements the own-team spray chart pipeline and is automatically included as steps 2 and 3 of `bb data scout`.

**Pipeline steps -- run in order:**

```bash
# Step 1: Crawl scouting spray chart data for all tracked opponents
bb data crawl --crawler scouting-spray

# Step 2: Load crawled data into the spray_charts table
bb data load --loader scouting-spray
```

**When to run separately**: `bb data scout` runs both steps automatically. Use these standalone commands when you want to re-load spray data without re-running the full scouting crawl, or when troubleshooting a specific step.

**Dependency**: The scouting-spray crawler reads scouting files written by `ScoutingCrawler`. Run `bb data scout` (or the scouting crawl step manually) before running the scouting-spray crawler in isolation.

**Raw data location**: `data/raw/{season}/teams/{public_id}/scouting-spray/{event_id}.json`

**Output**:

```
Scouting spray crawl complete: files_written=N files_skipped=N errors=N
Scouting spray load complete: loaded=N skipped=N errors=N
```

### Plays Pipeline (`bb data crawl --crawler plays` / `bb data load --loader plays`)

The plays pipeline fetches and loads play-by-play data for all completed games for member teams. Each play record represents a single plate appearance; derived flags `is_first_pitch_strike` (FPS) and `is_qab` (Quality At-Bat) are computed during parsing and written to the `plays` table.

**Pipeline steps -- run in order:**

```bash
# Step 1: Crawl play-by-play data from the GameChanger API
bb data crawl --crawler plays

# Step 2: Load crawled data into the plays and play_events tables
bb data load --loader plays
```

**What the crawler does**: For each completed game in `data/raw/{season}/teams/{gc_uuid}/game_summaries.json`, fetches `GET /game-stream-processing/{event_id}/plays` and writes the raw JSON response to `data/raw/{season}/teams/{gc_uuid}/plays/{event_id}.json`. Files are skipped if they already exist -- completed game plays do not change.

**What the loader does**: Reads each plays JSON file, parses plate appearances into `plays` rows and individual pitch, baserunner, and substitution events into `play_events` rows, and inserts them in a per-game transaction. Whole-game idempotency: if any `plays` row already exists for a game, the entire game is skipped. Stub player rows are created for any unknown batter or pitcher IDs to satisfy foreign key constraints.

**Dependency**: The plays crawler reads `game_summaries.json` written by `ScheduleCrawler`. Run the main crawl pipeline for the team first:

```bash
# Full member-team sync first, then plays:
bb data crawl --source db
bb data load --source db
bb data crawl --crawler plays
bb data load --loader plays
```

**Integration with the normal sync**: The Admin UI Sync button does not currently run the plays pipeline automatically. Run it separately after a team sync.

**Raw data location**: `data/raw/{season}/teams/{gc_uuid}/plays/{event_id}.json`

**Output**:

```
Crawl complete: files_written=N files_skipped=N errors=N
Plays load complete for {path}: loaded=N skipped=N errors=N
```

**ID mapping note**: The plays endpoint path parameter is `event_id` from game-summaries. This is NOT `game_stream.id` -- both fields appear in the game-summaries response but they are different values. The crawler uses `event_id` (which equals `game_stream.game_id`).

### Validating Plays Data (`scripts/validate_plays_stats.py`)

After running the plays pipeline, use `validate_plays_stats.py` to verify that derived FPS (First Pitch Strike) and QAB (Quality At-Bat) counts match the season-stats values from the GameChanger API. This is an operator validation tool, not part of the regular sync workflow.

**Prerequisites**: Both plays data and season stats must be loaded in `data/app.db`.

```bash
# Validate with default database and output paths
python scripts/validate_plays_stats.py

# Specify a custom database path
python scripts/validate_plays_stats.py --db-path /path/to/app.db

# Write the report to a custom location
python scripts/validate_plays_stats.py --output /path/to/report.md
```

The script compares plays-derived FPS per pitcher and QAB per batter against `player_season_pitching.fps` and `player_season_batting.qab` in the database. Players are compared only when data exists in both sources.

**Output**: Prints a summary to stdout and writes a detailed Markdown report to `.project/research/E-195-validation-results.md` (configurable with `--output`). The report contains:

- **Plays data coverage**: How many completed member-team games have plays data loaded, and which games are missing.
- **FPS comparison table**: Per-pitcher derived vs. GC values, absolute difference, percentage difference, and match status.
- **QAB comparison table**: Per-batter derived vs. GC values, same columns.
- **Discrepancy diagnostics**: For any player exceeding the 5% tolerance threshold, a per-game FPS/QAB breakdown and sample plays for inspection.
- **Summary**: Overall match rates and outlier counts.

**Tolerance**: Players whose derived count differs from GC's by more than 5% are flagged `MISMATCH` and receive per-game diagnostic detail. Players within 5% are `OK`. Exit code is 0 on success regardless of mismatch count; 1 only on database connectivity errors.

### Migration 009: Plays Schema

Migration `migrations/009_plays_play_events.sql` adds two tables and four indexes to support play-by-play data ingestion.

**Table: `plays`** (one row per plate appearance)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PK` | Auto-increment internal key |
| `game_id` | `TEXT` | FK to `games(game_id)` |
| `play_order` | `INTEGER` | Sequential position within the game |
| `inning` | `INTEGER` | Inning number |
| `half` | `TEXT` | `'top'` or `'bottom'` |
| `season_id` | `TEXT` | FK to `seasons(season_id)` |
| `batting_team_id` | `INTEGER` | FK to `teams(id)` -- the team at bat |
| `batter_id` | `TEXT` | FK to `players(player_id)` |
| `pitcher_id` | `TEXT` | FK to `players(player_id)`; nullable (absent on some abandoned PAs) |
| `outcome` | `TEXT` | Plate-appearance result string (e.g., `'Single'`, `'Strikeout'`) |
| `pitch_count` | `INTEGER` | Total pitches in the plate appearance |
| `is_first_pitch_strike` | `INTEGER` | 1 if the first pitch was a strike (FPS); 0 otherwise |
| `is_qab` | `INTEGER` | 1 if the plate appearance meets Quality At-Bat criteria; 0 otherwise |
| `home_score` | `INTEGER` | Score at end of plate appearance (nullable) |
| `away_score` | `INTEGER` | Score at end of plate appearance (nullable) |
| `did_score_change` | `INTEGER` | 1 if a run scored on this play (nullable) |
| `outs_after` | `INTEGER` | Outs recorded after this play (nullable) |
| `did_outs_change` | `INTEGER` | 1 if an out was recorded on this play (nullable) |

UNIQUE constraint on `(game_id, play_order)`.

**Table: `play_events`** (one row per event within a plate appearance)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PK` | Auto-increment internal key |
| `play_id` | `INTEGER` | FK to `plays(id)` |
| `event_order` | `INTEGER` | Sequence position within the plate appearance |
| `event_type` | `TEXT` | `'pitch'`, `'baserunner'`, `'substitution'`, or `'other'` |
| `pitch_result` | `TEXT` | One of `'ball'`, `'strike_looking'`, `'strike_swinging'`, `'foul'`, `'foul_tip'`, `'in_play'`; null for non-pitch events |
| `is_first_pitch` | `INTEGER` | 1 if this is the first pitch event in the plate appearance |
| `raw_template` | `TEXT` | Raw GC template string from the API (nullable; useful for debugging) |

UNIQUE constraint on `(play_id, event_order)`.

**Indexes added**:

| Index | Table / Columns | Notes |
|-------|----------------|-------|
| `idx_plays_game_id` | `plays(game_id)` | Game-level plays lookups |
| `idx_plays_batter_id` | `plays(batter_id)` | Per-batter QAB aggregation |
| `idx_plays_pitcher_id` | `plays(pitcher_id)` | Per-pitcher FPS aggregation |
| `idx_plays_fps` (partial) | `plays(pitcher_id, is_first_pitch_strike)` WHERE `outcome NOT IN ('Hit By Pitch', 'Intentional Walk')` | Efficient FPS% queries; excludes HBP and IBB from the denominator per FPS% definition |

The migration is applied automatically on container startup. No backfill was needed -- both tables are populated solely by the plays pipeline.

### Migration 006: Spray Chart Schema Additions

Migration `migrations/006_spray_charts_indexes.sql` adds three columns and three indexes to the `spray_charts` table (which existed in the base schema but was unpopulated):

| Addition | Type | Purpose |
|----------|------|---------|
| `event_gc_id` column | `TEXT` | GC UUID per ball-in-play event. UNIQUE -- enables `INSERT OR IGNORE` idempotency. |
| `created_at_ms` column | `INTEGER` | API's `createdAt` timestamp in Unix milliseconds. |
| `season_id` column | `TEXT` | Season slug from the file path (e.g., `2026-spring-hs`). Enables per-season filtering per the fresh-start philosophy. |
| `idx_spray_charts_event_gc_id` index | UNIQUE | On `event_gc_id`. Enforces idempotency at the DB level. |
| `idx_spray_charts_player` index | | On `(player_id, team_id, season_id)`. Serves player profile and per-player chart queries. |
| `idx_spray_charts_game` index | | On `game_id`. Serves game-level spray queries. |

The migration is applied automatically on container startup by `migrations/apply_migrations.py`. The table was unpopulated when this migration was written -- no backfill was needed.

### Spray Chart Rendering

Charts are rendered on-the-fly by `src/charts/spray.py` using `matplotlib` and `numpy`. The renderer is not called directly -- it is invoked by two dashboard image routes:

| Route | What it renders |
|-------|----------------|
| `GET /dashboard/charts/spray/player/{player_id}.png` | Per-player offensive spray chart for the current (or `?season_id=`) season. Returns 204 if the player has 0 BIP. |
| `GET /dashboard/charts/spray/team/{team_id}.png` | Team aggregate offensive spray chart. Returns 204 if the team has 0 BIP. |

Charts render as 4×6 inch PNGs at 150 DPI, matching the 320×480 coordinate space used by GameChanger's own UI. Both routes require an authenticated session (Cloudflare Access) but do **not** perform `permitted_teams` team membership checks -- this is intentional so opponent player charts load correctly from the scouting report.

**Threshold behavior**: A chart is displayed for any player or team with at least 1 BIP. Players or teams with 0 BIP receive "No spray chart data available" in the dashboard UI; the image route returns HTTP 204 as a defensive fallback for direct URL access.

## Programs Management

Programs are umbrella entities that group teams under a shared organizational identity (e.g., `lsb-hs` = Lincoln Standing Bear High School). Navigate to the **Programs** tab (`/admin/programs`) in the admin sub-navigation.

### Programs List

The Programs page lists all programs with these columns:

| Column | Contents |
|--------|---------|
| Name | Display name (e.g., "Lincoln Standing Bear HS") |
| Program ID | Operator-chosen slug used as the primary key (e.g., `lsb-hs`) |
| Type | `hs`, `usssa`, or `legion` |
| Org Name | Optional organization name |
| Teams | Count of teams assigned to this program |
| Created | Creation timestamp |

### Adding a Program

The "Add Program" form is on the Programs page itself. Fill in:

| Field | Notes |
|-------|-------|
| **Program ID** | Short slug (e.g., `lsb-hs`). Must be unique -- duplicate IDs return an error flash, not a 500. |
| **Display Name** | Human-readable name shown in dropdowns and tables. |
| **Type** | `hs`, `usssa`, or `legion`. |
| **Org Name** | Optional. |

Click **Add Program**. The new program appears immediately in the programs list and in the program dropdown on the team add/edit pages -- no app restart required.

**Note**: Program edit and delete are not available in the UI. To rename a program, update the `programs` table directly with `sqlite3 data/app.db`. Program deletion is only safe when no teams reference the program.

## User Role Management

The admin UI enforces role-based access. Two roles exist:

| Role | Access |
|------|--------|
| `admin` | Full access: team CRUD, program CRUD, user CRUD, crawl triggers, opponent mapping. |
| `user` | Read-only: coaching dashboards and reports. Cannot access management routes. |

### Granting Admin Access

Admin access is granted via either of two mechanisms (both are checked):

1. **`ADMIN_EMAIL` environment variable** (bootstrap path): If the authenticated user's email matches `ADMIN_EMAIL` in `.env`, they receive admin access regardless of their database role. Use this to bootstrap the first admin account.

2. **Database role** (ongoing): Set `role = 'admin'` on the user's row. Once set, the user has permanent admin access even if `ADMIN_EMAIL` is changed or removed.

To promote a user to admin via SQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';  <!-- pii-ok -->
```

After promotion, the user's Role column on the Users page shows `admin`.

### Role Field in User Forms

The **Users** page (`/admin/users`) displays a **Role** column. The **Add User** form and **Edit User** form both include a Role field (radio: Admin / User, default: User).

**Self-demotion guard**: An admin cannot set their own role to `user` via the edit form -- a server-side validation error prevents accidental lockout.

### Revoking Admin Access

Change the user's role to `user` on the Edit User page (`/admin/users/{id}/edit`). The change takes effect immediately on the next request.

## Opponent Mapping

The Opponents page (`/admin/opponents`) shows all opponent links discovered for member teams. Navigate there via the **Opponents** tab in the admin sub-navigation, or via the Opponents count link on any team row.

### Reading the Opponents Page

A summary stat line at the top of the page shows the current state:

```
14 opponents -- 10 with stats, 2 syncing, 2 need linking.
```

The admin subnav **Opponents** tab shows a badge with the count of opponents that need linking, so you can spot outstanding work at a glance.

**Filter pills** above the table narrow the list:

| Pill | Shows |
|------|-------|
| All | All non-hidden opponents |
| Stats loaded | Opponents with scouting stats available in the dashboard |
| Needs linking | Opponents with no GameChanger team linked yet |
| Hidden | Opponents marked "no match" and excluded from the active pipeline |

When opponents need linking, a banner appears at the top of the page. Click **Start linking** to switch to that view.

The table shows each opponent with a **Status** badge:

| Badge | Meaning |
|-------|---------|
| Stats loaded (green) | Scouting stats are available; the team has been synced. |
| Syncing... (yellow) | A scouting sync is currently running for this team. |
| Sync failed (red) | The last scouting sync encountered an error. |
| Needs linking (orange) | No GameChanger team has been linked yet; scouting stats unavailable. |
| Hidden (gray) | Marked "no match" by the admin; excluded from the active pipeline. |

Auto-resolved opponents (~86%) are linked automatically via the `progenitor_team_id` field on the schedule. The remaining ~14% require admin action.

### Linking an Opponent (Find on GameChanger)

For any **Needs linking** row, click **Find on GameChanger**. This opens the unified resolve page titled "Find [opponent] on GameChanger", which combines a search path (primary) and a URL-paste path (fallback) in a single page.

**Search path (primary)**:

1. The page opens pre-filled with the opponent's name, the member team's season year, and `sport=baseball`. Review the result cards -- each shows: team name, season year, location, player count, and staff names.
2. Use the **Refine Search** form to adjust name, state, or city if the default results are not helpful.
3. Click a card to open the confirm page with the full team profile. If the selected team's `public_id` already exists in the database, a yellow duplicate warning appears with a link to the merge page.
4. Click **Confirm** to save. The system atomically updates `opponent_links`, links the team in `team_opponents`, activates the team, and starts a background scouting sync. You are redirected to the Needs linking filter so the next opponent is immediately visible.

**URL-paste path (fallback)**:

Below a "-- or --" divider, paste the team's GameChanger URL directly (find it at [web.gc.com](https://web.gc.com)). Click **Look up**, review the confirm page, and click **Confirm** -- the same write-through and auto-scout steps run.

**Auto-scout after linking**: As soon as you confirm, a background scouting sync starts automatically for the linked opponent. The row status changes to **Syncing...** and then to **Stats loaded** when complete. No CLI command is needed.

### Dismissing Unresolvable Opponents

When no valid match exists, click **No match -- skip** at the bottom of the resolve page. This sets `is_hidden = 1` on the opponent link, which:

- Removes the opponent from the Needs linking count and banner.
- Excludes the opponent from the scouting pipeline (resolver and seeder skip hidden entries).
- Does **not** delete the row -- it is reversible.

### Viewing and Restoring Hidden Opponents

Click the **Hidden** filter pill to see all opponents marked "no match." Each row shows an **Unhide** button. Clicking it sets `is_hidden = 0` and returns the opponent to the active list.

---

## Credential Rotation

### GameChanger API Tokens

GameChanger credentials expire frequently. When API calls start failing with authentication errors:

1. Log in to [web.gc.com](https://web.gc.com) in a browser.
2. Open DevTools -> Network tab -> copy any API request as cURL.
3. Save to `secrets/gamechanger-curl.txt` (or pass inline with `--curl`).
4. Run:

```bash
python scripts/refresh_credentials.py
```

Also available as `bb creds import`.

5. Verify with the smoke test:

```bash
python scripts/smoke_test.py
```

6. If the app is running, restart it to pick up the new `.env` values:

```bash
docker compose restart app
```

**Auto-recovery note**: If `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` are present in the Docker environment (i.e., set in `.env` and passed through by Docker Compose), the system automatically performs the full login flow when the refresh token expires. This means routine refresh-token expiry does not require manual intervention -- the next sync or API call triggers re-authentication automatically. Keep these credentials in `.env` for ongoing resilience, not just one-time setup.

### Cloudflare Service Tokens

Cloudflare Access service tokens (`CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`) have an expiry set at creation time (typically 1 year). To rotate:

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) -> Access -> Service Tokens.
2. Create a new token (or refresh the existing one).
3. Update `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` in `.env` on the server.
4. Restart the stack: `docker compose restart`.
5. Verify API access through the tunnel.

The Cloudflare Tunnel token (`CLOUDFLARE_TUNNEL_TOKEN`) does not expire unless revoked.

## Database Backup and Restore

### Backup

Create a timestamped copy of the database:

```bash
python scripts/backup_db.py
```

Also available as `bb db backup`.

This copies `data/app.db` to `data/backups/app-<timestamp>.db`. The backups directory is created automatically and is git-ignored.

### Restore

To restore from a backup:

```bash
# 1. Stop the application
docker compose down

# 2. Replace the database with the backup
cp data/backups/app-2026-03-02T140000.db data/app.db

# 3. Restart the application
docker compose up -d
```

### Verify a Restore

```bash
sqlite3 data/app.db "PRAGMA integrity_check; PRAGMA journal_mode;"
```

A healthy database returns `ok` and `wal`.

### Development Database Reset

For local development, drop and recreate the database with seed data:

```bash
python scripts/reset_dev_db.py
```

Also available as `bb db reset`.

This script has a production safety guard: if `APP_ENV=production`, the `--force` flag is required.

For full details, see [docs/database-restore.md](../database-restore.md).

## Troubleshooting

### App is unreachable

1. **Check Docker is running**: `docker info` -- an error means the Docker daemon is down.
2. **Check container status**: `docker compose ps` -- the `app` service must show `Up`.
3. **Check app logs**: `docker compose logs app` -- look for startup errors or migration failures.
4. **Check port conflicts**: `lsof -i :8001` -- if occupied, stop the conflicting process.
5. **Restart the app**: `docker compose restart app`, then `curl -s http://localhost:8001/health`.

### Health check returns 503

The health endpoint (`GET /health`) returns 503 when the database is unreachable or uninitialized:

```json
{"status": "error", "db": "error"}
```

- Verify the database file exists at `data/app.db`.
- Check if migrations have been applied: `sqlite3 data/app.db "SELECT * FROM _migrations;"`.
- The app container mounts `./data:/app/data` -- make sure the host directory exists and is writable.

### GameChanger API errors

- **Credential expired**: Run `python scripts/refresh_credentials.py` (or `bb creds import`) and then `python scripts/smoke_test.py`.
- **Rate limited**: The HTTP session factory handles rate limiting automatically with 1--1.5 second delays between requests. If you hit rate limits, increase the delay: adjust `min_delay_ms` and `jitter_ms` in `src/http/session.py`.
- **Unknown endpoint error**: Check [docs/api/README.md](../api/README.md) for the current endpoint documentation.

### Cloudflare Tunnel not connecting

- Check cloudflared logs: `docker compose logs cloudflared`.
- Verify `CLOUDFLARE_TUNNEL_TOKEN` is set in `.env`.
- In the Cloudflare dashboard (Networks -> Tunnels), the tunnel status should show Healthy.
- See [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md) for detailed troubleshooting.

### Database is corrupted

1. Backup the current state (even if corrupted): `cp data/app.db data/app.db.corrupted`
2. Check integrity: `sqlite3 data/app.db "PRAGMA integrity_check;"`
3. If integrity check fails, restore from a backup (see above).
4. If no backup exists, reset the database: `python scripts/reset_dev_db.py` (or `bb db reset`)

## Monitoring

The production stack is lightweight and does not include a dedicated monitoring service. Use the following manual checks:

### Health Endpoint

```bash
curl -s http://localhost:8001/health
# or through the tunnel:
curl -s https://[CONFIGURE: your domain here]/health
```

Expected: `{"status": "ok", "db": "connected"}` with HTTP 200.

### Docker Compose Logs

```bash
# All services
docker compose logs

# Follow live logs for the app
docker compose logs -f app

# Last 50 lines from a specific service
docker compose logs --tail=50 cloudflared
```

### Container Status

```bash
docker compose ps
```

All services should show status `Up`. The app service should also show `(healthy)`.

### Database Size

```bash
ls -lh data/app.db
```

For the expected data volume (~30 games x 4 teams x a few seasons), the database should remain well under 100 MB.

---

*Last updated: 2026-04-01 | Source: E-195 (plays pipeline, migration 009, validate_plays_stats.py), E-173 (resolution write-through, auto-scout after linking, unified Find on GC resolve page, dashboard sort by next game date, terminology cleanup, bb data repair-opponents), E-167 (bb data dedup CLI, GC search-powered opponent resolution, skip/unhide workflow), E-163 (scouting spray pipeline, updated thresholds, bb data scout 4-step flow), E-158 (spray chart pipeline, migration 006, chart routes), E-156 (bb data scout --force flag), E-155 (duplicate team detection and merge UI), E-143 (programs, user roles, team delete, opponent mapping UX, crawl trigger UI), E-120-06 (bare UUID input documented), E-055 (unified CLI), E-115-01 (E-100 team management model), E-028-03 (original)*
