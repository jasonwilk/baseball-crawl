---
method: GET
path: /me/schedule
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. 71 events across 26 teams. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.all_events_schedule+json; version=0.2.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "71 events across 26 teams"
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [me, events, schedule]
caveats:
  - >
    SHORT CACHE TTL: expire_in_seconds: 30 observed. This endpoint reflects near-real-time
    event status.
related_schemas: []
see_also:
  - path: /teams/{team_id}/schedule
    reason: Team-scoped schedule with full event detail including location objects
---

# GET /me/schedule

**Status:** CONFIRMED LIVE -- 200 OK. 71 events across 26 teams. Last verified: 2026-03-07.

Returns a unified cross-team schedule for all teams the authenticated user belongs to. Single call returns upcoming and recent events across all active teams.

**Coaching relevance: HIGH.** Single call gives the full schedule picture across all teams, with RSVP status and video availability inline.

```
GET https://api.team-manager.gc.com/me/schedule
```

## Response

Single JSON object with 5 top-level keys.

| Field | Type | Description |
|-------|------|-------------|
| `teams` | object | Map of team UUIDs to team metadata. 26 teams observed. |
| `teams.<uuid>.name` | string | Team display name |
| `teams.<uuid>.sport` | string | Sport (present for newer teams) |
| `teams.<uuid>.createdAt` | string (ISO 8601) | Team creation date (present for newer teams) |
| `organizations` | object | Map of organization UUIDs to org metadata (empty `{}` in capture) |
| `config` | object | Schedule query configuration |
| `config.max_teams` | integer | Max teams returned (observed: `150`) |
| `config.max_future_days` | integer | Days ahead events are returned (observed: `180`) |
| `config.max_past_days` | integer | Days back events are returned (observed: `90`) |
| `expire_in_seconds` | integer | Cache TTL for this response (observed: `30`) |
| `events` | array | Flat array of upcoming/recent events across all teams. 71 events observed. |

### Event Item Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Event UUID |
| `team_id` | UUID | Which team this event belongs to |
| `kind` | string | Event type: `"game"`, `"practice"`, etc. |
| `notes` | string | Coach notes for this event |
| `is_all_day` | boolean | Whether the event spans the full day |
| `start_time` | string (ISO 8601) | Event start in UTC |
| `end_time` | string (ISO 8601) | Event end in UTC |
| `arrive_by_time` | string (ISO 8601) | Requested arrival time in UTC |
| `timezone` | string | IANA timezone |
| `opponent_id` | UUID or null | Opponent team UUID (for games) |
| `is_home_game` | boolean | Whether this is a home game |
| `location_name` | string | Venue name |
| `rsvps` | array | RSVP responses embedded inline |
| `rsvps[].attending_status` | string | `"going"`, `"not_going"`, `"maybe"` |
| `rsvps[].attendee_user_id` | UUID | User or player UUID who RSVPed |
| `rsvps[].attending_id_type` | string | `"user"` or `"player"` |
| `video` | object | Video availability summary |
| `video.is_live` | boolean | Whether stream is currently live |
| `video.has_videos` | boolean | Whether recorded videos exist |
| `video.is_test_stream` | boolean | Whether this was a test stream |

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
