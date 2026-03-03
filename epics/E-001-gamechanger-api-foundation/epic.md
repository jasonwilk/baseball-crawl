<!-- synthetic-test-data -->
# E-001: GameChanger API Foundation

## Status
`ACTIVE`

## Overview
Establish the foundational layer for all GameChanger API access: credential extraction from user-provided curl commands, a rotating-credential management system, an authenticated HTTP client utility, and a living API specification document. Every other epic in this project depends on this foundation being solid.

## Background & Context
GameChanger is a commercial platform used by Lincoln Standing Bear High School coaches to track stats for their Freshman, JV, Reserve, and Varsity teams. The platform does not offer a self-service developer API -- instead, the user extracts credentials by capturing network traffic (via curl commands) from the GameChanger web or mobile interface.

These credentials are short-lived and rotate frequently. The system must handle credential expiry gracefully, and the user must be able to refresh credentials without touching application code.

The user will provide curl commands as the primary mechanism for bootstrapping API access. From those curl commands we extract: base URL patterns, authentication headers (bearer tokens, cookies, or API keys), endpoint paths, and query parameter shapes.

A collaboratively maintained API spec document (`/.project/research/gamechanger-api-spec.md`) will serve as the single source of truth for what endpoints exist, what they return, and any known quirks or rate limits.

## Goals
- A Python utility (`src/gamechanger/client.py`) that makes authenticated requests to the GameChanger API, handles 401/403 errors, and raises a clear error when credentials need refreshing
- A credential configuration system that reads credentials from environment variables or a local secrets file (never hardcoded)
- A CLI tool or script (`scripts/refresh_credentials.py`) that accepts a raw curl command string and extracts/persists the credentials it contains
- An API spec document (`/.project/research/gamechanger-api-spec.md`) with at least the endpoints needed by E-002
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
- `/.project/research/gamechanger-api-spec.md` documents at least: base URL, authentication scheme, and the endpoints needed to retrieve team roster, game schedule, and game stats
- All code passes the project's style requirements (type hints, docstrings, pathlib, logging)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-001-01 | Extract credentials from curl and write credential parser | DONE | None | general-dev |
| E-001-02 | Build authenticated GameChanger HTTP client | TODO | E-001-01 | - |
| E-001-03 | Write GameChanger API spec document | DONE | None | general-dev |
| E-001-04 | Smoke test: verify client against live API | TODO | E-001-02, E-001-03 | - |

## Technical Notes

### Credential Storage
Credentials must never be committed to version control. Use one of:
- A `.env` file (gitignored) read by `python-dotenv`
- A `credentials.json` file in a gitignored `secrets/` directory

The credential parser (`E-001-01`) should write to whichever format is chosen here. The client (`E-001-02`) should read from the same format. Recommend `.env` for simplicity since `python-dotenv` is widely understood.

### Authentication Scheme (Unknown Until E-001-03)
GameChanger likely uses one of: bearer token in `Authorization` header, session cookie, or a combination. The exact scheme will be determined when the user provides a curl command. The client should be designed so the auth mechanism is injectable/configurable rather than hardcoded.

### Rate Limiting
Unknown at this stage. The client should include a configurable per-request delay (default: 500ms) and should log a warning if a 429 is received. Actual rate limit values will be documented in the API spec.

### Credential Rotation
Credentials rotate frequently (unknown cadence -- could be hours or days). The credential parser script must be re-runnable: running it again with new credentials overwrites the old ones cleanly. The client should detect a 401 response and raise `CredentialExpiredError` rather than retrying.

### Python Dependencies (Expected)
- `httpx` or `requests` for HTTP (prefer `httpx` for async-readiness)
- `python-dotenv` for credential loading
- Standard library `argparse` for the CLI script
- `pytest` for tests

## Open Questions
- What does a real GameChanger curl command look like? (User will provide; answers E-001-01 and E-001-03 immediately.)
- Are there multiple base URLs (e.g., separate auth endpoint vs. data endpoint)?
- What is the actual token expiry window? (Determines how urgent credential refresh UX needs to be.)
- Does GameChanger paginate responses? If so, what's the pagination scheme?
- Are opponent team stats accessible from the same API, or is there a different endpoint/permission scope?

## History
- 2026-02-28: Created
