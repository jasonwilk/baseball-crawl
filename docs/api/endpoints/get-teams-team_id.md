---
method: GET
path: /teams/{team_id}
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: Full schema documented. Tested with both own team and opponent UUIDs.
  mobile:
    status: unverified
    notes: Not captured from mobile profile.
accept: "application/vnd.gc.com.team+json; version=0.10.0"
gc_user_action: "data_loading:team"
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/team-detail-sample.json
raw_sample_size: "own team, 910 bytes; opponent: data/raw/team-detail-opponent-sample.json"
discovered: "2026-03-04"
last_confirmed: "2026-03-04"
tags: [team, user]
related_schemas: []
see_also:
  - path: /me/teams
    reason: List endpoint; returns all teams for the authenticated user (same schema)
  - path: /teams/{team_id}/season-stats
    reason: Season statistics for the team
  - path: /teams/{team_id}/opponents
    reason: Opponent registry for the team
  - path: /teams/{team_id}/public-team-profile-id
    reason: UUID-to-public_id bridge for accessing public endpoints
---

# GET /teams/{team_id}

**Status:** CONFIRMED LIVE -- 200 OK. Own team and opponent teams confirmed. Last verified: 2026-03-04.

Returns the full detail object for a single team by UUID. The response is a 25-field JSON object -- identical to a team object in `GET /me/teams` but for a single team identified by UUID.

**Opponent access confirmed:** The `opponent_id` field from `GET /teams/{team_id}/schedule` `pregame_data.opponent_id` can be used directly as the `team_id` path parameter. Both own teams and opponent teams return the full 25-field schema. The only difference is the `gc-user-action` header value: use `data_loading:opponents` when fetching an opponent team, `data_loading:team` for your own team.

```
GET https://api.team-manager.gc.com/teams/{team_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `team_id` | UUID | Team UUID. Can be from `GET /me/teams`, schedule `pregame_data.opponent_id`, or game-summaries `game_stream.opponent_id`. |

## Headers (Web Profile)

```
gc-token: {GC_TOKEN}
gc-device-id: {GC_DEVICE_ID}
gc-app-name: web
Accept: application/vnd.gc.com.team+json; version=0.10.0
gc-user-action: data_loading:team
gc-user-action-id: {UUID}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36
```

**Note on `gc-user-action`:** Use `data_loading:opponents` instead of `data_loading:team` when fetching details for an opponent team. Both values return HTTP 200 with the same schema -- the distinction is telemetry on the server side only.

## Response

Single JSON object. Same 25-field schema as team objects in `GET /me/teams` (without `badge_count` and `user_team_associations`).

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID | No | Team UUID. Same as the path parameter. |
| `name` | string | No | Human-readable team name. |
| `team_type` | string | No | Access/ownership type (e.g., `"admin"`). |
| `city` | string | No | City. |
| `state` | string | No | State abbreviation. |
| `country` | string | No | Country name. |
| `age_group` | string | No | Age bracket (e.g., `"14U"`). |
| `competition_level` | string | No | `"club_travel"`, `"recreational"`, etc. |
| `sport` | string | No | Always `"baseball"` in this dataset. |
| `season_year` | int | No | Four-digit season year. |
| `season_name` | string | No | `"spring"`, `"summer"`, `"fall"`. |
| `stat_access_level` | string | No | Who can view stats. |
| `scorekeeping_access_level` | string | No | Who can keep score. |
| `streaming_access_level` | string | No | Who can access video. |
| `paid_access_level` | string or null | Yes | `"premium"` or null. |
| `settings` | object | No | Scorekeeping settings. Contains `scorekeeping.bats.innings_per_game` (int: 7 for travel ball, likely 9 for HS varsity). |
| `organizations` | array | No | Organizations this team belongs to. May be empty for opponents. |
| `ngb` | **JSON-encoded string** | No | NGB affiliation. **Requires double-parse.** `json.loads(team["ngb"])` |
| `team_avatar_image` | null | Yes | Avatar URL. May be null. |
| `team_player_count` | null | Yes | Always null observed. |
| `created_at` | ISO 8601 | No | Team creation timestamp. |
| `public_id` | string | No | Short alphanumeric public ID slug (e.g., `"a1GFM9Ku0BbF"`). |
| `url_encoded_name` | string | No | URL-safe name slug. |
| `archived` | boolean | No | Whether archived. |
| `record` | object | No | `{wins: int, losses: int, ties: int}`. |

## Key Fields for Coaching Analytics

- **`settings.scorekeeping.bats.innings_per_game`** (int) -- needed for stat normalization (K/9, BB/9). Travel ball: 7. High school varsity: likely 9.
- **`competition_level`** (string) -- useful for tier filtering between travel/recreational/high school.
- **`record`** object -- cumulative win/loss/tie record. Always present.
- **`public_id`** -- use this with the `/public/teams/{public_id}` endpoints and as input to `GET /teams/{team_id}/public-team-profile-id`.

## Example Response

```json
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
  "team_avatar_image": null,
  "team_player_count": null,
  "created_at": "2024-11-02T12:34:20.229Z",
  "public_id": "a1GFM9Ku0BbF",
  "url_encoded_name": "2025-summer-lincoln-rebels-14u",
  "archived": false,
  "record": {"wins": 61, "losses": 29, "ties": 2}
}
```

## Known Limitations

- `ngb` requires double-JSON-parsing (string containing JSON).
- `organizations` and `ngb` may be empty arrays for opponent teams -- this reflects actual data, not access restrictions.
- `team_player_count` is always null observed.
- Opponent team access confirmed for `pregame_data.opponent_id` from schedule. Usability with season-stats, players, and game-summaries endpoints is structurally consistent but not all variants have been independently confirmed.

**Discovered:** 2026-03-04. **Opponent validation confirmed:** 2026-03-04.
