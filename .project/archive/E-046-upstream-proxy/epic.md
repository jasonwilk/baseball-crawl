# E-046: Upstream Proxy Support

## Status
`COMPLETED`

## Overview
Add dual-zone upstream proxy support so Python crawlers and mitmproxy route traffic through Bright Data proxy zones matched to their HTTP header profile. Two env vars (`PROXY_URL_WEB`, `PROXY_URL_MOBILE`) map to the existing `profile="web"` and `profile="mobile"` session profiles. A master `PROXY_ENABLED` switch controls proxy for all outbound paths. This enables the operator to route web-profile traffic through a residential proxy and mobile-profile traffic through a mobile proxy.

mitmproxy supports both profiles: the operator selects which profile to use at start time via `./start.sh --profile mobile` (default) or `./start.sh --profile web`. The selected profile determines which upstream proxy URL (`PROXY_URL_MOBILE` or `PROXY_URL_WEB`) is used for upstream routing.

## Background & Context
GameChanger may throttle or block requests from known datacenter/home IP ranges. Routing traffic through an external proxy mitigates this. The operator uses Bright Data with two proxy zones:

- **Residential zone** (`baseball_crawl_residential`) -- for `profile="web"` sessions (Chrome browser fingerprint)
- **Mobile zone** (`baseball_crawl_mobile`) -- for `profile="mobile"` sessions (iOS Odyssey app fingerprint)

Both zones share the same Bright Data superproxy host and port (`brd.superproxy.io:33335`). The zone is selected by the username embedded in the proxy URL. The httpx proxy URL format is `http://USER:PASS@HOST:PORT`.

Two outbound paths exist:
1. **Python crawlers** -- `create_session()` in `src/http/session.py` produces `httpx.Client` instances used by all crawlers and the GameChanger client. The `profile` parameter already selects web vs. mobile headers; now it also selects the matching proxy zone.
2. **Host-based mitmproxy** -- runs as a standalone Docker Compose stack in `proxy/` on the Mac host (migrated from the project Docker Compose stack by E-048). mitmproxy can intercept either iPhone traffic (mobile profile) or browser traffic (web profile). The operator selects which profile at start time; the entrypoint maps the profile to the corresponding proxy URL.

Both must respect the same proxy configuration. When `PROXY_ENABLED` is unset or `false`, current behavior is preserved (no proxy).

SE consultation completed (2026-03-06): Two full URLs (`PROXY_URL_WEB`, `PROXY_URL_MOBILE`) preferred over decomposed host/port/user/pass because httpx and mitmproxy both consume a single URL string. Fewer env vars, no reassembly logic, self-documenting profile-to-URL mapping.

## Goals
- A single `.env` configuration controls proxy for both Python crawlers and mitmproxy
- Profile-aware proxy routing: web sessions use residential proxy, mobile sessions use mobile proxy
- Proxy URLs (which contain credentials) are never logged or exposed
- Graceful degradation: misconfiguration warns but does not crash

## Non-Goals
- Per-host proxy routing (all traffic or no traffic)
- Proxy provider abstraction or multi-provider support
- Proxy health checking or failover
- Automatic zone detection (profile-to-zone mapping is explicit)

## Success Criteria
- `PROXY_ENABLED=true` + valid `PROXY_URL_WEB` routes web-profile Python crawler traffic through the residential proxy
- `PROXY_ENABLED=true` + valid `PROXY_URL_MOBILE` routes mobile-profile Python crawler traffic through the mobile proxy
- `PROXY_ENABLED=true` + valid `PROXY_URL_MOBILE` + `./start.sh` (or `./start.sh --profile mobile`) starts mitmproxy in upstream mode with the mobile proxy
- `PROXY_ENABLED=true` + valid `PROXY_URL_WEB` + `./start.sh --profile web` starts mitmproxy in upstream mode with the residential proxy
- `PROXY_ENABLED=false` (or unset) preserves current no-proxy behavior for both paths
- `PROXY_ENABLED=true` + missing URL for a given profile logs a WARNING and proceeds without proxy for that profile
- Proxy URLs never appear in log output
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-046-01 | Python crawler proxy support | DONE | None | software-engineer |
| E-046-02 | mitmproxy upstream mode | DONE | None | software-engineer |

## Dispatch Team
- software-engineer

## Technical Notes

### Proxy Configuration
- **Env vars**:
  - `PROXY_ENABLED` (string: `true`/`false`, default unset = disabled) -- master on/off switch
  - `PROXY_URL_WEB` (full URL including credentials, format: `http://USER:PASS@host:port`) -- residential proxy for web-profile sessions
  - `PROXY_URL_MOBILE` (full URL including credentials, format: `http://USER:PASS@host:port`) -- mobile proxy for mobile-profile sessions
- **Profile-to-URL mapping**: `get_proxy_config(profile="web")` reads `PROXY_URL_WEB`; `get_proxy_config(profile="mobile")` reads `PROXY_URL_MOBILE`. The env var name is derived from the profile name: `PROXY_URL_{profile.upper()}`.
- **Credential safety**: Both proxy URLs contain embedded credentials (Bright Data zone passwords). They must never appear in log output, error messages, or debug traces. Use the same discipline as `GC_TOKEN`.
- **Bright Data URL format**: `http://brd-customer-{CUSTOMER_ID}-zone-{ZONE}-country-us:{ZONE_PASSWORD}@HOST:PORT`. Both zones share the same host:port; the zone is selected by the username.

### httpx Proxy API (v0.28.x)
- `httpx.Client(proxy="http://...")` -- singular `proxy` kwarg (string). Routes all traffic through the proxy.
- When `proxy` is `None` (default), no proxy is used. This is the current behavior.
- httpx handles `http://user:pass@host:port` proxy auth natively -- no special handling needed.
- `create_session()` must pass `trust_env=False` to `httpx.Client()` to prevent httpx from reading system `HTTP_PROXY`/`HTTPS_PROXY` env vars. Proxy routing is exclusively controlled by `PROXY_ENABLED` + `PROXY_URL_*`.

### mitmproxy Upstream Mode (Host-Based Stack)
- E-048 migrated mitmproxy to a standalone `proxy/` directory on the Mac host. The proxy stack has its own `proxy/docker-compose.yml`, start/stop/status scripts, and `.env` file.
- mitmproxy can intercept either iPhone traffic (mobile profile) or browser traffic (web profile). The operator selects which profile at start time via `./start.sh --profile <name>` (default: `mobile` for backward compatibility).
- **Profile selection mechanism**: `start.sh` accepts `--profile mobile` (default) or `--profile web`. It sets `MITMPROXY_PROFILE` as an environment variable and passes it to `docker compose up`. The entrypoint script maps the profile to the corresponding proxy URL env var: `PROXY_URL_${MITMPROXY_PROFILE^^}` (e.g., `mobile` -> `PROXY_URL_MOBILE`, `web` -> `PROXY_URL_WEB`).
- `mitmweb --mode upstream:http://proxy-url:port` starts mitmproxy in upstream proxy mode, forwarding all traffic through the specified proxy.
- When no `--mode` is specified, mitmproxy runs as a regular intercepting proxy (current behavior).
- A wrapper entrypoint script (`proxy/proxy-entrypoint.sh`) replaces the static `mitmweb` entrypoint. It reads `MITMPROXY_PROFILE` (default: `mobile`), resolves the corresponding `PROXY_URL_*` env var, and conditionally adds `--mode upstream:${PROXY_URL}` when `PROXY_ENABLED=true` and the URL is set. This avoids Docker Compose variable interpolation in `command:`, which would inline credentials into `docker compose config` output.
- mitmproxy's `--mode upstream:http://user:pass@host:port` supports embedded credentials in the same format as httpx.
- Only one mitmproxy instance runs at a time (same ports 8080/8081). To switch profiles, stop and restart with the new profile argument. Running both simultaneously is a non-goal.

### `.env` Path Resolution and Credential Safety
The proxy stack reads `proxy/.env` via its `env_file` directive (relative to `proxy/docker-compose.yml`). However, `PROXY_ENABLED`, `PROXY_URL_WEB`, and `PROXY_URL_MOBILE` are documented in the project root `.env.example`. To avoid requiring the operator to duplicate vars into two `.env` files, E-046-02 adds `../.env` to the `env_file` list in `proxy/docker-compose.yml` so the proxy container inherits vars from both the root `.env` and `proxy/.env`. Both entries are `required: false`. The `proxy/.env` is listed second for override precedence.

**Credential safety model**: The entrypoint wrapper keeps proxy URLs out of the compose `command:` block and out of host process listings (`ps -ef`). Note that `docker compose config` will resolve and display env_file values under `environment:` regardless of whether they come from `env_file` or the `environment:` block — the distinction does NOT prevent exposure in compose config output. The real protection is: credentials stay in env vars read at runtime by the entrypoint script, never baked into command-line args visible in process listings. This is acceptable for a local dev tool on the operator's own machine.

`MITMPROXY_PROFILE` is set by `start.sh` and passed via the `environment:` block. It contains no credentials (just the string `mobile` or `web`), so inlining it is safe.

### `.env.example` Format
```
# ---------------------------------------------------------------------------
# Upstream Proxy (Bright Data)
# ---------------------------------------------------------------------------

# Master switch: set to "true" to route traffic through Bright Data proxies.
# When false or unset, all traffic goes direct (no proxy).
# Both Python crawlers and mitmproxy respect this setting.
# PROXY_ENABLED=false

# Residential proxy URL for web-profile sessions (Chrome browser fingerprint).
# Format: http://USER:PASS@HOST:PORT
# Used by Python crawlers when profile="web" and by mitmproxy --profile web.
# PROXY_URL_WEB=

# Mobile proxy URL for mobile-profile sessions (iOS Odyssey app fingerprint).
# Format: http://USER:PASS@HOST:PORT
# Used by Python crawlers when profile="mobile" and by mitmproxy --profile mobile.
# PROXY_URL_MOBILE=
```

### File Ownership (Parallel Safety)
- **E-046-01** modifies: `src/http/session.py`, `tests/test_http_session.py`, `.env.example`
- **E-046-02** modifies: `proxy/docker-compose.yml`, `proxy/start.sh`, `proxy/status.sh`; creates: `proxy/proxy-entrypoint.sh`
- No file conflicts -- stories can be dispatched in parallel.

## Open Questions
None.

## History
- 2026-03-05: Created. Set to READY.
- 2026-03-06: Refined to account for E-048 (host proxy migration). E-046-02 fully rewritten -- all file references, commands, and technical approach updated for the standalone `proxy/` stack. SE consulted on approach; wrapper entrypoint recommended over Docker Compose variable substitution for credential safety.
- 2026-03-06: Spec review triage. 5 findings reviewed: 3 REFINED (Finding 1 -- E-046-01 now auto-wires env vars into create_session() so all callers gain proxy support without code changes; Finding 2 -- removed PROXY_URL from environment: block, env_file-only injection prevents credential exposure in docker compose config; Finding 5 -- both env_file entries marked required: false), 1 REFINED-MINOR (Finding 4 -- added AC-8 to E-046-01 explicitly preserving dual-profile behavior from E-049), 1 DISMISSED (Finding 3 -- PROXY_URL in process args is inherent to mitmproxy's --mode upstream:URL; acceptable for local dev tool on operator's own machine). Epic remains READY.
- 2026-03-06: Major refinement -- dual-zone proxy support. User selected Bright Data with two zones (residential for web profile, mobile for mobile profile). Single PROXY_URL replaced with PROXY_URL_WEB + PROXY_URL_MOBILE. SE consultation: two full URLs preferred over decomposed host/port/user/pass (httpx and mitmproxy both consume single URL strings; fewer vars, no reassembly). get_proxy_config() now accepts profile param. mitmproxy uses PROXY_URL_MOBILE specifically (intercepts iPhone traffic). All three files (epic, E-046-01, E-046-02) updated. Non-goal revised: "Mobile vs. residential proxy distinction in code" removed (now a goal). Epic remains READY.
- 2026-03-06: Credential safety model corrected -- `docker compose config` exposes env_file values regardless of injection method. Real protection is keeping creds out of command-line args visible in `ps -ef`. Acceptable for local dev tool.
- 2026-03-06: Dual-profile mitmproxy support. E-046-02 rewritten: `./start.sh` now accepts `--profile mobile|web` (default: mobile). Entrypoint reads `MITMPROXY_PROFILE` and maps to `PROXY_URL_${PROFILE}`. Both profiles share the same ports (one instance at a time). `start.sh` and `status.sh` updated to show active profile. Added `proxy/start.sh` to E-046-02 file list. Epic remains READY.
- 2026-03-06: SE technical review. 8 findings triaged: 7 REFINED, 1 DISMISSED. HIGH: (1) Corrected false env_file credential-safety claim in AC-4/AC-6 -- docker compose config exposes env_file vars; real protection is keeping creds out of command args; (2) Added AC-11 for malformed URL scheme validation in get_proxy_config(). MEDIUM: (3) Added mock.patch guidance for verifying proxy kwarg in tests; (4) Added trust_env=False requirement to prevent httpx reading system HTTP_PROXY vars; (5) Added double-quoting for bash variable expansions in entrypoint script. LOW: (6) Added type annotation note for sentinel pattern; (7) Fixed inaccurate "Python one-liner" note. DISMISSED: (8) .env.example convention -- no issue. Epic remains READY.
- 2026-03-06: Dispatched both stories in parallel (no file conflicts). Both completed successfully.
- 2026-03-06: Codex post-dev review. 2 findings, both fixed: (1) P1 Bug -- proxy-entrypoint.sh PROXY_ENABLED comparison was case-sensitive, inconsistent with Python's case-insensitive parsing; fixed by normalizing with tr/xargs. (2) P2 Missing test -- added TestTrustEnvDisabled to verify trust_env=False is passed to httpx.Client(). 35 session tests pass.
- 2026-03-06: COMPLETED. All acceptance criteria verified. Documentation impact: docs/admin/mitmproxy-guide.md needs update to document --profile flag on start.sh and upstream proxy mode. Deferred to separate docs-writer dispatch (not blocking archive).
