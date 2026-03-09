---
method: PATCH
path: /teams/{team_id}/schedule/events/{event_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile. Expected to work (same endpoint pattern).
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 1 hit, HTTP 200.
      Content-Type: application/vnd.gc.com.patch_event+json; version=0.6.0.
      Response content-type: application/json. Fired 8 seconds after POST /schedule/events
      created a new game -- the create-then-patch pattern is the iOS app's way of
      incrementally building an event.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-09"
last_confirmed: "2026-03-09"
tags: [schedule, games, write]
caveats:
  - >
    WRITE OPERATION: Updates properties of an existing scheduled event. Observed
    pattern: iOS app creates a minimal event with POST, then patches it with full
    details (opponent, location, etc.) in a second call.
  - >
    REQUEST BODY UNKNOWN: Body schema not captured (proxy logs metadata only).
    Based on the vendor content-type (patch_event) version 0.6.0, patchable fields
    likely include: title, scheduled_time, opponent_id, is_home, location,
    event_notes, cancellation_reason.
  - >
    RESPONSE IS JSON: Unlike PATCH /opponent which returns text/plain, this endpoint
    returns application/json -- likely the full updated event object.
  - >
    VERSION NOTE: Content-Type version is 0.6.0 (higher than the POST's 0.3.0),
    suggesting the PATCH schema has evolved to support more fields.
see_also:
  - path: /teams/{team_id}/schedule
    reason: GET all events (reflects updates)
  - path: /events/{event_id}
    reason: Individual event detail with pregame_data
  - path: /post-teams-team_id-schedule-events
    reason: POST to create a new event (creates before PATCH updates)
---

# PATCH /teams/{team_id}/schedule/events/{event_id}

**Status:** CONFIRMED (mobile proxy, 1 hit, HTTP 200). Request/response bodies not captured. Last verified: 2026-03-09.

Updates properties of an existing scheduled event. In the iOS app, this is called immediately after `POST /schedule/events` to complete event setup (create-then-patch pattern). Also called when a user edits an existing game.

```
PATCH https://api.team-manager.gc.com/teams/{team_id}/schedule/events/{event_id}
Content-Type: application/vnd.gc.com.patch_event+json; version=0.6.0
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Your team's UUID |
| `event_id` | UUID | The event UUID to update |

## Request Headers (Mobile Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.patch_event+json; version=0.6.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
gc-app-version: 2026.8.0.0
Accept-Language: en-US;q=1.0
Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8
x-gc-features: lazy-sync
```

## Request Body

Body schema not captured. Based on event fields from `GET /teams/{team_id}/schedule`, expected patchable fields:

```json
{
  "opponent_id": "{opponent_team_uuid}",
  "title": "vs. Lincoln 9U",
  "scheduled_time": "2025-05-15T18:00:00Z",
  "is_home": true,
  "location": {
    "name": "Field Name",
    "address": "..."
  },
  "event_notes": "..."
}
```

All fields are optional in a PATCH -- include only fields being changed.

## Response

**HTTP 200.** Response content-type `application/json` -- likely returns the full updated event object.

## Known Limitations

- Request body schema unverified.
- Response body not captured -- schema unknown.
- The event "delete game" user action is likely a DELETE method on this same path, not a PATCH -- not yet observed.

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
