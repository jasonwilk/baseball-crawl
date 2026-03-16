# Operational Notes -- Priorities, Boxscore Facts, JWT Tips, Security

## Areas Not Yet Explored / High-Priority

- **`POST /search` BODY SCHEMA** -- request body and response body not captured. Live curl needed to see query field names and response structure.
- **`GET /search/opponent-import` RESPONSE BODY** -- endpoint confirmed 200 OK (both mobile and web profiles) but proxy only captures metadata, not JSON. Live curl needed.
- **`GET /teams/{team_id}/import-summary` RESPONSE BODY** -- endpoint confirmed 200 OK but body not captured. Schema unknown.
- **LSB coaching account credentials** -- current credentials are travel ball only. LSB HS teams not visible.
- **`PATCH /players/{player_id}` schema** -- body and response format unknown.
- **`GET /organizations/{uuid}/game-summaries`** -- test with LSB org UUID when credentials available.
- **DELETE /teams/{team_id}/schedule/events/{event_id}** -- user "deleted a game" in this session but no DELETE was observed; either it uses a PATCH with a cancel/delete field or was not captured.

## Boxscore Endpoint Critical Facts

- **URL param is `game_stream.id` from game-summaries** (NOT `event_id` or `game_stream.game_id`)
- **Asymmetric team key format**: own team key = public_id slug; opponent key = UUID
- **Groups**: `"lineup"` (batting: AB/R/H/RBI/BB/SO) and `"pitching"` (IP/H/R/ER/BB/SO)
- Accept: `application/vnd.gc.com.event_box_score+json; version=0.0.0`

## JWT Payload Decode Tips

`exp-iat < 1000` = client (10 min). `exp-iat < 50000` = access (~61 min web OR ~12 hours mobile). `exp-iat > 1000000` = refresh (14 days).

## Security Rules

Never display/log/store credentials. Use `{AUTH_TOKEN}` placeholders. Strip auth headers from raw responses.

**PII hotspots:** `/teams/{team_id}/users` (emails), `/users/{user_id}` (name+email), `/me/associated-players` (player names across teams).
