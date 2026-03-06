# E-049: API Endpoint Documentation and Dual-Header System

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT -> READY -> ACTIVE -> COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Ingest, analyze, and fully document the 37 raw API payloads captured via mitmproxy proxy capture of the iOS GameChanger app, and build a dual-header system to support both web browser and mobile app request profiles. This epic converts raw discovery data into actionable API documentation and equips the codebase to use either header profile when calling endpoints.

## Background & Context
On 2026-03-05, mitmproxy captured ~300 HTTP requests from the iOS GameChanger (Odyssey) app, revealing 50+ new endpoint patterns. A subsequent bulk collection using web browser credentials saved 37 raw API payloads to `data/raw/bulk-20260305-234522/`. Three critical discoveries emerged:

1. **Three endpoints returned HTTP 500 with web browser headers**: `GET /me/related-organizations`, `GET /organizations/{org_id}/teams`, `GET /organizations/{org_id}/opponent-players`. These errors are server-side (`Cannot read properties of undefined (reading 'page_starts_at')` or `'page_size'`). They succeeded in the iOS proxy capture (HTTP 200), but the root cause is unknown -- it could be missing mobile-specific headers, different pagination parameters, or something else entirely. Investigation is captured as IDEA-011.

2. **Two distinct header profiles exist**: the web browser profile (Chrome UA, `sec-ch-ua*`, `sec-fetch-*`) and the iOS Odyssey profile (`Odyssey/2026.7.0` UA, `gc-app-version: 2026.7.0.0`, `x-gc-features`, `x-gc-application-state`, `x-gc-origin`). The proxy `header-report.json` at `proxy/data/header-report.json` documents these differences in detail.

3. **Several high-value endpoints were discovered**: `GET /me/associated-players` (cross-team player tracking -- goldmine for longitudinal analysis), `GET /organizations/{org_id}/standings` (full standings with home/away/last10/streak/run-differential), `GET /game-streams/gamestream-recap-story/{id}` (structured game narrative with player UUIDs and names), and the entire `/organizations/*` family.

**Expert consultation**: User requested api-scout and software-engineer consultation. PM incorporated domain knowledge via thorough review of api-scout memory (`/.claude/agent-memory/api-scout/MEMORY.md`), all 37 raw payloads, the current API spec (`docs/gamechanger-api.md`), and the HTTP layer code (`src/http/headers.py`, `src/http/session.py`). No Task tool available for live agent consultation; context is sufficient from file review. **Note**: E-049-07 (coaching priority matrix) would benefit from baseball-coach consultation for tier validation; in its absence, CLAUDE.md "Key Metrics We Track" serves as the coaching priority proxy.

## Goals
- Full schema documentation for all 37 bulk-collected endpoint payloads in `docs/gamechanger-api.md`
- A dual-header system in `src/http/` enabling the codebase to use mobile or web profiles per endpoint
- Documented workflow for capturing and refreshing mobile app credentials
- A coaching-value priority matrix mapping discovered endpoints to coaching use cases

## Non-Goals
- Building new crawlers or loaders for any discovered endpoints (future epics)
- Implementing programmatic token refresh (the `POST /auth` signing key is still unknown)
- Ingesting video/clip endpoints (`/clips/*`, `/video-stream/*`, `vod-archive.gc.com`) -- low coaching value for stat analytics
- Exploring the sync/realtime system (`/sync-topics/*`) -- infrastructure, not data
- Modifying the existing `GameChangerClient` to use the dual-header system (that's a follow-on story)

## Success Criteria
- Every endpoint with a raw payload in `data/raw/bulk-20260305-234522/` has its response schema documented in `docs/gamechanger-api.md` with field types, nullability, and notes
- The three HTTP-500 endpoints are documented with their error responses and observed context (web headers used, iOS proxy succeeded)
- `src/http/headers.py` exports both `BROWSER_HEADERS` and `MOBILE_HEADERS` profiles
- `create_session()` accepts a `profile` parameter to select the header set
- All existing tests pass (no regressions from the header changes)
- A credential capture workflow for mobile credentials is documented in `docs/admin/mitmproxy-guide.md`
- An endpoint priority matrix exists ranking endpoints by coaching value

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-049-01 | Document /me/* endpoint schemas from bulk payloads | DONE | None | api-scout |
| E-049-02 | Document /organizations/* endpoint schemas from bulk payloads | DONE | E-049-01 | api-scout |
| E-049-03 | Document team, event, and game-stream endpoint schemas from bulk payloads | DONE | E-049-02 | api-scout |
| E-049-04 | ~~Document mobile vs web header differences and endpoint compatibility~~ | ABANDONED | - | - |
| E-049-05 | Implement dual-header profile system | DONE | None | software-engineer |
| E-049-06 | Document mobile credential capture workflow | DONE | None | docs-writer |
| E-049-07 | Endpoint coaching-value priority matrix | DONE | E-049-03 | api-scout |

## Dispatch Team
- api-scout (stories 01, 02, 03, 07)
- software-engineer (story 05)
- docs-writer (story 06)

## Technical Notes

### Raw Payload Inventory

The 37 files in `data/raw/bulk-20260305-234522/` break down as follows:

**`/me/*` family (7 files):**
- `me-user.json` -- already documented, verify no schema drift
- `me-teams-summary.json` -- lightweight: `{"archived_teams":{"count":8,"range":{"from_year":2019,"to_year":2023}}}`
- `me-associated-players.json` -- RICH: cross-team player tracking with teams map, players map (name + team_id), and associations array
- `me-archived-teams.json` -- full team objects for 8 archived teams (same schema as `/me/teams`)
- `me-related-organizations.json` -- **HTTP 500**: `{"error":"Cannot read properties of undefined (reading 'page_starts_at')"}`
- `me-widgets.json` -- app widget config (low value)
- `me-schedule.json` -- large, cross-team schedule (34K+ tokens)

**`/organizations/*` family (8 files):**
- `org-teams.json` -- **HTTP 500**: same `page_starts_at` error
- `org-events.json` -- needs analysis
- `org-game-summaries.json` -- empty array `[]` (no current season data for travel ball org)
- `org-standings.json` -- 7 team records with home/away/last10/streak/run-differential structure
- `org-opponents.json` -- 7 opponent records with root_team_id/progenitor_team_id/owning_team_id
- `org-opponent-players.json` -- **HTTP 500**: `{"error":"Cannot read properties of undefined (reading 'page_size')"}`
- `org-team-records.json` -- needs analysis
- `org-users.json` -- single admin user record (PII endpoint)
- `org-scoped-features.json` -- feature flags (low value)

**Team-scoped (12 files):**
- `team.json`, `team-players.json`, `team-users.json`, `team-schedule.json`, `team-game-summaries.json`, `team-opponents.json` -- largely already documented, verify for schema updates
- `team-opponents-players.json` -- LARGE (102K+ tokens), paginated bulk opponent roster
- `team-associations.json`, `team-relationships.json`, `team-external-associations.json` -- team graph data
- `team-scoped-features.json`, `team-notification-setting.json` -- config endpoints (low value)

**Event/game-stream (8 files):**
- `event-player-stats.json` -- already documented (CONFIRMED)
- `event-rsvp-responses.json`, `event-video-live-status.json`, `event-video-stream.json`, `event-video-assets.json` -- event metadata
- `gamestream-recap-story.json` -- RICH: structured narrative with typed segments (team/player/text), player UUIDs and names, RBI/hit details
- `gamestream-viewer-payload-lite.json`, `gamestream-events.json` -- game viewer data
- `event-highlight-reel.json` -- highlight clips

### HTTP 500 Endpoints -- Unresolved Failures

Three endpoints consistently return HTTP 500 with the web browser headers we tested:
1. `GET /me/related-organizations` -- error: `page_starts_at` undefined
2. `GET /organizations/{org_id}/teams` -- error: `page_starts_at` undefined
3. `GET /organizations/{org_id}/opponent-players` -- error: `page_size` undefined

All three succeeded in the iOS proxy capture (HTTP 200). The root cause is unknown -- possible factors include missing pagination parameters, mobile-specific headers (`gc-app-version`, `x-gc-features`, `x-gc-application-state`), or other differences between the two request profiles. Investigation is deferred to a future epic (see IDEA-011).

### Header Profile Specifications

**Web browser profile** (current `BROWSER_HEADERS` in `src/http/headers.py`):
- UA: Chrome 131 on macOS (needs update to 145 per API spec -- note: current code still says 131)
- Includes: `sec-ch-ua*`, `sec-fetch-*`
- Auth: `gc-token`, `gc-device-id`, `gc-app-name: web`

**Mobile (Odyssey) profile** (from `proxy/data/header-report.json`):
- UA: `Odyssey/2026.7.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0`
- Includes: `gc-app-version: 2026.7.0.0`, `x-gc-features: lazy-sync`, `x-gc-application-state: foreground`
- Auth: same `gc-token`, `gc-device-id` mechanism
- Excludes: `sec-ch-ua*`, `sec-fetch-*` (browser-only headers)
- Accept-Encoding includes Brotli (`br`)

### Dual-Header Implementation Design

`src/http/headers.py` will export:
- `BROWSER_HEADERS: dict[str, str]` (existing, unchanged key name)
- `MOBILE_HEADERS: dict[str, str]` (new)
- `HeaderProfile` enum or literal type: `"web"` | `"mobile"`

`src/http/session.py` `create_session()` signature change:
```python
def create_session(
    min_delay_ms: int = 1000,
    jitter_ms: int = 500,
    profile: str = "web",  # "web" or "mobile"
) -> httpx.Client:
```

Default `"web"` ensures backward compatibility -- no existing callers break.

### PII Sensitivity

Several payloads contain PII (player names, user emails, team names). When documenting schemas:
- Use redacted/generic examples
- Note PII fields explicitly
- Never include real names, emails, or UUIDs from the raw data in documentation

### Proxy Data Ephemerality

Files in `proxy/data/` (endpoint-log.jsonl, header-report.json) are gitignored and ephemeral -- they are working inputs for story authors, not committed deliverables. The 2026-03-05 capture session data exists on the operator's machine but is not reproducible from a fresh clone. Stories that reference these files use them as supplementary evidence; the primary deliverables (API spec documentation, header constants in code) stand on their own. Committing proxy data snapshots is a separate infrastructure concern outside this epic's scope.

### Chrome Version Drift

The API spec documents Chrome 145, but `src/http/headers.py` still has Chrome 131. Story E-049-05 should update the browser profile to Chrome 145 while adding the mobile profile.

## Open Questions
- What causes the three HTTP 500 endpoints to fail with web headers? Could be mobile-specific headers, pagination parameters, or something else. Deferred to IDEA-011.
- Does the mobile token (from iOS app) differ from the web token? Same `gc-token` JWT format? (Likely yes -- same API, same auth system)
- Does `GET /organizations/{org_id}/game-summaries` return data for LSB orgs? (Empty for travel ball org -- may have data for school program orgs)

## History
- 2026-03-05: Created. Bulk proxy capture of 37 endpoints. Three endpoints returned HTTP 500 with web headers. Epic structured as 7 stories across 3 agent types.
- 2026-03-06: Manual spec review (codex script timed out on 516-line epic). 3 REFINE findings applied: (1) E-049-05 AC-8 corrected -- Chrome 131->145 update breaks 3 existing tests in test_http_headers.py, added file to modify list and revised AC to acknowledge test updates; (2) E-049-05 Notes clarified sec-fetch-* header treatment (keep for backward compat); (3) E-049-07 Technical Approach expanded with baseball-coach consultation note and CLAUDE.md key-metrics proxy guidance. 5 findings dismissed (transitive deps, docs-only DoD, section reference precision, story sizing, forward reference in E-049-04).
- 2026-03-06: User feedback -- E-049-04 ABANDONED. The "mobile-only" categorization was a hypothesis, not fact. The 500 errors could have multiple causes. Removed E-049-04 (experimentation/categorization). Factual 500-error documentation stays in E-049-01 AC-4 and E-049-02 AC-3/AC-4. Header-profile documentation absorbed into E-049-05 AC-10. Investigation of 500 errors captured as IDEA-011. Scrubbed "mobile-only" language from all stories. Epic reduced to 6 active stories.
- 2026-03-06: Codex spec review triage (5 findings, 2 open questions). 3 REFINE: (1) E-049-01 AC-8 rewritten -- endpoint-log.jsonl has request_content_type not Accept; AC now points to curl captures in API spec as the correct Accept source; (2) E-049-05 AC-4 clarified -- backward compat means API contract (no caller changes), not header values (which change per AC-2); (3) E-049-05 Technical Approach sanity test replaced -- "no overlapping keys with conflicting values" was wrong (conflicting values are the point), replaced with "both profiles contain required baseline keys." 2 DISMISS: (4) proxy/data/ ephemerality noted in Technical Notes but not a story-level change; (5) E-049-07 /.project/ paths match PM quality checklist convention. Open questions resolved: (Q1) proxy data snapshots deferred as separate infrastructure concern; (Q2) AC-8 switched to curl-capture evidence.
- 2026-03-06: COMPLETED. All 6 active stories DONE (E-049-04 ABANDONED). Key deliverables: (1) Full schema documentation for all 37 bulk-collected endpoint payloads across /me/*, /organizations/*, teams, events, and game-streams families in docs/gamechanger-api.md; (2) Dual-header profile system (BROWSER_HEADERS + MOBILE_HEADERS) in src/http/headers.py with profile parameter on create_session(); Chrome 131->145 update; (3) Mobile credential capture workflow documented in docs/admin/mitmproxy-guide.md; (4) Endpoint Priority Matrix with 4 tiers and top-5 integration recommendations. Three HTTP 500 endpoints documented but unresolved (IDEA-011). No documentation impact beyond the epic's own deliverables.
