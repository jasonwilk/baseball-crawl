# Error Handling

## Common HTTP Status Codes

| Status | Meaning in GC API context |
|--------|--------------------------|
| 200 OK | Request succeeded. Response body is the resource data. |
| 204 No Content | CORS preflight (OPTIONS requests). Not a real API response. |
| 304 Not Modified | Cached response (ETag match). Occurs when `If-None-Match` is used; response body is empty. |
| 400 Bad Request | Malformed request. Most commonly seen on `POST /auth` with an expired or invalid `gc-signature`. |
| 401 Unauthorized | Authentication required or expired. The `gc-token` is missing, expired (~61-minute access token TTL), or invalid. Run `GET /me/user` to check token validity. Refresh programmatically via `POST /auth {"type":"refresh"}`. |
| 403 Forbidden | Authenticated but not authorized. Common case: `GET /bats-starting-lineups/{event_id}` returns 403 for away games where the authenticated user's team was not the primary scorer. |
| 404 Not Found | Endpoint does not exist, or the resource does not exist for this entity. Some 404s indicate premium/gated features (e.g., batting insight endpoints returned 404). |
| 500 Internal Server Error | Server-side error. A known pattern: endpoints requiring pagination parameters (`?page_size=50` + `x-pagination: true` header) return HTTP 500 when those parameters are missing. See Pagination 500 Errors below. |

## Pagination HTTP 500 Errors

A specific HTTP 500 pattern occurs on certain paginated endpoints when pagination query parameters are missing:

**Error message (JSON body):**
```json
{"error": "Cannot read properties of undefined (reading 'page_starts_at')"}
```
or:
```json
{"error": "Cannot read properties of undefined (reading 'page_size')"}
```

**Cause:** The server-side pagination handler expects `page_starts_at` or `page_size` query parameters. Without them, the handler raises an unhandled error.

**Fix:** Add the required pagination parameters to the query string AND the `x-pagination: true` request header:

| Endpoint | Required fix |
|----------|-------------|
| `GET /me/organizations` | `?page_size=50` + `x-pagination: true` |
| `GET /me/related-organizations` | `?page_starts_at=0&page_size=50` + `x-pagination: true` |
| `GET /organizations/{org_id}/teams` | `?page_starts_at=0&page_size=50` + `x-pagination: true` |
| `GET /organizations/{org_id}/opponent-players` | Suspected: `?page_size=50` -- not yet confirmed as of 2026-03-07 |

All three of the first endpoints above were confirmed fixed by adding these parameters (2026-03-07). The fourth (`/opponent-players`) remains blocked as of 2026-03-07.

## 404 on Batting/Insight Endpoints

The following endpoints returned HTTP 404:

- `GET /game-streams/insight-story/bats/{game_stream_id}`
- `GET /game-streams/player-insights/bats/{game_stream_id}`
- `GET /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}`

These 404s suggest premium subscription gating or limited rollout features. Not confirmed as viable data sources.

## 404 on Profile Photo Endpoints

- `GET /users/{user_id}/profile-photo` -- returns 404 with body: `"No profile photo found for user: <uuid>"`
- `GET /players/{player_id}/profile-photo` -- returns 404 with body: `"No profile photo found for player: <uuid>"`

No observed users had profile photos set. The endpoint pattern exists; 404 is expected when no photo has been uploaded.

## 403 on Away-Game Lineups

`GET /bats-starting-lineups/{event_id}` returns HTTP 403 when the `event_id` refers to an away game where the authenticated user's team was not the primary scorer. Use home game event_ids, or events where the user's team managed scoring.

## Retry Behavior

- **401 Unauthorized:** Do not retry. The token is expired. Rotate credentials via the browser capture workflow (`bb creds import`) and restart the session.
- **400 Bad Request:** Do not retry with the same request. Diagnose the malformed parameter or header.
- **500 Internal Server Error:** Check if pagination parameters are missing. If it is a one-off 500 (not a pagination issue), wait and retry with exponential backoff.
- **Rate limiting:** No `429 Too Many Requests` responses observed in captures. Follow the rate limiting and timing guidelines in `CLAUDE.md` (1-2 second delays between sequential requests, exponential backoff on errors).

## Implementation Pattern

```python
import logging

logger = logging.getLogger(__name__)

def safe_get(session, url: str, **kwargs):
    """Make a GET request with standard error handling."""
    response = session.get(url, **kwargs)

    if response.status_code == 401:
        raise AuthExpiredError("gc-token is expired -- rotate credentials")

    if response.status_code == 403:
        logger.warning("403 Forbidden for %s -- check authorization scope", url)
        return None

    if response.status_code == 404:
        logger.warning("404 Not Found for %s -- resource may not exist", url)
        return None

    if response.status_code == 500:
        body = response.text
        if "page_starts_at" in body or "page_size" in body:
            raise PaginationParamError(
                f"HTTP 500 with pagination error for {url}. "
                "Add ?page_size=50 and x-pagination: true header."
            )
        raise APIError(f"HTTP 500 for {url}: {body}")

    response.raise_for_status()
    return response
```
