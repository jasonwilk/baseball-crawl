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
| `GET /me/organizations` | 50 | Send `x-pagination: true`. Whether the query params are *also* required is **unverified** -- see the org-level section below. |
| `GET /me/related-organizations` | 50 | Send `x-pagination: true`. Query-param requirement **unverified** -- see below. |
| `GET /organizations/{org_id}/teams` | 50 (server-capped) | **The `x-pagination: true` HEADER is the requirement; the query params are optional.** Params *without* the header → HTTP 500. Measured 2026-08-04. |
| `GET /organizations/{org_id}/opponents` | 50 | Cursor-based, same pattern. |
| `GET /organizations/{org_id}/opponent-players` | 50 | Send `x-pagination: true`; the bare call still 500s (2/2, 2026-08-04). 460 records across 2 calls measured. The older "suspected pagination params required" reading was backwards -- it is the header. |

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

⚠ **On the two endpoints actually measured, the HEADER is the requirement and the query params are optional.** Measured 2026-08-04 on `/organizations/{org_id}/teams`: `x-pagination: true` alone → 200, while `page_starts_at` + `page_size` **without** the header → HTTP 500. Same on `/organizations/{org_id}/opponent-players` (bare call 500s, 2/2). An earlier revision of this section had the causation backwards -- it read as though the params were required and the header incidental.

**Scope this claim honestly.** It rests on two endpoints. The `/me/*` pair below has **not** been re-measured, and their endpoint docs still assert the params are required:

| Endpoint | Causation verified? |
|---|---|
| `/organizations/{org_id}/teams` | ✅ measured 2026-08-04 — header required, params optional, `page_size` capped at 50 |
| `/organizations/{org_id}/opponent-players` | ✅ measured 2026-08-04 — bare call 500s 2/2 |
| `/me/organizations` | ❓ **unverified** — same server and error message, so the same causation is *likely*, but likely is not measured |
| `/me/related-organizations` | ❓ **unverified** — same |

Practical rule either way: **send `x-pagination: true` always**; add params only when you want a specific offset. That is correct under both readings, which is why it is safe to state while the `/me/*` question is open.

```
GET /me/organizations?page_size=50                                  # causation unverified
Header: x-pagination: true
```

```
GET /me/related-organizations?page_starts_at=0&page_size=50          # causation unverified
Header: x-pagination: true
```

```
GET /organizations/{org_id}/teams                                    # header alone suffices
Header: x-pagination: true
```

The HTTP 500 body is: `"Cannot read properties of undefined (reading 'page_starts_at')"` or `"Cannot read properties of undefined (reading 'page_size')"`. Read it as *"the header was missing, so the server had no pagination object to read that key from"* -- **not** as "you forgot the query param." The message names the key it tried to read, which is what made the original diagnosis point at the params.

## End-of-Pagination Detection

**Terminate on an empty response body OR on `x-next-page` being absent -- whichever comes first.** Check both.

⚰ **RETIRED 2026-08-04** -- the previous guidance said the opposite and is quoted here only so it is not reintroduced: *"**Correct:** `x-next-page` header is **absent** from the response. **Incorrect:** Do not rely on an empty response body -- the last page will have records but no `x-next-page` header."*

**Why it was wrong: `x-next-page` OVER-REPORTS.** Measured 2026-08-04 on `/organizations/{org_id}/teams` -- the last **populated** page still carried an `x-next-page` header, and following it returned `200 []`. So header-absence is not a reliable stop signal on its own: a loop that waits for the header to disappear makes at least one extra request, and cannot distinguish "one more page" from "no more pages."

The empty body is the authoritative terminator. Header-absence remains a valid *early* stop where it does occur -- it just cannot be the only one you check. Note the failure mode is quiet: an over-reported page returns `200` with an empty array, so nothing raises and a naive loop simply does redundant work rather than crashing.

## Page Size Notes

50 records per page observed on game-summaries with `x-pagination: true`. The last page may have fewer records (42 records on the 2nd page of 92 total). Page size of 50 appears to be the maximum; it may vary by endpoint.
