---
method: POST
path: /search
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile. Web may use GET /search/opponent-import instead.
  mobile:
    status: confirmed
    notes: >
      6 hits, all HTTP 200. Triggered by typing in the main GC app search bar ("nighthawks").
      Multiple sequential calls observed as user types (search-as-you-type pattern).
      Confirmed 2026-03-09.
accept: null
gc_user_action: null
query_params:
  - name: start_at_page
    required: false
    description: >
      Pagination: page number to start at. Present on all 6 observed calls (including
      first page). Value not captured from proxy metadata.
pagination: true
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: null
tags: [search]
caveats:
  - >
    SCHEMA UNKNOWN: Request body and response body not captured by proxy -- only
    the content-type and query key metadata are available. Body schema requires
    live curl to determine.
  - >
    MOBILE-ONLY CONFIRMED: This is the main mobile app search endpoint (GC app search bar).
    The web equivalent may be GET /search/opponent-import, which is documented separately.
    Whether POST /search works on web is unknown.
  - >
    SEARCH-AS-YOU-TYPE: 6 calls were observed in ~10 seconds of user typing "nighthawks".
    The mobile app fires this endpoint repeatedly as the user types. Likely has query params
    in the body to filter by sport, age group, or result type -- unknown without body capture.
see_also:
  - path: /search/opponent-import
    reason: Alternative search endpoint (GET, web/mobile) for opponent import flow -- known response schema
  - path: /search/history
    reason: GET to read search history; POST to record a completed search
---

# POST /search

**Status:** CONFIRMED (observed 6 hits, HTTP 200). Request/response body schema unknown.

Main general-purpose team search in the iOS GC app. Triggered when the user types in the primary search bar -- fires repeatedly as the user types (search-as-you-type). Distinct from `GET /search/opponent-import`, which is used specifically in the "add opponent" import flow.

```
POST https://api.team-manager.gc.com/search?start_at_page={page}
Content-Type: application/vnd.gc.com.post-search+json; version=0.0.0
```

## Path Parameters

None.

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `start_at_page` | optional | Pagination page number. Observed on all calls including page 1. |

## Request Body

Body schema unknown -- not captured by proxy. Expected to contain the search query string and possibly filters (sport, age group, competition level, result type).

Content-Type: `application/vnd.gc.com.post-search+json; version=0.0.0`

## Response

Response body schema unknown -- not captured by proxy.

Response Content-Type: `application/json; charset=utf-8`

Based on the `GET /search/history` response shape (which stores past search results), expected response fields per result item include:
- `id` (UUID)
- `public_id` (slug)
- `name` (team name)
- `sport`
- `season` (name, year)
- `location` (city, state, country)
- `staff` (array of strings)
- `number_of_players` (int)
- `avatar_url` (optional, signed URL)

## Navigation Flow (Mobile)

The mobile app uses this endpoint in the following sequence:

1. App opens → `GET /search/history` (load recent searches for display)
2. User types in search bar → `POST /search?start_at_page=0` fired repeatedly
3. User selects a result → `POST /search/history` (record the selection)
4. App navigates to team page → `GET /teams/{progenitor_team_id}` (team metadata)
5. App loads full team context → bulk parallel requests to team sub-resources

The UUID returned in the search result is the `progenitor_team_id` that is used with all `/teams/{team_id}/*` authenticated endpoints.

## Known Limitations

- Body and response schema not captured -- live curl needed for full documentation.
- Number of results per page unknown.
- Filtering capabilities (sport, level, age group) unknown.

**Discovered:** 2026-03-09.
