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
| Actions | Edit link, Activate/Deactivate button, Discover button (active teams with a public ID only), Sync button (eligible teams only), Delete button (inactive teams only) |

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
- **Member teams**: Full crawl + load via `crawl.run(source="db", team_ids=[id])` then `load.run(source="db", team_ids=[id])`.
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

### Discovering Opponents

For any active team that has a public ID, the **Discover** button calls `POST /admin/teams/{id}/discover-opponents`. The system fetches `GET /public/teams/{public_id}/games`, extracts unique opponent names, and inserts placeholder rows for any opponents not already in the database.

**Important limitation**: The public games endpoint returns opponent names only -- no public ID or other identifier. Discovered opponents are inserted as placeholder rows in the `teams` table with `membership_type = 'tracked'`, `is_active = 0`, and `public_id = NULL`. To upgrade a placeholder to a full record, paste the team's GameChanger URL into the Add Team form at `/admin/teams`.

After running discovery, navigate to the **Opponents** tab to see which opponents were auto-resolved and which need manual mapping.

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
| `GET /dashboard/charts/spray/player/{player_id}.png` | Per-player offensive spray chart for the current (or `?season_id=`) season. Returns 204 if the player has fewer than 10 BIP. |
| `GET /dashboard/charts/spray/team/{team_id}.png` | Team aggregate offensive spray chart. Returns 204 if the team has fewer than 20 BIP. |

Charts render as 4×6 inch PNGs at 150 DPI, matching the 320×480 coordinate space used by GameChanger's own UI. Both routes require an authenticated session (Cloudflare Access) but do **not** perform `permitted_teams` team membership checks -- this is intentional so opponent player charts load correctly from the scouting report.

**Threshold behavior**: The BIP thresholds (10 per player, 20 for team aggregate) are enforced by the image routes (204 response) and separately by the HTML templates (which show threshold-appropriate messages before even attempting to load the image). The 204 response is a defensive fallback for direct URL access.

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

A summary stat line at the top of the page shows the current mapping state:

```
14 opponents -- 10 resolved, 4 need mapping.
```

The table shows each opponent with a **Status** badge:

| Badge | Meaning |
|-------|---------|
| Resolved (green) | `public_id` is known; the team can be crawled for scouting data. |
| Unresolved (orange) | `public_id IS NULL`; scouting data cannot be fetched until the team is mapped. |

Auto-resolved opponents (~86%) are linked automatically via the `progenitor_team_id` field on the schedule. The remaining ~14% require manual mapping.

### Manually Connecting an Opponent

For any **Unresolved** row, click the **Connect** button (blue primary button). This opens the URL paste form where you provide the opponent team's GameChanger URL. The system shows a preview before saving.

To find the URL: navigate to the team's page on [web.gc.com](https://web.gc.com) and copy the URL.

After connecting, the row shows a **Resolved** badge and a gray **Disconnect** button (in case of mis-mapping).

### Running Opponent Discovery

The **Run Discovery** link at the top of the Opponents page navigates to the Teams page where the per-team **Discover** buttons are available. Run discovery for each of your member teams to import opponents from their schedules.

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

*Last updated: 2026-03-26 | Source: E-158 (spray chart pipeline, migration 006, chart routes), E-156 (bb data scout --force flag), E-155 (duplicate team detection and merge UI), E-143 (programs, user roles, team delete, opponent mapping UX, crawl trigger UI), E-120-06 (bare UUID input documented), E-055 (unified CLI), E-115-01 (E-100 team management model), E-028-03 (original)*
