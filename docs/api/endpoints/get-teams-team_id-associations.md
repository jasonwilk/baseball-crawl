---
method: GET
path: /teams/{team_id}/associations
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: 244-record live capture confirmed 2026-03-04.
  mobile:
    status: observed
    notes: >
      1 hit, HTTP 200. Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6).
accept: "application/vnd.gc.com.team_associations:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/team-associations-sample.json
raw_sample_size: "170+ records (2026-03-07 capture)"
discovered: "2026-03-04"
last_confirmed: "2026-03-07"
tags: [team, user]
related_schemas: []
see_also:
  - path: /teams/{team_id}/users
    reason: User roster with PII (name, email) -- complementary to associations (this endpoint has roles, users has names)
  - path: /teams/{team_id}/relationships
    reason: User-to-player mapping for parent/guardian and self-associations
---

# GET /teams/{team_id}/associations

**Status:** CONFIRMED LIVE -- 200 OK. 244 records returned in single response. Last verified: 2026-03-04.

Returns all user-team membership records for a team. Each record represents one user's role relationship to the team. Useful for finding all managers, players, family members, and fans associated with a team.

```
GET https://api.team-manager.gc.com/teams/{team_id}/associations
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team_associations:list+json; version=0.0.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

No `gc-user-action` observed for this endpoint.

## Response

Bare JSON array of association records. No pagination observed (170+ records returned in a single response in the 2026-03-07 capture; 244 records in the 2026-03-04 capture -- same team at a later date may reflect member churn).

**Distribution observed (2026-03-07 sample):** majority `family` and `fan`, with `manager` and `player` entries present. Association types confirmed from actual data: `manager`, `family`, `fan`, `player`.

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | UUID | Team UUID. Always matches the `{team_id}` path parameter. |
| `user_id` | UUID | GameChanger user UUID. NOT the same as the player UUID returned by `/teams/{team_id}/players`. |
| `association` | string | Role of this user relative to the team. See values below. |

### association Values

| Value | Description |
|-------|-------------|
| `"manager"` | Team manager or coach. Has administrative access. |
| `"player"` | Registered as a player on this team. Low count -- does not represent the full active roster. |
| `"family"` | Family member (parent/guardian) of a player. |
| `"fan"` | Fan or follower without a direct player/family link. |

## Example Response

```json
[
  {
    "team_id": "72bb77d8-REDACTED",
    "user_id": "e07b2d06-REDACTED",
    "association": "manager"
  },
  {
    "team_id": "72bb77d8-REDACTED",
    "user_id": "abc12345-REDACTED",
    "association": "family"
  }
]
```

## Known Limitations

- The `user_id` in this response is a GC user UUID, NOT the player UUID from `/teams/{team_id}/players`. Users and players are distinct entities.
- The `"player"` count (2 of 244) is much lower than the actual active roster. Many roster players may not have a GameChanger account linked.
- No pagination triggered on 244 records. Behavior for very large team communities (2000+ fans) unknown.
- This endpoint has no PII (name, email) -- use `GET /teams/{team_id}/users` for those fields.
- `gc-user-action` was absent from the observed capture -- may not be required.

**Discovered:** 2026-03-04. **Schema confirmed:** 2026-03-04. **Raw sample updated:** 2026-03-07.
