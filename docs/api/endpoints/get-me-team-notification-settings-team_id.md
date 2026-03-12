---
method: GET
path: /me/team-notification-settings/{team_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: 3 hits, HTTP 304. Observed in session 2026-03-12_034919.
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
discovered: "2026-03-12"
last_confirmed: null
tags: [me, team, user]
caveats:
  - >
    DISTINCT FROM /teams/{team_id}/team-notification-setting: That endpoint returns the
    team-level admin setting. This endpoint (/me/team-notification-settings/{team_id})
    returns the authenticated user's personal notification preferences for this team.
    Per-user, per-team setting -- not a team-wide setting.
  - >
    SCHEMA UNKNOWN: All 3 hits returned HTTP 304 (Not Modified / cached). Response body
    not captured from this session.
  - >
    NOT RELEVANT FOR DATA INGESTION: Notification preference data has no coaching value.
see_also:
  - path: /teams/{team_id}/team-notification-setting
    reason: Team-admin-level notification setting (not per-user)
  - path: /PATCH/me/team-notification-settings/{team_id}
    reason: Endpoint to update this setting
---

# GET /me/team-notification-settings/{team_id}

**Status:** OBSERVED -- HTTP 304 (3 hits) in web proxy session 2026-03-12_034919.

Returns the authenticated user's personal notification settings for a specific team. Distinct from `GET /teams/{team_id}/team-notification-setting`, which is a team-admin-level setting. This is a per-user, per-team preference (e.g., whether to receive event reminders for this team).

```
GET https://api.team-manager.gc.com/me/team-notification-settings/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID |

## Response

Schema unknown (304 cached responses only). Expected: object with notification preference fields similar to `/teams/{team_id}/team-notification-setting` but scoped to the authenticated user.

**Coaching relevance: NONE.** User notification preferences. Not relevant to data ingestion.

**Discovered:** 2026-03-12. Session: 2026-03-12_034919 (web).
