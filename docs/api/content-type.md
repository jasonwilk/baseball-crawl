# Content-Type Convention

## Vendor Media Types

GameChanger uses a **vendor-typed media type** convention for `Accept` headers on all GET endpoints. The format is:

```
application/vnd.gc.com.{resource_type}+json; version={version}
```

Where `{resource_type}` is a dot-separated identifier describing the resource, and `{version}` is a semantic version string (e.g., `0.1.0`, `0.2.0`).

Examples:
```
application/vnd.gc.com.team:list+json; version=0.10.0
application/vnd.gc.com.event:list+json; version=0.2.0
application/vnd.gc.com.game_summary:list+json; version=0.1.0
application/vnd.gc.com.event_box_score+json; version=0.0.0
```

List resources use the pattern `{type}:list+json`. Singleton resources use `{type}+json`.

## Exceptions to the Vendor Type Convention

Two endpoints do NOT use vendor-typed Accept headers:

| Endpoint | Accept value | Reason |
|----------|-------------|--------|
| `POST /auth` | `*/*` | Auth lifecycle endpoint. Uses `Content-Type: application/json; charset=utf-8` for the request body. |
| `GET /teams/{team_id}/schedule/events/{event_id}/player-stats` | `application/json, text/plain, */*` | Unique exception -- this endpoint accepts a generic JSON accept header rather than a vendor type. |

## Request Content-Type

For GET requests, no `Content-Type` request header is required. The web profile sends:

```
Content-Type: application/vnd.gc.com.none+json; version=undefined
```

This is the browser's default for XHR requests from `https://web.gc.com`. It is not required for API correctness but is included in the full browser-mimicking header set.

For `POST /auth`, the request body uses:

```
Content-Type: application/json; charset=utf-8
```

### POST Endpoints with Vendor-Typed Content-Type

Some POST endpoints use vendor-typed Content-Type headers for the request body (distinct from the Accept header):

| Endpoint | Content-Type | Accept | Notes |
|----------|-------------|--------|-------|
| `POST /search` | `application/vnd.gc.com.post_search+json; version=0.0.0` | `application/vnd.gc.com.search_results+json; version=0.0.0` | Content-Type uses underscore (`post_search`). Accept uses a different resource name (`search_results`). |
| `POST /clips/search` | See endpoint file | See endpoint file | |

Note: The Content-Type and Accept resource names can differ on the same endpoint (as with POST /search: `post_search` vs `search_results`). Always check the endpoint file for the confirmed values.

## Response Content-Type

All API responses return `Content-Type: application/json` regardless of the Accept header sent. The vendor-typed Accept header is used for API routing/versioning on the server side, not for altering response format.

One exception: `GET /organizations/{org_id}/pitch-count-report` returns **CSV** text, not JSON. This is the only non-JSON endpoint in the spec.

## Finding Accept Header Values

The `accept` field in each endpoint file's YAML frontmatter contains the correct value for that endpoint. When `accept: null` appears in frontmatter, the Accept header was not captured for that endpoint -- use the standard vendor-typed format as a best guess and confirm with a proxy capture.

See `headers.md` for a consolidated quick-reference table of all known Accept header values.
