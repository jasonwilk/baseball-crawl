# E-039: mitmproxy Credential Sync and API Discovery

## Status
`COMPLETED`
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
- Stopping the proxy (`docker compose stop mitmproxy`) leaves other services running with no side effects

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-039-R-01 | Research: mitmproxy addon ecosystem | DONE | None | - |
| E-039-01 | mitmproxy Docker Compose service and shared filter | DONE | E-039-R-01 | - |
| E-039-02 | GameChanger credential extraction addon | DONE | E-039-01 | - |
| E-039-03 | Header capture and parity report | DONE | E-039-01 | - |
| E-039-04 | API endpoint discovery log | DONE | E-039-01 | - |
| E-039-06 | Operator CLI and documentation | DONE | E-039-01, E-039-03, E-039-04 | - |

**E-039-05 removed**: The shared `gc_filter.py` module (domain filtering + source detection) is now created in E-039-01 as infrastructure. Stories 02/03/04 import from it directly, eliminating the refactor-after-the-fact pattern. Source-aware credential logging (the only remaining AC from E-039-05) is absorbed into E-039-02 AC-7.

## Technical Notes

### Docker Compose Profile Strategy
The mitmproxy service uses a Docker Compose **profile** (`proxy`) so it does not start by default. `docker compose up -d` starts only the app/traefik/cloudflared services as today. `docker compose --profile proxy up -d` adds mitmproxy. This avoids port conflicts and resource waste when the proxy is not needed.

### Port Exposure
- **8080**: mitmproxy listen port (HTTP/HTTPS proxy). Must bind to `0.0.0.0` so the iPhone on the LAN can reach it. Note: this conflicts with the Traefik dashboard port (currently `8080:8080`). Resolution: move the Traefik dashboard to port `8180` (Traefik is rarely accessed directly; mitmproxy needs the well-known proxy port).
- **8081**: mitmweb UI (web interface for inspecting traffic). Bind to `0.0.0.0` for access from the host browser.

### Addon Architecture
mitmproxy addons are Python scripts loaded via `--scripts` flag. Each addon is a class with event hooks (`request()`, `response()`, etc.). The project will create addon scripts under `mitmproxy/addons/` (new top-level directory, dev-only). Key modules:
1. **gc_filter.py** -- shared utility module (pure Python, no mitmproxy imports) providing `is_gamechanger_domain(host) -> bool` and `detect_source(user_agent) -> str` ("ios"/"web"/"unknown"). Created in E-039-01 as infrastructure; all addon stories import from it.
2. **credential_extractor.py** -- watches for `gc-token`, `gc-device-id`, `gc-signature` headers; writes to `.env` via the existing `merge_env_file()` function from `src/gamechanger/credential_parser.py`. Logs traffic source alongside credential updates.
3. **header_capture.py** -- captures all headers from GameChanger requests, groups by source (iOS/web), writes a diff report.
4. **endpoint_logger.py** -- logs every unique (method, path, content-type) tuple seen on GameChanger domains.

### Traffic Source Detection (iOS vs. Web)
The User-Agent header reliably distinguishes iOS app traffic from web browser traffic:
- iOS: contains `GameChanger/` or `CFNetwork/` or `Darwin/`
- Web: contains `Chrome/` or `Firefox/` or `Safari/` (without the iOS markers)
The tagging logic lives in the filter addon and sets a flow metadata key (`gc_source: ios | web | unknown`) that downstream addons read.

### Container Volume Mounts (E-039-01 Infrastructure)
The mitmproxy container needs access to project files for addon imports and data writes. All volume mounts are configured in E-039-01 so addon stories (02/03/04) do not need to modify `docker-compose.yml`:
- **Project root** mounted at `/app` -- provides `sys.path` access so addons can `import src.gamechanger.credential_parser` and `import src.http.headers`.
- **`.env` file** accessible at `/app/.env` (via project root mount) -- addons write credentials here using `merge_env_file("/app/.env", ...)`.
- **`data/mitmproxy/`** mounted or accessible at `/app/data/mitmproxy/` -- addons write header reports and endpoint logs here.

### Credential File Integration
The credential extractor addon reuses `src.gamechanger.credential_parser.merge_env_file()` to write credentials, passing `/app/.env` as the `env_path` argument. This ensures the same merge-not-overwrite behavior and `.env` format. The addon does NOT import `parse_curl` (no curl to parse -- it reads headers directly from the mitmproxy flow object). Credentials in `.env` are NOT source-tagged (one `GAMECHANGER_AUTH_TOKEN`, not per-source keys). The source is logged for operator visibility but does not affect the `.env` schema.

### Security Considerations
- mitmproxy CA certificate: must be installed on the iPhone to intercept HTTPS. The `mitm.it` page handles this automatically when traffic flows through the proxy. The CA cert is generated on first run and stored in a Docker volume.
- The proxy service is dev-only (profile-gated). It is never deployed to production.
- Credentials extracted by the addon go to `.env` which is git-ignored.
- The mitmproxy addons directory (`mitmproxy/`) should be committed (it is code), but any captured data/logs should be git-ignored.

### File Layout
```
proxy/                              # Top-level directory (committed); renamed from mitmproxy/ to avoid namespace collision
  addons/
    __init__.py
    gc_filter.py                    # Domain filter + source detection (E-039-01)
    loader.py                       # Single-script addon loader (E-039-01)
    credential_extractor.py         # Token/credential extraction -> .env (E-039-02)
    header_capture.py               # Header capture + parity report (E-039-03)
    endpoint_logger.py              # API path/method logging (E-039-04)
data/mitmproxy/                     # Runtime data (git-ignored via data/ rule)
  endpoint-log.jsonl                # Append-only endpoint log
  header-report.json                # Latest header parity report
# CA certificates: stored in a named Docker volume (mitmproxy-certs),
# NOT in data/mitmproxy/. Persisted across container restarts automatically.
```

### Devcontainer Port Forwarding
`devcontainer.json` already forwards port 8080. This will need updating: forward 8080 (proxy), 8081 (mitmweb), and move Traefik dashboard to 8180. The `forwardPorts` array update is part of E-039-01.

## Open Questions
- Research spike will determine: are there existing mitmproxy addons for credential/header extraction that we can reuse or adapt?
- Should the endpoint logger produce JSONL (append-only) or overwrite a summary file? (Leaning JSONL for completeness, with a separate summary command.)
- Will the mitmproxy Docker image need additional Python dependencies (e.g., `python-dotenv` for `.env` writes)? Research spike should check what is available in the image.

## History
- 2026-03-04: Created
- 2026-03-04: Spec review (PM + Codex). 13 findings addressed: E-039-05 absorbed (gc_filter.py moved to E-039-01 infrastructure), E-039-06 routing/deps/stop-semantics fixed, volume mounts centralized in E-039-01, .env path specified, cert location clarified, redundant .gitignore AC removed, DoD syntax fixed, header-report.json schema defined.
- 2026-03-04: Dispatch started. R-01 (research spike) dispatched first.
- 2026-03-04: Second Codex spec review -- 6 findings triaged. 2 accepted: E-039-01 AC-2 refined with concrete healthcheck verification method; E-039-03 AC-1/AC-3/AC-4 updated to account for `"unknown"` traffic source from gc_filter.detect_source(). 4 dismissed: P1 api-scout consultation (passive dev tooling, no API behavior change); P1 claude-architect consultation (E-039-06 already routes to claude-architect at dispatch); P2 E-039-04 AC-4 "unique" conflict (no conflict -- append-only log with downstream dedup is consistent); P3 .gitignore AC-8 (already a verification check, not new behavior).
- 2026-03-05: R-01 research spike completed. Key findings: build all addons from scratch, use mitmweb variant, stock Docker image sufficient (no custom Dockerfile), PYTHONPATH=/app for imports, loader.py pattern for multi-addon loading. No changes to epic Technical Notes required (findings align with existing design). E-039-01 dispatched.
- 2026-03-05: E-039-01 (infrastructure) completed -- Docker Compose service, gc_filter, loader. E-039-02/03/04 dispatched in parallel.
- 2026-03-05: E-039-02 (credentials), E-039-03 (headers), E-039-04 (endpoints) all completed in parallel. E-039-06 dispatched to claude-architect.
- 2026-03-05: E-039-06 (CLI/docs) completed. All stories DONE.
- 2026-03-05: Codex code review -- 4 findings. Remediated 3: P1 namespace collision (renamed mitmproxy/ -> proxy/ to avoid shadowing real mitmproxy package), P1 proxy-endpoints.sh chronological ordering fix, P6 type hints in endpoint_logger.py. Dismissed 1: P3 read-write volume mount (dev-only tool, complexity not warranted). 706 tests pass.
- 2026-03-05: Documentation assessment: triggers fired (new feature, deployment config change), but documentation was built into E-039-06 (docs/admin/mitmproxy-guide.md created, CLAUDE.md Commands updated). No additional docs-writer dispatch needed.
- 2026-03-05: Epic COMPLETED.
