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

## Add Teams

Teams are configured through the admin UI, not by editing configuration files directly.

1. Start the stack and visit `http://localhost:8001/admin/teams`.
2. Paste a GameChanger team URL for each LSB team (Freshman, JV, Varsity, Reserve) and select **Lincoln Program** as the team type.
3. Click **Discover Opponents** on each Lincoln team to populate tracked opponents from their schedules.
4. Activate any opponents you want to track.

The admin UI calls the public GameChanger API (no credentials required) to resolve the team name and location from the URL.

**Note on `config/teams.yaml`**: The YAML file remains available as a bootstrap mechanism, but it is no longer the primary team configuration path. The admin UI and the `--source db` flag on `scripts/crawl.py` / `scripts/load.py` are the recommended workflow for ongoing operation. See [Operations: Admin Team Management](operations.md#admin-team-management) for the full workflow.

---

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

Also available as `bb db reset`.

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

GameChanger API credentials are stored in `.env` (git-ignored) and never committed. Two credential profiles are supported:

### Web Profile (auto-refreshing)

1. Log in to [web.gc.com](https://web.gc.com) in a browser.
2. Open DevTools (F12) -> Network tab.
3. Trigger any GameChanger API request (e.g., navigate to a team page).
4. Right-click the request -> Copy -> Copy as cURL.
5. Import credentials:

```bash
bb creds import --curl "curl 'https://...' -H 'gc-token: ...'"
```

Or save the cURL command to `secrets/gamechanger-curl.txt` and run `bb creds import`.

Web credentials refresh programmatically (`bb creds refresh`). With login fallback (E-085), the web profile requires no manual recapture beyond the initial setup.

### Mobile Profile (proxy-assisted)

Mobile credentials are captured via mitmproxy from the iOS GameChanger app:

1. Start mitmproxy on the Mac host (`cd proxy && ./start.sh`)
2. Configure your iPhone to use the proxy (see [mitmproxy guide](mitmproxy-guide.md#iphone-proxy-configuration))
3. Open GameChanger on the iPhone and navigate to any page
4. Stop the proxy (`cd proxy && ./stop.sh`) and disable the iPhone proxy
5. Extract credentials:

```bash
bb creds capture --profile mobile
```

Or import from a curl command with the mobile profile flag:

```bash
bb creds import --profile mobile --curl "curl 'https://...' -H 'gc-token: ...'"
```

The mobile access token lasts ~12 hours. Programmatic refresh is not available -- recapture via proxy when it expires. See [mitmproxy guide](mitmproxy-guide.md#mobile-credential-capture) for the full workflow.

### Verify API Access

After capturing credentials, verify connectivity:

```bash
bb creds check                   # web profile (default)
bb creds check --profile mobile  # mobile profile
```

## Environment Variables

Key variables in `.env`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_PATH` | Path to the SQLite database file. Defaults to `./data/app.db`. |
| `APP_ENV` | Runtime environment (`development` or `production`). |
| `LOG_LEVEL` | Logging level for the FastAPI app (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `GAMECHANGER_REFRESH_TOKEN_WEB` | GameChanger refresh token JWT (14-day, self-renewing). See `docs/api/auth.md`. |
| `GAMECHANGER_CLIENT_ID_WEB` | GameChanger client ID (static, from app bundle). |
| `GAMECHANGER_CLIENT_KEY_WEB` | GameChanger HMAC signing key (static, from app bundle). **Secret.** |
| `GAMECHANGER_DEVICE_ID_WEB` | GameChanger device identifier (stable hex string). |
| `GAMECHANGER_ACCESS_TOKEN_MOBILE` | Mobile access token (~12-hour lifetime, proxy-captured). |
| `GAMECHANGER_REFRESH_TOKEN_MOBILE` | Mobile refresh token (14-day lifetime, proxy-captured). |
| `GAMECHANGER_CLIENT_ID_MOBILE` | Mobile client ID (from iOS app, proxy-captured). |
| `GAMECHANGER_DEVICE_ID_MOBILE` | Mobile device identifier (proxy-captured). |
| `GAMECHANGER_USER_EMAIL` | GameChanger account email. **PII.** |
| `GAMECHANGER_USER_PASSWORD` | GameChanger account password. **Secret.** |
| `GAMECHANGER_BASE_URL` | GameChanger API base URL (written by `refresh_credentials.py`). |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel token (production only). |
| `CF_ACCESS_CLIENT_ID` | Cloudflare Access service token client ID (production only). |
| `CF_ACCESS_CLIENT_SECRET` | Cloudflare Access service token secret (production only). |

---

*Last updated: 2026-03-10 | Source: E-086 (mobile credentials), E-055 (unified CLI), E-042 (team onboarding via admin UI), E-028-03 (original)*
