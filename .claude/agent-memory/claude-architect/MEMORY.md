# Claude Architect -- Agent Memory

## Core Principle: Simple First, Complexity as Needed
IMPORTANT -- This is the governing design principle for the entire project.
- Build the smallest working thing, then iterate
- Do NOT pre-create agents, infrastructure, or abstractions before they are needed
- One file > framework, script > pipeline, dict > class (until it isn't)
- When in doubt, leave it out
- CRITICAL LESSON: The principle guides FUTURE decisions. It does NOT justify deleting existing working context, architectural details, or agent configs. Existing documentation has value.

## Project: baseball-crawl
- Project root: repository root (workspace-relative paths used throughout)
- Purpose: Coaching analytics for Lincoln Standing Bear HS baseball (GameChanger data)
- Teams: Freshman, JV, Varsity, Reserve (Legion later)
- Users: Jason (operator), coaching staff (consumers)
- MVP: queryable database for scouting/game prep; dashboards come later
- State: Active development -- src/http/ module exists (headers, session factory), multiple epics completed

## Key Architectural Decisions
- PII safety system: two-layer defense (Git pre-commit hook + Claude Code PreToolUse hook)
  - Design doc: `/.project/research/E-006-precommit-design.md`
  - Git hook: `.githooks/pre-commit` with `core.hooksPath` (not pre-commit framework)
  - Claude Code hook: `.claude/hooks/pii-check.sh` (PreToolUse, Bash matcher)
  - Scanner: `src/safety/pii_scanner.py` (stdlib only, shared by both hooks)
  - No agent/skill created for scanning (deterministic check, not reasoning)
- Product-manager has full template content inline (comprehensive operational manual)
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite (WAL mode). Home Linux server. Simple file backup via scripts/backup_db.py. Decision finalized in E-009.
- Docker Compose stack (3 services): app (FastAPI, localhost:8001 direct / localhost:8000 via Traefik), traefik (reverse proxy, dashboard at :8180), cloudflared (tunnel). E-027 established devcontainer-to-compose networking.
- App troubleshooting section in CLAUDE.md covers: stack management, health check, logs, rebuild after changes, unreachable diagnosis. Agents should rebuild + health-check after modifying src/, migrations/, Dockerfile, docker-compose.yml, or requirements.txt.
- Proxy boundary: mitmproxy runs on Mac host, NOT in the devcontainer. Agents must not attempt proxy lifecycle commands (start/stop/status/logs). Agents CAN read proxy data from `proxy/data/` and credentials from `.env`. Documented in CLAUDE.md "Proxy Boundary" section + Commands subsection separation + `.claude/rules/proxy-boundary.md` (glob-triggered on `proxy/**`). See `docs/admin/mitmproxy-guide.md` for full details.
- CLAUDE.md has Core Principle section at top, followed by full project context
- Ideas workflow in `/.project/ideas/` for pre-epic tracking (IDEA-NNN numbering)
- Ideas rule: if acceptance criteria cannot be written, it is not an epic -- capture as idea
- Ideas are reviewed on every epic completion (mandatory) and every 90 days
- Ideas workflow encoded in five places:
  - `CLAUDE.md` (Ideas Workflow subsection under Project Management)
  - `.claude/rules/ideas-workflow.md` (scoped rule, paths: .project/ideas/**)
  - `.claude/agents/product-manager.md` (Ideas Workflow section + System of Work flow)
  - `.claude/agent-memory/product-manager/MEMORY.md` (idea numbering state)
- PM handles "capture for later" / "someday" / "idea" intent directly
- Any agent identifying future work should flag to PM, not create speculative epics
- Auth module architecture (E-077): `src/gamechanger/exceptions.py` (shared exceptions to break circular imports), `signing.py` (gc-signature HMAC-SHA256), `token_manager.py` (POST /auth refresh, caching, .env write-back via `atomic_merge_env_file()`), `client.py` (lazy token fetch, 401 retry). TokenManager uses standalone httpx client (NOT `create_session()`). `dotenv_values()` used throughout (does NOT populate `os.environ`). HTTP 400 on POST /auth = signing error (`AuthSigningError`); HTTP 401 = token error (`CredentialExpiredError`).
- Dashboard access model (E-228): admin-sees-all. `_get_permitted_teams()` in `src/api/auth.py` returns ALL `teams` rows for admins, explicit `user_team_access` grants for non-admins (dev + prod). Canonical admin predicate is `_user_is_admin(conn, user)` / `user_is_admin(user)` in `src/api/auth.py` (admin = ADMIN_EMAIL match OR `users.role='admin'`); `dashboard.py::_is_admin_user` and `admin.py::_require_admin` delegate — no third copy allowed. `bb db reset` now produces an EMPTY DB (migrations + `programs` lsb-hs bootstrap only; seed_dev.sql + scripts/seed_dev.py deleted). Codified in CLAUDE.md Architecture (two canonical entries) + `.claude/rules/data-model.md` (empty-reset footgun).
- Report generation telemetry (E-235): `report_generation_runs` (migration 002) — one WIDE row per report generation (mirrors `scouting_runs`), FK→reports CASCADE, UNIQUE(report_id); the audit foundation Epic E (scheduled reports) builds on. Three durable patterns codified: (a) wide run-record pattern, (b) canonical-function ADDITIVE-EXTENSION (`ensure_team_row`→`ensure_team_row_with_provenance`/`EnsureTeamResult`; `derive_season_id_for_team`→`..._with_fallback`/`SeasonDerivation` — legacy delegates, zero caller churn), (c) per-run created-set orphan attribution via `EnsureTeamResult.inserted` (cross-process safe, no snapshot). KEY FOOTGUN — scored-but-empty games: a completed `games` row can have ZERO stat rows (scores written unconditionally, stats conditionally); scored-but-empty is the MODAL scouting case. Any coverage/freshness signal MUST be data-bearing (EXISTS on player_game_*, perspective-scoped), never a bare COUNT of scored games. Codified in `.claude/rules/architecture-subsystems.md` (a, b, c) + `.claude/rules/data-model.md` (data-bearing coverage trap + concurrent-INSERT recovery). No CLAUDE.md change — rules glob-trigger on src/reports, src/db, migrations, loaders (proportional/simple-first).
- Report self-reporting integrity (E-236): `classify_stage_status(loaded, errors, expected)` in `src/reports/run_status.py` is the SINGLE per-stage status authority — every load/crawl stage routes its `*_status` through it via `STATUS_COMPLETED/PARTIAL/FAILED` constants (no literals). CORE PRINCIPLE: status is ERROR-DRIVEN not coverage-driven — plays/spray coverage shortfalls (scorekeeper-didn't-chart, null≠error) must NEVER be `partial`; only the boxscore crawl uses coverage-shortfall→partial. Failure-signal precedence: stages with own failure signal map to FAILED before the classifier. `overall_status` CHECK (running/completed/failed) NOT widened — "degraded" is DERIVED at read time, never stored. Operator-vs-coach honesty split (degradation → admin only). FOOTGUN: `_RUN_RECORD_COLUMNS` frozenset in generator.py silently DROPS writes to unlisted columns — add column to allowlist + prove with real-schema round-trip test. Codified in `.claude/rules/architecture-subsystems.md` (Reports Package: stage-status honesty + allowlist footgun), `.claude/rules/data-model.md` (load-status corollary cross-ref in Data-Bearing Coverage), `.claude/rules/testing.md` (pytest pipe-RC trap + disk-backed db.backup deadlock). No CLAUDE.md change — subsystem detail in already-referenced rules (simple-first).
- Payload-first loaders + aggregate integrity (E-237): TWO codifications. (1) `canonical_recompute(conn, team_id, season_id)` in `src/db/season_aggregates.py` is the SINGLE entry point for `boxscore_only` season-aggregate recomputes (DELETE+INSERT, perspective-scoped, Option-B superset columns); `ScoutingLoader._compute_season_aggregates` + player-dedup path delegate. PROVENANCE OWNERSHIP: owns ONLY boxscore_only, never touches full/supplemented member rows. (2) MIXED-PROVENANCE SCOPE FOOTGUN (caused TWO real bugs): one (team_id, season_id) can legitimately hold both a member `full` row AND `boxscore_only` rows; any per-scope recompute/aggregate/compare/delete-rewrite of `player_season_*` MUST apply the same full/supplemented exclusion — fixed sites: `aggregate_parity.py::verify_aggregates`, `player_dedup.py::merge_player_pair`. (3) Payload-first loader pattern: `PlaysLoader.load_payload`/`GameLoader.load_payload` are in-memory entry points; path methods are thin file-reading wrappers over a shared core (removed last 2 temp-file bridges from reports core). Codified in CLAUDE.md Architecture (canonical helper entry) + `.claude/rules/data-model.md` (Season-Aggregate Parity: mixed-provenance footgun) + `.claude/rules/architecture-subsystems.md` (Reports Package: payload-first loaders).
- Dispatch pattern: PM is a standing team coordinator (not fire-and-forget)
  - PM joins every dispatch team, stays active throughout, manages all state
  - Implementers do NOT update story statuses or epic tables -- PM owns that
  - PM verifies acceptance criteria before marking DONE, cascades to unblocked stories
  - Encoded in: `dispatch-pattern.md` (rule), `product-manager.md` (Dispatch Mode), `CLAUDE.md` (Workflow Contract #5)

## User Preferences (Jason)
- "Simple first" is a guiding principle for FUTURE decisions, not a deletion tool
- Actively edits project files -- respect his changes, do not revert
- Values detailed context in agent prompts (full operational manuals)
- Wants all architectural details preserved (stack decisions, metrics, collaboration patterns)

## Pending Context-Layer Updates
- `review-cycle-reordering.md` -- Internal reviews (CR + team) before Codex in plan and implement skills; review scorecard pattern for epic History. Approved 2026-03-22, awaiting epic.

## Topic File Index
- `claude-practices.md` -- CLAUDE.md design, context management
- `agent-design.md` -- Subagent architecture, ecosystem patterns
- `skills-and-hooks.md` -- Skills system, hooks patterns
- `semantic-layer.md` -- Intent routing, layering strategy
- `agent-blueprints.md` -- Historical blueprints for agents (data-engineer, software-engineer built via E-013; baseball-coach, api-scout for reference)
- `boundaries.md` -- Operational boundary catalog (host vs container, auth vs public, PII, hallucinated identifiers)
- `ingest-workflow-log.md` -- Per-endpoint integration history from ingest-endpoint skill executions (19 endpoints, 2026-03-04)
- `codex-config.md` -- Codex CLI configuration, model, reasoning effort, available models

## Claude Code Platform Facts
- CLAUDE.md loaded every session; keep concise
- First 200 lines of MEMORY.md auto-loaded into system prompt
- Hooks: deterministic; CLAUDE.md: advisory
- Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) -- teammates CAN spawn other teammates (no nesting limit)
- Task tool: single subagent, no further nesting. Use for simple consultations.
- Agent Teams: multi-agent coordination with free spawning. Use for epic/story dispatch.
- Context window is the #1 resource to manage
- Statusline: configured via `statusLine` key in settings.json (type: "command", command: path to script)
- Statusline receives JSON on stdin with model, workspace, cost, context_window, etc.
- For devcontainer portability: use relative paths in statusLine.command (e.g., `.claude/hooks/statusline.sh`)
- Statusline runs after each assistant message, debounced at 300ms
- Custom hooks live in `.claude/hooks/` directory

## Epic History (Agent Ecosystem)
- E-013 (COMPLETED 2026-03-02): Agent Buildout -- completed data-engineer and software-engineer from stubs to full operational manuals, seeded memory directories for api-scout, baseball-coach, software-engineer, and data-engineer, wired skill references into all agent definitions. Absorbed E-012 and E-014.

## Skills Index
Four skills in `.claude/skills/`:
- **context-fundamentals** -- Context window mechanics, budget management, load/defer decisions
- **filesystem-context** -- File-based context delivery, progressive disclosure, ambient vs. deferred
- **multi-agent-patterns** -- Telephone game problem, verbatim relay, dispatch checklist
- **ingest-endpoint** -- Workflow automation: two-phase GameChanger API endpoint ingestion (api-scout -> claude-architect). Created 2026-03-04. Referenced from: CLAUDE.md (Workflows section). Replaces manual workflow used for season-stats and game-summaries endpoints.

## Domain Reference Documents
- `docs/api/` -- API spec directory (owned by api-scout). Index at `docs/api/README.md`, per-endpoint files in `docs/api/endpoints/`, global reference files in `docs/api/*.md`.
- `docs/gamechanger-stat-glossary.md` -- stat abbreviation data dictionary (owned by api-scout, created 2026-03-04). Referenced from: CLAUDE.md (Key Metrics), api-scout agent def + memory, data-engineer agent def + memory, software-engineer agent def + memory, baseball-coach agent def + memory. Integration audit completed 2026-03-04.

## Ingest-Endpoint Workflow Executions
20 integrations (19 endpoints 2026-03-04, plus POST /search re-ingestion 2026-03-29). Full per-endpoint integration log: `ingest-workflow-log.md`

## Codex Configuration
Details in topic file: `codex-config.md`

## Known Hallucination Traps
- `ghcr.io/devcontainers/features/apt:1` DOES NOT EXIST. The official devcontainers/features registry has no apt installer feature. Real apt features are from rocker-org and devcontainers-extra. See `.claude/rules/devcontainer.md` for correct identifiers.
- General rule: always verify devcontainer feature identifiers against https://containers.dev/features before referencing them in rules or configs.
