# GameChanger API Documentation

This directory contains the complete GameChanger API reference for the baseball-crawl project. All documentation is split into individual per-endpoint files, with global reference files for shared concepts.

## How to Use This Documentation

**For agents**: Load only what you need. Start with this index to find the relevant endpoint file, then load that file for the full schema, caveats, and examples. Do not load the entire directory -- each file is self-contained.

**For humans**: The index below is the entry point. Click a link to open the endpoint file. Global reference files (authentication, headers, pagination, etc.) explain concepts that apply across all endpoints.

**Status values**:
- `CONFIRMED` -- Response schema documented from live curl or web proxy capture with full schema
- `OBSERVED` -- Endpoint observed in proxy logs; schema not fully confirmed
- `PARTIAL` -- Endpoint works under specific conditions only (e.g., requires special parameters)
- `NOT_API` -- Path returns HTTP 404 on the API domain; documented for reference

---

## Global Reference Files

| File | Description |
|------|-------------|
| [base-url.md](base-url.md) | Base URL, API domain, and host conventions |
| [auth.md](auth.md) | Authentication headers: gc-token, gc-device-id, token lifetime |
| [headers.md](headers.md) | Standard browser headers required on all requests |
| [content-type.md](content-type.md) | Accept and Content-Type header patterns |
| [pagination.md](pagination.md) | Cursor-based pagination: x-pagination header, x-next-page |
| [error-handling.md](error-handling.md) | HTTP error codes and error response shapes |

---

## Endpoint Index

Endpoints are grouped by domain. Within each group, sorted alphabetically by path. "Auth" column: `req` = gc-token required, `none` = no auth needed.

### Authentication

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| POST | [/auth](endpoints/post-auth.md) | CONFIRMED | req | Full auth lifecycle: login (4 steps), token refresh, logout. Three-token architecture (client/access/refresh). gc-signature algorithm cracked 2026-03-07; programmatic refresh confirmed working from Python. |
| POST | [/me/tokens/braze](endpoints/post-me-tokens-braze.md) | CONFIRMED | req | Third-party Braze push notification JWT (not relevant for data ingestion) |
| POST | [/me/tokens/firebase](endpoints/post-me-tokens-firebase.md) | CONFIRMED | req | Firebase push notification token registration -- HTTP 204, mobile only (not relevant for data ingestion) |
| POST | [/me/tokens/stream-chat](endpoints/post-me-tokens-stream-chat.md) | CONFIRMED | req | Stream Chat JWT for team messaging feature (not relevant for data ingestion) |

---

### My Account (`/me/*`)

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/me/advertising/metadata](endpoints/get-me-advertising-metadata.md) | CONFIRMED | req | Advertising ppid and targeting metadata (PII) |
| GET | [/me/archived-teams](endpoints/get-me-archived-teams.md) | CONFIRMED | req | Past-season teams for the authenticated user |
| GET | [/me/associated-players](endpoints/get-me-associated-players.md) | CONFIRMED | req | All player records across all teams -- key for longitudinal tracking |
| GET | [/me/external-calendar-sync-url/team/{team_id}](endpoints/get-me-external-calendar-sync-url-team-team_id.md) | OBSERVED | req | iCal/Google Calendar subscription URL for a team |
| GET | [/me/organizations](endpoints/get-me-organizations.md) | CONFIRMED | req | Organizations the user belongs to (requires pagination params) |
| GET | [/me/permissions](endpoints/get-me-permissions.md) | CONFIRMED | req | Permissions for a specific entity (requires entityId + entityType params) |
| GET | [/me/permissions/bulk](endpoints/get-me-permissions-bulk.md) | CONFIRMED | req | Bulk permission check for child entities under a parent (plain text "No permissions provided" when called without params) |
| GET | [/me/person-external-associations](endpoints/get-me-person-external-associations.md) | OBSERVED | req | External system associations for the user (legacy GC MongoDB IDs) |
| GET | [/me/related-organizations](endpoints/get-me-related-organizations.md) | CONFIRMED | req | Organizations accessible via team membership (requires pagination params) |
| GET | [/me/schedule](endpoints/get-me-schedule.md) | CONFIRMED | req | Cross-team unified schedule for all user teams |
| GET | [/me/scoped-features](endpoints/get-me-scoped-features.md) | OBSERVED | req | Feature flags scoped to the authenticated user (empty observed) |
| GET | [/me/subscription-information](endpoints/get-me-subscription-information.md) | CONFIRMED | req | Subscription tier summary (best_subscription + access_level) |
| GET | [/me/team-notification-settings/{team_id}](endpoints/get-me-team-notification-settings-team_id.md) | OBSERVED | req | Per-user notification preferences for a specific team |
| GET | [/me/team-tile/{team_id}](endpoints/get-me-team-tile-team_id.md) | CONFIRMED | req | Compact team summary with notification badge count |
| GET | [/me/teams](endpoints/get-me-teams.md) | CONFIRMED | req | Active teams for the authenticated user |
| GET | [/me/teams-summary](endpoints/get-me-teams-summary.md) | CONFIRMED | req | Lightweight archived team count and year range |
| GET | [/me/user](endpoints/get-me-user.md) | CONFIRMED | req | Authenticated user profile and subscription info |
| GET | [/me/widgets](endpoints/get-me-widgets.md) | CONFIRMED | req | App home screen widget configuration (live stream info) |
| DELETE | [/me/relationship-requests/{team_id}](endpoints/delete-me-relationship-requests-team_id.md) | OBSERVED | req | Unfollow a team / cancel a pending relationship request |
| PATCH | [/me/team-notification-settings/{team_id}](endpoints/patch-me-team-notification-settings-team_id.md) | OBSERVED | req | Update per-user notification preferences for a specific team. Per-field patching via {"updates":{...}} wrapper. Full schema confirmed 2026-03-12. |
| PATCH | [/me/user](endpoints/patch-me-user.md) | OBSERVED | req | Update authenticated user profile (write operation) |

---

### Teams -- Core (`/teams/{team_id}`)

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/teams/{team_id}](endpoints/get-teams-team_id.md) | CONFIRMED | req | Team metadata: name, location, competition level, record, settings |
| GET | [/teams/{team_id}/associations](endpoints/get-teams-team_id-associations.md) | CONFIRMED | req | Team associations (org memberships, federation links) |
| GET | [/teams/{team_id}/avatar-image](endpoints/get-teams-team_id-avatar-image.md) | CONFIRMED | req | Signed CloudFront URL for team avatar image |
| GET | [/teams/{team_id}/external-associations](endpoints/get-teams-team_id-external-associations.md) | CONFIRMED | req | Links to external systems (MaxPreps, USSSA -- empty observed) |
| GET | [/teams/{team_id}/public-team-profile-id](endpoints/get-teams-team_id-public-team-profile-id.md) | CONFIRMED | req | UUID-to-public_id bridge: resolves team UUID to public_id slug |
| GET | [/teams/{team_id}/public-url](endpoints/get-teams-team_id-public-url.md) | OBSERVED | req | Public web URL for the team's GameChanger profile page |
| GET | [/teams/{team_id}/relationships](endpoints/get-teams-team_id-relationships.md) | CONFIRMED | req | User-to-player relationship graph (parent/guardian mappings) |
| GET | [/teams/{team_id}/relationships/requests](endpoints/get-teams-team_id-relationships-requests.md) | CONFIRMED | req | Pending relationship requests for a team |
| GET | [/teams/{team_id}/scoped-features](endpoints/get-teams-team_id-scoped-features.md) | CONFIRMED | req | Feature flags scoped to a team (empty observed) |
| GET | [/teams/{team_id}/season-stats](endpoints/get-teams-team_id-season-stats.md) | CONFIRMED | req | Aggregate season stats for all players on a team |
| GET | [/teams/{team_id}/team-notification-setting](endpoints/get-teams-team_id-team-notification-setting.md) | CONFIRMED | req | Team event reminder notification setting (admin/team-wide view) |
| GET | [/teams/{team_id}/users](endpoints/get-teams-team_id-users.md) | CONFIRMED | req | Team user roster: id, status, name, email (no role field) |
| GET | [/teams/{team_id}/users/count](endpoints/get-teams-team_id-users-count.md) | CONFIRMED | req | Count of users on a team |
| GET | [/teams/{team_id}/web-widgets](endpoints/get-teams-team_id-web-widgets.md) | CONFIRMED | req | Widget configuration for the team web view |
| DELETE | [/teams/{team_id}/users/{user_id}](endpoints/delete-teams-team_id-users-user_id.md) | OBSERVED | req | Remove a user from a team / leave a team (self-removal confirmed, HTTP 204) |

---

### Teams -- Schedule & Events

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/teams/{team_id}/game-summaries](endpoints/get-teams-team_id-game-summaries.md) | CONFIRMED | req | Paginated game summaries with game_stream_id and scores |
| PATCH | [/teams/{team_id}/schedule/events/{event_id}](endpoints/patch-teams-team_id-schedule-events-event_id.md) | CONFIRMED | req | Update event details (opponent, time, location) -- write operation |
| POST | [/teams/{team_id}/schedule/events](endpoints/post-teams-team_id-schedule-events.md) | CONFIRMED | req | Create a new game or practice event (HTTP 201) -- write operation |
| GET | [/teams/{team_id}/schedule](endpoints/get-teams-team_id-schedule.md) | CONFIRMED | req | Full event schedule: games, practices, other events |
| GET | [/teams/{team_id}/schedule/event-series/{series_id}](endpoints/get-teams-team_id-schedule-event-series-series_id.md) | OBSERVED | req | Event series details (HTTP 404 observed) |
| GET | [/teams/{team_id}/schedule/events/{event_id}/player-stats](endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md) | CONFIRMED | req | Per-game per-player stats + spray charts for both teams (~106 KB) |
| GET | [/teams/{team_id}/schedule/events/{event_id}/rsvp-responses](endpoints/get-teams-team_id-schedule-events-event_id-rsvp-responses.md) | CONFIRMED | req | RSVP responses for a scheduled event (empty observed) |
| GET | [/teams/{team_id}/schedule/events/{event_id}/video-stream](endpoints/get-teams-team_id-schedule-events-event_id-video-stream.md) | CONFIRMED | req | Video stream metadata for a game event |
| GET | [/teams/{team_id}/schedule/events/{event_id}/video-stream/assets](endpoints/get-teams-team_id-schedule-events-event_id-video-stream-assets.md) | CONFIRMED | req | Video asset list for a game event |
| GET | [/teams/{team_id}/schedule/events/{event_id}/video-stream/live-status](endpoints/get-teams-team_id-schedule-events-event_id-video-stream-live-status.md) | CONFIRMED | req | Whether a game event is currently live-streaming |
| GET | [/teams/{team_id}/video-stream/assets](endpoints/get-teams-team_id-video-stream-assets.md) | CONFIRMED | req | All video assets for a team |
| GET | [/teams/{team_id}/video-stream/videos](endpoints/get-teams-team_id-video-stream-videos.md) | CONFIRMED | req | Video list for a team (distinct from /assets) |

---

### Teams -- Players & Opponents

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/teams/{team_id}/import-summary](endpoints/get-teams-team_id-import-summary.md) | CONFIRMED | req | Summary of importable stats for a team (checked before adding opponent) |
| GET | [/teams/{team_id}/lineup-recommendation](endpoints/get-teams-team_id-lineup-recommendation.md) | CONFIRMED | req | GC algorithm-generated batting order and field positions |
| GET | [/teams/{team_id}/opponent/{opponent_id}](endpoints/get-teams-team_id-opponent-opponent_id.md) | CONFIRMED | req | Single opponent registry entry by root_team_id |
| GET | [/teams/{team_id}/opponents](endpoints/get-teams-team_id-opponents.md) | CONFIRMED | req | Paginated opponent registry for a team |
| GET | [/teams/{team_id}/opponents/players](endpoints/get-teams-team_id-opponents-players.md) | CONFIRMED | req | Bulk opponent player roster with handedness (758 records observed) |
| GET | [/teams/{team_id}/share-with-opponent/opt-outs](endpoints/get-teams-team_id-share-with-opponent-opt-outs.md) | OBSERVED | req | Teams/games opted out of the "share stats with opponent" feature |
| PATCH | [/teams/{team_id}/opponent/{opponent_id}](endpoints/patch-teams-team_id-opponent-opponent_id.md) | CONFIRMED | req | Update opponent record (name, visibility) -- write operation |
| POST | [/teams/{team_id}/opponent/import](endpoints/post-teams-team_id-opponent-import.md) | CONFIRMED | req | Import an opponent team into the registry (HTTP 201) -- write operation |
| GET | [/teams/{team_id}/players](endpoints/get-teams-team_id-players.md) | CONFIRMED | req | Team player roster: name, number, avatar |
| GET | [/teams/{team_id}/players/{player_id}/stats](endpoints/get-teams-team_id-players-player_id-stats.md) | CONFIRMED | req | Per-game stats for one player across the season |

---

### Lineups & Player Attributes

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/bats-starting-lineups/{event_id}](endpoints/get-bats-starting-lineups-event_id.md) | CONFIRMED | req | Coach's entered starting lineup for a game (HTTP 403 for away games) |
| GET | [/bats-starting-lineups/latest/{team_id}](endpoints/get-bats-starting-lineups-latest-team_id.md) | CONFIRMED | req | Most recently entered starting lineup for a team |
| GET | [/player-attributes/{player_id}/bats](endpoints/get-player-attributes-player_id-bats.md) | CONFIRMED | req | Individual player handedness: batting side and throwing hand |

---

### Games & Streams

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/events/{event_id}](endpoints/get-events-event_id.md) | CONFIRMED | req | Single event detail with pregame_data and lineup_id |
| GET | [/events/{event_id}/best-game-stream-id](endpoints/get-events-event_id-best-game-stream-id.md) | CONFIRMED | req | Resolve event_id to game_stream_id for boxscore/plays access |
| GET | [/events/{event_id}/highlight-reel](endpoints/get-events-event_id-highlight-reel.md) | CONFIRMED | req | Structured highlight video playlist with pbp_id cross-references |
| GET | [/game-stream-processing/{game_stream_id}/boxscore](endpoints/get-game-stream-processing-game_stream_id-boxscore.md) | CONFIRMED | req | Per-player batting and pitching lines for both teams |
| GET | [/game-stream-processing/{event_id}/plays](endpoints/get-game-stream-processing-event_id-plays.md) | CONFIRMED | req | Pitch-by-pitch play log; works for non-managed teams (confirmed 2026-03-26); path param is event_id (NOT game_stream.id) |
| GET | [/game-streams/{game_stream_id}/events](endpoints/get-game-streams-game_stream_id-events.md) | CONFIRMED | req | Raw game event stream (event_data is JSON-encoded string) |
| GET | [/game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}](endpoints/get-game-streams-game_stream_id-game-stat-edit-collection-collection_id.md) | OBSERVED | req | Stat edit collection for a game (HTTP 404 observed -- route registered, no data returned) |
| GET | [/game-streams/gamestream-recap-story/{event_id}](endpoints/get-game-streams-gamestream-recap-story-event_id.md) | CONFIRMED | req | Game narrative recap (200 OK for some games; 404 for others). Accepts game_stream_id and team_id query params. |
| GET | [/game-streams/gamestream-viewer-payload-lite/{event_id}](endpoints/get-game-streams-gamestream-viewer-payload-lite-event_id.md) | CONFIRMED | req | Viewer event payload with stream_id resolved from event_id |
| GET | [/game-streams/insight-story/bats/{event_id}](endpoints/get-game-streams-insight-story-bats-event_id.md) | OBSERVED | req | Batting insight story (HTTP 404 observed) |
| GET | [/game-streams/player-insights/bats/{event_id}](endpoints/get-game-streams-player-insights-bats-event_id.md) | OBSERVED | req | Per-player batting insights (HTTP 404 observed) |

---

### Public Endpoints (No Auth Required)

These endpoints use `public_id` slugs and require **no** gc-token or gc-device-id.

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/public/game-stream-processing/{game_stream_id}/details](endpoints/get-public-game-stream-processing-game_stream_id-details.md) | CONFIRMED | none | Inning-by-inning line score and R/H/E totals for a game |
| GET | [/public/teams/{public_id}](endpoints/get-public-teams-public_id.md) | CONFIRMED | none | Team profile: name, location, record, staff, avatar |
| GET | [/public/teams/{public_id}/games](endpoints/get-public-teams-public_id-games.md) | CONFIRMED | none | Game schedule with final scores and opponent names |
| GET | [/public/teams/{public_id}/games/preview](endpoints/get-public-teams-public_id-games-preview.md) | CONFIRMED | none | Near-duplicate of /games (uses event_id; prefer /games) |

### Auth-Required Endpoints Under `/teams/public/` Path

**WARNING**: Despite the `/public/` path segment, these endpoints **require** gc-token authentication. Do not confuse with the truly public `/public/teams/` endpoints above.

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/teams/public/{public_id}/access-level](endpoints/get-teams-public-public_id-access-level.md) | CONFIRMED | req | Paid access tier for a team by public_id (AUTH REQUIRED) |
| GET | [/teams/public/{public_id}/id](endpoints/get-teams-public-public_id-id.md) | CONFIRMED | req | Reverse bridge: public_id slug → team UUID. **Own teams only -- HTTP 403 for opponent public_ids (confirmed 2026-03-09).** |
| GET | [/teams/public/{public_id}/players](endpoints/get-teams-public-public_id-players.md) | CONFIRMED | req | Player roster by public_id -- note inverted URL pattern (auth unverified) |

---

### Athlete Profiles (`/athlete-profile/{athlete_profile_id}`)

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/athlete-profile/{athlete_profile_id}](endpoints/get-athlete-profile-athlete_profile_id.md) | OBSERVED | req | Athlete profile metadata: name, handle, graduation year, positions |
| GET | [/athlete-profile/{athlete_profile_id}/career-stats](endpoints/get-athlete-profile-athlete_profile_id-career-stats.md) | OBSERVED | req | Cross-team career stats (31KB, longitudinal player tracking across all seasons) |
| GET | [/athlete-profile/{athlete_profile_id}/career-stats-association](endpoints/get-athlete-profile-athlete_profile_id-career-stats-association.md) | OBSERVED | req | Maps athlete profile to all player_ids across teams (lightweight ID map) |
| GET | [/athlete-profile/{athlete_profile_id}/players](endpoints/get-athlete-profile-athlete_profile_id-players.md) | OBSERVED | req | Player identities linked to athlete profile across teams (team name, jersey, games played) |

---

### Players & Users

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/players/{player_id}](endpoints/get-players-player_id.md) | OBSERVED | req | Individual player metadata: name, number, status, person_id |
| GET | [/players/{player_id}/profile-photo](endpoints/get-players-player_id-profile-photo.md) | OBSERVED | req | Player profile photo URL (HTTP 404 when no photo set) |
| PATCH | [/players/{player_id}](endpoints/patch-players-player_id.md) | OBSERVED | req | Update player attributes (batting side, throwing hand, jersey number -- write operation) |
| GET | [/users/{user_id}](endpoints/get-users-user_id.md) | CONFIRMED | req | User profile: id, status, first_name, last_name, email (PII) |
| GET | [/users/{user_id}/profile-photo](endpoints/get-users-user_id-profile-photo.md) | OBSERVED | req | User profile photo URL (HTTP 404 when no photo set) |

---

### Organization (`/organizations/{org_id}`)

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/organizations/{org_id}](endpoints/get-organizations-org_id.md) | OBSERVED | req | Organization metadata (base endpoint; schema unknown -- 304 responses only) |
| GET | [/organizations/{org_id}/avatar-image](endpoints/get-organizations-org_id-avatar-image.md) | OBSERVED | req | Organization avatar/logo image URL |
| GET | [/organizations/{org_id}/events](endpoints/get-organizations-org_id-events.md) | CONFIRMED | req | Cross-team event schedule at org level (empty for travel ball) |
| GET | [/organizations/{org_id}/game-summaries](endpoints/get-organizations-org_id-game-summaries.md) | CONFIRMED | req | Aggregated game summaries across org teams (empty observed) |
| GET | [/organizations/{org_id}/opponent-players](endpoints/get-organizations-org_id-opponent-players.md) | OBSERVED | req | Bulk opponent player roster at org level (107 players observed; HTTP 500 bug resolved as of 2026-03-11) |
| GET | [/organizations/{org_id}/opponents](endpoints/get-organizations-org_id-opponents.md) | OBSERVED | req | Opponent registry at organization level |
| GET | [/organizations/{org_id}/pitch-count-report](endpoints/get-organizations-org_id-pitch-count-report.md) | CONFIRMED | req | Pitcher pitch counts as CSV (not JSON) for the past 7 days |
| GET | [/organizations/{org_id}/scoped-features](endpoints/get-organizations-org_id-scoped-features.md) | CONFIRMED | req | Feature flags scoped to organization (empty observed) |
| GET | [/organizations/{org_id}/standings](endpoints/get-organizations-org_id-standings.md) | CONFIRMED | req | Current-season standings with run differential and streaks |
| GET | [/organizations/{org_id}/team-records](endpoints/get-organizations-org_id-team-records.md) | CONFIRMED | req | Historical win/loss records for all org teams |
| GET | [/organizations/{org_id}/teams](endpoints/get-organizations-org_id-teams.md) | CONFIRMED | req | All teams in an org (requires pagination params or HTTP 500) |
| GET | [/organizations/{org_id}/users](endpoints/get-organizations-org_id-users.md) | OBSERVED | req | Users associated with the organization |

---

### Sync & Subscription

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/announcements/user/read-status](endpoints/get-announcements-user-read-status.md) | CONFIRMED | req | In-app announcement read status for the user |
| GET | [/me/subscription-information](endpoints/get-me-subscription-information.md) | CONFIRMED | req | Subscription summary (best_subscription, access_level) |
| GET | [/subscription/details](endpoints/get-subscription-details.md) | CONFIRMED | req | Full subscription with plan, billing info, and dates |
| GET | [/subscription/recurly/plans](endpoints/get-subscription-recurly-plans.md) | CONFIRMED | req | Available subscription plans with pricing |
| GET | [/sync-topics/me/updated-topics](endpoints/get-sync-topics-me-updated-topics.md) | CONFIRMED | req | Real-time sync poll cursor (PII in next_cursor field) |
| POST | [/sync-topics/topic-subscriptions](endpoints/post-sync-topics-topic-subscriptions.md) | OBSERVED | req | Subscribe to a sync topic (not relevant for ingestion) |
| POST | [/sync-topics/updates](endpoints/post-sync-topics-updates.md) | OBSERVED | req | Batch sync update push (not relevant for ingestion) |

---

### Search

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/search/history](endpoints/get-search-history.md) | CONFIRMED | req | Recent team search history with UUID and public_id values |
| GET | [/search/opponent-import](endpoints/get-search-opponent-import.md) | CONFIRMED | req | GC UI opponent import search (search-as-you-type). Superseded by POST /search for programmatic opponent resolution (E-168). |
| POST | [/search](endpoints/post-search.md) | CONFIRMED | req | General-purpose team search (web + mobile). Full request/response schema documented. Used for opponent resolution (admin + automated fallback). |
| POST | [/search/history](endpoints/post-search-history.md) | CONFIRMED | req | Record a search history entry (called when user selects a search result). Mobile only, schema unknown. |

---

### Video & Clips

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| POST | [/clips/search](endpoints/post-clips-search.md) | CONFIRMED | req | Video clip search -- full request/response schema documented 2026-03-11. Supports event and player search modes. |
| POST | [/clips/search/v2](endpoints/post-clips-search-v2.md) | OBSERVED | req | Video clip search /v2 path (observed once; /clips/search now confirmed for both web and mobile) |

---

### Places & Calendar

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| GET | [/places/{place_id}](endpoints/get-places-place_id.md) | OBSERVED | req | Google Places-style venue lookup: address, lat/long, location name |
| GET | [/ics-calendar-documents/user/{user_id}.ics](endpoints/get-ics-calendar-documents-user-user_id-ics.md) | OBSERVED | req | iCal (RFC 5545) export of user's full schedule across all teams (non-JSON response) |

---

### Write Operations (Teams)

| Method | Path | Status | Auth | Description |
|--------|------|--------|------|-------------|
| POST | [/teams/{team_id}/follow](endpoints/post-teams-team_id-follow.md) | OBSERVED | req | Follow a team as the authenticated user (HTTP 204). Following unlocks the reverse bridge (GET /teams/public/{public_id}/id) for that team -- without following, the bridge returns HTTP 403 (confirmed 2026-03-12, two independent tests). **NOT required for the scouting pipeline** -- the public-endpoint scouting chain (schedule, roster, boxscores) works without following (confirmed 2026-03-12). |

See also: `DELETE /teams/{team_id}/users/{user_id}` and `DELETE /me/relationship-requests/{team_id}` under Teams -- Core and My Account respectively (the unfollow sequence).

---

### Web Routes (Not API Endpoints)

These URL patterns return HTTP 404 on `api.team-manager.gc.com`. They are web app routes served by `web.gc.com`. See [web-routes-not-api.md](endpoints/web-routes-not-api.md) for the full list and explanation.

---

## Flows

Multi-endpoint integration guides documenting how endpoints chain together for common tasks.

| Flow | Description |
|------|-------------|
| [opponent-resolution.md](flows/opponent-resolution.md) | Resolve opponents from the authenticated API to public_id slugs for unauthenticated access |
| [opponent-scouting.md](flows/opponent-scouting.md) | **Primary scouting path**: public_id → schedule (no auth) + roster + boxscores (gc-token) + local season aggregates. No UUIDs, no following required. |

---

## Completeness Check

| Count | Source |
|-------|--------|
| **121** | Files in `docs/api/endpoints/` (120 endpoint files + web-routes-not-api.md reference) |
| **121** | Endpoint rows in this index |
| **89** | E-062-R-01 spike inventory count (88 endpoints + 1 web-routes reference file) |

Notes:
- 1 new endpoint (`POST /me/tokens/braze`) added 2026-03-07. E-062 baseline was 89.
- 4 new endpoints added 2026-03-09 (session 2026-03-09_061156): `GET /search/opponent-import`, `POST /clips/search/v2`, `PATCH /players/{player_id}`, `GET /game-streams/{game_stream_id}/game-stat-edit-collection/{collection_id}`.
- 8 new endpoints added 2026-03-09 (session 2026-03-09_062610, mobile): `POST /teams/{team_id}/opponent/import`, `PATCH /teams/{team_id}/opponent/{opponent_id}`, `GET /teams/{team_id}/import-summary`, `POST /teams/{team_id}/schedule/events`, `PATCH /teams/{team_id}/schedule/events/{event_id}`, `POST /me/tokens/firebase`, `POST /me/tokens/stream-chat`, `POST /clips/search`.
- 2 new endpoints added 2026-03-09 (session 2026-03-09_063531, mobile search): `POST /search`, `POST /search/history`.
- 6 new endpoints added 2026-03-12 (session 2026-03-12_034919, web + mobile follow/unfollow flow): `DELETE /me/relationship-requests/{team_id}`, `DELETE /teams/{team_id}/users/{user_id}`, `GET /me/team-notification-settings/{team_id}`, `PATCH /me/team-notification-settings/{team_id}`, `GET /teams/{team_id}/share-with-opponent/opt-outs`, `GET /organizations/{org_id}`.
