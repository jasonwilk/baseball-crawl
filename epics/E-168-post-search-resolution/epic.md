# E-168: Switch Opponent Resolution to POST /search

## Status
`READY`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview

Replace the unverified `GET /search/opponent-import` endpoint in the admin resolve workflow with the live-confirmed `POST /search` endpoint, and add a POST /search fallback to the auto-resolver for the ~14% of opponents with null `progenitor_team_id`. This fixes a known bug in the admin confirm flow (passing UUIDs where `public_id` slugs are expected) and closes the gap on opponents that cannot be auto-resolved today.

## Background & Context

**The problem has two parts:**

1. **Admin resolve workflow (E-167-04) uses an unverified endpoint.** The `_gc_search_teams` helper calls `GET /search/opponent-import`, whose response body was **never captured live** -- the schema is entirely inferred from proxy metadata. The confirm flow passes the search result's `id` field (likely a UUID) to `resolve_team()` which expects a `public_id` slug, causing a 404 and triggering the fallback path. This works by accident but is fragile.

2. **Auto-resolver can't resolve null-progenitor opponents.** The `OpponentResolver` uses a 3-step chain: opponents list → `progenitor_team_id` → `GET /teams/{uuid}` → `public_id`. ~14% of opponents have null `progenitor_team_id` and fall through as unlinked. The experimental `resolve_unlinked()` follow→bridge→unfollow flow is a workaround but unreliable.

**The solution:** `POST /search` was captured live on 2026-03-27. It returns both `id` (UUID = `progenitor_team_id`) and `public_id` (slug) per result in one call. Confirmed schema at `docs/api/endpoints/post-search.md`.

**Expert consultation (SE + api-scout):**
- SE recommends POST /search as **fallback only** for null-progenitor opponents (not replacing the deterministic progenitor chain). Auto-accept: exact name match (case-insensitive) + season year match + single result after filtering.
- api-scout confirms POST /search has a verified schema, no rate limiting concerns (10 calls at 1.5s delay = ~15s), and recommends name-only search with client-side filtering (POST body filtering capabilities are unknown beyond `name`).
- Both recommend normalizing POST /search response in the helper to minimize template churn.

## Goals
- Admin resolve search uses a live-verified endpoint (`POST /search`) with known response schema
- Admin confirm flow receives both `public_id` and `gc_uuid` directly from search results -- no more UUID/slug mismatch
- Null-progenitor opponents get an automated resolution attempt via POST /search before falling through to manual
- Opponent resolution flow documentation reflects both resolution paths

## Non-Goals
- Replacing the progenitor chain for opponents that already have `progenitor_team_id` (deterministic > fuzzy)
- Testing POST /search body filtering beyond `name` (follow-up if needed)
- Removing the experimental `resolve_unlinked()` follow→bridge→unfollow code (can be deprecated separately)
- Pagination of search results (page 0 with 25 results is sufficient for name-based opponent matching)

## Success Criteria
- Admin opponent resolve search returns results from `POST /search` with correct field rendering
- Clicking "Select" on a search result passes the team's `public_id` to the confirm flow, and `resolve_team()` succeeds without fallback
- Auto-resolver resolves at least some previously-unlinked null-progenitor opponents via search
- Ambiguous search results (0 or 2+ matches after filtering) leave opponents unlinked for manual resolution
- All existing auto-resolved opponents (progenitor chain) continue to resolve identically

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-168-01 | Switch admin resolve search to POST /search | TODO | None | - |
| E-168-02 | Add POST /search fallback to OpponentResolver | TODO | E-168-01 | - |
| E-168-03 | Update opponent resolution flow documentation | TODO | E-168-01, E-168-02 | - |

## Dispatch Team
- software-engineer
- api-scout

## Technical Notes

### TN-1: POST /search Request Shape

```
POST https://api.team-manager.gc.com/search?start_at_page=0&search_source=search
Content-Type: application/vnd.gc.com.post_search+json; version=0.0.0

{"name": "search query"}
```

**Critical:** Content-Type uses `post_search` (underscore), not `post-search` (hyphen). The underscore variant was confirmed live 2026-03-27. The hyphen variant has never been tested.

Full endpoint spec: `docs/api/endpoints/post-search.md`

### TN-2: POST /search Response Shape

```json
{
  "total_count": 42,
  "hits": [{
    "type": "team",
    "result": {
      "id": "UUID (= progenitor_team_id)",
      "public_id": "slug",
      "name": "Team Name",
      "sport": "baseball",
      "location": {"city": "...", "state": "...", "country": "..."},
      "season": {"name": "spring", "year": 2026},
      "number_of_players": 15,
      "staff": ["Coach Name"]
    }
  }],
  "next_page": 1
}
```

Key mapping: `result.id` = `gc_uuid` (progenitor_team_id). `result.public_id` = public slug for `/public/teams/{public_id}` endpoints.

### TN-3: Response Normalization

The `_gc_search_teams` helper normalizes each `hits[].result` into a flat dict before returning to the route handler. This isolates the template from the API response structure.

Normalized shape per result:
```python
{
    "name": str,          # result.name
    "gc_uuid": str,       # result.id (the progenitor_team_id UUID)
    "public_id": str,     # result.public_id (slug)
    "city": str | None,   # result.location.city
    "state": str | None,  # result.location.state
    "season_year": int | None,  # result.season.year
    "season_name": str | None,  # result.season.name
    "sport": str | None,  # result.sport
    "num_players": int | None,  # result.number_of_players
    "staff": list[str],   # result.staff
}
```

### TN-4: Admin Confirm Flow Fix

Currently: "Select" link passes `team.id` (UUID) as `?confirm=<id>`. Confirm page calls `resolve_team(confirm_id)` which expects a `public_id` → 404s → fallback treats as gc_uuid.

Fixed: "Select" link passes `?confirm=<public_id>&gc_uuid=<uuid>`. Confirm page calls `resolve_team(public_id)` which succeeds. POST handler receives both `public_id` (via `confirm_id` form field) and `gc_uuid` (via new hidden field). Both are passed to `ensure_team_row()`.

### TN-5: Auto-Resolver Search Fallback Strategy

POST /search is a **fallback only** -- it runs after the progenitor chain completes, targeting only unlinked opponents (no existing `resolution_method`, not hidden).

Auto-accept criteria (ALL must be true):
1. Exact name match (case-insensitive) between `opponent_links.opponent_name` and `result.name`
2. `result.season.year` matches the member team's `season_year`
3. Exactly one result remains after both filters

If 0 or 2+ matches → leave as unlinked for manual resolution via admin UI. Do NOT use location/player-count heuristics for auto-resolution (too fragile).

Resolution method: `'search'` (distinguishes from `'auto'` progenitor chain and `'manual'` admin links).

### TN-6: Request Content-Type

```
application/vnd.gc.com.post_search+json; version=0.0.0
```

This is the Content-Type for the request body (not an Accept header). The response returns standard `application/json; charset=utf-8`.

### TN-7: `resolution_method='search'` Design Choice

Both admin resolve (E-168-01) and auto-resolver fallback (E-168-02) use `resolution_method='search'`. This means you cannot distinguish admin-selected from auto-matched by resolution_method alone.

This is an intentional design choice: the operational behavior is identical (disconnect only blocks `'manual'`; all other methods are treated equally). If disambiguation becomes necessary in the future, migrating to `'search-manual'` / `'search-auto'` is a trivial schema change.

### TN-8: `ensure_team_row()` Step-3 Backfill Limitation

`ensure_team_row()` has a conservative backfill rule (E-167): gc_uuid and public_id are NOT attached on name+season_year matches (step 3). This is correct for general pipeline use where name-only matches are heuristic.

However, the search fallback (E-168-02) has **verified identity** — exact name match + season year match + single result from a live API response. This is a stronger signal than a name-only heuristic. When a name-only tracked stub already exists (no gc_uuid, no public_id), `ensure_team_row()` will return the stub's `teams.id` but won't attach the search result's identifiers.

**Constraint**: `ensure_team_row()` itself must NOT be modified (E-167's conservative design is correct for general use). The search fallback must ensure that after resolution, the matched teams row has gc_uuid and public_id populated from the search result.

**Why this matters**: Without gc_uuid and public_id on the team row, the scouting pipeline cannot fetch opponent data. A search-resolved opponent without identifiers is nominally resolved but operationally useless.

## Open Questions
- None (all discovery questions resolved via SE + api-scout consultation)

## History
- 2026-03-27: Created. Expert consultation: SE (implementation scope, ambiguity handling) + api-scout (endpoint verification, rate limiting, disambiguation).
- 2026-03-28: Set to READY after 7 review passes (33 findings: 31 accepted, 2 dismissed).

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 — CR spec audit | 7 | 7 | 0 |
| Internal iteration 1 — Holistic team (PM+SE+api-scout) | 3 | 3 | 0 |
| Internal iteration 2 — CR spec audit | 4 | 4 | 0 |
| Internal iteration 2 — Holistic team | 3 | 3 | 0 |
| Codex iteration 1 | 6 | 5 | 1 |
| Codex iteration 2 | 6 | 5 | 1 |
| Codex iteration 3 | 4 | 4 | 0 |
| **Total** | **33** | **31** | **2** |

Dismissed findings (Codex iterations 1 and 2): DE consultation for E-168-02 — no schema changes, no migrations, uses only existing write infrastructure (`ensure_team_row()` + existing upsert pattern).
