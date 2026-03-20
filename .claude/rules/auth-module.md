---
paths:
  - "src/gamechanger/signing.py"
  - "src/gamechanger/token_manager.py"
  - "src/gamechanger/client.py"
  - "src/gamechanger/exceptions.py"
---

# Auth Module Implementation Constraints

These rules apply when editing the GameChanger auth module files listed above. For HTTP-level rules (headers, rate limiting, session behavior), see `http-discipline.md`.

## Exception Hierarchy

All shared exceptions live in `src/gamechanger/exceptions.py` to avoid circular imports between `client.py` and `token_manager.py`.

- `ConfigurationError` -- missing or invalid env vars (raised at construction time)
- `CredentialExpiredError` -- HTTP 401 (token expired or invalid)
  - `ForbiddenError(CredentialExpiredError)` -- HTTP 403 (per-resource denial)
  - `LoginFailedError(CredentialExpiredError)` -- login flow failure
- `RateLimitError` -- HTTP 429
- `GameChangerAPIError` -- HTTP 5xx after retries
- `AuthSigningError` -- HTTP 400 on POST /auth (signature rejected); defined in `token_manager.py`, not `exceptions.py`

Catch order matters: catch `ForbiddenError` / `LoginFailedError` before `CredentialExpiredError`.

## httpx Client Choice

`TokenManager` creates its own standalone `httpx.Client(timeout=30, trust_env=False)` for POST /auth requests. Do NOT use `create_session()` from `src/http/session.py` -- the token manager must operate independently of the session factory (no circular dependency, no browser fingerprint headers on auth requests).

`GameChangerClient` uses `create_session()` for all data-plane GET requests.

## Environment Variable Access

- Use `dotenv_values()` to read `.env` -- this returns a dict without populating `os.environ`.
- `GameChangerClient._load_credentials()` falls back to `os.environ` only for Docker container compatibility (env vars injected by Compose).
- Default `.env` path: `Path(__file__).resolve().parents[2] / ".env"` (repo root).

## .env Write-Back

Rotated refresh tokens and generated device IDs are persisted via `atomic_merge_env_file()` from `src/gamechanger/credential_parser.py`. This function performs atomic read-modify-write to avoid corrupting `.env` on concurrent access. Write failures log a WARNING but do not raise -- the access token remains valid for ~60 minutes.

## Client Pattern

- **Lazy token fetch**: `GameChangerClient` calls `_ensure_access_token()` before every request; the `TokenManager` caches the token and only hits POST /auth when expired.
- **401 retry**: On HTTP 401, the client calls `token_manager.force_refresh()` and retries once. If the retry also returns 401, raise `CredentialExpiredError`.
- **Login fallback**: When refresh token is expired (401) and email/password are configured, `TokenManager` automatically attempts the 3-step login flow (client-auth, user-auth, password).

## Security

- NEVER log, display, or hardcode tokens, client keys, or passwords.
- The client key (`GAMECHANGER_CLIENT_KEY_*`) is a shared HMAC-SHA256 secret -- treat as equivalent to a private key.
- JWT payloads may contain PII (email, user ID) -- do not log decoded token contents.
- Signature timestamps use `int(time.time())` -- clock skew causes HTTP 400 (not 401).
