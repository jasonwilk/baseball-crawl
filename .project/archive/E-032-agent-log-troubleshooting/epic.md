# E-032: Agent Log Access and Troubleshooting Verification

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Verify end-to-end that agents can reliably access application logs from the devcontainer, use those logs to diagnose real application errors, and propose fixes -- proving the troubleshooting workflow established in E-027 actually works in practice.

## Background & Context
E-027 (Devcontainer-to-Compose Networking, COMPLETED) established:
- App reachable at `http://localhost:8001` from inside the devcontainer
- `docker compose logs app` works for log access
- CLAUDE.md has an "App Troubleshooting" section (lines 87-122) with commands for stack management, health checks, logs, and diagnosing unreachable apps

But E-027 was a *setup* epic. The troubleshooting workflow was documented but never exercised against a real failure scenario. The user wants proof that the system works: can an agent actually start the app, hit an endpoint, observe an error in the logs, read the traceback, and propose a fix? And if something is missing from the toolchain, what is it?

This is a small verification epic -- not a feature-building epic. Think of it as an integration test for the agent troubleshooting workflow.

No expert consultation required before story writing -- this is infrastructure verification. If gaps are discovered during execution, the implementing agent will note them as findings (including any context layer adjustments for claude-architect to address in a follow-on).

## Goals
- Prove that agents can start the app stack, access logs, and read meaningful output
- Prove that agents can correlate log output with application errors (e.g., a 500 response traceback)
- Identify any toolchain gaps that prevent agents from being effective troubleshooters
- Document any findings or recommended improvements

## Non-Goals
- Building new monitoring, alerting, or log aggregation infrastructure
- Changing the app's error handling or logging format
- Modifying the Docker Compose configuration (unless a gap is discovered that requires it)
- Creating permanent test endpoints or fixtures in the app

## Success Criteria
- An agent has successfully: started the app, hit the health endpoint, read logs, triggered an error, found the traceback in logs, and identified the root cause
- Any gaps in the toolchain are documented with specific recommendations
- If gaps are found, follow-up work is captured (idea or story recommendation)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-032-01 | Verify agent log access and health check workflow | DONE | None | - |
| E-032-02 | Verify agent error diagnosis from logs | DONE | E-032-01 | - |

## Technical Notes

### App Architecture (for implementing agents)
- **Docker Compose file**: `/workspaces/baseball-crawl/docker-compose.yml`
- **App entrypoint**: `src/api/main.py` -- FastAPI app, started via uvicorn on port 8000 inside the container
- **Port mapping**: Container port 8000 -> host port 8001 (accessible as `http://localhost:8001` from devcontainer)
- **Health endpoint**: `GET /health` -- returns `{"status": "ok", "db": "connected"}` (200) or `{"status": "error", "db": "error"}` (503)
- **Dashboard endpoint**: `GET /dashboard` -- renders Jinja2 template with team batting stats
- **Logging**: Python `logging` module, format `%(asctime)s %(levelname)s [%(name)s] %(message)s`
- **Database**: SQLite at `./data/app.db` (host-mounted volume)

### CLAUDE.md Troubleshooting Section
The relevant commands are documented in CLAUDE.md lines 87-122. Key commands:
```bash
docker compose up -d          # start stack
docker compose ps             # check status
curl -s http://localhost:8001/health  # health check
docker compose logs app       # full logs
docker compose logs --tail=50 app    # last 50 lines
docker compose logs -f app    # follow live
```

### What "Verification" Means
These stories are not unit tests. They are hands-on exercises where an implementing agent runs real commands, observes real output, and reports what happened. The acceptance criteria are satisfied by demonstrating the workflow works (or documenting specifically how it fails).

### Error Scenario for E-032-02
The implementing agent should trigger a real application error that produces a traceback in logs. Options:
1. Hit a nonexistent endpoint (should produce a 404 -- but FastAPI handles this gracefully, may not produce a log traceback)
2. Temporarily break something that causes a 500 (e.g., rename the database file so the health check fails with a 503, or hit `/dashboard` when the expected DB table does not exist)
3. Any other approach that produces a genuine error with a traceback visible in `docker compose logs app`

The implementing agent should choose the approach that best demonstrates real-world troubleshooting. The key is that the error must be visible in the container logs (not just in the HTTP response body).

### Gap Documentation
If any step fails or is harder than expected, the implementing agent must document:
1. What they tried
2. What happened (include actual command output)
3. What was missing or broken
4. Specific recommendation for fixing it (e.g., "add X to CLAUDE.md", "adjust context layer file Y", "create a helper script for Z")

These findings will be reviewed by PM after the epic completes. If context layer changes are needed, they will be captured as follow-up work for claude-architect.

## Open Questions
- None. The scope is clear: run the workflow, report what works and what does not.

## History
- 2026-03-03: Created. Two-story verification epic. READY -- no expert consultation needed (infrastructure verification).
- 2026-03-03: Dispatch started. Epic set to ACTIVE. E-032-01 dispatched (IN_PROGRESS).
- 2026-03-03: E-032-01 verified DONE (all 5 ACs passed). E-032-02 unblocked, set to IN_PROGRESS.
- 2026-03-03: E-032-02 verified DONE (all 5 ACs passed). Agent triggered DB removal error, diagnosed root cause from logs alone, proposed correct fix, reverted changes, app left healthy. One recommendation: add grep-based log filtering examples to CLAUDE.md troubleshooting section.
- 2026-03-03: Epic COMPLETED. Both stories DONE. E-027 troubleshooting workflow validated end-to-end. No blocking gaps found. Minor recommendation (grep log filtering) noted for future CLAUDE.md update. Archived to /.project/archive/E-032-agent-log-troubleshooting/.
