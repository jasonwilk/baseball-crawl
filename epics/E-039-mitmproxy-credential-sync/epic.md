# E-039: mitmproxy Credential Sync and API Discovery

## Status
`DRAFT`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->
<!-- PM sets READY explicitly after: expert consultation done, all stories have testable ACs, quality checklist passed. -->
<!-- Only READY and ACTIVE epics can be dispatched. -->

## Overview
Integrate mitmproxy into the devcontainer as a passive traffic interception layer that automatically extracts GameChanger credentials, captures real browser/app headers, and logs API endpoint usage -- replacing manual curl-copy workflows with a live, always-current synchronization system. This makes credential rotation, header parity, and API discovery low-friction continuous processes rather than periodic manual chores.

## Background & Context
Today, credential management requires the user to (1) open Chrome DevTools, (2) copy a curl command, (3) paste it into `secrets/gamechanger-curl.txt`, and (4) run `scripts/refresh_credentials.py`. Headers in `src/http/headers.py` are manually copied from a single curl capture and go stale as Chrome versions change. API endpoint discovery requires manual investigation by api-scout.

mitmproxy is a mature, open-source HTTPS proxy that supports Python addon scripts hooking into every request/response. By running it as a Docker Compose service, the user can point their iPhone or web browser at the proxy and have credentials, headers, and endpoint data captured automatically. The iPhone (GameChanger iOS app) and web browser send different headers and may use different API endpoints -- the system must distinguish between these traffic sources.

No expert consultation required -- this is developer tooling/infrastructure work. The research spike (E-039-R-01) will investigate the mitmproxy addon ecosystem before implementation begins.

## Goals
- Eliminate manual curl-copy credential workflow -- credentials flow from live traffic to `.env` automatically
- Keep `BROWSER_HEADERS` in `src/http/headers.py` in sync with real browser/app traffic, not manual snapshots
- Passively discover and log every GameChanger API endpoint hit, feeding into `docs/gamechanger-api.md`
- Distinguish iOS app traffic from web browser traffic so the project can choose the best fingerprint
- Make the mitmproxy service trivial to start, stop, and configure within the devcontainer

## Non-Goals
- Intercepting or modifying traffic (this is passive capture only)
- Automatically updating `src/http/headers.py` on every request (that is a manual review step -- the system captures and reports)
- Replacing the existing `refresh_credentials.py` script (it remains for manual curl-paste fallback)
- Intercepting non-GameChanger traffic (filter to GameChanger domains only)
- Production deployment of mitmproxy (dev-only tool)
- Programmatic gc-signature generation (still unknown; mitmproxy captures it but cannot generate it)

## Success Criteria
- `docker compose --profile proxy up -d` starts mitmproxy alongside the app
- Credentials from live GameChanger traffic appear in `.env` within seconds of a request flowing through
- A header report shows the exact headers sent by iOS vs. web, diffed against `BROWSER_HEADERS`
- An endpoint log captures every unique GameChanger API path, method, and content-type seen
- The iPhone can reach the proxy from the LAN and install the mitmproxy CA cert via `mitm.it`
- Tearing down the proxy (`docker compose --profile proxy down`) leaves no side effects

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-039-R-01 | Research: mitmproxy addon ecosystem | TODO | None | - |
| E-039-01 | mitmproxy Docker Compose service | TODO | E-039-R-01 | - |
| E-039-02 | GameChanger credential extraction addon | TODO | E-039-01 | - |
| E-039-03 | Header capture and parity report | TODO | E-039-01 | - |
| E-039-04 | API endpoint discovery log | TODO | E-039-01 | - |
| E-039-05 | iOS vs. web traffic tagging | TODO | E-039-02, E-039-03, E-039-04 | - |
| E-039-06 | Operator CLI and documentation | TODO | E-039-01 | - |

## Technical Notes

### Docker Compose Profile Strategy
The mitmproxy service uses a Docker Compose **profile** (`proxy`) so it does not start by default. `docker compose up -d` starts only the app/traefik/cloudflared services as today. `docker compose --profile proxy up -d` adds mitmproxy. This avoids port conflicts and resource waste when the proxy is not needed.

### Port Exposure
- **8080**: mitmproxy listen port (HTTP/HTTPS proxy). Must bind to `0.0.0.0` so the iPhone on the LAN can reach it. Note: this conflicts with the Traefik dashboard port (currently `8080:8080`). Resolution: move the Traefik dashboard to port `8180` (Traefik is rarely accessed directly; mitmproxy needs the well-known proxy port).
- **8081**: mitmweb UI (web interface for inspecting traffic). Bind to `0.0.0.0` for access from the host browser.

### Addon Architecture
mitmproxy addons are Python scripts loaded via `--scripts` flag. Each addon is a class with event hooks (`request()`, `response()`, etc.). The project will create addon scripts under `mitmproxy/addons/` (new top-level directory, dev-only). Key addons:
1. **credential_extractor.py** -- watches for `gc-token`, `gc-device-id`, `gc-signature` headers; writes to `.env` via the existing `merge_env_file()` function from `src/gamechanger/credential_parser.py`.
2. **header_capture.py** -- captures all headers from GameChanger requests, groups by source (iOS/web), writes a diff report.
3. **endpoint_logger.py** -- logs every unique (method, path, content-type) tuple seen on GameChanger domains.
4. **gc_filter.py** -- base filter that passes only `*.gc.com` / `*.gamechanger.com` domains to downstream addons (reduces noise).

### Traffic Source Detection (iOS vs. Web)
The User-Agent header reliably distinguishes iOS app traffic from web browser traffic:
- iOS: contains `GameChanger/` or `CFNetwork/` or `Darwin/`
- Web: contains `Chrome/` or `Firefox/` or `Safari/` (without the iOS markers)
The tagging logic lives in the filter addon and sets a flow metadata key (`gc_source: ios | web | unknown`) that downstream addons read.

### Credential File Integration
The credential extractor addon reuses `src.gamechanger.credential_parser.merge_env_file()` to write credentials. This ensures the same merge-not-overwrite behavior and `.env` format. The addon does NOT import `parse_curl` (no curl to parse -- it reads headers directly from the mitmproxy flow object).

### Security Considerations
- mitmproxy CA certificate: must be installed on the iPhone to intercept HTTPS. The `mitm.it` page handles this automatically when traffic flows through the proxy. The CA cert is generated on first run and stored in a Docker volume.
- The proxy service is dev-only (profile-gated). It is never deployed to production.
- Credentials extracted by the addon go to `.env` which is git-ignored.
- The mitmproxy addons directory (`mitmproxy/`) should be committed (it is code), but any captured data/logs should be git-ignored.

### File Layout
```
mitmproxy/                          # New top-level directory (committed)
  addons/
    __init__.py
    gc_filter.py                    # Domain filter + source tagging
    credential_extractor.py         # Token/credential extraction -> .env
    header_capture.py               # Header capture + parity report
    endpoint_logger.py              # API path/method logging
  config/
    mitmproxy-config.yaml           # mitmproxy configuration (if needed)
data/mitmproxy/                     # Runtime data (git-ignored)
  endpoint-log.jsonl                # Append-only endpoint log
  header-report.json                # Latest header parity report
  certs/                            # mitmproxy CA certificates (volume-mounted)
```

### Devcontainer Port Forwarding
`devcontainer.json` already forwards port 8080. This will need updating: forward 8080 (proxy), 8081 (mitmweb), and move Traefik dashboard to 8180. The `forwardPorts` array update is part of E-039-01.

## Open Questions
- Research spike will determine: are there existing mitmproxy addons for credential/header extraction that we can reuse or adapt?
- Should the endpoint logger produce JSONL (append-only) or overwrite a summary file? (Leaning JSONL for completeness, with a separate summary command.)
- Will the mitmproxy Docker image need additional Python dependencies (e.g., `python-dotenv` for `.env` writes)? Research spike should check what is available in the image.

## History
- 2026-03-04: Created
