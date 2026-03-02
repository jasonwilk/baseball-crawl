# E-009 Technology Decision Record: Serving Layer Stack

**Decision Date**: 2026-02-28
**Decision Owner**: Product Manager (E-009-01)
**Status**: FINAL
**Epic**: [E-009: Tech Stack Redesign](../../epics/E-009-tech-stack-redesign/epic.md)

---

## The Decision

**We choose Option B: Docker + Cloudflare Access (the n8n-wilk-io pattern).**

This decision is made with high confidence. All four research spikes reached the same conclusion. The recommendation is not a close call.

---

## The Chosen Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Database** | SQLite in a Docker volume | WAL mode enabled; Litestream for production backup |
| **API / Dashboard** | FastAPI (Python) + Jinja2 templates | Single monolithic app; server-rendered HTML |
| **CSS** | Tailwind CDN | No build step for MVP; switch to Tailwind CLI if production performance requires it |
| **Proxy** | Traefik | Internal reverse proxy; routes by Host header; no exposed ports |
| **Tunnel / Auth** | Cloudflare Tunnel (cloudflared) + Zero Trust Access | Handles all inbound traffic and authentication |
| **Local Dev** | `docker compose up` | Identical to production; env vars are the only difference |
| **Production Hosting** | Linux VPS (Hetzner CX11 or equivalent) | ~$4-6/month; Docker installed; no managed services |
| **Language** | Python end-to-end | Crawlers (E-001--E-006), API, migrations, and tests all in Python |

---

## Summary of Research Findings

Four independent research spikes evaluated Option A (Native Cloudflare: Workers + D1 + Pages) against Option B (Docker + Cloudflare Access). All four recommended Option B. The findings are summarized below.

### R-01: Database Options

Both options use SQLite. For Option A that means Cloudflare D1 (managed, proprietary). For Option B that means SQLite in a Docker volume with WAL mode. At baseball-crawl's scale (~10 MB, 1-5 concurrent users, read-mostly) both databases are technically equivalent. D1's fidelity in local development is good as of 2026. SQLite in Docker is simpler to operate, backup, and inspect. No capability gap in either direction.

**R-01 leans Option B**: SQLite in Docker is simpler to operate and avoids proprietary bindings.

### R-02: API Layer Options

Option A requires TypeScript (Python Workers remain in beta as of February 2026). Option B uses FastAPI, keeping the entire stack in Python. The TypeScript learning curve for a Python-first developer is 2-4 weeks ramp-up plus ongoing context-switching cost every time serving-layer code is touched. FastAPI's async + SQLite pattern (`run_in_threadpool`) is straightforward and well-documented.

**R-02 leans Option B**: Python homogeneity eliminates learning cost and ongoing friction.

### R-03: Dashboard Framework and Agent Browsability

Both options can deliver server-rendered HTML browsable by the baseball-coach agent via WebFetch. Option B (FastAPI + Jinja2) makes this native; Jinja2 templates render on the server and the agent sees populated data. Option A requires explicit server-rendering via Eta or Nunjucks in TypeScript, which is possible but adds a dependency and a context switch.

**R-03 leans Option B**: Jinja2 server-rendering is native to Python; agent browsability is excellent.

### R-04: Infrastructure Comparison

The head-to-head comparison quantified the trade-offs across eight dimensions: local dev experience, language consistency, operational burden, team velocity, feature parity, cost, risk, and dev/prod parity. Option B won 13 comparisons; Option A won 4; 9 were ties.

The decisive factor from R-04: the n8n-wilk-io pattern is already running in production. Jason has lived experience operating this exact architecture. That single fact reduces Option B's implementation risk to near-zero. It is not speculative.

**R-04 recommends Option B**: "For Jason solo-operating baseball-crawl with Python expertise and a proven reference implementation, Option B is the stronger choice."

---

## Why Option A Was Rejected

Option A (Native Cloudflare) is a technically sound choice. It is not being rejected for capability reasons. It is rejected because:

1. **Language friction is real and ongoing.** TypeScript for the serving layer means Jason switches mental models every time he works on the API or dashboard. For a solo operator who is also writing Python crawlers, this tax compounds indefinitely.

2. **Python Workers are not production-ready.** As of February 2026, Python Workers require a beta compatibility flag. The one scenario that would make Option A attractive -- Python end-to-end on Cloudflare -- is not available today. If that changes (when Cloudflare removes the beta flag), revisit this decision.

3. **Vendor lock-in is asymmetric.** Option A binds the serving layer to Cloudflare's proprietary APIs (D1 bindings, Workers APIs, Pages Functions). Migrating out later means a full serving-layer rewrite. Option B uses Docker, FastAPI, and SQLite -- all portable, standard technologies. Cloudflare is a peripheral (Tunnel, Access) rather than a dependency.

4. **True cost favors Option B.** Option A's zero infrastructure cost is offset by 4-6 weeks of TypeScript ramp-up time. Option B's VPS cost (~$60-75/year at Hetzner CX11) is trivially smaller than the opportunity cost of learning a new language.

5. **The n8n-wilk-io reference is decisive.** Option A has no equivalent reference implementation that Jason has personally operated. Option B is a pattern he has running in production today. When both options are technically viable, the one with lived operational experience wins.

---

## Why Option B Won

The core reasons are straightforward:

- Python end-to-end. One language for crawlers, API, dashboard, migrations, and tests.
- Zero learning curve for the serving layer. FastAPI + Jinja2 + SQLite are beginner-accessible Python patterns.
- Near-perfect dev/prod parity. The same `docker-compose.yml` runs locally and in production. Environment variables are the only difference.
- Proven reference architecture. The n8n-wilk-io deployment already runs this pattern in production with Cloudflare Tunnel, Zero Trust Access, and Docker Compose on a VPS. Jason can troubleshoot from lived experience, not documentation.
- Low vendor lock-in. Docker and Python are portable. If Cloudflare's pricing changes or service quality declines, the compute layer can be migrated independently.

---

## Decision-Determining Factors

The five questions from R-04 applied:

1. **Learning curve vs. ops overhead**: Learning TypeScript is more costly than managing a single VPS. Option B.
2. **Risk tolerance**: Vendor lock-in (Option A) is a bigger strategic risk than VPS uptime (Option B). Option B.
3. **Future hiring**: Python is a larger talent pool. Option B.
4. **Observability**: SSH access and full log visibility is valuable. Option B.
5. **Long-term flexibility**: The ability to migrate away from Cloudflare matters. Option B.

Score: 5-0 for Option B.

---

## What Stays the Same

This decision affects only the serving layer: the API, the dashboard, the database runtime, and deployment. Everything else stays unchanged:

- E-001 through E-006 (crawlers, HTTP discipline, PII protection) remain valid Python implementations.
- The SQL migration files in `migrations/` are portable. The schema does not change.
- Credentials management via `.env` continues. The `.env` file is git-ignored.
- Python-dotenv for local dev. Docker environment variables for production.

---

## Implementation: What Happens Next

The following stories implement Option B. Story files will be written now that the decision is finalized.

| Story | Title | Assignee | Depends On |
|-------|-------|----------|-----------|
| E-009-02 | Docker Compose environment -- database + API | data-engineer | E-009-01 (this decision) |
| E-009-03 | Docker Compose environment -- dashboard | general-dev | E-009-01 (this decision) |
| E-009-04 | Cloudflare Tunnel + Zero Trust Access configuration | general-dev | E-009-02, E-009-03 |
| E-009-05 | Database seeding and reset workflow | data-engineer | E-009-02 |
| E-009-06 | Agent browsability verification | general-dev | E-009-03 |
| E-009-07 | Production deployment runbook | general-dev | E-009-02, E-009-03 |
| E-009-08 | CLAUDE.md and E-004 update | PM | E-009-01 (this decision) |

### Immediate Open Questions for Implementation Stories

These questions were identified in R-04 and must be resolved during story execution:

- **VPS provider**: Hetzner CX11 (before April 1 price increase at €3.49/month) is the recommended choice. DigitalOcean Droplet ($6/month) is the backup. Either is acceptable.
- **Litestream backup target**: Cloudflare R2 is the preferred target (keeps vendor surface consistent). S3 is the fallback. MinIO is acceptable for local testing only.
- **Traefik routing**: Single-host Docker Compose with Host header routing. Dashboard at `baseball.<domain>`, API at `api.baseball.<domain>` or `baseball.<domain>/api/`.
- **SQLite placement**: Host-mounted file (`./data/app.db` in docker-compose.yml) rather than a named Docker volume. This keeps the database visible on the filesystem for inspection, backup verification, and migration dry-runs.
- **Migration tooling**: Simple numbered SQL scripts (`migrations/001_schema.sql`, etc.) with a lightweight `apply_migrations.py` bootstrap script. No Alembic. This matches the existing E-003 migration pattern.
- **SSL certificates**: Cloudflare Tunnel handles all SSL. No local cert management required.

### E-004 (Coaching Dashboard) Implications

E-004 is currently DRAFT with no stories, blocked pending E-009 completion. Now that the stack decision is made, E-004 can be re-scoped. The E-004 Technical Notes must be updated to specify:

- Dashboard framework: FastAPI + Jinja2
- CSS: Tailwind CDN
- Data layer: SQLite (same database as API)
- Local dev: `docker compose up` at `http://localhost:8000`
- Agent browsability: User provides localhost URL; agent uses WebFetch
- MVP scope: Server-rendered HTML tables and stat cards; no client-side JavaScript required for MVP; HTMX and Alpine.js are optional enhancements

---

## Trigger to Revisit This Decision

This decision stands until one of the following occurs:

1. **Cloudflare removes the beta flag from Python Workers.** At that point, Option A becomes Python end-to-end and the language friction argument disappears. Re-evaluate with a fresh spike.
2. **VPS operational burden becomes untenable.** If Jason consistently spends more than 4 hours/month on VPS maintenance, Option A's zero-ops appeal becomes economically rational.
3. **The project grows beyond single-VPS capacity.** If the database exceeds 1 GB, user count exceeds 50, or multi-region performance becomes a requirement, revisit. (This is unlikely given scope: 4 teams, ~15 players each.)
4. **n8n-wilk-io pattern is retired or changes significantly.** If the reference implementation shifts, re-evaluate compatibility.

---

## Research Artifacts

All research findings that informed this decision are at:

- `/Users/jason/Documents/code/baseball-crawl/.project/research/E-009-R-01-database-options.md`
- `/Users/jason/Documents/code/baseball-crawl/.project/research/E-009-R-02-api-layer-options.md`
- `/Users/jason/Documents/code/baseball-crawl/.project/research/E-009-R-03-dashboard-framework.md`
- `/Users/jason/Documents/code/baseball-crawl/.project/research/E-009-R-04-option-comparison.md`

---

## History

- 2026-02-28: Decision recorded. All four research spikes completed and synthesized. Option B selected unanimously. Epic E-009 moves to ACTIVE.
