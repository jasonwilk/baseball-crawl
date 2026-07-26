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
- Per-epic codification records: **see [epic-codifications.md](epic-codifications.md)** -- 27 epics, E-077 through E-276, one section each: what was codified, where it was placed, and why. That file is the record; this index deliberately does not restate it. (Collapsed 2026-07-26, layer pass D6: this bullet had reached 8,553 characters -- 42% of MEMORY.md -- duplicating its own topic file and tripping the read-limit hook. Before removal, its project-fact content was verified still present, in fuller form, in `.claude/rules/data-model.md` (the scored-but-empty MODAL case and the data-bearing-EXISTS rule), `canonical-seams.md` (the canonical helpers, and the same-population-is-necessary-but-not-sufficient invariant with its load-bearing temporal clause), `architecture-subsystems.md`, and CLAUDE.md (report generation and deletion are destructive).)
  - Two habits from that record that generalize past any single epic, kept here because they change how a codification pass is RUN: **a defect belongs where it BINDS** -- the rule an agent already has loaded at the moment it would make the mistake, not the rule nearest to where the defect was found; and **re-homing beats duplicating** -- at E-276 a lesson moved into a shared rule let software-engineer delete its longer local copy, so that promotion cost negative lines.
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
- `epic-codifications.md` -- Per-epic record of what was codified where (E-077, E-228, E-235..E-241, E-246..E-262, E-264, E-267, E-270, E-272, E-273)
- `claude-practices.md` -- CLAUDE.md design, context management
- `agent-design.md` -- Subagent architecture, ecosystem patterns
- `skills-and-hooks.md` -- Skills system, hooks patterns
- `semantic-layer.md` -- Intent routing, layering strategy
- `agent-blueprints.md` -- Historical blueprints for agents (data-engineer, software-engineer built via E-013; baseball-coach, api-scout for reference)
- `boundaries.md` -- Operational boundary catalog (host vs container, auth vs public, PII, hallucinated identifiers)
- `ingest-workflow-log.md` -- Per-endpoint integration history from ingest-endpoint skill executions (19 endpoints, 2026-03-04)
- `codex-config.md` -- Codex CLI configuration, model, reasoning effort, available models
- `model-behavior-reference.md` -- Four-tier placement architecture, verification taxonomy, per-model adapters (4.8/Opus 5/Sonnet 5/Fable 5), dated alias-to-model register. Consult BEFORE any placement or agent-definition call.

## Claude Code Platform Facts
- CLAUDE.md loaded every session; keep concise
- First 200 lines of MEMORY.md auto-loaded into system prompt
- Hooks: deterministic; CLAUDE.md: advisory
- Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). In practice only the main session spawns subagents -- but because no agent definition GRANTS the `Agent` tool, not because nesting is impossible. Nesting works (verified 2026-07-26, 2.1.220: a subagent produced four `spawnDepth: 1` children).
- Flag gates the team-coordination surface: without `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, the team-coordination tools (`SendMessage` + the shared `Task*` task list) are unavailable and spawned agents are one-shot
- `TeamCreate`/`TeamDelete` were removed in Claude Code v2.1.178 (recorded 2026-06-29) -- team formation is now implicit and teardown automatic; no explicit create/delete calls exist
- `Agent` (Task tool): granted only to the main session today; spawns a named subagent. Subagents are long-lived and resumable -- re-engage via `SendMessage` with context intact. Use for epic/story dispatch.
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
- **A read disagreeing with disk has TWO causes and the alarming one is over-diagnosed.** "The transport garbled it" and "the file moved under a live writer" produce IDENTICAL evidence (second read disagrees; grep for the remembered text finds nothing) — the discriminators are the harness "modified on disk" note, `stat` mtime vs. read time, and the other writer's `~/.claude/projects/<slug>/<session>/subagents/*.jsonl` payloads. `.claude/rules/tool-output-integrity.md` carried only the garble etiology until 2026-07-25, when a re-adjudication of its own E-267 anchor anecdote showed that case was a concurrent writer (mutation-testing mutant on disk), not a garble. Garble is real and kept; the anchor for it is `.project/research/E-231-harness-repro/harness-output-reliability-report.md`. Full record: `epic-codifications.md` E-267 T3 re-adjudication. The same 2026-07-25 pass added ONE paragraph ("A handoff artifact is a claim with a timestamp") for the agent-actionable half of the root cause and DELIBERATELY declined a new session-lifecycle rule: only the operator opens a second session or seeds a successor, so a rule addressed to agents cannot bind it. If it recurs, extend `dispatch-pattern.md` (which already carries the advisory concurrency note) rather than creating a surface.
- **`pitch-rules.md`'s NRBL/LEGION separate-constant rationale is DELIBERATE and stated at line 134** ("a future Legion-only change must not silently move NRBL, nor an NRBL-only change move Legion"), mirroring the `PITCH_SMART_15_18` note at line 180; line 136's nrbl.net cite is a THIRD, separate point. Do not collapse the two constants in a sweep, and do not accept a summary of this passage — on 2026-07-25 it was misstated three times in one afternoon (a true claim retracted, then the retraction "corrected" into a second false claim), with the underlying verdict staying right at every step, so no verdict-level check caught it. That shape is codified in `.claude/rules/tool-output-integrity.md` under "A claim you RELAY is a claim you AUTHOR".
- `ghcr.io/devcontainers/features/apt:1` DOES NOT EXIST. The official devcontainers/features registry has no apt installer feature. Real apt features are from rocker-org and devcontainers-extra. See `.claude/rules/devcontainer.md` for correct identifiers.
- General rule: always verify devcontainer feature identifiers against https://containers.dev/features before referencing them in rules or configs.
