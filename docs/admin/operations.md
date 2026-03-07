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

1. Navigate to `/admin/teams`.
2. Paste a GameChanger team URL (e.g., `https://web.gc.com/teams/a1GFM9Ku0BbF/2025-lincoln-varsity`) or a bare public ID slug into the URL input field.
3. Select the team type: **Lincoln Program** (an LSB-owned team) or **Tracked Opponent**.
4. Optionally set a level (freshman, jv, varsity, reserve, legion, other).
5. Submit. The system calls `GET /public/teams/{public_id}` (no authentication required) to resolve the team name and location, then stores the record.

The success flash message includes the resolved team name and location (e.g., "Team added: Lincoln Rebels (Omaha, NE)"). If the name or location looks wrong, use the Edit button to correct it.

**What the URL parser accepts**:
- Full GameChanger web URL: `https://web.gc.com/teams/{public_id}/any-slug`
- Mobile share URLs or any URL containing `/teams/{public_id}` in the path
- A bare public ID slug: `a1GFM9Ku0BbF`

**Discovered placeholder upgrade**: If a team was previously auto-discovered from an opponent's schedule (name-only, no public ID), pasting its URL will upgrade that existing placeholder record rather than creating a duplicate row.

### Team List Layout

The teams page shows two sections:

| Section | Contents |
|---------|---------|
| **Lincoln Program** | Teams with `is_owned = 1` -- LSB Freshman, JV, Varsity, Reserve, and any other owned teams. |
| **Tracked Opponents** | Teams with `is_owned = 0` -- opponents added manually or discovered via schedule. |

Newly discovered opponents appear in Tracked Opponents with status Inactive. An admin must activate them before they are included in crawls.

### Editing a Team

From either team table, click **Edit** on any team row to open the edit form at `/admin/teams/{team_id}/edit`. Editable fields: Name, Level, and Type (owned vs. tracked). Public ID and last-synced date are shown read-only.

### Activating and Deactivating Teams

The **Activate/Deactivate** button on each team row calls `POST /admin/teams/{team_id}/toggle-active`. Active teams (`is_active = 1`) are included when crawling with `--source db`. Deactivated teams are preserved in the database but excluded from crawls.

### Discovering Opponents

For any Lincoln Program team that has a public ID, click **Discover Opponents** to trigger automatic opponent discovery. The system calls `GET /public/teams/{public_id}/games`, extracts unique opponent names from the schedule, and inserts placeholder records for any opponents not already in the database.

**Important limitation**: The public games endpoint returns opponent names only -- no public ID or other identifier. Discovered opponents are stored as placeholders (`source = 'discovered'`, `public_id = NULL`, `is_active = 0`). To fully onboard a discovered opponent, paste their GameChanger URL via the Add Team form.

### Database-Driven Crawl Configuration

By default, `scripts/crawl.py` and `scripts/load.py` read team configuration from `config/teams.yaml`. Pass `--source db` to read active owned teams directly from the database instead:

```bash
python scripts/crawl.py --source db
python scripts/load.py --source db
```

Also available as `bb data crawl --source db` and `bb data load --source db`.

With `--source db`, both scripts query:
```sql
SELECT team_id, name, level FROM teams WHERE is_active = 1 AND is_owned = 1
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

Also available as `bb creds refresh`.

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

- **Credential expired**: Run `python scripts/refresh_credentials.py` (or `bb creds refresh`) and then `python scripts/smoke_test.py`.
- **Rate limited**: The HTTP session factory handles rate limiting automatically with 1--1.5 second delays between requests. If you hit rate limits, increase the delay: adjust `min_delay_ms` and `jitter_ms` in `src/http/session.py`.
- **Unknown endpoint error**: Check [docs/gamechanger-api.md](../gamechanger-api.md) for the current endpoint documentation.

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

*Last updated: 2026-03-07 | Source: E-055 (unified CLI), E-042 (admin team management), E-028-03 (original)*
