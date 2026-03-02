# E-009: Tech Stack Redesign -- Portable, Agent-Browsable, Cloudflare-Integrated

## Status
`ACTIVE`

## Overview
Decide and implement the right serving-layer stack for baseball-crawl: either fully native
Cloudflare (Workers + D1 + Pages) or Docker Compose on a Linux server fronted by Cloudflare
Tunnel and Zero Trust Access. Both options are first-class candidates. Research spikes evaluate
each. The choice drives E-004 (Coaching Dashboard) and all future serving-layer work.

## Background & Context

### What Exists Today
The current architecture is fully Cloudflare-native: D1 (SQLite at edge) for the database,
Workers for API/ETL, and Pages for the eventual coaching dashboard. The crawling and loading
layer is Python, but everything that "runs" -- the API, the scheduled jobs, the frontend --
is designed to live inside Cloudflare's runtime.

The previous plan for local development (IDEA-001) assumed we would wrap Cloudflare's own
local dev tools (Miniflare, `wrangler dev`) to simulate the runtime locally. That approach
has a fundamental problem: it keeps us tied to Cloudflare's toolchain even in development,
and Cloudflare's local dev story has historically been inconsistent and lagged behind
production behavior.

### Why the Rethink
The user has raised three problems with the current direction:

1. **Local/prod friction**: Iterating on dashboards requires pushing to Cloudflare. Every
   change = a deploy cycle. This is untenable for the dashboard-heavy E-004 work ahead.

2. **Agent feedback loops**: The baseball-coach agent needs to *browse* the coaching
   dashboard as it's being developed -- checking layout, mobile rendering, and data
   presentation -- not just hit JSON endpoints. A cloud-only dashboard makes this workflow
   extremely awkward. A locally-running HTTP server makes it natural.

3. **Portability and control**: Cloudflare D1 and Workers are proprietary runtimes. The
   project is small (4 teams, ~15 players each, ~30 games/season). There is no scale
   argument for a distributed edge database. A plain SQLite file in a Docker volume -- or
   any standard relational database -- serves this data volume trivially.

### The Two Deployment Options

This epic evaluates and decides between two first-class deployment paths:

**Option A -- Native Cloudflare**
Keep the serving layer in Cloudflare's runtime: Workers (API/ETL), D1 (database), Pages
(dashboard). Use `wrangler dev` for local development, with its known friction. This path
keeps the stack minimal (no servers to manage) and benefits from Cloudflare's global
network.

**Option B -- Docker + Cloudflare Access (n8n-wilk-io pattern)**
Run the full stack (API, database, dashboard) in Docker Compose on a single Linux server.
Use Cloudflare Tunnel for all inbound traffic (no exposed ports) and Cloudflare Zero Trust
Access for authentication (service tokens, WARP, public bypass). This is the pattern used
by the n8n-wilk-io production deployment -- battle-tested and fully documented.

The same `docker-compose.yml` runs locally and in production. Environment variables are
the only difference between dev and prod. No platform-specific config files, no Fly.io
account, no Render dashboard. Just: clone repo, `docker compose up`.

### The n8n-wilk-io Reference Implementation
The user operates a production deployment using this exact pattern. Key characteristics
proven in production:

- Docker Compose with multiple services (app, Traefik reverse proxy, optional Postgres)
- Traefik routes traffic by Host header internally (multiple services on one server)
- Cloudflare Tunnel for all inbound traffic -- no ports exposed to the internet
- Cloudflare Zero Trust Access controls who can reach each service:
  - Service tokens for machine-to-machine (crawlers calling the API)
  - WARP + email login for humans (coaching staff)
  - Public bypass for URLs that should be open (e.g., a specific scouting report)
- `.env` files for all credentials (git-ignored, never committed)
- Same `docker-compose.yml` for local dev and production
- Automated backups, health checks on every service
- Lean privilege: separate database users per service where applicable

Deployment procedure: clone repo, run `./setup.sh`, edit `.env`, run `docker compose up -d`.
No platform vendor lock-in. Works on any Linux server with Docker (Hetzner, DigitalOcean,
VPS, bare metal).

**Why this matters**: Option B is not speculative. It is a proven architecture the user
already understands and operates. If research confirms it fits baseball-crawl, the implementation
risk is low.

### What This Epic Does NOT Do
This epic evaluates and decides the serving-layer stack, then builds the local environment.
It does NOT rewrite the existing crawling code (E-001 through E-006 remain valid). The
crawling pipeline is Python and stays Python. Only the serving layer (API, database,
dashboard) and deployment target change.

### Relationship to E-004 (Coaching Dashboard)
E-004 is currently DRAFT with no stories, blocked on E-002 and E-003. This epic runs
concurrently with E-002 and E-003 on the infrastructure side. When E-009 is complete,
E-004 will be re-scoped to target the chosen stack.

### Relationship to IDEA-001
IDEA-001 (Local Cloudflare Dev Container) is superseded by this epic. Once E-009-01 is
complete, IDEA-001 should be marked DISCARDED with a reference to E-009.

## Goals

- A technology decision is recorded and rationale documented: Option A (Native Cloudflare)
  or Option B (Docker + Cloudflare Access), with the reasoning for the choice.
- The chosen stack runs locally with a single command (`docker compose up` for Option B,
  `wrangler dev` for Option A).
- The development database can be seeded with test data and reset cleanly.
- An agent running in the development environment can browse the dashboard at a localhost
  URL using `WebFetch` or an equivalent mechanism.
- The production deployment mirrors the local environment as closely as possible. For
  Option B: same `docker-compose.yml`, environment variables only difference. For Option A:
  `wrangler dev` locally, `wrangler deploy` to production.
- CLAUDE.md is updated to document the new stack conventions, local dev commands, and
  production deployment instructions.

## Non-Goals

- Migrating E-001 through E-006 implementations (crawlers, PII protection, HTTP discipline)
  to a new language or runtime. Python stays. Only the serving layer changes.
- High availability, load balancing, or horizontal scaling. This is a single-instance app.
- Authentication on the dashboard beyond Cloudflare Access (whichever option is chosen,
  CF Access handles auth; no application-layer login screens).
- CI/CD pipelines or automated deployment (out of scope; manual deploy is fine for now).
- Real-time data updates or websockets.
- Building any actual dashboard views (that is E-004's job once the stack is decided).
- Multi-region or CDN optimization beyond what Cloudflare provides by default.
- Hosting on AWS, Azure, Fly.io, Render, or Railway. The only hosting options are:
  Native Cloudflare (Option A) or a Linux VPS with Docker + Cloudflare Tunnel (Option B).

## Success Criteria

1. E-009-01 (Technology Decision Record) is complete and selects either Option A or Option B
   with documented rationale.
2. The chosen stack runs locally in under 60 seconds from a clean checkout.
3. A test verifies that an agent can fetch the dashboard URL and receive a valid HTML
   response with at least a page title and one data element rendered.
4. The production deployment process is documented in a runbook (one markdown file) and
   verified against a real host.
5. CLAUDE.md reflects the new stack with accurate commands for local dev, test, and deploy.
6. E-004 Technical Notes are updated to reference the chosen technology choices.

## Stories

| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-009-R-01 | Research: Database Options for Each Deployment Path | DONE | None | - |
| E-009-R-02 | Research: API Layer Options for Each Deployment Path | DONE | None | - |
| E-009-R-03 | Research: Dashboard Framework and Agent Browsability | DONE | None | - |
| E-009-R-04 | Research: Option A vs Option B -- Infrastructure Comparison | DONE | None | - |
| E-009-01   | Technology Decision Record -- choose Option A or Option B | DONE | R-01, R-02, R-03, R-04 | PM |
| E-009-02   | Docker Compose environment -- database + API (Option B) | DONE | E-009-01 | data-engineer |
| E-009-03   | Docker Compose environment -- dashboard (Option B) | TODO | E-009-02 | general-dev |
| E-009-04   | Cloudflare Tunnel + Zero Trust Access configuration (Option B) | TODO | E-009-02; conflicts with E-009-05 (no parallel) | general-dev |
| E-009-05   | Database seeding and reset workflow | TODO | E-009-02; conflicts with E-009-04 (no parallel) | data-engineer |
| E-009-06   | Agent browsability verification | TODO | E-009-03 | general-dev |
| E-009-07   | Production deployment runbook | TODO | E-009-02, E-009-03, E-009-04, E-009-05 | general-dev |
| E-009-08   | CLAUDE.md and E-004 update | TODO | E-009-07 (run last; all prior stories must be DONE) | PM |
| E-009-R-05 | Research: MCP Ecosystem as Agent Integration Layer | DONE | None | - |
| E-009-R-06 | Research: Git and GitHub Integration: gh CLI vs. MCP | DONE | None | - |
| E-009-R-07 | Research: apitap and Alternatives (Tool Category Investigation) | DONE | None | - |

## Technical Notes

### The Two Paths

#### Option A -- Native Cloudflare
```
Local dev:   wrangler dev (simulates Workers + D1 locally via Miniflare)
Production:  wrangler deploy -> Cloudflare Workers + D1 + Pages
Access:      Cloudflare Access (same for both options)
Database:    Cloudflare D1 (SQLite syntax, edge-distributed)
API:         Cloudflare Workers (TypeScript/JavaScript)
Dashboard:   Cloudflare Pages (static or server-rendered via Workers)
```

Pros:
- No server to manage. Cloudflare handles infrastructure entirely.
- Existing D1 migrations and schema (E-003) transfer directly.
- Global edge performance (irrelevant for 5 users, but free).
- Zero server cost (Workers free tier is generous).

Cons:
- Local dev uses Miniflare, which lags behind production behavior.
- Proprietary runtime (TypeScript for Workers, not Python).
- Tight deploy loop friction for dashboard iteration.
- Switching to a different language/runtime for the serving layer (Python crawlers stay,
  but the API would be TypeScript unless a Python Workers runtime is used).

#### Option B -- Docker + Cloudflare Access (n8n-wilk-io Pattern)
```
Local dev:   docker compose up (same stack as production)
Production:  docker compose up on a Linux VPS (Hetzner, DigitalOcean, etc.)
Access:      Cloudflare Tunnel (cloudflared) + Zero Trust Access
Database:    SQLite in a Docker volume (or Postgres if justified by research)
API:         FastAPI (Python) -- same language as crawlers
Dashboard:   FastAPI + Jinja2 templates (server-rendered HTML)
Proxy:       Traefik (internal reverse proxy, routes by Host header)
```

Pros:
- Zero local/prod gap. Same `docker-compose.yml` everywhere. Environment variables only.
- Python end to end. No language context switch between crawlers and API.
- No proprietary runtimes. Standard Docker containers.
- Cloudflare Tunnel means no exposed ports, no firewall rules, no SSL cert management.
- Cloudflare Access provides robust auth (WARP, service tokens, public bypass) without
  any application-layer login code.
- Proven pattern: the user already runs this in production (n8n-wilk-io).
- Works on any Linux server with Docker. No vendor lock-in for compute.

Cons:
- Requires a VPS ($4-10/month, Hetzner or DigitalOcean).
- Requires managing one Linux server (updates, backups, health monitoring).
- More initial setup than Option A (Traefik config, Cloudflare Tunnel setup, .env wiring).

### Constraints (Non-Negotiable for Both Options)
- No AWS. No Azure. No Fly.io. No Render. No Railway.
- Cloudflare is involved regardless of option (DNS, Access/Zero Trust, Tunnel for Option B,
  full stack for Option A).
- Python for crawling stays. Option B keeps Python for the serving layer too.
- Agents must be able to browse rendered HTML -- a real HTTP server at a localhost URL.
- Simple first. 4 teams, ~15 players each, ~30 games/season. Not building for scale.
- Dev/prod parity is non-negotiable. Whichever option is chosen, local and prod must
  behave identically except for environment variables.

### Scale Reality Check
To calibrate all technology decisions:
- 4 teams, ~15 players per team = ~60 player records total
- ~30 games per team per season = ~120 game records per season
- ~3 seasons of history = ~360 game records, ~1,800 player-season stat rows
- Total database size comfortably under 10 MB. SQLite handles this trivially.
- Read-mostly workload. Coaches look; they do not write.
- 1-5 concurrent users at peak (coaching staff across all teams).

This scale eliminates any argument for a distributed database, a managed cloud database
service, or connection pooling. A single SQLite file handles this workload.

### n8n-wilk-io Reference Patterns (Option B)

These patterns are available for reuse if Option B is selected:

**Traefik routing**: Each service declares its own `traefik.http.routers` labels in
`docker-compose.yml`. Traefik routes by Host header (e.g., `baseball.example.com` ->
dashboard service, `api.baseball.example.com` -> API service). No exposed ports except
Traefik's internal port.

**Health checks**: Every service in `docker-compose.yml` has a `healthcheck` block with
a `test`, `interval`, `timeout`, and `retries`. Dependent services use `condition:
service_healthy`. This ensures startup order and allows monitoring.

**Cloudflare Tunnel**: The `cloudflared` service in Docker Compose creates an outbound-only
tunnel to Cloudflare. No inbound ports. DNS is managed by Cloudflare. The tunnel token
comes from a Cloudflare Zero Trust dashboard and lives in `.env`.

**Zero Trust Access policies** (layered):
- Service-to-service calls: service access tokens in `Authorization: Bearer` header
- Human (coaching staff) access: WARP client required, or email OTP via Cloudflare Access
- Public bypass: specific URL patterns (e.g., a game-day scouting page) can be marked
  public in the Access policy

**Credential management**: All secrets in `.env` (git-ignored). The `docker-compose.yml`
references `${VARIABLE_NAME}` syntax. No secrets ever appear in committed files.

**Backup pattern**: A `backup` service in Docker Compose runs on a schedule, copying the
SQLite database file (or pg_dump for Postgres) to a mounted backup directory. Cloudflare R2
can serve as the off-host backup target via rclone.

### Agent Browsability (Both Options)

The baseball-coach agent needs to browse the dashboard -- see rendered HTML, check layouts,
verify that stats appear correctly. This requires:
1. A real HTTP server running locally
2. A tool available to agents for fetching and rendering HTML

The `WebFetch` tool in Claude Code fetches a URL and processes it with an AI model. This
is sufficient for reviewing dashboard content. The agent fetches the dashboard URL, sees the
rendered HTML, and can evaluate layout, data correctness, and mobile suitability.

For Option B: dashboard runs at `http://localhost:<port>` in Docker Compose. Agent (on the
host machine) fetches it via `WebFetch`.

For Option A: dashboard runs via `wrangler dev` on a localhost port. Agent fetches it via
`WebFetch`. (R-03 must verify this works.)

A headless browser (Playwright) is NOT required for this use case. If visual pixel-level
rendering becomes important (unlikely for a stats dashboard), Playwright can be added later.

### Exploratory Research Spikes (R-05, R-06) -- Awareness Only

R-05 and R-06 are **exploratory** spikes added after the primary stack decision was made.
They do not affect the chosen stack (Option B -- Docker + Cloudflare Access). They
investigate whether specific tools in adjacent problem spaces would benefit the agent
infrastructure, and report findings without making recommendations or commitments.

**What they cover:**

- **R-05 (MCP Ecosystem)**: Evaluates four specific MCP servers -- docker/mcp,
  ChromeDevTools/chrome-devtools-mcp, CodeGraphContext/CodeGraphContext, and
  GlitterKill/sdl-mcp -- as potential integration-layer tools for Claude Code agents.
  Each server is assessed for fit against the simpler alternative (CLI + bash). No MCP
  adoption is assumed or authorized by this spike.

- **R-06 (Git + GitHub Integration)**: Evaluates `gh` CLI vs. abhigyanpatwari/GitNexus
  (MCP server for git) as approaches for agents to access git history and repository
  metadata. Relevant because agents currently have no structured way to query commit
  history; relevant to future work once the project has a GitHub remote.

**Execution notes:**
- Both spikes are fully independent. They can run in parallel or in any order.
- Both spikes are also independent of E-009-02 through E-009-08. They do not block and
  are not blocked by any implementation story.
- Output is a research report file per spike (see each spike's Deliverable section).
- If either spike concludes that a tool is worth adopting, the PM creates a follow-on
  story or epic. The spike itself is never a commitment.

### Agent Topology Notes (from claude-architect consultation)

**Do we need a frontend/UX designer agent?**

Recommendation: No, not at this stage. The dashboard is a simple data-display application:
tables, stat cards, mobile layout. The baseball-coach agent fills the UX feedback role.
A general-dev agent following Jinja2 templates + a minimal CSS approach can produce an
adequate coaching dashboard.

When to create a frontend-designer agent:
- The dashboard requires custom data visualizations (charts, heat maps, spray charts)
- The user specifically says visual design quality is unsatisfactory
- The general-dev agent consistently produces dashboards the baseball-coach agent finds hard to use

Until any of these triggers fire, general-dev handles frontend, and baseball-coach handles
UX feedback via the browsability mechanism.

### File Conventions (Option B -- Expected Shape)

```
docker-compose.yml          # Local dev AND production orchestration
.env.example                # Template for required environment variables (committed)
.env                        # Actual credentials (git-ignored)
traefik/
  traefik.yml               # Traefik static config
  dynamic/                  # Traefik dynamic config (optional)
Dockerfile                  # App container (FastAPI + Jinja2)
src/
  api/                      # FastAPI application
    main.py
    routes/
    templates/              # Jinja2 templates
  gamechanger/              # Existing crawlers (unchanged)
  safety/                   # Existing PII module (unchanged)
data/
  dev.db                    # SQLite database (local, gitignored)
  seeds/                    # Seed SQL files (versioned)
    seed_dev.sql
migrations/                 # SQL schema migrations (versioned)
```

### File Conventions (Option A -- Expected Shape)

```
wrangler.toml               # Cloudflare Workers + Pages config
src/
  worker/                   # TypeScript/JS for Cloudflare Workers API
  pages/                    # Static assets for Cloudflare Pages dashboard
  gamechanger/              # Existing Python crawlers (unchanged)
  safety/                   # Existing PII module (unchanged)
migrations/                 # D1 SQL schema migrations (existing)
```

## Open Questions

*All original questions have been resolved. Retained for historical reference.*

1. ~~**Option A local dev story**~~: RESOLVED. Option B selected; this question is moot.

2. ~~**Option B server cost**~~: RESOLVED. Hetzner CX11 (2 vCPU, 2GB RAM, ~3.49-4.15 EUR/month)
   confirmed in E-009-01 decision record. Documented in E-009-07 runbook.

3. ~~**Cloudflare Tunnel authentication for crawlers**~~: RESOLVED. Service token pattern
   documented in E-009-04 (CF-Access-Client-Id / CF-Access-Client-Secret headers).

4. ~~**SQLite in Docker volume vs. mounted host file**~~: RESOLVED in E-009-02. Host-mounted
   file at `./data/app.db`. Implemented and working.

5. ~~**Migration tooling**~~: RESOLVED in E-009-02. Numbered SQL files + `apply_migrations.py`.
   No Alembic. Implemented and working.

6. ~~**Does IDEA-001 need formal closure?**~~: RESOLVED. IDEA-001 marked DISCARDED when
   E-009-01 completed.

7. ~~**TypeScript surface for Option A**~~: RESOLVED. Option B selected (Python end-to-end);
   this question is moot.

### New Questions (from refinement review, 2026-03-02)

8. **`restart: unless-stopped` missing from E-009-02**: The current docker-compose.yml does
   not set `restart: unless-stopped` on the `app` or `traefik` services. E-009-04 should
   add this when modifying the compose file. If missed, E-009-07 must catch it.

9. **Parallel dispatch constraint**: E-009-04 and E-009-05 both modify `docker-compose.yml`
   and `.env.example`. They MUST be dispatched sequentially, not in parallel. Both story
   files now document this constraint.

## History
- 2026-02-28: Created as DRAFT. Expert consultation synthesized by PM. Research spikes
  to be created next. No stories written until E-009-01 (tech decision record) is complete.
- 2026-02-28: Refined to reflect two explicit deployment options (Option A: Native Cloudflare;
  Option B: Docker + Cloudflare Access via n8n-wilk-io pattern). R-04 re-scoped from
  "hosting platforms" to "Option A vs Option B infrastructure comparison." Fly.io, Render,
  and Railway removed as candidates (user constraint: Cloudflare or Docker+CF only).
  PM priors updated: Option B is now the stronger prior given proven production reference.
- 2026-02-28: E-009-01 DONE. Decision recorded at /.project/decisions/E-009-decision.md.
  Option B (Docker + Cloudflare Access) selected unanimously by all four research spikes.
  Epic status moved from DRAFT to ACTIVE. Stories E-009-02 through E-009-08 are now
  unblocked and ready for dispatch.
- 2026-02-28: Story files E-009-02 through E-009-08 written. Research spike statuses
  updated from IN_PROGRESS to DONE. Epic board cleanup complete. All stories are TODO
  and ready for dispatch per the dependency order in the Stories table.
- 2026-03-01: Added exploratory research spikes E-009-R-05 (MCP Ecosystem) and
  E-009-R-06 (Git + GitHub Integration: gh CLI vs. MCP). Awareness and fit-assessment
  only -- no architectural commitments. Both spikes are independent of implementation
  stories E-009-02 through E-009-08 and of each other. Technical Notes updated with
  R-05/R-06 scope summary.
- 2026-03-01: Added exploratory research spike E-009-R-07 (apitap and Alternatives).
  Researcher investigates apitap from scratch -- no prior on category or fit. Spike
  identifies the tool category, surveys alternatives, and assesses fit for baseball-crawl.
  Awareness only -- no commitment. Independent of all other stories and spikes.
- 2026-03-02: **Refinement pass** on stories E-009-02 through E-009-08. PM reviewed all
  story files against the E-009-02 implementation (DONE). Key changes:
  - E-009-02 status corrected from IN_PROGRESS to DONE in epic table.
  - E-009-03: Removed redundant WebFetch AC (moved to E-009-06). Fixed route prefix
    inconsistency (no prefix, not /dashboard prefix). Updated Notes with current seed data state.
  - E-009-04: Added E-009-02 as explicit blocker. Added file conflict warning with E-009-05.
    Clarified AC-6/AC-7 require real Cloudflare account. Added restart: unless-stopped note.
  - E-009-05: Fixed dev.db/app.db ambiguity (use DATABASE_PATH env var). Added Docker Compose
    profile for Litestream (skip in local dev). Added file conflict warning with E-009-04.
    Added production safety check (--force flag).
  - E-009-06: Broadened AC-1 to allow Bash curl fallback. Added curl as primary fallback
    before mcp__ide__executeCode. Clarified baseball-coach invocation pattern.
  - E-009-07: Added Litestream profile to startup command. Added restart policy verification.
    Added user dependency note (VPS must be provisioned by operator).
  - E-009-08: Fixed dependency (E-009-07, not E-009-01). Fixed hardcoded date in AC-6.
    Added Litestream profile command to CLAUDE.md Commands spec.
  - Open Questions: Closed all 7 original questions as RESOLVED. Added 2 new questions
    (restart policy gap, parallel dispatch constraint).
