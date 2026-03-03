# Product Manager -- Agent Memory

## Numbering State
- Next available epic number: E-033
- Epics created: E-001 through E-032 (E-006, E-007, E-008, E-011, E-012, E-013, E-014, E-015, E-016, E-017, E-018, E-019, E-020, E-021, E-022, E-024, E-025, E-026, E-027, E-029, E-030, E-031 archived)
- Next available idea number: IDEA-005
- Ideas created: IDEA-001 through IDEA-004

## Project Context
- Project: baseball-crawl -- GameChanger API -> database -> coaching dashboard
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite.
- Architecture: src/gamechanger/ for source, src/api/ for FastAPI app, tests/ for tests, data/raw/ for crawl output, migrations/ for SQL
- Credentials: short-lived, user provides curl commands, scripts/refresh_credentials.py handles extraction
- See CLAUDE.md for full project conventions

## Active Epics (Summary)
- E-001 (ACTIVE): GameChanger API Foundation -- E-001-01 DONE, E-001-03 DONE, E-001-02 TODO, E-001-04 TODO (blocked on E-001-02).
- E-002 (ACTIVE): Data Ingestion Pipeline -- 8 stories all TODO. Crawl stories blocked on E-001-02+E-001-03 (E-001-03 now DONE). Load stories blocked on E-003-01.
- E-003 (ACTIVE): Data Model and Storage Schema -- E-003-01 TODO, E-003-02 TODO (blocked on 01), E-003-03 ABANDONED, E-003-04 TODO (blocked on 02+E-009-02).
- E-004 (DRAFT): Coaching Dashboard -- no stories yet, blocked on E-002 + E-003. Still references old Cloudflare stack (E-009-08 will fix).
- E-005 (ACTIVE): HTTP Request Discipline -- 4/5 DONE. E-005-03 TODO (blocked on E-001-02).
- E-009 (ACTIVE): Tech Stack Redesign -- 02/03/04/05/06 DONE. 07 TODO (production runbook), 08 TODO (CLAUDE.md update, blocked on 07). All research spikes DONE.
- E-010 (ACTIVE): Intent/Context Layer -- Phase 1 DONE (01/02/03). Phase 2 BLOCKED on E-002+E-003.
- E-023 (READY): Auth and Team-Level Permissions -- 5 stories. 01 TODO (schema), 02 TODO (magic link login, blocked on 01), 03 TODO (passkeys, blocked on 02), 04 TODO (dashboard scoping, blocked on 02), 05 TODO (admin, blocked on 02+04). 03 and 04 can run parallel. ALL users auth = magic link + passkey + SQLite sessions (unified). Admin routes = session + is_admin guard (app) + Cloudflare Access policy on /admin (network). No CF JWT header parsing in app. Mailgun for email (stdout in dev).
- E-028 (READY): Documentation System -- 5 stories. 01 TODO (agent def), 02 TODO (rules), 03 TODO (admin docs, blocked on 01), 04 TODO (coaching docs, blocked on 01), 05 TODO (CLAUDE.md+workflow updates, blocked on 01+02). 01+02 parallel; then 03+04+05 parallel. Revised per E-030 to remove all orchestrator references.
- E-032 (READY): Agent Log Access and Troubleshooting Verification -- 2 stories. 01 TODO (verify log access + health check), 02 TODO (verify error diagnosis from logs, blocked on 01). Validation epic proving E-027 troubleshooting workflow works end-to-end.
## Archived Epics
- E-006 (ABANDONED): PII Protection -- demoted to IDEA-004. Revisit when E-002 produces real data.
- E-007 (COMPLETED): Orchestrator Workflow Discipline -- refined PM modes, READY gate, Decision Gates
- E-008 (COMPLETED): Intent/Context Layer Design -- APPROVED Option 5 (Hybrid), follow-on = E-010
- E-011 (ABANDONED): PM Workflow Discipline -- fully absorbed by E-016.
- E-012 (ABANDONED): Filesystem-Context Skill Integration -- absorbed into E-013
- E-013 (COMPLETED): Agent Buildout -- all agent definitions completed to production quality.
- E-014 (ABANDONED): Multi-Agent Patterns Skill Integration -- absorbed into E-013
- E-015 (COMPLETED): Fix Agent Dispatch -- established dispatch-pattern.md.
- E-016 (COMPLETED): Evolve PM to Product Manager
- E-017 (COMPLETED): Terminology Cleanup -- replaced stale "Project Manager" prose.
- E-018 (COMPLETED): Agent Frontmatter Refinement -- follow-on = E-020.
- E-019 (COMPLETED): Pre-Commit Safety Gates -- two-layer pre-commit defense.
- E-020 (COMPLETED): Agent Effectiveness Audit & Refinement -- all 5 target agents refined.
- E-021 (COMPLETED): Agent Workflow Guardrails -- work authorization and dispatch failure protocols.
- E-022 (COMPLETED): Safety Scan Hardening -- visible confirmation, hook hardening, CLAUDE.md reminder, integration tests.
- E-024 (COMPLETED): Epic Archive Enforcement -- hook + PM protocol fix to prevent completed epics lingering in /epics/.
- E-025 (COMPLETED): Devcontainer Update -- Python 3.12 + Docker-in-Docker alongside Node.js.
- E-026 (COMPLETED): Python Version Governance -- migrated 3.12->3.13, .python-version as source of truth, pyproject.toml.
- E-027 (COMPLETED): Devcontainer-to-Compose Networking -- port 8001 mapping for app access from devcontainer, troubleshooting docs in CLAUDE.md.
- E-029 (COMPLETED): Context-Layer Routing Enforcement -- explicit context-layer file paths in dispatch-pattern.md routing table + PM dispatch pre-check step. Closes recurring mis-routing pattern from E-019/E-027.
- E-030 (COMPLETED): Remove Orchestrator Agent -- deleted orchestrator.md, updated CLAUDE.md/rules/agent defs/skills/memory to reflect user->PM->implementing agent model. E-028 stories revised. Agent ecosystem now 6 agents.
- E-031 (COMPLETED): Dispatch Closure Sequence -- expanded dispatch closure in dispatch-pattern.md and product-manager.md into a 7-step sequence (validate, update, archive, memory, ideas, summary, commit offer).

## Key Architectural Decisions
- Storage: SQLite (WAL mode). Host-mounted at ./data/app.db. Simple file backup via scripts/backup_db.py (no Litestream).
- Serving layer: FastAPI + Jinja2 (Python). Single monolithic app. No TypeScript.
- Deployment: Docker Compose (local + prod). Home Linux server (no VPS, no hosting cost). Cloudflare Tunnel + Zero Trust.
- Migrations: numbered SQL scripts (migrations/001_*.sql). No Alembic. apply_migrations.py at startup.
- HTTP layer: src/http/headers.py + src/http/session.py. Chrome 131/macOS fingerprint.
- ip_outs: innings pitched stored as integer outs (1 IP = 3 outs)
- Soft referential integrity in stats tables (orphaned player IDs accepted with WARNING)
- Routing model (2026-03-03): Orchestrator removed (E-030). PM is the direct entry point for all work. User talks to PM or direct-routing exceptions. Simplifies architecture, eliminates telephone game relay.
- Auth model (revised 2026-03-03): ALL users (coaches + admins) = magic link email + optional passkey (py_webauthn) + SQLite sessions table. No separate admin login path. Admin routes protected by two layers: (1) Cloudflare Access policy requires WARP to reach /admin/* (network-level, external to app), (2) app session middleware + is_admin flag. App does NOT inspect Cf-Access-Jwt-Assertion or any CF headers. No passwords. Mailgun for email (MAILGUN_API_KEY env var; stdout fallback in dev). Dev bypass via DEV_USER_EMAIL env var. Migration 003_auth.sql (002 reserved for E-003-02 stats schema).

## User Preferences
- Build it right, no rush
- Coaches see dashboards; user (operator) runs the system
- Multi-team (4 Lincoln levels), multi-season, player tracking across orgs

## Ideas Backlog
| ID | Title | Status | Review By | Notes |
|----|-------|--------|-----------|-------|
| IDEA-001 | Local Cloudflare Dev Container | DISCARDED | 2026-02-28 | Superseded by E-009 |
| IDEA-002 | Web Scraping Fallback Strategy | CANDIDATE | 2026-05-29 | Promote when API data gap discovered |
| IDEA-003 | Work Management as Agent Interface | CANDIDATE | 2026-05-29 | Promote when file-based system causes friction |
| IDEA-004 | Hard Data Boundaries and PII Protection | PROMOTED | 2026-03-02 | Promoted to E-019. Consolidated 6 stories to 4, added credential scanning. |

## Key Workflow Contract
- Routing model: user -> PM -> implementing agent (no orchestrator; removed in E-030)
- PM modes: Refinement (form epics) / Decision Gates (evaluation synthesis) / Dispatch (execute stories)
- Epic lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED)
- READY gate: must be READY/ACTIVE before dispatch. PM sets READY explicitly.
- Dispatch: PM uses Agent Teams (TeamCreate + Agent tool). See /.claude/rules/dispatch-pattern.md.
- Direct-routing exceptions (no PM needed): api-scout, baseball-coach, claude-architect
- Implementing agents needing work auth: general-dev, data-engineer, docs-writer
- Agent ecosystem: 6 agents (claude-architect, product-manager, baseball-coach, api-scout, data-engineer, general-dev)
- Before assigning epic numbers: ALWAYS ls /epics/ to avoid numbering collisions

## Detailed Notes (Separate Files)
- `lessons-learned.md` -- Epic authoring patterns, dependency patterns, process patterns, platform constraints
- `mcp-research.md` -- MCP server evaluation findings (E-009-R-05, R-06)
