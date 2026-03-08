# E-073: API Documentation Validation Sweep

## Status
`READY`

## Overview
Systematically validate the entire GameChanger API documentation layer (`docs/api/`) against ground truth: proxy session captures (web and mobile), live programmatic API calls, and the working gc-signature auth implementation. This epic ensures every endpoint doc, header profile, auth behavior, and response schema is accurate and confirmed.

## Background & Context
On 2026-03-07 we completed a major documentation session: reverse-engineered the gc-signature HMAC-SHA256 algorithm, documented the three-token architecture, and ran a 4-agent accuracy review that found 8 real errors (stale variable names, wrong response schemas, incorrect token lifetimes). Those fixes were applied ad-hoc.

This epic takes that ad-hoc process and makes it **systematic**. The project now has 90 endpoint doc files, 6 global reference files, working programmatic token refresh, and a mature proxy capture infrastructure. We have the tools to validate everything -- we just need to run the validation end-to-end and fix what it finds.

**What exists today:**
- `docs/api/endpoints/` -- 90 endpoint doc files with YAML frontmatter (status, auth, profiles, Accept headers, etc.)
- `docs/api/` global files -- auth.md, headers.md, pagination.md, content-type.md, base-url.md, error-handling.md
- `proxy/data/sessions/` -- proxy session captures with endpoint-log.jsonl and header-report.json
- `scripts/proxy-endpoints.sh`, `scripts/proxy-report.sh` -- scripts for reading proxy data
- `src/gamechanger/client.py` -- GameChangerClient with working auth
- `src/http/headers.py` -- BROWSER_HEADERS and MOBILE_HEADERS canonical dicts
- Working gc-signature implementation enables programmatic POST /auth calls
- Web profile credentials available; mobile profile credentials NOT yet captured

**Expert consultation:** No expert consultation required -- this is a validation and documentation accuracy epic. The PM has deep context on the API infrastructure, proxy tooling, and endpoint doc structure from direct file review. api-scout will execute the live validation work as an implementer.

## Goals
- Every endpoint doc file has been compared against proxy capture data (where available) and live API response
- All web profile endpoints have programmatically confirmed `last_confirmed` dates
- Header parity between docs and actual traffic is verified (web profile; mobile where captures exist)
- Auth flow (all 5 POST /auth body types) is programmatically validated
- Mobile profile header differences are captured and documented
- Every endpoint doc `profiles.web.status` reflects actual verification state
- Undocumented endpoints (seen in traffic but no doc file) are identified and flagged

## Non-Goals
- Adding new endpoint documentation for never-before-seen endpoints (flag only; follow-up work)
- Changing the crawl pipeline or loaders
- Mobile profile credential capture automation (user handles proxy session manually)
- Response body deep-schema validation (field-by-field JSON schema checks) -- we validate shape (array/object/string) and key top-level fields, not every nested field
- Fixing the three HTTP 500 endpoints (IDEA-011 scope)

## Success Criteria
- A validation report exists showing pass/fail status for every documented endpoint (frontmatter consistency + live response match)
- All endpoint files with web profile verification have `last_confirmed: "2026-03-07"` (or current date) and `profiles.web.status: confirmed`
- Auth flow validation covers all 5 POST /auth body types with documented request/response schemas
- If mobile proxy captures exist, a parity report documents header differences between web and mobile profiles
- Zero known inaccuracies remain in `docs/api/` after the documentation corrections story completes

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-073-01 | API doc frontmatter validation script | TODO | None | - |
| E-073-02 | Web profile live endpoint validation | TODO | None | - |
| E-073-03 | Auth flow programmatic validation | TODO | None | - |
| E-073-04 | Mobile proxy capture analysis | TODO | E-073-02 (soft) | - |
| E-073-05 | Documentation correction sweep | TODO | E-073-01, E-073-02, E-073-03 | - |

## Dispatch Team
- software-engineer
- api-scout

## Technical Notes

### Validation Script Design (Story 01)
The validation script reads all 90 endpoint doc files, parses YAML frontmatter, and performs two types of checks:
1. **Frontmatter consistency** -- all required fields present, status values from the allowed set, Accept header format matches pattern, tags from the vocabulary, profiles section present.
2. **Proxy coverage cross-reference** -- reads endpoint-log.jsonl from proxy sessions, compares paths against documented endpoints. Outputs: (a) documented endpoints NOT seen in any proxy traffic, (b) proxy traffic paths NOT matching any doc file.

Output: structured report (JSON or formatted text) suitable for Story 05.

**Key files:** There is already a `scripts/validate_api_docs.py` with 36 tests from E-062. That script validates structural correctness of the docs. Story 01 extends it (or creates a companion script) to add proxy cross-referencing.

### Live Validation Approach (Story 02)
Use `GameChangerClient` to make real API calls against every documented endpoint that the web profile can reach. For each endpoint:
- Confirm HTTP status code matches expected (200 for CONFIRMED, document actual for OBSERVED)
- Confirm `response_shape` frontmatter matches actual response (array vs object vs string)
- Confirm `Accept` header value works (no 406 Not Acceptable)
- Record actual response for later doc comparison

**Rate limiting**: GameChangerClient already has delay/jitter. Use conservative timing (2+ seconds between calls). Group by domain (team endpoints together, public endpoints together) to mimic human access patterns.

**Parameterization**: Many endpoints require path parameters (team_id, event_id, game_stream_id, player_id). The validation script must resolve these from known data: `GET /me/teams` provides team_ids, `GET /teams/{id}/game-summaries` provides game_stream_ids, etc. Build a dependency chain that resolves IDs progressively.

**Endpoints that cannot be validated**: Some endpoints are destructive (PATCH /me/user), require specific conditions (event-series, RSVP), or are known to return 404/500 (see caveats in docs). These should be skipped with documented reason.

### Auth Validation (Story 03)
Five POST /auth body types to validate:
1. `{type: "refresh"}` -- already confirmed working programmatically
2. `{type: "client-auth", client_id: "..."}` -- establishes anonymous session
3. `{type: "user-auth", email: "..."}` -- identifies user within client session
4. `{type: "password", password: "..."}` -- authenticates (requires steps 2+3 first)
5. `{type: "logout"}` -- invalidates session

The gc-signature algorithm is cracked and working. Signature chaining between steps is documented. This story validates the documented request schemas, response schemas, and token types match reality.

**Caution**: Steps 2-4 constitute a full login flow with signature chaining. Step 5 (logout) invalidates the current session. Run these in a controlled sequence, and re-establish credentials afterward. Steps 2-4 should be tested as a chain, not independently.

### Mobile Capture Dependency (Story 04)
Mobile credentials are not yet captured. The user must:
1. Run a mobile proxy session on the Mac host (iOS device through mitmproxy)
2. Browse several pages in the GameChanger iOS app to generate traffic

Story 04 then reads the proxy session data and compares mobile headers/endpoints against web docs. This story has a **soft dependency** on Story 02 (so it can compare mobile findings against confirmed web behavior), but can proceed independently if proxy data exists.

If no mobile proxy session exists when this story is dispatched, the story should document what's needed and produce a checklist for the user, then mark itself DONE with the analysis framework in place.

### Credential Safety
All validation scripts must follow existing credential safety rules:
- Never log, print, or store actual token values
- Use `GameChangerClient` (which loads from `.env`) -- never hardcode credentials
- Test output should reference endpoint paths and status codes, not auth header values
- The auth flow validation (Story 03) must be especially careful: it handles passwords and refresh tokens

### File Locations
- Existing validation script: `/workspaces/baseball-crawl/scripts/validate_api_docs.py`
- Endpoint docs: `/workspaces/baseball-crawl/docs/api/endpoints/`
- Global reference files: `/workspaces/baseball-crawl/docs/api/` (auth.md, headers.md, etc.)
- Proxy session data: `/workspaces/baseball-crawl/proxy/data/sessions/`
- Header profiles: `/workspaces/baseball-crawl/src/http/headers.py`
- API client: `/workspaces/baseball-crawl/src/gamechanger/client.py`
- Frontmatter schema: `/workspaces/baseball-crawl/.claude/rules/api-docs.md`
- Endpoint-log JSONL schema: see `/workspaces/baseball-crawl/proxy/addons/endpoint_logger.py` for field definitions

## Open Questions
- None -- infrastructure is mature and well-understood.

## History
- 2026-03-07: Created. Motivated by ad-hoc accuracy review that found 8 real errors in API docs. This epic systematizes that process.
