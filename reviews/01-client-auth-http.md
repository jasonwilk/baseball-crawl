# Code Review: GameChanger Client, Auth & HTTP

**Reviewer**: code-reviewer agent
**Date**: 2026-03-17
**Test suite**: 385 tests, all passing
**Files reviewed**: 14 source files, 11 test files

---

## Critical Issues

### C-1: Dead code branch in `values_for_signer` -- unreachable `dict is None` check

**File**: `src/gamechanger/signing.py:65`

```python
if isinstance(obj, dict):
    if obj is None:       # <-- This is unreachable
        return ["null"]
```

If `obj` passes `isinstance(obj, dict)`, it cannot be `None`. This dead branch means a `None` value inside a nested structure is handled by the later `if obj is None` check at line 82, which is correct -- so there is no functional bug. However, this dead code is misleading and suggests the author may have intended different logic (e.g., checking for a `None` value in the dict). Since this is a cryptographic signing function whose output must match the JavaScript implementation exactly, any confusion about its behavior is concerning.

**Severity**: Important (dead code in security-critical path, but no functional impact)

### C-2: `_make_client_auth_request` uses raw `httpx.Client()` instead of `create_session()`

**File**: `src/gamechanger/credentials.py:288`

```python
with httpx.Client(trust_env=False, verify=proxy_url is None, proxy=proxy_url, timeout=30) as client:
    response = client.post(f"{base_url.rstrip('/')}{_AUTH_PATH}", json=body, headers=headers)
```

CLAUDE.md states: "All callers (ingestion scripts, smoke tests, etc.) must use this client -- never make raw httpx calls directly." While this function intentionally bypasses `TokenManager` to avoid side effects (documented in the docstring), it also bypasses the session factory's header profile, rate limiting, and cookie jar. The `_WEB_AUTH_HEADERS` on line 251-256 are hardcoded instead of using the profile system. This creates a maintenance divergence -- if browser fingerprint headers change, this call won't pick them up.

Note: The `TokenManager._post_refresh_request()` (line 291) and `_do_login_fallback()` (line 604) have the same pattern -- raw `httpx.Client()` for POST /auth calls. These are arguably justified because they are auth bootstrapping calls that cannot use the authenticated session.

**Severity**: Minor (intentional design choice for credential checking, but creates header fingerprint drift risk)

### C-3: `credential_parser._decode_jwt_type` uses bare `except Exception:` without `noqa` comment

**File**: `src/gamechanger/credential_parser.py:57`

```python
except Exception:
    return None
```

The project convention (`.claude/rules/python-style.md`) requires "explicit exception types, never bare `except:`". While this catches `Exception` (not bare `except:`), the parallel function `decode_jwt_exp` in `credentials.py:72` has `# noqa: BLE001` for the same pattern. This file is missing the noqa comment, which means a linter would flag it inconsistently.

**Severity**: Minor (consistent with the project's practical approach to JWT decoding, but missing the noqa comment)

---

## Important Issues

### I-1: `get_paginated` does not re-authenticate on subsequent pages after initial 401 retry

**File**: `src/gamechanger/client.py:232-341`

The `get_paginated` method calls `_ensure_access_token()` once at line 232, then enters the pagination loop. If the access token expires *during* a multi-page fetch (between pages, not on the first page), the 401 retry logic on line 262-280 handles it correctly for the failing page. However, the `_ensure_access_token()` call at line 232 only runs once before the loop -- it does not run before each page. This is actually fine because the 401 retry block handles mid-pagination token expiry, but the asymmetry between `get()` (which calls `_ensure_access_token` per-call) and `get_paginated` (once before the loop) could cause confusion in future maintenance.

**Severity**: Observation (not a bug -- the 401 retry covers this case)

### I-2: `get_paginated` pagination URL construction trusts server-provided `x-next-page` header

**File**: `src/gamechanger/client.py:333-337`

```python
next_page_url = page_response.headers.get("x-next-page")
if not next_page_url:
    break
url = next_page_url
```

The `x-next-page` header value from the server replaces the URL entirely. If the server returns a URL pointing to a different host, the client would follow it, potentially sending auth tokens to an attacker-controlled server. For an undocumented API, this is a low-probability risk, but defense-in-depth would validate the URL's host matches `self._base_url`.

**Severity**: Minor security hardening opportunity

### I-3: `_check_token_health` builds the env key differently than `_required_keys`

**File**: `src/gamechanger/credentials.py:218`

```python
raw_token = env.get(f"GAMECHANGER_REFRESH_TOKEN_{profile.upper()}")
```

This uses `f"GAMECHANGER_REFRESH_TOKEN_{profile.upper()}"` (with underscore before profile suffix), while `_required_keys` in `client.py:78` uses `f"GAMECHANGER_REFRESH_TOKEN{suffix}"` where `suffix = "_WEB"`. These produce the same result (`GAMECHANGER_REFRESH_TOKEN_WEB`), but the inconsistent construction pattern is fragile -- if someone adds a new profile, they could easily get it wrong in one place.

**Severity**: Minor (no functional impact, code smell)

### I-4: `merge_env_file` returned dict does not strip value whitespace

**File**: `src/gamechanger/credential_parser.py:448-449`

```python
if "=" in stripped:
    k, _, v = stripped.partition("=")
    merged[k.strip()] = v
```

The key is stripped but the value `v` is not. If the .env file has `KEY = value` (with spaces), the returned dict will have `" value"` as the value. The `_build_merged_lines` function at line 403 also uses `partition("=")` without stripping the key when building `existing_keys`, though the key is stripped. This is inconsistent -- some code paths strip, others don't.

In practice, dotenv files rarely have spaces around `=`, and `dotenv_values()` handles this properly for actual credential loading. This only affects the returned dict from `merge_env_file`, which is used for confirmation output. But it could cause subtle bugs if the returned dict is ever used for anything more important.

**Severity**: Minor

### I-5: `_make_rate_limit_hook` type annotation uses lowercase `callable` instead of `Callable`

**File**: `src/http/session.py:200`

```python
def _make_rate_limit_hook(
    min_delay_ms: int,
    jitter_ms: int,
) -> callable:
```

The return type should be `Callable` from `typing` (or the more specific `Callable[[httpx.Response], None]`), not the built-in `callable`. The built-in `callable` is a function, not a type -- using it as a return type annotation is technically incorrect (though it works at runtime due to `from __future__ import annotations` making it a string). This would fail a strict type checker like pyright.

**Severity**: Minor (convention violation per `.claude/rules/python-style.md` -- type hints for all function parameters and return types in `src/`)

### I-6: `test_http_headers.py` is missing `from __future__ import annotations`

**File**: `tests/test_http_headers.py:1`

The file starts with the docstring and jumps directly to imports. Per project conventions, every module should have `from __future__ import annotations`. While this is a test file (and the convention is more strictly enforced in `src/`), every other test file in the review scope includes it.

**Severity**: Minor

### I-7: Rate limit handling sleeps then immediately raises

**File**: `src/gamechanger/client.py:296-300` (also lines 434-438, 533-537)

```python
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", "60"))
    ...
    time.sleep(retry_after)
    raise RateLimitError(...)
```

The code sleeps for the `Retry-After` duration and then raises an exception. This means the caller must catch the exception and retry the entire operation. The sleep is wasted because no retry happens after it. A more useful pattern would be either (a) sleep and retry automatically, or (b) raise immediately and let the caller decide whether to sleep and retry. The current approach combines the worst of both: it blocks the thread *and* forces the caller to handle the exception.

Additionally, `int(response.headers.get("Retry-After", "60"))` will crash with `ValueError` if the server sends a non-integer `Retry-After` value (e.g., an HTTP-date string, which is valid per RFC 7231).

**Severity**: Important (the `int()` crash is a bug; the sleep-then-raise is a design issue)

### I-8: `_handle_auth_error` is called even on 200 responses in `_do_refresh`

**File**: `src/gamechanger/token_manager.py:260-261`

```python
self._handle_auth_error(response)
return self._apply_refresh_response(response)
```

When `_do_refresh` calls `_post_refresh_request()` and the response is 200, it still calls `_handle_auth_error(response)` which checks `if response.status_code == 200: return` on line 349. This is not a bug, but it's confusing flow -- a function named `_handle_auth_error` being called on success responses.

**Severity**: Minor (code clarity)

---

## Minor Issues

### M-1: `values_for_signer` has inconsistent `result` variable naming

**File**: `src/gamechanger/signing.py:59,67`

The `result` variable is declared inside both the `list` branch (line 59) and the `dict` branch (line 67) with the same name. This shadows the outer scope in a way that works but could confuse readers. Additionally, the empty dict case on line 67 goes through `sorted(obj.keys())` which returns an empty list, so the `result` initialized on line 67 is returned empty -- correct but the `if obj is None` dead code (C-1) muddies understanding.

### M-2: Duplicated display name extraction logic

**File**: `src/gamechanger/credentials.py:150-158` vs `src/gamechanger/credentials.py:450-452`

The `_extract_display_name` helper exists at line 150, but `check_single_profile` at line 450 duplicates the same logic inline:

```python
# In check_single_profile (legacy helper):
first = (user.get("first_name") or "").strip()
last = (user.get("last_name") or "").strip()
display = f"{first} {last}".strip() if (first and last) else "(authenticated user)"
```

This is a DRY violation. If the display name logic changes (e.g., to add further PII protections), it needs to be changed in two places.

### M-3: `_PROFILE_SUFFIXES` dict in `client.py` duplicated conceptually

**File**: `src/gamechanger/client.py:49-52`

The profile-to-suffix mapping `{"web": "_WEB", "mobile": "_MOBILE"}` is simple enough to derive from `f"_{profile.upper()}"`, which is what most other code does. Having both patterns coexist means there are two ways to get the suffix, and some code paths use the dict while others use the f-string derivation.

### M-4: `key_extractor.py` uses raw `httpx.Client` for public web requests

**File**: `src/gamechanger/key_extractor.py:92`

```python
with httpx.Client(trust_env=False, follow_redirects=True) as client:
```

This bypasses the session factory entirely -- no rate limiting, no header profile, no cookie jar. The `_PUBLIC_HEADERS` dict on line 40-50 is manually derived from `BROWSER_HEADERS`. This is another instance of header fingerprint drift risk similar to C-2.

### M-5: `proxy_refresh.py` uses `exec()` to parse existing headers file

**File**: `src/http/proxy_refresh.py:143`

```python
exec(compile(headers_text, "<headers.py>", "exec"), namespace)  # noqa: S102
```

The comment says "safe -- it is our own file, no user input." This is true for the current usage, but `exec()` on file contents is inherently risky. A safer approach would be to use AST parsing to extract the dict values. The `noqa: S102` suppresses the Bandit security warning, which is appropriate but worth noting.

### M-6: `_build_merged_lines` imports `Path` inside the function body

**File**: `src/gamechanger/credential_parser.py:389`

```python
def _build_merged_lines(env_path: str, new_values: dict[str, str]) -> list[str]:
    from pathlib import Path
```

`Path` is already imported at the module level in `credential_parser.py` -- wait, actually it is not. The module uses `shlex`, `json`, `base64`, `logging`, and `re` at the top level, but `Path` is only imported inside function bodies (lines 389, 433, 479). This is unusual -- `pathlib.Path` is a standard import that should be at the top level per convention.

---

## Observations

### O-1: Excellent credential security posture

The codebase consistently avoids logging credential values. Every module that handles tokens, keys, or proxy URLs is careful to log only metadata (variable names, status codes, profile names) and never the actual values. Multiple test files include dedicated log-safety assertions. This is a strong security pattern.

### O-2: Well-structured exception hierarchy

The `exceptions.py` module defines a clean hierarchy: `CredentialExpiredError` as the base for auth failures, with `ForbiddenError` and `LoginFailedError` as subclasses. This allows callers to catch at the appropriate granularity. The backward-compatibility rationale is well-documented.

### O-3: Comprehensive test coverage

385 tests across 11 test files provide thorough coverage of happy paths, error paths, edge cases, and security properties. The tests are well-organized with clear section headers and descriptive docstrings. The use of `respx` for HTTP mocking is consistent and clean.

### O-4: Atomic credential write-back

The `atomic_merge_env_file` function using `tempfile.mkstemp` + `os.replace` is a solid approach to preventing credential loss during refresh token rotation. The `TokenManager._persist_refresh_token` method correctly degrades gracefully (logs warning, doesn't raise) on write failure.

### O-5: Good separation of concerns

The layering is clean: `http/` provides the transport layer (sessions, headers, proxy), `gamechanger/` provides the auth layer (client, tokens, signing), and each module has a clear responsibility. The `exceptions.py` module prevents circular imports. The `credential_parser.py` handles the operator workflow (curl import) separately from the programmatic flow.

### O-6: Token type discrimination in credential parser

The `_route_gc_token` / `_resolve_web_token_key` logic that decodes JWT payloads to distinguish access tokens from refresh tokens is well-designed. The web profile correctly rejects access tokens (which expire too quickly), and the mobile profile routes each type to the correct env key. This prevents a common operator error.

### O-7: Dual-profile architecture is consistent

The web/mobile profile system flows cleanly through headers, sessions, proxy config, credentials, and token management. Each layer respects the profile parameter and applies profile-specific behavior without code duplication (mostly -- see M-3).

---

## Summary

This is a well-engineered authentication and HTTP subsystem. The code is security-conscious, well-tested (385 tests), and cleanly layered. The main areas of concern are:

1. **One real bug**: The `int()` cast of `Retry-After` headers (I-7) will crash on valid HTTP-date values. This should be wrapped in a try/except.

2. **Dead code in signing module** (C-1): The unreachable `dict is None` check in `values_for_signer` should be removed to avoid confusion in this security-critical function.

3. **Minor maintenance risks**: Several places use raw `httpx.Client()` instead of the session factory (C-2, M-4), which creates header fingerprint drift risk. The duplicated display name logic (M-2) is a DRY violation waiting to diverge.

4. **Type annotation issue** (I-5): The `callable` return type should be `Callable`.

Overall health: **Good**. The critical security properties (no credential leakage, atomic token persistence, proper auth error handling) are solid. The issues found are mostly maintenance and correctness edge cases, not architectural problems.
