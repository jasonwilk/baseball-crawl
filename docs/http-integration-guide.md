<!-- synthetic-test-data -->
# HTTP Integration Guide

Every HTTP request in this project -- API calls, scrapers, anything that touches the network -- goes through a shared session factory that handles browser headers, rate limiting, and cookie persistence. This guide shows how to use it.

Policy lives in the CLAUDE.md "HTTP Request Discipline" section. This guide covers implementation.

## Quick Start

```python
from src.http.session import create_session

# 1. Create a session
session = create_session()

# 2. Inject auth credentials (GameChanger uses gc-token, not Authorization: Bearer)
session.headers["gc-token"] = token
session.headers["gc-device-id"] = device_id
session.headers["gc-app-name"] = "web"

# 3. Make requests -- rate limiting happens automatically
response = session.get("https://api.gc.com/teams/123")
data = response.json()
```

The session is an `httpx.Client`. Use it as you would any httpx client: `.get()`, `.post()`, `.request()`, context manager, etc.

```python
with create_session() as session:
    session.headers["gc-token"] = token
    session.headers["gc-device-id"] = device_id
    session.headers["gc-app-name"] = "web"
    response = session.get("https://api.gc.com/teams/123")
```

## The Browser Header Profile

`src/http/headers.py` exports `BROWSER_HEADERS: dict[str, str]` -- a set of 10 headers captured from a real Chrome browser session. Every session created by `create_session()` sends these headers on every request.

The headers include:

| Header | Purpose |
|--------|---------|
| `User-Agent` | Chrome 131 on macOS |
| `Accept` | `application/json, text/plain, */*` |
| `Accept-Language` | `en-US,en;q=0.9` |
| `Accept-Encoding` | `gzip, deflate, br, zstd` |
| `sec-ch-ua` | Chrome 131 client hint |
| `sec-ch-ua-mobile` | `?0` (not mobile) |
| `sec-ch-ua-platform` | `"macOS"` |
| `sec-fetch-site` | `same-site` |
| `sec-fetch-mode` | `cors` |
| `sec-fetch-dest` | `empty` |

### Updating the Chrome Version

When the Chrome version in `BROWSER_HEADERS` falls more than 2 major versions behind current stable:

1. Open a real browser session to GameChanger
2. Capture a request as a curl command from browser DevTools
3. Update the `User-Agent` and `sec-ch-ua` values in `src/http/headers.py`
4. Keep the version numbers in sync between `User-Agent` and `sec-ch-ua`

Do NOT add credentials (`Authorization`, `Cookie`, session tokens) to `BROWSER_HEADERS`. Auth is injected per-session by the caller.

## Rate Limiting and Jitter

Rate limiting is enforced automatically by the session via an httpx response event hook. After every response, the session sleeps for `min_delay_ms + random(0, jitter_ms)` milliseconds before the next request can proceed.

**Defaults:**
- `min_delay_ms`: 1000 (1 second minimum between requests)
- `jitter_ms`: 500 (up to 0.5 seconds of random additional delay)

**Effective range:** Each request is followed by a 1.0--1.5 second delay.

**Overriding defaults:**

```python
# Slower pace for aggressive endpoints
session = create_session(min_delay_ms=2000, jitter_ms=1000)

# Faster pace for batch/internal work (use with care)
session = create_session(min_delay_ms=500, jitter_ms=200)
```

**Callers must NOT add their own sleeps.** The session handles all timing. Adding `time.sleep()` between requests doubles the delay and defeats the jitter pattern. If the default timing is wrong for your use case, override the parameters at session creation.

## Auth Injection Pattern

Auth credentials are never baked into the session factory. Inject them after creating the session.

**GameChanger** uses custom headers (not `Authorization: Bearer`):

```python
session = create_session()

# GameChanger auth headers
session.headers["gc-token"] = credentials["GAMECHANGER_AUTH_TOKEN"]
session.headers["gc-device-id"] = credentials["GAMECHANGER_DEVICE_ID"]
session.headers["gc-app-name"] = "web"
```

The session factory is generic -- other integrations may use different auth patterns (e.g., `Authorization: Bearer`). The pattern above is specific to GameChanger, which is currently the only consumer.

Keep credentials out of logs and source code (per CLAUDE.md "Security Rules").

## Cookie Jar

Each session has a persistent `httpx.Cookies()` cookie jar. `Set-Cookie` response headers are automatically captured and replayed on subsequent requests to matching domains.

You do not need to manage cookies manually. If a login endpoint returns a session cookie, subsequent requests through the same session will include it.

If you need to pre-set a cookie:

```python
session = create_session()
session.cookies.set("session_id", "abc123", domain="gc.com")
```

Each call to `create_session()` creates a fresh, empty cookie jar. Cookies are not shared between sessions.

## Adding a New Integration

Checklist for any new HTTP integration (API client, scraper, data fetcher):

1. **Call `create_session()`** -- do not construct `httpx.Client()` directly
2. **Inject credentials after session creation** -- bearer tokens, API keys, cookies
3. **Do not add manual delays** -- no `time.sleep()`, no `asyncio.sleep()`, the session handles rate limiting
4. **Do not log request or response headers** -- headers contain auth credentials and browser fingerprints (per CLAUDE.md "Security Rules")
5. **Mock at the transport layer in tests** -- use `httpx.MockTransport`, not by patching `create_session()` itself

## Testing New Integrations

Mock at the httpx transport layer so your tests verify that your code uses the session correctly without making real network calls:

```python
import httpx
from src.http.session import create_session


def test_my_integration():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "gc-token" in request.headers
        return httpx.Response(200, json={"team": "LSB Varsity"})

    session = create_session(min_delay_ms=0, jitter_ms=0)
    session._transport = httpx.MockTransport(handler)

    session.headers["gc-token"] = "test-token"
    session.headers["gc-device-id"] = "abc123"
    session.headers["gc-app-name"] = "web"
    response = session.get("https://api.gc.com/teams/123")

    assert response.status_code == 200
    assert response.json()["team"] == "LSB Varsity"
```

Set `min_delay_ms=0, jitter_ms=0` in tests to eliminate rate-limiting sleeps.

The mock transport receives the full request including `BROWSER_HEADERS`, so you can assert on header presence if needed. Never assert on exact header values in unit tests -- integration tests cover that.

## What Not to Do

**Do not construct bare httpx clients:**

```python
# WRONG -- bypasses headers, rate limiting, and cookie jar
client = httpx.Client()
client.get("https://api.gc.com/data")

# RIGHT
session = create_session()
session.get("https://api.gc.com/data")
```

**Do not add manual sleeps:**

```python
# WRONG -- doubles delay, defeats jitter
response = session.get(url)
time.sleep(1.5)
next_response = session.get(next_url)

# RIGHT -- session handles timing automatically
response = session.get(url)
next_response = session.get(next_url)
```

**Do not log headers:**

```python
# WRONG -- leaks credentials and fingerprint
logger.info("Request headers: %s", response.request.headers)

# RIGHT -- log URL path and status only
logger.info("GET %s -> %d", response.request.url.path, response.status_code)
```

**Do not put credentials in `BROWSER_HEADERS`:**

```python
# WRONG -- shared across all sessions, appears in source code
BROWSER_HEADERS["gc-token"] = token

# RIGHT -- inject on the session instance
session.headers["gc-token"] = token
```
