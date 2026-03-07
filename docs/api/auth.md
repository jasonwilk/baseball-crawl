# Authentication

GameChanger uses a custom JWT-based authentication scheme. There is no standard OAuth or API key flow. Credentials come from browser captures.

## Required Credentials

Two values must be present in `.env` and injected into every authenticated request:

| Variable | Description |
|----------|-------------|
| `GC_TOKEN` | JWT session token (14-day lifetime) |
| `GC_DEVICE_ID` | Stable 32-character hex device identifier |

See `headers.md` for how these values map to request headers.

## JWT Structure

The `gc-token` is a standard JWT. Decoded payload fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Compound identifier: `{session_uuid}:{refresh_token_uuid}` |
| `cid` | UUID | Client identifier. Matches the `gc-client-id` header used in `POST /auth`. Store this alongside `gc-device-id`. |
| `uid` | UUID | Authenticated user's UUID. Same as the `id` field returned by `GET /me/user`. |
| `email` | string | User's email address. **PII -- never log or store.** |
| `iat` | int | Token issued-at (Unix seconds) |
| `exp` | int | Token expiry (Unix seconds). `exp - iat = 1,209,600` (14 days). |

Previously documented fields `type`, `userId`, and `rtkn` were NOT observed in decoded tokens from 2026-03-04 captures. These may have been speculative. Do not rely on them.

## Token Lifetime

**14 days** (confirmed from `exp - iat = 1,209,600` seconds in decoded JWT payload, 2026-03-04).

The earlier estimate of ~1 hour was incorrect. Token rotation is needed approximately every two weeks, not hourly. Batch ingestion pipelines can run for days under a single token. Use `GET /me/user` as a pre-flight health check before long runs.

## Token Health Check

```
GET /me/user
```

Returns HTTP 200 if the `gc-token` is valid, HTTP 401 if expired. This is the recommended pre-flight check before starting a long ingestion run.

## Token Refresh

**Programmatic token refresh is NOT currently possible.**

The `POST /auth` endpoint with `{"type": "refresh"}` exists but requires a `gc-signature` HMAC header. The signing key is embedded in browser JavaScript and has not been extracted. Until the signing algorithm is reversed, tokens must come from browser captures.

**Freshness window for `gc-signature`:** The signature and accompanying `gc-timestamp` are time-bound. A signature computed 22,316 seconds (~6.2 hours) before the request was rejected with HTTP 400. Execute browser captures and extract credentials promptly after capture (within minutes, not hours).

**Token rotation workflow:**
1. User opens a browser, logs into GameChanger
2. mitmproxy intercepts traffic and captures the gc-token and gc-device-id
3. Credentials are stored in `.env`
4. New gc-token is valid for up to 14 days

See `docs/admin/mitmproxy-guide.md` for the proxy setup guide and credential capture workflow.

## Public Endpoints (No Auth)

Some endpoints under the `/public/` path prefix require NO authentication. Do not include `gc-token` or `gc-device-id` headers on these requests.

Confirmed public (no auth) endpoints:
- `GET /public/teams/{public_id}` -- team profile
- `GET /public/teams/{public_id}/games` -- game schedule with scores
- `GET /public/teams/{public_id}/games/preview` -- game schedule (near-duplicate)
- `GET /public/game-stream-processing/{game_stream_id}/details` -- game line scores

**Warning:** Some endpoints with `/public/` in the path STILL REQUIRE authentication:
- `GET /teams/public/{public_id}/access-level` -- returns HTTP 401 without gc-token
- `GET /teams/public/{public_id}/id` -- returns HTTP 401 without gc-token

The `/teams/public/` path prefix (note: `teams` before `public`) is an authenticated path. Only endpoints under `/public/teams/` are unauthenticated. Check each endpoint file for its `auth` frontmatter field.

## Security Rules

- **Never hardcode credentials** in source code, tests, or configuration files
- **Never log tokens** -- treat `gc-token` as sensitive at all times
- **Use `.env` files** for local development (gitignored)
- **Use environment variables** for production (Docker Compose reads `.env` automatically)
- Strip or redact auth headers before storing raw API response samples
