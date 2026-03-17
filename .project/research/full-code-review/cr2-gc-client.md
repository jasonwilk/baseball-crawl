# Code Review: GameChanger Client & Credentials

**Reviewer**: code-reviewer agent
**Date**: 2026-03-17
**Scope**: `src/gamechanger/{client,token_manager,credentials,credential_parser,signing,key_extractor,bridge,team_resolver,url_parser,config,exceptions,types}.py` and corresponding test files
**Test suite**: 323 tests, all passing

---

## Critical Issues

### C-1: Dead code / unreachable branch in `values_for_signer` (signing.py:64-66)

```python
if isinstance(obj, dict):
    if obj is None:          # <-- IMPOSSIBLE: dicts are never None
        return ["null"]
```

Inside the `isinstance(obj, dict)` branch, `obj is None` can never be `True`. This is dead code. The `None` case IS correctly handled later at line 83, so this is not a correctness bug -- but it indicates a copy-paste error and could confuse future maintainers reading the signing algorithm. **Severity: Low** (no incorrect behavior, but confusing in a security-critical HMAC module).

### C-2: Duplicate `GameChangerAPIError` class in `team_resolver.py` shadows `exceptions.py`

**File**: `src/gamechanger/team_resolver.py:43-44`

```python
class GameChangerAPIError(Exception):
    """Raised when the GameChanger API returns an unexpected error response."""
```

This is a **separate class** from `src.gamechanger.exceptions.GameChangerAPIError`. They share a name but are different Python types. This means:

- Code catching `src.gamechanger.exceptions.GameChangerAPIError` will **NOT** catch errors raised by `team_resolver.resolve_team()` or `team_resolver.discover_opponents()`.
- Any caller that imports both modules gets name shadowing.
- The exception hierarchy (`exceptions.py`) was explicitly created to avoid this exact problem (see `exceptions.py` docstring: "Defined in a standalone module to avoid circular imports").

**Impact**: Silent exception type mismatch. A pipeline calling `resolve_team()` inside a `try/except GameChangerAPIError` block (importing from `exceptions`) will get an unhandled exception.

**Fix**: Replace the local class with `from src.gamechanger.exceptions import GameChangerAPIError` in `team_resolver.py`. Also remove the local `TeamNotFoundError(ValueError)` and move it to `exceptions.py` if it needs to be catchable externally, or at minimum import `GameChangerAPIError` from the canonical location.

---

## High Priority

### H-1: `key_extractor.py` uses raw `httpx.Client()` without browser headers (partial)

**File**: `src/gamechanger/key_extractor.py:92`

```python
with httpx.Client(trust_env=False, follow_redirects=True) as client:
```

This client is constructed without the `BROWSER_HEADERS` from `src/http/headers.py`. The module does import `BROWSER_HEADERS` and constructs `_PUBLIC_HEADERS` (line 40-50) which it passes as per-request headers, so the User-Agent and other fingerprint headers ARE sent. However, the session-level defaults are empty, meaning any redirect or follow-up request that doesn't explicitly pass headers will lack the fingerprint. The `follow_redirects=True` flag makes this a tangible risk: if `web.gc.com` redirects, the redirect request will have bare headers.

**Recommendation**: Use `create_session(min_delay_ms=0, jitter_ms=0, proxy_url=None)` instead, or at minimum pass `headers=_PUBLIC_HEADERS` to the `httpx.Client` constructor so redirects carry the fingerprint.

### H-2: `token_manager.py` POST /auth uses raw `httpx.Client()` -- no rate limiting or browser fingerprint

**File**: `src/gamechanger/token_manager.py:291-292, 604`

```python
with httpx.Client(timeout=30, trust_env=False) as client:
    return client.post(url, json=body, headers=headers)
```

Token refresh and login fallback create throwaway `httpx.Client` instances with no User-Agent, no rate limiting, no cookie jar. The `headers` dict passed to `client.post()` includes `Content-Type`, `gc-*` headers, and `Accept`, but **no User-Agent**. The HTTP discipline rule requires "a realistic User-Agent string" on all requests.

**Mitigating factor**: These are POST /auth requests, not data-fetching GETs, and the headers explicitly built include the GC-specific headers. But the missing User-Agent is a fingerprint gap that could theoretically trigger server-side bot detection.

**Recommendation**: At minimum, add `"User-Agent": BROWSER_HEADERS["User-Agent"]` to the POST /auth headers. Alternatively, use `create_session()` for consistency.

### H-3: `_get_with_retries` raises `GameChangerAPIError` on 5xx after exhausting retries, but also raises it for unexpected non-5xx status codes -- the error path has an `else` clause that can shadow the retry loop

**File**: `src/gamechanger/client.py:539-558`

The `else` at line 555 is attached to the `if 500 <= response.status_code < 600` at line 539. When a 5xx response occurs on the final retry (attempt index 2), the code sets `last_error` (line 540-544) and falls through (the `continue` at line 553 is only for `attempt < len(backoff_delays) - 1`). The loop body ends, and the `else` clause at line 555 is reached, which raises `GameChangerAPIError("Unexpected status ...")`. This means the **final 5xx retry does NOT raise the more informative `last_error`** -- it raises the generic "Unexpected status" error instead.

Wait -- re-reading: the `else` is paired with the `if 500 <= response.status_code < 600`, not the `for` loop. So on the last 5xx retry: status is 500-599, so the `if` matches, `last_error` is set, `attempt < len(backoff_delays) - 1` is False so no `continue`, and the `else` block is NOT entered (the `if` matched). The loop body ends, the `for` loop continues to the next iteration -- but there is no next iteration. So the `if page_response is None` check fires and raises `last_error`. This is correct.

Actually wait, this is `_get_with_retries`, not `get_paginated`. Let me re-read lines 539-558:

```python
if 500 <= response.status_code < 600:
    last_error = ...
    if attempt < len(backoff_delays) - 1:
        ...
        continue

# Unexpected non-success status
raise GameChangerAPIError(...)
```

The `raise` at line 556 is NOT in an `else` block -- it's at the same indentation as the `if 500` block. So on the last 5xx retry: the `if 500` matches, `last_error` is set, `attempt < 2` is False so no `continue`, and then execution falls through to line 556 which raises the "Unexpected status" error. **This IS a bug**: on the final 5xx retry, the code raises `"Unexpected status 500 for /path"` instead of the more informative `last_error` message that includes the attempt count.

Actually, let me re-read more carefully.

**File**: `client.py:539-561`

After the `if 500 <=` block, if we don't `continue`, we fall through. The next statement after the `if` block is:

```python
# Unexpected non-success status -- treat as a non-retryable API error.
raise GameChangerAPIError(
    f"Unexpected status {response.status_code} for {path}."
)
```

This fires for the last 5xx attempt because the `continue` was skipped. The code then raises "Unexpected status 500" instead of the `last_error` that says "Server error for /path (HTTP 500) after 3 attempt(s)." The error message loses the retry context.

**Impact**: Minor -- the operator sees "Unexpected status 500" instead of "Server error after 3 attempts". Not a data-loss bug, but a degraded error message. The same pattern is correctly handled in `get_paginated` (line 323-325) with the `if page_response is None: raise last_error` pattern.

### H-4: `credentials.py:_check_client_key` disables SSL verification based on proxy presence

**File**: `src/gamechanger/credentials.py:288`

```python
with httpx.Client(trust_env=False, verify=proxy_url is None, proxy=proxy_url, timeout=30) as client:
```

This disables TLS certificate verification when a proxy is configured. This is consistent with the project's Bright Data proxy setup (self-signed CONNECT tunnel cert), but the `_check_client_key` function is a diagnostic tool -- it should not silently downgrade security. A WARNING log would be appropriate (like `create_session` does at line 273-277 of `session.py`).

### H-5: `check_single_profile` duplicates display name logic from `_extract_display_name`

**File**: `src/gamechanger/credentials.py:450-452`

```python
first = (user.get("first_name") or "").strip()
last = (user.get("last_name") or "").strip()
display = f"{first} {last}".strip() if (first and last) else "(authenticated user)"
```

This is an exact copy of `_extract_display_name` (line 150-158). The `_run_api_check` function correctly uses `_extract_display_name`, but the legacy `check_single_profile` has its own inline copy. This is a DRY violation that could lead to divergence if one is updated and the other is forgotten.

---

## Medium Priority

### M-1: `credential_parser.py:_decode_jwt_type` bare `except Exception` missing `# noqa: BLE001`

**File**: `src/gamechanger/credential_parser.py:57`

```python
except Exception:
    return None
```

The python-style rule says: "Use explicit exception types, never bare `except:`" and the project convention requires `# noqa: BLE001` on `except Exception:` blocks. This is a minor convention violation.

### M-2: `credential_parser.py:_build_merged_lines` uses inline `from pathlib import Path` import

**File**: `src/gamechanger/credential_parser.py:389`

```python
def _build_merged_lines(env_path: str, new_values: dict[str, str]) -> list[str]:
    from pathlib import Path
```

`Path` is not imported at module level. The same pattern appears in `merge_env_file` (line 433) and `atomic_merge_env_file` (line 479). Since `pathlib` is a stdlib module with no import cost, these deferred imports serve no purpose and violate the convention of top-level imports.

### M-3: `bridge.py` creates a new `GameChangerClient` per call -- no connection reuse

**File**: `src/gamechanger/bridge.py:51, 84`

Both `resolve_public_id_to_uuid` and `resolve_uuid_to_public_id` create a fresh `GameChangerClient(min_delay_ms=0, jitter_ms=0)` per call. Each client loads `.env`, constructs a `TokenManager`, and creates two `httpx.Client` sessions. For a single call this is fine, but if called in a loop (e.g., batch-resolving UUIDs), this creates N clients with N token refreshes.

**Recommendation**: Accept an optional `client` parameter and create one only when not provided.

### M-4: `url_parser.py:parse_team_url` uses `input` as a parameter name

**File**: `src/gamechanger/url_parser.py:56`

```python
def parse_team_url(input: str) -> TeamIdResult:
```

`input` shadows the Python builtin. This is a linting smell though not a runtime bug in this context.

### M-5: `url_parser.py:parse_team_url` recompiles regex on every call

**File**: `src/gamechanger/url_parser.py:92`

```python
teams_pattern = re.compile(r"/teams/([^/?#]+)")
```

This regex is compiled inside the function body on every call. It should be a module-level constant (like `_PUBLIC_ID_RE` and `_UUID_RE` already are).

### M-6: `token_manager.py` `_do_login_fallback` does not handle `httpx.HTTPError` from the login chain

**File**: `src/gamechanger/token_manager.py:582-622`

The login fallback steps (2, 3, 4) each call `client.post()` which can raise `httpx.ConnectError`, `httpx.TimeoutException`, etc. These are not caught anywhere in the login chain -- they will propagate as unhandled `httpx.HTTPError` subclasses. The caller (`_do_refresh`) doesn't catch them either. Ultimately they bubble to the `GameChangerClient._get_with_retries` caller, which only catches `CredentialExpiredError`, `AuthSigningError`, and `LoginFailedError`.

**Impact**: A network error during login fallback produces an unhandled `httpx.ConnectError` instead of a user-friendly `LoginFailedError`.

### M-7: `config.py` test file uses `sys.path` manipulation

**File**: `tests/test_config.py:20-21`

```python
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```

The python-style rule says "No `sys.path` manipulation in `src/` modules" -- this is in a test file, not `src/`, so it technically doesn't violate the rule. However, with the editable install in place, this is unnecessary and could mask import issues.

### M-8: `get_paginated` does not handle 403 after 401 retry correctly

**File**: `src/gamechanger/client.py:262-280`

After a 401 response, the code does `force_refresh()` and retries. If the retry returns a non-200 status other than 401, it falls through to the error-handling code below. Specifically, if the retry returns 403, the code correctly raises `ForbiddenError`. But if the retry returns 429 or 5xx, those also hit the right handlers. This is actually correct -- no bug here. (Self-correcting after closer reading.)

---

## Low Priority

### L-1: `client.py` docstring example uses `from src.gamechanger.client import` path

**File**: `src/gamechanger/client.py:10`

```python
from src.gamechanger.client import GameChangerClient
```

The `src.` prefix in the import path is technically correct for this project (editable install with `src/` as package root), but the rest of the codebase's test files use the same convention, so this is consistent.

### L-2: `_PROFILE_SUFFIXES` dict in `client.py` could just be string manipulation

**File**: `src/gamechanger/client.py:49-52`

```python
_PROFILE_SUFFIXES: dict[str, str] = {
    "web": "_WEB",
    "mobile": "_MOBILE",
}
```

With the fallback at line 75 (`f"_{profile.upper()}"`), the dict adds no value for the two known profiles. The dict could be eliminated. This is cosmetic.

### L-3: `key_extractor.py:KeyExtractionError` inherits from `RuntimeError` rather than the project exception hierarchy

**File**: `src/gamechanger/key_extractor.py:56`

`KeyExtractionError(RuntimeError)` is not part of the `exceptions.py` hierarchy. This is defensible since key extraction is a standalone utility with different semantics, but it means callers can't catch `GameChangerAPIError` to handle all GC-related failures uniformly.

### L-4: `_EXPIRY_SAFETY_MARGIN_SECONDS` is 5 minutes (300s) -- generous but reasonable

**File**: `src/gamechanger/token_manager.py:48`

A 5-minute safety margin means the token is refreshed when it has more than 5 minutes of life remaining. This is conservative but appropriate for a system where clock skew and slow requests are real risks.

### L-5: `credential_parser.py` boolean flag heuristic may consume URL arguments

**File**: `src/gamechanger/credential_parser.py:194-199`

```python
if token.startswith("-") and "=" not in token:
    if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
        i += 2
    else:
        i += 1
    continue
```

For unknown flags, this heuristic checks if the next token starts with `-`. If it doesn't, it's consumed as the flag's value. This could fail for a curl command where the URL is the last argument after an unknown boolean flag (e.g., `curl --compressed https://...`), since `--compressed` is boolean but the URL doesn't start with `-`. In practice, curl URLs typically come first, so this is unlikely to cause issues. But the heuristic is fragile.

---

## Positive Observations

### P-1: Excellent credential security posture

- Display name extraction (`_extract_display_name`) deliberately falls back to `"(authenticated user)"` rather than exposing email addresses. Tests explicitly verify no PII leakage.
- Credential values are never logged -- tests verify this with `caplog` inspection.
- The `signing.py` module is thoroughly tested with known-input/output HMAC verification, including nonce-as-bytes (not string) verification.
- `atomic_merge_env_file` uses `tempfile.mkstemp()` + `os.replace()` for crash-safe credential persistence.

### P-2: Robust token lifecycle management

- The `TokenManager` handles multiple credential configurations (web full, mobile no-key fallback, manual access token) with clear validation at construction time.
- The 3-step login fallback flow is well-documented and well-tested, including signature chaining between steps.
- Refresh token rotation is persisted atomically with graceful degradation (warning, not crash) on write failure.

### P-3: Comprehensive test coverage

- 323 tests across 10 test files covering happy paths, error cases, edge cases, and security invariants.
- Tests use `respx` for HTTP mocking consistently, never making real network requests.
- Credential values in tests are clearly synthetic (marked with `# synthetic-test-data` comments).
- The `check_profile_detailed` tests cover presence, token health, API reachability, proxy status, and client key validation as independent dimensions.

### P-4: Clean exception hierarchy

- `exceptions.py` provides a clear, documented exception hierarchy with backward-compatible inheritance (`ForbiddenError` extends `CredentialExpiredError`).
- Error messages consistently include actionable recovery instructions (e.g., "run: bb creds check", "run: bb creds extract-key").

### P-5: Well-structured paginated fetch

- `get_paginated` correctly follows `x-next-page` headers with per-page retry logic and token refresh on 401.
- Rate limiting is handled via the `create_session` event hook pattern, avoiding manual sleep management in callers.

### P-6: Signing module is clean and well-documented

- `values_for_signer` correctly implements the recursive JSON value extraction with sorted keys, matching the JS reference implementation.
- `sign_payload` correctly uses nonce as raw bytes (not Base64 string), with a dedicated test verifying this distinction.
- The signing module is purely functional with no side effects beyond logging.
