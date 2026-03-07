---
method: GET
path: /me/permissions
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Previously returned HTTP 501 without required params. CONFIRMED 2026-03-07 with
      ?entityId={uuid}&entityType=team. Full schema documented.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params:
  - name: entityId
    required: true
    description: UUID of the entity to check permissions for. Server returns HTTP 501 without this.
  - name: entityType
    required: true
    description: Type of entity. Observed value -- "team". Server returns HTTP 501 without this.
pagination: false
response_shape: object
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [me, permissions]
caveats:
  - >
    REQUIRED PARAMS: Must include ?entityId={team_uuid}&entityType=team. Server returns
    HTTP 501 "Not Implemented" without these parameters.
related_schemas: []
see_also:
  - path: /me/teams
    reason: Team list -- source of team UUIDs for entityId parameter
---

# GET /me/permissions

**Status:** CONFIRMED LIVE -- 200 OK. Previously HTTP 501 without required params. Last verified: 2026-03-07.

Returns the authenticated user's permissions for a specific entity. Requires `?entityId={uuid}&entityType=team` query parameters.

**Coaching relevance: LOW for data ingestion.** Useful for understanding what access a given token has before attempting data pulls.

```
GET https://api.team-manager.gc.com/me/permissions?entityId={team_uuid}&entityType=team
```

## Required Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `entityId` | UUID | UUID of the entity to check permissions for |
| `entityType` | string | Type of entity. Observed: `"team"` |

## Response

| Field | Type | Description |
|-------|------|-------------|
| `results` | array | Array of permission result objects |
| `results[].permissions` | array of strings | List of permission strings granted to the user |
| `results[].entity` | object | The entity this permission applies to |
| `results[].entity.type` | string | Entity type (e.g., `"team"`) |
| `results[].entity.id` | UUID | Entity UUID |

### Observed Permission Values (full admin access)

`can_view_team_details`, `can_view_team_relationships`, `can_manage_team`, `can_view_video`, `can_view_team_announcements`, `can_manage_lineup`, `can_invite_fans`, `can_manage_opponent`, `can_manage_player`, `can_view_stats`, `can_view_team_schedule`, `can_view_lineup`, `can_receive_player_alerts`, `can_manage_event_video`, `can_view_event_rsvps`, `can_manage_messaging`, `can_purchase_team_pass`, `can_manage_game_scorekeeping`

## Example Response

```json
{
  "results": [
    {
      "permissions": ["can_view_team_details", "can_manage_team", "can_view_stats"],
      "entity": {
        "type": "team",
        "id": "72bb77d8-REDACTED"
      }
    }
  ]
}
```

**Discovered:** 2026-03-07. **Confirmed with required params:** 2026-03-07.
