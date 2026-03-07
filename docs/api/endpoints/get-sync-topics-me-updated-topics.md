---
method: GET
path: /sync-topics/me/updated-topics
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Previously observed with status field only. Confirmed 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params:
  - name: cursor
    type: string
    required: false
    description: Pagination cursor for polling for updates. Use `next_cursor` from previous response.
  - name: timeout
    type: integer
    required: false
    description: Long-poll timeout in seconds.
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
tags: [sync, user]
caveats:
  - >
    PII IN CURSOR: The `next_cursor` field encodes the authenticated user's UUID in its
    value (format: `v2_{sequence}_{timestamp}_{user_id}_{counter}_{uuid}`). Do not log
    or store the raw cursor value in plaintext logs.
related_schemas: []
see_also: []
---

# GET /sync-topics/me/updated-topics

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the current sync state and any pending topic updates for the authenticated user. Used for real-time change notification polling.

```
GET https://api.team-manager.gc.com/sync-topics/me/updated-topics
```

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cursor` | string | No | Cursor from previous response to poll for changes since that point |
| `timeout` | integer | No | Long-poll timeout in seconds |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Sync status. Observed: `"update-all"` |
| `updates` | array | Array of pending topic updates. Empty array observed. |
| `next_cursor` | string | Opaque cursor for the next poll. Contains user UUID -- do not log. |

## Example Response

```json
{
  "status": "update-all",
  "updates": [],
  "next_cursor": "v2_..."
}
```

**Discovered:** 2026-03-05. **Confirmed:** 2026-03-07.
