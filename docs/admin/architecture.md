# Architecture

## System Overview

Baseball-crawl is a coaching analytics platform for the Lincoln Standing Bear (LSB) High School baseball program. It extracts game data from the GameChanger API, stores it in a SQLite database, and serves a web dashboard for coaching staff to review batting stats, scouting reports, and opponent analysis.

The system is designed for a small-scale deployment: 4 teams (Freshman, JV, Varsity, Reserve), roughly 12--15 players per team, and approximately 30 games per team per season. The primary users are Jason (system operator) and the LSB coaching staff (dashboard consumers).

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **FastAPI app** | Python 3.13, FastAPI 0.115, Uvicorn | Serves the web dashboard (Jinja2 templates) and a JSON health endpoint. Runs inside a Docker container on port 8000. |
| **SQLite database** | SQLite with WAL mode | Stores players, teams, rosters, games, per-game/per-season batting and pitching stats, and coaching assignments. Located at `data/app.db` (host-mounted volume). |
| **Docker Compose stack** | Docker Compose | Orchestrates three services: the FastAPI app, Traefik (reverse proxy), and cloudflared (Cloudflare Tunnel). |
| **Traefik** | Traefik v3 | Reverse proxy that routes requests by `Host` header. In development, accessible at `http://localhost:8000`. Waits for the app health check before accepting traffic. |
| **Cloudflare Tunnel** | cloudflared | Exposes the stack to the internet through Cloudflare's network. Handles SSL termination and integrates with Cloudflare Zero Trust for access control. |
| **Agent ecosystem** | Claude Code agents | AI agents that manage the project: planning, coding, API exploration, domain expertise, and documentation. See [Agent Guide](agent-guide.md). |

## Data Flow

```
GameChanger Web UI
       |
       | (browser DevTools -> copy as cURL)
       v
refresh_credentials.py  -->  .env (auth tokens)
       |
       v
GameChanger API  <--  src/gamechanger/client.py (authenticated HTTP client)
       |
       | (JSON responses)
       v
src/gamechanger/  (parse & transform)
       |
       v
SQLite database (data/app.db)
       |
       | (SQL queries via src/api/db.py)
       v
FastAPI + Jinja2 templates
       |
       v
Dashboard (browser)  <--  Traefik  <--  Cloudflare Tunnel  <--  Internet
```

1. **Credential capture**: Copy a GameChanger API request as a cURL command from browser DevTools. Run `scripts/refresh_credentials.py` to extract auth tokens into `.env`.
2. **Data extraction**: The `src/gamechanger/client.py` module calls the GameChanger API using credentials from `.env`. All HTTP requests go through the shared session factory (`src/http/session.py`) which handles browser-like headers, rate limiting, and cookie persistence.
3. **Storage**: Parsed data is inserted into the SQLite database via SQL. Migrations are managed by `migrations/apply_migrations.py`.
4. **Serving**: The FastAPI app reads from SQLite and renders Jinja2 templates for the dashboard. The health endpoint (`GET /health`) checks database connectivity.
5. **Access**: In production, Cloudflare Tunnel routes internet traffic through Traefik to the app. Cloudflare Zero Trust Access policies control who can reach the dashboard and API.

## Directory Structure

```
baseball-crawl/
  src/
    api/              # FastAPI app: routes, templates, static files, db module
    gamechanger/      # GameChanger API client and credential parser
    http/             # Shared HTTP session factory and browser headers
    safety/           # PII scanning module
  tests/              # pytest test suite (mocked HTTP, no network calls)
  migrations/         # Numbered SQL migration files and the migration runner
  scripts/            # Utility scripts (credential refresh, seeding, backup, smoke test)
  data/
    seeds/            # Development seed SQL (committed to git)
    app.db            # Runtime SQLite database (git-ignored, host-mounted)
    backups/          # Timestamped database backups (git-ignored)
  docs/               # API specs, guides, and this admin documentation
  epics/              # Active epics and story files (project management)
  .project/           # Archive, ideas, research, templates
  .claude/            # Agent definitions, rules, skills, hooks, memory
  .githooks/          # Git hooks (PII pre-commit scan)
  .devcontainer/      # VS Code devcontainer configuration
```

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.13 | Governed by `.python-version`. All dependencies support 3.13. Version synced across `pyproject.toml`, `Dockerfile`, and `devcontainer.json`. |
| **HTTP client** | httpx 0.28 | Async-capable, supports cookie jars and custom transports. Used for all GameChanger API calls. |
| **Web framework** | FastAPI 0.115 + Uvicorn 0.34 | Lightweight async framework. Serves both JSON endpoints and server-rendered HTML via Jinja2. |
| **Database** | SQLite (WAL mode) | Simple, zero-configuration, file-based. Sufficient for the data volume (~30 games x 4 teams). WAL mode enables concurrent reads during writes. |
| **Templating** | Jinja2 3.1 | Server-side HTML rendering for the dashboard. No client-side JavaScript framework. |
| **Testing** | pytest 8.3 + pytest-asyncio | All tests mock HTTP at the transport layer. No real network calls in the test suite. |
| **Reverse proxy** | Traefik v3 | Docker-native, label-based routing. No config files needed beyond `docker-compose.yml`. |
| **Tunnel** | Cloudflare Tunnel (cloudflared) | Secure exposure without opening ports. Handles SSL and integrates with Zero Trust access policies. |
| **Container** | Docker Compose | Single `docker-compose.yml` defines all services. The app container runs migrations on startup. |

## Cross-References

- **GameChanger API**: Full endpoint documentation in [docs/gamechanger-api.md](../gamechanger-api.md).
- **HTTP discipline**: Session factory, rate limiting, and header profile in [docs/http-integration-guide.md](../http-integration-guide.md).
- **Cloudflare setup**: Tunnel creation, Zero Trust policies, and DNS configuration in [docs/cloudflare-access-setup.md](../cloudflare-access-setup.md).

---

*Last updated: 2026-03-04 | Story: E-003-02*
