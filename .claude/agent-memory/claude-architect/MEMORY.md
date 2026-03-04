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

## Ingest-Endpoint Workflow Executions (continued 5)
- **opponents** (2026-03-04): Eighth context integration. NEW endpoint (`GET /teams/{team_id}/opponents`), opponent registry with pagination. Phase 2 updates: data-engineer memory (three-UUID distinction -- root_team_id is local-only vs progenitor_team_id is canonical, is_hidden filtering, batch scouting enumeration use case, raw sample path), general-dev memory (raw sample path added to inventory, three UUID semantics, pagination same as game-summaries, gc-user-action and Accept header, batch scouting workflow), baseball-coach memory (complete opponent catalog in one call, is_hidden for data quality, updated scouting pipeline with opponents as step 1 replacing game-by-game schedule crawl). No CLAUDE.md changes (existing Opponents bullet under Key Metrics already covers opponent scouting at the right abstraction level). No stat glossary changes (structural data, no stat abbreviations). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 6)
- **public-team-games** (2026-03-04): Ninth context integration. NEW endpoint (`GET /public/teams/{public_id}/games`), second confirmed unauthenticated endpoint. Phase 2 updates: data-engineer memory (no-auth game results with scores directly embedded, id join key to authenticated data, absent-vs-null avatar_url behavior, date format difference from authenticated schedule, schema impact assessment), general-dev memory (raw sample path added to inventory, no-auth client note, avatar_url absent-not-null pattern, Accept header, date format difference, id join key), baseball-coach memory (passive opponent scouting with zero credential cost, home/away patterns, film review candidates via has_videos_available, win/loss margin analysis, passive scouting pipeline steps), CLAUDE.md GameChanger API section (updated public endpoints bullet from "First confirmed" to "Two confirmed", added games endpoint description). No stat glossary changes (score/status fields are structural, not stat abbreviations). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 7)
- **me-user** (2026-03-04): Tenth context integration. NEW endpoint (`GET /me/user`), authenticated user profile with subscription info. PII endpoint (email, name, UUID) -- no coaching or schema relevance. Two implementation uses: token validity check (200=valid, 401=expired) and user UUID retrieval. Phase 2 updates: general-dev memory (raw sample path added to data/raw inventory, token health check pattern with Accept header and pre-flight use case). No data-engineer memory changes (no schema/ETL impact). No baseball-coach memory changes (no coaching relevance). No CLAUDE.md changes (existing authenticated endpoints bullet already covers `/me/*` at the right abstraction level). No stat glossary changes (user profile data, not stats). No agent definition or rule changes. Lightest-touch integration to date -- only one agent memory needed updating.

## Ingest-Endpoint Workflow Executions (continued 8)
- **public-team-games-preview** (2026-03-04): Eleventh context integration. NEW endpoint (`GET /public/teams/{public_id}/games/preview`), third confirmed unauthenticated endpoint. Near-duplicate of `/games` -- same 32 records, same order, only 2 differences: `event_id` instead of `id`, and `has_videos_available` absent. Low-impact integration. Phase 2 updates: general-dev memory (raw sample path added to data/raw inventory with note to prefer `/games` sample), CLAUDE.md GameChanger API section (updated public endpoints count from "Two confirmed" to "Three confirmed", added brief games/preview description with prefer-`/games` guidance). No data-engineer memory changes (no new schema implications -- subset of `/games`). No baseball-coach memory changes (no coaching relevance beyond what `/games` already provides). No stat glossary changes. No agent definition or rule changes. Second-lightest-touch integration -- only two updates needed.

## Ingest-Endpoint Workflow Executions (continued 9)
- **boxscore** (2026-03-04): Twelfth context integration. NEW endpoint (`GET /game-stream-processing/{game_stream_id}/boxscore`), per-game box score for both teams. HIGH-IMPACT: unblocks E-002-03. Phase 2 updates: data-engineer memory (game_stream.id two-step pipeline, asymmetric key format detection, player names embedded for FK stub creation, sparse extras merge pattern, batting order from list index, IP integer interpretation warning, opponent data first-class, one-call-per-game count), general-dev memory (raw sample path added to data/raw inventory, asymmetric key detection pattern, sparse extras parsing, batting order from list order, is_primary substitute flag, player_text position/decision encoding, Accept header, no gc-user-action), baseball-coach memory (both-teams-in-one-call scouting, pitch count + strike count per pitcher, batting order and lineup tendencies, position history from player_text, pitcher decisions, errors by player, comparison with player-stats endpoint, pipeline dependency note), CLAUDE.md Key Metrics (added Box scores bullet between per-game splits and spray charts), stat glossary (added TS -- total strikes thrown -- to Pitching Standard table). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 10)
- **public-game-details** (2026-03-04): Thirteenth context integration. NEW endpoint (`GET /public/game-stream-processing/{game_stream_id}/details?include=line_scores`), fourth confirmed unauthenticated endpoint. Per-game inning-by-inning scoring (runs per inning array + R/H/E totals). Same `game_stream_id` as authenticated boxscore -- complementary views. Phase 2 updates: data-engineer memory (line_score conditional on include param, inning scores array variable length, R/H/E totals as positional 3-element array, complementary relationship with boxscore, no-auth pipeline expansion to four endpoints, storage recommendations -- JSON text for innings + named columns for R/H/E), general-dev memory (raw sample path added to data/raw inventory, line_score conditional on query param, totals positional array parsing, no-auth client note, complementary to boxscore via same game_stream_id), baseball-coach memory (inning-by-inning scoring patterns for opponent tendency analysis, late-inning tendencies, blowout vs close game detection, mercy rule detection from innings count, R/H/E error pattern scouting, updated passive scouting pipeline with game details as step 4, noted game_stream_id dependency on authenticated data), CLAUDE.md GameChanger API section (updated public endpoints count from "Three confirmed" to "Four confirmed", added game details description with line_scores param and boxscore complementarity note). No stat glossary changes (R/H/E and per-inning runs are structural scoring data, not stat abbreviations). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 11)
- **plays** (2026-03-04): Fourteenth context integration. NEW endpoint (`GET /game-stream-processing/{game_stream_id}/plays`), pitch-by-pitch play log for both teams. Same `game_stream_id` as boxscore and public game details. HIGH-IMPACT: most granular game data in the API (pitch sequences, contact quality, baserunner events, fielder identity, substitutions). Phase 2 updates: data-engineer memory (same two-step ID pipeline as boxscore, same asymmetric team key format, PlateAppearance entity alignment, pitch sequence as JSON text column recommendation, UUID template regex extraction, lineup change events inline, courtesy runner pattern, last-play anomaly with empty details, raw sample path), general-dev memory (raw sample path added to data/raw inventory and inline inventory, UUID template regex pattern, name_template nested access, contact quality regex extraction, lineup changes inline, courtesy runner vs pinch runner distinction, last-play edge case, Accept header, no gc-user-action), baseball-coach memory (pitch sequence per at-bat for approach analysis, contact quality classification, pitcher approach patterns, baserunner intelligence, fielder identity on outs, substitution tracking, comparison with boxscore and player-stats, pipeline dependency), CLAUDE.md Key Metrics (added pitch-by-pitch plays bullet). No stat glossary changes (narrative templates, not stat abbreviations). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 12)
- **players-roster** (2026-03-04): Fifteenth context integration. NEW endpoint path (`GET /teams/public/{public_id}/players`), roster listing with inverted URL pattern (`/teams/public/` instead of `/public/teams/`). Also backfilled schema for existing authenticated `GET /teams/{team_id}/players`. First LSB team data captured (JV Grizzlies, 20 players). Medium-impact: provides the player UUID list needed for per-player stat lookups (missing link between team identification and player-level data). Phase 2 updates: data-engineer memory (Player entity mapping, UUID as canonical FK, first_name initials pattern, jersey number string + duplicates, avatar_url empty string vs null normalization, URL pattern anomaly, auth requirement unclear, raw sample path), general-dev memory (raw sample path added to data/raw inventory and inline inventory, URL pattern warning for URL constructors, avatar_url empty string handling, Accept header, auth requirement unclear), baseball-coach memory (first LSB team data milestone, player UUID as missing link for scouting pipeline, roster size 20 vs expected 12-15, jersey number duplicates, first name initials, updated scouting pipeline with roster step confirmed), CLAUDE.md GameChanger API section (updated public endpoints bullet to note inverted URL pattern `/teams/public/` coexisting with `/public/teams/`, warning not to assume all public endpoints follow `/public/*`). No stat glossary changes (structural roster data, no stat abbreviations). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 13)
- **best-game-stream-id** (2026-03-04): Sixteenth context integration. NEW endpoint (`GET /events/{event_id}/best-game-stream-id`), routing/plumbing endpoint that bridges schedule `event_id` to `game_stream_id` for boxscore/plays access. Simplest response in the API (single field). Low-impact but architecturally significant: completes documentation of the two ID chains to game data. Accept version `0.0.2` (higher than typical `0.0.0`). Phase 2 updates: data-engineer memory (updated boxscore two-step pipeline to document both ID paths with guidance on when to use each), general-dev memory (raw sample path added to data/raw inventory, new endpoint section with Accept header, version note, bridge pattern, two-path guidance). No baseball-coach memory changes (routing/plumbing endpoint, no coaching-relevant data). No CLAUDE.md changes (authenticated endpoint fits existing description at the right abstraction level). No stat glossary changes (UUID response, no stat abbreviations). No agent definition or rule changes. Third-lightest-touch integration -- only two agent memories updated.

## Ingest-Endpoint Workflow Executions (continued 14)
- **team-users** (2026-03-04): Seventeenth context integration. NEW endpoint (`GET /teams/{team_id}/users`), team member listing with pagination. LOW-IMPACT: auth/admin plumbing with minimal coaching value. Bare JSON array of 5-field user records (id, status, first_name, last_name, email). No role field, no stats, most PII-dense endpoint. Status values "active" vs "active-confirmed" are the only distinguishing data. Phase 2 updates: general-dev memory (raw sample path added to data/raw inventory with "no coaching or schema value" note). No data-engineer memory changes (no schema entities, no ETL patterns). No baseball-coach memory changes (no coaching relevance). No CLAUDE.md changes (fits existing authenticated endpoints at the right abstraction level). No stat glossary changes (user profile data, not stats). No agent definition or rule changes. Lightest-touch integration tied with me-user -- only one agent memory updated.

## Ingest-Endpoint Workflow Executions (continued 15)
- **public-team-profile-id** (2026-03-04): Eighteenth context integration. NEW endpoint (`GET /teams/{team_id}/public-team-profile-id`), UUID-to-public_id bridge. Single-field response `{"id": "<slug>"}`. MEDIUM-IMPACT: architecturally significant as the missing link between authenticated API (UUIDs) and public API (`public_id` slugs). Enables programmatic public_id resolution for opponents -- without this, no way to get public_id for teams not in the user's `/me/teams` list. Opponent UUID behavior unverified (highest priority follow-up). Phase 2 updates: data-engineer memory (bridge pattern for two-tier ETL, Team entity public_id column, lightweight single-call pattern, opponent UUID follow-up, raw sample path), general-dev memory (raw sample path added to data/raw inventory, new endpoint section with Accept header, gc-user-action, bridge pattern, implementation note for opponent scouting pipeline, opponent UUID follow-up), baseball-coach memory (updated scouting pipeline with step 2a for public_id resolution, updated both passive scouting pipeline instances to reference bridge endpoint as primary public_id source, opponent UUID follow-up as highest priority), CLAUDE.md GameChanger API section (added UUID-to-public_id bridge note to authenticated endpoints bullet). No stat glossary changes (single UUID/slug field, no stat abbreviations). No agent definition or rule changes.

## Ingest-Endpoint Workflow Executions (continued 16)
- **auth-refresh** (2026-03-04): Nineteenth context integration. NEW endpoint (`POST /auth`), first POST endpoint, token refresh flow. HTTP 400 received (stale gc-signature, not expired token). HIGH-IMPACT on context layer: corrected a pervasive factual error (token lifetime is 14 DAYS, not 1 hour). Key discovery: `gc-signature` HMAC header blocks programmatic token refresh. Four new headers documented (gc-signature, gc-timestamp, gc-client-id, gc-app-version). JWT payload schema corrected. Phase 2 updates: CLAUDE.md GameChanger API section (corrected "Credentials have short lifespans -- rotation is frequent" to accurate 14-day lifetime, updated Workflows bullet to remove ~1-hour expiry reference), ingest-endpoint skill (corrected three references to ~1-hour credential lifetime -- now references gc-signature freshness as the time-sensitive constraint, not token expiry), data-engineer memory (new Token Lifetime and ETL Scheduling section -- 14-day window enables batch ingestion pipelines without mid-run expiry), general-dev memory (corrected JWT `userId` to `uid`, new Token Lifetime and Credential Management section with JWT fields, new headers, programmatic refresh status, batch pipeline impact, auth-refresh raw sample path). No baseball-coach memory changes (no coaching relevance). No stat glossary changes (auth endpoint, no stat abbreviations). No agent definition or rule changes.

## Known Hallucination Traps
- `ghcr.io/devcontainers/features/apt:1` DOES NOT EXIST. The official devcontainers/features registry has no apt installer feature. Real apt features are from rocker-org and devcontainers-extra. See `.claude/rules/devcontainer.md` for correct identifiers.
- General rule: always verify devcontainer feature identifiers against https://containers.dev/features before referencing them in rules or configs.
