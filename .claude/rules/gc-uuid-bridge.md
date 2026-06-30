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

## Reverse Bridge (gc_uuid → public_id)

The bridge also runs in reverse. When you have a team's `gc_uuid` (UUID) but need its `public_id` (for public endpoints or report generation):

- **Use `GET /teams/{gc_uuid}`** -- it returns the `public_id` directly. Verified 2026-06-12 to work for **non-managed** teams (you need only follow/fan access, not management).
- **Do NOT use `GET /teams/{team_id}/public-team-profile-id`** for non-managed teams -- it returns **403** unless you manage the team. It is the wrong tool for opponent resolution.

This reverse path is the rung-(a) auto-resolution mechanism in the report-generation and (future) scheduled-report flows: an authenticated opponents-list entry carrying a `progenitor_team_id` (its `gc_uuid`) resolves to a `public_id` via `GET /teams/{progenitor_team_id}`, which then feeds the public scouting pipeline.

## BANNED PATH: the follow → bridge → unfollow resolution pattern

**Do NOT reintroduce the follow → bridge → unfollow resolution pattern** (the former `resolve_unlinked()` / `_follow_bridge_unfollow()` approach, deleted in E-239). It issued `POST /teams/{root_team_id}/follow`, hit the bridge endpoint, then unfollowed.

Why it is banned:

- **Wrong identifier namespace**: it follows against `root_team_id`, which is NOT a `gc_uuid`. `root_team_id` is a separate namespace (the local opponent-registry key from manually-typed opponents) -- consistent with the CLAUDE.md "Opponent entry duality" guidance, `root_team_id` must NEVER be treated as, or stored in, `gc_uuid`. Following/bridging against it is operating on the wrong identifier.
- **Mutates external GameChanger state**: unlike every other bridge path in this file (which is read-only `GET`/`POST /search`), this path *writes* to GC -- it follows a team, hits the bridge endpoint, then issues two best-effort unfollow `DELETE`s. A failed or interrupted cycle can leave the authenticated account following teams it never intended to.
- **Unverified**: the original implementation's own docstring noted the flow was experimental and that whether `root_team_id` works with the follow/bridge endpoints was unverified.

The correct opponent-resolution mechanisms are the read-only paths documented above (the forward `POST /search` bridge and the rung-(a) reverse `GET /teams/{gc_uuid}` bridge) plus operator-pasted GC team URLs for unindexed teams. New work MUST NOT reintroduce the follow → bridge → unfollow path; route any such need to PM.

## Search Cannot Find Unindexed Teams (Name-Source Warning)

`POST /search` (the forward bridge above) only finds teams **GameChanger has indexed**. Two failure modes are invariant-level and easy to misdiagnose as transient:

- **Indexed name ≠ URL slug**: Searching a URL-slug-derived string returns **0 hits** -- the indexed name differs from the slug. Always source the search term from a real name field (`name` from `GET /public/teams/{public_id}` or an opponents-list entry), never from slug text.
- **Unindexed teams are unfindable**: Many teams are simply absent from GC's searchable index -- notably opponents a coach **typed manually** rather than added via team lookup (e.g., HS varsity programs). Search will never recover these; the resolution path for them is operator-pasted GC team URL (the same input `bb report generate` accepts), not search. A zero-hit search is therefore ambiguous: punctuation quirk (recoverable via the helper's normalization) **or** genuinely unindexed (not recoverable).

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

Implementation: `src/gamechanger/search.py` (canonical `search_teams_by_name()` helper with punctuation-normalization fallback) and `src/reports/generator.py` (report generation uses the bridge pattern with `public_id` filtering). The forward bridge is the `POST /search` filtered-by-`public_id` path above; the former 3-tier `gc_uuid_resolver.py` was dead code (its upstream data sources removed in E-239) and was deleted in E-246.
