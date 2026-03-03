<!-- synthetic-test-data -->
# E-001: GameChanger API Foundation

## Status
`ACTIVE`

## Overview
Establish the foundational layer for all GameChanger API access: credential extraction from user-provided curl commands, a rotating-credential management system, an authenticated HTTP client utility, and a living API specification document. Every other epic in this project depends on this foundation being solid.

## Background & Context
GameChanger is a commercial platform used by Lincoln Standing Bear High School coaches to track stats for their Freshman, JV, Reserve, and Varsity teams. The platform does not offer a self-service developer API -- instead, the user extracts credentials by capturing network traffic (via curl commands) from the GameChanger web or mobile interface.

These credentials are short-lived and rotate frequently. The system must handle credential expiry gracefully, and the user must be able to refresh credentials without touching application code.

The user will provide curl commands as the primary mechanism for bootstrapping API access. From those curl commands we extract: base URL (`https://api.team-manager.gc.com`), authentication headers (`gc-token`, `gc-device-id`, `gc-app-name`), endpoint paths, and query parameter shapes.

The canonical API spec document (`docs/gamechanger-api.md`) serves as the single source of truth for what endpoints exist, what they return, and any known quirks or rate limits.

## Goals
- A Python utility (`src/gamechanger/client.py`) that makes authenticated requests to the GameChanger API, handles 401/403 errors, and raises a clear error when credentials need refreshing
- A credential configuration system that reads credentials from environment variables or a local secrets file (never hardcoded)
- A CLI tool or script (`scripts/refresh_credentials.py`) that accepts a raw curl command string and extracts/persists the credentials it contains
- An API spec document (`docs/gamechanger-api.md`) with at least the endpoints needed by E-002
- Proof that the client works: a smoke test script that calls at least one live endpoint and prints a response summary

## Non-Goals
- Automatic credential refresh (i.e., automatically re-authenticating when a token expires) -- credentials are short-lived enough that manual refresh is acceptable for now
- OAuth flows or any first-party authentication implementation
- Storing credentials in a remote secrets manager (Cloudflare Secrets, AWS SSM, etc.) -- that's infrastructure work for a later epic
- Parsing or normalizing API responses -- that belongs to E-002
- Any dashboard or UI work

## Success Criteria
- Given a fresh curl command string from the user, `scripts/refresh_credentials.py` extracts and stores credentials in under 30 seconds with no manual editing of config files
- Given valid credentials, `src/gamechanger/client.py` successfully completes a GET request to at least one GameChanger endpoint and returns the parsed JSON
- Given expired/invalid credentials, the client raises a `CredentialExpiredError` with a message that tells the user exactly how to refresh
- `docs/gamechanger-api.md` documents at least: base URL, authentication scheme, and the endpoints needed to retrieve team roster, game schedule, and game summaries
- All code passes the project's style requirements (type hints, docstrings, pathlib, logging)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-001-01 | Extract credentials from curl and write credential parser | DONE | None | general-dev |
| E-001-02 | Build authenticated GameChanger HTTP client | DONE | E-001-01 (E-005-02 DONE) | general-dev |
| E-001-03 | Write GameChanger API spec document | DONE | None | general-dev |
| E-001-04 | Smoke test: verify client against live API | DONE | E-001-02, E-001-03 | general-dev |

## Technical Notes

### Credential Storage
Credentials are stored in a `.env` file (gitignored) read by `python-dotenv`. The credential parser (`E-001-01`, `scripts/refresh_credentials.py`) writes to `.env`; the client (`E-001-02`) reads from it. Stored credential keys: `GAMECHANGER_AUTH_TOKEN`, `GAMECHANGER_DEVICE_ID`, `GAMECHANGER_APP_NAME`, `GAMECHANGER_BASE_URL`.

### Authentication Scheme (Confirmed)
GameChanger uses a custom `gc-token` header (NOT `Authorization: Bearer`) carrying a JWT. Two additional custom headers are required on every request: `gc-device-id` (stable 32-char hex device fingerprint) and `gc-app-name` (always `"web"`). Endpoint-specific `Accept` headers using vendor-typed media types are also required. See `docs/gamechanger-api.md` for the full header reference.

### Vendor-Typed Accept Headers
GameChanger requires endpoint-specific `Accept` headers using custom media types (e.g., `application/vnd.gc.com.game_summary:list+json; version=0.1.0`). Sending generic `application/json` may result in unexpected behavior. See the per-endpoint Accept header table in `docs/gamechanger-api.md`.

### HTTP Session Infrastructure (E-005)
E-001-02 must use `create_session()` from `src/http/session.py` as its HTTP client base, NOT create a bare `httpx.Client()`. The session factory provides browser-realistic headers, cookie persistence, and rate limiting. Auth credentials (`gc-token`, `gc-device-id`, `gc-app-name`) are injected on top of the base session. See `docs/http-integration-guide.md` for the integration pattern and `docs/gamechanger-api.md` "Notes for Implementers" section for GameChanger-specific injection.

### Rate Limiting
No rate limit responses (HTTP 429) have been observed from GameChanger. The HTTP session factory (`src/http/session.py`) enforces a default delay of 1000ms + 0-500ms jitter between requests. The client should still handle 429 responses with `Retry-After` header support as a safety measure.

### Credential Rotation
JWT tokens expire in approximately 1 hour (observed `exp - iat ~ 3864 seconds`). The JWT `exp` claim provides the exact expiry timestamp. A refresh token reference (`rtkn`) exists in the JWT payload but the refresh flow has not been confirmed. Credential refresh currently requires re-capturing from browser dev tools via `scripts/refresh_credentials.py`.

### Python Dependencies
- `httpx` (0.28.1) -- HTTP client
- `python-dotenv` (1.0.1) -- credential loading from `.env`
- `respx` (0.22.0) -- HTTP mocking for tests
- `pytest` (8.3.4) -- test runner

## Open Questions
All original open questions have been answered through API discovery (E-001-03). See `docs/gamechanger-api.md` for authoritative answers. Remaining unknowns:
- Exact response field name carrying the next-page cursor in paginated responses
- Whether a token refresh endpoint exists (JWT contains `rtkn` field but flow is unconfirmed)
- Game-level box score / player stats endpoint (not yet discovered -- game-summaries provides team scores but not individual player stats)

## History
- 2026-02-28: Created
- 2026-03-03: Refinement audit -- updated stale technical notes (auth scheme, rate limiting, credential rotation, dependencies all confirmed), resolved all 5 original open questions, corrected API spec path references to canonical `docs/gamechanger-api.md`, added E-005 session factory and vendor-typed Accept header notes, updated E-001-02 and E-001-04 stories with corrected ACs and technical approaches
- 2026-03-03: E-001-02 DONE -- GameChangerClient with 4 exception types, 17 unit tests, all 8 ACs verified by PM. E-001-04 now unblocked.
- 2026-03-03: E-001-04 DONE (code-complete) -- smoke test script at scripts/smoke_test.py, all 7 ACs verified by PM. Awaiting user validation against live API before epic can be marked COMPLETED.
