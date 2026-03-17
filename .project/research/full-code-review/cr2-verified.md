# CR2 (GC Client & Credentials) — Verified Findings

**Verifier**: software-engineer
**Date**: 2026-03-17

---

## Critical Issues

### C-1 — Dead code / unreachable branch in `values_for_signer`
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/signing.py:64-66` — Inside `if isinstance(obj, dict):`, the check `if obj is None:` can never be True. A dict is never None. The `None` case is correctly handled at line 82. Dead code, not a correctness bug.
**Notes**: Not covered by E-122. Low severity despite "Critical" label — the reviewer acknowledged this. The signing algorithm produces correct results.

### C-2 — Duplicate `GameChangerAPIError` class in `team_resolver.py` shadows `exceptions.py`
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/team_resolver.py:43-44` defines `class GameChangerAPIError(Exception)` — a separate class from `src.gamechanger.exceptions.GameChangerAPIError` (line 45 of exceptions.py). These are different Python types. Code catching `exceptions.GameChangerAPIError` will NOT catch errors raised by `team_resolver.resolve_team()`. The `TeamNotFoundError(ValueError)` at line 47 is also local.
**Notes**: Not covered by E-122. This is a real type-mismatch bug. Any pipeline wrapping `resolve_team()` in `try/except GameChangerAPIError` (from exceptions) will get an unhandled exception. Severity depends on how `team_resolver` is called — need to check callers.

---

## High Priority

### H-1 — `key_extractor.py` uses raw `httpx.Client()` without browser headers (partial)
**Verdict**: NEEDS CONTEXT
**Evidence**: `src/gamechanger/key_extractor.py:92` — `with httpx.Client(trust_env=False, follow_redirects=True) as client:`. The module imports `BROWSER_HEADERS` and constructs `_PUBLIC_HEADERS` (lines 40-50) which ARE passed to `_fetch_homepage` and `_fetch_bundle` as per-request headers. The concern about `follow_redirects=True` sending bare headers on redirects is valid in theory, but httpx's `follow_redirects` behavior carries per-request headers through redirects by default. The actual risk is lower than stated.
**Notes**: Not covered by E-122. The finding overstates the risk — httpx preserves request-level headers on redirects. However, using `create_session()` or passing headers to the client constructor would be more robust.

### H-2 — `token_manager.py` POST /auth uses raw `httpx.Client()` — no User-Agent
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/token_manager.py:291` — `with httpx.Client(timeout=30, trust_env=False) as client:`. The `headers` dict (built at lines 278-288) includes `gc-token`, `gc-app-name`, `Content-Type`, and GC-specific headers, but no `User-Agent`. Same pattern at line 604 for login fallback. The HTTP discipline rule requires a realistic User-Agent on all requests.
**Notes**: Not covered by E-122. Real HTTP discipline violation. Low practical risk — these are auth POST requests with GC-specific headers that clearly identify the caller regardless of User-Agent. But it's a consistency gap.

### H-3 — `_get_with_retries` final 5xx raises wrong error message
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/client.py:539-558` — On the final retry attempt (attempt=2), if 5xx: `last_error` is set (line 540-543), `attempt < len(backoff_delays) - 1` is False so no `continue` (line 544), execution falls through to line 555-558 which raises `GameChangerAPIError("Unexpected status {status} for {path}.")` — losing the retry context from `last_error`. The `assert last_error is not None; raise last_error` at lines 560-561 is unreachable for 5xx on the last attempt. This matches the `get_paginated` pattern bug the reviewer noted.
**Notes**: Not covered by E-122. Real bug — degraded error message on final 5xx retry. The operator sees "Unexpected status 500" instead of "Server error after 3 attempts". Easy fix: add `raise last_error` after the `if 500 <=` block on the last attempt (or restructure to use a `for/else`).

### H-4 — `credentials.py:_check_client_key` disables SSL verification with proxy
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/credentials.py:288` — `verify=proxy_url is None` disables TLS verification when proxy is configured. No warning is logged (unlike `create_session` at session.py:273-277 which logs a WARNING).
**Notes**: Not covered by E-122. Consistent behavior with the proxy pattern but missing the warning log. Low severity — this is a diagnostic function (`bb creds check`), not a data pipeline path.

### H-5 — `check_single_profile` duplicates `_extract_display_name` logic
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/credentials.py:450-452` — inline display name extraction identical to `_extract_display_name` at lines 150-158. `_run_api_check` (line 161) correctly uses `_extract_display_name`, but the legacy `check_single_profile` does not.
**Notes**: Not covered by E-122. DRY violation but not a bug — both produce the same output. E-122-05 covers publicizing `_run_api_check` but doesn't address this duplication.

---

## Medium Priority

### M-1 — `credential_parser.py:_decode_jwt_type` bare `except Exception`
**Verdict**: CONFIRMED (trivial)
**Evidence**: `src/gamechanger/credential_parser.py:57` — `except Exception: return None`. Missing `# noqa: BLE001` comment per project convention. The bare except is intentional (JWT decoding can fail many ways), just missing the annotation.
**Notes**: Not covered by E-122. Trivial convention fix.

### M-2 — `credential_parser.py` deferred `from pathlib import Path` imports
**Verdict**: CONFIRMED (trivial)
**Evidence**: `src/gamechanger/credential_parser.py:389` — `from pathlib import Path` inside `_build_merged_lines`. `pathlib` is stdlib with no import cost. The deferred import serves no purpose.
**Notes**: Not covered by E-122. Trivial cleanup.

### M-3 — `bridge.py` creates a new `GameChangerClient` per call
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/bridge.py:51` and `:84` — both `resolve_public_id_to_uuid` and `resolve_uuid_to_public_id` create `GameChangerClient(min_delay_ms=0, jitter_ms=0)` per call. Each instantiation loads `.env`, creates a `TokenManager`, and opens two httpx sessions.
**Notes**: Not covered by E-122. In practice, these functions are called infrequently (team add flow). The overhead is acceptable for current usage. Would matter if called in a batch loop.

### M-4 — `url_parser.py:parse_team_url` uses `input` as parameter name
**Verdict**: CONFIRMED (trivial)
**Evidence**: `src/gamechanger/url_parser.py:56` — `def parse_team_url(input: str)`. Shadows the `input` builtin. No runtime impact in this context.
**Notes**: Not covered by E-122. Trivial lint issue.

### M-5 — `url_parser.py:parse_team_url` recompiles regex on every call
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/url_parser.py:92` — `teams_pattern = re.compile(r"/teams/([^/?#]+)")` inside the function body. Module-level constants `_PUBLIC_ID_RE` and `_UUID_RE` already follow the correct pattern.
**Notes**: Not covered by E-122. Minor performance issue. Python caches compiled regexes internally, so the actual cost is minimal.

### M-6 — `token_manager.py` `_do_login_fallback` doesn't handle `httpx.HTTPError`
**Verdict**: CONFIRMED
**Evidence**: `src/gamechanger/token_manager.py:604` — `with httpx.Client(timeout=30, trust_env=False) as client:` — the login steps (lines 605-609) call `client.post()` which can raise `httpx.ConnectError`, `httpx.TimeoutException`, etc. These are not caught in `_do_login_fallback` or its caller `_do_refresh`. They propagate as unhandled httpx exceptions.
**Notes**: Not covered by E-122. Real gap — network errors during login fallback produce unhelpful stack traces instead of `LoginFailedError`. Impact is limited to the login fallback path which is already a failure recovery mechanism.

### M-7 — `config.py` test file uses `sys.path` manipulation
**Verdict**: CONFIRMED (acceptable)
**Evidence**: The reviewer confirmed this is in a test file, not `src/`, and acknowledged it doesn't violate the style rule. Acceptable per project conventions.
**Notes**: Not covered by E-122. Not a real issue.

### M-8 — `get_paginated` 403 after 401 retry handling
**Verdict**: FALSE POSITIVE
**Evidence**: The reviewer self-corrected during the review — "Actually wait... This is actually correct -- no bug here." The 403, 429, and 5xx paths are all correctly handled after a 401 retry.
**Notes**: N/A — reviewer retracted the finding.

---

## Low Priority

### L-1 — Docstring import path uses `src.` prefix
**Verdict**: CONFIRMED (non-issue)
**Evidence**: Consistent with project convention (editable install). Not a real issue.

### L-2 — `_PROFILE_SUFFIXES` dict could be string manipulation
**Verdict**: CONFIRMED (cosmetic)
**Evidence**: `src/gamechanger/client.py:49-52` — dict with only two entries, plus fallback at line 75. Cosmetic.

### L-3 — `KeyExtractionError` inherits from `RuntimeError`
**Verdict**: CONFIRMED (acceptable)
**Evidence**: `src/gamechanger/key_extractor.py:56` — `class KeyExtractionError(RuntimeError)`. Not in the exceptions.py hierarchy. Defensible — key extraction is standalone utility code.

### L-4 — `_EXPIRY_SAFETY_MARGIN_SECONDS` is 5 minutes
**Verdict**: CONFIRMED (acceptable)
**Evidence**: Conservative but appropriate for the use case. Not a bug.

### L-5 — `credential_parser.py` boolean flag heuristic
**Verdict**: CONFIRMED (acceptable)
**Evidence**: `src/gamechanger/credential_parser.py:194-199` — heuristic could misparse edge cases. In practice, curl commands from the browser always have URL first. Fragile but functional.

---

## E-122 Overlap Summary

| Finding | Covered by E-122? |
|---------|-------------------|
| E-122-05 (publicize `_ALL_PROFILES` and `_run_api_check`) | Partially — E-122-05 covers the private naming, but `check_single_profile` duplication (H-5) is not in scope |
| All others | No |

## Actionable Findings Not in E-122

**Bugs (should fix)**:
- C-2: Duplicate `GameChangerAPIError` in team_resolver.py — type mismatch
- H-3: `_get_with_retries` final 5xx raises wrong error message

**HTTP discipline gaps**:
- H-2: token_manager POST /auth missing User-Agent
- H-1: key_extractor client lacks session-level headers (low risk)

**Code quality**:
- C-1: Dead code in signing.py (trivial)
- H-4: Missing SSL warning log in credentials diagnostic
- H-5: Display name duplication in check_single_profile
- M-6: Login fallback missing httpx error handling
