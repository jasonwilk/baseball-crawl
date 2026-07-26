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

## A Wrong Vendor Type Gets 415 (a generic one does not)

_Verified live 2026-07-26 on `GET /public/teams/{public_id}/games` and `GET /public/teams/{public_id}` -- both public, no-auth. Full evidence table in `error-handling.md`._

An `Accept` naming the **wrong resource type** is rejected with a hard **HTTP 415**. There is no fallback to a default representation and no silent ignoring of the header.

A **generic** `Accept` (`application/json, text/plain, */*`) returns a normal **200** with the full body. So the 415 fires on a *mismatch*, not on the absence of a vendor type.

Two consequences:

- **A 415 means "check your Accept header."** It looks exactly like a removed or gated endpoint, so it is easy to misdiagnose. The resource type is often not guessable from the path -- the games endpoint wants `public_team_schedule_event`, not the `public_game` a reader would guess.
- **Pinning a vendor type is more brittle than not pinning one.** A pin that goes stale hard-fails; a generic header cannot. Pins do buy server-side version determinism, so this is a trade rather than a case for dropping them -- but each pin is a maintenance obligation, and a *wrong* pin is worse than *no* pin.

Note that a stale **version** on the *right* type behaves differently -- it returns **403**, not 415 (the false-403 trap; see `error-handling.md` and `.claude/rules/auth-module.md`). Both are Accept problems wearing different status codes.

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

This applies to requests GC **accepts**. It does not mean the Accept header is optional or inert: a *wrong* vendor resource type is rejected outright with 415, and a stale *version* can return 403. See "A Wrong Vendor Type Gets 415" above.

One exception: `GET /organizations/{org_id}/pitch-count-report` returns **CSV** text, not JSON. This is the only non-JSON endpoint in the spec.

## Finding Accept Header Values

The `accept` field in each endpoint file's YAML frontmatter contains the correct value for that endpoint. When `accept: null` appears in frontmatter, the Accept header was not captured for that endpoint -- use the standard vendor-typed format as a best guess and confirm with a proxy capture.

See `headers.md` for a consolidated quick-reference table of all known Accept header values.
