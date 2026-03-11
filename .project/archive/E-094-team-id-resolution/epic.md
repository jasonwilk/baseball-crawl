# E-094: Fix Team ID Resolution in Import and Crawl Pipeline

## Status
`COMPLETED`

## Overview
The team import path stores the `public_id` slug as both `team_id` AND `public_id` in the database. Since crawlers pass `team_id` to authenticated API endpoints that expect UUIDs, the entire `--source db` crawl pipeline is broken (500 errors). This epic fixes ID resolution at import time and adds metadata to the crawl config layer so future crawlers can distinguish endpoint style (authenticated UUID-based vs. public slug-based) per team.

## Background & Context
When a team is added via the admin UI (`POST /admin/teams`), the user provides a GameChanger URL or public_id slug. The current code calls `resolve_team(public_id)` (public API), gets a `TeamProfile` back, and inserts `public_id` as the `team_id` PK. The crawlers then call authenticated endpoints like `GET /teams/{team_id}/players` which expect UUIDs, producing 500 errors.

**API constraints (confirmed 2026-03-10, verified via HAR capture 2026-03-11 -- reverse bridge response format and 403 behavior confirmed for 2 owned teams and 8 opponent teams):**
- `GET /teams/public/{public_id}/id` -- reverse bridge, returns UUID. Auth required. Returns 403 for teams you do not belong to (only works for owned teams).
- `GET /me/teams` -- returns all account teams with both `id` (UUID) and `public_id`. Auth required. Only returns teams the user is a member of.
- `GET /teams/{uuid}/public-team-profile-id` -- forward bridge, returns public_id for a UUID. Auth required.
- Authenticated endpoints (`/teams/{uuid}/players`, `/teams/{uuid}/schedule`, etc.) require UUIDs.
- Public endpoints (`/public/teams/{public_id}`, `/public/teams/{public_id}/games`, `/teams/public/{public_id}/players`) use public_id slugs and require no auth.

**Key insight:** For owned teams, we can resolve public_id to UUID via the reverse bridge. For non-owned teams, we cannot get the UUID (403), but we do not need it -- public endpoints serve the same data using public_id. The crawl config layer needs to express this distinction so crawlers pick the right endpoint style.

Refined via team review (PM, SE, DE, api-scout) -- see History. Original API behavior confirmed via live testing.

## Goals
- Team import accepts any GC input (URL with public_id, bare public_id, or UUID) and stores the correct value in each column
- Owned teams have UUID as `team_id` (resolved via reverse bridge at import time)
- Non-owned teams store the public_id as `team_id` (no UUID available, no UUID needed)
- `url_parser.py` accepts UUIDs as valid input alongside public_id slugs
- Crawl config layer distinguishes owned vs. non-owned teams so crawlers can select the correct endpoint paths
- `--source db` crawl works end-to-end for owned teams

## Non-Goals
- Changing the `team_id` PK column type or schema (the column is TEXT, it can hold either UUIDs or public_id slugs)
- Adding UUID resolution for non-owned/opponent teams (they use public endpoints with public_id)
- Migrating existing YAML-config teams (YAML teams already have correct UUIDs from manual entry)
- Building public-endpoint crawlers for non-owned teams (future work -- the config layer just needs to express the distinction)
- Opponent UUID resolution via `/search/opponent-import` (response schema capture is a prerequisite for any future story using this endpoint)

## Success Criteria
- Adding an owned team via the admin UI stores UUID as `team_id` and slug as `public_id`
- Adding a non-owned team via the admin UI stores public_id as `team_id` and slug as `public_id`
- `bb data crawl --source db` succeeds for owned teams (authenticated endpoints receive UUIDs)
- `parse_team_url()` accepts both UUID strings and public_id slugs
- `CrawlConfig.owned_teams` entries carry enough information for crawlers to choose endpoint style

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-094-01 | Accept UUIDs in URL Parser | DONE | None | SE |
| E-094-02 | Resolve UUID at Team Import Time | DONE | E-094-01 | SE |
| E-094-03 | Add Endpoint Style to Crawl Config | DONE | None | SE |

Wave 1 (parallel): E-094-01 + E-094-03. Wave 2: E-094-02 (after 01).

## Dispatch Team
- software-engineer

## Technical Notes

### ID Format Detection
UUIDs match the pattern `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (36 chars with dashes, hex digits). Public_id slugs are alphanumeric, 6-20 chars, no dashes. These formats are mutually exclusive and can be distinguished with a simple regex check.

### UUID Resolution Strategy
- **Owned team + public_id input:** Call `GET /teams/public/{public_id}/id` (reverse bridge) to get UUID. If 200, store UUID as `team_id`. If 403, reject with a clear error explaining the team was not found on the user's account (the user selected "owned" for a team they are not a member of).
- **Owned team + UUID input:** Use UUID directly as `team_id`. Call `GET /teams/{uuid}/public-team-profile-id` to get public_id if not already known.
- **Non-owned team:** Store public_id as `team_id`. No UUID resolution needed.

### Crawl Config Endpoint Style
The `TeamEntry` dataclass in `config.py` needs an `is_owned` field (or equivalent) so the crawl orchestrator knows whether to use authenticated UUID-based endpoints or public slug-based endpoints. For now, only owned teams are crawled (existing behavior), but the config should express the distinction so public-endpoint crawlers can be added later without another config refactor.

### Bridge Endpoint Details (confirmed 2026-03-11)

**Reverse bridge** (`GET /teams/public/{public_id}/id`):
- Requires auth (`gc-token` + `gc-device-id`)
- Required Accept header: `application/vnd.gc.com.team_id+json; version=0.0.0`
- 200 response body: `{"id": "uuid-string"}`
- 403 response body: bare string `"Forbidden"` (NOT JSON) -- error handling must use `response.text`, not `response.json()`
- Full endpoint doc: `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-public-public_id-id.md`

**Forward bridge** (`GET /teams/{uuid}/public-team-profile-id`):
- Requires auth (`gc-token` + `gc-device-id`)
- Required Accept header: `application/vnd.gc.com.team_public_profile_id+json; version=0.0.0`
- 200 response body: `{"id": "public_id_slug"}`
- Also own-team-only (403 for non-owned teams)
- Full endpoint doc: `/workspaces/baseball-crawl/docs/api/endpoints/get-teams-team_id-public-team-profile-id.md`

The import route runs in the FastAPI request context (no `GameChangerClient` available). Story E-094-02 will need to create a `GameChangerClient` instance to make bridge calls. This is acceptable -- `GameChangerClient` handles auth automatically via `TokenManager`.

### FK Risk on PK Update
`_upgrade_placeholder_team()` updates the `team_id` PK. Eight child tables reference `teams(team_id)` with RESTRICT semantics (no CASCADE). For placeholder teams with no child rows (the normal case), the update succeeds. If a placeholder somehow acquired child rows before upgrade, the update would fail with a FK violation. Implementer should add a defensive check or document why child rows cannot exist at upgrade time.

### Files Overview
| File | Stories |
|------|---------|
| `src/gamechanger/url_parser.py` | 01 |
| `tests/test_url_parser.py` | 01 |
| `src/api/routes/admin.py` | 02 |
| `src/gamechanger/team_resolver.py` | 02 |
| `src/gamechanger/bridge.py` (new, optional) | 02 |
| `tests/test_admin_teams.py` | 02 |
| `src/gamechanger/config.py` | 03 |
| `tests/test_config.py` | 03 |

## Open Questions
- None. API behavior is confirmed. Schema supports the fix without migration.

## History
- 2026-03-10: Created. Bug identified during investigation of `--source db` crawl failures. API constraints confirmed via live testing.
- 2026-03-11: Refined via team review (PM, SE, DE, api-scout). Added bridge response formats, FK risk note, dispatch waves, duplicate-check mechanism, UUID-in-URL AC, corrected AC-2 forward-bridge-only path. Set to READY.
- 2026-03-11: Dispatched. Wave 1 (parallel): E-094-01 + E-094-03. Wave 2: E-094-02. All three stories APPROVED by code-reviewer.
- 2026-03-11: COMPLETED. All stories DONE. Key artifacts: `src/gamechanger/bridge.py` (new — reverse/forward bridge API helpers), `TeamIdResult` return type in `url_parser.py`, `is_owned` field on `TeamEntry` in `config.py`, rewritten `add_team()` in `admin.py` with proper UUID resolution. SHOULD FIX notes from reviewer: owned-team placeholder upgrade test coverage gap, `add_team()` at 102 lines (pre-existing violation worsened slightly).
- 2026-03-11: Documentation assessment — No documentation impact. Internal bug fix to existing import pipeline; no new user-facing features, no schema changes, no deployment changes.
- 2026-03-11: Context-layer assessment — All six triggers evaluated as **no**: (1) No new convention — bridge module follows established patterns. (2) No architectural decision — `is_owned` field is self-documenting and extends existing config pattern. (3) No new footgun — 403 bare-string response already documented in `docs/api/endpoints/`. (4) No agent behavior changes. (5) No new domain knowledge — reverse bridge documented in API endpoint docs; CLAUDE.md already covers the forward bridge concept. (6) No new CLI commands or workflows.
