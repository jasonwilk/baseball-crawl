---
method: PATCH
path: /teams/{team_id}/opponent/{opponent_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 2 hits, both HTTP 200.
      Content-Type: application/vnd.gc.com.patch_opponent_team+json; version=0.0.0.
      Response content-type: text/plain (empty body or status message).
      Both calls occurred ~5 seconds before POST /opponent/import, suggesting this
      PATCH fires when the user modifies opponent visibility/name before confirming import.
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
    WRITE OPERATION: Updates properties of an existing opponent record. The two
    observed calls both hit opponent bd05f3d5-1dfb-47c1-8e81-93c0660eaaef (which
    is different from db210ea3, the opponent used in POST /opponent/import).
    This suggests bd05f3d5 was an already-existing opponent that the user modified.
  - >
    REQUEST BODY UNKNOWN: Body schema not captured (proxy logs metadata only). Based
    on the vendor content-type (patch_opponent_team) and the GET schema in
    /teams/{team_id}/opponent/{opponent_id}, likely patchable fields are: name
    (custom display name), is_hidden (soft-delete/hide from list).
  - >
    RESPONSE IS TEXT/PLAIN: The response content-type is text/plain, suggesting the
    body is either empty or a simple status string (e.g., "OK"), not a JSON object.
    HTTP 200 confirmed.
  - >
    TIMING CONTEXT: Both PATCH calls at 06:28:52 and 06:28:57 preceded the
    POST /opponent/import at 06:30:07. Between them, GET /opponent/bd05f3d5 was
    fetched at 06:28:59 to confirm the update. This suggests a rename/visibility
    toggle was applied to an existing opponent record.
see_also:
  - path: /teams/{team_id}/opponent/{opponent_id}
    reason: GET for the opponent record -- shows the current field values
  - path: /teams/{team_id}/opponents
    reason: Paginated list of all opponent records
  - path: /post-teams-team_id-opponent-import
    reason: POST to create a new opponent association
---

# PATCH /teams/{team_id}/opponent/{opponent_id}

**Status:** CONFIRMED (mobile proxy, 2 hits, HTTP 200). Request/response bodies not captured. Last verified: 2026-03-09.

Updates properties of an existing opponent record. Observed when the user modifies an opponent (likely toggling visibility or updating a custom name) in the iOS app.

```
PATCH https://api.team-manager.gc.com/teams/{team_id}/opponent/{opponent_id}
Content-Type: application/vnd.gc.com.patch_opponent_team+json; version=0.0.0
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Your team's UUID |
| `opponent_id` | UUID | The opponent's root_team_id (UUID of the opponent team) |

## Request Headers (Mobile Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.patch_opponent_team+json; version=0.0.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
gc-app-version: 2026.8.0.0
Accept-Language: en-US;q=1.0
Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8
x-gc-features: lazy-sync
```

## Request Body

Body schema not captured. Based on the GET schema for `/teams/{team_id}/opponent/{opponent_id}`, the expected patchable fields are:

```json
{
  "name": "Custom Opponent Display Name",
  "is_hidden": false
}
```

All fields are optional in a PATCH -- only include fields being changed.

## Response

**HTTP 200.** Response content-type is `text/plain` -- the body is either empty or a simple status string, not JSON.

## Known Limitations

- Request body schema unverified -- capture needed.
- `is_hidden` field behavior: when set to `true`, the opponent is likely hidden from the default opponents list but still accessible by UUID.

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
