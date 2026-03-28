---
method: POST
path: /search
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Live curl from devcontainer (web headers) returned 200 OK, 2026-03-27.
      Content-Type uses underscore: post_search (not post-search).
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
      Pagination: zero-indexed page number. Page 0 is the first page.
      25 results per page.
  - name: search_source
    required: false
    description: >
      Observed value: "search". Purpose unclear -- may distinguish search origin
      (e.g., search bar vs. opponent import). Observed on web 2026-03-27.
pagination: true
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-27"
tags: [search]
caveats:
  - >
    CONTENT-TYPE UNDERSCORE: The working Content-Type uses an underscore (`post_search`),
    not a hyphen (`post-search`). The underscore variant was confirmed to return 200 OK
    on 2026-03-27. The hyphen variant has not been tested.
  - >
    SEARCH-AS-YOU-TYPE: On mobile, 6 calls were observed in ~10 seconds of user typing
    "nighthawks". The mobile app fires this endpoint repeatedly as the user types.
see_also:
  - path: /search/opponent-import
    reason: Legacy opponent import search endpoint (GET). POST /search is now the primary search mechanism for opponent resolution (E-168).
  - path: /search/history
    reason: GET to read search history; POST to record a completed search
---

# POST /search

**Status:** CONFIRMED -- live curl returned 200 OK (2026-03-27). Full request/response schema documented.

Main general-purpose team search. Used by the iOS GC app search bar (search-as-you-type), confirmed working from web profile, and used programmatically for opponent resolution (both admin resolve and automated fallback -- see [opponent-resolution.md](../flows/opponent-resolution.md)).

```
POST https://api.team-manager.gc.com/search?start_at_page={page}&search_source=search
Content-Type: application/vnd.gc.com.post_search+json; version=0.0.0
```

**Note:** The Content-Type uses `post_search` (underscore), not `post-search` (hyphen).

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
| `hits[].result.location.city` | string | Team city. |
| `hits[].result.location.country` | string | Team country. |
| `hits[].result.location.state` | string | Team state. |
| `hits[].result.season.name` | string | Season name (e.g., `"spring"`). |
| `hits[].result.season.year` | int | Season year. |
| `hits[].result.number_of_players` | int | Number of players on the roster. |
| `hits[].result.staff` | array of strings | Coach/staff names. |
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
        "name": "Example Team Varsity 2026",
        "sport": "baseball",
        "location": {
          "city": "Anytown",
          "country": "US",
          "state": "XX"
        },
        "season": {
          "name": "spring",
          "year": 2026
        },
        "number_of_players": 15,
        "staff": ["Jane Doe", "Player One"]
      }
    }
  ],
  "next_page": 1
}
```

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

**Discovered:** 2026-03-09. **Last confirmed:** 2026-03-27.
