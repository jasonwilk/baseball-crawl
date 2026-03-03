# E-027: Devcontainer-to-Compose Networking

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Connect the devcontainer to the Docker Compose network so Claude Code can reliably reach the FastAPI app by container name, read app logs, and troubleshoot the running system -- without manual IP lookups or fragile workarounds.

## Background & Context
Claude Code runs inside the devcontainer, which uses Docker-in-Docker to run `docker compose up`. The app container lands on the `baseball-crawl_default` bridge network. Currently, the only way to reach the app from inside the devcontainer is to discover the container's IP address (e.g., `172.18.0.2:8000`), which changes on every restart. There is no stable hostname, and accessing logs requires manual `docker logs` commands with container IDs that also change.

This is a developer-experience problem: Claude Code should be able to check health endpoints, curl the app, and read logs as part of normal troubleshooting -- without friction.

No expert consultation required -- this is standard Docker networking and devcontainer configuration, fully within the infrastructure domain.

## Goals
- The app container is reachable from the devcontainer by a stable, human-readable hostname
- App logs are trivially accessible from inside the devcontainer
- Claude Code (and the user) can troubleshoot the running app without manual IP lookups

## Non-Goals
- Changing the Docker Compose service definitions (Traefik, cloudflared, app) beyond what is needed for network connectivity
- Production deployment changes -- this is purely a dev-time improvement
- Modifying the app's code or health check endpoint
- Adding monitoring, alerting, or log aggregation tooling

## Success Criteria
- From inside the devcontainer, `curl http://app:8000/health` (or equivalent stable hostname) returns a successful response
- From inside the devcontainer, `docker logs baseball-crawl-app-1` (or equivalent) returns app logs without needing to look up container IDs
- CLAUDE.md documents the troubleshooting workflow so agents and the user know how to use it

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-027-01 | Connect devcontainer to Compose network | DONE | None | - |
| E-027-02 | Document troubleshooting workflow in CLAUDE.md | DONE | E-027-01 | - |

## Technical Notes

### Network Approach
The devcontainer needs to join the Docker Compose bridge network (`baseball-crawl_default`) so it can resolve Compose service names. The standard approach is to either:
1. Add the devcontainer to the Compose network after startup (via a lifecycle script that runs `docker network connect`)
2. Configure the devcontainer to use the Compose network directly

Option 1 (post-start script) is simpler and does not require the Compose network to exist before the devcontainer starts. A `postStartCommand` or `initializeCommand` in `devcontainer.json` can run `docker network connect baseball-crawl_default <devcontainer-hostname>` after the container is up.

**Key detail**: Inside a docker-in-docker devcontainer, the devcontainer itself is not a Docker container from its own Docker daemon's perspective -- it is the host. The Compose containers run inside the devcontainer's Docker daemon. This means the networking solution may differ from the typical "connect container to network" pattern. The implementing agent should verify the actual network topology and adapt accordingly. The acceptance criteria care about the outcome (stable hostname access), not the specific mechanism.

### Log Access
The `docker` CLI is already available inside the devcontainer (docker-in-docker feature). `docker logs` and `docker compose logs` should work once the implementing agent confirms the Docker socket is accessible. The story should verify this and document the exact commands.

### Files Involved
- `.devcontainer/devcontainer.json` -- network configuration or lifecycle script
- Possibly a helper script in `.devcontainer/` or `scripts/` if a lifecycle hook is needed
- `CLAUDE.md` -- troubleshooting section
- `docker-compose.yml` -- only if network configuration needs to be explicit (e.g., named network)

## Open Questions
- None. The problem and desired outcome are clear. Implementation details (exact networking mechanism) are delegated to the implementing agent.

## History
- 2026-03-03: Created. READY -- no expert consultation needed (standard Docker networking).
- 2026-03-03: Dispatch started. Epic set to ACTIVE. E-027-01 dispatched (IN_PROGRESS).
- 2026-03-03: E-027-01 DONE. Solution: added `ports: ["8001:8000"]` to app service in docker-compose.yml. Port 8001 avoids conflict with Traefik's 8000:80 mapping. App reachable at localhost:8001 from devcontainer.
- 2026-03-03: E-027-02 DONE. Added 30-line "App Troubleshooting" section to CLAUDE.md with stack management, health check, logs, and unreachable troubleshooting commands.
- 2026-03-03: All stories DONE. Epic COMPLETED. Archived to /.project/archive/E-027-devcontainer-compose-networking/.
