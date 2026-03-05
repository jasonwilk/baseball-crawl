# Getting Started

This guide walks through setting up the baseball-crawl development environment from a fresh clone.

## Prerequisites

- **Git** (any recent version)
- **Docker** and **Docker Compose** (for running the application stack)
- **Python 3.13** (if running scripts outside the container; the devcontainer installs this automatically)

**Recommended**: Use the VS Code devcontainer. It provides Python 3.13, Docker-in-Docker, Node.js, GitHub CLI, and all VS Code extensions pre-configured.

## Clone and Setup

```bash
git clone <repository-url>
cd baseball-crawl
```

### Install Git Hooks

The project includes a PII pre-commit hook that scans staged files for credentials before each commit. Set it up once after cloning:

```bash
./scripts/install-hooks.sh
```

This configures Git to use the `.githooks/` directory and ensures the pre-commit hook is executable. You can verify it works with:

```bash
git commit --allow-empty -m 'test hook'
```

### Install Python Dependencies

If working outside the devcontainer:

```bash
pip install -r requirements.txt
```

The devcontainer runs this automatically via its `postCreateCommand`.

## Start the Development Stack

The Docker Compose stack includes three services: the FastAPI app, Traefik (reverse proxy), and cloudflared (Cloudflare Tunnel). For local development, only the app and Traefik are needed -- cloudflared requires a tunnel token configured in `.env`.

```bash
docker compose up -d
```

This builds the app image (if not cached), runs database migrations, and starts all services. The app container runs `migrations/apply_migrations.py` on every startup, so the database schema is always current.

### Access Points

| URL | Service | Notes |
|-----|---------|-------|
| `http://localhost:8001` | FastAPI app (direct) | Bypasses Traefik. Use for health checks and debugging. |
| `http://localhost:8000` | Traefik -> FastAPI | Routes by Host header. |
| `http://localhost:8180` | Traefik dashboard | Dev-only admin UI for Traefik. |

### Verify the Stack

```bash
curl -s http://localhost:8001/health
```

Expected response:

```json
{"status": "ok", "db": "connected"}
```

If the health check fails, see [Operations: Troubleshooting](operations.md#troubleshooting).

## Seed the Development Database

The database is created empty by migrations. To load sample data for development:

```bash
python scripts/seed_dev.py
```

This executes `data/seeds/seed_dev.sql`, which uses `INSERT OR IGNORE` so it can be run multiple times safely.

Alternatively, use the reset script to drop the database, re-run migrations, and load seed data in one step:

```bash
python scripts/reset_dev_db.py
```

After seeding, visit `http://localhost:8001/dashboard` to see the batting stats dashboard with sample data.

**Note**: If the app is running in Docker, you may need to restart it after seeding so it picks up the new data:

```bash
docker compose restart app
```

## Verify the Dashboard

Open `http://localhost:8001/dashboard` in a browser. You should see a table of batting statistics. If you see an empty table, confirm the database was seeded (see above).

## Run Tests

```bash
pytest
```

All tests mock HTTP requests at the transport layer -- no network calls are made, and no running stack is required. Tests cover:

- API health endpoint (`test_api_health.py`)
- GameChanger client (`test_client.py`)
- Credential parser (`test_credential_parser.py`)
- Dashboard routes (`test_dashboard.py`)
- HTTP session and headers (`test_http_session.py`, `test_http_headers.py`, `test_http_discipline.py`)
- Database migrations (`test_migrations.py`)
- Seed data loading (`test_seed.py`)
- PII scanning (`test_pii_scanner.py`, `test_pii_hook_integration.py`)

## Credential Management

GameChanger API credentials are short-lived and must be refreshed frequently. Credentials are stored in `.env` (git-ignored) and never committed.

### Refresh Credentials

1. Log in to [web.gc.com](https://web.gc.com) in a browser.
2. Open DevTools (F12) -> Network tab.
3. Trigger any GameChanger API request (e.g., navigate to a team page).
4. Right-click the request -> Copy -> Copy as cURL.
5. Save the cURL command to `secrets/gamechanger-curl.txt`, then run:

```bash
python scripts/refresh_credentials.py
```

Or pass the cURL command inline:

```bash
python scripts/refresh_credentials.py --curl "curl 'https://...' -H 'gc-token: ...'"
```

The script extracts auth tokens from the cURL command and writes them to `.env`, preserving any existing non-credential values.

### Verify API Access

After refreshing credentials, run the smoke test to verify end-to-end API connectivity:

```bash
python scripts/smoke_test.py
```

This calls three GameChanger endpoints (`/me/teams`, game summaries, and players) and prints a summary table. All endpoints should show `OK`.

## Environment Variables

Key variables in `.env`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_PATH` | Path to the SQLite database file. Defaults to `./data/app.db`. |
| `APP_ENV` | Runtime environment (`development` or `production`). |
| `LOG_LEVEL` | Logging level for the FastAPI app (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `GAMECHANGER_AUTH_TOKEN` | GameChanger API auth token (written by `refresh_credentials.py`). |
| `GAMECHANGER_DEVICE_ID` | GameChanger device identifier (written by `refresh_credentials.py`). |
| `GAMECHANGER_BASE_URL` | GameChanger API base URL (written by `refresh_credentials.py`). |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel token (production only). |
| `CF_ACCESS_CLIENT_ID` | Cloudflare Access service token client ID (production only). |
| `CF_ACCESS_CLIENT_SECRET` | Cloudflare Access service token secret (production only). |

---

*Last updated: 2026-03-03 | Story: E-028-03*
