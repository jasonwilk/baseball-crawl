---
method: GET
path: /teams/{team_id}/schedule/events/{event_id}/rsvp-responses
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Returns empty array []. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [games, events]
caveats: []
related_schemas: []
see_also:
  - path: /me/schedule
    reason: Unified schedule includes inline RSVP data per event
---

# GET /teams/{team_id}/schedule/events/{event_id}/rsvp-responses

**Status:** CONFIRMED LIVE -- 200 OK (empty array). Last verified: 2026-03-07.

Returns RSVP responses for a scheduled event. **Coaching relevance: NONE.** Attendance tracking, not performance data.

```
GET https://api.team-manager.gc.com/teams/{team_id}/schedule/events/{event_id}/rsvp-responses
```

## Response

`[]` (empty array observed). Full schema unknown when records are present.

**Discovered:** 2026-03-05. **Confirmed (empty):** 2026-03-07.
