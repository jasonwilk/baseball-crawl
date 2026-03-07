---
method: GET
path: /me/permissions/bulk
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200 with plain text "No permissions provided" response when called without query params. Captured 2026-03-07.
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
response_shape: string
response_sample: data/raw/me-permissions-bulk-sample.json
raw_sample_size: "plain text: 'No permissions provided'"
discovered: "2026-03-05"
last_confirmed: "2026-03-07"
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

When called without query parameters, returns plain text (not JSON):

```
No permissions provided
```

This suggests the endpoint expects specific query parameters to return meaningful permission data. The 200 status with this message is consistent with the endpoint being functional but requiring `childType`, `parentId`, `parentType`, and `permissions` query parameters to return a real permission result.

**Response content-type when no params provided:** plain text (not JSON).

**Discovered:** 2026-03-05. **No-param response confirmed:** 2026-03-07.
