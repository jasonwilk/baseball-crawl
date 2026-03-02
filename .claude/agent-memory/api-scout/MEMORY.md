# API Scout -- Agent Memory

## Credential Lifecycle

Credentials are short-lived. The user provides curl commands containing live tokens. The script `scripts/refresh_credentials.py` extracts and stores them in `.env`. Tokens expire frequently -- always check for auth errors before assuming an endpoint has changed.

Credentials are NEVER logged, committed, or displayed. Redact to `{AUTH_TOKEN}` in all documentation and output. If the user pastes a curl with real tokens, acknowledge receipt and immediately work with the redacted version.

## API Spec Location

Single source of truth: `docs/gamechanger-api.md`

Every documented endpoint follows this structure:
- URL pattern (with path parameters)
- HTTP method
- Required headers (credentials as `{PLACEHOLDER}`)
- Query parameters (name, type, required/optional, description)
- Response schema (JSON structure with types)
- Example response (sensitive data redacted)
- Known limitations
- Discovery date
- Changelog entry

All discoveries go into the spec immediately. Do not accumulate findings in memory or conversation -- write to the spec file.

## Exploration Status

As of 2026-02-28 -- API is undocumented. Exploration has not formally begun (E-001 credential parser is the first active story). All API knowledge is empirical -- discovered by running curl commands provided by the user.

Areas not yet explored:
- Authentication flow (token acquisition, refresh, expiration behavior)
- Team endpoints (roster, schedule, stats)
- Game endpoints (box scores, play-by-play)
- Player endpoints (stats, profiles)
- Opponent data availability
- Rate limiting behavior
- Pagination patterns

## Security Rules

These five rules are non-negotiable, every session:

1. NEVER display, log, or store actual API tokens, session cookies, or credentials in any committable file.
2. Use `{AUTH_TOKEN}`, `{SESSION_ID}`, or similar placeholders when documenting API calls.
3. When the user provides a curl with real credentials, immediately work with the redacted version in all documentation.
4. If credentials appear in any file outside `.env`, flag it as a security issue immediately.
5. Strip authentication headers from all stored raw API responses.

## HTTP Request Discipline

All GameChanger requests must present as a normal browser user:
- Realistic User-Agent (Chrome/Firefox, not python-requests)
- Standard browser headers (Accept, Accept-Language, Accept-Encoding, Referer/Origin)
- Maintain cookie jars across requests within a session
- Canonical header set lives in `src/http/headers.py`
- Rate limiting: 1-2 second delays between requests, exponential backoff on errors, jitter on timing
- Access resources in human-plausible order (list page before detail page)

## Agent Interactions

- **baseball-coach** defines what data is most important to find -- prioritize exploration accordingly
- **data-engineer** consumes the spec to design schemas and ingestion pipelines
- **general-dev** consumes the spec to implement API client code
- **product-manager** uses discoveries to write informed stories

## Key File Paths

- API spec: `docs/gamechanger-api.md`
- Credential extraction: `scripts/refresh_credentials.py`
- HTTP headers module: `src/http/headers.py`
- HTTP session module: `src/http/session.py`
- Local credentials: `.env` (gitignored)
