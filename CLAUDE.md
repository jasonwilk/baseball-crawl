# baseball-crawl

## Core Principle

**Simple first. Complexity as needed.**

Every decision in this project -- code, architecture, agent design, process -- starts with the simplest thing that works. Complexity is added only when a real problem demands it, not in anticipation of problems that might never arrive.

What this means in practice:
- Build the smallest working thing, then iterate
- Do not design for scale, generality, or future needs until those needs are real
- One file is better than a framework. A script is better than a pipeline. A dict is better than a class -- until it isn't.
- When in doubt, leave it out. You can always add; removing is harder.

## Project Purpose

Coaching analytics platform for **Lincoln Standing Bear High School** baseball program. Extracts data from GameChanger, builds a queryable database for scouting and game preparation, and (later) publishes dashboards for coaching staff.

**The core value proposition**: Give LSB coaches a competitive advantage through data-driven scouting, lineup optimization, and opponent analysis -- capabilities that most high school programs do not have.

### Scope
- **Teams**: LSB Freshman, JV, Varsity, Reserve. Legion teams added later.
- **Roster size**: 12-15 players per team
- **Season**: ~30 games per team
- **Multi-season**: Players tracked across LSB HS, Legion, and travel ball over time
- **Data sources**: GameChanger API (primary), potentially others later
- **Users**: Jason (system operator), coaching staff (dashboard consumers)

### MVP Target
A queryable database containing team and opponent statistics, sufficient for scouting reports and game prep. Dashboards come after the data layer is solid.

### Deployment Target
- **Cloudflare**: D1 (SQLite database), Workers (API/ETL), Pages (dashboards when ready), KV/R2 (caching/raw storage as needed)

## Data Philosophy

**We automate what a coach could do by hand.**

Every piece of data this project gathers is information already visible to any GameChanger user through the normal UI. This project does not access hidden data, reverse-engineer proprietary analytics, or perform novel data mining. It scales the manual work of opening box scores, copying stats into a spreadsheet, and comparing them across games and seasons.

This guides our data-source decisions:
- **GameChanger API** (preferred): Programmatic access to the same data shown in the app.
- **Web scraping** (fallback): Screen-scrape when the API does not cover a data point, but only for data already visible in the UI.

## Tech Stack
- Python (version governed by `.python-version` -- Dockerfile, devcontainer.json, and pyproject.toml must stay in sync with it) for data extraction and processing scripts
- Cloudflare D1 (SQLite) for structured data storage
- Cloudflare Workers for API endpoints and scheduled jobs
- TypeScript/JavaScript for Workers and Pages (when dashboard phase begins)

## Python Version Policy

- **Source of truth**: `.python-version` (pyenv). All other locations must match it.
- **Also specified in**: `pyproject.toml` (`requires-python`), `Dockerfile` (`FROM` tag), `.devcontainer/devcontainer.json` (Python feature version).
- **Current version**: 3.13 -- chosen over 3.14 (httpx/jinja2 lack official 3.14 support markers) and over 3.12 (all deps support 3.13, extending the EOL window).

**When to consider upgrading:**
- Annually, when a new stable Python release has been out 6+ months and key dependencies support it.
- Immediately, when a dependency drops support for the current version.

**How to verify before upgrading:**
- Check dep compatibility at pyreadiness.org or via per-package PyPI classifiers.
- Run `pip install -r requirements.txt` on the new version.
- Run `pytest` and confirm no failures.
- Check for deprecation warnings in test output.

**When you update the version**, change it in all four locations atomically and reference the story in the commit.

## Key Metrics We Track
These are the statistics and dimensions that matter for coaching decisions:
- **Batting**: OBP, strikeout rate, home/away splits, left/right pitcher splits
- **Pitching**: K/9, BB/9, left/right batter splits, home/away splits
- **Players**: Key player identification (aces, closers, leadoff), lineup position history
- **Opponents**: Lineup patterns and changes, tendencies, roster composition
- **Longitudinal**: Player development across seasons, teams, and levels

## GameChanger API
- Credentials have short lifespans -- rotation is frequent
- NEVER log, commit, display, or hardcode credentials in source code
- The API is undocumented; we maintain our own spec at `docs/gamechanger-api.md`
- API limitations are discovered iteratively -- document everything
- All API interactions must handle auth expiration gracefully

## Commands
- `./scripts/install-hooks.sh` -- one-time setup for PII pre-commit hook (run after cloning)

## Code Style
- Use type hints for all function signatures
- Write docstrings for public functions and classes
- Prefer dataclasses or Pydantic models for structured data
- Use pathlib for file paths, not os.path
- Use logging module, not print statements, for operational output

## Architecture
- Keep data extraction separate from analysis/processing
- Use a clear directory structure: `src/` for source, `tests/` for tests, `data/` for local dev outputs, `docs/` for API specs and documentation
- Extraction should be idempotent -- re-running should not duplicate data
- All HTTP requests should include proper error handling, retries, and rate limiting
- Store raw API responses before transforming (raw -> processed pipeline)
- Credential management: environment variables for local dev, Cloudflare secrets for production

## Security Rules
- IMPORTANT: Credentials and tokens MUST NEVER appear in code, logs, commit history, or agent output
- Use `.env` files locally (always in `.gitignore`)
- Use Cloudflare secrets/environment variables for production
- When agents work with API responses, strip or redact auth headers before storing raw responses
- Treat GameChanger session tokens as sensitive data at all times

## HTTP Request Discipline

All HTTP requests to GameChanger -- whether API calls or web scraping -- must present as a normal user on a real browser. We are automating legitimate user work, and our traffic should honestly reflect that.

### Headers & Identity
- Use a realistic `User-Agent` string (e.g., Chrome or Firefox on macOS/Windows). Never send `python-requests/x.x.x`, `httpx`, or similar library defaults.
- Include standard browser headers: `Accept`, `Accept-Language`, `Accept-Encoding`, `Referer`/`Origin` where appropriate.
- Store the canonical header set in a shared module so all HTTP code uses the same defaults.

### Session Behavior
- Maintain cookie jars across requests within a session. Do not start a fresh cookieless request mid-flow.
- Reuse the same `User-Agent` and header profile for the duration of a session -- do not randomize per-request.
- Handle redirects and set-cookie responses the way a browser would.

### Rate Limiting & Timing
- Respect any `Retry-After` or rate-limit headers.
- Add reasonable delays between sequential requests (start with 1-2 seconds; tune based on observed behavior).
- Do not make parallel/concurrent requests to the same endpoint unless confirmed safe.
- Back off exponentially on errors (4xx/5xx), not just retries.

### Pattern Hygiene
- Vary request timing slightly (jitter) rather than hitting endpoints at exact intervals.
- Access resources in a human-plausible order (e.g., list page before detail page).
- Do not request the same resource repeatedly in a tight loop.

### Implementation Notes
- These rules apply to both `requests`/`httpx` API calls and any future `playwright`/`selenium` scraping.
- When writing tests, mock at the HTTP layer so tests do not depend on header correctness -- but integration/smoke tests should verify the real header profile.

## Testing
- Write tests for data parsing and transformation logic
- Use pytest as the test runner
- Mock HTTP requests in tests -- never make real network calls in test suite

## Project Management

This project uses a structured epic/story system managed by the **product-manager** agent.

### Key Directories
- `/epics/` -- Active epics and their stories (each epic in its own `E-NNN-slug/` folder)
- `/.project/archive/` -- Completed and abandoned epics (moved here from `/epics/`)
- `/.project/ideas/` -- Pre-epic ideas and future directions (see below)
- `/.project/research/` -- Standalone research, POCs, and query artifacts
- `/.project/templates/` -- Canonical templates for epics, stories, and research spikes
- `/docs/` -- API specifications, architecture docs, domain reference

### Numbering Scheme
- Epics: `E-NNN` (e.g., E-001, E-002)
- Stories: `E-NNN-SS` (e.g., E-001-01, E-001-02)
- Research spikes: `E-NNN-R-SS` (e.g., E-001-R-01)

### Ideas vs. Epics: The Core Distinction

**Ideas** (`/.project/ideas/`) are lightweight captures for directions, problems, or plans that are not yet ready to be structured as epics. An idea has no stories, no acceptance criteria, and no assignees. It just holds the thought until the time is right.

**Epics** (`/epics/`) are structured work with clear scope, stories, and testable acceptance criteria. An epic is ready when an agent could pick it up and execute without guessing.

**The rule:** If you cannot write real acceptance criteria, it is not an epic yet. Capture it as an idea.

**Promotion triggers** (any one is sufficient):
- A blocking dependency clears
- The project hits the pain the idea addresses
- A strategic decision makes it the next priority

**Review cadence:** The product-manager reviews `/.project/ideas/README.md` every time an epic completes, and every 90 days. Each idea file contains a "Review by" date.

**Adding an idea:** Copy `/.project/templates/idea-template.md`, name it `IDEA-NNN-short-slug.md`, fill in all sections, add a row to `/.project/ideas/README.md`, and update the numbering state in `/.claude/agent-memory/product-manager/MEMORY.md`.

### Epic Workflow
`DRAFT` -> `READY` -> `ACTIVE` -> `COMPLETED` (or `BLOCKED` / `ABANDONED`)

Stories can only be dispatched when the parent epic is `READY` or `ACTIVE`. PM sets the epic to `READY` explicitly after completing refinement (expert consultation done, all stories have testable ACs).

### Story Workflow
`TODO` -> `IN_PROGRESS` -> `DONE` (or `BLOCKED` / `ABANDONED`)

### IMPORTANT: Before Starting Work on a Story
- Read the story file completely, including all acceptance criteria
- Check the parent epic for context and technical notes
- Verify no file conflicts with other in-progress stories
- Update story status to `IN_PROGRESS` before beginning
- Update story status to `DONE` when all acceptance criteria are met

## Workflow
- Use Plan Mode (Shift+Tab twice) before complex multi-file changes
- Run tests after making changes to data processing logic
- Use /clear between unrelated tasks to keep context clean
- When executing a story, reference the story ID in commit messages (e.g., `feat(E-001-02): add statcast parser`)

## Git Conventions
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Write descriptive commit messages explaining the "why"
- Keep PRs focused on a single concern
- Reference story IDs in commit messages when working on stories
- After committing, verify the `[pii-scan]` confirmation appears in the output -- if it is missing, the safety scan may not have run; investigate before proceeding

## Agent Ecosystem

This project uses specialized agents coordinated by an orchestrator:

| Agent | Role |
|-------|------|
| **orchestrator** | Smart router with file-reading capability -- reads project state (epic status, story files) before making routing decisions |
| **claude-architect** | Designs and manages agents, CLAUDE.md, rules, skills |
| **product-manager** | Product Manager -- owns what to build, why, and in what order. Discovers requirements, plans epics, delegates implementation to specialists. |
| **baseball-coach** | Domain expert -- translates coaching needs into technical requirements |
| **api-scout** | Explores GameChanger API, maintains API spec, manages credential patterns |
| **data-engineer** | Database schema design, ETL pipelines, SQLite architecture |
| **general-dev** | Python implementation, testing, general coding work |

### How Agents Collaborate
- **orchestrator** reads project state (epic status, story files) to make informed routing decisions, then delegates to the correct agent
- **baseball-coach** produces domain requirements that inform stories and data models
- **api-scout** maintains `docs/gamechanger-api.md` -- the single source of truth for API knowledge
- **data-engineer** designs schemas informed by both baseball-coach requirements and api-scout discoveries
- **general-dev** implements stories, referencing specs produced by other agents
- **product-manager** discovers requirements, consults domain experts, writes epics and stories, dispatches implementation work, and closes completed work
- Any agent that identifies future work should flag it to the PM for idea capture rather than creating speculative epics

### Workflow Contract

All routed work follows this contract:

1. **Orchestrator routes to PM.** All work-initiation requests go to product-manager first.
2. **PM consults experts during formation.** Before writing stories, PM consults domain experts as needed. When not required, PM notes the reason.
3. **PM marks the epic `READY` when refinement is complete.** `DRAFT` epics are not dispatchable.
4. **"Ready for dev" = `Status: TODO` in a `READY` epic.** No story file means no implementation work begins.
5. **PM dispatches via Agent Teams.** PM joins every dispatch team as the standing coordinator -- managing story statuses, verifying acceptance criteria, and dispatching newly unblocked stories as predecessors complete. See `/.claude/rules/dispatch-pattern.md`.
6. **Implementing agents require a story reference.** Must receive a story file path or story ID before beginning any task.

**Enforcement Boundary**: The user always retains override authority to invoke any agent directly; this contract governs the normal orchestrated path.

**Direct-Routing Exceptions**: `api-scout`, `baseball-coach`, `claude-architect` may be invoked directly without PM intermediation.

## Statusline

A custom statusline is configured in `.claude/settings.json` and displayed at the bottom of the Claude Code terminal during sessions. It shows:
- Model name, current directory, and git branch
- Color-coded context window usage bar (green < 70%, yellow 70-89%, red 90%+)
- Session cost and elapsed time

Script location: `.claude/hooks/statusline.sh`
Documentation: `.claude/hooks/README.md`
Dependencies: `bash`, `jq`, `git` (optional, for branch display)
