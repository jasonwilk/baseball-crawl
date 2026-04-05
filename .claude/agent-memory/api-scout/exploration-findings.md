# API Exploration Findings

Last updated: 2026-03-16

Detailed findings from proxy sessions and API exploration beyond the core credential and endpoint basics.

## 2026-03-12 Key Findings (session 2026-03-12_034919, MOBILE)

**CRITICAL: Follow-gating CONFIRMED (two independent tests, 2026-03-12).** `POST /teams/{team_id}/follow` is a prerequisite for the reverse bridge:
- Reverse bridge WITHOUT following → HTTP 403 Forbidden
- Reverse bridge AFTER following as fan → HTTP 200 OK with UUID

This means the opponent scouting pipeline must call `POST /teams/{team_id}/follow` before resolving an opponent's public_id via `GET /teams/public/{public_id}/id`.

**Unfollow is a two-step sequence:**
1. `DELETE /teams/{team_id}/users/{user_id}` (HTTP 204) -- self-removal; Accept = `vnd.gc.com.none+json; version=0.0.0`
2. `DELETE /me/relationship-requests/{team_id}` (HTTP 200, body "OK", text/plain) -- cancels pending request

**Accept headers and schemas confirmed for previously-incomplete endpoints:**
- `GET /teams/{team_id}/share-with-opponent/opt-outs`: `vnd.gc.com.share_with_opponent_opt_outs+json; version=0.0.0`. Response is `[]` when empty.
- `PATCH /me/team-notification-settings/{team_id}`: Content-Type = `vnd.gc.com.patch_user_team_notification_settings+json; version=0.0.0`. Uses `{"updates":{...}}` per-field wrapper. Response echoes full settings object with all boolean/null notification fields.

**iOS app version bumped to 2026.9.0** (was 2026.8.0, iOS 26.3.0 → 26.3.1). Updated `docs/api/headers.md`.

## iOS App Identity (updated 2026-03-12)

- **Odyssey app UA (UPDATED):** `Odyssey/2026.9.0 (com.gc.teammanager; build:0; iOS 26.3.1) Alamofire/5.9.0` (was 2026.8.0/iOS 26.3.0 prior to session 2026-03-12_034919)
- **gc-app-version on iOS (UPDATED):** `2026.9.0.0` (was `2026.8.0.0`; web app value is `0.0.0`)
- **Media CDN hostnames:** `media-service.gc.com` (signed image delivery) and `vod-archive.gc.com` (AWS IVS video archive).

## Opponent ID Hierarchy (CONFIRMED AND EXPANDED 2026-03-09)

Three IDs per opponent from `GET /teams/{team_id}/opponents`, each used with DIFFERENT endpoints:

| ID | Used With |
|----|-----------|
| `root_team_id` | /opponent/{id}, /teams/{root_team_id}/players, /teams/{root_team_id}/avatar-image |
| `progenitor_team_id` | GET /teams/{progenitor_team_id} -- FULL access to ALL /teams/{id}/* endpoints |
| `public_id` | All /public/teams/{public_id} endpoints |

**KEY DISCOVERY (session 2026-03-09_063531):** `progenitor_team_id` gives FULL access to the opponent's team data via all `/teams/{team_id}/*` endpoints:
- `/teams/{progenitor_team_id}` -- team metadata
- `/teams/{progenitor_team_id}/game-summaries` -- all their games
- `/teams/{progenitor_team_id}/schedule` -- full schedule
- `/teams/{progenitor_team_id}/schedule/events/{event_id}/player-stats` -- per-game player stats (55 calls all 200!)
- `/teams/{progenitor_team_id}/season-stats` -- season aggregates
- `/teams/{progenitor_team_id}/players` -- roster
- `/teams/{progenitor_team_id}/opponents` -- their opponents
- `/teams/{progenitor_team_id}/opponents/players` -- all their opponent player data
- `/teams/{progenitor_team_id}/users` -- team users
- `/teams/{progenitor_team_id}/associations` -- org memberships

This means: by obtaining an opponent's `progenitor_team_id` from search results or our own opponents list, we have the SAME data access for any team as we do for our own teams. This is the foundation of the entire scouting data pipeline.

**Nighthawks Navy AAA 14U example:** root=`bd05f3d5-...`, progenitor=`14fd6cb6-...`, public_id=`smgRExWHuBJJ`

**CORRECTION (2026-03-09):** Previous docs incorrectly said "use progenitor_team_id for /players and /avatar-image". That is WRONG. Use `root_team_id` for both. Endpoint files updated.

## 2026-03-09 Key Findings (session 2026-03-09_061156)

- **NEW: `POST /clips/search/v2`** -- video clip search POST body query. CT: `application/vnd.gc.com.video_clip_search_query+json; version=0.0.0`. Body/response schema unknown.
- **NEW: `PATCH /players/{player_id}`** -- update player attributes. CT: `application/vnd.gc.com.patch_player+json; version=0.1.0`. Body/response schema unknown.
- **NEW: `GET /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}`** -- HTTP 404 only. Route registered; purpose unclear (stat correction tracking?).
- **`/public/game-stream-processing/{id}/details` accepts event_id directly** -- confirmed 200 OK with event_id. No need for /best-game-stream-id lookup when using this endpoint.
- **`/teams/{id}/avatar-image` returns HTTP 404** (not 200 with null) when team has no avatar set.
- **`/bats-starting-lineups/{event_id}` confirmed 200 OK** for home game event_id `387c28f7-...` (2026-03-09).

## 2026-03-09 Key Findings (session 2026-03-09_062610, MOBILE)

**App version update:** iOS app upgraded to `2026.8.0` / `gc-app-version: 2026.8.0.0`. All mobile UA strings and header examples updated in `docs/api/headers.md`.

**Opponent Import Flow (fully documented):**
1. `GET /search/opponent-import` (search-as-you-type, 3 calls per user interaction)
2. `GET /teams/{opponent_uuid}/import-summary` (check available stats -- NEW endpoint)
3. `POST /teams/{my_team_id}/opponent/import` (create association -- NEW endpoint, HTTP 201)
4. `GET /teams/{my_team_id}/opponent/{opponent_id}` (fetch result)
5. `GET /teams/{opponent_id}/players` + `GET /player-attributes/{id}/bats` ×11 (populate roster)

**Game Creation Flow:** `POST /teams/{team_id}/schedule/events` (HTTP 201, NEW) followed within 8 seconds by `PATCH /teams/{team_id}/schedule/events/{event_id}` (HTTP 200, NEW) -- create-then-patch pattern.

**Mobile-only third-party token endpoints (startup sequence, not relevant for ingestion):**
- `POST /me/tokens/stream-chat` -- Stream.io chat JWT (HTTP 200)
- `POST /me/tokens/firebase` -- Firebase push notification device token (HTTP 204, no body)

**Mobile clip search:** iOS uses `POST /clips/search` (no /v2 suffix); web uses `POST /clips/search/v2`. Same content-type. Both documented.

**Write endpoint content-types confirmed:**
- `POST /opponent/import`: `application/vnd.gc.com.post_opponent_team_import+json; version=0.0.0`
- `PATCH /opponent/{id}`: `application/vnd.gc.com.patch_opponent_team+json; version=0.0.0` (resp: text/plain)
- `POST /schedule/events`: `application/vnd.gc.com.post_event+json; version=0.3.0`
- `PATCH /schedule/events/{id}`: `application/vnd.gc.com.patch_event+json; version=0.6.0` (resp: JSON)

## 2026-03-09 Key Findings (session 2026-03-09_063531, MOBILE SEARCH + OPPONENT NAVIGATION)

**NEW: `POST /search`** -- Main mobile GC app search. Content-type: `application/vnd.gc.com.post-search+json; version=0.0.0`. Query param: `start_at_page`. 6 hits (search-as-you-type for "nighthawks"). Body/response schema unknown.

**NEW: `POST /search/history`** -- Records a user's search selection. Content-type: `application/vnd.gc.com.add_search_history+json; version=0.0.0`. Response is text/plain HTTP 200. Called after user taps a result.

**MOBILE SEARCH FLOW confirmed:** `GET /search/history` (on open) → `POST /search` (repeated as user types) → `POST /search/history` (on selection) → navigate to team.

**OPPONENT FULL ACCESS via progenitor_team_id CONFIRMED:** The mobile app navigates into the Nighthawks team using `progenitor_team_id` (`14fd6cb6`) and calls ALL the same `/teams/{id}/*` endpoints as it does for own teams. 55 calls to `/schedule/events/{event_id}/player-stats` all returned HTTP 200. This is the core scouting data access pattern.

## 2026-03-11 Key Findings (session 2026-03-11_032625, WEB, full request+response)

**E-094 API constraints CONFIRMED again from this session:**
- `GET /teams/public/a1GFM9Ku0BbF/id` -- HTTP 200 (or 304, 200 on first hit) -- owned team (`a1GFM9Ku0BbF` = Lincoln Rebels 14U). Accept: `application/vnd.gc.com.team_id+json; version=0.0.0`
- `GET /teams/public/smgRExWHuBJJ/id` -- HTTP 403, body: "Forbidden" -- opponent/non-owned team (Nighthawks). Same Accept header. 8 separate calls, ALL returned Forbidden.
- This confirms: the reverse bridge returns 403 for non-owned teams. E-094's Technical Notes are correct.

**New gc-user-action values confirmed (added to headers.md):**
- `data_loading:event` -- used on /events/{id}, /schedule/events/{id}/video-stream, /rsvp-responses
- `data_loading:event_game_stats` -- used on /best-game-stream-id, /game-streams/{id}/events
- `data_loading:teams` -- used on /me/teams, /me/organizations, /bats-starting-lineups/latest
- `data_saving:opponents` -- used on POST /teams/{id}/opponent/import
- `search:opponent` -- used on GET /search/opponent-import

**video-stream Accept header confirmed:** `application/vnd.gc.com.schedule_event_video_stream+json; version=0.0.0`. Two new fields: `person_id` (string, empty), `active_asset_playback_url` (string, empty on ended streams).

**me/organizations Accept header:** Two versions in use simultaneously: `version=0.3.1` (no gc-user-action) and `version=0.3.2` (gc-user-action: data_loading:teams). Both return 401 without auth or 304 with fresh auth. Updated spec to 0.3.2.

**All other observed endpoints already documented.** This session confirmed existing spec rather than revealing new endpoints. The spec is comprehensive for the web profile.

## 2026-03-11 Key Findings (session 2026-03-11_034739, WEB)

**10 new endpoint files created** -- athlete-profile (4), places, ics-calendar, me/scoped-features, me/person-external-associations, players/{id}, post-teams-follow.

**SPEC CORRECTION: `POST /clips/search` body schema CONFIRMED.** Full request/response schema documented. The web app calls /clips/search (not /v2 as previously assumed). Two search modes: `select.kind: "event"` (team+event filter) and `select.kind: "player"` (player across games). Accept header is version=0.3.0 (not 0.0.0). `play_summary` and `perspective` fields use `${player_uuid}` placeholders requiring roster resolution.

**HTTP 500 bug resolved: `GET /organizations/{org_id}/opponent-players`** now returns HTTP 200 with web headers. 107 players observed. Previously required iOS headers to avoid 500.

**Athlete profile hierarchy:** `GET /me/athlete-profile` (list) → `GET /athlete-profile/{id}` (metadata) → `/career-stats` (31KB full career) or `/career-stats-association` (ID list only) or `/players` (team roster cards).

**Accept headers backfilled** for 15+ existing endpoints that previously had `accept: null`.

**`POST /teams/{team_id}/follow`** -- HTTP 204 No Content, no body. Both Accept and Content-Type are `vnd.gc.com.none+json; version=0.0.0`.

**`GET /places/{place_id}`** -- Google Places ID lookup. Returns address, lat/long, location_name, types[]. Used for venue display.

**`GET /ics-calendar-documents/user/{user_id}.ics`** -- Non-JSON endpoint. Accept: `text/calendar`. Returns RFC 5545 VCALENDAR. X-PUBLISHED-TTL: PT18000S (5 hours).

**`GET /me/scoped-features`** -- Returns `{"scoped_features": {}}`. Same schema as team/org scoped-features.

**`GET /me/person-external-associations`** -- Maps person_id to legacy MongoDB `external_id` with `external_organization: "gamechanger"`.

## 2026-03-12 Key Findings (session 2026-03-12_034919, WEB + MOBILE, followed team browsing)

**6 NEW endpoints documented** -- unfollow lifecycle (2 DELETEs), per-user notification settings (GET + PATCH), share-with-opponent opt-outs, org base metadata.

**UNFOLLOW SEQUENCE CONFIRMED (2-step):**
1. `DELETE /teams/{team_id}/users/{user_id}` (HTTP 204) -- self-removes from team. `accept: vnd.gc.com.none+json; version=0.0.0`.
2. `DELETE /me/relationship-requests/{team_id}` (HTTP 200, body: "OK" text/plain) -- cancels relationship request. `accept: vnd.gc.com.none+json; version=0.0.0`.
Then optionally: `POST /teams/{team_id}/follow` (HTTP 204) -- re-associates as fan.

**NOTIFICATION SETTINGS (per-user, per-team):**
- `GET /me/team-notification-settings/{team_id}` (3 hits, 304) -- per-user prefs (distinct from `/teams/{team_id}/team-notification-setting`, which is team-admin view).
- `PATCH /me/team-notification-settings/{team_id}` (12 hits web, 2 hits mobile) -- accept: `application/json; charset=utf-8` (unusual -- most GC endpoints use vendor type). Uses `{"updates": {...}}` wrapper body. Full schema in endpoint file.

**SHARE-WITH-OPPONENT OPT-OUTS:** `GET /teams/{team_id}/share-with-opponent/opt-outs` -- accept: `vnd.gc.com.share_with_opponent_opt_outs+json; version=0.0.0`. Response was `[]` (empty array). Item schema unknown. Moderate coaching relevance (explains missing stat data when opponents opt out of sharing).

**`GET /organizations/{org_id}` BASE ENDPOINT:** HTTP 304 (3 hits). Schema unknown. Org UUID in session: `04dc5d56-59ae-4257-9d66-bfd43ded50cc`.

**Session context:** operator browsed a followed non-owned team (UUID `468c0fe0-...`), unfollowed via the 2-step DELETE sequence, then re-followed. 363 total requests, 82 unique endpoints -- most already documented.

## HTTP 500 (pagination bugs)
- `/organizations/{org_id}/teams`, `/me/organizations`, `/me/related-organizations` -- try `?page_size=50` or `?start_at=0`.

## Confirmed HTTP 404 / 403 patterns
- `/bats-starting-lineups/{event_id}` -- HTTP 403 for away game event_id (scorer access only)
- `/teams/{team_id}/avatar-image` -- HTTP 404 when team has no avatar (not an error -- treat as "no avatar")
- `/teams/{team_id}/public-team-profile-id` -- HTTP 403 for opponent team UUIDs (own-team only)
- `/teams/public/{public_id}/id` -- HTTP 403 for opponent public_ids (own-team only)
- `/game-streams/insight-story/bats/{event_id}` and `/player-insights/bats/{event_id}` -- feature not available
