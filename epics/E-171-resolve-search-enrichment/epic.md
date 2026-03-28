# E-171: Enrich Resolve Search Results

## Status
`READY`

## Overview
Enrich the admin opponent-resolve search results page so the operator can make confident disambiguation decisions without leaving the page. Season year is currently rendered but too subtle (tiny gray text); player count and staff names are already in the API response but not displayed.

## Background & Context
E-168 shipped the `POST /search`-based resolve workflow. The normalized search results contain `season_year`, `num_players`, and `staff` fields. The template currently renders team name, city/state, and season year — but season year uses `text-xs text-gray-400`, making it nearly invisible when multiple seasons of the same team appear in results.

**Coach consultation** (baseball-coach):
- Season year is the #1 disambiguator — must be prominent, not tiny gray text
- Player count is a quick sanity check (HS varsity = 12-15 players)
- Staff/coach names help when the operator recognizes the coach
- Win/loss record is NOT worth the extra latency for disambiguation

**SE consultation** (software-engineer):
- Record fetch is feasible via parallel `GET /public/teams/{public_id}` calls (~300-500ms total), but coach recommends skipping it
- No architecture changes needed for the free fields — pure template work

## Goals
- Season year is visually prominent (the strongest disambiguator when multiple seasons of the same team appear)
- Player count and staff names are visible in result cards
- Operator can confidently pick the right team from 5-10 results without additional research

## Non-Goals
- Win/loss record enrichment (coach recommended skipping; feasible if needed later)
- Changing the search algorithm or adding new search filters
- Redesigning the resolve page layout beyond the result cards

## Success Criteria
- All free fields from the search response are visible in result cards
- Season year is the most prominent metadata field (not tiny/gray)

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-171-01 | Enrich search result cards | TODO | None | - |

## Dispatch Team
- software-engineer

## Technical Notes

### Available Fields in Normalized Dict
The `_gc_search_teams` function (line 2730 of `src/api/routes/admin.py`) normalizes search results into flat dicts with these keys:
`name`, `gc_uuid`, `public_id`, `city`, `state`, `season_year`, `season_name`, `sport`, `num_players`, `staff`

Currently rendered: `name`, `city`/`state`, `season_year` (tiny gray text).
Not rendered: `num_players`, `staff`, `season_name`.

### Display Hierarchy (per coach consultation)
1. **Team name** — primary, bold (already exists)
2. **Season year** — prominent badge or tag, NOT tiny gray text. This is the #1 disambiguator.
3. **Location** (city, state) — secondary line (already exists)
4. **Player count** — inline metadata (e.g., "14 players")
5. **Staff** — smallest text, comma-separated names. `staff` is a list of strings (e.g., `["Jane Doe", "Player One"]`) per `docs/api/endpoints/post-search.md`.

## Open Questions
None.

## History
- 2026-03-28: Created. Coach and SE consultations completed. Record fetch deferred per coach recommendation.
- 2026-03-28: Set to READY. Single-story epic — internal and Codex review skipped (minimal scope).

## Review Scorecard
| Round | Source | Findings | Accepted | Dismissed | Notes |
|-------|--------|----------|----------|-----------|-------|
