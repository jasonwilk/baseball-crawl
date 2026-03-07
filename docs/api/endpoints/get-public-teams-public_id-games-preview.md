---
method: GET
path: /public/teams/{public_id}/games/preview
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: No auth required. Near-duplicate of /games -- 32 records confirmed.
  mobile:
    status: not_applicable
    notes: Public endpoint -- no auth profile distinction.
accept: "application/vnd.gc.com.public_team_event:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: array
response_sample: data/raw/public-team-games-preview-sample.json
raw_sample_size: "32 records, near-duplicate of /games"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [games, team, public]
related_schemas: []
see_also:
  - path: /public/teams/{public_id}/games
    reason: Preferred endpoint -- same data but uses `id` field instead of `event_id`, includes has_videos_available
---

# GET /public/teams/{public_id}/games/preview

**Status:** CONFIRMED LIVE -- 200 OK. 32 records confirmed. **AUTHENTICATION: NOT REQUIRED.** Last verified: 2026-03-04.

Returns completed games for a team -- a near-duplicate of `GET /public/teams/{public_id}/games`. The primary differences are the UUID field name (`event_id` instead of `id`) and the absence of `has_videos_available`.

**Recommendation:** Prefer `GET /public/teams/{public_id}/games` over this endpoint. The `/games` endpoint uses the `id` field name (consistent with authenticated schedule `event.id`) and includes `has_videos_available`.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}/games/preview
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Alphanumeric public ID slug. NOT a UUID. |

## Headers

```
Accept: application/vnd.gc.com.public_team_event:list+json; version=0.0.0
User-Agent: Mozilla/5.0 ...
```

Do NOT include `gc-token` or `gc-device-id` headers.

## Response

Bare JSON array. Same records as `/games` in same order, with these differences from `/games`:

| Field | `/games/preview` | `/games` |
|-------|-----------------|---------|
| Game UUID field | `event_id` | `id` |
| `has_videos_available` | Absent | Present |
| Record count | 32 | 32 |
| All other fields | Identical | Identical |

10 fields per record (vs. 11 in `/games`). All records: `game_status: "completed"`, `has_live_stream: false`.

## Known Limitations

- Use `GET /public/teams/{public_id}/games` instead -- it provides `id` (not `event_id`) and includes `has_videos_available`.
- `event_id` vs `id` naming inconsistency: this endpoint uses `event_id` which matches the schedule endpoint field name; `/games` uses `id` which does NOT match -- note this if joining across endpoints.

**Discovered:** 2026-03-04. **Confirmed no-auth:** 2026-03-04.
