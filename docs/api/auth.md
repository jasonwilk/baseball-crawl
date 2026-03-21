# Authentication

GameChanger uses a custom JWT-based authentication scheme with a three-token architecture. There is no standard OAuth or API key flow. The signing algorithm has been fully reverse-engineered (2026-03-07), enabling fully programmatic token refresh and login without browser captures.

## Three-Token Architecture (Confirmed 2026-03-07)

GC uses three distinct JWT types with different lifetimes and purposes:

| Token | `type` field | JWT `kid` | Lifetime | JWT Fields | Purpose |
|-------|-------------|-----------|----------|------------|---------|
| **Client token** | `"client"` | `fd4b4904-...` | 10 minutes | `type`, `sid`, `cid`, `iat`, `exp` | Anonymous session token; used as `gc-token` during steps 3 and 4 of the login flow |
| **Access token** | `"user"` | `fd4b4904-...` | ~60 minutes (web); ~12 hours (mobile) | `type`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp` | Authenticates all standard API requests (`gc-token` header) |
| **Refresh token** | (none) | `b3503b45-...` | 14 days | `id`, `cid`, `uid`, `email`, `iat`, `exp` | Obtains a new access+refresh token pair via `POST /auth {type:"refresh"}` |

**How to distinguish token types by decoding the JWT:**
- `type == "client"` → client token (has `sid` field, no user identity)
- `type == "user"` → access token (~60 min web, ~12 hours mobile)
- No `type` field (and different `kid`) → refresh token (14 days)
- Quick heuristic without decoding: `exp - iat < 50,000` → access token (covers both web ~3,600s and mobile ~43,997s); `exp - iat > 1,000,000` → refresh token. Note: the old threshold of `< 10,000` is too narrow for mobile access tokens.

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
| `exp` | int | Token expiry (Unix seconds). `exp - iat ≈ 3,600` (~60 minutes) for web profile; `exp - iat ≈ 43,997` (~12 hours) for mobile profile. |

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

For step-by-step extraction and recovery procedures, see [Client Key Extraction](#client-key-extraction).

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

**Login fallback:** `TokenManager` automatically recovers from expired refresh tokens (HTTP 401 on refresh) by performing the full login flow (steps 2-4 above: client-auth, user-auth, password). This is web profile only and requires `GAMECHANGER_USER_EMAIL` and `GAMECHANGER_USER_PASSWORD` in `.env` or the Docker environment. If login credentials are absent, `CredentialExpiredError` is raised as before. The fallback is triggered from the `get_access_token()` path and from `force_refresh(allow_login_fallback=True)` calls. On login failure, `LoginFailedError` is raised with diagnostic context.

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

## Client Key Extraction

The client key (`GAMECHANGER_CLIENT_KEY_WEB`) is embedded in the GameChanger web JavaScript bundle. It must be re-extracted whenever GC redeploys their bundle. This section documents how to detect a stale key and how to extract a fresh one -- automatically or manually.

**Key characteristics:**
- The client key is **app-wide** -- the same value for all GC users, not per-user or per-session
- `GAMECHANGER_CLIENT_ID_WEB` may also change at the same time -- both values come from the same composite string in the bundle
- The variable name in the JS bundle is `EDEN_AUTH_CLIENT_KEY`, in the format `clientId:clientKey`
- The JS bundle URL pattern is `https://web.gc.com/static/js/index.{hash}.js` -- the hash changes with each deployment
- Rotations are unpredictable (potentially months apart), but always coincide with a GC web bundle redeployment
- **Never cache the bundle URL between extraction runs** -- always fetch the HTML page fresh, since the hash changes on every GC deployment

### How to Know the Key Is Stale

**Symptom:** All authentication fails. `bb creds refresh` reports "Credentials expired" or a signature-rejected error. `bb creds check` shows `[XX]` on the Client Key section.

**Cause:** GC redeployed their JavaScript bundle with a new `EDEN_AUTH_CLIENT_KEY` value. The `gc-signature` HMAC is being computed with the wrong (stale) key.

**The misleading diagnostic path:** The refresh token appears valid and the presence check passes, but every `POST /auth` call fails with HTTP 401. This looks identical to an expired refresh token because the server returns the same HTTP 401 status code for both a stale client key and an expired refresh token. The current code maps HTTP 401 to `CredentialExpiredError` -- but in the stale-key scenario, the same error path is hit, producing a misleading "Refresh token rejected" / "Credentials expired" message.

**How to distinguish:** If `bb creds check` shows the refresh token is within its 14-day window but refresh calls still fail, suspect a stale client key before concluding the refresh token is invalid. Run `bb creds extract-key` to check whether the bundle contains a different key than what is in `.env`.

### Automated Extraction

Use the `bb creds extract-key` command to fetch the current client key from the live JS bundle and compare it against `.env`.

**Dry-run (default):** Shows what would change without writing anything:

```
$ bb creds extract-key
Fetching bundle from https://web.gc.com...
Parsing EDEN_AUTH_CLIENT_KEY from index.{hash}.js...

Client ID:  {current-value} -> {new-value}
Client Key: [changed]

Run with --apply to update .env
```

**Apply mode:** Writes updated values to `.env`:

```
$ bb creds extract-key --apply
Fetching bundle from https://web.gc.com...
Parsing EDEN_AUTH_CLIENT_KEY from index.{hash}.js...

Client ID:  [unchanged]
Client Key: [changed]

.env updated. Run `bb creds check --profile web` to verify, then `bb creds refresh --profile web`.
```

**If the key is already current:**

```
$ bb creds extract-key
Client key is current (no update needed).
```

**Error exits (exit code 1):**
- HTML page fetch failed
- Bundle script URL not found in the HTML page
- `EDEN_AUTH_CLIENT_KEY` not found in the bundle

**Note on validation:** The `bb creds check` client key validation uses the step-2 client-auth call (`POST /auth {"type": "client-auth", ...}`). This call is ideal for validation because it requires no `previousSignature` -- it is always the first call in any login sequence -- so it can be executed independently at any time without depending on a prior response in the chain.

### Manual Extraction (Browser DevTools)

Use this procedure if `bb creds extract-key` is unavailable or fails.

1. Open `https://web.gc.com` in Google Chrome and wait for the page to fully load.
2. Open Chrome DevTools (F12, or Cmd+Option+I on macOS).
3. Go to the **Sources** tab.
4. Press Cmd+Shift+F (macOS) or Ctrl+Shift+F (Windows/Linux) to open the global search across all loaded files.
5. Search for `EDEN_AUTH_CLIENT_KEY`.
6. Open the matching result -- it will be in a file like `index.{hash}.js` under `web.gc.com/static/js/`.
7. The value is a composite string in the format `clientId:clientKey`, for example: `EDEN_AUTH_CLIENT_KEY:"{uuid}:{base64-string}"`.
8. Copy the full composite value (everything inside the quotes, not including the quotes themselves).
9. Split on the **first** `:` to separate the two parts:
   - Left side = UUID → `GAMECHANGER_CLIENT_ID_WEB`
   - Right side = base64 string → `GAMECHANGER_CLIENT_KEY_WEB`
10. Update `.env` with the new values for `GAMECHANGER_CLIENT_ID_WEB` and `GAMECHANGER_CLIENT_KEY_WEB`.

### Verification

After updating `.env` (via either method):

1. Run `bb creds check --profile web` and confirm the Client Key section shows `[OK]`.
2. Run `bb creds refresh --profile web` to confirm the token refresh succeeds end-to-end.

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

## Mobile Profile Differences (Confirmed 2026-03-08)

The mobile (iOS) profile uses a distinct client identity and has a significantly longer access token lifetime. These differences were confirmed from a live POST /auth refresh response captured via mitmweb on 2026-03-08.

### Mobile Client ID

The mobile client ID is **different from the web client ID**:

| Profile | Client ID (`gc-client-id` / JWT `cid`) |
|---------|----------------------------------------|
| Web | `07cb985d-ff6c-429d-992c-b8a0d44e6fc3` |
| Mobile (iOS) | `0f18f027-c51e-4122-a330-9d537beb83e0` |

Because the client ID differs, the mobile client **key** almost certainly also differs (the key is bundled alongside the client ID in the app binary as `{clientId}:{clientKey}`). The mobile client key has NOT yet been extracted -- it is embedded in the iOS binary and would require binary analysis to obtain. Do not assume the web client key works for mobile signing.

Store as `GAMECHANGER_CLIENT_ID_MOBILE` in `.env`. The corresponding `GAMECHANGER_CLIENT_KEY_MOBILE` is unknown; leave commented out until extracted.

### Mobile Token Lifetimes

| Token | Web Lifetime | Mobile Lifetime |
|-------|-------------|-----------------|
| Access token | ~3,600s (~60 minutes) | ~43,997s (~12 hours) |
| Refresh token | 1,209,600s (14 days) | 1,209,600s (14 days) |

The mobile access token lifetime (~12 hours) is approximately 12x longer than the web access token. This affects how frequently programmatic token refresh is needed for mobile-profile sessions.

**Distinguish-by-lifetime heuristic update for mobile access tokens:** `exp - iat ≈ 43,997` for mobile access tokens. The `type == "user"` field is still present and authoritative; do not rely solely on lifetime for type detection across profiles.

### Mobile JWT Structure

Despite the different client ID and token lifetime, the mobile JWT payload structure is **identical to web**:

| Token | JWT `kid` | `type` field | Payload Fields |
|-------|-----------|-------------|----------------|
| Access token | `fd4b4904-39e0-48ca-a932-59d1e45aca30` | `"user"` | `type`, `cid`, `email`, `userId`, `rtkn`, `iat`, `exp` |
| Refresh token | `b3503b45-e2aa-4e86-918c-54bf6dea87b9` | (none) | `id`, `cid`, `uid`, `email`, `iat`, `exp` |

The JWT `kid` values are the same across web and mobile profiles.

### Mobile POST /auth Response Shape

The POST /auth response shape is **identical** between web and mobile:

```json
{
  "type": "token",
  "access": {"data": "<jwt>", "expires": <unix-ts>},
  "refresh": {"data": "<jwt>", "expires": <unix-ts>}
}
```

### Mobile POST /auth Content-Type Difference

Mobile uses a different `Content-Type` for POST /auth requests:

| Profile | Content-Type |
|---------|-------------|
| Web | `application/json; charset=utf-8` |
| Mobile (iOS) | `application/vnd.gc.com.post_eden_auth+json; version=1.0.0` |

The `post_eden_auth` vendor type is mobile-specific. Despite this header difference, the response schema is confirmed identical. Whether the request body format also differs is not yet confirmed -- see `epics/E-075-mobile-credential-capture/R-01-findings.md` for open questions.

## Source Materials

- `data/raw/gc-signature-algorithm.md` -- full reverse-engineered algorithm with JS pseudocode
- `data/raw/gc-auth-module.js` -- original captured JS auth module from web.gc.com
- `data/raw/auth-login-flow-findings.json` -- complete 4-step login flow documentation
- `data/raw/auth-refresh-findings.json` -- refresh flow documentation and programmatic confirmation
