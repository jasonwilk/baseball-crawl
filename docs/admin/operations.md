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

*Last updated: 2026-03-21 | Source: E-143 (programs, user roles, team delete, opponent mapping UX, crawl trigger UI), E-120-06 (bare UUID input documented), E-055 (unified CLI), E-115-01 (E-100 team management model), E-028-03 (original)*
