# E-062 Format Specification: Per-Endpoint API Documentation

**Author:** Software Engineer (E-062-R-01 research spike)
**Date:** 2026-03-07
**Status:** Final -- Ready for implementation stories E-062-01 through E-062-06

---

## 1. Finalized YAML Frontmatter Schema

```yaml
---
method: GET | POST | PATCH | PUT | DELETE
path: /path/{param}/subpath           # Full path template with {placeholders}
status: CONFIRMED | OBSERVED | PARTIAL | UNTESTED | DEPRECATED
auth: required | none
profiles:
  web:
    status: confirmed | unverified | not_applicable
    notes: >
      Optional free-text behavioral notes specific to the web profile.
      Use when behavior differs from mobile, or to note caveats.
  mobile:
    status: confirmed | unverified | not_applicable
    notes: >
      Optional free-text behavioral notes specific to the mobile profile.
accept: "application/vnd.gc.com.{resource_type}:{cardinality}+json; version={semver}"
         # null when not yet confirmed or when endpoint uses Accept: */*
gc_user_action: "data_loading:{context}"   # null when not observed/required
query_params:
  - name: param_name
    required: true | false | unknown
    description: >
      Single-line or multi-line description of the parameter.
pagination: true | false | unknown
response_shape: array | object | string   # "string" for CSV responses
response_sample: data/raw/filename.json   # relative path to raw sample file, or null
raw_sample_size: "N records, K KB"        # human-readable sample size, or null
discovered: "YYYY-MM-DD"
last_confirmed: "YYYY-MM-DD"             # null if never independently confirmed (OBSERVED only)
tags: [tag1, tag2]                        # see Tag Vocabulary below
caveats:
  - >
    Free-text notes about partial/conditional behavior. Use for the PARTIAL
    status case (endpoint works only with specific parameters), known HTTP 500
    edge cases, parameter-dependent responses, etc.
    Omit this field entirely when no caveats apply.
related_schemas:
  - me-teams            # named schema in Response Schemas section of monolith
  - game-summaries      # include names for endpoints whose schema lives separately
  # Omit field (or use []) when schema is fully inline in this file
see_also:
  - path: /other/endpoint
    reason: One-line description of why the cross-reference exists
---
```

### Field Descriptions and Allowed Values

#### `status`

| Value | Meaning |
|-------|---------|
| `CONFIRMED` | Live curl call returned 200 OK; response schema documented from actual data |
| `OBSERVED` | Seen in proxy/curl traffic but not independently verified; response schema not fully documented |
| `PARTIAL` | Endpoint exists and responds, but only works correctly with specific parameters (e.g., HTTP 500 without `?page_size=50`); see `caveats` field for details |
| `UNTESTED` | Path pattern known (from proxy log or client code) but no response captured yet |
| `DEPRECATED` | Endpoint was confirmed but is no longer active or has been replaced |

**When to use PARTIAL vs. OBSERVED:** Use `PARTIAL` when the endpoint has been directly tested and an HTTP 500 (or other error) was confirmed for the common case, with the fix documented in `caveats`. Use `OBSERVED` when the endpoint was seen in traffic logs but has not been directly tested at all.

#### `profiles.{profile}.status`

| Value | Meaning |
|-------|---------|
| `confirmed` | Response schema documented from this profile's captured traffic |
| `unverified` | Not captured from this profile; assumed to work or untested |
| `not_applicable` | This endpoint is only meaningful for one profile (e.g., public endpoints have no auth profile distinction) |

**When to add profile notes:** Add `notes` to a profile entry when behavior differs from the other profile (different fields, different status codes, different Accept headers, different gc-user-action values). Omit `notes` when behavior is identical or not yet observed.

#### `accept`

Use `null` when:
- The Accept header is not yet confirmed from a live capture
- The endpoint uses a non-vendor-typed Accept (e.g., `Accept: */*` as on `POST /auth` and the `schedule/events/.../player-stats` endpoint)

When `null`, note the uncertainty in the endpoint body's Headers section.

#### `pagination`

Use `unknown` when the endpoint was seen but no pagination behavior was tested. Use `false` when `x-pagination: true` was sent and no `x-next-page` was returned (single-page response confirmed).

#### `response_shape`

- `array`: Response body is a bare JSON array (most list endpoints)
- `object`: Response body is a JSON object (detail endpoints, structured responses)
- `string`: Response body is a non-JSON string (currently only `GET /organizations/{org_id}/pitch-count-report` which returns CSV)

#### `caveats`

Omit this field entirely when there are no caveats. Include it only for `PARTIAL` or `OBSERVED` endpoints where specific conditions must be met for the endpoint to work correctly. Examples:
- Required query parameters that cause HTTP 500 when missing
- Auth-despite-public-path behavior (`GET /teams/public/{public_id}/access-level`)
- Parameter-conditional response fields (e.g., `?include=line_scores` on public game details)
- Access restrictions (e.g., `GET /bats-starting-lineups/{event_id}` returns HTTP 403 for away games)

#### `related_schemas`

List schema names from the "Response Schemas" section of the monolith that this endpoint's response schema is documented under. Migration stories must inline these schemas into the endpoint file. Omit (or use `[]`) when the schema is fully documented inline in the endpoint body.

Currently named schemas in the monolith's Response Schemas section:
- `me-teams` -- absorb into: `get-me-teams.md`
- `game-summaries` -- absorb into: `get-teams-team_id-game-summaries.md`
- `season-stats` -- absorb into: `get-teams-team_id-season-stats.md`
- `associations` -- absorb into: `get-teams-team_id-associations.md`
- `player-stats` -- absorb into: `get-teams-team_id-players-player_id-stats.md`

#### `tags`

**Controlled Tag Vocabulary:**

| Tag | Use for |
|-----|---------|
| `schedule` | Event scheduling, calendar, RSVP |
| `games` | Game results, scores, game-level data |
| `team` | Team metadata, roster, settings |
| `player` | Individual player identity or stats |
| `stats` | Statistical data (batting, pitching, fielding) |
| `season` | Season-aggregate or season-scoped data |
| `organization` | Org-level data (standings, teams, opponents at org scope) |
| `opponent` | Opponent scouting data |
| `video` | Video streaming, highlight reels, recordings |
| `lineup` | Batting order, fielding positions, lineup management |
| `public` | No-auth public endpoints |
| `auth` | Authentication, token management |
| `subscription` | Subscription and billing data |
| `user` | User profile, PII-containing endpoints |
| `sync` | Real-time sync and WebSocket-adjacent endpoints |
| `coaching` | Coaching tools (recommendation, pitch count, etc.) |
| `spray-chart` | Ball-in-play coordinate data |
| `events` | Event-level game stream data (boxscore, plays, game streams) |
| `bridge` | ID-resolution bridge endpoints (UUID to public_id, etc.) |
| `bulk` | High-value bulk data endpoints (avoid multiple calls) |

**Tag conventions:**
- Use 2-5 tags per endpoint
- Prefer specific tags over general ones when possible
- `public` should always appear alongside the relevant domain tag for unauthenticated endpoints
- `bridge` applies to endpoints whose primary purpose is ID resolution (not data retrieval)

---

## 2. File Naming Convention

### General Rule

```
{method}-{path-segments-with-params-as-words}.md
```

All lowercase. Hyphens between path segments. Path parameters (`{uuid}`, `{team_id}`, etc.) are rendered by their parameter name (without curly braces). Path separators (`/`) become hyphens.

### Examples

| API Path | Filename |
|----------|----------|
| `GET /me/teams` | `get-me-teams.md` |
| `GET /teams/{team_id}` | `get-teams-team_id.md` |
| `GET /teams/{team_id}/schedule` | `get-teams-team_id-schedule.md` |
| `GET /teams/{team_id}/players/{player_id}/stats` | `get-teams-team_id-players-player_id-stats.md` |
| `GET /public/teams/{public_id}` | `get-public-teams-public_id.md` |
| `GET /public/teams/{public_id}/games` | `get-public-teams-public_id-games.md` |
| `GET /public/teams/{public_id}/games/preview` | `get-public-teams-public_id-games-preview.md` |
| `GET /teams/public/{public_id}/players` | `get-teams-public-public_id-players.md` |
| `GET /teams/public/{public_id}/access-level` | `get-teams-public-public_id-access-level.md` |
| `GET /teams/public/{public_id}/id` | `get-teams-public-public_id-id.md` |
| `POST /auth` | `post-auth.md` |

### Edge Case: Inverted URL Pattern

The `GET /teams/public/{public_id}/players` endpoint uses `/teams/public/` (not `/public/teams/`). Its filename directly mirrors the path:

- `GET /public/teams/{public_id}` -> `get-public-teams-public_id.md`
- `GET /teams/public/{public_id}/players` -> `get-teams-public-public_id-players.md`

The filename difference (`public-teams` vs. `teams-public`) visually flags the path structure difference, which is intentional -- this is the most important quirk in the API.

### Edge Case: Long Paths

`GET /teams/{team_id}/schedule/events/{event_id}/player-stats` becomes:
`get-teams-team_id-schedule-events-event_id-player-stats.md`

Long but unambiguous. Do not abbreviate.

### Edge Case: Teams-Additional Paths with Same Sub-Path

`GET /teams/{team_id}/video-stream/assets` -> `get-teams-team_id-video-stream-assets.md`
`GET /teams/{team_id}/schedule/events/{event_id}/video-stream/assets` -> `get-teams-team_id-schedule-events-event_id-video-stream-assets.md`

Unambiguous through full path expansion.

---

## 3. Markdown Body Structure Template

Every endpoint file follows this section ordering:

```markdown
---
{YAML frontmatter}
---

# {METHOD} {path}

**Status:** {One-line status description with date}

{One or two paragraph summary describing what the endpoint returns and when to use it.
For public endpoints, note "AUTHENTICATION: NOT REQUIRED." prominently.}

```
{HTTP_METHOD} https://api.team-manager.gc.com{path}
```

## Path Parameters          <- Omit if no path params

| Parameter | Type | Description |
|-----------|------|-------------|

## Query Parameters          <- Omit if none observed

| Parameter | Required | Description |
|-----------|----------|-------------|

## Headers ({Profile} Profile)    <- Usually "Web Profile"; add mobile section if different

```
{header block}
```

{Notes on specific headers: gc-user-action, Accept, x-pagination, etc.}

## Pagination Response Header     <- Include only when pagination=true

```
x-next-page: {full URL template}
```

{Notes on cursor format, end-of-pagination signal}

## Response

{One paragraph describing overall response shape (array/object, size observed)}

### {Sub-object Name}         <- One subsection per major nested object

| Field | Type | Notes |
|-------|------|-------|

## Example Response

```json
{redacted example}
```

## Comparison to Related Endpoints    <- Include only when a comparison table adds value

| Dimension | {This endpoint} | {Other endpoint} |
|-----------|-----------------|------------------|

## Known Limitations

- {Bullet list of edge cases, unconfirmed behavior, and implementation gotchas}

**Discovered:** {date}. **Last confirmed:** {date}.
```

### Section Ordering Rules

1. Always present: frontmatter, title, status line, summary, URL example, Response, Known Limitations
2. Include Path Parameters when there are path parameters
3. Include Query Parameters when at least one has been observed
4. Include separate Headers sections per profile only when profiles differ materially
5. Include Pagination Response Header only for paginated endpoints
6. Include Comparison tables only when the comparison adds unique value not obvious from summary
7. Known Limitations is always last before the trailing Discovered line

---

## 4. Cross-Reference Convention

### Within Endpoint Files

Use the `see_also` frontmatter field for machine-readable cross-references. In the body, add hyperlinks using the filename as the link target (relative path from the endpoint file's location).

**Frontmatter (machine-readable):**
```yaml
see_also:
  - path: /teams/{team_id}/game-summaries
    reason: Required to obtain game_stream_id for this endpoint
```

**Body text (human-readable reference):**
```markdown
> **ID routing:** The `game_stream_id` path parameter must come from
> `GET /teams/{team_id}/game-summaries` (`game_stream.id` field), not from
> the schedule `event_id`. See [game-summaries](get-teams-team_id-game-summaries.md).
```

### Inline "ID Chain" Blocks

For endpoints that require multi-step ID resolution, include an ID chain block in the summary section:

```markdown
**ID chain for this endpoint:**
```
GET /teams/{team_id}/game-summaries -> game_stream.id
  -> GET /game-stream-processing/{game_stream_id}/boxscore (this endpoint)
```
```

### Cross-References Between Complement Pairs

Many endpoints have complement pairs (e.g., boxscore + public details, games + games/preview). Document the relationship in the `see_also` frontmatter of both files with a brief `reason` string explaining what the other endpoint provides that this one does not.

---

## 5. Profile-Specific Information Convention

### When Profiles Behave Identically

Do not add separate profile sections. Note in the Headers section that both profiles use the same authentication mechanism:

```markdown
Both web and mobile profiles use `gc-token` + `gc-device-id` authentication.
No profile-specific behavioral differences have been observed.
```

### When Profiles Differ

Structure the headers and behavioral notes per profile. Use separate `## Headers (Web Profile)` and `## Headers (Mobile Profile)` sections when the header sets differ materially (different Accept, different gc-app-version, different sec-ch-ua handling, etc.).

The `profiles` frontmatter field captures the machine-readable distinction:

```yaml
profiles:
  web:
    status: confirmed
    notes: Uses vendor-typed Accept header. Returns 200 OK.
  mobile:
    status: confirmed
    notes: >
      Uses Accept: */* with gc-app-version: 2026.7.0.0.
      Response schema is identical but response size differs
      (mobile may return a subset of fields -- unverified).
```

### Profile Status Values and Their Meaning

- `confirmed`: Live capture from this profile, response schema documented
- `unverified`: Profile not tested; assumed same behavior as confirmed profile
- `not_applicable`: Only one profile can reach this endpoint (e.g., public endpoints with no auth needed)

---

## 6. Global Reference Files

The following global reference files belong in `docs/api/` alongside the endpoint files. They contain information that would otherwise be duplicated across dozens of endpoint files.

| Filename | Content |
|----------|---------|
| `README.md` | Index of all endpoints with filename, status, and one-line description |
| `auth.md` | JWT structure, token lifetime, gc-token header, gc-device-id, auth expiration handling |
| `headers.md` | Canonical header sets for web and mobile profiles; comparison table; header profiles; User-Agent values |
| `pagination.md` | How x-pagination works, x-next-page behavior, cursor format, pagination loop pattern |
| `content-type.md` | Vendor-typed Accept header pattern, content-type convention for GET vs POST |
| `base-url.md` | Base URL, subdomain structure (api.team-manager.gc.com vs web.gc.com) |
| `error-handling.md` | Common HTTP error codes and their meanings in the GC API context |

### What Goes in Global Files vs. Endpoint Files

**Global files contain:**
- Header fields that appear on every request (gc-token, gc-device-id, gc-app-name, User-Agent, sec-ch-ua, etc.)
- The pagination pattern that applies to all paginated endpoints
- JWT structure and token lifetime
- Base URL and subdomain conventions

**Endpoint files contain:**
- The exact Accept header value for this endpoint (always endpoint-specific)
- Query parameters specific to this endpoint
- The gc-user-action value for this endpoint (when observed)
- Pagination behavior specific to this endpoint (page size observed, whether x-next-page was seen)
- Response schema (either inline or by reference to `related_schemas`)
- Known limitations specific to this endpoint

**The Accept header:** Always in the endpoint file, not global. The vendor-typed Accept header is endpoint-specific (different resource type, different version per endpoint). The global `content-type.md` explains the pattern; each endpoint file documents its specific value.

**Standard browser headers (sec-ch-ua, referer, origin, sec-fetch-*):** Document once in `headers.md`. Endpoint files show the full header block for reference but note that standard browser headers are defined in `headers.md`.

---

## 7. Complete Endpoint Inventory

### Inventory Format

| # | Method | Path | Status | Filename | Story | Schema |
|---|--------|------|--------|----------|-------|--------|
| | | | | | E-062-02=Tier1/E-062-03=Tier2/E-062-06=observed | name if in Response Schemas section |

**Stories:**
- **E-062-02**: Core endpoints (Tier 1 -- CONFIRMED, fully documented in monolith)
- **E-062-03**: Confirmed endpoints from 2026-03-07 live probe session (partially documented)
- **E-062-06**: Proxy-discovered and minimal/observed endpoints

---

### Tier 1: Fully Documented Endpoints (E-062-02)

These endpoints have complete schema documentation in the monolith's main Endpoints section.

| # | Method | Path | Status | Filename | Schema |
|---|--------|------|--------|----------|--------|
| 1 | GET | `/me/teams` | CONFIRMED | `get-me-teams.md` | `me-teams` (inline from schema section) |
| 2 | GET | `/me/user` | CONFIRMED | `get-me-user.md` | inline |
| 3 | GET | `/teams/{team_id}` | CONFIRMED | `get-teams-team_id.md` | inline |
| 4 | GET | `/teams/{team_id}/schedule` | CONFIRMED | `get-teams-team_id-schedule.md` | inline |
| 5 | GET | `/teams/{team_id}/game-summaries` | CONFIRMED | `get-teams-team_id-game-summaries.md` | `game-summaries` (inline from schema section) |
| 6 | GET | `/teams/{team_id}/players` | CONFIRMED | `get-teams-team_id-players.md` | inline |
| 7 | GET | `/teams/public/{public_id}/players` | CONFIRMED | `get-teams-public-public_id-players.md` | inline |
| 8 | GET | `/teams/{team_id}/video-stream/assets` | CONFIRMED (partial schema) | `get-teams-team_id-video-stream-assets.md` | inline (incomplete) |
| 9 | GET | `/teams/{team_id}/season-stats` | CONFIRMED | `get-teams-team_id-season-stats.md` | `season-stats` (inline from schema section) |
| 10 | GET | `/teams/{team_id}/associations` | CONFIRMED | `get-teams-team_id-associations.md` | `associations` (inline from schema section) |
| 11 | GET | `/teams/{team_id}/players/{player_id}/stats` | CONFIRMED | `get-teams-team_id-players-player_id-stats.md` | `player-stats` (inline from schema section) |
| 12 | GET | `/public/teams/{public_id}` | CONFIRMED | `get-public-teams-public_id.md` | inline |
| 13 | GET | `/public/teams/{public_id}/games` | CONFIRMED | `get-public-teams-public_id-games.md` | inline |
| 14 | GET | `/public/teams/{public_id}/games/preview` | CONFIRMED | `get-public-teams-public_id-games-preview.md` | inline |
| 15 | GET | `/teams/{team_id}/opponents` | CONFIRMED | `get-teams-team_id-opponents.md` | inline |
| 16 | GET | `/game-stream-processing/{game_stream_id}/boxscore` | CONFIRMED | `get-game-stream-processing-game_stream_id-boxscore.md` | inline |
| 17 | GET | `/game-stream-processing/{game_stream_id}/plays` | CONFIRMED | `get-game-stream-processing-game_stream_id-plays.md` | inline |
| 18 | GET | `/public/game-stream-processing/{game_stream_id}/details` | CONFIRMED | `get-public-game-stream-processing-game_stream_id-details.md` | inline |
| 19 | GET | `/events/{event_id}/best-game-stream-id` | CONFIRMED | `get-events-event_id-best-game-stream-id.md` | inline |
| 20 | GET | `/teams/{team_id}/users` | CONFIRMED | `get-teams-team_id-users.md` | inline |
| 21 | GET | `/teams/{team_id}/public-team-profile-id` | CONFIRMED | `get-teams-team_id-public-team-profile-id.md` | inline |
| 22 | POST | `/auth` | PARTIAL | `post-auth.md` | inline (partial -- 200 response schema unconfirmed) |
| 23 | GET | `/teams/{team_id}/schedule/events/{event_id}/player-stats` | CONFIRMED | `get-teams-team_id-schedule-events-event_id-player-stats.md` | inline |

**Response Schema absorption:** The 5 named schemas in the "Response Schemas" section of the monolith are absorbed into the following files:
- `me-teams` schema -> `get-me-teams.md`
- `game-summaries` schema -> `get-teams-team_id-game-summaries.md`
- `season-stats` schema -> `get-teams-team_id-season-stats.md`
- `associations` schema -> `get-teams-team_id-associations.md`
- `player-stats` schema -> `get-teams-team_id-players-player_id-stats.md`

---

### Tier 2: Confirmed from 2026-03-07 Live Probe Session (E-062-03)

These endpoints were confirmed in the bulk probe session with full schema documentation in the "Confirmed Endpoints (2026-03-07)" section of the monolith.

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 24 | GET | `/teams/{team_id}/opponent/{opponent_id}` | CONFIRMED | `get-teams-team_id-opponent-opponent_id.md` |
| 25 | GET | `/teams/{team_id}/opponents/players` | CONFIRMED | `get-teams-team_id-opponents-players.md` |
| 26 | GET | `/teams/{team_id}/lineup-recommendation` | CONFIRMED | `get-teams-team_id-lineup-recommendation.md` |
| 27 | GET | `/bats-starting-lineups/{event_id}` | CONFIRMED | `get-bats-starting-lineups-event_id.md` |
| 28 | GET | `/bats-starting-lineups/latest/{team_id}` | CONFIRMED | `get-bats-starting-lineups-latest-team_id.md` |
| 29 | GET | `/game-streams/{game_stream_id}/events` | CONFIRMED | `get-game-streams-game_stream_id-events.md` |
| 30 | GET | `/game-streams/gamestream-viewer-payload-lite/{event_id}` | CONFIRMED | `get-game-streams-gamestream-viewer-payload-lite-event_id.md` |
| 31 | GET | `/game-streams/gamestream-recap-story/{event_id}` | OBSERVED (HTTP 404 in probe) | `get-game-streams-gamestream-recap-story-event_id.md` |
| 32 | GET | `/game-streams/insight-story/bats/{event_id}` | OBSERVED (HTTP 404) | `get-game-streams-insight-story-bats-event_id.md` |
| 33 | GET | `/game-streams/player-insights/bats/{event_id}` | OBSERVED (HTTP 404) | `get-game-streams-player-insights-bats-event_id.md` |
| 34 | GET | `/player-attributes/{player_id}/bats` | CONFIRMED | `get-player-attributes-player_id-bats.md` |
| 35 | GET | `/organizations/{org_id}/standings` | CONFIRMED | `get-organizations-org_id-standings.md` |
| 36 | GET | `/organizations/{org_id}/team-records` | CONFIRMED | `get-organizations-org_id-team-records.md` |
| 37 | GET | `/organizations/{org_id}/pitch-count-report` | CONFIRMED (CSV) | `get-organizations-org_id-pitch-count-report.md` |
| 38 | GET | `/organizations/{org_id}/events` | CONFIRMED (empty) | `get-organizations-org_id-events.md` |
| 39 | GET | `/organizations/{org_id}/game-summaries` | CONFIRMED (empty) | `get-organizations-org_id-game-summaries.md` |
| 40 | GET | `/organizations/{org_id}/scoped-features` | CONFIRMED | `get-organizations-org_id-scoped-features.md` |
| 41 | GET | `/organizations/{org_id}/teams` | CONFIRMED (PARTIAL->CONFIRMED) | `get-organizations-org_id-teams.md` |
| 42 | GET | `/events/{event_id}` | CONFIRMED | `get-events-event_id.md` |
| 43 | GET | `/events/{event_id}/highlight-reel` | CONFIRMED | `get-events-event_id-highlight-reel.md` |
| 44 | GET | `/teams/public/{public_id}/access-level` | CONFIRMED | `get-teams-public-public_id-access-level.md` |
| 45 | GET | `/teams/public/{public_id}/id` | CONFIRMED | `get-teams-public-public_id-id.md` |
| 46 | GET | `/teams/{team_id}/users/count` | CONFIRMED | `get-teams-team_id-users-count.md` |
| 47 | GET | `/teams/{team_id}/relationships` | CONFIRMED | `get-teams-team_id-relationships.md` |
| 48 | GET | `/teams/{team_id}/relationships/requests` | CONFIRMED (empty) | `get-teams-team_id-relationships-requests.md` |
| 49 | GET | `/teams/{team_id}/scoped-features` | CONFIRMED | `get-teams-team_id-scoped-features.md` |
| 50 | GET | `/teams/{team_id}/team-notification-setting` | CONFIRMED | `get-teams-team_id-team-notification-setting.md` |
| 51 | GET | `/teams/{team_id}/web-widgets` | CONFIRMED | `get-teams-team_id-web-widgets.md` |
| 52 | GET | `/teams/{team_id}/external-associations` | CONFIRMED (empty) | `get-teams-team_id-external-associations.md` |
| 53 | GET | `/teams/{team_id}/avatar-image` | CONFIRMED | `get-teams-team_id-avatar-image.md` |
| 54 | GET | `/teams/{team_id}/video-stream/videos` | CONFIRMED (empty) | `get-teams-team_id-video-stream-videos.md` |
| 55 | GET | `/teams/{team_id}/schedule/events/{event_id}/video-stream` | CONFIRMED | `get-teams-team_id-schedule-events-event_id-video-stream.md` |
| 56 | GET | `/teams/{team_id}/schedule/events/{event_id}/video-stream/assets` | CONFIRMED | `get-teams-team_id-schedule-events-event_id-video-stream-assets.md` |
| 57 | GET | `/teams/{team_id}/schedule/events/{event_id}/video-stream/live-status` | CONFIRMED | `get-teams-team_id-schedule-events-event_id-video-stream-live-status.md` |
| 58 | GET | `/teams/{team_id}/schedule/events/{event_id}/rsvp-responses` | CONFIRMED (empty) | `get-teams-team_id-schedule-events-event_id-rsvp-responses.md` |
| 59 | GET | `/teams/{team_id}/schedule/event-series/{series_id}` | OBSERVED (HTTP 404) | `get-teams-team_id-schedule-event-series-series_id.md` |
| 60 | GET | `/me/permissions` | CONFIRMED (PARTIAL->CONFIRMED) | `get-me-permissions.md` |
| 61 | GET | `/me/organizations` | CONFIRMED (PARTIAL->CONFIRMED) | `get-me-organizations.md` |
| 62 | GET | `/me/schedule` | CONFIRMED | `get-me-schedule.md` |
| 63 | GET | `/me/associated-players` | CONFIRMED | `get-me-associated-players.md` |
| 64 | GET | `/me/teams-summary` | CONFIRMED | `get-me-teams-summary.md` |
| 65 | GET | `/me/widgets` | CONFIRMED | `get-me-widgets.md` |
| 66 | GET | `/me/archived-teams` | CONFIRMED | `get-me-archived-teams.md` |
| 67 | GET | `/me/advertising/metadata` | CONFIRMED | `get-me-advertising-metadata.md` |
| 68 | GET | `/me/subscription-information` | CONFIRMED | `get-me-subscription-information.md` |
| 69 | GET | `/me/team-tile/{team_id}` | CONFIRMED | `get-me-team-tile-team_id.md` |
| 70 | GET | `/me/related-organizations` | CONFIRMED (PARTIAL->CONFIRMED) | `get-me-related-organizations.md` |
| 71 | GET | `/users/{user_id}` | CONFIRMED | `get-users-user_id.md` |
| 72 | GET | `/users/{user_id}/profile-photo` | OBSERVED (HTTP 404) | `get-users-user_id-profile-photo.md` |
| 73 | GET | `/players/{player_id}/profile-photo` | OBSERVED (HTTP 404) | `get-players-player_id-profile-photo.md` |
| 74 | GET | `/subscription/details` | CONFIRMED | `get-subscription-details.md` |
| 75 | GET | `/subscription/recurly/plans` | CONFIRMED | `get-subscription-recurly-plans.md` |
| 76 | GET | `/search/history` | CONFIRMED | `get-search-history.md` |
| 77 | GET | `/announcements/user/read-status` | CONFIRMED | `get-announcements-user-read-status.md` |
| 78 | GET | `/sync-topics/me/updated-topics` | CONFIRMED | `get-sync-topics-me-updated-topics.md` |

---

### Tier 3: Proxy-Discovered / Observed / Minimal (E-062-06)

These endpoints were observed in proxy captures or have minimal documentation (HTTP 404 confirmed, empty responses, or limited schema).

| # | Method | Path | Status | Filename |
|---|--------|------|--------|----------|
| 79 | POST | `/sync-topics/updates` | OBSERVED | `post-sync-topics-updates.md` |
| 80 | POST | `/sync-topics/topic-subscriptions` | OBSERVED | `post-sync-topics-topic-subscriptions.md` |
| 81 | GET | `/organizations/{org_id}/opponents` | CONFIRMED | `get-organizations-org_id-opponents.md` |
| 82 | GET | `/organizations/{org_id}/opponent-players` | PARTIAL | `get-organizations-org_id-opponent-players.md` |
| 83 | GET | `/organizations/{org_id}/users` | CONFIRMED | `get-organizations-org_id-users.md` |
| 84 | GET | `/organizations/{org_id}/avatar-image` | OBSERVED | `get-organizations-org_id-avatar-image.md` |
| 85 | GET | `/teams/{team_id}/public-url` | OBSERVED | `get-teams-team_id-public-url.md` |
| 86 | GET | `/me/permissions/bulk` | OBSERVED | `get-me-permissions-bulk.md` |
| 87 | GET | `/me/external-calendar-sync-url/team/{team_id}` | OBSERVED | `get-me-external-calendar-sync-url-team-team_id.md` |
| 88 | PATCH | `/me/user` | OBSERVED | `patch-me-user.md` |

**Web-Route Pattern (HTTP 404 on API domain -- document as NOT_API):**

The following paths from the 2026-03-07 proxy section returned HTTP 404 on `api.team-manager.gc.com`. They appear to be web app routes (`web.gc.com`), not API endpoints. Include them as a group in a single `web-routes-not-api.md` file rather than individual files:

- `GET /teams/{public_id}/{season-slug}/opponents`
- `GET /teams/{public_id}/{season-slug}/schedule/{event_id}/plays`
- `GET /teams/{public_id}/{season-slug}/season-stats`
- `GET /teams/{public_id}/{season-slug}/team`
- `GET /teams/{public_id}/{season-slug}/tools`
- `GET /teams/{public_id}/players/{player_id}`
- `GET /public/teams/{public_id}/live`

**Total Endpoint Count: 88 endpoints + 1 web-routes reference file**

---

## 8. Recommendation Section: Research Question Answers

### RQ-1: Does the YAML Frontmatter Schema Capture All Metadata?

**Answer: Yes, with the refinements made in this spike.**

The original prototype schema from the epic Technical Notes was close but needed the following additions:

1. **`profiles.{profile}.status` and `profiles.{profile}.notes`** -- Replacing the simple `profiles: web: true/false` boolean with a status + notes structure. This captures the profile behavioral granularity identified as a concern (endpoint works differently per profile, not just present/absent).

2. **`status: PARTIAL`** -- Added to the status vocabulary to handle endpoints that work only with specific parameters (e.g., HTTP 500 without `?page_size=50`). The existing `CONFIRMED | OBSERVED | UNTESTED | DEPRECATED` set was missing this case.

3. **`caveats` field** -- Free-text bullet list for PARTIAL endpoints and other edge cases. Captures required-parameter combinations, access restrictions, and conditional behavior.

4. **`gc_user_action` field** -- Added to capture the `gc-user-action` request header value per endpoint. This field varies enough (data_loading:team, data_loading:events, data_loading:player_stats, data_loading:team_stats, data_loading:opponents) to be worth tracking in frontmatter.

5. **`response_shape` field** -- Added to capture whether the response is an `array`, `object`, or `string` (for the CSV pitch-count-report endpoint). Helps implementers know immediately what to deserialize into.

6. **`related_schemas` field** -- Added to link endpoints to the named schemas in the monolith's Response Schemas section, ensuring migration stories know to inline those schemas.

**Fields from the prototype that remain unchanged:** `method`, `path`, `auth`, `accept`, `query_params`, `pagination`, `response_sample`, `discovered`, `last_confirmed`, `tags`, `see_also`.

### RQ-2: File Naming Convention for Edge-Case Paths

**Answer: Mirror the URL path structure directly.**

The inverted URL pattern (`GET /teams/public/{public_id}/players` vs. `GET /public/teams/{public_id}`) is handled by mirroring the path structure literally into the filename:

- `GET /public/teams/{public_id}` -> `get-public-teams-public_id.md` (public segment first)
- `GET /teams/public/{public_id}/players` -> `get-teams-public-public_id-players.md` (teams segment first)

The filename difference itself documents the API's inverted pattern. This is better than any normalization or aliasing approach because it preserves the exact API structure that implementers need to understand.

**Why not normalize to `public-` prefix?** Because the two path structures have different auth behaviors:
- `/public/teams/{public_id}` endpoints -- truly no-auth public
- `/teams/public/{public_id}` endpoints -- require `gc-token` despite the "public" path segment

Maintaining the filename difference reinforces this critical behavioral distinction.

### RQ-3: Cross-Reference Patterns and File Links

**Answer: Two-layer cross-reference system (frontmatter + body text).**

The monolith contains the following cross-reference patterns that need to be expressed in the split structure:

1. **ID routing dependencies** (most important): Endpoints like boxscore and plays require a `game_stream_id` that must come from game-summaries -- not from the schedule. Express in `see_also` frontmatter + an "ID chain" block in the endpoint body.

2. **Complement pairs**: Endpoints that cover different aspects of the same game/resource (boxscore + public details, games + games/preview, season-stats + player-stats-per-game). Express in `see_also` frontmatter with a `reason` explaining what the other endpoint adds.

3. **Bridge/resolver relationships**: `public-team-profile-id` resolves UUID -> public_id, enabling public endpoint access. `events/{event_id}/best-game-stream-id` resolves event_id -> game_stream_id. Express in `see_also` with `reason: "Bridge endpoint: {source_id} -> {target_id}"`.

4. **Shared response schema**: The `me-teams` and `me-archived-teams` endpoints return the same schema. Note this in both files' Known Limitations or Notes.

5. **Profile header reference**: Each endpoint's Headers section refers to the global `headers.md` for the standard browser header set, avoiding duplication.

### RQ-4: Web vs. Mobile Profile-Specific Information

**Answer: Inline per-profile sections using the `profiles` frontmatter structure.**

Most endpoints have not been tested on both profiles. The convention:

- **When only web profile confirmed:** `profiles.mobile.status: unverified` with a note. No separate mobile headers section in the body.
- **When both profiles confirmed with identical behavior:** `profiles.{both}.status: confirmed` with no notes. Single headers section labeled "Web Profile." Add a line: "Mobile profile uses the same endpoint with mobile-profile headers (see `headers.md`). Response schema is identical."
- **When profiles differ materially:** Add separate `## Headers (Web Profile)` and `## Headers (Mobile Profile)` sections. Note specific differences (different Accept version, different gc-app-version, different response fields).

The most important profile difference observed so far: the mobile Odyssey app includes `gc-app-version: 2026.7.0.0` and `x-gc-features: lazy-sync`, `x-gc-application-state: foreground`. These appear only in global `headers.md`. Endpoint files note when the mobile profile was confirmed.

### RQ-5: Global Reference File vs. Per-Endpoint Content Boundary

**Answer: Accept header always per-endpoint; everything else follows the global-when-identical principle.**

The boundary rule:

**Always in the endpoint file (never global):**
- `Accept` header value -- different per endpoint, always specific
- `gc-user-action` value -- endpoint-specific action label
- Query parameter documentation
- Response schema (inline or via `related_schemas` reference)
- Known Limitations specific to this endpoint
- Pagination behavior observed for this endpoint (page size, cursor format)

**Always global (never repeated per endpoint):**
- JWT structure and token lifetime
- gc-token and gc-device-id format and storage conventions
- Standard browser headers (sec-ch-ua, sec-fetch-*, referer, origin, DNT, etc.)
- Pagination mechanism (how x-pagination: true request header + x-next-page response header works)
- Base URL and subdomain conventions
- Python pagination loop implementation (Notes for Implementers)

**The Accept header is per-endpoint.** This is the key boundary decision. The Accept header format follows a pattern (`application/vnd.gc.com.{resource}:{cardinality}+json; version={v}`) that is documented globally in `content-type.md`, but the specific value (`resource`, `cardinality`, `version`) is unique per endpoint and must live in each endpoint file. Searching for "what Accept header does X use" should return the answer immediately from the endpoint file, not require cross-referencing a global table.

**The full header block in endpoint files:** Each endpoint file shows a complete header block for reference, including standard browser headers. This is intentionally redundant with `headers.md`. The redundancy helps readers immediately see what a complete request looks like without jumping to another file. A note at the bottom of each header block says: "Standard browser headers (sec-ch-ua, sec-fetch-*, etc.) are defined in `headers.md`."

---

## 9. Implementation Notes for Story Authors

### For E-062-01 (Directory Structure and Global Reference Files)

Create the following structure:
```
docs/api/
  README.md                  <- Endpoint index with filenames and one-line descriptions
  auth.md                    <- JWT, token lifetime, credential headers
  headers.md                 <- Profile comparison table, standard browser headers
  pagination.md              <- x-pagination mechanism, loop pattern, cursor format
  content-type.md            <- Vendor-typed Accept pattern
  base-url.md                <- Base URL and subdomain notes
  error-handling.md          <- Common error codes in GC API context
  {endpoint-files...}        <- All per-endpoint files
```

### For E-062-02 (Core Endpoint Migration)

The 23 Tier 1 endpoints need their full content migrated from the monolith. Pay special attention to:
- 5 endpoints whose schemas live in the "Response Schemas" section -- these must be inlined
- `POST /auth` has a partial schema (200 response not confirmed) -- mark status: PARTIAL

### For E-062-03 (2026-03-07 Probe Endpoints)

The 55 Tier 2 endpoints vary widely in documentation quality:
- Some (lineup-recommendation, opponent/{id}, bats-starting-lineups) are fully documented
- Others (empty-array-returning endpoints) have minimal content
- Video endpoints contain security-sensitive fields (publish_url, stream keys) -- note redaction requirements

### For E-062-06 (Proxy-Discovered / Minimal Endpoints)

The 10+ Tier 3 endpoints mostly have OBSERVED status. The key task is creating minimal-but-complete files that:
- Set accurate `status: OBSERVED` or `status: PARTIAL`
- Document what IS known (path pattern, HTTP status observed, query keys seen in proxy log)
- Use `caveats` to document what investigation is needed
- Set `related_schemas: []` and `response_sample: null` explicitly

The `get-organizations-org_id-opponent-players.md` prototype demonstrates the pattern for a PARTIAL endpoint.

---

*End of Format Specification Document*
