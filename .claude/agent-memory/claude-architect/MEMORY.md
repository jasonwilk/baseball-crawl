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
- MVP (achieved): queryable database for scouting/game prep. Product is REPORTS-FIRST -- generate a report for a GC `public_id` and share the link. The dashboard, member-sync, and tracked-opponent surfaces were REMOVED in E-239 (ROADMAP D2 slice), NOT quarantined. Forward feature: morning-of-game scheduled reports.
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
- Team access model (admin-sees-all, E-228; surfaces trimmed E-239): `_get_permitted_teams()` in `src/api/auth.py` returns ALL `teams` rows for admins, explicit `user_team_access` grants for non-admins (dev + prod). Canonical admin predicate is `_user_is_admin(conn, user)` / `user_is_admin(user)` in `src/api/auth.py` (admin = ADMIN_EMAIL match OR `users.role='admin'`). After E-239 the SURVIVING delegator is `reports_admin.py::_require_admin` — the old `dashboard.py::_is_admin_user` and `admin.py::_require_admin` were DELETED with the dashboard / admin-team-management surfaces (no second copy allowed). `bb db reset` produces an EMPTY DB (migrations + `programs` lsb-hs bootstrap only; seed_dev.sql + scripts/seed_dev.py deleted in E-228). Codified in CLAUDE.md Architecture (two canonical entries) + `.claude/rules/data-model.md` (empty-reset footgun).
- Report generation telemetry (E-235): `report_generation_runs` (migration 002) — one WIDE row per report generation (mirrors `scouting_runs`), FK→reports CASCADE, UNIQUE(report_id); the audit foundation Epic E (scheduled reports) builds on. Three durable patterns codified: (a) wide run-record pattern, (b) canonical-function ADDITIVE-EXTENSION — live example `ensure_team_row`→`ensure_team_row_with_provenance`/`EnsureTeamResult` (legacy delegates, zero caller churn); the season-derivation instance of this pattern was DELETED in E-241 (year-only collapse), leaving `ensure_team_row` the sole live example, (c) per-run created-set orphan attribution via `EnsureTeamResult.inserted` (cross-process safe, no snapshot). KEY FOOTGUN — scored-but-empty games: a completed `games` row can have ZERO stat rows (scores written unconditionally, stats conditionally); scored-but-empty is the MODAL scouting case. Any coverage/freshness signal MUST be data-bearing (EXISTS on player_game_*, perspective-scoped), never a bare COUNT of scored games. Codified in `.claude/rules/architecture-subsystems.md` (a, b, c) + `.claude/rules/data-model.md` (data-bearing coverage trap + concurrent-INSERT recovery). No CLAUDE.md change — rules glob-trigger on src/reports, src/db, migrations, loaders (proportional/simple-first).
- Report self-reporting integrity (E-236): `classify_stage_status(loaded, errors, expected)` in `src/reports/run_status.py` is the SINGLE per-stage status authority — every load/crawl stage routes its `*_status` through it via `STATUS_COMPLETED/PARTIAL/FAILED` constants (no literals). CORE PRINCIPLE: status is ERROR-DRIVEN not coverage-driven — plays/spray coverage shortfalls (scorekeeper-didn't-chart, null≠error) must NEVER be `partial`; only the boxscore crawl uses coverage-shortfall→partial. Failure-signal precedence: stages with own failure signal map to FAILED before the classifier. `overall_status` CHECK (running/completed/failed) NOT widened — "degraded" is DERIVED at read time, never stored. Operator-vs-coach honesty split (degradation → admin only). FOOTGUN: `_RUN_RECORD_COLUMNS` frozenset in generator.py silently DROPS writes to unlisted columns — add column to allowlist + prove with real-schema round-trip test. Codified in `.claude/rules/architecture-subsystems.md` (Reports Package: stage-status honesty + allowlist footgun), `.claude/rules/data-model.md` (load-status corollary cross-ref in Data-Bearing Coverage), `.claude/rules/testing.md` (pytest pipe-RC trap + disk-backed db.backup deadlock). No CLAUDE.md change — subsystem detail in already-referenced rules (simple-first).
- Payload-first loaders + aggregate integrity (E-237): TWO codifications. (1) `canonical_recompute(conn, team_id, season_id)` in `src/db/season_aggregates.py` is the SINGLE entry point for `boxscore_only` season-aggregate recomputes (DELETE+INSERT, perspective-scoped, Option-B superset columns); `ScoutingLoader._compute_season_aggregates` + player-dedup path delegate. PROVENANCE OWNERSHIP: owns ONLY boxscore_only, never touches full/supplemented member rows. (2) MIXED-PROVENANCE SCOPE FOOTGUN (caused TWO real bugs): one (team_id, season_id) can legitimately hold both a member `full` row AND `boxscore_only` rows; any per-scope recompute/aggregate/compare/delete-rewrite of `player_season_*` MUST apply the same full/supplemented exclusion — fixed sites: `aggregate_parity.py::verify_aggregates`, `player_dedup.py::merge_player_pair`. (3) Payload-first loader pattern: `PlaysLoader.load_payload`/`GameLoader.load_payload` are in-memory entry points; path methods are thin file-reading wrappers over a shared core (removed last 2 temp-file bridges from reports core). Codified in CLAUDE.md Architecture (canonical helper entry) + `.claude/rules/data-model.md` (Season-Aggregate Parity: mixed-provenance footgun) + `.claude/rules/architecture-subsystems.md` (Reports Package: payload-first loaders).
- Reports-first surface removal (E-239, ROADMAP D2): DELETED the dashboard, the member-sync pipeline (`src/pipeline/` whole package), opponent discovery (`opponent_resolver.py`/`opponent_seeder.py`), the standalone member/plays/spray crawlers + loaders, `src/api/routes/{dashboard,admin}.py`, `config/teams.yaml`, `src/gamechanger/config.py`, `src/db/merge.py`, `finalize_opponent_resolution()`, and the `bb data crawl/load/scout/dedup/repair-opponents` CLI. Reports (`src/reports/`) is the SOLE scouting/delivery surface; admin SURVIVES as `src/api/routes/reports_admin.py` (reports + user management under `/admin`). Surviving `bb data` = reconcile/dedup-players/backfill (maintenance over already-loaded data); plays/spray now fetched in-memory by the report generator. Context layer: DELETED `.claude/rules/quarantine.md` (the `resolve_unlinked` follow→bridge→unfollow ban now lives SELF-CONTAINED in `gc-uuid-bridge.md`) and `.claude/rules/scouting-data-flows.md` (serving/lifecycle/naming conventions migrated into `architecture-subsystems.md` Reports Package); trimmed parity/pipeline-caller/opponent-resolution content from CLAUDE.md + 9 rules; cleaned dangling `paths:` frontmatter (dashboard.py, src/pipeline, templates/dashboard, scripts/*crawl*/*fetch*). KEPT `src/gamechanger/crawlers|loaders/**` + `parsers/**` globs (still match scouting/plays/game survivors). De-scoped permanently: cross-team identity (E-104), multi-season rollups, longitudinal tracking. "Quarantine" is now historical vocabulary — surfaces are GONE, not parity-excluded.
- Removal-epic process footguns (learned E-239): (1) Surface-REMOVAL epics break tests in files NO story touches — e.g. `tests/test_auth.py` used `GET /dashboard` as a generic authenticated-200 probe; per-story review can't catch it (10 tests failed, surfaced only at Phase 4a integration review + the full-suite-green gate). Remedy: for removal epics, repo-wide grep the removed route/symbol across ALL tests during the integration-review step (codified: implement skill Phase 4a). (2) Large removal diffs blow the Codex input limit — the full E-239 diff was ~2.57M chars / 84 deleted files vs Codex's ~1.05M limit; scoping to added/modified/renamed only (ACMR — pure deletions have no content to review and dominate the byte count) brought it to ~445K and worked (codified: codex-review skill size-refuse remedy). Do NOT change `codex-review.sh`'s default `git diff main` — dropping deletions universally would hide removal-completeness signal; ACMR is a per-run remedy for oversized removal diffs only.
- Season machinery removal → year-only collapse (E-241, ROADMAP-adjacent de-scope): ripped the multi-season bones out at the ROOT (the user's ~5×-asked deep de-scope, not another leaf patch). DELETED the `program_type`→suffix taxonomy (`_PROGRAM_TYPE_SUFFIX`, `spring-hs`/`summer-usssa`/`summer-legion`), the `season_fallback` telemetry flag+badge+chain (migration 006 drops the column), the `derive_season_id_for_team_with_fallback`/`SeasonDerivation` additive-extension variant, and the crawler's `season_suffix` param. SURVIVING load-bearing kernel: `derive_season_id_for_team` keeps its `tuple[str,int|None]` signature but is now YEAR-ONLY (`str(season_year or datetime.now().year)`) — the current-year fallback STAYS; `ensure_season_row` always writes `season_type='default'`; the scouting crawler's `_derive_season_id` is year-only and names BOTH the on-disk `data/raw/{season}/...` dir and the DB writes. Filesystem-vs-DB decoupling SURVIVES as a stronger invariant: loaders glob the season path component as an opaque literal (`*`) and NEVER parse the DB `season_id` from it (derive from team metadata instead), so a LEGACY compound on-disk tree may differ from year-only DB rows. Context layer (E-241-04): trimmed `architecture-subsystems.md` (Season_id Derivation rewritten year-only; additive-extension menu drops the dead `*_with_fallback` half + dead example; Filesystem-vs-DB section REVISED not retired). CLAUDE.md byte-untouched (tuple shape unchanged). TWO footguns codified in `.claude/rules/data-model.md` (Seasons Row section): (a) two writers (`_ensure_season_row` crawler + canonical `ensure_season_row`) both `ON CONFLICT DO NOTHING` → first-writer-wins is SILENT, so they MUST agree on all non-key columns (bug: crawler wrote `'unknown'`, suppressed `'default'`); (b) a seeded compound `season_id` literal in a test is NOT format-invariant if a loader DERIVES year-only from team metadata → silent `FOREIGN KEY constraint failed` (only the full suite proves invariance, grep-only recon insufficient).
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
- Play-ingestion fidelity north star (codified 2026-06-28): DIRECTIONAL operating principle added to CLAUDE.md Data Philosophy ("### Operating Principle: Always Get Closer to Byte-Identical Play Ingestion"), cross-refs `docs/VISION.md` north-star section. FORWARD ITEM at E-245 closure: the concrete mechanical-enforcement rule ("play-ingestion changes must not regress the reconciliation scoreboard") lands only once the E-245 scoreboard tool/command actually exists -- context-layer assessment at E-245 closure picks it up. Do NOT author the enforcement rule before the scoreboard exists.

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
- Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) -- only the main session (lead) spawns subagents via the `Agent` tool; subagents cannot spawn their own (no nesting)
- Flag gates the team-coordination surface: without `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, the team-coordination tools (`SendMessage` + the shared `Task*` task list) are unavailable and spawned agents are one-shot
- `TeamCreate`/`TeamDelete` were removed in Claude Code v2.1.178 (recorded 2026-06-29) -- team formation is now implicit and teardown automatic; no explicit create/delete calls exist
- `Agent` (Task tool): main session only; spawns a named subagent. Subagents are long-lived and resumable -- re-engage via `SendMessage` with context intact. Use for epic/story dispatch.
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
