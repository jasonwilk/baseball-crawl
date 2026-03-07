# Base URL

## Primary API Domain

All authenticated and public API endpoints use the following base URL:

```
https://api.team-manager.gc.com
```

Every path in the endpoint files is relative to this base. Example:

```
GET https://api.team-manager.gc.com/me/teams
GET https://api.team-manager.gc.com/teams/{team_id}/schedule
GET https://api.team-manager.gc.com/public/teams/{public_id}
```

## Additional Domains

Two media/video delivery hostnames were observed in proxy captures. These are **not API domains** and are not used for data ingestion:

| Hostname | Purpose |
|----------|---------|
| `media-service.gc.com` | Media asset delivery via AWS CloudFront signed URLs (avatars, images). 200 and 403 responses observed (403 = expired signature). |
| `vod-archive.gc.com` | AWS IVS video archive for recorded game video (HLS `.m3u8` playlists, `.ts` segments, thumbnails). |

## Web App Domain

The web application frontend is served at `https://web.gc.com`. Season-slug URL patterns observed in proxy captures (e.g., `GET /teams/{public_id}/{season-slug}/season-stats`) returned HTTP 404 on the API domain. These are web frontend routes, not API endpoints. See `endpoints/web-routes-not-api.md` for details.

## API Delivery Infrastructure

The API is served through AWS CloudFront CDN. Observed response headers confirm this:

```
x-cache: Miss from cloudfront
via: 1.1 <cloudfront-node>
x-amz-cf-pop: <CloudFront POP>
x-amz-cf-id: <CloudFront request ID>
```

ETags are returned on some responses (e.g., game-summaries). Conditional requests using `If-None-Match` have not been tested but could support efficient polling. The `x-server-epoch` response header carries the server's Unix timestamp in seconds.
