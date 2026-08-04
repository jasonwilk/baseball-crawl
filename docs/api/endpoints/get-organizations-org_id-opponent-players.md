---
method: GET
path: /organizations/{org_id}/opponent-players
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200 with x-pagination: true -- 460 players across 16 of 18 member teams in 2 calls
      on a non-associated org (2026-08-04). The BARE call still returns HTTP 500 (2/2), so the
      2026-03-11 "the page_size bug appears to have been resolved server-side" reading is
      WITHDRAWN: the header was the missing ingredient all along, not a server-side fix.
  mobile:
    status: observed
    notes: 2 hits, status 200, paginated. Discovered 2026-03-05. Schema not captured from mobile.
accept: "application/vnd.gc.com.player:list+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: true
response_shape: array
response_sample: null
raw_sample_size: "460 players across 16 of 18 member teams, 2 calls (2026-08-04); 107 players ~32KB (web, 2026-03-11)"
discovered: "2026-03-05"
last_confirmed: "2026-08-04"
tags: [organization, opponent, player, bulk]
caveats:
  - >
    SEND x-pagination: true -- THE BARE CALL STILL 500s. The 2026-03-11 note below claimed the
    HTTP 500 "appears to have been resolved server-side"; that does NOT hold. Measured
    2026-08-04: the bare call returned HTTP 500 on 2/2 attempts, and succeeded with the
    x-pagination header. Same shape as /organizations/{org_id}/teams -- the HEADER is the
    requirement, not the query params.
  - >
    RETIRED 2026-08-04 -- the following was the 2026-03-11 claim, kept so it is not
    reintroduced: "HTTP 500 RESOLVED ... As of 2026-03-11 web proxy session, returns HTTP 200
    without pagination parameters. The server-side bug appears fixed." Refuted above. The
    likeliest explanation is that the proxied browser session sent the header and the
    observation credited the absence of the query params.
  - >
    IT ROUTES AROUND THE TEAM-ROSTER ASSOCIATION GATE -- the highest-value property here.
    Measured 2026-08-04 on an organization the account has NO relationship with: 460 players
    across 16 of 18 member teams in 2 calls, with the per-team count matching
    GET /teams/public/{public_id}/players EXACTLY (27 == 27) -- while
    GET /teams/{gc_uuid}/players returned 403 for that same team. Producible refusal control
    in-session: /organizations/{id}/pitch-count-report 200 on 4/4 related, 403 on 28/28
    strangers.
  - >
    JOIN KEY: the team_id field here is the member's proxy_team_id, NOT its gc_uuid. Join
    through /organizations/{org_id}/teams to reach gc_uuid / team_public_id.
  - >
    STATUS UPDATE 2026-03-11: Changed from PARTIAL to OBSERVED. Schema now documented
    from live web proxy data. Previous "iOS only" limitation no longer observed.
see_also:
  - path: /teams/{team_id}/opponents/players
    reason: Team-level bulk opponent player roster (confirmed, 758 records) -- team scope
  - path: /organizations/{org_id}/teams
    reason: Maps this endpoint's proxy_team_id join key to gc_uuid / team_public_id
  - path: /organizations/{org_id}/opponents
    reason: The same membership set in opponent shape (NOT opponents faced)
---

# GET /organizations/{org_id}/opponent-players

**Status:** CONFIRMED -- HTTP 200 with `x-pagination: true`. Last verified 2026-08-04 (460 players, non-associated org, with a producible 403 control).

Returns player rosters for the organization's member teams, in bulk.

⚠ **Send `x-pagination: true`. The bare call returns HTTP 500 (2/2, 2026-08-04)** -- the 2026-03-11 "resolved server-side" note was wrong; see the caveats.

**This is the most capable org endpoint we know of**: on an organization the account has no relationship with, it returned 460 players across 16 of 18 member teams in 2 calls, per-team counts matching the public roster endpoint exactly -- **while the authenticated per-team roster endpoint 403s for those same teams.** It routes around the roster association gate.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/opponent-players
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization identifier |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.player:list+json; version=0.1.0
```

## Response

**HTTP 200.** JSON array of player objects.

| Field | Type | Description |
|-------|------|-------------|
| `[].id` | UUID | Player UUID |
| `[].team_id` | UUID | ⚠ The **member team** this player belongs to, keyed by that team's **`proxy_team_id`** -- NOT its `gc_uuid` (8/8, 10/10 measured). Join through `/organizations/{org_id}/teams` to reach `gc_uuid` / `team_public_id`. |
| `[].status` | string | Player status. Observed: `"active"`. |
| `[].first_name` | string | Player first name |
| `[].last_name` | string | Player last name (may be abbreviated) |
| `[].number` | string | Jersey number as string |
| `[].bats` | object | Batting/throwing handedness (may be partially populated) |
| `[].bats.player_id` | UUID | Player UUID (repeated within bats object) |
| `[].bats.throwing_hand` | string | Throwing hand. Observed: `"right"`. (May be absent) |
| `[].bats.batting_side` | string | Batting side. Observed: `"right"`. (May be absent) |
| `[].person_id` | UUID | Person UUID |

## Example Response (truncated)

```json
[
  {
    "id": "00000000-REDACTED",
    "team_id": "00000000-REDACTED",
    "status": "active",
    "first_name": "Player",
    "last_name": "A",
    "number": "99",
    "bats": {
      "player_id": "00000000-REDACTED"
    },
    "person_id": "00000000-REDACTED"
  },
  {
    "id": "00000000-REDACTED",
    "team_id": "00000000-REDACTED",
    "status": "active",
    "first_name": "Player",
    "last_name": "B",
    "number": "7",
    "bats": {
      "throwing_hand": "right",
      "batting_side": "right",
      "player_id": "00000000-REDACTED"
    },
    "person_id": "00000000-REDACTED"
  }
]
```

**Coaching relevance: HIGH.** Bulk player rosters for an organization's **member teams**, in one or two calls, without needing an association with any of them. The `bats` object provides handedness when populated.

⚠ **NOT "players the org's teams have faced."** Despite the `opponent-players` path and the opponent-shaped schema, the population is the org's own membership -- the same set `/organizations/{org_id}/opponents` returns, whose intersection with those teams' real opponents-faced registries is **zero** (3/3 orgs, 2026-08-04). An earlier revision of this line described it as a scouting database of faced opponents; that is refuted.

**Status history.** PARTIAL (HTTP 500 from web, 2026-03-05) → OBSERVED (2026-03-11, web proxy session showed HTTP 200) → **CONFIRMED (2026-08-04)**. The 2026-03-11 step drew the wrong conclusion from a correct observation: the proxied browser session was sending `x-pagination: true`, and the absence of query params got the credit. The endpoint was never server-side-fixed; it was always header-gated.

**Discovered:** 2026-03-05. **Last confirmed:** 2026-08-04.
