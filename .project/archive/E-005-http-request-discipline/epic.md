<!-- synthetic-test-data -->
# E-005: HTTP Request Discipline

## Status
`COMPLETED`

## Overview
Build a centralized HTTP session layer that enforces consistent, browser-realistic request behavior across all GameChanger API calls (and any future integrations). Without this layer, every new crawler or client will reinvent headers, reinvent rate limiting, and risk presenting as a Python script rather than a real browser -- increasing the chance of blocks and making the codebase fragile to maintain.

## Background & Context
CLAUDE.md now formally specifies HTTP Request Discipline: all requests must present realistic browser headers, maintain session/cookie state, apply rate limiting with jitter, and follow human-plausible access patterns. This guidance was added after the user provided a real GameChanger curl example showing the full header set (sec-ch-ua, sec-fetch-* headers, realistic User-Agent, etc.) that the platform actually expects to see.

E-001-02 (the GameChanger HTTP client) was scoped before this discipline existed. It currently plans to handle auth injection but says nothing about User-Agent realism, cookie jar persistence, jitter, or the shared header profile. Left as-is, E-001-02 would ship a client with httpx defaults (User-Agent: `python-httpx/0.x.x`) -- exactly what CLAUDE.md prohibits.

This epic builds the shared HTTP infrastructure first, then retrofits E-001-02 to use it. The result is a single place to update the header profile when GameChanger changes their fingerprinting, a single place to tune rate limiting, and a clear pattern for any future scraping or API integration to follow.

## Goals
- A shared module (`src/http/session.py`) that produces configured httpx sessions with realistic browser headers, cookie jar, and rate-limiting/jitter behavior built in
- A canonical header configuration file (`src/http/headers.py`) with the full browser header set derived from the real GameChanger curl example, easy to update when the platform's expected fingerprint changes
- E-001-02's `GameChangerClient` updated to use this session factory instead of raw httpx -- no behavioral regression, just better defaults
- Tests that verify: correct headers are sent, auth tokens are never written to logs, rate limiting fires between requests, jitter is applied
- A pattern guide (`docs/http-integration-guide.md`) documenting how future integrations should use this layer

## Non-Goals
- Playwright or Selenium browser automation -- this epic is Python requests/httpx only
- Rotating User-Agents or anti-fingerprinting techniques -- we use one consistent, realistic profile per the discipline spec
- Automatic credential refresh -- that remains E-001's concern
- Proxy support or IP rotation -- out of scope
- Async session support -- sync first; async can come later if E-002 needs it

## Success Criteria
- `src/http/session.py` exports a `create_session()` factory that returns an httpx client pre-loaded with the canonical header set and cookie jar
- `src/http/headers.py` exports `BROWSER_HEADERS: dict[str, str]` containing at minimum: `User-Agent`, `Accept`, `Accept-Language`, `Accept-Encoding`, `sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform`, `sec-fetch-site`, `sec-fetch-mode`, `sec-fetch-dest`
- Running `pytest tests/test_http_session.py` passes, covering: headers present on request, auth token not logged at any log level, minimum delay between sequential requests, jitter applied (second request does not arrive at exactly delay_ms after first)
- `GameChangerClient` (E-001-02) uses `create_session()` -- confirmed by grep showing no bare `httpx.Client()` call in `src/gamechanger/client.py`. Auth uses `gc-token` header (not `Authorization: Bearer`).
- `docs/http-integration-guide.md` exists and covers: how to use `create_session()`, how to override specific headers, how to add auth, and the rate limiting contract

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-005-01 | Build canonical browser header configuration | DONE | None | - |
| E-005-02 | Build HTTP session factory with rate limiting and jitter | DONE | E-005-01 | - |
| E-005-03 | Verify GameChanger client session factory integration | DONE | E-005-02, E-001-02 | - |
| E-005-04 | Write header discipline tests | DONE | E-005-02 | - |
| E-005-05 | Write HTTP integration guide | DONE | E-005-02 | - |

## Technical Notes

### Module Layout
```
src/
  http/
    __init__.py
    headers.py        # BROWSER_HEADERS dict and any header-building helpers
    session.py        # create_session() factory
  gamechanger/
    client.py         # Updated to import create_session from src.http.session
```

### The Canonical Header Set (from user's curl example)
The GameChanger API example shows these headers are expected. This is the profile to replicate:

```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
Accept: application/json, text/plain, */*
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br, zstd
sec-ch-ua: "Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
sec-fetch-site: same-site
sec-fetch-mode: cors
sec-fetch-dest: empty
```

The Chrome version in User-Agent and sec-ch-ua should stay in sync. The macOS platform profile is intentional and consistent with the project operator's environment.

### Auth Injection Pattern
Auth credentials are NOT part of `BROWSER_HEADERS` -- they are injected by the consuming client (e.g., `GameChangerClient`) on top of the base session. This keeps the session factory reusable for unauthenticated requests and ensures credentials are never baked into shared config.

**GameChanger-specific pattern** (confirmed via API discovery -- see `docs/gamechanger-api.md`):
```python
session = create_session()
session.headers["gc-token"] = credentials["GAMECHANGER_AUTH_TOKEN"]     # NOT Authorization: Bearer
session.headers["gc-device-id"] = credentials["GAMECHANGER_DEVICE_ID"]  # 32-char hex, stable per device
session.headers["gc-app-name"] = "web"                                  # fixed value
```

GameChanger does NOT use `Authorization: Bearer`. Auth is carried in the custom `gc-token` header. The `gc-device-id` is a persistent device identifier that should be stored alongside credentials and reused across sessions.

### Rate Limiting Contract
`create_session()` accepts `min_delay_ms: int = 1000` and `jitter_ms: int = 500`. Between each request, the session sleeps for `min_delay_ms + random.uniform(0, jitter_ms)` milliseconds. This is enforced via a custom httpx event hook, not by the caller.

The jitter range means requests arrive between 1000ms and 1500ms apart by default -- human-plausible but not robotically identical.

### Logging Safety Rule
The session layer must never log header values. It may log:
- Request method and URL path (never full URL with query params if params contain tokens)
- Response status code and response time

It must NOT log:
- Any header value (Authorization, Cookie, or otherwise)
- Any query parameter values
- Any response body content

This is enforced in tests by asserting that no log record at any level contains credential-pattern strings such as "Bearer", "Cookie", or the `gc-token` value.

### Relationship to E-001
E-005-03 depends on E-001-02 being done (or being done in coordination). The cleanest approach is to write E-001-02 and E-005 in sequence: finish E-001-02 with its current bare httpx approach, then E-005-03 retrofits it. Alternatively, if E-001-02 has not yet been started, it can be written directly against `create_session()` -- in that case E-005-03 becomes a no-op and can be abandoned.

## Open Questions
- What Chrome version does the current GameChanger curl example show? -- **Answered**: Chrome 131 from the original capture (2026-02-28). Updated captures (2026-03-04) show Chrome 145. `src/http/headers.py` still has Chrome 131 -- a header refresh is needed (see Gaps below).
- Does GameChanger send `Origin` or `Referer` headers that should also be in the canonical set? -- **Answered**: Yes. `Referer: https://web.gc.com/` and `origin: https://web.gc.com` appear in multiple endpoint captures. `DNT: 1` also appears consistently. These are not yet in `BROWSER_HEADERS`. See Gaps below.
- Should `create_session()` support a context manager protocol? -- **Answered**: Yes, httpx.Client already supports this. `create_session()` returns an httpx.Client directly, so context manager usage works. Confirmed in E-005-02 AC-7.

## Gaps Identified During Refinement (2026-03-04)
These are outside E-005 scope but should be tracked:

1. **Chrome version stale in `src/http/headers.py`**: Headers show Chrome 131, but API captures from 2026-03-04 show Chrome 145. The integration guide documents the update process. This should be a small follow-up task.
2. **Missing headers in `BROWSER_HEADERS`**: `DNT: 1`, `Referer: https://web.gc.com/`, and `origin: https://web.gc.com` are present in API captures but not in the canonical header set. These could be added to `BROWSER_HEADERS` or handled per-request.
3. ~~**Integration guide examples use `Authorization: Bearer`**~~: **RESOLVED** (2026-03-04). Guide updated to use `gc-token` as the primary example with a note that the session factory is generic.

## History
- 2026-02-28: Created. Prompted by addition of HTTP Request Discipline section to CLAUDE.md and user providing a real GameChanger curl example.
- 2026-03-04: Refined E-005-03 based on API discovery progress. The GameChanger client was written directly against `create_session()` (not retrofitted), so E-005-03 changed from a retrofit story to a verification story. Updated epic Technical Notes to reflect `gc-token` auth pattern (not `Authorization: Bearer`), updated logging safety rule, resolved open questions, and documented three gaps for follow-up: Chrome version staleness in headers.py, missing DNT/Referer/Origin headers, and integration guide examples showing Bearer auth.
- 2026-03-04: **COMPLETED.** All 5 stories DONE (E-005-01 through E-005-05, with E-005-03 completing last as verification). Codex spec review remediation applied before final dispatch: corrected `Authorization: Bearer` to `gc-token` in E-005-04 AC-6, E-005-05 Technical Approach, and `docs/http-integration-guide.md`. Added AC-7 to E-005-03 to close the gap from E-005-04's skipped AC-6. 27 tests pass across `test_client.py` and `test_http_discipline.py`. Remaining gaps (Chrome 131->145, missing DNT/Referer/Origin) are tracked for follow-up. No documentation impact beyond the integration guide updates already applied during this dispatch.
