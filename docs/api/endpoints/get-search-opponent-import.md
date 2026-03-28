---
method: GET
path: /search/opponent-import
status: CONFIRMED
auth: required
profiles:
  web:
    status: confirmed
    notes: >
      21 hits returning HTTP 200 observed in proxy session 2026-03-09_062059 while
      user browsed the Nighthawks Navy AAA 14U opponent team page and GC performed
      live search to resolve/import teams as opponents. Full query parameter set
      documented from OPTIONS preflight. Response content-type: application/json.
  mobile:
    status: observed
    notes: >
      Captured from iOS app (session 2026-03-09_062610). 3 hits, all HTTP 200.
      Accept: application/vnd.gc.com.none+json; version=0.0.0. Same query params
      as web: age_group, city, competition_level, country, name, season, sport,
      start_at, state, year. Search-as-you-type pattern confirmed (3 calls within
      7 seconds). Called during opponent import flow before POST /opponent/import.
accept: "application/vnd.gc.com.none+json; version=undefined"
gc_user_action: "team_import:search_opponent"
query_params:
  - name: name
    required: false
    description: >
      Team name search string. The primary search field -- the user types a team
      name and the GC UI fires repeated requests (21 hits in one session) as the
      user types (debounced search-as-you-type pattern).
  - name: sport
    required: false
    description: >
      Sport filter. Observed values: "baseball" (from context). Likely filters
      results to a specific sport.
  - name: age_group
    required: false
    description: >
      Age group filter for the team search. Examples: "14U", "16U", "18U", "varsity".
      Narrows results to teams of the appropriate age bracket.
  - name: competition_level
    required: false
    description: >
      Competition level filter. Examples: "recreational", "competitive", "elite".
      Corresponds to the team's registered competition tier.
  - name: season
    required: false
    description: >
      Season filter. Likely a season slug such as "spring", "summer", "fall" or a year.
  - name: year
    required: false
    description: >
      Year filter. Integer year (e.g., 2024, 2025). Narrows results to teams active
      in that season year.
  - name: city
    required: false
    description: >
      City filter for team location. Narrows results to teams in a specific city.
  - name: state
    required: false
    description: >
      State/province filter. Narrows results to teams in a specific state.
  - name: country
    required: false
    description: >
      Country filter. Narrows results to teams in a specific country.
  - name: search_source
    required: false
    description: >
      Source context identifier for the search. Observed in OPTIONS preflight.
      Likely a tracking/analytics field indicating what UI context triggered the
      search (e.g., "import_opponent", "team_search").
  - name: include_avatar
    required: false
    description: >
      Boolean flag. When true, each result includes a pre-signed avatar_url for
      the team's logo/avatar. When false or absent, avatar data may be omitted
      to reduce response size.
  - name: start_at
    required: false
    description: >
      Pagination cursor -- the record offset to start from. Observed as a query
      key in OPTIONS preflight. Used for paginating through large result sets.
pagination: true
response_shape: array
response_sample: null
raw_sample_size: "~125 results inferred (125 team UUIDs fetched by GC UI after search)"
discovered: "2026-03-09"
last_confirmed: "2026-03-09"
tags: [search, team, opponent, bulk]
caveats:
  - >
    RESPONSE BODY NOT CAPTURED: The proxy log captures endpoint metadata (path,
    query keys, status codes) but not response bodies. The full JSON schema is
    inferred from secondary evidence: after 21 search-as-you-type calls returned
    200, the GC UI proceeded to fetch GET /teams/{uuid}/avatar-image and
    GET /teams/{uuid}/players for ~125 unique team UUIDs -- strongly indicating
    the search response returns an array of team objects each with a UUID field.
  - >
    SEARCH-AS-YOU-TYPE: The GC UI fires 21 separate requests in rapid succession
    (timestamps ~06:21:13 to ~06:21:15, ~2 second window), consistent with
    debounced search-as-you-type behavior as the user types a team name. Each
    request refines the query.
  - >
    CRITICAL FOR OPPONENT RESOLUTION: This endpoint is how GC resolves opponent
    teams when a coach imports opponents. It is the automated equivalent of a
    coach manually looking up an opponent team in the GC search UI. This makes
    it the key endpoint for automated opponent discovery by team name.
  - >
    AUTH REQUIRED: Despite not being under /me/ or /teams/{uuid}/, this endpoint
    requires gc-token authentication. The response content-type is plain
    application/json (not a vendor content-type), which is unusual.
see_also:
  - path: /search/history
    reason: User's recent search history -- contains team IDs from prior searches
  - path: /teams/public/{public_id}/id
    reason: Reverse bridge (public_id -> UUID) -- useful after getting public_id from search results
  - path: /teams/{team_id}/opponents
    reason: Opponent registry -- teams added via search are tracked here
  - path: /teams/{team_id}/opponents/players
    reason: Bulk opponent player data -- populated after opponent is imported
---

# GET /search/opponent-import

**Status:** CONFIRMED LIVE -- 200 OK. **Response body schema not yet captured.** Last verified: 2026-03-09.

> **Note (E-168):** This endpoint is no longer the primary search mechanism for opponent resolution in our pipeline. As of E-168, both the admin resolve workflow and the automated opponent resolver use [`POST /search`](post-search.md) instead, which has a fully documented request/response schema. This endpoint remains available in the GC UI for the "add opponent" import flow.

The team search endpoint used by the GC UI when a coach searches for opponent teams to import. This is a search-as-you-type endpoint -- the UI fires requests on each keystroke (debounced).

**Coaching relevance:** This endpoint enables search of any team in the GameChanger database by name, sport, age group, location, and season. For programmatic opponent resolution, prefer [`POST /search`](post-search.md) which has a confirmed response schema.

```
GET https://api.team-manager.gc.com/search/opponent-import
```

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | no | Team name search string (primary search field) |
| `sport` | string | no | Sport filter (e.g., `"baseball"`) |
| `age_group` | string | no | Age group (e.g., `"14U"`, `"varsity"`) |
| `competition_level` | string | no | Competition level (e.g., `"competitive"`, `"elite"`) |
| `season` | string | no | Season slug (e.g., `"summer"`, `"fall"`) |
| `year` | integer | no | Season year (e.g., `2025`) |
| `city` | string | no | City name filter |
| `state` | string | no | State/province filter |
| `country` | string | no | Country filter |
| `search_source` | string | no | UI context tag for analytics (e.g., `"import_opponent"`) |
| `include_avatar` | boolean | no | Include avatar URLs in results when `true` |
| `start_at` | integer | no | Pagination offset (cursor into result list) |

## Inferred Response Schema

**NOTE:** Response body not captured from proxy (proxy logs metadata only). Schema inferred from secondary evidence: the GC UI fetched 125 unique team UUIDs after receiving search results, strongly indicating the response contains an array of team objects. Based on the pattern observed in `/search/history` results, each team object likely contains:

| Field | Type | Description (inferred) |
|-------|------|------------------------|
| `id` | UUID | Team UUID |
| `public_id` | string | Team public_id slug |
| `name` | string | Team display name |
| `sport` | string | Sport type |
| `season` | object | Season info: `{name, year}` |
| `location` | object | Location info: `{city, state, country}` |
| `age_group` | string | Age group (inferred from query param existence) |
| `competition_level` | string | Competition level (inferred from query param existence) |
| `avatar_url` | string or null | CloudFront-signed avatar URL (present when `include_avatar=true`) |
| `staff` | array | Staff/coach names |
| `number_of_players` | integer | Player count |

**This schema must be verified by capturing the actual response body.**

## Secondary Evidence: Post-Search Behavior

After the 21 search calls completed, the GC UI immediately fetched:
- `GET /teams/{uuid}/avatar-image` for ~125 team UUIDs (some returned 404)
- `GET /teams/{uuid}/players` for the same ~125 UUIDs

This pattern confirms:
1. The response contains team UUIDs
2. The result set contained approximately 125 teams
3. The GC UI uses the UUIDs to fetch additional details about each result

## Usage Pattern

The GC UI fires this endpoint as a search-as-you-type query:

```
# Example: Searching for "Nighthawks Navy" baseball 14U teams
GET /search/opponent-import?name=Night&sport=baseball&age_group=14U&include_avatar=true
GET /search/opponent-import?name=Nighthawks&sport=baseball&age_group=14U&include_avatar=true
GET /search/opponent-import?name=Nighthawks+N&sport=baseball&age_group=14U&include_avatar=true
```

## Coaching Use Cases

1. **Automated opponent discovery**: Search by opponent team name to find their team UUID for subsequent authenticated API calls.
2. **Roster pre-population**: After getting team UUID, use `/teams/{team_id}/players` to get their player list before a game.
3. **Multi-season opponent tracking**: Search with `year` parameter to find the same team across multiple seasons.

**Discovered:** 2026-03-09 (proxy session 2026-03-09_062059). **Confirmed:** 2026-03-09.

**PRIORITY: Capture actual response body** -- execute a GET with a known team name and inspect the JSON shape. This endpoint may be the most strategically important discovery for the opponent scouting pipeline.
