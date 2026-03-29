# Operational Notes -- Priorities, Boxscore Facts, JWT Tips, Security

## Areas Not Yet Explored / High-Priority

- **`GET /search/opponent-import` RESPONSE BODY** -- endpoint confirmed 200 OK (both mobile and web profiles) but proxy only captures metadata, not JSON. Live curl needed. (Note: this endpoint is superseded by POST /search for programmatic use, but schema still undocumented.)
- **`GET /teams/{team_id}/import-summary` RESPONSE BODY** -- endpoint confirmed 200 OK but body not captured. Schema unknown.
- **LSB coaching account credentials** -- current credentials are travel ball only. LSB HS teams not visible.
- **`PATCH /players/{player_id}` schema** -- body and response format unknown.
- **`GET /organizations/{uuid}/game-summaries`** -- test with LSB org UUID when credentials available.
- **DELETE /teams/{team_id}/schedule/events/{event_id}** -- user "deleted a game" in this session but no DELETE was observed; either it uses a PATCH with a cancel/delete field or was not captured.

## Boxscore & Plays Endpoint Critical Facts

- **PLAYS URL param is `event_id`** (confirmed 2026-03-26 via fresh browser curl). `event_id` == `game_stream.game_id`, NOT `game_stream.id`. Our Python client was getting HTTP 500 because it used `game_stream.id`. Old doc caveat "NOT event_id" was wrong.
- **Boxscore URL param**: CLAUDE.md says `event_id`. Operational notes previously said `game_stream.id` -- trust CLAUDE.md. Needs verification via live curl.
- **Both endpoints share path pattern**: `/game-stream-processing/{event_id}/boxscore` and `/game-stream-processing/{event_id}/plays`
- **Asymmetric team key format**: own team key = public_id slug; opponent key = UUID (same for both endpoints)
- **Plays `team_players`**: array of player objects (NOT nested dict keyed by UUID). Includes `number` (jersey number). Confirmed 2026-03-26.
- **Boxscore groups**: `"lineup"` (batting: AB/R/H/RBI/BB/SO) and `"pitching"` (IP/H/R/ER/BB/SO)
- Boxscore Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`
- Plays Accept: `application/vnd.gc.com.event_plays+json; version=0.0.0`

## CLAUDE.md Context Layer Fix (2026-03-26) -- RESOLVED

Fixed by claude-architect: CLAUDE.md Data Model section now correctly states that both boxscore and plays
endpoints use `event_id`, and that `game_stream_id` links to game-streams endpoints.

## JWT Payload Decode Tips

`exp-iat < 1000` = client (10 min). `exp-iat < 50000` = access (~61 min web OR ~12 hours mobile). `exp-iat > 1000000` = refresh (14 days).

## Security Rules

Never display/log/store credentials. Use `{AUTH_TOKEN}` placeholders. Strip auth headers from raw responses.

**PII hotspots:** `/teams/{team_id}/users` (emails), `/users/{user_id}` (name+email), `/me/associated-players` (player names across teams).
