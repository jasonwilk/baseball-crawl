---
method: GET
path: /me/permissions/bulk
status: OBSERVED
auth: required
profiles:
  web:
    status: unverified
    notes: Not captured from web profile.
  mobile:
    status: observed
    notes: 4 hits, status 200 and 304. Discovered 2026-03-05.
accept: null
gc_user_action: null
query_params:
  - name: childType
    type: string
    required: unknown
    description: Type of child entities to check permissions for.
  - name: parentId
    type: string
    required: unknown
    description: UUID of the parent entity.
  - name: parentType
    type: string
    required: unknown
    description: Type of the parent entity (e.g., "team", "organization").
  - name: permissions
    type: string
    required: unknown
    description: Comma-separated list of permissions to check.
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-05"
last_confirmed: null
tags: [me, permissions]
caveats:
  - >
    NOT RELEVANT FOR DATA INGESTION: Bulk permission check used by the app UI to
    determine what features to show the user. Not needed for analytics pipelines.
related_schemas: []
see_also:
  - path: /me/permissions
    reason: Single-entity permission check (confirmed, 18 permissions documented)
---

# GET /me/permissions/bulk

**Status:** OBSERVED (proxy log, 4 hits, status 200 and 304). Schema not captured.

Bulk permission check endpoint. Checks permissions for a class of child entities under a parent entity (e.g., all events under a team). Used by the app to determine feature visibility.

```
GET https://api.team-manager.gc.com/me/permissions/bulk
```

## Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `childType` | string | Type of child entities to check |
| `parentId` | UUID | Parent entity UUID |
| `parentType` | string | Parent entity type (e.g., `"team"`) |
| `permissions` | string | Permissions to check (format unknown) |

## Response

Schema not captured. Status 200 and 304 observed.

**Discovered:** 2026-03-05.
