# Production Deployment Runbook

This runbook covers every step from a bare Linux server to a running baseball-crawl stack
accessible over HTTPS at https://bbstats.ai via Cloudflare Tunnel. A developer who has
never touched this project can follow these steps end-to-end.

**Architecture overview**:

```
Internet  -->  Cloudflare (SSL termination)  -->  Cloudflare Tunnel bbstats-ai
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
| `APP_URL` | `https://bbstats.ai` | Used to construct magic link URLs |
| `WEBAUTHN_RP_ID` | `bbstats.ai` | Must match the hostname browsers see |
| `WEBAUTHN_ORIGIN` | `https://bbstats.ai` | Must be HTTPS in production |
| `MAILGUN_API_KEY` | `<key>` | Required for magic link email delivery |
| `MAILGUN_DOMAIN` | `mg.bbstats.ai` | Sending domain (see Mailgun DNS prerequisite below) |
| `MAILGUN_FROM_EMAIL` | `noreply@` + your `MAILGUN_DOMAIN` | From address for magic link emails (see `.env.example`) |
| `ADMIN_EMAIL` | `<jason's-email>` | Bootstrap admin access |

Optional -- scheduled reports:

| Variable | Value | Notes |
|----------|-------|-------|
| `OPERATING_TIMEZONE` | `America/Chicago` | IANA timezone name. Controls the venue-local "today" that `bb report morning-run` defaults its target date to (see [operations.md](operations.md#morning-run-scheduled-reports)); an explicit `--date` still overrides it. Defaults to `America/Chicago` if unset; an invalid value falls back to the default with a logged warning. |

Optional -- Cloudflare management (not needed for tunnel runtime):

| Variable | Value | Notes |
|----------|-------|-------|
| `CLOUDFLARE_API_TOKEN` | `<token>` | Scoped management token (see [cloudflare-access-setup.md](cloudflare-access-setup.md) Section 6) -- NOT the tunnel token |

Leave these unset in production:
- `DEV_USER_EMAIL` -- dev bypass, must not be set when `APP_ENV=production` (app fails to start)
- `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` -- not needed; CF Access is not enforcing policies for bbstats.ai

> **Mailgun DNS prerequisite**: Before magic link emails will deliver from `mg.bbstats.ai`,
> complete Mailgun DNS verification: add the SPF and DKIM TXT records Mailgun provides to
> the `bbstats.ai` zone in Cloudflare DNS. Without these records, Mailgun silently
> refuses delivery.

### 2.4 Bootstrap GameChanger credentials

Add your GameChanger account credentials to `.env`:

| Variable | Value |
|----------|-------|
| `GAMECHANGER_USER_EMAIL` | Your GameChanger account email |
| `GAMECHANGER_USER_PASSWORD` | Your GameChanger account password |

Then run the credential bootstrap command inside the app container -- the `bb` console script is installed only there (no host-side install step; see the Dockerfile):

```bash
docker compose exec app bb creds setup web
```

This executes the programmatic login flow using your credentials, stores the resulting session tokens, and verifies API connectivity. For details on the authentication architecture and token lifetimes, see [docs/api/auth.md](../api/auth.md).

> **Keep these variables in `.env` for ongoing resilience.** `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` are not just for one-time bootstrap. When the refresh token expires (every 14 days if not renewed sooner), the system uses these credentials to perform the full login flow automatically. If they are absent, expiry causes a `CredentialExpiredError` requiring manual intervention. Retaining them means routine token expiry is handled without operator action.

### 2.5 Seed the first admin user

The admin UI requires at least one user in the database before the first login. After
starting the stack (Step 4), run:

```bash
sqlite3 data/app.db "INSERT INTO users (email) VALUES ('<YOUR_EMAIL>');"
```

Replace the email with the actual admin user's email. This is a one-time bootstrap step.

---

## Step 3: Configure Cloudflare Tunnel

Full Cloudflare setup is documented in
[cloudflare-access-setup.md](cloudflare-access-setup.md). Summary of the steps
needed before first startup:

> **⚠️ Pre-go-live required**: Before bringing the tunnel live, you MUST remove the two
> blocking CF Access policies from the `bbstats-ai` Access application. If active policies
> remain, all non-Jason traffic will be blocked by Cloudflare Access -- including anyone
> opening a shared scouting-report link. See the mandatory pre-go-live step in
> [cloudflare-access-setup.md](cloudflare-access-setup.md) Section 2.

### 3.1 Create a tunnel and get the token

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) -> **Networks** -> **Tunnels**.
2. Click **Create a Tunnel** -> choose **Cloudflared** -> name it **`bbstats-ai`**.
3. On the next screen, Cloudflare shows a Docker run command with `--token <TOKEN>`. Copy the token value.
4. Set it in `.env`: `CLOUDFLARE_TUNNEL_TOKEN=<TOKEN>`

### 3.2 Configure public hostnames

In the tunnel configuration -> **Public Hostnames**, add:

| Subdomain | Domain | Type | URL |
|-----------|--------|------|-----|
| *(leave blank)* | `bbstats.ai` | HTTP | `traefik:80` |

Leave the Subdomain field blank to route the apex domain `bbstats.ai`. Cloudflare creates
the DNS CNAME record automatically when you use the Public Hostnames tab.

### 3.3 Remove blocking CF Access policies (pre-go-live required)

See [cloudflare-access-setup.md](cloudflare-access-setup.md) Section 2 for the
full removal procedure. The `bbstats-ai` Access application currently has two active
blocking policies that must be removed before the tunnel goes live. Skipping this step
blocks all visitors, including anyone opening a shared scouting-report link.

### 3.4 Scoped API token (optional)

A scoped management token (`CLOUDFLARE_API_TOKEN`) enables programmatic Cloudflare API
access (DNS updates, Access config). See [cloudflare-access-setup.md](cloudflare-access-setup.md)
Section 6 for permissions, creation steps, and the distinction from the tunnel token.

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
# Health endpoint -- no authentication required
curl -v https://bbstats.ai/health
```

Expected: HTTP 200 with `{"status": "ok", "db": "connected"}`.

The health endpoint is publicly accessible -- no CF Access authentication or app login required.

### 5.5 Admin login and report access

1. Open `https://bbstats.ai/admin/reports` in a browser.
2. The app login page loads directly (no CF Access redirect).
3. Log in via magic link (email) or passkey.
4. The Reports admin page should load, listing any generated reports.
5. Generate a report (see [operations.md: Standalone Reports](operations.md#standalone-reports)) and open its `/reports/{slug}` link in a private/incognito window -- it should load with **no login required**. Shared scouting reports are public by design; only `/admin/*` requires authentication.

### 5.6 Backup script available

Verify the backup script runs cleanly (requires the database to exist from Step 5.1). The `backup_db.py` script is installed only inside the app container, so run it via `docker compose exec`:

```bash
docker compose exec -T app python scripts/backup_db.py
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

**Required, scheduled -- not an optional cleanup step.** Schedule a daily backup via cron
(below) on every production deployment. `backup_db.py` is installed only inside the app
container (no host-side install step), so invoke it via `docker compose exec` (also
available as `bb db backup` -- both run the same `backup_database()`):

```bash
docker compose exec -T app python scripts/backup_db.py
```

This copies `data/app.db` to `data/backups/app-<timestamp>.db`. The backups directory is
created automatically. Backups are not automatically deleted -- manage disk usage manually
or add a cron job to prune old backups:

```bash
# Example: keep backups from the last 30 days
find data/backups -name "*.db" -mtime +30 -delete
```

**Copy every backup off the host disk.** `data/backups/` is inside the same host-mounted
`./data` volume as `app.db` -- a backup left there is destroyed alongside the database on
disk loss (dead disk, corrupted filesystem, host wipe). A backup that never leaves `./data`
protects against nothing but an accidental `DELETE`. After each scheduled backup, copy the
newest file to storage on a *different* disk -- another machine, network share, or object
storage:

```bash
# Example: rsync the newest backup to a second machine
rsync -av "$(ls -t data/backups/app-*.db | head -1)" backup-host:/srv/baseball-crawl-backups/
```

(`backup_database()` itself always writes under `./data/backups/` with no output-target
option -- the off-host copy is a runbook step, not a script flag.)

For the **required** daily schedule, add a cron entry that runs the backup and the
off-host copy together, inside the container's host:

```bash
crontab -e
# Add (2 AM daily -- backup, then copy the fresh file off-host):
0 2 * * * cd /opt/baseball-crawl && docker compose exec -T app python scripts/backup_db.py >> data/backups/backup.log 2>&1 && rsync -av "$(ls -t data/backups/app-*.db | head -1)" backup-host:/srv/baseball-crawl-backups/ >> data/backups/backup.log 2>&1
```

Replace `backup-host:/srv/baseball-crawl-backups/` with your actual off-host destination.

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
2. **Back up the database**: `docker compose exec -T app python scripts/backup_db.py` (run before Step 1 stops the stack, or start the stack briefly to take the backup)
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

## Closure Runtime Smoke (Step 1d)

Every epic closure that touches a runtime or build-input surface runs a live smoke test
against the reports flow before the closure commit lands
(`.claude/skills/implement/SKILL.md`, Step 1d). It runs in the main checkout, post-merge,
against the **live dev database** -- not CI, and not the epic worktree (which has no `bb`,
no Docker, no `.env`, no `data/`). This section documents the operator-owned setup that
procedure depends on.

### The `.smoke-fixture` file

Step 1d reads a gitignored, two-field file at the repo root -- `.smoke-fixture` -- **never
`.env`** (the credential-read guard blocks any Bash command naming `.env*`, so a fixture
stored there would be unreadable to the reviewer that must read it). Create it once, using
LSB's own real GameChanger identifiers:

```
generate=<public_id>
morning-run=<lsb-team-url-1> <lsb-team-url-2> ...
```

- `generate` -- the `public_id` slug `bb report generate` runs against.
- `morning-run` -- one or more LSB team URLs, space-separated, passed positionally to
  `bb report morning-run --dry-run`.

Both values are real LSB identifiers and must never be committed -- `.smoke-fixture` is
already in `.gitignore`.

**`generate` target requirement: high play-by-play coverage.** The team pinned for
`generate` must have a plays-rich corpus, or the reconciliation reading that follows is
vacuous. When pinning it, verify coverage in the dev DB with a count of games that
actually carry play-by-play rows -- data-bearing, not a bare games count, since
scored-but-empty games are the modal case.

The fixture was previously also required to be a **terminal** team (a completed season
gaining no further games), for one reason: a static corpus could not produce a self-caused
ingestion delta that would false-trip the one-way ratchet. That gate was retired on
2026-07-26, so nothing now turns on staticness or on the ordering of the checks below. The
currently pinned team happens to be terminal and needs no change.

### What the smoke checks (in order)

1. **Preflight** (an environment problem, not an epic defect, if any of these fail):
   `.smoke-fixture` present with both fields non-empty; the app stack up -- rebuilt, not
   just started, when the closure touched a build input (`docker compose up -d --build app`);
   credentials live for the web profile (`bb creds check --profile web` -- **not** the bare
   multi-profile `bb creds check`, which can exit 0 on a mixed state where a valid mobile
   profile masks a dead web profile, and the smoke's `bb report generate` uses the web
   profile).
2. **`bb report generate <generate public_id>`** -- run it first so the scoreboard below
   reads the state this run produced. The printed `reference_date` must equal today
   in the operating timezone.
3. **`curl -s http://localhost:8001/health`** -- the app answers.
4. **`bb report reconcile-scoreboard --json`** -- `self_games` must be `0`, a hard zero.
   That is the only assertion; **ignore the command's exit code**, which can still be
   non-zero from the vestigial baseline diff left behind by the retired ratchet gate.
5. **`bb report morning-run --dry-run <morning-run urls>`** -- asserts exit `0` only,
   order-independent after the health check. On an arbitrary closure date LSB usually has
   no games, so this step gates the entry-point wiring and schedule-read path, not the
   resolution ladder.

This procedure is normally run by the code-reviewer as part of epic closure. An operator can
run the same sequence manually at any time as a health check against the live database.

---

## Verified on

<!-- Operator: fill in after verifying on a real server -->

| Check | Result | Date | Notes |
|-------|--------|------|-------|
| All services start within 60s, healthy/running | Verified on: | | |
| `restart: unless-stopped` on all services | Verified on: | | |
| Dashboard reachable at `https://bbstats.ai` from external browser | Verified on: | | |
| Health check returns 200 from external curl | Verified on: | | |
| Backup script creates backup file | Verified on: | | |
| Scheduled backup cron entry runs and the off-host copy lands | Verified on: | | |

---

*Last updated: 2026-07-12 | Source: E-259 (E-259-06: removed the `bb report verify-aggregates` closure sub-check from the Closure Runtime Smoke procedure -- the command and the stored `player_season_*` tables it checked were retired in E-259-03/04), E-157-02 (original), E-252-05 (added OPERATING_TIMEZONE env var), E-255-05 (Truth Sweep: fixed relocation-stale operations.md/auth.md links; corrected bare host commands -- `bb creds setup web` and `python scripts/backup_db.py` -- to the `docker compose exec` form, since the package is installed only inside the app container; rewrote the dashboard-access verification to the current admin-login-plus-public-reports model), E-256-10 (required daily backup cadence + off-host copy step in Routine backup; added the Closure Runtime Smoke (Step 1d) section documenting the `.smoke-fixture` file and the operator-facing smoke procedure), E-262-07 (synced Step 1d to the settled skill text: preflight now names `bb creds check --profile web`; added the terminal-fixture `generate`-target requirement, one-time bootstrap re-snapshot, and plays-coverage check to the `.smoke-fixture` section)*
