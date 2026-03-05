# E-045: Resolve mitmproxy Port Conflict with Devcontainer

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
The mitmproxy proxy listener (port 8080) is unreachable from the iPhone because VS Code devcontainer port forwarding and OrbStack Docker port mapping both claim port 8080 on the Mac host, causing `mitm.it` to route to Traefik's dashboard instead of the mitmproxy certificate installation page. This epic resolves the conflict so mitmproxy is reliably accessible from LAN devices.

## Background & Context
When the user configures their iPhone to use the mitmproxy proxy at `<host-ip>:8080` and visits `http://mitm.it` in Safari, they see the Traefik `/dashboard` page instead of the mitmproxy certificate installer. Investigation with `lsof -i :8080` on the Mac host shows both OrbStack (`*:8080`) and VS Code (`localhost:8080`) listening on port 8080. The devcontainer's `forwardPorts: [8000, 8080, 8081, 8180]` causes VS Code to forward port 8080 from the devcontainer to the host, which conflicts with OrbStack's Docker-level `0.0.0.0:8080:8080` mapping from `docker-compose.yml`.

The Traefik dashboard was already moved from 8080 to 8180 in E-039 to free 8080 for mitmproxy, but the devcontainer port forwarding was not updated to account for this -- it still forwards 8080, creating the conflict.

**Root cause**: `devcontainer.json` `forwardPorts` includes 8080, which VS Code auto-forwards. This races with Docker's own port mapping for the mitmproxy container. The iPhone connects to whichever listener wins the bind on the host's `0.0.0.0:8080`.

No expert consultation required -- the root cause is identified from direct investigation, and the solution is port configuration changes across Docker Compose, devcontainer, scripts, and docs.

## Goals
- mitmproxy proxy listener is reliably accessible from iPhone on the LAN (no port conflict)
- Devcontainer port forwarding does not conflict with Docker Compose port mappings
- Operator documentation and scripts reflect the correct port configuration
- All existing app stack functionality continues to work unchanged

## Non-Goals
- Changing the mitmproxy proxy listener port inside the container (8080 is mitmproxy's default and should stay)
- Automating LAN IP detection (existing `<your-host-lan-ip>` placeholder is adequate)
- Changing Traefik, app, or cloudflared port mappings (only mitmproxy and devcontainer forwarding are in scope)

## Success Criteria
- iPhone configured with `<host-ip>:<proxy-port>` can reach `http://mitm.it` and see the mitmproxy certificate installation page (not Traefik dashboard)
- `lsof -i :<proxy-port>` on the Mac host shows only one process listening
- `docker compose up` and `docker compose --profile proxy up` both start without port conflicts
- Existing tests pass (`pytest`)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-045-01 | Remove mitmproxy ports from devcontainer forwarding | DONE | None | software-engineer |
| E-045-02 | Update operator docs and scripts for port clarity | DONE | E-045-01 | software-engineer |

## Dispatch Team
- software-engineer (both stories -- E-045-02 doc changes are small, context-specific troubleshooting paragraphs tightly coupled to the port config; routing to docs-writer would add coordination overhead disproportionate to the work)

## Technical Notes

### Root Cause Analysis

The conflict arises from two independent port-forwarding mechanisms both targeting port 8080:

1. **Docker Compose** (`docker-compose.yml`): `0.0.0.0:8080:8080` on the mitmproxy service -- this is the OrbStack/Docker-level binding that makes the proxy reachable from the LAN.
2. **VS Code devcontainer** (`devcontainer.json`): `forwardPorts: [8000, 8080, 8081, 8180]` -- VS Code independently forwards these ports from the devcontainer to the host.

When Docker Compose binds `0.0.0.0:8080:8080`, OrbStack handles the host-side binding. Separately, VS Code sees port 8080 in `forwardPorts` and creates its own forwarding tunnel. Both end up on host port 8080, and depending on timing, the iPhone may connect to VS Code's forwarding (which routes to whatever is listening on 8080 inside the devcontainer -- nothing, or Traefik's internal port) instead of OrbStack's Docker mapping (which correctly routes to the mitmproxy container).

### Solution Approach

The fix is to **stop VS Code from forwarding ports that Docker Compose already maps externally**. Ports in `docker-compose.yml` with `0.0.0.0` binding are intended for LAN access via Docker's own networking -- VS Code forwarding is redundant and creates conflicts.

**Ports to remove from `forwardPorts`**: 8080 (mitmproxy proxy) and 8081 (mitmweb UI). These are Docker-mapped with `0.0.0.0` binding for LAN access.

**Ports to keep in `forwardPorts`**: 8000 (Traefik web entry, `localhost` access from devcontainer host) and 8180 (Traefik dashboard, `localhost` access from devcontainer host). These provide developer convenience for accessing the app from the host browser.

**Note on 8001**: Port 8001 (`127.0.0.1:8001:8000` for the app) is bound to localhost only in Docker Compose and is NOT in `forwardPorts` -- this is correct and should not change. It is for direct app access from inside the devcontainer (bypassing Traefik).

### File Conflict Matrix

| File | E-045-01 | E-045-02 |
|------|----------|----------|
| `.devcontainer/devcontainer.json` | MODIFY | - |
| `docker-compose.yml` | MODIFY (add comment only, no functional change) | - |
| `scripts/proxy.sh` | - | MODIFY |
| `docs/admin/mitmproxy-guide.md` | - | MODIFY |

No file conflicts between stories, but E-045-02 depends on E-045-01 to know the final port configuration before updating docs.

## Open Questions
- None. Root cause is identified and solution approach is clear.

## History
- 2026-03-05: Created. Root cause identified from user investigation (lsof showing dual listeners on port 8080).
- 2026-03-05: SE technical review completed -- root cause, fix, and all ACs validated against actual file state. No changes required. Epic set to READY.
- 2026-03-05: Codex spec review completed. Two changes incorporated: (1) File Conflict Matrix corrected docker-compose.yml from "READ" to "MODIFY" for E-045-01, (2) Dispatch Team section annotated with routing exception rationale for E-045-02 doc work. Remaining findings (DoD genericity, AC flexibility language, regression-guard AC) assessed as low-impact -- no changes needed.
- 2026-03-05: Dispatch started. E-045-01 marked IN_PROGRESS, epic set to ACTIVE.
- 2026-03-05: All stories DONE. E-045-01 removed 8080/8081 from devcontainer forwardPorts and added warning comments. E-045-02 added troubleshooting subsection to mitmproxy guide and enhanced proxy.sh status with lsof port-conflict detection. No documentation impact beyond the in-scope doc changes (E-045-02 already updated mitmproxy-guide.md). Epic COMPLETED.
