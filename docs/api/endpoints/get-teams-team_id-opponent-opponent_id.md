---
method: GET
path: /teams/{team_id}/opponent/{opponent_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Discovered 2026-03-07.
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
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [team, opponent]
caveats:
  - >
    URL STRUCTURE: Uses /opponent/ (singular), not /opponents/ (plural). The singular
    form returns a specific opponent; the plural form (/opponents) returns the paginated list.
  - >
    opponent_id IS root_team_id: The path parameter opponent_id must be the root_team_id
    from GET /teams/{team_id}/opponents -- NOT the progenitor_team_id.
  - >
    ID USAGE HIERARCHY (confirmed 2026-03-09): root_team_id is for /opponent/{id},
    /players, and /avatar-image. progenitor_team_id is for GET /teams/{id} (metadata).
    public_id (from GET /teams/{progenitor_team_id} response) is for public endpoints.
    See GET /teams/{team_id} for the full ID hierarchy table.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents
    reason: Paginated list of all opponents. Source of root_team_id and progenitor_team_id values.
---

# GET /teams/{team_id}/opponent/{opponent_id}

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-03-07.

Returns the opponent entry record for a specific opponent within a team's opponent registry. This is the per-opponent lookup complement to `GET /teams/{team_id}/opponents` (the paginated list).

**URL structure:** Uses `/opponent/` (singular), not `/opponents/` (plural).

```
GET https://api.team-manager.gc.com/teams/{team_id}/opponent/{opponent_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | The owning team's UUID |
| `opponent_id` | UUID | The opponent's `root_team_id` from `GET /teams/{team_id}/opponents`. **NOT the `progenitor_team_id`.** |

## Response

Single JSON object (not an array). Same 5-field schema as individual records from the opponents list.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | UUID | The local opponent registry ID (matches the `opponent_id` path parameter) |
| `owning_team_id` | UUID | UUID of the requesting team |
| `name` | string | Opponent display name |
| `is_hidden` | boolean | Whether hidden from UI |
| `progenitor_team_id` | UUID | Canonical GC team UUID -- use this for `/teams/{id}`, `/season-stats`, `/players`, etc. |

## Example Response

```json
{
  "root_team_id": "6e898958-c6e3-48c7-a97e-e281a35cfc50",
  "owning_team_id": "72bb77d8-REDACTED",
  "name": "Blackhawks 14U",
  "is_hidden": false,
  "progenitor_team_id": "f0e73e42-f248-402b-8171-524b4e56a535"
}
```

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
