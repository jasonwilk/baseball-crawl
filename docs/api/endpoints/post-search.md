---
method: POST
path: /search
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Live curl returned 200 OK, 2026-03-29.
      Content-Type uses underscore: post_search (not post-search).
      Accept header confirmed: search_results (not post_search).
      avatar_url field discovered (optional, signed CloudFront URL).
  mobile:
    status: confirmed
    notes: >
      6 hits, all HTTP 200. Triggered by typing in the main GC app search bar ("nighthawks").
      Multiple sequential calls observed as user types (search-as-you-type pattern).
      Confirmed 2026-03-09.
accept: "application/vnd.gc.com.search_results+json; version=0.0.0"
gc_user_action: null
query_params:
  - name: start_at_page
    required: false
    description: >
      Pagination: zero-indexed page number. Page 0 is the first page.
      25 results per page.
  - name: search_source
    required: false
    description: >
      Observed value: "search". Purpose unclear -- may distinguish search origin
      (e.g., search bar vs. opponent import). Observed on web 2026-03-27.
pagination: true
response_shape: object
response_sample: data/raw/search-sample.json
raw_sample_size: "25 records, ~25 KB"
discovered: "2026-03-09"
last_confirmed: "2026-03-29"
tags: [search, team]
caveats:
  - >
    CONTENT-TYPE UNDERSCORE: The working Content-Type uses an underscore (`post_search`),
    not a hyphen (`post-search`). The underscore variant was confirmed to return 200 OK
    on 2026-03-29. The hyphen variant has not been tested.
  - >
    ACCEPT HEADER: The browser sends `Accept: application/vnd.gc.com.search_results+json; version=0.0.0`
    (resource name: `search_results`). This differs from the Content-Type resource name (`post_search`).
    Our programmatic code was not setting a specific Accept header and still received valid JSON responses.
    Both approaches work but `search_results` is the correct vendor media type. Confirmed 2026-03-29.
  - >
    SEARCH-AS-YOU-TYPE: On mobile, 6 calls were observed in ~10 seconds of user typing
    "nighthawks". The mobile app fires this endpoint repeatedly as the user types.
  - >
    AVATAR_URL OPTIONAL: The `avatar_url` field is only present on teams that have uploaded
    a team logo/avatar. It is a signed CloudFront URL with time-limited validity. Not all
    teams have this field. Discovered 2026-03-29.
see_also:
  - path: /search/opponent-import
    reason: Legacy opponent import search endpoint (GET). POST /search is now the primary search mechanism for opponent resolution (E-168).
  - path: /search/history
    reason: GET to read search history; POST to record a completed search
---

# POST /search

**Status:** CONFIRMED -- live curl returned 200 OK (2026-03-29). Full request/response schema documented.

Main general-purpose team search. Used by the iOS GC app search bar (search-as-you-type), confirmed working from web profile, and used programmatically for opponent resolution (both admin resolve and automated fallback -- see [opponent-resolution.md](../flows/opponent-resolution.md)). Also used as the **public_id-to-gc_uuid bridge**: search by team name, filter hits by `result.public_id`, and extract `result.id` as the `gc_uuid`. See `.claude/rules/gc-uuid-bridge.md` for the full pattern.

```
POST https://api.team-manager.gc.com/search?start_at_page={page}&search_source=search
Accept: application/vnd.gc.com.search_results+json; version=0.0.0
Content-Type: application/vnd.gc.com.post_search+json; version=0.0.0
```

**Note:** The Content-Type uses `post_search` (underscore), not `post-search` (hyphen). The Accept header uses `search_results` -- a different resource name than the Content-Type. Our programmatic code was not setting a specific Accept header; the browser sends `search_results`. Both appear to work (the API returns JSON regardless), but `search_results` is the correct vendor media type for this endpoint's response.

## Path Parameters

None.

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `start_at_page` | optional | Zero-indexed page number. 25 results per page. |
| `search_source` | optional | Observed value: `"search"`. Purpose unclear -- may indicate search origin context. |

## Request Body

```json
{
  "name": "search query string"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Search query. Matches against team names. |

Content-Type: `application/vnd.gc.com.post_search+json; version=0.0.0`

### Example Request Body

```json
{
  "name": "example team varsity"
}
```

## Response

Response Content-Type: `application/json; charset=utf-8`

### Schema

```json
{
  "total_count": 263,
  "hits": [
    {
      "type": "team",
      "result": {
        "id": "UUID",
        "public_id": "string (slug)",
        "name": "string",
        "sport": "string",
        "location": {
          "city": "string",
          "country": "string",
          "state": "string"
        },
        "season": {
          "name": "string",
          "year": 2026
        },
        "avatar_url": "string (signed CloudFront URL) | absent",
        "number_of_players": 15,
        "staff": ["string"]
      }
    }
  ],
  "next_page": 1
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `total_count` | int | Total number of matching results across all pages. |
| `hits` | array | Array of search result objects for the current page. 25 per page. |
| `hits[].type` | string | Result type. Observed value: `"team"`. |
| `hits[].result.id` | UUID | The `progenitor_team_id` -- canonical GC team UUID used with all `/teams/{team_id}/*` authenticated endpoints. |
| `hits[].result.public_id` | string | Public slug for the team. Used with `/public/teams/{public_id}` endpoints. |
| `hits[].result.name` | string | Team display name (typically includes year, e.g., "Team Name 2026"). |
| `hits[].result.sport` | string | Sport identifier (e.g., `"baseball"`). |
| `hits[].result.location` | object | Team location. Can be empty object `{}` when no location is set. |
| `hits[].result.location.city` | string | Team city. Absent when `location` is empty. |
| `hits[].result.location.country` | string | Team country. Observed values: `"United States"`, `"USA"`, `"US"`. Absent when `location` is empty. |
| `hits[].result.location.state` | string | Team state (two-letter abbreviation). Absent when `location` is empty. |
| `hits[].result.season.name` | string | Season name (e.g., `"spring"`, `"summer"`, `"fall"`). |
| `hits[].result.season.year` | int | Season year. |
| `hits[].result.avatar_url` | string or absent | Signed CloudFront URL for team avatar image. Only present for teams that have uploaded an avatar. URL includes `Policy`, `Key-Pair-Id`, and `Signature` query parameters (time-limited). |
| `hits[].result.number_of_players` | int | Number of players on the roster. Can be `0` for teams with no roster. |
| `hits[].result.staff` | array of strings | Coach/staff names. Can be empty array `[]`. |
| `next_page` | int or null | Next page number for pagination, or null if no more pages. |

### Example Response

```json
{
  "total_count": 42,
  "hits": [
    {
      "type": "team",
      "result": {
        "id": "00000000-0000-0000-0000-000000000001",
        "public_id": "xXxXxXxXxXxX",
        "name": "Example Team 12U",
        "sport": "baseball",
        "location": {
          "city": "Anytown",
          "country": "United States",
          "state": "XX"
        },
        "season": {
          "name": "spring",
          "year": 2026
        },
        "avatar_url": "https://media-service.gc.com/example-avatar-url",
        "number_of_players": 12,
        "staff": ["Jane Doe", "Player One"]
      }
    },
    {
      "type": "team",
      "result": {
        "id": "00000000-0000-0000-0000-000000000002",
        "public_id": "yYyYyYyYyYyY",
        "name": "Anytown Eagles 12U",
        "sport": "baseball",
        "location": {},
        "season": {
          "name": "fall",
          "year": 2025
        },
        "number_of_players": 0,
        "staff": []
      }
    }
  ],
  "next_page": 1
}
```

**Note:** The first hit shows a team with `avatar_url` (teams that have uploaded a logo), the second shows a team without `avatar_url`, with an empty `location`, zero players, and empty staff list -- all observed in live data.

## Pagination

- 25 results per page.
- Use `start_at_page=0` for the first page.
- `next_page` in the response provides the next page number; null when no more pages.
- `total_count` gives the total matching results across all pages.

## Navigation Flow (Mobile)

The mobile app uses this endpoint in the following sequence:

1. App opens → `GET /search/history` (load recent searches for display)
2. User types in search bar → `POST /search?start_at_page=0` fired repeatedly
3. User selects a result → `POST /search/history` (record the selection)
4. App navigates to team page → `GET /teams/{progenitor_team_id}` (team metadata)
5. App loads full team context → bulk parallel requests to team sub-resources

The `result.id` UUID returned in each search hit is the `progenitor_team_id` used with all `/teams/{team_id}/*` authenticated endpoints. The `result.public_id` slug is used with `/public/teams/{public_id}` public endpoints.

## Known Limitations

- Only `"team"` result type observed. Unknown if other types (player, org) exist.
- Whether `search_source` affects results is unknown.
- Filtering capabilities beyond the `name` field (sport, level, age group) are unknown.
- The hyphen variant of Content-Type (`post-search`) has not been tested.
- `avatar_url` is a signed CloudFront URL with time-limited validity (expiry embedded in the `Policy` parameter). Do not cache these URLs long-term.
- `location.country` is inconsistent: observed `"United States"`, `"USA"`, and `"US"` across different teams. Consumers should normalize.

**Discovered:** 2026-03-09. **Last confirmed:** 2026-03-29.
