---
method: POST
path: /teams/{team_id}/opponent/import
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). User tapped "Add Opponent"
      and selected an opponent found via /search/opponent-import. HTTP 201 observed.
      Content-Type: application/vnd.gc.com.post_opponent_team_import+json; version=0.0.0.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-09"
tags: [team, opponent, write]
caveats:
  - >
    WRITE OPERATION: Creates an opponent association. This endpoint fires when the user
    selects a team from /search/opponent-import results and confirms the import. The
    opponent_id in the POST body is the team UUID of the team being added as an opponent.
  - >
    REQUEST BODY UNKNOWN: Body schema not captured (proxy logs metadata only). Based on
    the vendor content-type (post_opponent_team_import) and the flow observed, the body
    almost certainly contains the opponent team's UUID (e.g., {"team_id": "...uuid..."}).
    After the POST, GET /teams/{team_id}/opponent/{opponent_id} was called immediately
    to fetch the newly-created opponent record.
  - >
    RESPONSE BODY UNKNOWN: Response body not captured. HTTP 201 Created suggests the
    body contains the newly-created opponent record (root_team_id, owning_team_id, name,
    is_hidden, progenitor_team_id) -- matching the schema documented in GET /teams/{team_id}/opponent/{opponent_id}.
  - >
    OBSERVED FLOW: /search/opponent-import (3x search-as-you-type) -> /teams/{id}/import-summary
    (check if source team has data) -> POST /opponent/import (creates association) ->
    GET /opponent/{opponent_id} (fetches result). The import-summary call preceding this
    endpoint suggests GC checks whether the source team has stats available before offering
    the import option.
see_also:
  - path: /search/opponent-import
    reason: Search endpoint used to find the opponent team UUID before calling this endpoint
  - path: /teams/{team_id}/opponent/{opponent_id}
    reason: GET for the resulting opponent record after import (called immediately after this POST)
  - path: /teams/{team_id}/opponents
    reason: Full paginated opponent registry (reflects new opponent after import)
  - path: /teams/{team_id}/import-summary
    reason: Called before this endpoint to check if the source team has importable stats
  - path: /patch-teams-team_id-opponent-opponent_id
    reason: PATCH endpoint to update opponent settings after creation
---

# POST /teams/{team_id}/opponent/import

**Status:** CONFIRMED (mobile proxy, 1 hit, HTTP 201). Request/response bodies not captured. Last verified: 2026-03-09.

Creates an opponent association for a team by importing a team from the GameChanger team database. This is the write side of the opponent import flow -- the user searches for an opponent via `/search/opponent-import`, selects a result, and the app fires this endpoint to create the association.

```
POST https://api.team-manager.gc.com/teams/{team_id}/opponent/import
Content-Type: application/vnd.gc.com.post_opponent_team_import+json; version=0.0.0
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Your team's UUID (the team you're adding an opponent to) |

## Request Headers (Mobile Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.post_opponent_team_import+json; version=0.0.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
gc-app-version: 2026.8.0.0
Accept-Language: en-US;q=1.0
Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8
x-gc-features: lazy-sync
```

## Request Body

Body schema not captured (proxy logs metadata only). Based on the vendor content-type `post_opponent_team_import` and the flow observed, the expected body is:

```json
{
  "team_id": "{opponent_team_uuid}"
}
```

Where `opponent_team_uuid` is the UUID returned by `/search/opponent-import`.

## Response

**HTTP 201 Created.** Body not captured. Based on subsequent `GET /teams/{team_id}/opponent/{opponent_id}` call in the same session, the response likely contains the newly-created opponent record:

```json
{
  "root_team_id": "{opponent_team_uuid}",
  "owning_team_id": "{your_team_uuid}",
  "name": "Opponent Team Name",
  "is_hidden": false,
  "progenitor_team_id": "{original_team_uuid}"
}
```

## Observed Flow (Complete Opponent Import Sequence)

1. `GET /search/opponent-import?name=...` (repeated as user types) -- find the opponent team
2. `GET /teams/{opponent_uuid}/import-summary` -- check if opponent team has importable stats
3. `POST /teams/{my_team_id}/opponent/import` -- **(this endpoint)** create the association
4. `GET /teams/{my_team_id}/opponent/{opponent_id}` -- fetch the newly-created opponent record

After step 4, the app fetches `GET /teams/{opponent_id}/players` and multiple `GET /player-attributes/{player_id}/bats` calls to populate the opponent roster and handedness data.

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
