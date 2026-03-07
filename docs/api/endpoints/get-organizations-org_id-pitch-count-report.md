---
method: GET
path: /organizations/{org_id}/pitch-count-report
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: HTTP 200. CSV format response confirmed. Discovered 2026-03-07.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: null
gc_user_action: null
query_params: []
pagination: false
response_shape: string
response_sample: null
raw_sample_size: null
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [organization, coaching, stats]
caveats:
  - >
    CSV RESPONSE: Unlike all other endpoints, response is a CSV string (not JSON).
    This is the only non-JSON API response documented in this spec.
  - >
    PAST WEEK ONLY (default): Report appears to cover the past 7 days by default.
    Query parameter for date range not yet confirmed.
related_schemas: []
see_also:
  - path: /me/related-organizations
    reason: Source of org_id values
---

# GET /organizations/{org_id}/pitch-count-report

**Status:** CONFIRMED LIVE -- 200 OK. CSV format. Last verified: 2026-03-07.

Returns a pitch count report for all pitchers in the organization for the past week. **This is the only endpoint that returns CSV format (not JSON).**

**Coaching relevance: HIGH.** Pitch count tracking is a safety and regulatory requirement for youth baseball. This endpoint provides org-wide pitch counts in one call.

```
GET https://api.team-manager.gc.com/organizations/{org_id}/pitch-count-report
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `org_id` | UUID | Organization UUID |

## Response

CSV string (content-type: `text/csv` or `text/plain`).

### CSV Columns

| Column | Description |
|--------|-------------|
| `Game Date` | Date of the game |
| `Start Time` | Game start time |
| `Pitcher` | Pitcher name |
| `Team` | Pitcher's team name |
| `Opponent` | Opposing team |
| `Pitch Count` | Total pitches thrown |
| `Last Batter, First Pitch #` | Pitch number of the first pitch to the last batter faced |
| `Innings Pitched` | Innings pitched |
| `Innings Caught` | Innings the pitcher also caught |
| `Final Score` | Final game score |
| `Scored By` | Who recorded the scoring |

## Example Response

```
Game Date,Start Time,Pitcher,Team,Opponent,Pitch Count,"Last Batter, First Pitch #",Innings Pitched,Innings Caught,Final Score,Scored By
No games with pitcher data were found in the past week.
```

## Known Limitations

- Default date range covers past 7 days. Query parameter for custom range not confirmed.
- `"No games with pitcher data were found in the past week."` message is returned when no recent games exist.

**Discovered:** 2026-03-07. **Confirmed:** 2026-03-07.
