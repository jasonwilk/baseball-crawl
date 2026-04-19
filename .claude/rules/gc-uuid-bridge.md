---
paths:
  - "src/gamechanger/**"
  - "src/reports/**"
  - "docs/api/**"
---

# public_id-to-gc_uuid Bridge Pattern

## When to Use

When you have a team's `public_id` (the slug used in public endpoints) but need its `gc_uuid` (the UUID used in authenticated endpoints like `/teams/{team_id}/*`). Common scenarios:

- **Standalone reports**: The report generator receives a `public_id` from the user but needs `gc_uuid` to call authenticated endpoints (e.g., the spray chart player-stats endpoint).
- **Tracked opponent enrichment**: A tracked team was added via public URL and has `public_id` but no `gc_uuid`.
- **Any flow that crosses the public-to-authenticated boundary**: Public endpoints use `public_id` slugs; authenticated endpoints require UUIDs.

## API Call Sequence

1. **Search by team name**: Call `search_teams_by_name(client, team_name, *, start_at_page=0)` from `src/gamechanger/search.py`. This is the canonical shared entry point for all `POST /search` by-team-name calls. It returns the `hits` list and transparently handles the punctuation quirk described below.

   **Do NOT call `client.post_json("/search", body={"name": ...}, ...)` directly for team name searches.** The direct call will silently return zero hits for names containing certain punctuation. Use the helper instead.

   Under the hood, the helper issues:
   ```
   POST /search
   Content-Type: application/vnd.gc.com.post_search+json; version=0.0.0
   Body: {"name": "<team_name>"}
   Query: start_at_page=<N>&search_source=search
   ```

2. **Filter results by `public_id`**: Each hit contains `result.id` (the `gc_uuid`) and `result.public_id`. Find the hit where `result.public_id` matches the known `public_id` exactly.

3. **Extract `gc_uuid`**: `result.id` from the matching hit is the `gc_uuid` (also known as `progenitor_team_id`).

## Punctuation Quirk and Apostrophe Trap

`POST /search` has two silent-failure modes that the canonical helper absorbs:

- **Punctuation zero-hit bug**: GC's search backend returns zero hits for team names containing `/`, straight apostrophe `'` (U+0027), `%`, or `#` -- even though the indexed canonical name contains that character. The indexed record exists; the query simply fails to match.
- **Unicode apostrophe trap**: GC indexes canonical names with the curly apostrophe (U+2019, `'`). A query containing a straight apostrophe (U+0027, `'`) fails to match silently -- the two glyphs are visually identical in most fonts, so this failure mode is extremely easy to miss.
- **Diacritics are fine**: Accented letters (`é`, `ñ`, etc.) work on the first attempt -- GC folds diacritics server-side. The normalization therefore preserves accented letters by using `re.UNICODE`.

The helper's retry gate fires only when the first attempt returns zero hits AND the name contains at least one `[^\w ]` character. Clean-name zero-hit results are passed through unchanged.

**Normalization shape** (implemented in `src/gamechanger/search.py::_normalize_team_name`):

```python
re.sub(r"[^\w ]+", " ", name, flags=re.UNICODE)   # non-word non-space → space
re.sub(r"\s+", " ", ...)                          # collapse whitespace
.strip()                                          # trim ends
```

This normalization is lossy (multiple distinct inputs can collapse to the same query) but is sufficient to recover the indexed record for the punctuation failure modes above. The zero-hits-vs-25-hits binary failure signature is distinctive and reliable -- partial matches from this quirk have not been observed.

**When writing new GC query-construction code** that targets `POST /search` or a similar backend, assume the same quirk may apply and route through the shared helper rather than re-deriving normalization logic ad hoc.

## Storage Rule

Store the resolved `gc_uuid` only when the team does not already have one:

```sql
UPDATE teams SET gc_uuid = ? WHERE id = ? AND gc_uuid IS NULL
```

Never overwrite an existing `gc_uuid` -- it may have been set via a more authoritative path (e.g., authenticated team management).

## Edge Cases

- **No match found**: Search returns hits but none match the target `public_id`. The team may have been renamed, deactivated, or may not be indexed. In this case, `gc_uuid` remains NULL and features requiring it (e.g., spray charts) are unavailable for this team.
- **Pagination**: Search returns 25 results per page. If the team name is common, the matching hit may be on a later page. Paginate if needed.
- **Team name required**: The search endpoint requires a team name string. Obtain it from the `teams` table or from the public team profile (`GET /public/teams/{public_id}`).

## Critical Warning: Spray Endpoint Asymmetry

The spray chart player-stats endpoint (`GET /teams/{team_id}/schedule/events/{event_id}/player-stats`) is **asymmetric** -- it does NOT return both teams' data regardless of which UUID is used:

- **Owning team's UUID** (the team whose schedule contains the game): returns BOTH teams' spray data.
- **Participant's UUID**: returns ONLY that team's data.
- **Unrelated team**: 404.

Do NOT assume that resolving any team's `gc_uuid` gives access to complete game data. This false premise -- that the spray endpoint returns both teams' data regardless of which UUID is used -- was the root cause of missing spray charts in E-158 and E-176. For complete per-game spray data, you must use the owning team's UUID. See the endpoint doc at `docs/api/endpoints/get-teams-team_id-schedule-events-event_id-player-stats.md` for full details.

## Verification Evidence

Pattern verified 2026-03-29:
- Team: Lincoln Standing Bear HS Varsity
- `public_id`: known from database
- `POST /search` with team name returned hits including one where `result.public_id` matched exactly
- `result.id` from that hit was the correct `gc_uuid`, confirmed by successful authenticated API calls

Implementation: `src/gamechanger/search.py` (canonical `search_teams_by_name()` helper with punctuation-normalization fallback), `src/gamechanger/resolvers/gc_uuid_resolver.py` (Tier 3 delegates to the helper), and `src/reports/generator.py` (report generation uses the bridge pattern with `public_id` filtering).
