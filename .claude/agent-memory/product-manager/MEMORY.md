# Product Manager -- Agent Memory

## Numbering State
- Next available epic number: E-036
- Epics created: E-001 through E-035 (E-001, E-006, E-007, E-008, E-010, E-011, E-012, E-013, E-014, E-015, E-016, E-017, E-018, E-019, E-020, E-021, E-022, E-024, E-025, E-026, E-027, E-028, E-029, E-030, E-031, E-032, E-033, E-034, E-035 archived)
- Next available idea number: IDEA-007
- Ideas created: IDEA-001 through IDEA-006

## Project Context
- Project: baseball-crawl -- GameChanger API -> database -> coaching dashboard
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite.
- Architecture: src/ for source (gamechanger/, api/, http/, safety/), tests/ for tests, data/ for local dev outputs, migrations/ for SQL
- Credentials: short-lived, user provides curl commands, scripts/refresh_credentials.py handles extraction
- See CLAUDE.md for full project conventions

## Active Epics (Summary)
- E-002 (ACTIVE): Data Ingestion Pipeline -- 8 stories all TODO. Crawl stories blocked on E-001-02+E-001-03 (both now DONE via E-001 completion). Load stories blocked on E-003-01.
- E-003 (READY): Data Model and Storage Schema -- REFINED 2026-03-03. E-003-01 TODO (rewrite 001_initial_schema.sql: seasons, crawl config, pitching, expanded splits), E-003-02 TODO (coaching_assignments migration 004, blocked on E-003-01 + E-023-01), E-003-03 ABANDONED, E-003-04 TODO (seed data + query tests, blocked on E-003-01). E-003-01 has NO blockers. E-003-01 and E-003-04 can run sequentially without E-023. E-003-02 cross-epic dep on E-023-01.
- E-004 (DRAFT): Coaching Dashboard -- no stories yet, blocked on E-002 + E-003. Still references old Cloudflare stack (E-009-08 will fix).
- E-005 (ACTIVE): HTTP Request Discipline -- 4/5 DONE. E-005-03 TODO (blocker E-001-02 now DONE -- ready for dispatch).
- E-009 (ACTIVE): Tech Stack Redesign -- 02/03/04/05/06 DONE. 07 TODO (production runbook), 08 TODO (CLAUDE.md update, blocked on 07). All research spikes DONE.
- E-023 (READY): Auth and Team-Level Permissions -- 5 stories. 01 TODO (schema), 02 TODO (magic link login, blocked on 01), 03 TODO (passkeys, blocked on 02), 04 TODO (dashboard scoping, blocked on 02), 05 TODO (admin, blocked on 02+04). 03 and 04 can run parallel. ALL users auth = magic link + passkey + SQLite sessions (unified). Admin routes = session + is_admin guard (app) + Cloudflare Access policy on /admin (network). No CF JWT header parsing in app. Mailgun for email (stdout in dev).
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
- E-010 (ABANDONED): Intent/Context Layer -- Phase 1 DONE (3 skill files delivered and in use). Phase 2 abandoned: blockers (E-002+E-003) distant, epic text stale (orchestrator refs from pre-E-030). Phase 2 concept captured as IDEA-005.
- E-028 (COMPLETED): Documentation System -- docs-writer agent, documentation maintenance rules, admin docs (architecture, getting-started, operations, agent-guide), coaching docs (stats glossary, scouting reports), workflow integration (dispatch-pattern.md, workflow-discipline.md, PM agent def).
- E-032 (COMPLETED): Agent Log Access and Troubleshooting Verification -- validated E-027 troubleshooting workflow end-to-end. No blocking gaps. Recommendation: add grep-based log filtering to CLAUDE.md troubleshooting section.
- E-033 (COMPLETED): Project Hygiene -- aligned docs and tests with current reality. CLAUDE.md stack sections corrected, hardcoded paths fixed in 16 context-layer + story files, TestClient lifecycle fixed, pytest-timeout added, migration comment corrected.
- E-034 (COMPLETED): Codex Review Integration -- two review lanes (code + spec). Artifacts: `.project/codex-review.md`, `scripts/codex-review.sh`, `.project/codex-spec-review.md`, `scripts/codex-spec-review.sh`. CLAUDE.md Commands section updated. PM agent def updated with optional spec-review step. No follow-up work identified.
- E-001 (COMPLETED): GameChanger API Foundation -- credential parser, API client, endpoint docs, smoke test. All 4 stories DONE. Archived 2026-03-03.
- E-035 (COMPLETED): Context Layer Staleness Fixes -- fixed P1 (misleading agent count, stale deployment details, wrong budget numbers), P2 (stale references in hooks/skills/rules), P3 (memory file duplication). 10 context-layer files updated. No follow-up work.

## Key Architectural Decisions
- Storage: SQLite (WAL mode). Host-mounted at ./data/app.db. Simple file backup via scripts/backup_db.py (no Litestream).
- Serving layer: FastAPI + Jinja2 (Python). Single monolithic app. No TypeScript.
- Deployment: Docker Compose (local + prod). Home Linux server (no VPS, no hosting cost). Cloudflare Tunnel + Zero Trust.
- Migrations: numbered SQL scripts (migrations/001_*.sql). No Alembic. apply_migrations.py at startup.
- HTTP layer: src/http/headers.py + src/http/session.py. Chrome 131/macOS fingerprint.
- ip_outs: innings pitched stored as integer outs (1 IP = 3 outs)
- Soft referential integrity in stats tables (orphaned player IDs accepted with WARNING)
- Data model (revised 2026-03-03): seasons = first-class entity (season_id TEXT PK, type-based filtering). teams have crawl config (source, is_active, last_synced). All season references are FKs to seasons table. player_season_pitching added. Expanded splits on batting (hr, bb, so per split group). coaching_assignments = domain table (not auth), FKs to users+teams+seasons. Migration numbering: 001=data model, 003=auth, 004=coaching_assignments. Slot 002 unused.
- Routing model (2026-03-03): Orchestrator removed (E-030). PM is the direct entry point for all work. User talks to PM or direct-routing exceptions. Simplifies architecture, eliminates telephone game relay.
- Auth model (revised 2026-03-03): ALL users (coaches + admins) = magic link email + optional passkey (py_webauthn) + SQLite sessions table. No separate admin login path. Admin routes protected by two layers: (1) Cloudflare Access policy requires WARP to reach /admin/* (network-level, external to app), (2) app session middleware + is_admin flag. App does NOT inspect Cf-Access-Jwt-Assertion or any CF headers. No passwords. Mailgun for email (MAILGUN_API_KEY env var; stdout fallback in dev). Dev bypass via DEV_USER_EMAIL env var. Migration 003_auth.sql.

## User Preferences
- Build it right, no rush
- Coaches see dashboards; user (operator) runs the system
- Multi-team (4 Lincoln levels), multi-season, player tracking across orgs
- CLAUDE.md and shipped code comments describe current implemented reality, NOT future planned state
- Epics/stories describe future work until that work is done
- Archived files are frozen historical records -- do not modify

## Ideas Backlog
| ID | Title | Status | Review By | Notes |
|----|-------|--------|-----------|-------|
| IDEA-001 | Local Cloudflare Dev Container | DISCARDED | 2026-02-28 | Superseded by E-009 |
| IDEA-002 | Web Scraping Fallback Strategy | CANDIDATE | 2026-05-29 | Promote when API data gap discovered |
| IDEA-003 | Work Management as Agent Interface | CANDIDATE | 2026-05-29 | Promote when file-based system causes friction |
| IDEA-004 | Hard Data Boundaries and PII Protection | PROMOTED | 2026-03-02 | Promoted to E-019. Consolidated 6 stories to 4, added credential scanning. |
| IDEA-005 | Directory-Scoped Intent Nodes at src/ Module Boundaries | CANDIDATE | 2026-06-01 | Phase 2 of abandoned E-010. Promote when E-002+E-003 complete. |
| IDEA-006 | Epic Lanes Convention for Multi-Workstream Epics | CANDIDATE | 2026-06-01 | Formalize lane-style Technical Notes headers. Promote when 6+ story epics are common AND agents report TN scoping confusion. |

## Key Workflow Contract
- Routing model: user -> PM -> implementing agent (no orchestrator; removed in E-030)
- PM modes: Refinement (form epics) / Decision Gates (evaluation synthesis) / Dispatch (execute stories)
- Epic lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED)
- READY gate: must be READY/ACTIVE before dispatch. PM sets READY explicitly.
- Dispatch: PM uses Agent Teams (TeamCreate + Agent tool). See /.claude/rules/dispatch-pattern.md.
- Direct-routing exceptions (no PM needed): api-scout, baseball-coach, claude-architect
- Implementing agents needing work auth: general-dev, data-engineer, docs-writer
- Agent ecosystem: 7 agents (claude-architect, product-manager, baseball-coach, api-scout, data-engineer, general-dev, docs-writer)
- Before assigning epic numbers: ALWAYS ls /epics/ to avoid numbering collisions

## Detailed Notes (Separate Files)
- `lessons-learned.md` -- Epic authoring patterns, dependency patterns, process patterns, platform constraints
- `mcp-research.md` -- MCP server evaluation findings (E-009-R-05, R-06)
