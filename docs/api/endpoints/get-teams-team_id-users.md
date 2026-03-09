---
method: GET
path: /teams/{team_id}/users
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      Page 2 (start_at=100) confirmed 2026-03-04 -- 33 records. Page 1 confirmed
      2026-03-07 against Lincoln Rebels 14U (72bb77d8) -- 100 records. Schema
      consistent across teams.
  mobile:
    status: observed
    notes: >
      3 hits, HTTP 200. Observed 2026-03-09 (session 063531). Called with opponent
      progenitor_team_id (14fd6cb6) including paginated call (start_at).
accept: "application/vnd.gc.com.team_user:list+json; version=0.0.0"
gc_user_action: "data_loading:team"
query_params:
  - name: start_at
    required: false
    description: Pagination cursor (integer). Omit for first page. Obtain from x-next-page response header. Page 2 confirmed with start_at=100.
pagination: true
response_shape: array
response_sample: data/raw/team-users-sample.json
raw_sample_size: "33 records, PII-redacted, ~3.5 KB (page 2)"
discovered: "2026-03-04"
last_confirmed: "2026-03-07"
tags: [team, user]
caveats:
  - >
    PII-DENSE ENDPOINT: Every record contains real name, email address, and user UUID.
    Raw responses must never be stored without full redaction. Sample file at
    data/raw/team-users-sample.json has all PII replaced with placeholders.
  - >
    NO ROLE FIELD: Response does not indicate whether a user is a coach, player,
    parent, or fan. Cross-reference with /teams/{team_id}/associations or
    /me/teams?include=user_team_associations for role context.
  - >
    STATUS ENUM INCOMPLETE: Only "active", "active-confirmed", and "invited" observed.
    Values like "inactive", "pending", "removed" may exist.
related_schemas: []
see_also:
  - path: /teams/{team_id}/associations
    reason: Role/relationship data for team members (coach, player, parent, fan)
  - path: /teams/{team_id}/users/count
    reason: Get total user count before paginating to know how many pages to expect
  - path: /me/teams
    reason: Includes user_team_associations for the authenticated user's own roles
---

# GET /teams/{team_id}/users

**Status:** CONFIRMED LIVE -- 200 OK. Page 2 confirmed 2026-03-04, page 1 confirmed 2026-03-07. Last verified: 2026-03-07.

**PII WARNING:** This endpoint returns real user names, email addresses, and UUIDs. All stored samples must be fully redacted. Never log, display, or commit actual values.

Returns the user roster for a team -- the list of GameChanger accounts associated with that team (parents, coaches, players, fans). Each record is a flat user object with identity and account status. No role or association type is returned; this endpoint does not indicate whether a user is a coach, player, or family member.

```
GET https://api.team-manager.gc.com/teams/{team_id}/users
GET https://api.team-manager.gc.com/teams/{team_id}/users?start_at={cursor}
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
Accept: application/vnd.gc.com.team_user:list+json; version=0.0.0
gc-user-action: data_loading:team
gc-user-action-id: {UUID}
x-pagination: true
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note:** `gc-user-action: data_loading:team` -- same value as `GET /teams/{team_id}` (team detail) and `GET /teams/{team_id}/public-team-profile-id`. All three are grouped as "team loading" actions in GameChanger's telemetry.

## Pagination Response Header

```
x-next-page: https://api.team-manager.gc.com/teams/{team_id}/users?start_at={cursor}
```

When `x-next-page` is absent, you are on the last page. Use `GET /teams/{team_id}/users/count` to get the total user count before paginating.

## Response

Bare JSON array of user objects. Page size 100 (confirmed). 33 records on page 2 (start_at=100).

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID | No | User UUID. Stable identifier for this GameChanger account. **PII -- redact in all stored files.** |
| `status` | string | No | Account status. See status enum below. |
| `first_name` | string | No | User's first name. **PII -- redact in all stored files.** |
| `last_name` | string | No | User's last name. **PII -- redact in all stored files.** |
| `email` | string | No | User's email address. **PII -- redact in all stored files.** |

### Status Enum

| Value | Description |
|-------|-------------|
| `"active"` | Standard active account. Majority of users. |
| `"active-confirmed"` | Active account with email confirmation explicitly recorded. May relate to coach/staff roles. |
| `"invited"` | User has been invited but has not yet accepted/set up their account. Confirmed 2026-03-07. |

Other values (`"inactive"`, `"pending"`, `"removed"`) may exist but have not been observed.

## Example Response (PII fully redacted)

```json
[
  {
    "id": "REDACTED_UUID_1",
    "status": "active",
    "first_name": "REDACTED_FIRST",
    "last_name": "REDACTED_LAST",
    "email": "REDACTED_EMAIL"
  },
  {
    "id": "REDACTED_UUID_2",
    "status": "active-confirmed",
    "first_name": "REDACTED_FIRST",
    "last_name": "REDACTED_LAST",
    "email": "REDACTED_EMAIL"
  }
]
```

## Known Limitations

- **No role information:** Response does not indicate whether a user is a coach, player, parent, or fan. Cross-reference with `/teams/{team_id}/associations` or `/me/teams?include=user_team_associations` for role context.
- **`active-confirmed` semantics unclear:** Observed on 2/33 records. The distinction from `"active"` is undocumented.
- **Large teams require multiple pages:** Lincoln Rebels 14U (`72bb77d8`) has 243 total users across at least 3 pages (100+100+43). Cross-reference with `/users/count` before paginating.
- **Schema confirmed across 2 teams:** Originally captured from team `cb67372e`, re-confirmed 2026-03-07 against team `72bb77d8`.

**Discovered:** 2026-03-04. **Multi-page and multi-team confirmed:** 2026-03-07.
