---
method: GET
path: /announcements/user/read-status
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. Schema documented. Previously observed with 304 only. Confirmed 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [user, auth]
caveats: []
related_schemas: []
see_also: []
---

# GET /announcements/user/read-status

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the read status of in-app announcements for the authenticated user.

```
GET https://api.team-manager.gc.com/announcements/user/read-status
```

## Response

| Field | Type | Description |
|-------|------|-------------|
| `read_status` | string | `"read"` if all announcements have been read, `"unread"` otherwise |

## Example Response

```json
{"read_status": "read"}
```

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
