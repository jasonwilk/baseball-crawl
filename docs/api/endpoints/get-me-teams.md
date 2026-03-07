---
method: GET
path: /me/teams
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented from 15-record live capture on 2026-03-04.
  mobile:
    status: unverified
    notes: Not captured from mobile profile; assumed to work with standard auth headers.
accept: "application/vnd.gc.com.team:list+json; version=0.10.0"
gc_user_action: null
query_params:
  - name: include
    required: false
    description: >
      Pass `include=user_team_associations` to populate the `user_team_associations`
      array on each team object. Without this param, the array is absent or empty.
pagination: false
response_shape: array
response_sample: data/raw/me-teams-sample.json
raw_sample_size: "15 teams, 18 KB"
discovered: "2026-02-28"
last_confirmed: "2026-03-04"
tags: [team, user]
related_schemas: []
see_also:
  - path: /teams/{team_id}
    reason: Single team detail; same 25-field schema but returns one team by UUID
  - path: /me/archived-teams
    reason: Historical/archived teams for the same account (multi-season analysis)
  - path: /me/teams-summary
    reason: Lightweight team count and date range -- quick check for account scope
---

# GET /me/teams

**Status:** CONFIRMED LIVE -- 200 OK. 15 teams returned. Last verified: 2026-03-04.

Returns all teams the authenticated user has any association with (manager, player, family member, or fan). This is the recommended first call for bootstrapping -- it provides all team UUIDs needed for downstream endpoints.

```
GET https://api.team-manager.gc.com/me/teams
```

## Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `include` | No | Pass `user_team_associations` to get the user's roles per team (e.g., `["manager", "family"]`). Without this param, the `user_team_associations` field is absent. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team:list+json; version=0.10.0
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

No `gc-user-action` was observed for this endpoint.

## Response

Bare JSON array of team objects. No pagination observed (15 teams returned in one response). The response is the same 25-field schema as `GET /teams/{team_id}` with two additions: `user_team_associations` (populated when `include=user_team_associations`) and `badge_count`.

**Observed counts (2026-03-04, Jason's travel ball account):**
- 15 total teams (8 archived, 7 active)
- Ages: 8U through 14U, plus "Between 13-18" for Legion
- Seasons: 2019-2025
- LSB high school teams NOT present (separate coaching account required)

### Team Object Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID | No | Team UUID. Use this as `team_id` in all team-scoped endpoints. |
| `name` | string | No | Human-readable team name (e.g., "Lincoln Rebels 14U"). |
| `team_type` | string | No | Access/ownership type. All 15 observed: `"admin"`. |
| `city` | string | No | City of the team. |
| `state` | string | No | State abbreviation (e.g., `"NE"`). |
| `country` | string | No | Country name (e.g., `"United States"` or `"USA"` -- both observed). |
| `age_group` | string | No | Age bracket string. Observed: `"8U"`, `"9U"`, `"10U"`, `"11U"`, `"12U"`, `"13U"`, `"14U"`, `"Between 13 - 18"`. |
| `competition_level` | string | No | Observed: `"club_travel"`, `"recreational"`. |
| `sport` | string | No | Always `"baseball"` in this dataset. |
| `season_year` | int | No | Four-digit year of the season. |
| `season_name` | string | No | Season identifier: `"spring"`, `"summer"`, `"fall"`. |
| `stat_access_level` | string | No | Who can view stats: `"confirmed_individual"`, `"confirmed_full"`, `"fans"`. |
| `scorekeeping_access_level` | string | No | Who can keep score. All 15 observed: `"staff_only"`. |
| `streaming_access_level` | string | No | Who can access video: `"confirmed_members"`, `"staff_only"`. |
| `paid_access_level` | string or null | Yes | `"premium"` or `null`. Null for most teams. |
| `settings` | object | No | Scorekeeping and integration settings. |
| `settings.scorekeeping.bats.innings_per_game` | int | No | Default innings per game. Observed: 6 or 7. |
| `settings.scorekeeping.bats.shortfielder_type` | string | No | All observed: `"none"`. |
| `settings.scorekeeping.bats.pitch_count_alert_1` | int or null | Yes | Pitch count warning threshold 1. Usually null. |
| `settings.scorekeeping.bats.pitch_count_alert_2` | int or null | Yes | Pitch count warning threshold 2. Usually null. |
| `settings.maxpreps` | null | Yes | MaxPreps integration config. Always null in this dataset. |
| `organizations` | array | No | Organizations this team belongs to. Empty array for most teams. Each entry: `{organization_id: UUID, status: "active"}`. |
| `ngb` | **JSON-encoded string** | No | National Governing Body affiliation. **IMPORTANT: This is a string containing JSON, not a native array. Double-parse required.** Observed: `"[]"`, `"[\"usssa\"]"`, `"[\"american_legion\"]"`. |
| `user_team_associations` | array of strings | Conditional | The user's roles for this team. Only present when `include=user_team_associations`. Observed: `"manager"`, `"player"`, `"family"`, `"fan"`. A user may have multiple roles. |
| `team_avatar_image` | null | Yes | Team avatar image URL. All 15 observed: `null`. |
| `team_player_count` | null | Yes | Player count. All 15 observed: `null`. |
| `created_at` | ISO 8601 | No | Team creation timestamp. |
| `public_id` | string | No | Short public identifier slug (e.g., `"a1GFM9Ku0BbF"`). Not a UUID. Used in public URLs. |
| `url_encoded_name` | string | No | URL-safe team name slug (e.g., `"2025-summer-lincoln-rebels-14u"`). |
| `archived` | boolean | No | Whether the team is archived. 8 of 15 teams archived. |
| `record` | object | No | Win-loss record: `{wins: int, losses: int, ties: int}`. Always present. |
| `badge_count` | int | No | All 15 observed: `0`. Purpose unclear. |

### user_team_associations Values

| Value | Description |
|-------|-------------|
| `"manager"` | Team manager or coach. Has administrative access. |
| `"player"` | Registered as a player on this team. |
| `"family"` | Family member (parent/guardian) of a player. |
| `"fan"` | Follows the team without a direct player connection. |

## Example Response (Abridged)

```json
[
  {
    "id": "72bb77d8-54ca-42d2-8547-9da4880d0cb4",
    "name": "Lincoln Rebels 14U",
    "team_type": "admin",
    "city": "Lincoln",
    "state": "NE",
    "country": "United States",
    "age_group": "14U",
    "competition_level": "club_travel",
    "sport": "baseball",
    "season_year": 2025,
    "season_name": "summer",
    "stat_access_level": "confirmed_full",
    "scorekeeping_access_level": "staff_only",
    "streaming_access_level": "confirmed_members",
    "paid_access_level": null,
    "settings": {
      "scorekeeping": {
        "bats": {
          "innings_per_game": 7,
          "shortfielder_type": "none",
          "pitch_count_alert_1": null,
          "pitch_count_alert_2": null
        }
      },
      "maxpreps": null
    },
    "organizations": [{"organization_id": "<uuid>", "status": "active"}],
    "ngb": "[\"usssa\"]",
    "user_team_associations": ["family", "manager"],
    "team_avatar_image": null,
    "team_player_count": null,
    "created_at": "2024-11-02T12:34:20.229Z",
    "public_id": "a1GFM9Ku0BbF",
    "url_encoded_name": "2025-summer-lincoln-rebels-14u",
    "archived": false,
    "record": {"wins": 61, "losses": 29, "ties": 2},
    "badge_count": 0
  }
]
```

## Bootstrap Discovery Flow

This endpoint is the recommended first call. From the response you can:

- Extract all team UUIDs (`id` field) for use with downstream endpoints
- Filter to current season: `season_year` and `archived: false`
- Filter to managed teams: `"manager"` in `user_team_associations`
- Get the `public_id` slug for public endpoint access
- Get win-loss records without additional API calls

```python
import json

# Double-parse the ngb field (JSON-encoded string, not native array)
ngb_list = json.loads(team["ngb"])  # first parse: string -> list
# ngb_list is now ["usssa"] or [] or ["american_legion"]
```

## Known Limitations

- `ngb` field requires double-JSON-parsing (string containing JSON). See above.
- `team_player_count` is always `null` in observed data. Purpose unknown.
- `badge_count` is always `0`. Purpose unknown.
- `user_team_associations` is only populated when `include=user_team_associations` is passed.
- **Account scope:** The `gc-token` is account-specific. The 2026-03-04 capture returned only Jason's travel ball teams. LSB high school teams require a gc-token from a coaching account with access to those teams.
- No pagination observed. All 15 teams returned in a single response. Behavior for accounts with very large team counts is unknown.

**Discovered:** Pre-2026-03-01. **Schema fully documented:** 2026-03-04.
