---
method: GET
path: /organizations/{org_id}/opponent-players
status: PARTIAL
auth: required
profiles:
  web:
    status: partial
    notes: >
      Returns HTTP 500 with web browser headers. Error: "Cannot read properties
      of undefined (reading 'page_size')". A missing pagination parameter is
      triggering the 500 -- similar to /me/organizations and /me/related-organizations
      which both required ?page_size=50 + x-pagination:true. Required parameter
      combination not yet confirmed.
  mobile:
    status: observed
    notes: >
      iOS proxy capture showed 200 OK responses with 2 hits and pagination
      (start_at cursor observed). Mobile profile may send the required pagination
      parameters automatically. Schema not captured from mobile response.
accept: null
gc_user_action: null
query_params:
  - name: start_at
    required: unknown
    description: >
      Pagination cursor (observed in iOS proxy log). Likely an integer sequence
      number consistent with other paginated endpoints (game-summaries, opponents).
      May also require page_size parameter -- not yet confirmed.
pagination: true
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [organizations, opponents, players, roster, handedness, bulk]
caveats:
  - >
    HTTP 500 returned with web headers without correct pagination parameters.
    Suspected fix: add ?page_size=50 + x-pagination:true request header
    (same pattern as /organizations/{org_id}/teams, /me/organizations,
    /me/related-organizations). Not yet verified.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents/players
    reason: >
      Team-scoped equivalent: returns all opponent players for one team. CONFIRMED
      working (758 records, 61 teams, 2026-03-07). If the org-level endpoint remains
      blocked, iterate this endpoint per org team as a fallback.
  - path: /organizations/{org_id}/opponents
    reason: Org-level opponent registry (CONFIRMED working) -- use for opponent UUIDs
  - path: /organizations/{org_id}/teams
    reason: Enumerate org teams to drive per-team /opponents/players calls as fallback
---

# GET /organizations/{org_id}/opponent-players

**Status:** PARTIAL -- endpoint exists but returns HTTP 500 with web browser headers due to missing pagination parameters. iOS proxy capture confirms the endpoint returns HTTP 200 with paginated responses from the mobile profile. Web-profile fix not yet confirmed.

Returns opponent player rosters at the organization level. This is the org-scoped analog to `GET /teams/{team_id}/opponents/players` (which is CONFIRMED and returns 758 records for one team). The org-level variant would aggregate across all teams in the organization in a single call.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/opponent-players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id`  | UUID | Organization UUID |

## Query Parameters

| Parameter   | Required | Description |
|-------------|----------|-------------|
| `start_at`  | Unknown  | Pagination cursor (observed in iOS proxy log). Likely integer sequence number. |
| `page_size` | Unknown  | Suspected required parameter. Try `50` based on pattern from other org endpoints. |

## Suspected Required Headers (Unverified)

Based on the error message and the pattern from other org endpoints that previously returned HTTP 500:

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
x-pagination: true    <- suspected required; server returns 500 without it on similar endpoints
Accept: (unknown -- vendor-typed accept for opponent player list)
```

> **Investigation needed:** Try `GET /organizations/{org_id}/opponent-players?page_size=50` with `x-pagination: true` request header. This combination fixed `/organizations/{org_id}/teams`, `/me/organizations`, and `/me/related-organizations`.

## Error Response (HTTP 500 -- Web Headers Without Required Params)

```json
{"error": "Cannot read properties of undefined (reading 'page_size')"}
```

The error message is different from the error observed on other org endpoints (`"Cannot read properties of undefined (reading 'page_starts_at')"` for `/organizations/{org_id}/teams`). This suggests `opponent-players` uses a different pagination parameter name (`page_size` directly, vs. `page_starts_at` + `page_size` for `/teams`). Priority investigation target.

## Expected Response

Based on the team-scoped equivalent (`GET /teams/{team_id}/opponents/players` -- CONFIRMED 2026-03-07), the response is likely a bare JSON array of player records with the following structure:

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | The opponent team UUID the player belongs to |
| `player_id` | UUID | The player's UUID |
| `person` | object | Player identity (`id`, `first_name`, `last_name`) |
| `attributes` | object | `player_number` (string), `status` ("active" or "removed") |
| `bats` | object or null | `batting_side` ("left", "right", "both", or null), `throwing_hand` ("left", "right", or null) |

This is the expected schema based on the team-level equivalent. Actual org-level response may include additional fields (e.g., `org_id`) or use a different structure.

## Fallback Strategy

If this endpoint cannot be confirmed, use the team-level equivalent per org team:

```
1. GET /organizations/{org_id}/teams?page_starts_at=0&page_size=50 (CONFIRMED)
   -> enumerate all org team UUIDs

2. For each team UUID:
   GET /teams/{team_id}/opponents/players (CONFIRMED -- 758 records, no pagination needed)
   -> aggregate opponent player records
```

The team-level endpoint is confirmed working and returns all opponent players without pagination. The org-level endpoint would simply eliminate the per-team iteration.

## Known Limitations

- **HTTP 500 blocker.** Cannot confirm response schema until the correct parameter combination is identified.
- **Paginated in iOS capture.** The iOS proxy capture showed `start_at` cursor present, suggesting large response sets. Pagination behavior with correct web-profile params is untested.
- **Schema unverified.** Expected schema is inferred from the team-level equivalent -- actual org-level response may differ.

**Discovered:** 2026-03-05.
