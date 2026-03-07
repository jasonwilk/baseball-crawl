# Authentication

GameChanger uses a custom JWT-based authentication scheme with a three-token architecture. There is no standard OAuth or API key flow. The signing algorithm has been fully reverse-engineered (2026-03-07), enabling fully programmatic token refresh and login without browser captures.

## Three-Token Architecture (Confirmed 2026-03-07)

GC uses three distinct JWT types with different lifetimes and purposes:

| Token | `type` field | JWT `kid` | Lifetime | JWT Fields | Purpose |
|-------|-------------|-----------|----------|------------|---------|
| **Client token** | `"client"` | `fd4b4904-...` | 10 minutes | `type`, `sid`, `cid`, `iat`, `exp` | Anonymous session token; used as `gc-token` during steps 3 and 4 of the login flow |
| **Access token** | `"user"` | `fd4b4904-...` | ~60 minutes | `type`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp` | Authenticates all standard API requests (`gc-token` header) |
| **Refresh token** | (none) | `b3503b45-...` | 14 days | `id`, `cid`, `uid`, `email`, `iat`, `exp` | Obtains a new access+refresh token pair via `POST /auth {type:"refresh"}` |

**How to distinguish token types by decoding the JWT:**
- `type == "client"` → client token (has `sid` field, no user identity)
- `type == "user"` → access token (~60 min)
- No `type` field (and different `kid`) → refresh token (14 days)
- Quick heuristic without decoding: `exp - iat < 10,000` → access token; `exp - iat > 1,000,000` → refresh token

**Credential tier durability (most to least durable):**
1. **Client ID + Client Key** -- static app-wide secret; only changes on app deploys (potentially months or years)
2. **Refresh token** -- 14-day lifetime; self-renewing (each refresh call returns a new refresh token)
3. **Access token** -- ~61-minute lifetime; generated on demand via refresh; should not be stored

## JWT Payload Fields

### Access Token Payload

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"user"` |
| `cid` | UUID | Client identifier. Matches the `gc-client-id` header. |
| `email` | string | User's email address. **PII -- never log or store.** |
| `userId` | UUID | Authenticated user's UUID (camelCase -- note difference from refresh token's `uid`). |
| `rtkn` | string | Refresh token identifier (format: `{uuid}:{uuid}`). |
| `iat` | int | Token issued-at (Unix seconds) |
| `exp` | int | Token expiry (Unix seconds). `exp - iat ≈ 3,600` (~60 minutes). |

### Refresh Token Payload

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Compound identifier: `{session_uuid}:{refresh_token_uuid}` |
| `cid` | UUID | Client identifier. Matches the `gc-client-id` header. Same as access token `cid`. |
| `uid` | UUID | Authenticated user's UUID (lowercase -- note difference from access token's `userId`). |
| `email` | string | User's email address. **PII -- never log or store.** |
| `iat` | int | Token issued-at (Unix seconds) |
| `exp` | int | Token expiry (Unix seconds). `exp - iat = 1,209,600` (14 days). |

Note: Refresh token has no `type` field. Access token has no `id` field. The `cid` field is present in both and matches the `gc-client-id` request header.

### Client Token Payload

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"client"` |
| `sid` | UUID | Anonymous session identifier |
| `cid` | UUID | Client identifier. Matches `gc-client-id` header. |
| `iat` | int | Token issued-at (Unix seconds) |
| `exp` | int | Token expiry (Unix seconds). `exp - iat = 600` (10 minutes). |

Note: Client token has no user identity fields (`email`, `userId`, `uid`). It represents an anonymous app session.

## gc-signature Signing Algorithm (Fully Cracked 2026-03-07)

The `gc-signature` header implements request signing for `POST /auth`. The algorithm was fully reverse-engineered from the web.gc.com JavaScript bundle on 2026-03-07.

Source file: `data/raw/gc-signature-algorithm.md`. Original JS: `data/raw/gc-auth-module.js`.

### Format

```
gc-signature: {nonce}.{hmac}
```

- **nonce** = `Base64(random 32 bytes)` -- generated fresh per request
- **hmac** = `HMAC-SHA256(clientKey, message)` encoded as Base64

### HMAC Message Construction

The message is built by concatenating these values with `|` delimiters:

```
{timestamp}|{nonce_raw_bytes}|{sorted_body_values}[|{previousSignature_raw_bytes}]
```

Important encoding details:
- `timestamp` is appended as a decimal string, followed by `|`
- `nonce` is appended as **raw bytes** (parsed from Base64), not as the Base64 string
- `sorted_body_values` is the result of recursive body extraction (see below), values joined by `|`
- `previousSignature` is appended as **raw bytes** (parsed from Base64), NOT the Base64 string
- `previousSignature` is optional -- it is absent for standalone calls (refresh) where there is no prior response in the same chain

### Body Value Extraction

The request body is recursively flattened to leaf string values with keys sorted alphabetically:

```javascript
function valuesForSigner(obj) {
    if (Array.isArray(obj)) return obj.flatMap(valuesForSigner);
    switch (typeof obj) {
        case "object":
            return obj && Object.keys(obj).sort().flatMap(k => valuesForSigner(obj[k])) || ["null"];
        case "string": return [obj];
        case "number": return [String(obj)];
        case "undefined": return [];
    }
}
```

Examples:
- `{"type":"refresh"}` → `["refresh"]`
- `{"type":"client-auth","client_id":"abc"}` → keys sorted: `client_id, type` → `["abc", "client-auth"]`

### Signature Chaining

The server returns its own `gc-signature` in every response header. The client extracts the part after the dot (the HMAC component) and uses it as `previousSignature` in the NEXT request's message. This creates a chain that prevents replay attacks.

```javascript
// After receiving a response:
var responseSigParts = response.headers.get("gc-signature").split(".");
this.previousSignature = responseSigParts[1];  // store for next request
```

**Exception:** The `client-auth` step explicitly sets `usePreviousSignature: false` -- it is the first call in the login chain and has no prior response to chain from. For standalone refresh calls (no preceding POST /auth in the same session), previousSignature is also omitted.

### Header Assembly

```javascript
var timestamp = getTimestamp();          // unix epoch seconds
var nonce = generateNonce();             // Base64(random 32 bytes)
var sigParams = { timestamp, nonce };

if (this.previousSignature && usePreviousSignature) {
    sigParams.previousSignature = this.previousSignature;
}

var K = signPayload(this.clientKey, sigParams, requestBody);

headers["gc-signature"] = nonce + "." + K;
headers["gc-client-id"] = this.clientId;
headers["gc-timestamp"] = String(timestamp);
```

### Client Key

The `clientKey` is a **static, app-wide secret** hardcoded in the main web bundle as:

```
{clientId}:{clientKey}
```

The JS splits this on `:` and passes the two parts to the `AuthClient` constructor. The `clientKey` is a Base64-encoded 32-byte HMAC secret. It is the same for all users and only changes when the app bundle is redeployed.

Store in `.env` as `GAMECHANGER_CLIENT_KEY_WEB`. Store the `clientId` as `GAMECHANGER_CLIENT_ID_WEB`.

## Complete Login Flow (4 Steps)

For full programmatic login from credentials only (no existing tokens). Discovered from Chrome Network tab capture 2026-03-07.

Each step sends `POST /auth` with a different `type` in the body.

### Step 1: Logout (Invalidate Previous Session)

```
Body:      {"type": "logout"}
gc-token:  {REFRESH_TOKEN}           (previous session's refresh token)
gc-signature: required (generated)
```

Invalidates the previous session. Prevents dangling sessions.

### Step 2: Client Auth (Establish Anonymous Session)

```
Body:         {"type": "client-auth", "client_id": "{CLIENT_ID}"}
gc-token:     NOT SENT               (the only auth step with no gc-token header)
gc-signature: required (generated, usePreviousSignature: false)
```

Returns a **client token** (`type: "client"`, 10-minute lifetime). This token is used as `gc-token` in steps 3 and 4. The `client_id` in the body matches the `gc-client-id` header value.

### Step 3: User Auth (Identify User)

```
Body:      {"type": "user-auth", "email": "{EMAIL}"}
gc-token:  {CLIENT_TOKEN}            (from step 2)
gc-signature: required (chained from step 2 response)
```

Identifies the user by email within the client session. Does not authenticate -- just declares intent.

### Step 4: Password Auth (Authenticate)

```
Body:      {"type": "password", "password": "{PASSWORD}"}
gc-token:  {CLIENT_TOKEN}            (same client token as step 3)
gc-signature: required (chained from step 3 response)
```

Authenticates with password. Returns access token + refresh token on success.

## Token Refresh Flow (Programmatic -- Confirmed Working)

The preferred day-to-day flow. Requires only the refresh token and client key -- no password needed.

```
POST /auth
Body:         {"type": "refresh"}
gc-token:     {REFRESH_TOKEN}        (14-day refresh token)
gc-signature: {generated}            (no previousSignature needed for standalone refresh)
gc-timestamp: {unix_epoch_seconds}
gc-client-id: {CLIENT_ID}
gc-device-id: {DEVICE_ID}
gc-app-name:  web
gc-app-version: 0.0.0
Accept: */*
Content-Type: application/json; charset=utf-8
```

Response (200 OK):

```json
{
  "type": "token",
  "access": {"data": "<access-token-jwt>", "expires": "<unix-timestamp>"},
  "refresh": {"data": "<refresh-token-jwt>", "expires": "<unix-timestamp>"}
}
```

- `access.data`: New access token JWT (~60 minutes)
- `access.expires`: Unix timestamp for access token expiry
- `refresh.data`: New refresh token JWT (~14 days)
- `refresh.expires`: Unix timestamp for refresh token expiry

The new refresh token (`refresh.data`) replaces the old one in `.env`. The access token (`access.data`) is used for all API calls until it expires.

**Confirmed working programmatically from Python (2026-03-07).** No browser interaction required.

Source: `data/raw/auth-refresh-findings.json`.

## Required Credentials (.env Variables)

Updated credential architecture as of 2026-03-07. The `gc-signature` field is now generated programmatically, not stored.

| Variable | Description | Source |
|----------|-------------|--------|
| `GAMECHANGER_REFRESH_TOKEN_WEB` | Refresh token JWT (14-day lifetime). Used as `gc-token` in `POST /auth {type:"refresh"}`. Self-renewing -- updated after each refresh call. | Browser capture (once), then programmatic renewal |
| `GAMECHANGER_CLIENT_ID_WEB` | Stable UUID. The `clientId` half of the `clientId:clientKey` string from the app bundle. Used as `gc-client-id` header and as body field in `client-auth`. Matches `cid` in JWT payload. | App bundle (static) |
| `GAMECHANGER_CLIENT_KEY_WEB` | Base64-encoded 32-byte HMAC key. The `clientKey` half of the app bundle's `clientId:clientKey` string. Used to compute `gc-signature`. **Treat as a secret -- never log or commit.** | App bundle (static) |
| `GAMECHANGER_DEVICE_ID_WEB` | Stable 32-character hex device identifier. Used as `gc-device-id` header. | Browser capture (stable) |
| `GAMECHANGER_USER_EMAIL` | User account email. Used in `user-auth` step of full login flow. **PII -- never log or commit.** | Manual |
| `GAMECHANGER_USER_PASSWORD` | User account password. Used in `password` step of full login flow. **Sensitive -- never log or commit.** | Manual |

**Deprecated variables** (replaced 2026-03-07):

| Old Variable | Replaced By | Reason |
|-------------|-------------|--------|
| `GAMECHANGER_AUTH_TOKEN_WEB` | `GAMECHANGER_REFRESH_TOKEN_WEB` | Renamed for clarity; the stored token is the refresh token, not the access token |
| `GAMECHANGER_SIGNATURE_WEB` | (none -- computed) | Signature is now generated programmatically; no longer needs to be captured and stored |

See `headers.md` for how these values map to request headers.

## Token Health Check

```
GET /me/user
```

Returns HTTP 200 if the `gc-token` (access token) is valid, HTTP 401 if expired. Use as a pre-flight check before long ingestion runs. This endpoint does NOT accept refresh tokens -- pass the access token only.

## Browser Auto-Refresh Pattern (Observed 2026-03-07)

The browser implements automatic token refresh when the access token expires. Observed sequence from proxy session `2026-03-07_171705`:

```
17:19:28 POST /auth -> 200 (initial session auth with refresh token)
17:19:29 POST /auth -> 200 (second team auth)
17:19:49 POST /auth -> 401 (expired access token used as gc-token -- detected by browser)
17:19:49 POST /auth -> 200 (immediate retry with refresh token)
17:19:51 POST /auth -> 401 (another expired access token attempt)
17:19:52 POST /auth -> 200 (retry with refresh token)
18:11:06 POST /auth -> 200 (periodic refresh ~51 minutes later)
```

This confirms:
- The browser detects 401 and automatically retries with the refresh token
- The access and refresh tokens are stored separately
- The browser proactively refreshes before the ~61-minute access token expiry

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
- **Never log tokens, passwords, or the client key** -- treat all credential variables as sensitive at all times
- **Use `.env` files** for local development (gitignored)
- **Use environment variables** for production (Docker Compose reads `.env` automatically)
- Strip or redact auth headers before storing raw API response samples
- **The client key is a shared app secret.** It is not per-user. Compromising it could affect all GC users. Handle it with the same care as a personal token.

## Source Materials

- `data/raw/gc-signature-algorithm.md` -- full reverse-engineered algorithm with JS pseudocode
- `data/raw/gc-auth-module.js` -- original captured JS auth module from web.gc.com
- `data/raw/auth-login-flow-findings.json` -- complete 4-step login flow documentation
- `data/raw/auth-refresh-findings.json` -- refresh flow documentation and programmatic confirmation
