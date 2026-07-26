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

Coaching analytics platform for GameChanger-scored baseball. Extracts data from GameChanger, builds a queryable database for scouting and game preparation, and generates shareable scouting reports for coaching staff. **Lincoln Standing Bear High School** (Freshman, JV, Varsity, Reserve) is the operator's own program and the proving ground, but the report tool serves any team scored on GameChanger, addressed by its `public_id` -- Legion summer ball, USSSA youth, and travel programs included. See `docs/VISION.md` ("Scope and Scale").

**The core value proposition**: Give coaches a competitive advantage through data-driven scouting, lineup optimization, and opponent analysis -- capabilities that most programs at this level do not have.

> **Current strategic frame (2026-06-12)**: The product as actually used is reports-first -- generate a one-off scouting report for a GameChanger `public_id` and share the link. The member-team sync, dashboard, and tracked-opponent surfaces were unused and have been **removed** (E-239, the `docs/ROADMAP.md` D2 slice). The forward feature is morning-of-game scheduled reports. Explicit non-goals: cross-team player identity, multi-season rollups, longitudinal tracking. See `docs/ROADMAP.md` for the full reframe, protected core, and epic sequence (A-E). As of the 2026-07-05 "curate the vision" session, `docs/VISION.md` has been reconciled to this reports-first reframe, so `docs/VISION.md` and `docs/ROADMAP.md` now agree on scope (reports-first, single-season, morning-of-game). The Project Purpose / Scope sections below were reconciled to this reports-first frame in E-255 (CE-5), and their remaining LSB-only scope claim was reconciled to `docs/VISION.md`'s any-team reach on 2026-07-25 -- do not narrow it back.

### Scope
- **Teams**: LSB Freshman, JV, Varsity, Reserve are the operator's own program. **Any GameChanger team can be scouted by `public_id`, at any level** -- high school, Legion, USSSA/travel youth. A 14U or 9U team in the database is a legitimate user's team, not import noise: the operator supports coaches outside the high-school program, and reasoning "LSB is a high school program, so a youth-age team must be junk" has already nearly discarded 84 real teams (2026-07-25).
- **Roster size**: 12-15 players per team
- **Season**: ~30 games per team
- **Single-season scope**: Each team-season is tracked independently. There is no multi-season rollup, longitudinal cross-season tracking, or cross-team athlete identity (explicit non-goals). **Multi-program breadth does NOT license multi-season depth**: serving any team means the tool works for any team's *current* season, one report at a time -- never blending programs, tracking a team across seasons, or rebuilding the machinery E-239 deleted. Breadth and depth are different things; we pursue the breadth and deliberately decline the depth. See `docs/VISION.md` ("Explicit Non-Goals")
- **Data sources**: GameChanger API (primary), potentially others later
- **Users**: Jason (system operator), coaching staff (report consumers)

### MVP Target
A queryable database containing team and opponent statistics, sufficient for scouting reports and game prep. Shareable scouting reports are generated on top of that data layer.

### Deployment Target
- **Local dev**: `docker compose up` starts the full stack at http://baseball.localhost:8001 (the canonical user-facing URL -- matches APP_URL / the WebAuthn origin; `baseball.localhost` resolves to 127.0.0.1). Direct in-container access (curl, health checks) uses http://localhost:8001, the same app port with a `localhost` Host header.
- **Production**: Docker Compose on a Linux server (home server or any machine with Docker)
- **Production URL**: `https://bbstats.ai`
- **Network**: Cloudflare Tunnel for ingress (no exposed ports). App-internal auth via magic links and passkeys (E-023). Cloudflare Access is present but passive (no enforcing policies).
- **Database**: SQLite at `./data/app.db` (host-mounted, WAL mode, simple file backup via `scripts/backup_db.py`)
- See `docs/admin/production-deployment.md` for the verified deployment runbook

## Data Philosophy

**We automate what a coach could do by hand.**

Every piece of data this project gathers is information already visible to any GameChanger user through the normal UI. This project does not access hidden data, reverse-engineer proprietary analytics, or perform novel data mining. It scales the manual work of opening box scores, copying stats into a spreadsheet, and comparing them across games.

This guides our data-source decisions:
- **GameChanger API** (preferred): Programmatic access to the same data shown in the app.
- **Web scraping** (fallback): Screen-scrape when the API does not cover a data point, but only for data already visible in the UI.
- **Freshness for coaches**: Coaches think in games, not sync timestamps. Data freshness should be presented as game coverage ("Through [date] ([N] games)"), not system sync dates ("Updated Mar 27"). This applies to reports, cards, and any UI showing how current the data is.

### Operating Principle: Always Get Closer to Byte-Identical Play Ingestion

**Every change to play ingestion moves plays-derived stats closer to GameChanger's official box scores -- never further.** When we derive a stat from play-by-play and call it the same stat GameChanger reports, the burden is on us to prove it reconciles, and to keep proving it as the parser and data sources evolve. This binds all play-ingestion, parser, and reconciliation work: a change that improves one stat's fidelity at the cost of regressing another is not acceptable; the standing direction is the whole-season plays-to-boxscore gap trending toward zero.

This is a direction and a discipline, not a one-time threshold -- quick-scored games, abandoned at-bats, and scorekeeper noise leave an irreducible residual, so a perfect zero is not the bar. See the canonical statement in `docs/VISION.md` ("North Star: Always Get Closer to Byte-Identical Play Ingestion"). `bb report reconcile-scoreboard` (see Commands) is the standing plays-vs-boxscore measurement: run it before and after an ingestion change and compare the two readings. It is a DIAGNOSTIC, not a gate -- the one-way ratchet against a committed baseline was retired 2026-07-26 on the operator's decision that it cost more attention than it returned. So this principle binds as direction and judgment, never mechanically: a change that improves one stat at another's expense is still unacceptable, and it is the author's job to show the readings support the change.

## Tech Stack
- Python end-to-end (version governed by `.python-version` -- Dockerfile, devcontainer.json, and pyproject.toml must stay in sync with it) -- crawlers, API, serving layer, migrations, and tests
- FastAPI + Jinja2 for the serving layer (server-rendered HTML)
- SQLite (WAL mode, host-mounted Docker volume at `./data/app.db`) for structured storage
- Docker Compose for local development and production deployment
- Cloudflare Tunnel for network ingress; app-internal authentication (magic links + passkeys)
- **Dependency management**: pip-tools (`*.in` → `*.txt`). See `.claude/rules/dependency-management.md` for workflow, file layout, and Python version policy.

## Key Metrics

See `.claude/rules/key-metrics.md` for stat definitions, coaching priorities, and the data dictionary reference.

## GameChanger API

The API is undocumented; we maintain our own spec at `docs/api/README.md` (index) with per-endpoint files in `docs/api/endpoints/` and flows in `docs/api/flows/`. Limitations are discovered iteratively -- document everything you learn there, not here.

- **Auth**: three-token architecture (client, access, refresh) with programmatic refresh and login fallback. **NEVER log, commit, display, or hardcode credentials.** Implementation constraints in `.claude/rules/auth-module.md`; full architecture in `docs/api/auth.md`.
- **Authenticated endpoints** (`/teams/*`, `/me/*`) need `gc-token` + `gc-device-id` and must handle expiration gracefully. **Public endpoints need neither header.**
- **Gotcha -- the public URL pattern is not uniform.** Most public endpoints are `/public/teams/{public_id}`, but the roster is `GET /teams/public/{public_id}/players` -- inverted. Do not assume a shape; check the endpoint doc.
- **Gotcha -- public game ids are perspective-specific.** The same real-world game gets a different `id` depending on which team's schedule you queried, so diffing stored ids against a fetched array reports false removals unless you perspective-control first (E-270: 22 of 22 apparent removals were cross-perspective twins). Authenticated `game-summaries` returns a stable `event_id` instead. Retention, status-stability and truncation behavior are documented in `docs/api/endpoints/get-public-teams-public_id-games.md`.
- **Gotcha -- `root_team_id` is a different namespace from `gc_uuid`.** NEVER store one in the other's column. Presence of `progenitor_team_id` means the coach linked the opponent via team lookup (a reliable single-season dedup signal); absence means they typed it by hand.
- **`public_id` to `gc_uuid`**: resolve via `POST /search` filtered by `public_id` -- see `.claude/rules/gc-uuid-bridge.md` for the pattern, storage rules, and the punctuation/apostrophe quirks.
- **HTTP discipline**: every request presents as a normal browser user. See `.claude/rules/http-discipline.md`.

## Commands

`bb` is the operator CLI and the primary interface; `bb --help` lists everything. Command groups: `bb status`, `bb creds`, `bb data`, `bb proxy`, `bb db`, `bb report`. **Per-command behavior, flags, exit codes, and operator procedures live in `docs/admin/operations.md`**, which carries a section per command and is the current source wherever it disagrees with a CLI docstring.

Two destructive-action boundaries worth knowing before running anything:

- **`bb report generate` is not read-only** -- it hard-deletes (see Architecture below). There is no "just look at the data" invocation of it.
- **`bb db purge-scouting` wipes all 20 scouting/report tables**, preserving only the 7 identity/auth/bootstrap tables, so logins survive but team-access grants do not and must be re-granted by an admin. `--force` (override the production refusal) and `--yes` (skip the prompt) are SEPARATE flags -- a scripted production purge needs both, and an unrecognized `APP_ENV` refuses outright since an ambiguous posture is not waved through by any flag.

## Workflows
- **Plan**: When the user says "plan an epic for X" (or similar -- "plan E-NNN", "create an epic for X", "write stories for X", "let's plan X", "design an epic for X"), load `.claude/skills/plan/SKILL.md` and follow its workflow. The main session suggests a planning team based on domain signals, spawns PM and domain experts, guides through discovery, planning, automatic spec review, refinement, and READY gate. Supports a "plan and dispatch" compound modifier to chain into the implement skill after READY.
- **Implement**: When the user says "implement E-NNN" (or similar -- "start epic", "execute E-NNN", "dispatch E-NNN", "kick off E-NNN"), load `.claude/skills/implement/SKILL.md` and follow its workflow. The main session reads the epic for team composition and spawns implementers, code-reviewer, and PM. Supports an "and review" modifier to chain a code review after implementation completes.
- **Ingest endpoint**: When the user says "ingest endpoint" (or similar -- "curl is ready", "new endpoint to analyze"), load `.claude/skills/ingest-endpoint/SKILL.md` and follow its two-phase workflow. The user has placed a curl command in `secrets/gamechanger-curl.txt` and expects api-scout to execute it (time-sensitive -- the `gc-signature` header in POST requests expires within minutes, and curl commands should be executed promptly regardless of token lifetime), then claude-architect to integrate findings into the context layer.
- **Spec review**: When the user says "spec review" (or similar -- "spec review E-NNN", "codex spec review", "spec review prompt", "codex spec review prompt"), load `.claude/skills/codex-spec-review/SKILL.md` and follow its workflow. Supports two execution paths: headless (default -- runs Codex via script, presents findings, offers advisory triage) and prompt generation (trigger phrase contains "prompt" -- assembles lean prompt for copy-paste).
- **Code review**: When the user says "codex review" (or similar -- "review with codex", "code review", "review epic", "codex review prompt", "code review prompt", "post-dev review"), load `.claude/skills/codex-review/SKILL.md` and follow its workflow. Supports two execution paths: headless (default -- runs Codex via script, presents findings, offers advisory triage) and prompt generation (trigger phrase contains "prompt" -- assembles lean prompt for copy-paste).
- **Curate the vision**: When the user says "curate the vision", invoke the product-manager in curate mode. PM reviews accumulated signals in `docs/vision-signals.md` with the user, discusses which belong in `docs/VISION.md`, updates the vision document, and clears processed signals.
- **Workflow help**: When the user says "/workflow-help" (or similar -- "what commands do I have", "show me the workflows", "cheat sheet"), load `.claude/skills/workflow-help/SKILL.md` and print the workflow cheat sheet.

## App Troubleshooting

After changing `src/`, `migrations/`, `Dockerfile`, `docker-compose.yml`, or `requirements.txt`, rebuild (`docker compose up -d --build app`) and verify the health check passes. See `.claude/rules/app-troubleshooting.md` for the full troubleshooting guide.

## Proxy Boundary (Host vs. Container)

**mitmproxy** runs on the Mac host (not in the devcontainer). Agents MUST NOT start, stop, or manage mitmproxy -- tell the user to run proxy commands on the Mac host. Agents CAN read proxy data in `proxy/data/` and credentials from `.env`. **Bright Data** runs inside the devcontainer as part of the normal HTTP session. See `.claude/rules/proxy-boundary.md` for full boundary rules, Bright Data configuration, and `docs/admin/mitmproxy-guide.md` for mitmproxy setup.

## Security Rules
- IMPORTANT: Credentials and tokens MUST NEVER appear in code, logs, commit history, or agent output
- Use `.env` files locally (always in `.gitignore`)
- Use environment variables via .env files for production (Docker Compose reads .env; files are git-ignored)
- When agents work with API responses, strip or redact auth headers before storing raw responses
- Treat GameChanger session tokens as sensitive data at all times
- **PII scanner**: `src/safety/pii_scanner.py` -- run manually with `python3 src/safety/pii_scanner.py --staged` (also supports `--stdin` and explicit file args). Scans credentials/email/phone (not names); `--staged` reads the staged blob and fails closed on an unreadable one. See `.claude/rules/pii-safety.md` for capabilities and the coverage footgun.
- **Doc-PII byte-gate**: `scripts/check_doc_pii.sh docs/api` greps a docs tree against a denylist of literal real identifiers (names, UUIDs, public_ids) that the pattern scanner cannot detect. Config/config.example split: the real denylist is the uncommitted, gitignored `secrets/pii-denylist.txt` (via `PII_DENYLIST_FILE`); the committed halves are the PII-free harness + the fake-sentinel `scripts/pii-denylist.example.txt`. Exit `0`=PASS, `1`=identifier present, `2`=INVALID, `3`=EXAMPLE MODE/INCONCLUSIVE. See `.claude/rules/pii-safety.md`.

## Architecture

Source in `src/`, tests in `tests/`, migrations in `migrations/`, local dev outputs in `data/`, docs in `docs/`. Extraction stays separate from analysis and is idempotent; all HTTP requests carry error handling, retries, and rate limiting. The scouting and reports pipelines crawl-to-load in memory with no disk intermediary, so there is no stored raw-response tier -- transformation happens in flight.

**The codebase funnels recurring operations through canonical seams** -- single entry points for DB-path resolution, SQLite connections, team and player upserts, deletions, team-name search, admin checks, production detection, timezone conversion, duplicate-game merges, reconcile-at-load, and orphan reclamation. Adding a second path to something that already has one is the recurring defect here: the copies drift, and the one nobody updated is the one that runs. Before writing any of these, read `.claude/rules/canonical-seams.md` -- it loads automatically when you touch `src/`, `tests/`, `migrations/`, `scripts/`, or `epics/`.

**Report generation is DESTRUCTIVE, which is the least obvious thing in this repo.** `generate_report()` runs two hard-deleting passes: reconcile-at-load can delete `games` and their entire child surface, and orphan reclamation can delete unreachable `teams` / `players` / `team_rosters`. Report deletion and `bb report cleanup` run the reclamation pass as well. Never treat generating a report as read-only, purely additive, or safe to re-run blindly against live data. Mechanics and grain contracts are in `.claude/rules/canonical-seams.md`.

Reports is the SOLE scouting/delivery surface; see `.claude/rules/architecture-subsystems.md` (Reports Package) for the reports flow's serving rules and conventions.
See `.claude/rules/data-model.md` for schema design decisions, table conventions, and column semantics.
See `.claude/rules/admin-ui.md` for admin interface structure, reports management, and user management.

## Project Management

Epic/story system managed by the **product-manager**. Epics: `E-NNN`, Stories: `E-NNN-SS`, Research: `E-NNN-R-SS`.

### Key Directories
- `/epics/` -- Active epics and stories; `/.project/archive/` -- Completed/abandoned epics
- `/.project/ideas/` -- Pre-epic ideas (see `.claude/rules/ideas-workflow.md`)
- `/.project/research/` -- Standalone research, POCs, and query artifacts
- `/docs/` -- API specs, architecture docs, domain reference; `/docs/VISION.md` -- Product vision

### Roadmap-Derived Epics
Epics that implement a `docs/ROADMAP.md` §5 slice (sequence A-E) follow the tracking convention defined in `docs/ROADMAP.md` §0 (authoritative): each such epic carries an explicit `## Roadmap` reference back to its §5 slice, and the §0 "Roadmap Tracking" table is updated at two moments -- the planning commit (slice → epic ID, status `PLANNING`) and epic closure (status `COMPLETED`). E-234 (slice A) established this pattern.

## Git Conventions
- Use conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Write descriptive commit messages explaining the "why"
- Keep PRs focused on a single concern
- Reference story IDs in commit messages when working on stories
- After committing, verify the `[pii-hook] PII scan passed.` confirmation appears in the output -- if it is missing, the safety scan may not have run; investigate before proceeding. (This line named `[pii-scan]` until 2026-07-26. That string is real -- `src/safety/pii_scanner.py` prints `[pii-scan] Scanned N file(s), 0 violations.` -- but only when at least one staged file qualifies for scanning, so it is legitimately absent from good commits and makes a poor thing to require. `[pii-hook] PII scan passed.` is the hook's terminating success line and appears whenever the gates pass.)

## Agent Ecosystem

This project uses specialized agents coordinated by the product-manager:

| Agent | Alias | Role |
|-------|-------|------|
| **claude-architect** | | Designs and manages agents, CLAUDE.md, rules, skills |
| **product-manager** | PM | Product Manager -- owns what to build, why, and in what order. Discovers requirements, plans epics, delegates implementation to specialists. |
| **baseball-coach** | coach | Domain expert -- translates coaching needs into technical requirements |
| **api-scout** | | Explores GameChanger API, maintains API spec, manages credential patterns |
| **data-engineer** | DE | Database schema design, ETL pipelines, SQLite architecture |
| **software-engineer** | SE | Python implementation, testing, general coding work |
| **docs-writer** | | Documentation specialist for operator and coaching-staff audiences. Writes and maintains admin runbooks and coaching how-tos for the reports and morning-run surfaces in `docs/admin/` and `docs/coaching/`. |
| **ux-designer** | | UX/interface designer for the reports serving surfaces -- report-layout, trust-surface, and tools-hub IA. Designs layouts, wireframes, component structure, and user flows for server-rendered HTML (Jinja2 + Tailwind). |
| **code-reviewer** | | Adversarial code reviewer -- verifies ACs and code quality before stories are marked DONE during dispatch. Spawned automatically by the implement skill; does not write or edit code. |

PM discovers requirements, writes epics/stories, and owns status transitions during dispatch. Code-reviewer gates every code story. Any agent identifying future work flags it to PM for idea capture. **Direct-routing exceptions**: `api-scout`, `baseball-coach`, `claude-architect` may be invoked without PM intermediation.

Dispatch relies on long-lived resumable named subagents (PM and code-reviewer persist across an epic, re-engaged via `SendMessage` with context intact). This requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (set in `.claude/settings.json`); without it the team-coordination tools (`SendMessage` and the shared `Task*` task list) are unavailable and spawned agents are one-shot.
