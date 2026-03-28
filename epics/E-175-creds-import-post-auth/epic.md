# E-175: Fix `bb creds import` for POST /auth Curl Commands

## Status
`READY`

## Overview
When an operator copies a `POST /auth` curl command from browser dev tools and runs `bb creds import`, the import fails silently or with a confusing error. This epic adds POST /auth curl detection, HTTP execution to retrieve tokens from the response body, and fixes a misleading warning message that sends users in circles.

## Background & Context
Three independent issues create a broken experience for POST /auth curls:

1. **Client token rejection**: POST /auth curls for password/user-auth/client-auth steps carry a client token (`type: "client"`) or no `gc-token` at all. `_resolve_web_token_key()` discards tokens with non-null type that isn't `"user"`, so the client token is silently skipped and validation fails.

2. **Tokens are in the response, not the request**: The actual refresh token is in the POST /auth *response body*, not in the request headers. The parser never executes the curl -- it only extracts headers. POST /auth curls require execution to yield useful credentials (exception: refresh-type curls already carry the refresh token in gc-token, but the user doesn't know which type they copied).

3. **Misleading warning message**: `_resolve_web_token_key()` tells users who paste access tokens to "copy a curl command from a POST /auth request" -- which doesn't work either, creating a circular dead end.

**What works today**: Pasting the raw JSON response body from POST /auth works (the `gc_auth` shape is already handled by `_parse_json_credentials()`). GET request curls with refresh tokens work for web profile. But the natural operator workflow -- copy curl, paste, import -- fails for POST /auth.

**Expert consultation (api-scout)**: Refresh-type POST /auth curls (`{"type":"refresh"}`) are the most common (fires on every browser session load and every ~51 minutes). The gc-token header in refresh-type curls already contains the refresh token and parses correctly. Password-type curls are rarer (explicit login only). Client-auth and user-auth curls carry client tokens. The gc-signature expiration constraint is on gc-timestamp freshness -- one confirmed rejection at ~6.2 hours stale; practical window is likely minutes to hours.

**Expert consultation (SE)**: Pending at draft time; story structure preserves parser purity by keeping HTTP execution in the CLI layer (`creds.py`), with the parser returning structured extraction results.

## Goals
- `bb creds import` handles any POST /auth curl command (all 5 body types) by executing the request and parsing the response
- Clear, actionable error messages for expired gc-signature (HTTP 400) and auth failures (HTTP 401)
- Non-token credentials (gc-device-id, gc-client-id) extracted from request headers alongside response tokens
- Password in `--data-raw` is never logged, stored in .env, or displayed
- The misleading access-token warning message is corrected
- Existing import paths (JSON response, GET curls, bare JWTs) continue to work unchanged

## Non-Goals
- Re-signing the request (generating a fresh gc-signature from client key)
- Programmatic mobile token refresh (generating gc-signature from mobile client key) -- mobile client key is unknown; this epic replays captured curls verbatim and does not generate signatures
- Extracting the client key from POST /auth curls
- Changes to `bb creds setup` flow
- Changes to the `bb creds refresh` flow or `TokenManager`

## Success Criteria
- An operator can copy ANY POST /auth curl from browser dev tools, paste it into `secrets/gamechanger-curl.txt`, run `bb creds import`, and either get credentials written to `.env` or receive a clear, actionable error message
- All existing `test_credential_parser.py` and `test_cli_creds.py` tests continue to pass
- No credential values (tokens, passwords, signatures) appear in logs or console output

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-175-01 | Detect POST /auth curls and extract request components | TODO | None | - |
| E-175-02 | Execute POST /auth curls and import credentials | TODO | E-175-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: Two-Layer Architecture

The parser (`credential_parser.py`) remains a pure parser -- no I/O, no network calls. It gains the ability to detect POST /auth curls and return a structured extraction result containing the request components (URL, headers dict, body string, detected method). The CLI layer (`creds.py`) is responsible for HTTP execution when the parser signals a POST /auth curl.

**Parser contract change**: `parse_curl()` currently returns `dict[str, str]` (env key → value). For POST /auth curls, the parser raises a new exception subclass `PostAuthCurlDetected(CredentialImportError)` carrying the extracted components (URL, headers dict, body string). This preserves the existing return type for all non-POST-auth paths. The caller (`import_creds()` in `creds.py`) catches `PostAuthCurlDetected` and branches into the execution path; all other `CredentialImportError` subclasses propagate as before.

### TN-2: POST /auth Body Types and Expected Behavior

| Body type | gc-token contains | Expected behavior |
|-----------|-------------------|-------------------|
| `{"type":"refresh"}` | Refresh token (14 days) | Execute → parse gc_auth response → write tokens + headers to .env |
| `{"type":"password","password":"..."}` | Client token (10 min) | Execute → parse gc_auth response → write tokens + headers to .env. **Password in body must never be logged/stored/displayed.** Response shape inferred from proxy observations (not independently confirmed via direct curl); if shape differs, surfaces as a "no tokens" error, not a code bug. |
| `{"type":"client-auth","client_id":"..."}` | No gc-token header | Execute → response contains only client token (not importable for credential refresh). Inform user: "This is a client-auth request; copy a refresh-type POST /auth curl instead." |
| `{"type":"user-auth","email":"..."}` | Client token | Execute → response does not contain access/refresh tokens. Inform user similarly. |
| `{"type":"logout"}` | Refresh token | **DO NOT EXECUTE.** Executing a logout curl invalidates the refresh token server-side, destroying the user's session. Detect the body type pre-execution and reject immediately: "This is a logout curl. Running it would end your GameChanger session. Copy a POST /auth curl with `{"type":"refresh"}` body instead." |

Body types are split into three categories:
1. **Token-yielding** (refresh, password): Execute and parse response for credentials.
2. **Non-token, safe** (client-auth, user-auth): Execute, but response won't contain importable tokens. Catch the parse failure and provide targeted guidance.
3. **Destructive** (logout): Reject pre-execution without making the HTTP call.

### TN-3: POST /auth Detection Heuristic

A curl is a POST /auth curl when:
1. URL path is exactly `/auth` (after stripping query params)
2. Method is POST -- detected from explicit `-X POST` flag, OR from presence of `--data-raw`/`-d`/`--data`/`--data-binary` (curl defaults to POST when data flags are present)

Both conditions must be true.

### TN-4: Request Component Extraction

The parser must capture from the curl tokens:
- **URL**: Full URL (already extracted by `parse_curl()`)
- **Headers**: All `-H`/`--header` values as a raw dict (name → value), built by direct string splitting of each `-H` value on the first `:`. This MUST NOT route through `_process_header()` -- that function filters credentials and drops headers in `_SKIP_HEADERS` (which includes `Content-Type`, required for POST /auth execution). All headers must be preserved: gc-signature, gc-timestamp, gc-token, gc-device-id, gc-client-id, gc-app-name, gc-app-version, Content-Type, Accept, User-Agent, etc.
- **Body**: The value from `--data-raw`, `-d`, `--data`, or `--data-binary` flag. This is the JSON body to POST.
- **Method**: POST (confirmed by detection heuristic)

### TN-5: HTTP Execution Requirements

- **HTTP discipline exception**: This is a one-shot curl replay, NOT a normal API session. The project's `create_session()` (from `src/http/session.py`) MUST NOT be used -- it injects project default headers (User-Agent, Accept, etc.) which would override the captured curl's headers. The gc-signature was computed for the original request parameters; substituting headers could invalidate it. Use a plain `httpx.Client()` (or `httpx.post()`) with no default headers, a 30-second timeout, and `follow_redirects=False`.
- Pass all extracted headers verbatim (the gc-signature is pre-computed in the curl)
- Pass the body as `content=body_bytes` (not `json=`) to preserve exact encoding
- **Security**: Never log the request body (may contain password), request headers (contain tokens/signatures), or response body (contains tokens). Only log the URL path and response status code.

### TN-6: Error Handling Matrix

| HTTP Status | Response Body | Meaning | User Message |
|-------------|---------------|---------|-------------|
| 200 | JSON gc_auth shape | Success | (proceed to credential extraction) |
| 200 | JSON without tokens or non-JSON body | Non-token body type response or unparseable response | "This POST /auth response did not contain access/refresh tokens. Copy a curl from a refresh-type POST /auth request in browser dev tools (filter Network tab by 'auth', look for requests with `{"type":"refresh"}` body)." |
| 400 | Plain text "Bad Request" | gc-timestamp/signature stale | "The gc-signature in this curl has expired. Copy a fresh curl from browser dev tools and run `bb creds import` again immediately." |
| 401 | Any | Auth failure (wrong token type, expired token) | "Authentication failed (HTTP 401). The token in this curl may be expired. Copy a fresh curl from browser dev tools." |
| Other 4xx/5xx | Any | Unexpected error | "POST /auth request failed with HTTP {status}. Copy a fresh curl and try again." |
| Network error | N/A | Connection failure | "Could not connect to GameChanger API. Check your network connection." |

**Implementation note**: On a 200 response, the CLI must catch ALL `CredentialImportError` variants from `_parse_json_credentials()` -- including `"Invalid JSON"` (non-JSON body), `"unrecognised shape"` (unexpected JSON structure), and `"No credentials could be extracted"` (valid shape but no tokens for this profile). All should map to the "no tokens" user message above, not expose raw parse errors.

### TN-7: Credential Merging for POST /auth

Three sources of credentials are merged into .env:
1. **From response body**: Access and refresh tokens, extracted via `_parse_json_credentials()` with the existing gc_auth shape handler
2. **From request headers**: gc-device-id, gc-client-id, gc-app-name -- extracted using the header-to-env-key mapping from `_non_token_credential_keys()` in `credential_parser.py`. Note: this function is module-private by convention (leading underscore). The implementer should either make it public (drop the underscore) or extract non-token credentials from the raw headers dict directly in `creds.py` using the same mapping logic.
3. **From request URL**: `GAMECHANGER_BASE_URL` -- derived from the POST /auth curl's URL (scheme + host, e.g., `https://api.team-manager.gc.com`). This mirrors the existing `parse_curl()` behavior at line 245 of `credential_parser.py`, which the POST /auth path bypasses.

All three sources use the same profile suffix (`_WEB` or `_MOBILE`) where applicable. The merged dict is passed to `merge_env_file()` as a single write.

### TN-8: Warning Message Fix

The current warning in `_resolve_web_token_key()` (line ~270) says:
> "To capture a refresh token, copy a curl command from a POST /auth request..."

Replace with guidance that reflects the post-E-175 capability:
> "To import a refresh token: copy a POST /auth curl from browser dev tools (tokens will be extracted automatically), paste the JSON response from POST /auth, or copy a curl from a GET request that carries a refresh token in the gc-token header."

### TN-9: Password Security

The `--data-raw` body may contain `{"type":"password","password":"..."}`. Security requirements:
- The body string is extracted by the parser and passed to the CLI layer for execution
- The body is used ONLY as the HTTP request content -- never logged, never written to .env, never displayed in console output
- After the HTTP call completes, the body string should not be retained (normal Python GC handles this; no special zeroing required)
- The `_print_import_summary()` function already only prints env key names, not values -- this is sufficient

## Open Questions
- None remaining -- all discovery questions resolved by expert consultation or user decision (support all body types).

## History
- 2026-03-28: Created (DRAFT). Expert consultation: api-scout (POST /auth body types, gc-signature expiration, error codes), SE (consultation sent, pending at draft time).
- 2026-03-28: Set to READY after 2 review iterations (1 internal + 1 Codex). 22 findings triaged, 18 accepted, 4 dismissed.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic team (PM) | 5 | 3 | 2 |
| Internal iteration 1 -- Holistic team (api-scout) | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic team (SE) | 4 | 3 | 1 |
| Codex iteration 1 | 5 | 4 | 1 |
| **Total** | **22** | **18** | **4** |
