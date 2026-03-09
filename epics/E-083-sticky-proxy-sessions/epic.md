# E-083: Bright Data Sticky Proxy Sessions

## Status
`READY`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Add automatic sticky session support to the Bright Data proxy layer so that all requests within a single crawl run use the same proxy IP address -- matching how a real user browses GameChanger from a single location. Currently each request gets a random IP from the Bright Data pool, which is a detectable signal of automated traffic.

## Background & Context
E-079 just fixed Bright Data proxy routing (the proxy was silently broken since E-046). Now `bb proxy check` confirms both web (residential) and mobile zones are routing correctly. However, each request gets a different IP from the Bright Data pool. The user wants sticky sessions so requests within a crawl session use the same IP.

**Bright Data sticky session mechanism**: Append `-session-<id>` to the username in the proxy URL. The session ID must be alphanumeric only. Same session ID = same proxy peer IP. For residential proxies, the IP persists for up to 5 minutes idle (no keep-alive needed since our rate-limiting delays are 1-2 seconds). If the peer becomes unavailable, Bright Data returns 502 on the first request then auto-assigns a new peer on the next request.

**Current architecture**: Proxy URLs are stored in `.env` as `PROXY_URL_WEB` and `PROXY_URL_MOBILE` (format: `http://USERNAME:PASS<at>HOST:PORT`). The username contains zone and country params: `brd-customer-XXX-zone-YYY-country-us`. `resolve_proxy_from_dict()` in `src/http/session.py` reads these from a dotenv dict. `create_session()` takes a `proxy_url` parameter and passes it to `httpx.Client`. `GameChangerClient.__init__` calls `resolve_proxy_from_dict()` and passes the URL to `create_session()`.

**Expert consultation completed**:
- **Software Engineer**: Reviewed design, recommended 4 refinements: (1) drop `session_id` from `get_proxy_config()` (no caller), (2) use `secrets.token_hex(8)` not `token_urlsafe`, (3) private `_inject_session_id()` helper with proper URL parsing and password re-encoding, (4) tighten log safety AC to cover injected URLs. All applied.
- **claude-architect**: No consultation required -- E-083-02 is a documentation addition to an existing CLAUDE.md section (adding sticky session behavior description), not an architectural decision. Routing to claude-architect for dispatch is correct per context-layer file rules.

## Goals
- All requests within a single `GameChangerClient` instance use the same Bright Data proxy IP (sticky session)
- Different client instances naturally get different IPs (session ID is unique per instance)
- No operator intervention required -- sticky sessions are automatic when proxy is enabled
- `bb proxy check` continues to work as a one-shot diagnostic (no sticky session needed)

## Non-Goals
- Keep-alive mechanism (rate-limiting delays of 1-2s are well within the 5-minute idle timeout)
- Configurable session duration or manual session ID override
- Session persistence across process restarts
- Sticky sessions for the mitmproxy traffic-capture tool (separate system, Mac host)
- Monitoring or alerting when Bright Data rotates a peer (502 -> new peer is handled transparently by Bright Data)

## Success Criteria
- When `PROXY_ENABLED=true`, all requests from a single `GameChangerClient` instance exit from the same IP address
- Different `GameChangerClient` instances use different session IDs (and thus different IPs)
- `bb proxy check` works without sticky sessions (diagnostic tool, one-shot)
- No credentials or proxy URLs leak into logs
- Existing proxy tests continue to pass
- CLAUDE.md documents the sticky session behavior

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-083-01 | Add sticky session injection to proxy URL resolution | TODO | None | - |
| E-083-02 | Document sticky session behavior in CLAUDE.md | TODO | E-083-01 | - |

## Dispatch Team
- software-engineer
- claude-architect

## Technical Notes

### Proxy URL Username Format
Bright Data proxy URLs use the format: `http://USERNAME:PASS<at>HOST:PORT` where USERNAME is `brd-customer-XXX-zone-YYY-country-us`. To enable sticky sessions, append `-session-<id>` to the username: `brd-customer-XXX-zone-YYY-country-us-session-abc123`.

### Session ID Design
- Generated once per `GameChangerClient` instance (in `__init__`), not per-request or per-crawl-run. This is the natural boundary: one client = one crawl session = one IP.
- Must be alphanumeric only (Bright Data requirement).
- Should be short but unique enough to avoid collisions across concurrent runs. A random alphanumeric string is sufficient.

### Injection Point
The session ID should be injected into the proxy URL at the resolution layer -- the functions that read proxy URLs from env vars and return them to callers. This keeps the injection centralized rather than scattered across callers.

`resolve_proxy_from_dict()` accepts an optional `session_id` parameter. When provided, it injects `-session-<id>` into the URL's username before returning it. `get_proxy_config()` is NOT modified -- it reads from `os.environ` and has no caller that needs sticky sessions.

`GameChangerClient.__init__` generates the session ID and passes it to `resolve_proxy_from_dict()`. `bb proxy check` (in `proxy_check.py`) does NOT pass a session ID -- it uses the default rotating behavior, which is correct for a diagnostic tool.

### Session ID Generation
Use `secrets.token_hex(8)` to produce a 16-character lowercase hex string. This satisfies Bright Data's alphanumeric-only requirement. Do NOT use `secrets.token_urlsafe()` (contains `-` and `_` which are not alphanumeric).

### URL Manipulation
The proxy URL format is `http://USERNAME:PASS<at>host:port`. The session suffix goes into the USERNAME portion only. Extract a private `_inject_session_id(proxy_url, session_id)` helper. Use `urllib.parse.urlparse()` to parse the URL, modify the username, and reconstruct it. When rebuilding the netloc, re-percent-encode `parsed.password` with `urllib.parse.quote()` to handle special characters safely. Never use string concatenation on URLs containing credentials.

### 502 Handling
When a sticky peer becomes unavailable, Bright Data returns 502 on the first request, then auto-assigns a new peer on the next request using the same session ID. The existing retry logic in `GameChangerClient._get_with_retries()` and `get_paginated()` already handles 5xx with exponential backoff (3 retries), so this case is covered automatically. No additional handling needed.

### Files Overview
- `src/http/session.py` -- core changes (session ID injection in proxy URL resolution)
- `src/gamechanger/client.py` -- generate session ID in `__init__`, pass to `resolve_proxy_from_dict()`
- `tests/test_http_session.py` -- new tests for session ID injection
- `tests/test_client.py` -- verify client passes session ID
- `tests/test_proxy_check.py` -- verify proxy check does NOT use sticky sessions
- `CLAUDE.md` -- document sticky session behavior

## Open Questions
None.

## History
- 2026-03-09: Created. SE consultation: (1) Drop `session_id` from `get_proxy_config()` -- no caller needs it; (2) Use `secrets.token_hex(8)` for session IDs, not `token_urlsafe`; (3) Extract private `_inject_session_id()` helper with proper URL parsing and password re-encoding; (4) Tighten AC-9 log safety to cover injected URL, not just raw URL. All recommendations applied.
- 2026-03-09: Codex spec review triage. 3 findings REFINED: AC-8 reworded from "without modification" to regression statement (was ambiguous given AC-9 requires new tests in same files); AC-6 reworded as explicit regression guard (already true in current code); E-083-02 DoD replaced with context-layer-appropriate checklist (removed inapplicable "tests written" and "code follows style"). 2 findings DISMISSED: missing CA consultation (documentation addition, not architectural decision -- noted in epic); generic E-083-01 DoD (template intentional, ACs carry the contract).
