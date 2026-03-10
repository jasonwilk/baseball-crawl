---
paths:
  - "docs/api/**"
---

# API Documentation Rules

## Canonical Location and Structure

GameChanger API documentation lives in `docs/api/`:

```
docs/api/
  README.md          # Index: all endpoints with method, path, status, auth, description
  auth.md            # JWT structure, token lifetime, gc-token, gc-device-id
  headers.md         # Canonical header sets for web and mobile profiles
  pagination.md      # x-pagination mechanism, x-next-page, cursor format
  content-type.md    # Vendor-typed Accept header pattern
  base-url.md        # Base URL and subdomain conventions
  error-handling.md  # Common HTTP error codes in GC API context
  flows/             # Multi-endpoint integration guides
    opponent-resolution.md
  endpoints/         # One file per endpoint (89 files)
    get-me-teams.md
    get-teams-team_id-schedule.md
    post-auth.md
    ...
```

## Loading Discipline

- **MUST** read `docs/api/README.md` first to identify which endpoint files are relevant to the current task.
- **MUST NOT** glob-read or bulk-load all files in `docs/api/endpoints/`. There are 89 endpoint files totaling thousands of lines -- loading them all wastes context window budget.
- **MUST** load only the specific endpoint files relevant to the current task.
- **Exception**: The ingest-endpoint skill workflow (api-scout already knows which file to create/update and does not need the index).
- Load `docs/api/flows/` docs by name when working on multi-endpoint integration tasks; do NOT bulk-load all flow docs.

## Accuracy Standard

- The `last_confirmed` frontmatter field MUST only be updated after live verification (executing a curl against the endpoint and confirming the response matches the documented schema).
- Do NOT update `last_confirmed` during migrations, edits, or changes that do not re-verify the endpoint against live data.
- Accept headers, auth requirements, and status values in frontmatter must match live verification evidence.
- All example JSON in endpoint files must use PII-safe placeholder values -- see the Example JSON Safety section below.

## File Naming Convention

Endpoint files are named: `{method}-{path-segments-with-params-as-words}.md`

- All lowercase. Hyphens between path segments.
- Path parameters are rendered by their parameter name **without curly braces**.
- Path separators (`/`) become hyphens.

Examples:
| API Path | Filename |
|----------|----------|
| `GET /me/teams` | `get-me-teams.md` |
| `GET /teams/{team_id}/schedule` | `get-teams-team_id-schedule.md` |
| `POST /auth` | `post-auth.md` |
| `GET /public/teams/{public_id}` | `get-public-teams-public_id.md` |
| `GET /teams/public/{public_id}/players` | `get-teams-public-public_id-players.md` |

## YAML Frontmatter Schema

Every endpoint file requires YAML frontmatter with these fields:

```yaml
---
method: GET | POST | PATCH | PUT | DELETE
path: /path/{param}/subpath
status: CONFIRMED | OBSERVED | PARTIAL | UNTESTED | DEPRECATED
auth: required | none
profiles:
  web:
    status: confirmed | observed | partial | unverified | not_applicable
    notes: >                    # Optional -- include when behavior differs from mobile
  mobile:
    status: confirmed | observed | partial | unverified | not_applicable
    notes: >                    # Optional
accept: "application/vnd.gc.com.{resource}:{cardinality}+json; version={semver}"
         # null when not yet confirmed
gc_user_action: "data_loading:{context}"   # null when not observed
query_params:
  - name: param_name
    required: true | false | unknown
    description: >
pagination: true | false | unknown
response_shape: array | object | string
response_sample: data/raw/filename.json    # null if no sample
raw_sample_size: "N records, K KB"         # null if no sample
discovered: "YYYY-MM-DD"
last_confirmed: "YYYY-MM-DD"              # null if never independently confirmed
tags: [tag1, tag2]
caveats:                                   # Omit entirely when no caveats
  - >
    Free-text caveat description.
see_also:
  - path: /other/endpoint
    reason: One-line cross-reference reason
---
```

### Status Values

| Value | Meaning |
|-------|---------|
| `CONFIRMED` | Live curl returned 200 OK; response schema documented from actual data |
| `OBSERVED` | Seen in proxy/curl traffic but not independently verified |
| `PARTIAL` | Endpoint exists but only works with specific parameters; see `caveats` |
| `UNTESTED` | Path pattern known but no response captured |
| `DEPRECATED` | Was confirmed but no longer active or replaced |

### Profile Status Values

| Value | Meaning |
|-------|---------|
| `confirmed` | Independently verified via direct curl from this profile |
| `observed` | Seen in proxy traffic for this profile but not independently verified via direct curl |
| `partial` | Some aspects confirmed for this profile, others not (e.g., specific parameters tested) |
| `unverified` | Not captured or tested from this profile |
| `not_applicable` | Profile does not apply to this endpoint |

### Tag Vocabulary

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
| `bulk` | High-value bulk data endpoints |
| `calendar` | External calendar sync endpoints |
| `me` | `/me/` path endpoints (user account, preferences, permissions) |
| `media` | Media asset endpoints (photos, images, avatar URLs) |
| `permissions` | Access control and permission endpoints |
| `search` | Search and discovery endpoints |
| `web-routes` | Web-only routes and non-API paths |
| `write` | Mutation endpoints (PATCH, POST for data changes other than auth/sync) |

Tag conventions: 2-5 tags per endpoint. `public` always accompanies relevant domain tags for unauthenticated endpoints.

## Example JSON Safety

Committed API doc files (`docs/api/endpoints/*.md`) must use clearly fake/redacted data in all example JSON -- both request body and response body examples. The PII pre-commit hook catches credentials (tokens, passwords) but not team names, cities, or other identifying data. These rules are the enforcement point for that broader concern.

### PII-Safe Placeholder Taxonomy

Use these approved placeholder values when writing or updating example JSON:

| Category | Placeholder Values |
|----------|-------------------|
| Team names | `"Example Team 14U"`, `"Anytown Eagles 12U"` |
| Organization/league names | `"Example Organization"`, `"Example League"` |
| Cities/States | `"Anytown"`, `"XX"` (or generic like `"Springfield"`, `"IL"`) |
| Venue/field names | `"Anytown Field"`, `"Example Park"` |
| Person names (players, coaches, staff, parents) | `"Jane Doe"`, `"Player One"` |
| Phone numbers | `"+1 (555) 555-0100"`, `"+15550001234"` |
| UUIDs | `"72bb77d8-REDACTED"` or `"00000000-0000-0000-0000-000000000001"` |
| Emails | `"user@example.com"` (use `example.com` domain) |
| public_id slugs | `"xXxXxXxXxXxX"` or similar clearly fake values |
| url_encoded_name | `"2024-spring-example-team-14u"` |
| Avatar/media URLs | `"https://media-service.gc.com/example-avatar-url"` |

**UUID scope**: The UUID redaction rule applies to ALL UUID fields regardless of field name (`id`, `stream_id`, `event_id`, `game_stream_id`, `player_uuid`, `team_id`, `opponent_id`, etc.) and when UUIDs appear as dict keys (e.g., player-stats keyed by player UUID).

### NOT PII -- Keep As-Is

The following categories are NOT PII and may be kept as-is from real responses:

- **Numeric stats** (batting averages, pitch counts, ERAs, etc.)
- **Dates** (keep realistic but not identifying -- any recent date is fine)
- **Jersey numbers** (visible on any game broadcast)
- **Boolean flags** (`true`/`false` values)
- **Enum values** (status codes, competition levels, etc.)

### Semi-Identifying Combinations

Even non-PII fields can become identifying when combined:

- **Win-loss records**: Avoid preserving exact records (e.g., `"61-29-2"`) that could identify a specific team. Use generic records (e.g., `{"wins": 12, "losses": 8, "ties": 0}`).
- **Season + age group + competition level**: Avoid combining a specific `season_year + age_group + competition_level` that matches a real team's history -- replace with a generic recent year.

## Example Request Body Guidance

Endpoint files SHOULD include an "Example Request Body" section (between Headers and Response sections) for POST, PATCH, PUT, and DELETE endpoints that accept a JSON body. The example request body follows the same PII-safe placeholder rules as response examples. Omit this section for GET endpoints or endpoints with no request body.
