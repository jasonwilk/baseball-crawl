---
method: GET
path: /public/teams/{public_id}
status: CONFIRMED
auth: none
profiles:
  web:
    status: confirmed
    notes: No gc-token or gc-device-id required. Returns 200 OK without authentication.
  mobile:
    status: not_applicable
    notes: Public endpoint -- no auth profile distinction.
accept: "application/vnd.gc.com.public_team_profile+json; version=0.1.0"
gc_user_action: null
query_params: []
pagination: false
response_shape: object
response_sample: data/raw/public-team-profile-sample.json
raw_sample_size: "~1.2 KB"
discovered: "2026-03-04"
last_confirmed: "2026-07-25"
tags: [team, public]
related_schemas: []
see_also:
  - path: /public/teams/{public_id}/games
    reason: Game schedule and scores for this team (also no-auth)
  - path: /teams/{team_id}
    reason: Authenticated equivalent with UUID path and more fields
  - path: /teams/{team_id}/public-team-profile-id
    reason: UUID-to-public_id bridge (get public_id from a team UUID)
  - path: /teams/public/{public_id}/id
    reason: Reverse bridge -- public_id slug to UUID (requires auth despite /public/ path)
---

# GET /public/teams/{public_id}

**Status:** CONFIRMED LIVE -- 200 OK. **AUTHENTICATION: NOT REQUIRED.** Last verified: 2026-07-25.

Returns the public profile for a team identified by its `public_id` slug. No `gc-token` or `gc-device-id` required. This is the first unauthenticated endpoint confirmed in this API.

```
GET https://api.team-manager.gc.com/public/teams/{public_id}
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_id` | string | Alphanumeric public ID slug (e.g., `"xXxXxXxXxXxX"`). NOT a UUID. |

## Headers

```
Accept: application/vnd.gc.com.public_team_profile+json; version=0.1.0
User-Agent: Mozilla/5.0 ...
```

Do NOT include `gc-token` or `gc-device-id` headers on this request.

**The vendor `Accept` is INERT on this endpoint (negative observation, verified 2026-07-25).** Sending the vendor media type above plus `gc-app-name: web` versus sending neither produces **no difference in the response**: identical `content-length` across paired requests, zero paths present in only one variant, zero type mismatches, and every field byte-identical. Three further points of corroboration:

- The response `content-type` is `application/json; charset=utf-8` under **both** variants -- the server does not echo the vendor media type back.
- The response `Vary` header is `Origin,Accept-Encoding` -- notably **not** `Accept`. That is server-side confirmation that `Accept` does not select the representation.
- A same-headers **control** (two bare requests back-to-back) produced the same single differing leaf as the treatment -- `avatar_url`, which is re-signed per request by CloudFront. Excluding `avatar_url`, bare-vs-vendor diffs to zero differing leaves.

Conclusion: this endpoint does not content-negotiate **between the correct vendor type and no vendor type**. Across that pair the `version=0.1.0` pin is inert in both directions -- sending it cannot regress the response, and omitting it costs nothing. **Do not re-probe that pair.**

**Bound on the inertness claim, added 2026-07-26 -- "inert" covers correct-vs-absent ONLY, and does NOT mean any `Accept` is safe.** The 2026-07-25 experiment compared the *correct* vendor type against a *bare* request; it never sent a *wrong* one. A live probe on 2026-07-26 sent `application/vnd.gc.com.public_game:list+json; version=0.0.0` (a wrong resource type) to this endpoint and got a hard **HTTP 415**. So the three states are distinct and must not be collapsed:

| `Accept` sent | Result |
|---------------|--------|
| Correct vendor type (`public_team_profile`) | 200, byte-identical to bare |
| Absent / generic (`application/json, text/plain, */*`) | 200, byte-identical to vendor |
| **Wrong vendor resource type** | **415, no body** |

The `Vary: Origin,Accept-Encoding` evidence above remains correct and is not in tension with this: `Vary` describes which headers select among *representations the server will serve*, and says nothing about which requests it will *refuse*. GC validates the type before it negotiates.

(Contrast `GET /me/teams`, where a stale `Accept` *version* returns a false 403 -- see `.claude/rules/auth-module.md`. That trap does not apply here, but the 415 above does. See `../error-handling.md`, "415 on a Mismatched Vendor Accept Type".)

## Response

Single JSON object with team profile data.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | The `public_id` slug (NOT the UUID). The internal UUID is not exposed. |
| `name` | string | Team name |
| `sport` | string | `"baseball"` |
| `ngb` | **JSON-encoded string** | NGB affiliation. Same double-parse quirk as authenticated endpoints -- but see the empty-form caveat below: the "no affiliation" value is sometimes `""`, which is not valid JSON. |
| `location` | object | Team location (city, state, etc.) |
| `age_group` | string | **A polymorphic LEVEL field, not merely an age bracket** -- for school teams it carries an explicit varsity / junior varsity / freshman token. Values are drawn from one of three disjoint family vocabularies. See "The `age_group` level field" below. |
| `team_season` | object | Current season info: `season` (name), `year`, and `record` |
| `team_season.season` | **string** | Season NAME. A bare string -- **NOT an object**. Observed: `"spring"`, `"summer"`. Treat as an **OPEN vocabulary**, not a closed enum -- `"fall"` is documented on the authenticated endpoints. **Reliably present**: across 73 school-family opponent profiles the `team_season` object, its `season` key, and its `year` key were present and non-null on 73/73, with zero absent, null, or empty-string values (2026-07-25). |
| `team_season.year` | int | Season year (e.g., `2025`). **FLAT** sibling of `season` -- the correct year path is `team_season.year`; there is **no** `team_season.season.year` nesting. |
| `team_season.record` | object | Win/loss/tie record. Uses **singular keys**: `win`, `loss`, `tie` (NOT `wins`/`losses`/`ties` as in authenticated endpoints). |
| `avatar_url` | string | Signed CloudFront URL for team avatar. Will expire -- do not cache long-term. |
| `staff` | array | Array of plain name strings (e.g., `["Jane Doe", "John Roe"]`). No roles, no IDs. |

**Record key normalization:** Authenticated `GET /teams/{team_id}` uses plural keys (`wins`/`losses`/`ties`) in a top-level `record` object. This endpoint uses singular keys (`win`/`loss`/`tie`) inside `team_season.record`. Parsers must handle both shapes.

## The `age_group` level field

The field name is misleading. `age_group` is **not** free text and **not** merely an age bracket -- it is a polymorphic **level** field whose value is drawn from one of three disjoint vocabularies, selected by the team's `competition_level`. For school teams it names the varsity / junior varsity / freshman tier directly.

| Family | `competition_level` (authenticated endpoints only) | `age_group` values |
|---|---|---|
| **school** | `school` | `elementary`, `middle_12U`, `middle_13O`, `high_freshman`, `high_junior_varsity`, `high_varsity`, `college` |
| **travel** | `club_travel` | `NNU` brackets -- observed live: `8U`, `9U`, `10U`, `11U`, `12U`, `13U`, `14U`, `15U`, `18U` |
| **recreational** | `recreational` | Free-text ranges rendering as `"Between N - M"` (observed: `"Between 13 - 18"`) |

**Provenance of the school enum:** the school family is exhaustively enumerated in GameChanger's own public web bundle (`https://web.gc.com/static/js/index.*.js`, fetched unauthenticated), in the display mapper that switches on `competition_level === SCHOOL` and maps `age_group` to a display label, and in the team-creation picker that labels `high_freshman` / `high_junior_varsity` / `high_varsity` as "Freshman" / "Junior Varsity" / "Varsity". That bundle is the authoritative source for this enum -- re-fetch it (the filename hash changes per deploy; find it via `src=` in the team page HTML) rather than guessing values. The bracket and range families' literals are generated dynamically and are **not** in the bundle; those were observed empirically off live responses.

**`competition_level` is authenticated-ONLY.** It is absent from this public response (confirmed across 7 additional samples on 2026-07-25, key set identical in all). This mostly does not matter, because **`age_group` is self-disambiguating by shape**: a `high_*` or `middle_*` prefix implies school, an `NNU` form implies travel, and a `"Between N - M"` form implies recreational. A caller needing the level for a school team does not need the authenticated endpoint.

**The level token IS present for teams you do not manage (verified live 2026-07-25).** Resolution route: an authenticated opponents-list entry carrying `progenitor_team_id` -> `GET /teams/{progenitor_team_id}` for the `public_id` -> this endpoint with no `gc-token` and no `gc-device-id`.

- **25 non-managed opponent public profiles: 25/25 present and populated** (`high_junior_varsity` x19, `high_varsity` x6). Zero null, zero empty, zero absent, zero non-200.
- **Zero authenticated-vs-public mismatches across 73 paired fetches.** Every one of 73 distinct non-managed opponents was fetched BOTH via authenticated `GET /teams/{team_id}` and via this endpoint; `age_group` was identical in all 73 (`high_junior_varsity` x29, `high_varsity` x22, `high_freshman` x22), with 0 errors on either side. The public profile is a faithful mirror of the authenticated value, not a degraded copy.
- All three high-school values -- `high_varsity`, `high_junior_varsity`, `high_freshman` -- were each directly observed on at least one non-managed team.

An earlier 18-team sweep that saw only `high_freshman` was a **sampling artifact**: its population contained no high-school varsity teams. It was never evidence of an access restriction.

**Population rate: 0% absent.** Across **73 distinct opponents** of the operator's four school teams, `age_group` was populated 73/73 (100%) -- no empty strings, nulls, or missing keys. Combined with the earlier 18-team sweep that is 91 distinct teams with no gaps.

**Family mix is schedule-dependent -- do not overgeneralize from one schedule.** A high-school schedule is 100% school family (observed: `high_junior_varsity` x29, `high_varsity` x22, `high_freshman` x22; zero travel, zero recreational). The `NNU` and `"Between N - M"` values come from legion and summer travel schedules, which are a different population.

**Three limitations on interpreting the value:**

- **Operator-entered.** `age_group` is whatever the team's own coach selected when creating the team in GameChanger. It is authoritative about that selection, not about the team's actual league classification -- it can be wrong, stale, or left at a default. Treat it as a strong signal, never as ground truth.
- **The school family has no "reserve" tier.** The high-school vocabulary is three values. A program that fields four squads (freshman / reserve / junior varsity / varsity) cannot express that fourth tier here; both its freshman-level squads appear as `high_freshman`. Observed directly on the operator's own program.
- **Coverage is bounded upstream, by opponent ENTRY -- not by this field.** 61 of 144 visible opponent entries (**42%**) carry no `progenitor_team_id`: they were typed manually by the coach and have no reachable GC team, hence no `public_id` and no profile to read. That constrains opponent *resolution*, not the level signal. Conditioned on a team being reachable by `public_id` at all, population is 100% -- so do not quote a degraded coverage figure for this field on account of the 42%.

### How coaches actually populate the school values (measured 2026-07-25, n=73)

Measured across all 73 distinct coach-linked opponents of one high-school program's four teams (`high_junior_varsity` x29, `high_varsity` x22, `high_freshman` x22 -- 100% school family). Two behaviours matter to any consumer:

- **"Reserve" squads are mapped DOWN, never up.** GameChanger has no reserve tier, so a coach fielding one must pick something. Across **two independent populations** (spring school schedule and summer/legion schedule), **23 school-family teams** carry "Reserve"/"Reserves" in the name: **20 chose `high_freshman`, 3 chose `high_junior_varsity`, and 0 chose `high_varsity`.** The substitution is consistently toward the *lower* tier. A consumer using this field for anything safety-related (pitch-rest tiers, workload rules) should know the observed error direction is conservative, not permissive. (A further 17 Reserve-named teams in the summer population are travel/recreational family, where no high-school tier applies.)
- **On a SPRING school schedule the value is largely redundant with the team name -- but this does NOT hold generally.** All 73 spring opponents also carried an explicit level word in the name ("Varsity", "Junior Varsity"/"JV", "Freshman", "Reserve"); 72 of 73 carried a high-school tier word specifically.

  **Do not generalize that into "the name always carries the level."** A second measurement over a *summer* population (134 distinct coach-linked opponents of the same operator's five 2026 non-school teams) found **16 school-family teams, of which 3 carry NO level word in the name at all** -- and all 3 resolve to `unknown` under name-keyword parsing, i.e. the field is the *only* level signal available for them.

  The structural reason is worth knowing: those 3 are **school programs playing summer ball under a sponsor name**. Their team name is the sponsor, carrying neither a school name nor a tier word, while `age_group` still reports the true school tier. So the redundancy is a property of the *spring school schedule's naming convention*, not a property of the two signals.

The residual value of the field over name parsing, measured the same way on both populations:

| population | n (distinct linked) | classification would change | rate |
|---|---|---|---|
| spring school schedule | 73 | 3 | 4.1% |
| summer / legion schedule | 134 | 4 | 3.0% |

Spring: one team whose name reads as Legion but is `high_junior_varsity`, and two named "JV1" that a `\bjv\b` word-boundary match misses. Summer: the 3 sponsor-named school teams above (`unknown` -> a bound league), plus one resolving to the wrong league family. **Across both populations, 0 of 207 changes moved toward less rest** -- every change was either "no guidance -> guidance" or "looser -> stricter."

- **`season` does NOT track the family -- a school-family team can carry `season: "summer"`.** All 73 spring opponents returned `"spring"`, so within that population `season` is constant and carries no discriminating power. But the summer population contains **13 school-family teams with `season: "summer"`** (and 4 non-school teams with `season: "spring"`) -- and **every one of the three high-school values appears on a `"summer"` team**: `high_varsity` x7, `high_freshman` x5, `high_junior_varsity` x1. So the pairing is not merely possible in principle; each specific value has been observed with each season.

`season` and `age_group` are therefore **independent axes**: `season` names when the team plays, `age_group` names its level. **Do not use `season` to infer the family, or `age_group` to infer the season.** Season presence itself is reliable -- 0 absent across both populations.

**Scope note on the constancy observation, because it is the easiest thing here to over-read:** "all school-family teams carry `spring`" is true only of *one program's spring opponents*. It is NOT a property of school-value teams generally. A caution phrased as a general rule propagates further than a number does, because a number invites an audit and a caution does not -- so treat the constancy strictly as a per-population observation, never as a rule.

**Caveat on generalizing:** these are two schedules of one program in one season and one state. Naming conventions in particular are local. The two populations disagreed on exactly the property most tempting to over-generalize (whether the team name always carries the level), which is the reason both are reported here rather than one.

### Parser requirements

Measured across the 73-team sample on 2026-07-25:

- **No casing or whitespace variants.** Every school value was exactly lowercase-with-underscores (`value.lower() == value` and `value.strip() == value`).
- **No off-enum values observed.** Explicitly searched for and NOT found: `high_sophomore`, `high_jv`, `high_junior`, `varsity`, `jv`.
- **The recreational form rests on a single observation.** Only the literal `"Between 13 - 18"` has ever been seen. Do **not** treat `"Between N - M"` as a validated pattern.
- **The web-bundle enum is NOT provably exhaustive.** What was extracted is the display mapper's `switch` (7 school values) plus the creation picker (3 high-school options); the underlying enum *object* definition was never located, despite searching `index.js` and five other bundles. Two signs the set is open: the mapper has a `default:` branch, meaning GC itself handles unrecognized values, and the picker offers only 3 of the 7, so the other values must arrive via non-creation paths.

**Therefore a consumer MUST use an allowlist plus an explicit unknown fallback, and MUST NOT raise on an unrecognized value.**

**Not available from `POST /search`.** Search hits carry neither `age_group` nor `competition_level`. Re-verified 2026-07-25: 59 hits across 6 team-name queries, **zero** occurrences of either key. A hit is `{type, result}`, and the `result` object's full key set is `avatar_url, id, location, name, number_of_players, public_id, season, sport, staff` -- no level information of any kind. The public team profile is therefore the only cheap source for this field; the `public_id`-to-`gc_uuid` search bridge cannot supply it.

## Example Response

```json
{
  "id": "xXxXxXxXxXxX",
  "name": "Example Team 14U",
  "sport": "baseball",
  "ngb": "[\"usssa\"]",
  "location": {
    "city": "Anytown",
    "state": "NE"
  },
  "age_group": "14U",
  "team_season": {
    "season": "summer",
    "year": 2025,
    "record": {"win": 12, "loss": 8, "tie": 0}
  },
  "avatar_url": "https://media-service.gc.com/...",
  "staff": ["Coach Smith", "Coach Jones"]
}
```

### Example Response -- school family (the varsity level token)

Structure of a high-school varsity team's public profile. Note `age_group` carrying the level token, the absent `competition_level`, and the `""` empty form of `ngb`.

```json
{
  "id": "xXxXxXxXxXxX",
  "name": "Anytown Eagles Varsity",
  "sport": "baseball",
  "ngb": "",
  "location": {
    "city": "Anytown",
    "state": "XX"
  },
  "age_group": "high_varsity",
  "player_count": 18,
  "team_season": {
    "season": "spring",
    "year": 2026,
    "record": {"win": 12, "loss": 8, "tie": 0}
  },
  "avatar_url": "https://media-service.gc.com/example-avatar-url",
  "staff": ["Jane Doe", "John Roe"]
}
```

## Known Limitations

- `id` field in response is the `public_id` slug, NOT the UUID. The UUID is not exposed by this endpoint.
- Record uses singular keys (`win`/`loss`/`tie`), not plural (`wins`/`losses`/`ties`). Normalize on parse.
- `avatar_url` is a signed CloudFront URL that will expire. Do not cache long-term.
- `staff` is an array of name strings with no role or UUID information.
- `ngb` requires double-JSON-parsing -- **but has two distinct empty forms, and one of them is not valid JSON.** Observed 2026-07-25 across 7 teams: the literal string `"[]"` on 5, and the **empty string `""`** on 2. `json.loads("")` raises `JSONDecodeError`, so a naive double-parse crashes on the `""` form. Both forms mean "no governing body affiliation"; treat an empty or unparseable `ngb` as an empty list rather than an error. Note also that `"[]"` is truthy in Python, so a bare truthiness test on the raw string does not detect "no affiliation" either.
- `team_season.season` is a bare season-NAME string and `team_season.year` is a flat integer sibling -- the year is at `team_season.year`, NOT `team_season.season.year`. First noted 2026-07-07 from a cached sample; **confirmed live on 7 independent teams 2026-07-25**, all returning the flat shape `{"season": "spring", "year": 2026, "record": {"win": N, "loss": N, "tie": N}}`. Do not expect a nested `season` object here (the `POST /search` result's `season` object with `{name, year}` is a different endpoint's shape).
- The response key set is stable: `age_group, avatar_url, id, location, name, ngb, player_count, sport, staff, team_season` -- identical across all 7 teams sampled 2026-07-25.
- `team_season` reflects current season only; historical records not accessible via this endpoint.

**Discovered:** 2026-03-04. **Confirmed no-auth:** 2026-03-04. **Re-confirmed no-auth (7 non-managed opponent teams):** 2026-07-25.
