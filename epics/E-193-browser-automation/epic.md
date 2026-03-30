# E-193: Browser Automation Infrastructure

## Status
`READY`

## Overview
Enable agents to visually verify UI changes through browser automation, creating tighter design feedback loops. This adds a headless Chrome sidecar to Docker Compose, integrates `agent-browser` knowledge into the context layer, and establishes URL resolution conventions so agents know how to reach the running app.

## Background & Context
Agents (especially UXD) currently have no way to visually verify UI changes after implementation. They write HTML/CSS specifications but cannot confirm that the rendered output matches their intent. This gap means design verification relies entirely on the user's manual review.

The `agent-browser` npm package is already installed locally (`node_modules/agent-browser/`, v0.23+). It provides CDP-based browser automation commands: `open`, `snapshot` (accessibility tree with element refs), `click`, `type`, `fill`, `press`, `close`. However, it requires a Chrome/Chromium binary. Currently, Playwright's Chromium sits at `~/.cache/ms-playwright/` (928MB) -- an unnecessarily heavy footprint for the devcontainer. Note: `agent-browser` has zero npm dependencies -- Playwright is NOT a transitive dependency. The Chromium binary was installed separately (likely via `npx playwright install`).

**Expert consultation completed:**
- **SE**: Recommends `browserless/chrome` v2 Docker image (multi-arch, built-in health check, CDP WebSocket on port 3000, crash recovery). Connection via `--connect-over-cdp`.
- **CA**: Recommends a scoped rule at `.claude/rules/browser-automation.md` (fires on template/UI paths) + UXD agent definition update. NOT ambient in CLAUDE.md, NOT a skill. URL convention is simple: "app at localhost:8001 from devcontainer." Worktree constraint: browser automation only works in main checkout (epic worktree agents cannot reach Docker services).

## Goals
- Agents can open the running app in a headless browser and take accessibility-tree snapshots to verify UI structure
- Chrome runs as a Docker Compose sidecar, eliminating the 928MB local Playwright Chromium install
- Context layer teaches agents how, when, and where to use browser automation
- UXD agent definition includes browser verification as a capability

## Non-Goals
- Visual screenshot comparison (PNG diffing) -- accessibility tree snapshots are sufficient for now
- Automated test suites using browser automation -- this is for ad-hoc agent verification
- Production browser automation -- this is dev-only infrastructure
- Mac host or CI environment support -- devcontainer-only for now
- Multi-page flow recipes or auth-gated page automation patterns -- can be added later as needs arise

## Success Criteria
- `docker compose up -d` starts a Chrome sidecar alongside the existing services (via override file in dev)
- An agent can run `./node_modules/.bin/agent-browser --connect-over-cdp ws://localhost:3000 open http://localhost:8001` and receive an accessibility tree snapshot
- The scoped rule at `.claude/rules/browser-automation.md` teaches agents the correct commands, URL, and constraints
- UXD agent definition references browser automation as a verification capability
- Playwright Chromium is no longer downloaded into the devcontainer

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-193-01 | Chrome sidecar in Docker Compose | TODO | None | - |
| E-193-02 | Browser automation context-layer rule | TODO | None | - |
| E-193-03 | UXD agent definition browser capability | TODO | E-193-02 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Chrome Sidecar Configuration
- **Image**: `browserless/chrome` v2 (multi-arch: amd64 + arm64)
- **CDP port**: 3000 (browserless v2 default)
- **Service name**: `chrome` in docker-compose
- **Host-port binding**: `"127.0.0.1:3000:3000"` -- required because the devcontainer shell is the Docker-in-Docker host, not a compose service. Docker service-name DNS (`chrome`) only resolves from within other compose containers. The devcontainer must use `localhost:3000`.
- **Connection URL**: `ws://localhost:3000` from the devcontainer shell
- **Health check**: browserless v2 provides a built-in health endpoint
- **Flags**: `--no-sandbox --disable-gpu` handled automatically by browserless
- **Dev-only scoping**: Define the Chrome service in `docker-compose.override.yml.example` (the tracked template). Users copy this to `docker-compose.override.yml` (gitignored) for local dev. In development, the override is present and Chrome starts automatically with `docker compose up -d`. In production (no override file), the Chrome service does not exist. No profiles needed -- this matches the existing pattern where the example template defines dev-specific services.

### agent-browser CLI Usage
- **Binary**: `./node_modules/.bin/agent-browser` (NOT `npx agent-browser` -- misparses flags)
- **First command** (opens browser): `./node_modules/.bin/agent-browser --connect-over-cdp ws://localhost:3000 open "http://localhost:8001"`
- **Subsequent commands** (daemon persists): `./node_modules/.bin/agent-browser snapshot`, `./node_modules/.bin/agent-browser click --ref <ref>`, etc.
- **Close session**: `./node_modules/.bin/agent-browser close`

### URL Convention
- **Devcontainer**: `http://localhost:8001` (direct access to app, bypasses Traefik)
- Agents always run in the devcontainer. No environment detection logic needed for the rule -- just document the URL.

### Worktree Constraint
- Browser automation only works in the **main checkout**. Epic worktree agents cannot reach Docker services (Docker-in-Docker networking is scoped to the main devcontainer namespace).
- The rule must clearly state this constraint so agents don't attempt browser commands during dispatch.
- **AC verification implication**: AC-2 and AC-3 in E-193-01 require a live Chrome sidecar. These are verified manually by the user in the main checkout after merge, not in the epic worktree during dispatch. The implementer writes the Docker config; the user verifies the live connection post-merge. (The main session must not verify ACs per dispatch-pattern.md.)

### Playwright Chromium Removal
- `agent-browser` has zero npm dependencies -- Playwright is NOT a transitive dependency. The 928MB Chromium at `~/.cache/ms-playwright/` was installed separately (likely via `npx playwright install`).
- Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in `containerEnv` in `devcontainer.json` (NOT `remoteEnv` -- `remoteEnv` applies after container creation, which is too late to prevent downloads during `postCreateCommand`).
- This is defensive insurance. The primary fix is ensuring no step in `postCreateCommand` triggers a Playwright browser download.
- The existing 928MB at `~/.cache/ms-playwright/` will not be present in new container builds once no command downloads it.

## Open Questions
- None remaining after expert consultation and internal review.

## History
- 2026-03-30: Created from user request. SE and CA consulted. UXD unresponsive (needs inferred from domain knowledge).
- 2026-03-30: Internal review (iteration 1). 9 findings accepted: fixed CDP URL (ws://localhost:3000 + port binding), resolved AC-4 ambiguity (profiles in base compose), fixed env var timing (containerEnv), removed false E-193-02→E-193-01 dependency, specified exact glob patterns, removed redundant AC in E-193-03, added worktree verification note, clarified Playwright is not a transitive dep.
- 2026-03-30: Internal review (iteration 2). 2 findings accepted: replaced invalid profile activation with override-only approach (Chrome defined entirely in docker-compose.override.yml), removed vestigial Handoff Context from E-193-01.
- 2026-03-30: Codex spec review (iteration 1). 4 findings accepted: target tracked `.example` file (not gitignored override), AC-2/AC-3 user-verified (not main-session), AC-5 concrete observable outcome, removed superseded env var recommendations from Background.
- 2026-03-30: Set to READY.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 6 | 6 | 0 |
| Internal iteration 1 -- Holistic team (PM) | 5 | 5 | 0 |
| Internal iteration 2 -- CR spec audit | 2 | 2 | 0 |
| Internal iteration 2 -- Holistic team (PM) | 2 | 2 | 0 |
| Codex iteration 1 | 4 | 4 | 0 |
| **Total** | **19** | **19** | **0** |

Note: Internal iteration 1 had 11 raw findings deduped to 9 unique. Internal iteration 2 had 4 raw findings deduped to 2 unique. All counts above are unique (deduplicated).
