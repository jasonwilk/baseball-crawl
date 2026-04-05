---
paths:
  - "src/http/**"
  - "src/gamechanger/**"
  - "src/pipeline/**"
  - "src/llm/**"
  - "scripts/*crawl*"
  - "scripts/*fetch*"
---

# HTTP Request Discipline

All HTTP requests to GameChanger -- whether API calls or web scraping -- must present as a normal user on a real browser. We are automating legitimate user work, and our traffic should honestly reflect that.

## Headers & Identity

- Use a realistic `User-Agent` string (e.g., Chrome or Firefox on macOS/Windows). Never send `python-requests/x.x.x`, `httpx`, or similar library defaults.
- Include standard browser headers: `Accept`, `Accept-Language`, `Accept-Encoding`, `Referer`/`Origin` where appropriate.
- Store the canonical header set in a shared module so all HTTP code uses the same defaults.

## Session Behavior

- Maintain cookie jars across requests within a session. Do not start a fresh cookieless request mid-flow.
- Reuse the same `User-Agent` and header profile for the duration of a session -- do not randomize per-request.
- Handle redirects and set-cookie responses the way a browser would.

## Rate Limiting & Timing

> **Scope**: These rate limits apply to production and operator HTTP sessions -- code in `src/` and `scripts/` that makes real network requests. Test code mocks HTTP at the transport layer and is not subject to rate limiting rules.

- Implement rate limiting between requests (minimum 1 second delay).
- Use exponential backoff for retries on failure (max 3 retries).
- Respect any `Retry-After` or rate-limit headers.
- Add reasonable delays between sequential requests (start with 1-2 seconds; tune based on observed behavior).
- Do not make parallel/concurrent requests to the same endpoint unless confirmed safe.
- Back off exponentially on errors (4xx/5xx), not just retries.

## Pattern Hygiene

- Vary request timing slightly (jitter) rather than hitting endpoints at exact intervals.
- Access resources in a human-plausible order (e.g., list page before detail page).
- Do not request the same resource repeatedly in a tight loop.

## Client & Fetching Conventions

- Handle HTTP errors gracefully: log the error and continue, do not crash.
- Store raw JSON responses before parsing (raw -> processed pipeline).
- Make fetching idempotent: re-running should not create duplicate data.
- Use sessions (httpx.Client) for connection pooling.
- Set reasonable timeouts on all HTTP requests (30 seconds default).
- Log the URL being fetched and the response status code.
- NEVER log or store authentication headers or tokens.

## Exceptions

- **OpenRouter (`src/llm/openrouter.py`)**: Uses plain `httpx.Client()` without browser-identity headers. OpenRouter is a standard commercial API with proper API key auth -- it does not require GameChanger-style browser presentation. This exception applies only to `src/llm/`; all GameChanger HTTP code remains fully subject to these rules.

## Implementation Notes

- These rules apply to both `requests`/`httpx` API calls and any future `playwright`/`selenium` scraping.
- When writing tests, mock at the HTTP layer so tests do not depend on header correctness -- but integration/smoke tests should verify the real header profile.
