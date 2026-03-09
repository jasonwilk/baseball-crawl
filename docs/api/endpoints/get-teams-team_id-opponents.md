---
method: GET
path: /teams/{team_id}/opponents
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: 70 records across 2 pages confirmed 2026-03-04.
  mobile:
    status: observed
    notes: >
      2 hits, HTTP 200. Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6) -- confirms the endpoint works for opponent teams.
accept: "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
gc_user_action: "data_loading:opponents"
query_params:
  - name: start_at
    required: false
    description: Pagination cursor. Use the full URL from x-next-page response header.
pagination: true
response_shape: array
response_sample: data/raw/opponents-sample.json
raw_sample_size: "70 records across 2 pages combined, 17 KB"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, opponent]
caveats:
  - >
    Three UUID fields with DIFFERENT semantics -- CRITICAL: root_team_id is the local
    registry key. owning_team_id always equals the path team_id (informational only).
    progenitor_team_id is the CANONICAL GC team UUID.
  - >
    ID USAGE BY ENDPOINT (confirmed 2026-03-09):
    root_team_id: use with GET /teams/{team_id}/opponent/{id},
    GET /teams/{root_team_id}/players, GET /teams/{root_team_id}/avatar-image.
    progenitor_team_id: use with GET /teams/{progenitor_team_id} (team metadata, public_id, record).
    public_id (from GET /teams/{progenitor_team_id} response): use with all /public/ endpoints.
    The pattern root_team_id for roster/avatar, progenitor_team_id for metadata was
    confirmed by observing GC web app traffic against Nighthawks Navy AAA 14U.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponent/{opponent_id}
    reason: Single opponent lookup by root_team_id (singular /opponent/ path)
  - path: /teams/{team_id}/opponents/players
    reason: Bulk opponent roster with handedness across all opponents in one call
  - path: /teams/{team_id}
    reason: Team detail using progenitor_team_id as the team_id
  - path: /organizations/{org_id}/opponents
    reason: Org-level opponent list (returns same fields, larger scope)
---

# GET /teams/{team_id}/opponents

**Status:** CONFIRMED LIVE -- 200 OK. 70 records across 2 pages. Last verified: 2026-03-04.

Returns the complete opponent registry for a team. Each record represents one opponent team that this team has played against. Paginated with page size 50 (same cursor pattern as game-summaries).

**CRITICAL -- Three UUID fields with different semantics (confirmed 2026-03-09):**
- `root_team_id`: Local registry key. Use with: `GET /teams/{team_id}/opponent/{root_team_id}`, `GET /teams/{root_team_id}/players`, `GET /teams/{root_team_id}/avatar-image`.
- `owning_team_id`: Always equals the path `team_id`. Informational only -- never use as a team_id parameter elsewhere.
- `progenitor_team_id`: **Canonical GC team UUID.** Use with: `GET /teams/{progenitor_team_id}` (returns team metadata including `public_id`). The `public_id` from that response is then used for all `/public/teams/{public_id}` endpoints.

```
GET https://api.team-manager.gc.com/teams/{team_id}/opponents
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
Accept: application/vnd.gc.com.opponent_team:list+json; version=0.0.0
gc-user-action: data_loading:opponents
gc-user-action-id: {UUID}
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

## Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/opponents?start_at={cursor}
```

When `x-next-page` is absent, you are on the last page.

## Response

Bare JSON array of opponent records. Page size 50. 70 records across 2 pages (50 + 20) observed.

| Field | Type | Notes |
|-------|------|-------|
| `root_team_id` | UUID | Local registry key. Use ONLY as `opponent_id` in `GET /teams/{team_id}/opponent/{opponent_id}`. Do NOT use with other team endpoints. |
| `owning_team_id` | UUID | Always equals the path `team_id`. Informational only. |
| `name` | string | Opponent display name |
| `is_hidden` | boolean | Whether hidden from UI. 57 visible, 13 hidden (dupes/bad entries) in observed data. Filter `is_hidden=true` in ETL. |
| `progenitor_team_id` | UUID or null | **Canonical GC team UUID.** Use THIS with `/teams/{id}`, `/season-stats`, `/players`, etc. Present on 60/70 records (10 opponents have no canonical UUID). |

**`progenitor_team_id` == `pregame_data.opponent_id`** from schedule (confirmed). This is the same UUID returned by `GET /teams/{team_id}/schedule` in `pregame_data.opponent_id`.

## Example Response

```json
[
  {
    "root_team_id": "6e898958-c6e3-48c7-a97e-e281a35cfc50",
    "owning_team_id": "72bb77d8-REDACTED",
    "name": "Blackhawks 14U",
    "is_hidden": false,
    "progenitor_team_id": "f0e73e42-f248-402b-8171-524b4e56a535"
  }
]
```

## Known Limitations

- `progenitor_team_id` is absent on 10/70 records -- opponents with no canonical GC team UUID. Cannot use those opponents for cross-endpoint lookups.
- Filter `is_hidden=true` records in ETL. Hidden opponents are duplicates or erroneous entries.
- `root_team_id` and `progenitor_team_id` look like UUIDs but have completely different semantics. Confusing the two is a common mistake.

**Discovered:** 2026-03-04. **Schema confirmed:** 2026-03-04.
