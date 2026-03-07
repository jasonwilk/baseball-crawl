---
status: NOT_API
discovered: "2026-03-07"
last_confirmed: "2026-03-07"
tags: [web-routes]
---

# Web Routes -- Not API Endpoints

**Status:** HTTP 404 on `api.team-manager.gc.com`. These are web app routes, not API endpoints.

The following URL patterns were observed in the 2026-03-07 proxy capture but returned HTTP 404 when tested against `api.team-manager.gc.com`. They appear to be **web app routes** served by `https://web.gc.com`, not the GameChanger REST API.

The proxy capture likely intercepted web-frontend navigation requests (browser page loads) rather than XHR API calls. These paths are NOT available on the API domain.

## Routes Observed

| Pattern | Notes |
|---------|-------|
| `GET /teams/{public_id}/{season-slug}/opponents` | Season-scoped opponent list |
| `GET /teams/{public_id}/{season-slug}/schedule/{event_id}/plays` | Play-by-play view (web UI) |
| `GET /teams/{public_id}/{season-slug}/season-stats` | Season stats page (web UI) |
| `GET /teams/{public_id}/{season-slug}/team` | Team page (web UI) |
| `GET /teams/{public_id}/{season-slug}/tools` | Tools page (web UI) |
| `GET /teams/{public_id}/players/{player_id}` | Player profile page (web UI) |
| `GET /public/teams/{public_id}/live` | Live game page (web UI) |

## Path Parameter Notes

- `{public_id}`: Short alphanumeric team slug (e.g., `"a1GFM9Ku0BbF"`). Same slug used in authenticated and public API endpoints.
- `{season-slug}`: A season identifier string (e.g., `"2024-fall"` or similar). Format not confirmed -- not tested further since these paths return 404 on the API domain.
- `{event_id}`: Schedule event UUID.

## Interpretation

These patterns follow a web app URL structure (`/teams/{slug}/{season}/...`) that matches how `web.gc.com` organizes team pages for browser navigation. When the proxy captured these requests, the browser was likely navigating to web app pages, and the web app's service worker or frontend router issued these as prefetch or navigation requests intercepted by mitmproxy.

**For stat data**: Use the authenticated API endpoints which are confirmed to work on `api.team-manager.gc.com`:
- Season stats: `GET /teams/{team_id}/season-stats` (authenticated)
- Per-game plays: `GET /game-stream-processing/{game_stream_id}/plays` (authenticated)
- Opponent list: `GET /teams/{team_id}/opponents` (authenticated)

**Discovered:** 2026-03-07. **Confirmed 404 on API domain:** 2026-03-07.
