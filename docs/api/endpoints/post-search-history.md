---
method: POST
path: /search/history
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: confirmed
    notes: >
      1 hit, HTTP 200. Called immediately after user selects a team from search results,
      before navigating to the team page. Confirmed 2026-03-09.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: null
tags: [search, user, write]
caveats:
  - >
    SCHEMA UNKNOWN: Request body and response body not captured by proxy -- only
    the content-type metadata is available. Body schema requires live curl to determine.
  - >
    WRITE OPERATION: This endpoint records a search history entry (user selected a result).
    It is called AFTER the user taps a search result, before navigating to the team page.
    Not called on every search query -- only on result selection.
see_also:
  - path: /search/history
    reason: GET counterpart -- reads the search history list
  - path: /search
    reason: POST /search is the search-as-you-type endpoint that fires before this
---

# POST /search/history

**Status:** CONFIRMED (observed 1 hit, HTTP 200). Request/response body schema unknown.

Records a user's team selection into their search history. Called by the iOS app immediately after the user taps a search result, before navigating to the selected team's page.

```
POST https://api.team-manager.gc.com/search/history
Content-Type: application/vnd.gc.com.add_search_history+json; version=0.0.0
```

## Request Body

Body schema unknown -- not captured by proxy.

Content-Type: `application/vnd.gc.com.add_search_history+json; version=0.0.0`

Expected to contain the team identifier (UUID or public_id) and possibly the search query term or result type.

## Response

Response Content-Type: `text/plain; charset=utf-8`

HTTP 200. Body likely minimal (empty or confirmation string) given the `text/plain` response content-type.

## Navigation Flow (Mobile)

This endpoint fires at the transition point between searching and navigating:

1. User taps a result in `POST /search` results
2. `POST /search/history` fires (record the selection)
3. `GET /teams/{progenitor_team_id}` fires (navigate to team page)

The search history is later retrieved via `GET /search/history` when the user returns to the search screen.

## Known Limitations

- Body and response schema not captured -- live curl needed.
- Whether the body contains team UUID, public_id, or both is unknown.

**Discovered:** 2026-03-09.
