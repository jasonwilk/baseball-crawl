---
method: GET
path: /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: >
      5 hits, all HTTP 404. game_stream_id aad088a2-df87-4c0f-b39a-cf42e8c8f24a,
      collection_id 7a9efb48-7855-466f-a14c-6b51ed3ab89e.
      Response Content-Type: text/plain; charset=utf-8. Discovered 2026-03-09.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.none+json; version=undefined"
gc_user_action: null
query_params: []
pagination: unknown
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: null
tags: [games, events, stats]
caveats:
  - >
    HTTP 404 ONLY: All 5 observed requests returned HTTP 404. The route exists in the
    client-side routing (OPTIONS returned 204) but the backend returned no content.
    The stat-edit-collection may be a draft or in-progress scorekeeping feature not
    yet enabled, or the collection_id may need to be created before it can be fetched.
  - >
    ROUTE EXISTS: OPTIONS preflight returns 204, confirming the route is registered
    in the API router. The 404 is a data-not-found response (specific collection does
    not exist), not a route-not-found (which would be a different status or no OPTIONS
    response).
  - >
    UNKNOWN PURPOSE: "game-stat-edit-collection" suggests this endpoint tracks a
    collection of user edits to game statistics (score corrections, stat adjustments,
    or pending scorekeeper changes). May be related to stat correction workflow.
  - >
    collection_id ORIGIN UNKNOWN: The collection_id 7a9efb48-7855-466f-a14c-6b51ed3ab89e
    was sent by the GC web app -- it may have been pre-generated client-side or retrieved
    from another endpoint not captured in this session.
related_schemas: []
see_also:
  - path: /game-streams/{game_stream_id}/events
    reason: Raw event stream for the same game (confirmed working)
  - path: /game-stream-processing/{game_stream_id}/boxscore
    reason: Processed boxscore for the same game
  - path: /game-stream-processing/{game_stream_id}/plays
    reason: Play-by-play log for the same game
---

# GET /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}

**Status:** OBSERVED (proxy log, 5 hits, all HTTP 404). Route is registered but returns 404 for the observed collection_id. Last verified: 2026-03-09.

Appears to retrieve a collection of stat edits (user corrections to recorded statistics) for a specific game stream. The route is active in the API but returned 404 for the specific `collection_id` used by the GC web app in this session.

```
GET https://api.team-manager.gc.com/game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `game_stream_id` | UUID | Game stream UUID (from `game_stream.id` in game-summaries) |
| `collection_id` | UUID | Stat edit collection UUID (origin unknown -- may be client-generated or from another endpoint) |

## Response

HTTP 404 observed. Response Content-Type is `text/plain; charset=utf-8` (plain text error body, not JSON).

## Known Limitations

- All 5 observations returned HTTP 404 -- successful response schema unknown.
- `collection_id` origin unknown. The GC client sent `7a9efb48-7855-466f-a14c-6b51ed3ab89e` -- unclear if this is created by another endpoint or generated client-side.
- The stat-edit-collection concept is not yet understood. May be a scorekeeping correction feature in limited release.
- No data value for ingestion until a 200 OK response is captured.

**Discovered:** 2026-03-09. Session: 2026-03-09_061156. All observations: HTTP 404.
