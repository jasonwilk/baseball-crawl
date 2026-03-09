---
method: POST
path: /teams/{team_id}/schedule/events
status: CONFIRMED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile. Expected to work (same endpoint pattern).
  mobile:
    status: confirmed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 1 hit, HTTP 201.
      Content-Type: application/vnd.gc.com.post_event+json; version=0.3.0.
      Fired when user added a new game. Event_id ba140306-34a7-43a9-833c-eecb4353628d
      appears to be the newly-created event (subsequent calls to that event_id followed).
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
    WRITE OPERATION: Creates a new scheduled event (game, practice, or other event).
    This fires when the user taps "Add Game" in the iOS app. The event_id for the
    newly-created event (ba140306-34a7-43a9-833c-eecb4353628d) appeared in
    subsequent GET and PATCH calls within seconds.
  - >
    REQUEST BODY UNKNOWN: Body schema not captured (proxy logs metadata only).
    Based on the vendor content-type (post_event) and the fields seen in the GET
    /teams/{team_id}/schedule response, expected fields include: event_type (game/
    practice/other), scheduled_time (ISO-8601), opponent_id (UUID), location,
    is_home (boolean), title.
  - >
    RESPONSE BODY UNKNOWN: HTTP 201 Created. Response body likely contains the full
    newly-created event object (same schema as events in GET /teams/{team_id}/schedule).
    The returned event_id is immediately used in subsequent API calls.
  - >
    COMPANION PATCH: After creation, `PATCH /teams/{team_id}/schedule/events/{event_id}`
    was called at 06:30:16 (8 seconds after the POST at 06:30:07), suggesting the
    app does a create-then-immediately-update pattern (e.g., creates with minimal
    fields, then patches with additional details like opponent assignment).
see_also:
  - path: /teams/{team_id}/schedule
    reason: GET all scheduled events for the team (includes newly-created event)
  - path: /patch-teams-team_id-schedule-events-event_id
    reason: PATCH to update a created event (observed immediately after this POST)
  - path: /teams/{team_id}/schedule/events/{event_id}/rsvp-responses
    reason: RSVP tracking for the created event
  - path: /events/{event_id}
    reason: Individual event detail endpoint (includes pregame_data and lineup_id)
---

# POST /teams/{team_id}/schedule/events

**Status:** CONFIRMED (mobile proxy, 1 hit, HTTP 201). Request/response bodies not captured. Last verified: 2026-03-09.

Creates a new scheduled event (game, practice, or other) for a team. Fired when the user adds a game in the iOS app.

```
POST https://api.team-manager.gc.com/teams/{team_id}/schedule/events
Content-Type: application/vnd.gc.com.post_event+json; version=0.3.0
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Your team's UUID |

## Request Headers (Mobile Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Content-Type: application/vnd.gc.com.post_event+json; version=0.3.0
User-Agent: Odyssey/2026.8.0 (com.gc.teammanager; build:0; iOS 26.3.0) Alamofire/5.9.0
gc-app-version: 2026.8.0.0
Accept-Language: en-US;q=1.0
Accept-Encoding: br;q=1.0, gzip;q=0.9, deflate;q=0.8
x-gc-features: lazy-sync
```

## Request Body

Body schema not captured. Based on the GET /teams/{team_id}/schedule event schema, expected fields:

```json
{
  "event_type": "game",
  "scheduled_time": "2025-05-15T18:00:00Z",
  "title": "vs. Lincoln 9U",
  "opponent_id": "{opponent_team_uuid}",
  "is_home": true,
  "location": {
    "name": "Field Name",
    "address": "..."
  }
}
```

All fields may not be required -- the observed create-then-patch pattern suggests a minimal initial creation body.

## Response

**HTTP 201 Created.** Response body likely contains the full event object, including the newly-assigned `event_id` UUID that the caller uses for subsequent operations.

## Observed Flow (Create Game Sequence)

At 06:30:07 in the session, the following happened simultaneously with POST /opponent/import:
1. `POST /teams/{team_id}/opponent/import` -- add the opponent
2. `GET /teams/{opponent_id}/players` -- fetch opponent roster
3. `GET /teams/{team_id}/schedule/events/{old_event_id}/rsvp-responses` -- (background refresh)
4. `POST /teams/{team_id}/schedule/events` -- **(this endpoint)** create the new game

Then at 06:30:13 (6 seconds later):
5. `GET /events/{new_event_id}` -- fetch the new event details
6. `GET /player-attributes/{player_id}/bats` (×11) -- fetch all player handedness for the lineup
7. `GET /teams/{opponent_id}/players` -- re-fetch opponent roster (cached)

Then at 06:30:16:
8. `PATCH /teams/{team_id}/schedule/events/{new_event_id}` -- update the new event (likely sets opponent)

**Discovered:** 2026-03-09. Session: 2026-03-09_062610 (mobile/iOS).
