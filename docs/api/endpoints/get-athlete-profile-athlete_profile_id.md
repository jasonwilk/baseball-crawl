---
method: GET
path: /athlete-profile/{athlete_profile_id}
status: OBSERVED
auth: required
profiles:
  web:
    status: observed
    notes: Captured from web proxy session 2026-03-11. HTTP 200. Full schema observed.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.athlete_profile+json; version=0.0.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: null
raw_sample_size: "1 record"
discovered: "2026-03-11"
last_confirmed: null
tags: [player, user]
see_also:
  - path: /me/athlete-profile
    reason: Returns list of athlete profiles linked to the authenticated account (same schema, list version)
  - path: /athlete-profile/{athlete_profile_id}/career-stats
    reason: Cross-team career statistics for this athlete profile
  - path: /athlete-profile/{athlete_profile_id}/career-stats-association
    reason: Maps athlete profile to all player_ids across teams
  - path: /athlete-profile/{athlete_profile_id}/players
    reason: Player identity records linked to this athlete profile
---

# GET /athlete-profile/{athlete_profile_id}

**Status:** OBSERVED -- HTTP 200 in web proxy session 2026-03-11. Schema based on observed data.

Returns metadata for a specific athlete profile. An athlete profile is a cross-team player identity -- it links a single person across all the teams and seasons they have played on. This is the public-facing player profile entity (distinct from the per-team `player` record).

```
GET https://api.team-manager.gc.com/athlete-profile/{athlete_profile_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `athlete_profile_id` | UUID | The athlete profile UUID |

## Request Headers

```
gc-token: {AUTH_TOKEN}
gc-device-id: {GC_DEVICE_ID}
Accept: application/vnd.gc.com.athlete_profile+json; version=0.0.0
```

## Response

**HTTP 200.** Single JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Athlete profile UUID |
| `first_name` | string | Player first name |
| `last_name` | string | Player last name |
| `handle` | string | Public username/handle |
| `publish_status` | string | Profile visibility. Observed: `"published"`. |
| `bio` | string | Player bio text (may be empty string) |
| `sport` | string | Sport. Observed: `"baseball"`. |
| `graduation_year` | integer | Expected graduation year (e.g., 2029) |
| `sport_attributes` | object | Sport-specific metadata |
| `sport_attributes.positions` | array of string | Positions played. Observed values: `"C"`, `"2B"`, `"P"`, `"IF"`. |
| `auto_create` | boolean | Whether the profile was automatically created |

## Example Response

```json
{
  "id": "00000000-REDACTED",
  "first_name": "Player",
  "last_name": "One",
  "handle": "playerone",
  "publish_status": "published",
  "bio": "",
  "sport": "baseball",
  "graduation_year": 2029,
  "sport_attributes": {
    "positions": ["C", "2B", "P", "IF"]
  },
  "auto_create": false
}
```

**Note:** The `graduation_year` field enables multi-season longitudinal tracking even when team names change.

**Coaching relevance: MEDIUM.** Provides a stable cross-team identity for tracked players. The `graduation_year` enables class-year-based cohort analysis.

**Discovered:** 2026-03-11. Session: 2026-03-11_034739 (web).
