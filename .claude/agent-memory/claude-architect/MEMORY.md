# Claude Architect -- Agent Memory

## Core Principle: Simple First, Complexity as Needed
IMPORTANT -- This is the governing design principle for the entire project.
- Build the smallest working thing, then iterate
- Do NOT pre-create agents, infrastructure, or abstractions before they are needed
- One file > framework, script > pipeline, dict > class (until it isn't)
- When in doubt, leave it out
- CRITICAL LESSON: The principle guides FUTURE decisions. It does NOT justify deleting existing working context, architectural details, or agent configs. Existing documentation has value.

## Project: baseball-crawl
- Project root: `/Users/jason/Documents/code/baseball-crawl/`
- Purpose: Coaching analytics for Lincoln Standing Bear HS baseball (GameChanger data)
- Teams: Freshman, JV, Varsity, Reserve (Legion later)
- Users: Jason (operator), coaching staff (consumers)
- MVP: queryable database for scouting/game prep; dashboards come later
- State: Active development -- src/http/ module exists (headers, session factory), multiple epics completed

## Agent Ecosystem (Current)
All seven agents in `.claude/agents/`:
- **orchestrator** (sonnet, cyan): Smart router with file-reading. Read/Glob/Grep/Task tools. No memory.
- **claude-architect** (opus, yellow): Meta-agent. Designs/manages agents, CLAUDE.md, rules.
- **product-manager** (opus, green): Product Manager. Epics, stories, dispatch via Agent Teams. No code.
- **baseball-coach** (sonnet, red): Domain expert. Coaching needs -> technical requirements.
- **api-scout** (sonnet, orange): GameChanger API exploration, documentation, credential patterns.
- **data-engineer** (sonnet, blue): Database schema, SQL migrations, ETL pipelines, query optimization.
- **general-dev** (sonnet, blue): Python implementation. Crawlers, parsers, loaders, utilities, tests.

### When to Create New Agents
Only when a user request requires specialized capability that existing agents cannot handle AND the work is recurring. When created, MUST update orchestrator routing.

## Key Architectural Decisions
- PII safety system: two-layer defense (Git pre-commit hook + Claude Code PreToolUse hook)
  - Design doc: `/.project/research/E-006-precommit-design.md`
  - Git hook: `.githooks/pre-commit` with `core.hooksPath` (not pre-commit framework)
  - Claude Code hook: `.claude/hooks/pii-check.sh` (PreToolUse, Bash matcher)
  - Scanner: `src/safety/pii_scanner.py` (stdlib only, shared by both hooks)
  - No agent/skill created for scanning (deterministic check, not reasoning)
- Orchestrator lists all agents that have .md files
- Product-manager has full template content inline (comprehensive operational manual)
- Tech stack: Python end-to-end. FastAPI+Jinja2 serving layer. Docker Compose + Cloudflare Tunnel. SQLite (WAL mode + Litestream). Hetzner CX11 VPS. Decision finalized in E-009.
- CLAUDE.md has Core Principle section at top, followed by full project context
- Ideas workflow in `/.project/ideas/` for pre-epic tracking (IDEA-NNN numbering)
- Ideas rule: if acceptance criteria cannot be written, it is not an epic -- capture as idea
- Ideas are reviewed on every epic completion (mandatory) and every 90 days
- Ideas workflow encoded in five places:
  - `CLAUDE.md` (Ideas Workflow subsection under Project Management)
  - `.claude/rules/ideas-workflow.md` (scoped rule, paths: .project/ideas/**)
  - `.claude/agents/product-manager.md` (Ideas Workflow section + System of Work flow)
  - `.claude/agent-memory/product-manager/MEMORY.md` (idea numbering state)
  - `.claude/agents/orchestrator.md` (routing examples for idea capture intent)
- Orchestrator routes "capture for later" / "someday" / "idea" intent to PM
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

## Known Hallucination Traps
- `ghcr.io/devcontainers/features/apt:1` DOES NOT EXIST. The official devcontainers/features registry has no apt installer feature. Real apt features are from rocker-org and devcontainers-extra. See `.claude/rules/devcontainer.md` for correct identifiers.
- General rule: always verify devcontainer feature identifiers against https://containers.dev/features before referencing them in rules or configs.
