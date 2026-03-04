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

## Agent Ecosystem (Current)
Seven agents in `.claude/agents/`:
- **claude-architect** (opus, yellow): Meta-agent. Designs/manages agents, CLAUDE.md, rules.
- **product-manager** (opus, green): Product Manager and entry point. Epics, stories, dispatch via Agent Teams. No code.
- **baseball-coach** (sonnet, red): Domain expert. Coaching needs -> technical requirements.
- **api-scout** (sonnet, orange): GameChanger API exploration, documentation, credential patterns.
- **data-engineer** (sonnet, blue): Database schema, SQL migrations, ETL pipelines, query optimization.
- **general-dev** (sonnet, blue): Python implementation. Crawlers, parsers, loaders, utilities, tests.
- **docs-writer** (sonnet, purple): Documentation specialist. Admin and coaching docs.

### When to Create New Agents
Only when a user request requires specialized capability that existing agents cannot handle AND the work is recurring.

## Key Architectural Decisions
- PII safety system: two-layer defense (Git pre-commit hook + Claude Code PreToolUse hook)
  - Design doc: `/.project/research/E-006-precommit-design.md`
  - Git hook: `.githooks/pre-commit` with `core.hooksPath` (not pre-commit framework)
  - Claude Code hook: `.claude/hooks/pii-check.sh` (PreToolUse, Bash matcher)
  - Scanner: `src/safety/pii_scanner.py` (stdlib only, shared by both hooks)
  - No agent/skill created for scanning (deterministic check, not reasoning)
- Product-manager has full template content inline (comprehensive operational manual)
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite (WAL mode). Home Linux server. Simple file backup via scripts/backup_db.py. Decision finalized in E-009.
- Docker Compose stack (3 services): app (FastAPI, localhost:8001 direct / localhost:8000 via Traefik), traefik (reverse proxy, dashboard at :8080), cloudflared (tunnel). E-027 established devcontainer-to-compose networking.
- App troubleshooting section in CLAUDE.md covers: stack management, health check, logs, rebuild after changes, unreachable diagnosis. Agents should rebuild + health-check after modifying src/, migrations/, Dockerfile, docker-compose.yml, or requirements.txt.
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

## Topic File Index
- `claude-practices.md` -- CLAUDE.md design, context management
- `agent-design.md` -- Subagent architecture, ecosystem patterns
- `skills-and-hooks.md` -- Skills system, hooks patterns
- `semantic-layer.md` -- Intent routing, layering strategy
- `agent-blueprints.md` -- Historical blueprints for agents (data-engineer, general-dev built via E-013; baseball-coach, api-scout for reference)

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

## Agent Frontmatter
- REQUIRED: `name`, `description`
- RECOMMENDED: `model`, `color`, `memory`
- Model guide: haiku=routing, sonnet=balanced, opus=deep reasoning
- `description` used for routing decisions

## Epic History (Agent Ecosystem)
- E-013 (COMPLETED 2026-03-02): Agent Buildout -- completed data-engineer and general-dev from stubs to full operational manuals, seeded memory directories for api-scout, baseball-coach, general-dev, and data-engineer, wired skill references into all agent definitions. Absorbed E-012 and E-014.

## Skills Index
Four skills in `.claude/skills/`:
- **context-fundamentals** -- Context window mechanics, budget management, load/defer decisions
- **filesystem-context** -- File-based context delivery, progressive disclosure, ambient vs. deferred
- **multi-agent-patterns** -- Telephone game problem, verbatim relay, dispatch checklist
- **ingest-endpoint** -- Workflow automation: two-phase GameChanger API endpoint ingestion (api-scout -> claude-architect). Created 2026-03-04. Referenced from: CLAUDE.md (Workflows section). Replaces manual workflow used for season-stats and game-summaries endpoints.

## Domain Reference Documents
- `docs/gamechanger-api.md` -- API spec (owned by api-scout)
- `docs/gamechanger-stat-glossary.md` -- stat abbreviation data dictionary (owned by api-scout, created 2026-03-04). Referenced from: CLAUDE.md (Key Metrics), api-scout agent def + memory, data-engineer agent def + memory, general-dev agent def + memory, baseball-coach agent def + memory. Integration audit completed 2026-03-04.

## Ingest-Endpoint Workflow Executions
- **player-stats** (2026-03-04): Third successful execution of the ingest-endpoint skill. Phase 2 updates: data-engineer memory (spray chart schema implications, per-game stat structure), general-dev memory (raw sample path, endpoint parsing notes), baseball-coach memory (coaching value of per-game stats and spray charts), CLAUDE.md Key Metrics (added per-game splits and spray charts). No new stat abbreviations -- all fields already in glossary.

## Ingest-Endpoint Workflow Executions (continued)
- **schedule** (2026-03-04): Fourth execution of the ingest-endpoint skill. Existing endpoint with stub replaced by full schema. Phase 2 updates: data-engineer memory (location polymorphism, coordinate key inconsistency, full-day format, opponent_id, status filtering, Game entity mapping), general-dev memory (raw sample path, 6 location shapes, full-day format, coordinate normalization), baseball-coach memory (opponent_id for automated scouting, home_away splits, lineup_id). No CLAUDE.md changes (existing Opponents bullet already covers the use case). No stat glossary changes (schedule is structural data, not stats). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 2)
- **team-detail** (2026-03-04): Fifth execution of the ingest-endpoint skill. NEW endpoint (`GET /teams/{team_id}`), single team object. Phase 2 updates: data-engineer memory (innings_per_game for stat normalization, settings.scorekeeping.bats structure, opponent metadata use case, raw sample path), general-dev memory (raw sample path added to data/raw inventory, team-detail endpoint section with innings_per_game and competition_level, ngb double-parse note extended), baseball-coach memory (innings_per_game for K/9 and BB/9 normalization across game lengths, competition_level for tier comparison, opponent record as scouting signal). No CLAUDE.md changes (existing Opponents bullet covers the use case; innings_per_game is below Key Metrics abstraction level). No stat glossary changes (structural metadata, not stats). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 3)
- **team-detail opponent validation** (2026-03-04): Sixth context integration (not a full ingest -- api-scout re-validated an existing endpoint with an opponent team UUID). Key finding: `opponent_id` from schedule works as `team_id` in `/teams/{team_id}`, returning identical 25-field schema with `stat_access_level: confirmed_full`. Phase 2 updates: data-engineer memory (opponent_id confirmed, stat_access_level signal for deeper endpoints), general-dev memory (opponent sample path added to inventory, opponent_id status upgraded from "potential" to "confirmed", team-detail section updated), baseball-coach memory (opponent scouting pipeline confirmed: schedule -> opponent_id -> team-detail -> season-stats/players expected, spray chart scouting note updated). No CLAUDE.md changes (Opponents bullet already covers the use case at the right abstraction level). No stat glossary changes (structural metadata, not stats). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 4)
- **public-team-profile** (2026-03-04): Seventh context integration. NEW endpoint (`GET /public/teams/{public_id}`), first confirmed unauthenticated endpoint. Phase 2 updates: data-engineer memory (no-auth pipeline split, public_id slug vs UUID mapping, record key singular/plural normalization, staff array, avatar_url expiry, team_season wrapper), general-dev memory (raw sample path added to inventory, no-auth HTTP client note, record key normalization, id-is-slug warning, staff field structure), baseball-coach memory (staff names for scouting context, no-auth as supplement not replacement for authenticated pipeline), CLAUDE.md GameChanger API section (split into authenticated vs public endpoint bullets, public_id slug distinction). No stat glossary changes (structural metadata, not stats). No agent definition or rule changes.

## Known Hallucination Traps
- `ghcr.io/devcontainers/features/apt:1` DOES NOT EXIST. The official devcontainers/features registry has no apt installer feature. Real apt features are from rocker-org and devcontainers-extra. See `.claude/rules/devcontainer.md` for correct identifiers.
- General rule: always verify devcontainer feature identifiers against https://containers.dev/features before referencing them in rules or configs.
