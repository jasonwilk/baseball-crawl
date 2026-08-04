---
method: GET
path: /organizations/{org_id}/teams
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      HTTP 200. The x-pagination header -- NOT the query params -- is what the server requires.
      Confirmed 2026-03-07; re-confirmed 2026-08-04 on 27 non-associated ("stranger") orgs.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.organization_team:list+json; version=0.1.0"
gc_user_action: null
query_params:
  - name: page_starts_at
    required: false
    description: >
      Pagination offset. Use 0 for first page. OPTIONAL -- the header alone returns 200.
      Sending this WITHOUT the x-pagination header returns HTTP 500.
  - name: page_size
    required: false
    description: >
      Requested page size. OPTIONAL. Server CAPS the effective page size at 50 regardless of
      the value sent. Sending this WITHOUT the x-pagination header returns HTTP 500.
pagination: true
response_shape: array
response_sample: null
raw_sample_size: "7 teams observed (2026-03-07); 27 stranger orgs, up to 50/page (2026-08-04)"
discovered: "2026-03-07"
last_confirmed: "2026-08-04"
tags: [organization, team]
caveats:
  - >
    THE HEADER IS THE REQUIREMENT, NOT THE PARAMS. Send x-pagination: true. Measured
    2026-08-04: header alone -> 200; page_starts_at + page_size WITHOUT the header -> HTTP 500
    ("Cannot read properties of undefined (reading 'page_size')"). An earlier revision of this
    file stated the params were required and the header incidental -- that causation was
    backwards. page_size is server-capped at 50.
  - >
    root_team_id IS THE TEAM UUID: Use root_team_id for /teams/{team_id} and all team-scoped
    endpoints. team_public_id enables public endpoint access without extra bridge calls.
    Verified 2026-08-04 on stranger orgs -- GET /teams/{root_team_id} 200 on 24/24, and the
    returned public_id equalled the row's team_public_id 24/24; controls (random UUID, an
    organization id, a fake public_id) all 404.
  - >
    NAMESPACE COLLISION -- THE FIELD NAME LIES ELSEWHERE. This root_team_id is a canonical
    gc_uuid. The IDENTICALLY-NAMED root_team_id on /teams/{team_id}/opponents is a LOCAL
    registry key that 404s on GET /teams/{id}. Same field name, two namespaces, one endpoint
    apart. CLAUDE.md's rule ("root_team_id is a different namespace from gc_uuid -- NEVER
    store one in the other's column") is correct about the OPPONENTS registry and must not be
    read as universal. Storing the wrong one is the E-211 contamination path.
  - >
    ACCESS IS NOT ASSOCIATION-GATED. Populated on 27/27 orgs the account has no relationship
    with (/me/organizations returns 0; only 4 orgs are "related"). Producible refusal control
    in the same session: GET /organizations/{id}/pitch-count-report returned 200 on 4/4
    related orgs and 403 on 28/28 strangers -- so the 200s here are a genuine grant, not an
    instrument that cannot say no.
related_schemas: []
see_also:
  - path: /me/related-organizations
    reason: Source of org_id values
  - path: /teams/{team_id}
    reason: Team detail using root_team_id from this response
---

# GET /organizations/{org_id}/teams

**Status:** CONFIRMED LIVE -- 200 OK. Last verified: 2026-08-04.

Returns all teams belonging to an organization. **Requires the `x-pagination: true` request header.** The `page_starts_at` / `page_size` query params are **optional**; sending them *without* the header returns HTTP 500.

**Coaching relevance: HIGH.** Single call enumerates all teams in an organization; replaces per-team discovery. It also works on organizations the account has no relationship with (27/27), which makes it a **team-discovery path that needs no name, no search index, and no association** -- see the access caveat in the frontmatter for the refusal control that makes that claim meaningful.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/teams
```

## Required Headers (in addition to standard auth)

```
x-pagination: true
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Optional Query Parameters

Both are optional -- the `x-pagination: true` header alone returns 200. **Sending either without the header returns HTTP 500.**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page_starts_at` | integer | Pagination offset. Use `0` for first page. |
| `page_size` | integer | Requested page size. **Server-capped at 50** regardless of the value sent. |

Follow `x-next-page` to paginate, and **terminate on an empty response body OR on the header's absence -- whichever comes first. Check both.** `x-next-page` over-reports (the last populated page still carried it and the next call returned `200 []`), so header-absence alone is not a reliable stop; but with no header there is no cursor to follow either. See `../pagination.md`.

## Response

Bare JSON array of team objects.

| Field | Type | Description |
|-------|------|-------------|
| `root_team_id` | UUID | Team's primary UUID (a canonical `gc_uuid`) -- use for `/teams/{team_id}` and all team-scoped endpoints. ⚠ **Do not generalize the field NAME**: the identically-named `root_team_id` on `/teams/{team_id}/opponents` is a local registry key that 404s on `GET /teams/{id}`. See the namespace-collision caveat. |
| `organization_id` | UUID | Organization UUID |
| `status` | string | Team status. The client-side enum is closed at **six** values -- `"active"`, `"org_blocked"`, `"org_invite"`, `"org_owned"`, `"team_blocked"`, `"team_request"` (read from the web app's own source 2026-08-04; only `active` and `org_invite` have been observed live). |
| `name` | string | Team display name |
| `sport` | string | Sport (e.g., `"baseball"`) |
| `season_name` | string | Season name (e.g., `"summer"`, `"spring"`) |
| `season_year` | integer | Season year |
| `city` | string | City |
| `state` | string | State/province |
| `country` | string | Country |
| `staff_ids` | array | Array of user UUIDs for team staff (populated for `org_invite` teams) |
| `proxy_team_id` | UUID or null | Internal proxy team ID (null for `"org_invite"` status teams) |
| `age_group` | string | **A polymorphic LEVEL field, not merely an age bracket** -- travel teams carry an `NNU` bracket (e.g. `"14U"`, `"9U"`), school teams carry a tier token (`high_varsity`, `high_junior_varsity`, `high_freshman`, ...), recreational teams carry a free-text range. Same field as on `GET /teams/{team_id}`; full three-family table in `get-public-teams-public_id.md` ("The `age_group` level field"). |
| `team_public_id` | string | Public ID slug -- enables public endpoint access without additional bridge calls |

## Example Record

```json
{
  "root_team_id": "00000000-REDACTED",
  "organization_id": "11111111-REDACTED",
  "status": "active",
  "name": "Example Team 9U",
  "sport": "baseball",
  "season_name": "summer",
  "season_year": 2026,
  "city": "Anytown",
  "state": "NE",
  "country": "United States",
  "staff_ids": [],
  "proxy_team_id": "22222222-REDACTED",
  "age_group": "9U",
  "team_public_id": "xXxXxXxXxXxX"
}
```

> The `NNNNNNNN-REDACTED` prefixes above are **synthetic**. An earlier revision used real UUID prefixes inside the `-REDACTED` placeholder, which re-embeds the very identifier the redaction removes; the denylist cannot catch an 8-char prefix, so this is a read-and-fix, not a scan-and-fix.

**Discovered:** 2026-03-07. **Last confirmed:** 2026-08-04 (stranger orgs, with a producible 403 control).
