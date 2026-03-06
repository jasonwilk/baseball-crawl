# E-046: Upstream Proxy Support

## Status
`READY`

## Overview
Add unified upstream proxy support so both Python crawlers and mitmproxy route traffic through an external proxy when configured. A single pair of env vars (`PROXY_ENABLED`, `PROXY_URL`) controls proxy for all outbound paths. This enables the operator to use residential or other proxy services to avoid IP-based blocking during crawls.

## Background & Context
GameChanger may throttle or block requests from known datacenter/home IP ranges. Routing traffic through an external proxy (e.g., Oxylabs residential) mitigates this. The operator chooses the proxy provider and URL -- the code just wires it through without distinguishing proxy types.

Two outbound paths exist:
1. **Python crawlers** -- `create_session()` in `src/http/session.py` produces `httpx.Client` instances used by all crawlers and the GameChanger client.
2. **mitmproxy Docker service** -- runs as a profile-activated service for credential capture and API discovery.

Both must respect the same proxy configuration. When `PROXY_ENABLED` is unset or `false`, current behavior is preserved (no proxy).

No expert consultation required -- this is pure infrastructure plumbing with well-understood requirements. The user provided complete requirements including env var names, file locations, and behavior for edge cases.

## Goals
- A single `.env` configuration controls proxy for both Python crawlers and mitmproxy
- Proxy URL (which contains credentials) is never logged or exposed
- Graceful degradation: misconfiguration warns but does not crash

## Non-Goals
- Per-host proxy routing (all traffic or no traffic)
- Mobile vs. residential proxy distinction in code
- Proxy provider selection or recommendation
- Proxy health checking or failover

## Success Criteria
- `PROXY_ENABLED=true` + valid `PROXY_URL` routes Python crawler traffic through the proxy
- `PROXY_ENABLED=true` + valid `PROXY_URL` starts mitmproxy in upstream mode
- `PROXY_ENABLED=false` (or unset) preserves current no-proxy behavior for both paths
- `PROXY_ENABLED=true` + empty `PROXY_URL` logs a WARNING and proceeds without proxy
- Proxy URL never appears in log output
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-046-01 | Python crawler proxy support | TODO | None | - |
| E-046-02 | mitmproxy upstream mode | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Proxy Configuration
- **Env vars**: `PROXY_ENABLED` (string: `true`/`false`, default unset = disabled), `PROXY_URL` (full URL including credentials, format: `http://USER:PASS` + `@host:port`)
- **Credential safety**: `PROXY_URL` contains embedded credentials. It must never appear in log output, error messages, or debug traces. Use the same discipline as `GC_TOKEN`.

### httpx Proxy API (v0.28.x)
- `httpx.Client(proxy="http://...")` -- singular `proxy` kwarg (string). Routes all traffic through the proxy.
- When `proxy` is `None` (default), no proxy is used. This is the current behavior.

### mitmproxy Upstream Mode
- `mitmweb --mode upstream:http://proxy-url:port` starts mitmproxy in upstream proxy mode, forwarding all traffic through the specified proxy.
- When no `--mode` is specified, mitmproxy runs as a regular intercepting proxy (current behavior).
- Docker Compose can conditionally include the `--mode` argument. Since Compose does not support conditional command args natively, the story should use a wrapper approach (entrypoint script or shell command) that checks `PROXY_ENABLED` at container start.

### File Ownership (Parallel Safety)
- **E-046-01** modifies: `src/http/session.py`, `tests/test_http_session.py`, `.env.example`
- **E-046-02** modifies: `docker-compose.yml`, `scripts/proxy.sh`
- No file conflicts -- stories can be dispatched in parallel.

## Open Questions
None.

## History
- 2026-03-05: Created. Set to READY.
