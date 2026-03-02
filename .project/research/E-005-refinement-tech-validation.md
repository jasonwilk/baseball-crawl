# E-005 Refinement: Technical Validation

**Date**: 2026-03-01
**Validator**: tech-validator agent
**Purpose**: Verify that E-005's technical assumptions are still current as of March 2026.

---

## 1. Chrome Version Currency

### What E-005 assumes
E-005-01 hardcodes Chrome 131 in both the User-Agent string and the sec-ch-ua header, based on a real GameChanger curl capture from 2026-02-28:
- `User-Agent: ...Chrome/131.0.0.0 Safari/537.36`
- `sec-ch-ua: "Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"`

### What is actually current
Chrome **146** is the current stable version, released March 10, 2026. Chrome 131 was the stable version around mid-December 2024 -- it is now **15 major versions behind** current stable.

### Impact: UPDATE REQUIRED

E-005-01's note at line 68 acknowledges this scenario: "If this story is executed significantly later and Chrome stable has advanced several major versions, update to the then-current stable version." Chrome 131 is well past the ">2 major versions behind" threshold mentioned in the docstring template.

**Required changes to E-005-01:**
1. Update `User-Agent` to: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36`
2. Update `sec-ch-ua` to match Chrome 146. The GREASE brand string changes per major version (Chrome uses a permutation algorithm based on `major_version % 6` to select brand character ordering). For Chrome 146, the GREASE brand will differ from Chrome 131's `"Not_A Brand"`. The implementing agent should capture a fresh curl from a Chrome 146 browser on macOS to get the exact value, OR derive it from the Chromium GREASE algorithm source code.
3. Update all references in the epic, E-005-01 AC-2, AC-3, and the Technical Notes to say Chrome 146 instead of Chrome 131.

**Note on sec-ch-ua GREASE brand format**: The GREASE brand string in sec-ch-ua is NOT fixed -- it changes with every Chrome major version. Chrome uses a permutation of escaped characters around `"Not" + "A" + "Brand"` seeded by the major version number. Known examples:
- Chrome 131: `"Not_A Brand";v="24"`
- Chrome 145: `"Not:A-Brand";v="99"`

For Chrome 146, the exact GREASE string must be determined empirically (capture a real request) or computed from the Chromium source algorithm. The AC should not hardcode a specific GREASE string without verifying it matches what Chrome 146 actually sends.

**Recommendation**: Update the epic and E-005-01 to specify Chrome 146. Add a note that the implementing agent should capture fresh headers from a real Chrome 146 session before writing the final values.

---

## 2. httpx API Validation

### What E-005-02 assumes
E-005-02 uses these httpx patterns:
- `httpx.Client(headers=..., cookies=httpx.Cookies(), event_hooks={"response": [callback]})`
- Context manager support: `with httpx.Client() as c:`
- Cookie jar auto-persistence via `cookies=httpx.Cookies()`

### What is actually current
The current httpx stable version is **0.28.1** (released December 6, 2024).

**Validation results:**

| Pattern | Status | Notes |
|---------|--------|-------|
| `headers=dict` parameter | VALID | No deprecation. Standard usage. |
| `cookies=httpx.Cookies()` | VALID | Cookie persistence is a documented Client feature. |
| `event_hooks={"response": [...]}` | VALID | Fully documented. Both `request` and `response` hooks supported. Must be a list of callables. |
| Context manager (`with httpx.Client() as c:`) | VALID | Documented as "the recommended way to use a Client." |

**Breaking changes in httpx 0.27-0.28 that E-005 should be aware of:**
- `app=...` shortcut was deprecated in 0.27 and removed in 0.28. E-005 does not use this, so no impact.
- `proxies=...` argument was removed in 0.28. E-005 does not use this, so no impact.
- JSON bodies now use compact representation in 0.28. No impact on E-005 (header/session layer, not body encoding).
- `zstd` content encoding support added in 0.27 via `httpx[zstd]` extra. E-005-01 correctly includes `zstd` in Accept-Encoding.

### Impact: NO UPDATE REQUIRED

All httpx patterns used in E-005-02 are current and undeprecated. The epic should pin or note a minimum httpx version of 0.27+ (for zstd support alignment with Accept-Encoding), but the API surface used is stable.

---

## 3. respx for Testing

### What E-005-04 assumes
E-005-04 recommends respx for mocking httpx at the transport level, using patterns like `@respx.mock` decorator and `respx.get(...).mock(return_value=httpx.Response(...))`.

### What is actually current
respx **0.22.0** was released December 19, 2024. The release notes explicitly state: "Support HTTPX 0.28.0."

| Aspect | Status |
|--------|--------|
| Actively maintained | Yes -- 0.22.0 released Dec 2024 |
| Compatible with httpx 0.28.x | Yes -- explicitly supported |
| Decorator pattern (`@respx.mock`) | Still supported |
| Route/mock pattern | Still supported |
| Python version | Dropped Python 3.7; requires 3.8+ |

**Alternatives considered:**
- `httpx.MockTransport` (built-in): Adequate for simple cases but lacks respx's request matching, assertion helpers, and route inspection. E-005-04 uses `route.calls.last.request` for header inspection, which is respx-specific.
- `pytest-httpx`: Another option, but respx is more mature and widely used.

### Impact: NO UPDATE REQUIRED

respx 0.22.0 is actively maintained, compatible with httpx 0.28.x, and well-suited for E-005-04's testing patterns. No better alternative exists for this use case.

---

## 4. E-009 Stack Decision Impact

### What E-009 decided
E-009 chose **Docker + FastAPI + SQLite** (Option B). Key file convention from E-009:

```
src/
  api/          # FastAPI application
    main.py
    routes/
    templates/  # Jinja2 templates
  gamechanger/  # Existing crawlers (unchanged)
  safety/       # Existing PII module (unchanged)
```

### E-005 module path alignment

E-005 proposes:
```
src/
  http/
    __init__.py
    headers.py
    session.py
  gamechanger/
    client.py
```

**Assessment**: The paths are **compatible**. E-009's file conventions show `src/gamechanger/` for crawlers, which matches E-005's `src/gamechanger/client.py`. E-005's `src/http/` module is a new shared infrastructure package -- it sits alongside `src/api/`, `src/gamechanger/`, and `src/safety/` without conflict. The `src/http/` module is consumed by the crawling layer (`src/gamechanger/`), not the serving layer (`src/api/`), so it fits naturally into the project structure.

**No path conflicts identified.**

### FastAPI async vs E-005 sync

E-009's decision document explicitly states: "E-001 through E-006 (crawlers, HTTP discipline, PII protection) remain valid Python implementations." The crawling layer is separate from the serving layer. FastAPI runs in `src/api/`; the HTTP session factory runs in `src/http/` and is consumed by `src/gamechanger/`. These are different execution contexts.

### Impact: MINOR CONSIDERATION (see Section 5)

The module paths are fine. The sync/async question is addressed below.

---

## 5. Async Question: Is sync-only httpx.Client sufficient?

### What E-005 assumes
Epic non-goal: "Async session support -- sync first; async can come later if E-002 needs it."

### Analysis

**The crawling layer and serving layer are separate execution contexts.**

| Layer | Location | Runtime | HTTP Client Usage |
|-------|----------|---------|-------------------|
| Crawling | `src/gamechanger/`, `src/http/` | Script/CLI or scheduled job | Makes outbound requests to GameChanger API |
| Serving | `src/api/` | FastAPI (uvicorn) | Serves inbound requests from coaching staff |

The session factory (`create_session()`) is used by the **crawling layer** -- it makes outbound HTTP requests to GameChanger. The **serving layer** (FastAPI) handles inbound requests from coaches browsing dashboards. These are independent. FastAPI's async nature does not impose async requirements on the crawling pipeline.

**When would async matter?**
- If the FastAPI application itself needed to make outbound HTTP requests to GameChanger in response to an inbound request (e.g., a "refresh stats now" endpoint that triggers a crawl synchronously). In that case, a sync `time.sleep()` inside an event hook would block the async event loop.
- If crawling were triggered as a background task within the FastAPI process.

**Current design avoids this problem.** Crawling is a separate process (CLI script or scheduled job), not embedded in the FastAPI request/response cycle. As long as this separation holds, sync `httpx.Client` with `time.sleep()` jitter is perfectly fine.

### Impact: NO UPDATE REQUIRED (with caveat)

E-005's "sync first" non-goal is correct given the current architecture. The session factory does not need an async variant at this time.

**Caveat for the epic**: Add a note that if a future story embeds crawling within a FastAPI request handler (e.g., an on-demand refresh endpoint), the session factory will need an `create_async_session()` variant using `httpx.AsyncClient` and `asyncio.sleep()` instead of `time.sleep()`. This is not needed now but should be flagged as a known future consideration.

---

## Summary of Required Updates

| Check | Verdict | Action |
|-------|---------|--------|
| Chrome version (131 -> 146) | **UPDATE REQUIRED** | Update UA and sec-ch-ua to Chrome 146 in epic, E-005-01, and all ACs. Implementing agent should capture fresh headers from a real Chrome 146 session. |
| httpx API (event_hooks, cookies, context manager) | No update needed | All patterns valid with httpx 0.28.1. |
| respx for testing | No update needed | respx 0.22.0 supports httpx 0.28.x. Actively maintained. |
| E-009 module path alignment | No update needed | `src/http/` fits cleanly into E-009's file conventions. |
| Sync vs async | No update needed (with caveat) | Sync is correct for crawling layer. Add a note about async variant if crawling is later embedded in FastAPI handlers. |

### Priority

The Chrome version update is the only blocking issue. It must be addressed before E-005-01 can be implemented, because the acceptance criteria explicitly hardcode Chrome 131 version strings that are now 15 major versions out of date. The other findings are informational or minor documentation improvements.
