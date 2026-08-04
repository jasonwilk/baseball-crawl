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
last_confirmed: "2026-08-04"
tags: [team, opponent]
caveats:
  - >
    URL STRUCTURE: Uses /opponent/ (singular), not /opponents/ (plural). The singular
    form returns a specific opponent; the plural form (/opponents) returns the paginated list.
  - >
    WORKS FOR NON-MANAGED TEAMS (confirmed 2026-08-03): 200 OK with the full record
    (is_hidden, name, owning_team_id, progenitor_team_id, root_team_id) for teams we
    neither manage nor follow -- 34 of 36 attempts across 20+ scouted teams; the 2
    non-200s were a bad input (a null opponent_id) and not an access refusal. This
    makes it the only reachable source of the DUAL-ENTRY signal for a scouted team:
    progenitor_team_id KEY PRESENT means the coach linked the opponent via GC team
    lookup, key ABSENT means they typed it by hand. Test key presence, not truthiness.
    The public schedule carries no such signal (see /public/teams/{public_id}/games).
  - >
    opponent_id IS root_team_id: The path parameter opponent_id must be the root_team_id
    from GET /teams/{team_id}/opponents -- NOT the progenitor_team_id.
  - >
    PREFER THE BULK PLURAL ENDPOINT FOR MULTI-LOOKUP WORK (2026-08-03): the plural
    GET /teams/{team_id}/opponents also requires NO association, so a whole registry
    is one PAGINATED fetch (send x-pagination: true -- the bare call silently caps
    at 100) and per-opponent lookups become an in-memory join on root_team_id.
    This endpoint agreed with the bulk registry on progenitor_team_id 6/6 on the
    same pairs. Reach for the singular form for a one-off lookup or when you hold a
    root_team_id but not the registry.
  - >
    THIS ENDPOINT NEVER RETURNS 404. Both a MALFORMED opponent_id and a WELL-FORMED
    UUID that is simply not in this team's registry return HTTP 500 (observed
    2026-08-03 and 2026-08-04; the latter carries a "Cannot find opponent" body).
    A caller therefore CANNOT distinguish bad-format from not-in-registry by status
    code -- only the response body text discriminates. A 500 here is a CALLER-side
    signal to validate the id, not evidence of a GC outage or a retryable failure.
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
| `progenitor_team_id` | UUID or **absent** | Canonical GC team UUID -- use this for `/teams/{id}`, `/season-stats`, `/players`, etc. The key is **omitted entirely** on a hand-typed opponent; test key presence, not truthiness. |

## Bulk alternative (2026-08-03)

The plural [`GET /teams/{team_id}/opponents`](get-teams-team_id-opponents.md) turned out to require **no association either** (21/21 teams with no relationship to the account, replicated 24/24 on a disjoint sample). That changes when to reach for this endpoint:

- **Resolving many opponents for a team** -- fetch the plural endpoint **with `x-pagination: true`** and join on `root_team_id` in memory. No per-opponent HTTP cost. ⚠ Do not use the bare plural call as the bulk source: it silently truncates at 100 records with no `x-next-page` and no error.
- **Resolving one opponent, or holding a `root_team_id` without the registry** -- this endpoint.

The two agree: on 6 pairs checked both ways, the `progenitor_team_id` returned here matched the bulk registry's **6/6**.

## Error behavior

| Input | Response |
|-------|----------|
| Valid `team_id` + valid `root_team_id` | 200 with the 5-field record |
| Malformed `opponent_id` (non-UUID sentinel) | **HTTP 500** (observed 2026-08-03) |
| **Well-formed UUID not in this team's registry** | **HTTP 500** (`Cannot find opponent[...]`, observed 2026-08-04) |
| Null `opponent_id` | non-200 (observed 2026-08-03) |

**This endpoint never returns 404.** Both bad-format and not-in-this-registry surface as **500**, so **a caller cannot distinguish the two by status code** — the response body text is the only discriminator. Treat a 500 here as a signal to validate the identifier, not as a GameChanger outage or a transient failure worth retrying.

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

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07. **Non-managed access, bulk-vs-singular agreement (6/6), and 500-on-malformed-input verified:** 2026-08-03. **500-on-unknown-well-formed-UUID (never 404) verified:** 2026-08-04.
