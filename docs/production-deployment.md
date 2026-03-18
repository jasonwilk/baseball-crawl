# Production Deployment Runbook

This runbook covers every step from a bare Linux server to a running baseball-crawl stack
accessible over HTTPS via Cloudflare Access. A developer who has never touched this project
can follow these steps end-to-end.

**Architecture overview**:

```
Internet  -->  Cloudflare (SSL, Zero Trust Access)  -->  Cloudflare Tunnel
    -->  Traefik (reverse proxy, port 80 inside Docker network)
    -->  FastAPI app (port 8000 inside Docker network)
    -->  SQLite (host-mounted at ./data/app.db)
```

---

## Prerequisites

Before starting, you need:

- A Linux server running **Ubuntu 24.04 LTS** (or equivalent -- Debian 12 works too).
  - Minimum: 1 vCPU, 1 GB RAM, 10 GB disk.
- SSH access to the server.
- A **Cloudflare account** with a domain whose DNS is managed by Cloudflare.
- The **Cloudflare Tunnel token** for this deployment (see Step 3).

---

## Step 1: Install Docker

If Docker is not yet installed on the server, install it using the official convenience script:

```bash
# Install Docker Engine
curl -fsSL https://get.docker.com | sh

# Add your user to the docker group (avoids needing sudo for docker commands)
sudo usermod -aG docker $USER

# Log out and back in for the group change to take effect, then verify:
docker --version
docker compose version
```

Both commands should print version numbers. This project requires Docker Compose v2 (bundled
with Docker Engine 23+). If `docker compose version` fails, install the plugin:

```bash
sudo apt-get install docker-compose-plugin
```

---

## Step 2: Clone and Configure

### 2.1 Clone the repository

```bash
cd /opt   # or any directory you prefer
git clone <repository-url> baseball-crawl
cd baseball-crawl
```

Replace `<repository-url>` with the actual Git remote URL.

### 2.2 Create the data directory

The SQLite database is host-mounted at `./data/app.db`. The application container runs as
a non-root user (`appuser`, UID 1000). Create the directory and set permissions so the
container can read/write the database:

```bash
mkdir -p data/backups
chown 1000:1000 data
chmod 755 data
```

> **Upgrading from an earlier version?** If `./data/` was previously created by root (or by
> a container running as root), update ownership: `sudo chown -R 1000:1000 data`

### 2.3 Create the `.env` file

```bash
cp .env.example .env
```

Edit `.env` with your production values. The required fields are:

```bash
# Open with your preferred editor
nano .env
```

Required settings for production:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_PATH` | `./data/app.db` | Keep the default -- matches the volume mount |
| `APP_ENV` | `production` | Enables production logging, disables debug features |
| `LOG_LEVEL` | `INFO` | Or `WARNING` to reduce noise |
| `CLOUDFLARE_TUNNEL_TOKEN` | `<token>` | From Step 3 below |
| `APP_URL` | `https://baseball.<your-domain>` | Used to construct magic link URLs |
| `WEBAUTHN_RP_ID` | `baseball.<your-domain>` | Must match the hostname browsers see |
| `WEBAUTHN_ORIGIN` | `https://baseball.<your-domain>` | Must be HTTPS in production |
| `MAILGUN_API_KEY` | `<key>` | Required for magic link email delivery |
| `MAILGUN_DOMAIN` | `mg.<your-domain>` | Your Mailgun sending domain |
| `MAILGUN_FROM_EMAIL` | `noreply@mg.<your-domain>` | From address for magic link emails |

Optional but recommended:

| Variable | Value | Notes |
|----------|-------|-------|
| `CF_ACCESS_CLIENT_ID` | `<client-id>` | Service token for crawler -> API calls |
| `CF_ACCESS_CLIENT_SECRET` | `<client-secret>` | Service token secret |

Leave these commented out or unset:
- `DEV_USER_EMAIL` -- dev bypass, must not be set in production
- `GC_TOKEN`, `GC_COOKIE` -- managed by `scripts/refresh_credentials.py`

### 2.4 Seed the first admin user

The admin UI requires at least one user in the database before the first login. After
starting the stack (Step 4), run:

```bash
sqlite3 data/app.db "INSERT INTO users (email) VALUES ('<YOUR_EMAIL>');"
```

Replace the email with the actual admin user's email. This is a one-time bootstrap step.

---

## Step 3: Configure Cloudflare Tunnel

Full Cloudflare Tunnel and Zero Trust Access setup is documented in
[docs/cloudflare-access-setup.md](cloudflare-access-setup.md). Summary of the steps
needed before first startup:

### 3.1 Create a tunnel and get the token

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) -> **Networks** -> **Tunnels**.
2. Click **Create a Tunnel** -> choose **Cloudflared** -> name it (e.g., `baseball-crawl-prod`).
3. On the next screen, Cloudflare shows a Docker run command with `--token <TOKEN>`. Copy the token value.
4. Set it in `.env`: `CLOUDFLARE_TUNNEL_TOKEN=<TOKEN>`

### 3.2 Configure public hostnames

In the tunnel configuration -> **Public Hostnames**, add:

| Subdomain | Domain | Type | URL |
|-----------|--------|------|-----|
| `baseball` | `<your-domain>` | HTTP | `traefik:80` |
| `api.baseball` | `<your-domain>` | HTTP | `traefik:80` |

Cloudflare creates DNS CNAME records automatically when you use the Public Hostnames tab.

### 3.3 Create Zero Trust Access applications

See [docs/cloudflare-access-setup.md](cloudflare-access-setup.md) sections 4 and 5 for
detailed steps. At minimum:

- Create a **Self-hosted application** for `baseball.<your-domain>` with a policy allowing
  coaching staff emails.
- Create a **Service Token** (`CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`) for
  crawler machine-to-machine access.

---

## Step 4: Start the Stack

```bash
docker compose up -d
```

This command:
1. Builds the `app` image from the `Dockerfile`.
2. Starts the `app` container, which runs database migrations then launches Uvicorn.
3. Starts `traefik` after the `app` health check passes (up to 15 seconds).
4. Starts `cloudflared` after the `app` health check passes.

Watch startup progress:

```bash
docker compose logs -f
```

All three services should be `Up` within 60 seconds. Only `app` will show `(healthy)` --
`traefik` and `cloudflared` have no healthcheck configured and show plain `Up`, which is normal.
Press Ctrl-C to stop following.

---

## Step 5: Verify

### 5.1 Health check (local)

```bash
# Direct to app container
curl -s http://localhost:8001/health
```

Expected response:

```json
{"status": "ok", "db": "connected"}
```

### 5.2 Check all containers are running

```bash
docker compose ps
```

All three services (`app`, `traefik`, `cloudflared`) should show `Up`. Only the `app`
service will also show `(healthy)` -- `traefik` and `cloudflared` have no healthcheck
configured and show plain `Up`, which is normal.

### 5.3 Tunnel connectivity

In the Cloudflare dashboard (**Networks** -> **Tunnels**), the tunnel status should show
**Healthy** within 30 seconds of startup.

Check cloudflared logs:

```bash
docker compose logs cloudflared
```

Expected log lines:

```
INF Connection registered connIndex=0 ...
INF Connection registered connIndex=1 ...
INF Registered tunnel connection ...
```

### 5.4 Health check through the tunnel

```bash
# Unauthenticated (health endpoint is excluded from Access policy)
curl -v https://baseball.<your-domain>/health

# Authenticated using CF Access service token
curl -s \
  -H "CF-Access-Client-Id: <your-client-id>" \
  -H "CF-Access-Client-Secret: <your-client-secret>" \
  https://baseball.<your-domain>/health
```

Expected: HTTP 200 with `{"status": "ok", "db": "connected"}` for both requests.

Note: `/health` is excluded from Cloudflare Access authentication so the unauthenticated
request should succeed without a browser login. The authenticated request verifies that
the CF Access service token is accepted end-to-end.

### 5.5 Dashboard access

1. Open `https://baseball.<your-domain>` in a browser.
2. Cloudflare redirects to the Access login page.
3. Authenticate using your email (a magic link will be emailed to you).
4. The dashboard should load.

### 5.6 Backup script available

Verify the backup script runs cleanly (requires the database to exist from Step 5.1):

```bash
python scripts/backup_db.py
```

Expected output: `Backup saved to /opt/baseball-crawl/data/backups/app-<timestamp>.db`

---

## Troubleshooting

### (a) Tunnel not connecting

**Symptoms**: cloudflared container exits immediately, or tunnel shows Inactive/Error in
Cloudflare dashboard.

**Diagnosis**:

```bash
docker compose logs cloudflared
```

Common errors:

| Log message | Cause | Fix |
|-------------|-------|-----|
| `Failed to get tunnel credentials` | Invalid or missing `CLOUDFLARE_TUNNEL_TOKEN` | Re-copy token from Cloudflare dashboard; check `.env` |
| `tunnel not found` | Token belongs to a deleted tunnel | Create a new tunnel, get a new token |
| `context deadline exceeded` | Server cannot reach Cloudflare (firewall/DNS) | Check outbound HTTPS (port 443) is allowed from the server |
| cloudflared exits but app/traefik are `Up` | App health check not yet passing when cloudflared started | Wait 30s and check again; `docker compose restart cloudflared` |

If the tunnel token is correct but the tunnel still shows Inactive:

```bash
# Verify the token is present without printing its value
docker compose exec cloudflared sh -c 'test -n "$TUNNEL_TOKEN" && echo "TUNNEL_TOKEN is set" || echo "TUNNEL_TOKEN is NOT set"'
```

### (b) Database not initializing

**Symptoms**: `curl http://localhost:8001/health` returns `{"status": "error", "db": "error"}`
or connection refused.

**Diagnosis**:

```bash
docker compose logs app
```

Common errors:

| Log message | Cause | Fix |
|-------------|-------|-----|
| `PermissionError: ./data/app.db` | `./data` directory not writable by container | `chmod 755 data` on the host |
| `No such file or directory: ./data` | `./data` directory missing | `mkdir -p data/backups` |
| Migration errors (SQL syntax, table exists) | Corrupted or partial migration state | Check `sqlite3 data/app.db "SELECT * FROM _migrations;"` |
| `ModuleNotFoundError` | Image not rebuilt after dependency changes | `docker compose up -d --build app` |

If the database file exists but migrations failed partway through:

```bash
# Check what migrations have been applied
sqlite3 data/app.db "SELECT * FROM _migrations;"

# Check integrity
sqlite3 data/app.db "PRAGMA integrity_check;"
```

If `integrity_check` returns anything other than `ok`, restore from backup (see
Backup and Migration section below).

### (c) App container crashing on startup

**Symptoms**: `docker compose ps` shows `app` as `Restarting` or `Exited`.

**Diagnosis**:

```bash
docker compose logs app --tail=50
```

Common causes:

| Symptom | Cause | Fix |
|---------|-------|-----|
| Uvicorn import errors | Missing or incompatible Python dependency | `docker compose up -d --build app` to rebuild |
| `WEBAUTHN_RP_ID` errors | RP ID mismatch between env and browser origin | Ensure `WEBAUTHN_RP_ID` matches the hostname, `WEBAUTHN_ORIGIN` includes scheme |
| Port 8000 already in use | Another process is using port 8000 inside the container | This should not happen in a fresh Docker Compose deployment; check for conflicting containers with `docker ps` |
| `DATABASE_PATH` pointing to nonexistent directory | `./data` does not exist | `mkdir -p data` on the host |
| Out of disk space | Logs, images, or database filled the disk | `df -h` to check; `docker system prune` to remove unused images |

After fixing the root cause, restart:

```bash
docker compose up -d
docker compose ps  # verify all services are Up
```

---

## Backup and Migration

### Database location

The SQLite database is host-mounted at `./data/app.db` on the server filesystem. This
means the database survives container restarts and image rebuilds -- it is not stored inside
the container.

### Routine backup

Create a timestamped backup at any time:

```bash
python scripts/backup_db.py
```

This copies `data/app.db` to `data/backups/app-<timestamp>.db`. The backups directory is
created automatically. Backups are not automatically deleted -- manage disk usage manually
or add a cron job to prune old backups:

```bash
# Example: keep backups from the last 30 days
find data/backups -name "*.db" -mtime +30 -delete
```

For a scheduled daily backup, add a cron entry:

```bash
crontab -e
# Add:
0 2 * * * cd /opt/baseball-crawl && python scripts/backup_db.py >> data/backups/backup.log 2>&1
```

### Restore from backup

```bash
# 1. Stop the application
docker compose down

# 2. Replace the database with the backup (example timestamp)
cp data/backups/app-2026-03-04T020000.db data/app.db

# 3. Restart
docker compose up -d

# 4. Verify
curl -s http://localhost:8001/health
sqlite3 data/app.db "PRAGMA integrity_check; PRAGMA journal_mode;"
```

A healthy database returns `ok` and `wal`.

### Server migration

When moving the stack to a new server:

1. **Stop the stack** on the old server: `docker compose down`
2. **Back up the database**: `python scripts/backup_db.py`
3. **Clone the repository on the new server** and follow this runbook through Step 2.3
   (`.env` setup) before copying any data:
   ```bash
   # On the new server:
   cd /opt
   git clone <repository-url> baseball-crawl
   mkdir -p baseball-crawl/data/backups
   ```
4. **Copy the database and `.env`** from the old server to the new server:
   ```bash
   # From the old server:
   rsync -av data/backups/app-<latest>.db newserver:/opt/baseball-crawl/data/app.db
   rsync -av .env newserver:/opt/baseball-crawl/.env
   ```
5. **Before starting the stack**, verify the database file is in place at `./data/app.db`.
6. **Start the stack**: `docker compose up -d`
7. **Verify** using the health check and tunnel connectivity steps in Step 5.
8. **Update the Cloudflare Tunnel** if the tunnel token is tied to the old server (create a
   new tunnel if needed, following Step 3).

Note: The `./data/backups/` directory does not need to be migrated -- it contains historical
backups only. The active database file (`data/app.db`) is what matters.

---

## Verified on

<!-- Operator: fill in after verifying on a real server -->

| Check | Result | Date | Notes |
|-------|--------|------|-------|
| All services start within 60s, healthy/running | Verified on: | | |
| `restart: unless-stopped` on all services | Verified on: | | |
| Dashboard reachable at `https://baseball.<domain>` from external browser | Verified on: | | |
| Health check returns 200 from external curl | Verified on: | | |
| Backup script creates backup file | Verified on: | | |

---

*Last updated: 2026-03-04 | Story: E-009-07*
