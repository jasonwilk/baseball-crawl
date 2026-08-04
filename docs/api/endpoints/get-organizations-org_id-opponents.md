---
method: GET
path: /organizations/{org_id}/opponents
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: >
      Schema documented from web headers 2026-03-05 (7 rows). Row SEMANTICS re-measured
      2026-08-04 on 3 organizations (18 / 27 / 7 rows): the rows are the org's MEMBER TEAMS,
      not opponents faced.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.opponent_team:list+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: true
response_shape: array
response_sample: null
raw_sample_size: "7 rows (2026-03-05); 18 / 27 / 7 across three orgs (2026-08-04)"
discovered: "2026-03-05"
last_confirmed: "2026-08-04"
tags: [organization, opponent]
caveats:
  - >
    OBSERVED STATUS: Schema was documented from web browser headers only -- not confirmed
    via independent curl call. Response body was captured but not independently verified.
  - >
    UUID SEMANTICS: The `owning_team_id` field is the organization UUID (= path param
    `org_id`), not a team UUID. Do not use it as `team_id` in other endpoints.
  - >
    THIS IS THE MEMBERSHIP ROSTER, NOT OPPONENTS FACED. Despite the path, the rows are the
    organization's own MEMBER TEAMS rendered in opponent shape. Measured 2026-08-04 on 3 orgs:
    each row's root_team_id equals a member team's proxy_team_id, and its progenitor_team_id
    equals that member's gc_uuid (18/18, 26/27, 7/7). The intersection with the UNION of the
    member teams' own /teams/{id}/opponents registries is ZERO in 3/3 orgs (org 18 vs union
    520; 27 vs 841; 7 vs 381). An earlier revision of this file said it "returns all opponents
    across all teams in the organization" -- that is refuted, not merely imprecise.
  - >
    CONSEQUENCE: this is NOT a broader bulk source of opponents-faced. Per-team
    /teams/{team_id}/opponents registries remain the only place opponents-faced live. It also
    explains why organizations show a 100%-linked progenitor rate: every row is a member team
    auto-linked at org join, so a progenitor is present by construction, not by coach behavior.
related_schemas: []
see_also:
  - path: /teams/{team_id}/opponents
    reason: The actual opponents-faced registry (this endpoint is NOT its org-level aggregate)
  - path: /organizations/{org_id}/teams
    reason: The same membership set in team shape, carrying gc_uuid + team_public_id
  - path: /organizations/{org_id}/opponent-players
    reason: Bulk member-team player rosters at org level (send x-pagination; bare call 500s)
  - path: /organizations/{org_id}/standings
    reason: Win/loss records for all org opponents
---

# GET /organizations/{org_id}/opponents

**Status:** OBSERVED (web headers, schema documented). Response schema captured but not independently verified via curl.

⚠ **The path name is misleading. This returns the organization's OWN MEMBER TEAMS, rendered in opponent shape -- not opponents its teams have faced.** Each row's `root_team_id` is a member team's `proxy_team_id` and its `progenitor_team_id` is that member's `gc_uuid`. Verified 2026-08-04 across 3 organizations, with **zero** overlap against the union of those orgs' member teams' real opponent registries.

If you want opponents-faced, use `GET /teams/{team_id}/opponents` per team; there is no org-level aggregate of it. If you want the membership set with usable identifiers, prefer `GET /organizations/{org_id}/teams`, which carries `gc_uuid` and `team_public_id` directly.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/opponents
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier (from `/me/related-organizations` or team `organizations` field) |

## Response

Bare JSON array. The objects use the **opponent** schema, but each one is a **member team of this organization** -- see the caveats. 7 rows observed 2026-03-05; 18 / 27 / 7 on the three orgs measured 2026-08-04.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | UUID | ⚠ **The member team's `proxy_team_id`** (18/18, 26/27, 7/7 measured) -- NOT a canonical `gc_uuid`, and NOT an opponent's key. Note this is a THIRD sense of the name: on `/organizations/{org_id}/teams` `root_team_id` IS a `gc_uuid`, and on `/teams/{team_id}/opponents` it is that team's local registry key. |
| `progenitor_team_id` | UUID | ⚠ **The member team's `gc_uuid`** (same ratios). Present on essentially every row *by construction* -- a member team is auto-linked at org join -- which is why organizations show a ~100% linked rate. That rate is an artifact of membership, not evidence about coach linking behavior. |
| `owning_team_id` | UUID | Organization UUID that owns this record (= `org_id`) |
| `name` | string | The member team's name |
| `is_hidden` | boolean | Whether this row is hidden (all `false` observed) |

## Example Response

```json
[
  {
    "root_team_id": "<member-team-proxy_team_id>",
    "progenitor_team_id": "<member-team-gc_uuid>",
    "owning_team_id": "<org-uuid>",
    "name": "Example Team 9U",
    "is_hidden": false
  }
]
```

**Discovered:** 2026-03-05. **Membership semantics measured:** 2026-08-04 (3 orgs; zero overlap with the union of those orgs' member teams' own opponent registries).
