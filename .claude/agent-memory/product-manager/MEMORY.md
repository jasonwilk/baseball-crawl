# Product Manager -- Agent Memory

## Numbering State
- Next available epic number: E-021
- Epics created: E-001 through E-020 (E-006, E-007, E-008, E-011, E-012, E-014, E-015, E-016, E-018 archived; E-013 renumbered from collision)
- Next available idea number: IDEA-005
- Ideas created: IDEA-001 through IDEA-004

## Project Context
- Project: baseball-crawl -- GameChanger API -> database -> coaching dashboard
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite.
- Architecture: src/gamechanger/ for source, src/api/ for FastAPI app, tests/ for tests, data/raw/ for crawl output, migrations/ for SQL
- Credentials: short-lived, user provides curl commands, scripts/refresh_credentials.py handles extraction
- See CLAUDE.md for full project conventions

## Active Epics (Summary)
- E-001 (ACTIVE): GameChanger API Foundation -- 4 stories. Start here.
- E-002 (ACTIVE): Data Ingestion Pipeline -- 8 stories, all BLOCKED on E-001-02 + E-001-03. Clarified for SQLite (2026-03-01).
- E-003 (ACTIVE): Data Model and Storage Schema -- 3 active stories (E-003-03 ABANDONED in favor of E-009-02). Clarified for SQLite (2026-03-01).
- E-004 (DRAFT): Coaching Dashboard -- no stories yet, blocked on E-002 + E-003
- E-005 (ACTIVE): HTTP Request Discipline -- 5 stories
- E-009 (ACTIVE): Tech Stack Redesign -- stories 02-08 all TODO, ready for dispatch
- E-010 (ACTIVE): Intent/Context Layer -- Phase 1 DONE, Phase 2 BLOCKED on E-002+E-003
- E-013 (ACTIVE): Agent Buildout -- 6 stories (absorbed E-012+E-014). 01/02/03 can run in parallel. E-013-04 expanded to wire ALL skills into ALL agents. E-013-06 new (PM procedures).
- E-017 (READY): Terminology Cleanup -- 1 story. Replace stale "Project Manager" prose with "Product Manager" in 5 live files.

## Archived Epics
- E-007 (COMPLETED): Orchestrator Workflow Discipline -- refined PM modes, READY gate, Decision Gates
- E-008 (COMPLETED): Intent/Context Layer Design -- APPROVED Option 5 (Hybrid), follow-on = E-010
- E-015 (COMPLETED): Fix Agent Dispatch -- established dispatch-pattern.md. Nesting constraint bypassed by Agent Teams.
- E-011 (ABANDONED): PM Workflow Discipline -- fully absorbed by E-016. All stories ABANDONED or DONE (R-01 only). Audit script never built.
- E-016 (COMPLETED): Evolve PM to Product Manager -- PM rewrite (opus), orchestrator rewrite (sonnet+Read/Glob/Grep), killed Dispatch Manifest, default agent = orchestrator
- E-006 (ABANDONED): PII Protection -- demoted to IDEA-004. Revisit when E-002 produces real data.
- E-012 (ABANDONED): Filesystem-Context Skill Integration -- absorbed into E-013 (stories -> E-013-04, E-013-06)
- E-014 (ABANDONED): Multi-Agent Patterns Skill Integration -- absorbed into E-013 (stories -> E-013-04)
- E-018 (COMPLETED): Agent Frontmatter Refinement -- fixed YAML frontmatter for 4 agents. Follow-on = E-020.
- E-019 (COMPLETED): Pre-Commit Safety Gates -- two-layer pre-commit defense (Git hook + Claude Code PreToolUse hook), stdlib Python PII/credential scanner, ephemeral directory, developer guide. All 4 stories DONE.
- E-020 (COMPLETED): Agent Effectiveness Audit & Refinement -- refined system prompts for all 5 target agents (claude-architect, api-scout, baseball-coach, general-dev, data-engineer). Removed CLAUDE.md duplication, added Anti-Patterns + Error Handling sections, consolidated memory sections, fixed architect's JSON/formatting issues.

## Key Architectural Decisions
- Storage: SQLite in Docker volume (WAL mode + Litestream backup). Host-mounted at ./data/app.db.
- Serving layer: FastAPI + Jinja2 (Python). Single monolithic app. No TypeScript.
- Deployment: Docker Compose (local + prod). Hetzner CX11 VPS. Cloudflare Tunnel + Zero Trust.
- Migrations: numbered SQL scripts (migrations/001_*.sql). No Alembic. apply_migrations.py at startup.
- HTTP layer: src/http/headers.py + src/http/session.py. Chrome 131/macOS fingerprint.
- ip_outs: innings pitched stored as integer outs (1 IP = 3 outs)
- Soft referential integrity in stats tables (orphaned player IDs accepted with WARNING)

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
- PM modes: Refinement (form epics) / Decision Gates (evaluation synthesis) / Dispatch (execute stories)
- Epic lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED)
- READY gate: must be READY/ACTIVE before dispatch. PM sets READY explicitly.
- Dispatch: PM must run in MAIN session. Subagent context -> one-line error (E-016 simplification).
- Direct-routing exceptions (no PM needed): api-scout, baseball-coach, claude-architect
- Implementing agents needing work auth: general-dev, data-engineer ONLY
- Before assigning epic numbers: ALWAYS ls /epics/ to avoid numbering collisions

## Detailed Notes (Separate Files)
- `lessons-learned.md` -- Epic authoring patterns, dependency patterns, process patterns, platform constraints
- `mcp-research.md` -- MCP server evaluation findings (E-009-R-05, R-06)
