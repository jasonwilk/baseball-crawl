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

As of 2026-03-04. All API knowledge is empirical -- discovered by running curl commands provided by the user.

### Confirmed Endpoints

| Endpoint | Status | Discovered |
|----------|--------|------------|
| `GET /me/teams` | Confirmed from capture | Pre-2026-03-01 |
| `GET /teams/{id}/schedule` | Confirmed from capture | Pre-2026-03-01 |
| `GET /teams/{id}/game-summaries` | Confirmed LIVE, 34 records | Pre-2026-03-01 |
| `GET /teams/{id}/players` | Confirmed from capture | Pre-2026-03-01 |
| `GET /teams/{id}/video-stream/assets` | Confirmed, 3 pages | Pre-2026-03-01 |
| `GET /teams/{id}/season-stats` | Confirmed LIVE, 200 OK | 2026-03-04 |

### Season-Stats Key Facts (2026-03-04)

- Returns full-season batting/pitching/fielding aggregates for all players on a team
- Response is a single object (not array), no pagination observed
- Players keyed by UUID only -- no names; must join with /players endpoint
- Defense section merges pitching AND fielding into one object (use GP:P / GP:F to split)
- `IP:POS` fields (IP:1B, IP:2B, etc.) are in fractional thirds (218.67 = 218 innings + 2 outs)
- `AB/HR` field only appears when HR > 0
- New gc-user-action value: `data_loading:team_stats`
- Accept header: `application/vnd.gc.com.team_season_stats+json; version=0.2.0`
- **Stat glossary**: `docs/gamechanger-stat-glossary.md` created alongside this endpoint. Maps all GC stat abbreviations to definitions (sourced from GC UI). Includes API field name mapping table for abbreviations that differ between UI and API (e.g., K-L -> SOL, HHB -> HARD). The API spec's season-stats schema cross-references this glossary.

### Areas Not Yet Explored

- Authentication flow (token acquisition, refresh, expiration behavior)
- Game endpoints (box scores, play-by-play)
- Player endpoints (individual stats, profiles)
- Opponent season-stats availability (does /season-stats work for opponent team UUIDs?)
- Season scoping (query params for filtering by season/year)
- Rate limiting behavior
- Cold streak data (`streak_C`) -- only hot streak `streak_H` confirmed

## Security Rules

These five rules are non-negotiable, every session:

1. NEVER display, log, or store actual API tokens, session cookies, or credentials in any committable file.
2. Use `{AUTH_TOKEN}`, `{SESSION_ID}`, or similar placeholders when documenting API calls.
3. When the user provides a curl with real credentials, immediately work with the redacted version in all documentation.
4. If credentials appear in any file outside `.env`, flag it as a security issue immediately.
5. Strip authentication headers from all stored raw API responses.

## HTTP Request Discipline
See CLAUDE.md HTTP Request Discipline section.
- Canonical header set lives in `src/http/headers.py`

## Agent Interactions

- **baseball-coach** defines what data is most important to find -- prioritize exploration accordingly
- **data-engineer** consumes the spec to design schemas and ingestion pipelines
- **general-dev** consumes the spec to implement API client code
- **product-manager** uses discoveries to write informed stories

## Key File Paths

- API spec: `docs/gamechanger-api.md`
- Stat glossary: `docs/gamechanger-stat-glossary.md` (cross-referenced from API spec's season-stats schema)
- Credential extraction: `scripts/refresh_credentials.py`
- HTTP headers module: `src/http/headers.py`
- HTTP session module: `src/http/session.py`
- Local credentials: `.env` (gitignored)
