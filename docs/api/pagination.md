# Pagination

## Protocol

GameChanger uses **cursor-based pagination** for endpoints that support it. The pagination mechanism is:

1. Send `x-pagination: true` as a **request header** to enable pagination
2. Read the `x-next-page` **response header** to get the URL for the next page
3. When `x-next-page` is absent from the response, you are on the last page

The response body is always a **bare JSON array** -- pagination metadata is NOT in the body.

## Paginated Endpoints

| Endpoint | Page Size | Notes |
|----------|-----------|-------|
| `GET /teams/{team_id}/game-summaries` | 50 | Confirmed 2026-03-04. 92 total records across 2 pages (50 + 42). |
| `GET /teams/{team_id}/opponents` | 50 | Confirmed 2026-03-04. 70 records across 2 pages (50 + 20). |
| `GET /teams/{team_id}/users` | Unknown | Confirmed cursor pattern from page 2 capture (`start_at=100`). |
| `GET /me/organizations` | 50 | Requires `?page_size=50` query param + `x-pagination: true` header. |
| `GET /me/related-organizations` | 50 | Requires `?page_starts_at=0&page_size=50` + `x-pagination: true` header. |
| `GET /organizations/{org_id}/teams` | 50 | Requires `?page_starts_at=0&page_size=50` + `x-pagination: true` header. |
| `GET /organizations/{org_id}/opponents` | 50 | Cursor-based, same pattern. |
| `GET /organizations/{org_id}/opponent-players` | Unknown | HTTP 500 with web headers; suspected pagination params required. |

## Non-Paginated Endpoints

These endpoints return all records in a single response (no `x-next-page` header observed):

- `GET /teams/{team_id}/schedule` -- 228 events returned in one response
- `GET /teams/{team_id}/players` -- 20 players returned in one response
- `GET /teams/{team_id}/season-stats` -- full season data in one response
- `GET /teams/{team_id}/associations` -- 244 records returned in one response
- `GET /teams/{team_id}/players/{player_id}/stats` -- 80 records in one response

## Reference Implementation

```python
def fetch_all_game_summaries(session, team_id: str) -> list:
    """Fetch all game summaries for a team using cursor-based pagination."""
    import time
    import random

    url = f"https://api.team-manager.gc.com/teams/{team_id}/game-summaries"
    headers = {
        "x-pagination": "true",
        "gc-user-action": "data_loading:events",
        "Accept": "application/vnd.gc.com.game_summary:list+json; version=0.1.0",
        # ... other standard headers from session defaults
    }
    results = []
    next_url = url  # start with no cursor (first page)

    while next_url:
        response = session.get(next_url, headers=headers)
        response.raise_for_status()
        page = response.json()

        if not page:
            break

        results.extend(page)

        # Pagination cursor is in the x-next-page response header
        # When absent, this is the last page
        next_url = response.headers.get("x-next-page")

        if next_url:
            # Jitter between pages -- respect rate limiting
            time.sleep(1 + random.random())

    return results
```

## Cursor Format

The `x-next-page` response header contains a **full URL** including the `start_at` cursor parameter. Do not parse the URL -- use it directly as the next request URL.

Example:
```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/game-summaries?start_at=136418700
```

The cursor value (`136418700` in this example) is an integer sequence number. The specific semantics vary by endpoint.

## Org-Level Pagination Pattern

Some organization endpoints require pagination parameters in the **query string** (not just the header), or they return HTTP 500:

```
GET /me/organizations?page_size=50
Header: x-pagination: true
```

```
GET /me/related-organizations?page_starts_at=0&page_size=50
Header: x-pagination: true
```

```
GET /organizations/{org_id}/teams?page_starts_at=0&page_size=50
Header: x-pagination: true
```

The error message when pagination params are missing is: `"Cannot read properties of undefined (reading 'page_starts_at')"` or `"Cannot read properties of undefined (reading 'page_size')"`.

## End-of-Pagination Detection

- **Correct:** `x-next-page` header is **absent** from the response
- **Incorrect:** Do not rely on an empty response body -- the last page will have records but no `x-next-page` header

## Page Size Notes

50 records per page observed on game-summaries with `x-pagination: true`. The last page may have fewer records (42 records on the 2nd page of 92 total). Page size of 50 appears to be the maximum; it may vary by endpoint.
