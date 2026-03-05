# E-048: Migrate mitmproxy to Host-Based Standalone Proxy

## Status
`ACTIVE`

## Overview
Move mitmproxy out of the project's Docker Compose stack and into a self-contained `proxy/` folder that runs directly on the Mac host. This eliminates all Docker-in-Docker + VS Code port forwarding complexity that has caused persistent networking issues (see MITM-TROUBLESHOOTING.md), and creates a clean operational boundary: proxy runs on the Mac, app runs in the devcontainer, they communicate via `host.docker.internal`.

## Background & Context
The mitmproxy service was added in E-039 as a Docker Compose profile (`--profile proxy`) running inside the devcontainer's Docker-in-Docker environment. This created a chain of networking problems documented extensively in MITM-TROUBLESHOOTING.md:
- Mac host cannot reach mitmproxy ports without VS Code port forwarding
- VS Code forwards ports as loopback-only by default, blocking iPhone LAN access
- The `portsAttributes` / `allInterfaces` setting behavior is unverified
- E-045 attempted fixes but was based on an incorrect networking model

The user validated that running mitmproxy directly on the Mac host in its own Docker container works perfectly:
- `host.docker.internal:8080` resolves from inside the devcontainer
- iPhone reaches `0.0.0.0:8080` on the Mac directly (no VS Code forwarding needed)
- mitmweb UI accessible at `localhost:8081` on the Mac
- A working prototype exists at `proxy-host/`

Expert consultation: Architecture validated by the user through hands-on testing. No pre-planning consultation required for schema, API, or domain design. claude-architect is included in the dispatch team for context-layer file edits (E-048-05 modifies devcontainer rules and architect memory; E-048-06 modifies CLAUDE.md), satisfying the agent infrastructure consultation requirement during dispatch.

## Goals
- `proxy/` is a fully self-contained folder with its own `docker-compose.yml`, scripts, certs, and data directories
- mitmproxy service, volume, and profile are removed from the project `docker-compose.yml`
- All addon output paths point to `proxy/data/` instead of `data/mitmproxy/`
- Report scripts read from `proxy/data/`
- devcontainer.json is cleaned up (no mitmproxy port forwarding or attributes)
- CLAUDE.md commands section reflects the new proxy workflow
- Documentation is updated for the host-based approach
- `proxy-host/` prototype is deleted (consolidated into `proxy/`)

## Non-Goals
- Upstream proxy support (E-046 covers PROXY_ENABLED/PROXY_URL env vars separately)
- Changing addon functionality -- the addons do the same thing, just in a different location
- Automating proxy setup for non-Mac hosts (Linux/Windows docs can come later)

## Success Criteria
- Operator can `cd proxy && ./start.sh` on the Mac host and have a working proxy
- iPhone can reach the proxy at `<mac-lan-ip>:8080` without any VS Code involvement
- Credential extractor still writes to the project root `.env`
- Report scripts (`scripts/proxy-report.sh`, `scripts/proxy-endpoints.sh`) read from `proxy/data/`
- `docker compose up` in the devcontainer starts only app + traefik + cloudflared (no mitmproxy references)
- All existing proxy addon tests pass
- MITM-TROUBLESHOOTING.md is deleted (obsolete)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-048-01 | Create proxy/ infrastructure | IN_PROGRESS | None | software-engineer |
| E-048-02 | Update addon output paths | IN_PROGRESS | None | software-engineer |
| E-048-03 | Update report scripts | TODO | E-048-02 | - |
| E-048-04 | Remove mitmproxy from project docker-compose.yml | IN_PROGRESS | None | software-engineer |
| E-048-05 | Clean up devcontainer.json | IN_PROGRESS | None | claude-architect |
| E-048-06 | Update CLAUDE.md and documentation | TODO | E-048-01, E-048-03, E-048-04 | claude-architect |
| E-048-07 | Delete prototype and obsolete files | TODO | E-048-01, E-048-06 | - |

## Dispatch Team
- software-engineer
- docs-writer
- claude-architect

## Technical Notes

### Container Volume Mounts
The proxy's `docker-compose.yml` mounts `..:/app` (project root at `/app`). This is how:
- Addons import `src.*` modules (via `PYTHONPATH=/app`)
- Credential extractor writes to `/app/.env` (project root `.env`)
- Addons write output to `/app/proxy/data/`

The `proxy/certs/` directory is bind-mounted at `/home/mitmproxy/.mitmproxy` for CA cert persistence (replacing the named Docker volume `mitmproxy-certs`).

### Path Changes Summary
| Current Path | New Path | Used By |
|---|---|---|
| `data/mitmproxy/header-report.json` | `proxy/data/header-report.json` | header_capture.py, proxy-report.sh |
| `data/mitmproxy/endpoint-log.jsonl` | `proxy/data/endpoint-log.jsonl` | endpoint_logger.py, proxy-endpoints.sh |
| Docker volume `mitmproxy-certs` | `proxy/certs/` (bind mount) | docker-compose.yml |

### Addon Import Path Note
`header_capture.py` has a `_PROJECT_ROOT = Path(__file__).resolve().parents[3]` sys.path fallback that resolves to `/` inside the container (should be `parents[2]` for `/app`). This is harmless because `PYTHONPATH=/app` handles imports, but the story should fix it to `parents[2]` while touching the file.

### Git Ignore Strategy
`proxy/.gitignore` handles `certs/`, `data/`, `.env`, and `__pycache__/`. The project-root `.gitignore` does not need changes -- `proxy/certs/` and `proxy/data/` are not under the project `data/` rule. The `proxy/.env` is caught by the project-root `.env.*` glob? No -- `.env.*` matches `.env.foo` but not `proxy/.env`. The `proxy/.gitignore` must handle `proxy/.env` locally.

### mitmweb Authentication
mitmweb now requires `?token=` or `--set web_password=...`. The proxy `.env.example` should document the `MITMWEB_PASSWORD` variable and the docker-compose should pass it through.

### Python Version Gap
The `mitmproxy/mitmproxy` Docker image ships Python 3.14. The project devcontainer runs Python 3.13. Addons execute under 3.14 at runtime inside the mitmproxy container. This is low practical risk because all addon code uses stdlib only (no project dependencies), but operators should be aware. `proxy/README.md` should document this.

### Existing Test Mocking
All tests in `tests/test_proxy/` mock `_REPORT_PATH` and `LOG_PATH` via `unittest.mock.patch`, so changing the default path values in the addon source will not break tests. The tests will continue to pass unchanged.

### Files Touched Per Story (Parallel Safety)
- E-048-01: Creates `proxy/docker-compose.yml`, `proxy/.env.example`, `proxy/.gitignore`, `proxy/start.sh`, `proxy/stop.sh`, `proxy/status.sh`, `proxy/logs.sh`, `proxy/certs/.gitkeep`, `proxy/data/.gitkeep`, `proxy/README.md`
- E-048-02: Modifies `proxy/addons/header_capture.py`, `proxy/addons/endpoint_logger.py`
- E-048-03: Modifies `scripts/proxy-report.sh`, `scripts/proxy-endpoints.sh`
- E-048-04: Modifies `docker-compose.yml`
- E-048-05: Modifies `.devcontainer/devcontainer.json`, `.claude/rules/devcontainer.md`, `.claude/agent-memory/claude-architect/MEMORY.md`
- E-048-06: Modifies `CLAUDE.md`, `docs/admin/mitmproxy-guide.md`
- E-048-07: Deletes `proxy-host/` directory, deletes `MITM-TROUBLESHOOTING.md`

No file conflicts between stories except the E-048-03 -> E-048-02 dependency (report scripts must read from the same paths addons write to) and E-048-06 depending on E-048-01/03/04 (docs reference final paths and commands).

### IDEA-010 Overlap
E-048 partially resolves IDEA-010 (docs port map consistency): mitmproxy references are cleaned up, and E-048-05 fixes the stale Traefik dashboard port in `.claude/rules/devcontainer.md` and `.claude/agent-memory/claude-architect/MEMORY.md`. After E-048 completes, IDEA-010 should be reviewed -- the remaining scope is Traefik dashboard port staleness in other docs files (e.g., getting-started.md).

## Open Questions
None -- architecture validated by operator testing.

## History
- 2026-03-05: Created. Architecture validated via hands-on testing (host.docker.internal confirmed, iPhone direct access confirmed, prototype at proxy-host/ working).
- 2026-03-05: Spec review triage. 5 findings reviewed: 1 ACCEPTED (Finding 5 -- added AC-11 to E-048-01 for devcontainer-to-host-proxy validation via `curl -sx http://host.docker.internal:8080 http://mitm.it`), 4 REJECTED as false positives (Finding 1: scripts/proxy.sh already in E-048-07 AC-3; Finding 2: DinD and Mac host are separate Docker engines, no port conflict; Finding 3: mitmweb auth already in E-048-01 AC-2; Finding 4: MITM-TROUBLESHOOTING.md is obsolete, git history preserves it). Epic remains READY.
- 2026-03-05: Dispatch started. Epic set to ACTIVE. Wave 1 dispatched: E-048-01 (SE), E-048-02 (SE), E-048-04 (SE), E-048-05 (claude-architect). All in parallel -- no file conflicts.
