# Product Manager -- Agent Memory

## Numbering State
- Next available epic number: E-059
- Epics created: E-001 through E-056 (E-001, E-003, E-005, E-006, E-007, E-008, E-010, E-011, E-012, E-013, E-014, E-015, E-016, E-017, E-018, E-019, E-020, E-021, E-022, E-024, E-025, E-026, E-027, E-028, E-029, E-030, E-031, E-032, E-033, E-034, E-035, E-036, E-037, E-038, E-044, E-046, E-048, E-049, E-050, E-052, E-053, E-054, E-056 archived)
- Next available idea number: IDEA-013
- Ideas created: IDEA-001 through IDEA-012

## Project Context
- Project: baseball-crawl -- GameChanger API -> database -> coaching dashboard
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite.
- Architecture: src/ for source (gamechanger/, api/, http/, safety/), tests/ for tests, data/ for local dev outputs, migrations/ for SQL
- Credentials: short-lived, profile-scoped (_WEB/_MOBILE env keys). Two capture paths: mitmproxy extractor (auto-detects web/ios) or scripts/refresh_credentials.py (web-only curl paste). No flat-key fallback.
- See CLAUDE.md for full project conventions

## Active Epics (Summary)
- E-041 (DRAFT): Evaluate json-render -- research epic. 1 spike (R-01: fit assessment) + 1 decision gate (99). Needs expert consultation (UX designer, software engineer) before READY.
- E-042 (READY): Admin Interface and Team Management -- 6 stories. URL-based team onboarding (paste GC URL, resolve via public API), admin CRUD for teams (two-section list: Lincoln Program / Tracked Opponents), opponent auto-discovery from public schedule, DB-driven crawl config. Expert consultation done (UX, DE, SE). Migration 005 (public_id on teams). Dispatch order: 01 first, then 02+06 parallel, then 03, then 04+05 parallel (or sequential if file conflicts).
- E-058 (READY): Fix Relative Path Bug in Proxy Scripts -- 1 story. Fix hardcoded relative paths in proxy-review.sh, proxy-report.sh, proxy-endpoints.sh (resolve via SCRIPT_DIR/REPO_ROOT instead of CWD). SE only.
- E-055 (READY): Unified Operator CLI -- 7 stories. Single `bb` entry point via Typer. Command groups: creds, data, proxy, db, status. Wraps existing scripts as library code. `bb status` = operator health dashboard. Dep chain: 01 first, then 02+03+04+05 parallel, then 06 (needs 02+04), then 07 (needs all). UX+SE consulted. Epic-level deps: E-042 (--source flag on crawl/load), ~~E-052~~, ~~E-053~~, ~~E-054~~. E-052+E-053+E-054 now COMPLETED. Dispatch blocked until E-042 also COMPLETED.
## Archived Epics
- E-004 (COMPLETED): Coaching Dashboard -- all 6 stories DONE. 7 routes: /dashboard (batting), /dashboard/pitching, /dashboard/games, /dashboard/games/{id}, /dashboard/opponents, /dashboard/opponents/{id}, /dashboard/players/{id}. 123 tests. Key artifacts: src/api/helpers.py (ip_display, format_avg, format_date), src/api/templates/dashboard/ (8 templates), src/api/db.py (8 query functions added), src/api/routes/dashboard.py (7 routes). Codex review: 3 findings fixed (context passthrough, date formatting, placeholder tests). Mobile-first with bottom nav, 44px touch targets, sticky headers. IDEA-008/009 now promotable (dashboard ready for trends).
- E-043 (COMPLETED): Dev Environment Auth and Networking Fix -- 1 story. Changed APP_URL, WEBAUTHN_ORIGIN, WEBAUTHN_RP_ID defaults from localhost:8000 to baseball.localhost:8001. Updated .env.example. No follow-up work.
- E-009 (COMPLETED): Tech Stack Redesign -- all 16 stories/spikes DONE. Option B selected (Docker + Cloudflare Access). Key artifacts: docker-compose.yml, Dockerfile, FastAPI+Jinja2 app, production runbook (docs/production-deployment.md), docker-compose.override.yml.example. CLAUDE.md and E-004 updated. E-009-07 operator verification (AC-3/4/5/6) deferred to user. Codex review: 5 fixes applied.
- E-005 (COMPLETED): HTTP Request Discipline -- all 5 stories DONE. Shared HTTP session layer: src/http/headers.py (BROWSER_HEADERS), src/http/session.py (create_session()), GameChangerClient verified using gc-token auth. 27 tests. docs/http-integration-guide.md. Follow-up needed: Chrome 131->145 update + DNT/Referer/Origin headers in BROWSER_HEADERS.
- E-023 (COMPLETED): Auth and Team-Level Permissions -- all 5 stories DONE. Magic link + passkey auth, team-scoped dashboard, admin CRUD. 385 tests. Key files: migrations/003_auth.sql, src/api/auth.py, src/api/routes/auth.py, src/api/routes/admin.py, src/api/email.py. Added webauthn + python-multipart to requirements.txt. E-003-02 cross-epic dependency on E-023-01 is now satisfied.
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
- E-036 (COMPLETED): Fix Codex Code-Review Wrapper -- `codex review` cannot combine [PROMPT] with diff-scope flags. Replaced with `codex exec --ephemeral -` + assembled rubric+diff prompt. User-facing interface unchanged. No follow-up work.
- E-037 (COMPLETED): Codex Review Remediation -- 4 stories. Fixed dashboard query (season->season_id column+format), rewrote E-002 loader orphan-player ACs to stub-player pattern, added E-002-06 soft dep to E-002-08, updated 6 context-layer files from "soft referential integrity" to FK-safe stub-player language. 385 tests pass. No follow-up work.
- E-038 (COMPLETED): Fix PII Pre-Commit Hook Silent Failure -- changed core.hooksPath from absolute to relative path (.githooks). Added auto-setup to devcontainer postCreateCommand. No follow-up work.
- E-002 (COMPLETED): Data Ingestion Pipeline -- all 13 stories DONE (1 research spike + 5 crawlers + 3 loaders + 1 orchestrator + 3 codex remediation). 615 tests total. Crawlers: roster, schedule, game-stats, player-stats, opponent (src/gamechanger/crawlers/). Loaders: roster, game, season-stats (src/gamechanger/loaders/). Orchestration: scripts/crawl.py + scripts/load.py (all 3 loaders wired). Client: get_paginated() with 5xx retry, ForbiddenError/CredentialExpiredError split. Config: config/teams.yaml. IDEA-005 trigger fully met (E-002+E-003 both complete). IDEA-008/009 promotable after dashboard work.
- E-003 (COMPLETED): Data Model and Storage Schema -- all actionable stories DONE (E-003-01: core schema rewrite, E-003-02: coaching_assignments migration 004, E-003-04: seed data + query validation). E-003-03 ABANDONED (absorbed by E-009-02). 394 tests total. Full schema: 10 data tables + 5 auth tables + 1 domain table (coaching_assignments). Migration sequence: 001->003->004.
- E-040 (COMPLETED): UX Designer Agent -- 1 story. Created .claude/agents/ux-designer.md (sonnet, cyan, memory: project). Updated CLAUDE.md Agent Ecosystem table, dispatch-pattern.md routing table, claude-architect.md agent list (7->8 agents). No follow-up work.
- E-044 (COMPLETED): Workflow Trigger Phrases -- 5 stories. Three workflow skills (spec-review, review-epic, implement) + Dispatch Team section in epic template + CLAUDE.md Workflows entries. All context-layer work via claude-architect. Key artifacts: `.claude/skills/spec-review/SKILL.md`, `.claude/skills/review-epic/SKILL.md`, `.claude/skills/implement/SKILL.md`, updated `/.project/templates/epic-template.md`, updated `/.claude/rules/dispatch-pattern.md`, updated `CLAUDE.md` Workflows section. No follow-up work.
- E-045 (COMPLETED): Resolve mitmproxy Port Conflict -- 2 stories. Removed 8080/8081 from devcontainer forwardPorts, added warning comments to docker-compose.yml, added troubleshooting subsection to mitmproxy-guide.md, enhanced proxy.sh status with lsof port-conflict detection. No follow-up work.
- E-039 (COMPLETED): mitmproxy Credential Sync and API Discovery -- 1 research spike + 5 implementation stories. Passive HTTPS proxy for credential extraction, header capture, and API endpoint discovery. Key artifacts: proxy/addons/ (gc_filter, credential_extractor, header_capture, endpoint_logger, loader), proxy/ scripts (start/stop/status/logs), proxy-report.sh + proxy-endpoints.sh, docs/admin/mitmproxy-guide.md. Codex review: namespace collision fixed (mitmproxy/ -> proxy/). 706 tests. Traefik dashboard moved 8080->8180. (E-048 later migrated proxy from Docker Compose profile to standalone host-based proxy/.)
- E-047 (COMPLETED): PM Workflow Bugs -- 3 stories. Fixed (1) user-directed consultation override rule in PM agent def, (2) dispatch authorization gate in 3 files (product-manager.md, dispatch-pattern.md, workflow-discipline.md), (3) spec-review skill Phase 1 timeout/foreground/duration guidance. All context-layer work via claude-architect. No follow-up work.
- E-048 (COMPLETED): Host Proxy Migration -- 7 stories. Migrated mitmproxy from Docker Compose profile to standalone host-based proxy/ folder. Key artifacts: proxy/docker-compose.yml, proxy/ scripts (start/stop/status/logs), proxy/README.md. Removed mitmproxy service from project docker-compose.yml. Cleaned devcontainer.json (removed 8080/8081 ports). Updated CLAUDE.md commands and mitmproxy-guide.md. Deleted proxy-host/ prototype, MITM-TROUBLESHOOTING.md, scripts/proxy.sh. IDEA-010 partially resolved (mitmproxy refs cleaned, remaining scope is getting-started.md port refs -- may already be fixed).
- E-049 (COMPLETED): API Endpoint Documentation and Dual-Header System -- 6 active stories (E-049-04 ABANDONED). Full schema docs for 37 bulk-collected payloads in gamechanger-api.md. Dual-header system (BROWSER_HEADERS + MOBILE_HEADERS) in src/http/headers.py; Chrome 131->145 update. Mobile credential capture workflow in docs/admin/mitmproxy-guide.md. Endpoint Priority Matrix with 4 tiers and top-5 integration recommendations. Three HTTP 500 endpoints documented but unresolved (IDEA-011). E-050-02 cross-epic dependency now satisfied. Follow-up: E-005 note about Chrome 131->145 + DNT/Referer is now resolved.
- E-046 (COMPLETED): Upstream Proxy Support -- 2 stories. Dual-zone Bright Data proxy (residential for web profile, mobile for mobile profile). Python: get_proxy_config(profile) + auto-wired create_session() proxy_url param + trust_env=False. mitmproxy: proxy-entrypoint.sh wrapper, start.sh --profile mobile|web, status.sh upstream display. .env.example updated. 35 session tests. Codex review: 2 findings fixed (case-insensitive PROXY_ENABLED in bash, trust_env test). Follow-up: docs/admin/mitmproxy-guide.md needs --profile and upstream proxy docs (deferred to separate docs-writer dispatch).
- E-050 (COMPLETED): Credential Validation and Crawl Bootstrap -- 4 stories. Credential health check script (`scripts/check_credentials.py`, 10 tests), profile-aware GameChangerClient (`profile` param, gc-app-name logic, 7 new tests), bootstrap pipeline (`scripts/bootstrap.py`, 14 tests), operator bootstrap guide (`docs/admin/bootstrap-guide.md`). `scripts/crawl.py` modified (profile param added to `run()`). Follow-up: CLAUDE.md Commands section needs `python scripts/check_credentials.py` and `python scripts/bootstrap.py` entries (context-layer update for claude-architect). IDEA-012 E-050 blocker now cleared (E-042 remains).
- E-051 (COMPLETED): Fix mitmproxy CA Certificate Persistence -- 1 story. Container runs as root (user: "0:0"), entrypoint chowns cert dir to mitmproxy user, drops privileges via su-exec before exec'ing mitmweb. start.sh mkdir uses -m 777. No follow-up work.
- E-056 (COMPLETED): Fix Dispatch Pattern -- Team Lead as Spawner -- 5 stories. Rewrote dispatch-pattern.md, PM agent def, implement skill, review-epic skill, CLAUDE.md, and workflow-discipline.md. Team lead now spawns all agents (PM + implementers); PM coordinates via SendMessage. IDEA-007 partially addressed (dispatch pattern now structurally correct). No follow-up work.
- E-053 (COMPLETED): Profile-Scoped Credentials -- 4 stories. Profile-scoped env keys (_WEB/_MOBILE) for credential extractor, GameChangerClient, check_credentials, bootstrap. No flat-key fallback (clean break). refresh_credentials.py writes _WEB keys. .env.example updated. 930 tests. E-050 follow-up (CLAUDE.md commands) resolved. E-055 epic-level dep now satisfied.
- E-054 (COMPLETED): Header Parity Refresh from MITM Captures -- 2 stories. scripts/proxy-refresh-headers.py reads proxy capture report, rewrites src/http/headers.py (dry-run default, --apply to write). header_capture.py parity fix (each source diffs against correct canonical dict). Workflow docs in CLAUDE.md + mitmproxy-guide.md. 57 new tests. E-055 epic-level dep now satisfied.
- E-052 (COMPLETED): Proxy Data Lifecycle -- 5 stories. Session-scoped proxy capture dirs (`proxy/data/sessions/`), addon output routing via `PROXY_SESSION_DIR` env var, review tracking (`scripts/proxy-review.sh`), session-aware report scripts (`--session`/`--all`/`--unreviewed`), stop-time summary. Key artifacts: proxy/start.sh (session creation), proxy/stop.sh (finalization + summary), proxy/docker-compose.yml (env var), proxy/addons/endpoint_logger.py + header_capture.py (session-aware paths), scripts/proxy-review.sh (new), scripts/proxy-endpoints.sh + proxy-report.sh (session flags). 4 new tests. Docs updated: mitmproxy-guide.md, CLAUDE.md Commands. E-055 epic-level dep now satisfied.

## Key Architectural Decisions
- Storage: SQLite (WAL mode). Host-mounted at ./data/app.db. Simple file backup via scripts/backup_db.py (no Litestream).
- Serving layer: FastAPI + Jinja2 (Python). Single monolithic app. No TypeScript.
- Deployment: Docker Compose (local + prod). Home Linux server (no VPS, no hosting cost). Cloudflare Tunnel + Zero Trust.
- Migrations: numbered SQL scripts (migrations/001_*.sql). No Alembic. apply_migrations.py at startup.
- HTTP layer: src/http/headers.py + src/http/session.py. Dual-header system: BROWSER_HEADERS (Chrome 145/macOS) + MOBILE_HEADERS (iOS Odyssey). create_session(profile="web"|"mobile"). Profile-aware proxy: PROXY_ENABLED + PROXY_URL_WEB/PROXY_URL_MOBILE env vars, get_proxy_config(profile), trust_env=False. Bright Data dual-zone (residential for web, mobile for mobile).
- ip_outs: innings pitched stored as integer outs (1 IP = 3 outs)
- FK-safe orphan handling: unknown player_ids get a stub row (first_name='Unknown', last_name='Unknown') inserted before the stat row; WARNING logged for operator backfill
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
| IDEA-005 | Directory-Scoped Intent Nodes at src/ Module Boundaries | CANDIDATE | 2026-06-01 | Phase 2 of abandoned E-010. **Trigger met**: E-002+E-003 both complete. Ready for promotion review. |
| IDEA-006 | Epic Lanes Convention for Multi-Workstream Epics | CANDIDATE | 2026-06-01 | Formalize lane-style Technical Notes headers. Promote when 6+ story epics are common AND agents report TN scoping confusion. |
| IDEA-007 | Dispatch Coordinator Guardrail | CANDIDATE | 2026-06-02 | Prevent team-lead-as-PM bypass in dispatch. Root cause: E-037 team lead created dispatch team directly instead of spawning PM first. Promote at next multi-story dispatch. |
| IDEA-008 | Plays and Line Scores Crawling | CANDIDATE | 2026-06-02 | Pitch-by-pitch plays + inning line scores. **Trigger met**: E-002+E-004 complete, dashboard ready. Promotable when coaches need pitch-level data. |
| IDEA-009 | Per-Player Game Stats + Spray Charts | CANDIDATE | 2026-06-02 | Per-player per-game stats + spray chart x/y data. **Trigger met**: E-002+E-004 complete, dashboard ready for trends. Promotable. |
| IDEA-010 | Docs Port Map Consistency for Devcontainer + Compose | CANDIDATE | 2026-06-03 | Patch stale docs port references (notably Traefik dashboard `8180` vs old `8080`) to match current compose/devcontainer networking. |
| IDEA-011 | Investigate HTTP 500 Endpoint Failures | CANDIDATE | 2026-06-04 | Three endpoints return 500 with web headers, succeeded in iOS proxy capture. Root cause unknown. Extracted from E-049-04 (ABANDONED). Blocked by E-049 completion + mobile credentials. |
| IDEA-012 | Crawl Orchestration and Scheduling System | CANDIDATE | 2026-06-06 | Recurring crawl scheduling, credential rotation awareness, run history, alerting. Trigger: operator has run bootstrap 5+ times manually OR season starts. E-050 blocker cleared; E-042 remains. |

## Key Workflow Contract
- Routing model: user -> PM -> implementing agent (no orchestrator; removed in E-030)
- PM modes: Refinement (form epics) / Decision Gates (evaluation synthesis) / Dispatch (execute stories)
- Epic lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED)
- READY gate: must be READY/ACTIVE before dispatch. PM sets READY explicitly.
- Dispatch: Team lead creates team and spawns PM + implementers. PM coordinates via SendMessage. See /.claude/rules/dispatch-pattern.md.
- Direct-routing exceptions (no PM needed): api-scout, baseball-coach, claude-architect
- Implementing agents needing work auth: software-engineer, data-engineer, docs-writer
- Agent ecosystem: 8 agents (claude-architect, product-manager, baseball-coach, api-scout, data-engineer, software-engineer, docs-writer, ux-designer)
- Before assigning epic numbers: ALWAYS ls /epics/ to avoid numbering collisions

## Detailed Notes (Separate Files)
- `lessons-learned.md` -- Epic authoring patterns, dependency patterns, process patterns, platform constraints
- `mcp-research.md` -- MCP server evaluation findings (E-009-R-05, R-06)
