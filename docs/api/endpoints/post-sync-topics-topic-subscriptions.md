---
method: POST
path: /sync-topics/topic-subscriptions
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: observed
    notes: 1 hit, status 201. Discovered 2026-03-05.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [sync, user]
caveats:
  - >
    NOT RELEVANT FOR DATA INGESTION: Part of the app's real-time notification
    infrastructure. Request body not captured. Response schema unknown.
related_schemas: []
see_also:
  - path: /sync-topics/me/updated-topics
    reason: Polling endpoint for receiving sync updates
  - path: /sync-topics/updates
    reason: Batch update push endpoint
---

# POST /sync-topics/topic-subscriptions

**Status:** OBSERVED (proxy log, 1 hit, status 201). Last observed: 2026-03-05.

Subscribe to a sync topic for real-time notifications. Part of the app's real-time notification infrastructure. Not relevant to data ingestion.

```
POST https://api.team-manager.gc.com/sync-topics/topic-subscriptions
```

## Response

Returns HTTP 201 Created. Response body schema not captured.

**Discovered:** 2026-03-05.
