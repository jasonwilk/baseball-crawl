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
| 415 Unsupported Media Type | **An `Accept` header naming the wrong vendor resource type.** Not a broken endpoint and not an auth problem -- check the `Accept` value against the endpoint file before anything else. See 415 on a Mismatched Vendor Accept Type below. |
| 429 Too Many Requests | Rate limited. **Never observed in captures** -- GC's actual 429 behavior is unknown. The shared client applies a defensive handling policy anyway; see 429 Rate-Limit Handling (client policy) below. |
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

## 415 on a Mismatched Vendor Accept Type

_Verified live 2026-07-26 on two public endpoints. See also `content-type.md`._

Sending an `Accept` header that names the **wrong vendor resource type** gets a hard **HTTP 415**. GC does not fall back to a default representation, does not ignore the header, and does not return a partial or alternate body -- the request simply fails.

**Read a 415 as "check the Accept header," never as "this endpoint is broken or gated."** Nothing else in the response distinguishes it, and the failure looks identical to an endpoint that has been removed.

Verified pairs (both no-auth public endpoints):

| Endpoint | Accept sent | Result |
|----------|-------------|--------|
| `GET /public/teams/{public_id}/games` | `application/vnd.gc.com.public_game:list+json; version=0.0.0` (**wrong type**) | **415** |
| `GET /public/teams/{public_id}/games` | `application/vnd.gc.com.public_team_schedule_event:list+json; version=0.0.0` (correct) | 200 |
| `GET /public/teams/{public_id}/games` | `application/json, text/plain, */*` (**generic**) | **200** |
| `GET /public/teams/{public_id}` | `application/vnd.gc.com.public_game:list+json; version=0.0.0` (**wrong type**) | **415** |

The `public_game` value in the first row is a plausible-looking guess, not a real GC type -- which is exactly how this is encountered. The endpoint's real type (`public_team_schedule_event`) is not guessable from the path.

**A wrong type is rejected; a generic or absent one is served.** The 415 fires on a *mismatch*, not on the absence of a vendor type -- a plain `application/json, text/plain, */*` returns a normal 200 with the full body. This has a counterintuitive consequence worth stating plainly: **pinning a vendor Accept type is strictly more brittle than sending a generic one.** A pin can go stale and hard-fail; a generic header cannot. Pins buy server-side version determinism (see the 403 note below), so this is a real trade, not an argument for removing them -- but it does mean every pin is a maintenance obligation.

### 415 vs. the false-403: two different Accept failures

Both symptoms come from the `Accept` header, and they are easy to confuse because neither mentions the header:

| What is wrong with the Accept | Status | Example |
|-------------------------------|--------|---------|
| Wrong **resource type** | **415** | `public_game` where the endpoint wants `public_team_schedule_event` |
| Stale **version** on the right type | **403** | `GET /me/teams` with a version older than `0.10.0` |

The 403 form is the documented false-403 trap (see `.claude/rules/auth-module.md`) and reads as credential expiry during debugging. When either status appears unexpectedly on a request that should succeed, check the `Accept` value against the endpoint file before touching credentials.

**Scope of this verification.** Confirmed on the two **public, no-auth** endpoints listed above. Not probed on authenticated endpoints -- do not assume the same 415-vs-403 split holds there without testing. The `/me/teams` 403 case above is prior evidence that the authenticated surface can answer an Accept problem with a *different* status.

## 403 on Away-Game Lineups

`GET /bats-starting-lineups/{event_id}` returns HTTP 403 when the `event_id` refers to an away game where the authenticated user's team was not the primary scorer. Use home game event_ids, or events where the user's team managed scoring.

## 429 Rate-Limit Handling (client policy)

_Source: E-252-04. Last updated: 2026-07-06._

**We have still never observed a `429 Too Many Requests` from the GC API in any capture** -- GC's real rate-limit behavior (thresholds, whether it even sends `Retry-After`, and in what units) remains unknown. The policy below is OUR defensive handling in the shared client (`src/gamechanger/client.py`, `_send_with_retries`), designed against that unobserved behavior so an unexpected 429 during a scheduled/cron run cannot hang the process indefinitely. It is not tuned to a measured value.

On HTTP 429 the client:

1. **Reads `Retry-After`.** The header value is parsed as integer delay-seconds (RFC 7231 §7.1.3). If the header is absent or unparseable, it falls back to `_DEFAULT_RETRY_AFTER_SECONDS = 60`.
2. **Clamps against a hard cap** `_MAX_RETRY_AFTER_SECONDS = 60`:
   - **Within cap (`Retry-After <= 60`):** sleep the value, then retry the request **once** inline (not a loop). Return the response on 200; otherwise raise `RateLimitError`.
   - **Over cap (`Retry-After > 60`):** raise `RateLimitError` **immediately, without sleeping** -- a server-dictated `Retry-After: 3600` must never stall the cron for an hour.

Because the default fallback (60s) equals the cap (60s), a header-less 429 always takes the within-cap path (sleep 60s, retry once).

> **Revisit if a real 429 is ever captured.** The 60s cap and the retry-once policy are placeholders against unknown behavior. Once GC's actual 429 semantics are observed (via mitmproxy captures in `proxy/data/`), re-tune the cap, the fallback, and the retry count to match, and update this section with the observed behavior.

## Retry Behavior

- **401 Unauthorized:** Do not retry. The token is expired. Rotate credentials via the browser capture workflow (`bb creds import`) and restart the session.
- **400 Bad Request:** Do not retry with the same request. Diagnose the malformed parameter or header.
- **415 Unsupported Media Type:** Do not retry -- it is fully deterministic in the request. Fix the `Accept` value against the endpoint file. The shared client already treats it as non-retryable, but classifies it as a `GameChangerAPIError`, which downstream callers report as a *transient* failure; see 415 on a Mismatched Vendor Accept Type above.
- **500 Internal Server Error:** Check if pagination parameters are missing. If it is a one-off 500 (not a pagination issue), wait and retry with exponential backoff.
- **Rate limiting (429):** No `429 Too Many Requests` responses observed in captures. The shared client nonetheless applies a defensive policy (60s `Retry-After` cap, within-cap-retry-once, over-cap-raise-immediately, header-fallback-then-clamp) -- see 429 Rate-Limit Handling (client policy) above. Follow the rate limiting and timing guidelines in `CLAUDE.md` (1-2 second delays between sequential requests, exponential backoff on errors) to avoid triggering rate limits in the first place.

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
