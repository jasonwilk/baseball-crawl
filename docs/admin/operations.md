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
| Actions | Edit link, Activate/Deactivate button, Discover button (active teams with a public ID only) |

### Editing a Team

Click **Edit** on any row to open the edit form at `/admin/teams/{id}/edit` (INTEGER `id`). The form shows Public ID and GameChanger UUID read-only, along with Status and Last Synced. Editable fields:

- **Name**: Team display name
- **Program**: Optional program assignment
- **Division**: Optional classification (same dropdown as Add Team)
- **Membership**: Radio button to toggle between Tracked and Member

### Activating and Deactivating Teams

The **Activate/Deactivate** button on each row calls `POST /admin/teams/{id}/toggle-active`. Active teams (`is_active = 1`) are included when crawling with `--source db`. Deactivated teams are preserved in the database but excluded from crawls.

### Discovering Opponents

For any active team that has a public ID, the **Discover** button calls `POST /admin/teams/{id}/discover-opponents`. The system fetches `GET /public/teams/{public_id}/games`, extracts unique opponent names, and inserts placeholder rows for any opponents not already in the database.

**Important limitation**: The public games endpoint returns opponent names only -- no public ID or other identifier. Discovered opponents are inserted as placeholder rows in the `teams` table with `membership_type = 'tracked'`, `is_active = 0`, and `public_id = NULL`. To upgrade a placeholder to a full record, paste the team's GameChanger URL into the Add Team form at `/admin/teams`.

### Database-Driven Crawl Configuration

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

`config/teams.yaml` remains functional as a bootstrap and seed mechanism. YAML is still the default to preserve backward compatibility; once all teams are in the database, switching to `--source db` is the recommended workflow.

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

*Last updated: 2026-03-17 | Source: E-120-06 (bare UUID input documented), E-055 (unified CLI), E-115-01 (E-100 team management model), E-028-03 (original)*
