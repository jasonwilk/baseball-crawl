---
method: POST
path: /sync-topics/updates
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: observed
    notes: 11 hits, status 200. Discovered 2026-03-05.
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
    NOT RELEVANT FOR DATA INGESTION: This is a write endpoint used by the app to push
    state updates. Response schema not captured. Not useful for analytics pipelines.
related_schemas: []
see_also:
  - path: /sync-topics/me/updated-topics
    reason: Read side of the sync topic system (polling for updates)
  - path: /sync-topics/topic-subscriptions
    reason: Subscribe to a sync topic
---

# POST /sync-topics/updates

**Status:** OBSERVED (proxy log, 11 hits, status 200). Last observed: 2026-03-05.

Batch sync update push endpoint. Used by the iOS app to push state updates to the sync system. Not relevant to data ingestion.

```
POST https://api.team-manager.gc.com/sync-topics/updates
```

## Request

| Header | Value |
|--------|-------|
| `Content-Type` | `application/vnd.gc.com.post_batch_scoped_sync_updates+json; version=0.0.0` |

## Response

Response schema not captured. Status 200 observed.

**Discovered:** 2026-03-05.
