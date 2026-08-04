---
method: GET
path: /organizations/{org_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: partial
    notes: >
      BEHAVIOR verified 2026-08-04 (HTTP 200 on 31 organizations, 404 on 9 team ids);
      SCHEMA only partially transcribed -- 12 fields counted, 4 documented. The 2026-03-12
      session saw only HTTP 304 (cached).
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "31 organizations (2026-08-04)"
discovered: "2026-03-12"
last_confirmed: "2026-08-04"
tags: [organization]
caveats:
  - >
    STATUS IS OBSERVED -- WHICH HALF IS WHICH. README.md defines OBSERVED as "schema not fully
    confirmed", which is exactly the case here: the BEHAVIOR is fully verified (200 on 31/31
    orgs, 404 on 9/9 team ids, two-sided access control), while the SCHEMA is not -- 12 fields
    counted, 4 transcribed. Promote to CONFIRMED only after transcribing the remaining 8 from a
    live response; do NOT promote on the behavioral evidence alone. last_confirmed below dates
    the BEHAVIORAL verification.
  - >
    DO NOT "CORRECT" THIS TO PARTIAL. PARTIAL means "works under specific conditions only
    (e.g., requires special parameters)" -- this endpoint takes no parameters and returns 200
    unconditionally, so PARTIAL would be a false hit for anyone filtering the index for
    parameter-gated calls. This file briefly carried PARTIAL on 2026-08-04, reasoned as
    "not CONFIRMED, therefore PARTIAL"; that inference skips the bucket that fits.
  - >
    THIS IS THE ENTITY-CLASS DISCRIMINATOR -- the most useful property of this endpoint.
    200 on 31/31 real organization ids; 404 on 9/9 TEAM ids and on a random UUID. It is one of
    only two org paths that validate entity class (the other is /avatar-image). Most org
    sub-resources do NOT: GET /organizations/{team_id}/opponents will happily serve that
    TEAM's own registry. Use this endpoint to answer "is this id an organization?"
  - >
    RESOLVABLE, NOT PERMITTED, NOT EXISTS -- keep the three apart. This tests resolvable /
    entity class. For PERMITTED use /organizations/{id}/pitch-count-report (200 on 4/4
    related orgs, 403 on 28/28 strangers -- the producible refusal control). There is NO cheap
    test for EXISTS, and BOTH directions fail: SOME org list sub-resources return 200 [] for a
    team id and for a random UUID alike (so empty is ambiguous), while OTHERS serve the TEAM'S
    OWN data under the org prefix -- /organizations/{team_id}/opponents returned that team's
    56-record registry. So a POPULATED list is ambiguous too, and that direction is the more
    dangerous: it attributes a team's records to an organization. Use this endpoint, not a
    list sub-resource, to decide entity class.
  - >
    A MALFORMED (non-UUID) org segment returns HTTP 500, not 403/404 -- e.g.
    /organizations/not-a-uuid. This DIFFERS from /teams/{non-uuid}/opponents, which returns
    403. Do not generalize the 403 across path prefixes.
  - >
    ngb IS A JSON-ENCODED STRING here (e.g. "[\"usssa\"]"), NOT an array as on team endpoints.
    Parse accordingly. See get-public-teams-public_id.md for the ngb enum caveats -- that enum
    is known NOT to be closed.
  - >
    RETIRED 2026-08-04 -- the 2026-03-12 claim, kept so it is not reintroduced: "SCHEMA
    UNKNOWN: All 3 hits returned HTTP 304 (Not Modified / cached)." The 304s were cache
    behavior in that session, not a property of the endpoint.
see_also:
  - path: /organizations/{org_id}/teams
    reason: Teams within this organization (carries gc_uuid + team_public_id)
  - path: /organizations/{org_id}/pitch-count-report
    reason: The permission probe -- pair it with this endpoint to separate class from access
  - path: /organizations/{org_id}/standings
    reason: Current-season standings for the organization's teams
  - path: /organizations/{org_id}/game-summaries
    reason: Aggregated game summaries across org teams
---

# GET /organizations/{org_id}

**Status:** OBSERVED -- **behavior** verified 2026-08-04 on 31 organizations (HTTP 200; 404 on team ids); **schema** only partially transcribed (4 of 12 fields), which is what keeps it below CONFIRMED.

Returns metadata for an organization. The base org endpoint -- analogous to `GET /teams/{team_id}` for teams.

**Its most valuable use is as an entity-class test**, not as a metadata read: it returns 200 for organization ids (31/31) and **404 for team ids** (9/9) and for a random UUID. Since `POST /search` returns organizations and teams in one heterogeneous result set, and most org sub-resources will serve a team id without complaint, this is how you confirm an id really is an organization.

```
GET https://api.team-manager.gc.com/organizations/{org_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Response

A JSON object of **12 fields**. The full field list has not been transcribed into this file; the fields confirmed by direct observation are:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Organization subtype. Closed enum, read from the web app's own source 2026-08-04: `"league"`, `"tournament"`, `"travel"`. Note this is the ORG subtype -- on a `POST /search` hit it lives at `result.type` and is **absent on teams**, which is why entity-class filtering must read the hit's ENVELOPE `type`, not `result.type`. |
| `public_id` | string | Public slug. Organizations DO carry one, so `public_id` alone never distinguishes an org from a team. |
| `ngb` | string | ⚠ A **JSON-encoded string** (e.g. `"[\"usssa\"]"`), unlike the array form on team endpoints. |
| `tournament_dates` | object | Start/end pair. Population unmeasured **on this endpoint** -- do not code a nullability rule off the search figure below. |

**Measured on `POST /search` hits, NOT on this endpoint** — kept because it is the only population data we have, but do not attribute it here: `tournament_dates` present on **45 of 93** organizations and **0 of 506** teams; `city`/`state` returned `null` in the search envelope while populated on this endpoint. This endpoint's own sample is **31 organizations** (frontmatter `raw_sample_size`), and it returns no teams at all, so no per-field population rate for it has been measured.

> **Do not treat the four rows above as the schema.** Twelve fields were counted; four are documented. The remainder are uncaptured, not absent -- transcribe them from a live response before relying on this table as complete.

**Discovered:** 2026-03-12. **Last confirmed:** 2026-08-04 (31 organizations, with a producible 403 control on `/pitch-count-report`).
