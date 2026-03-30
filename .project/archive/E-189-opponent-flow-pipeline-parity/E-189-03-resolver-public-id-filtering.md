# E-189-03: Add public_id filtering to gc_uuid resolver Tier 3

## Epic
[E-189: Opponent Flow Pipeline and Display Parity](epic.md)

## Status
`DONE`

## Description
After this story is complete, the gc_uuid resolver's Tier 3 search will prefer public_id-based filtering when the team's public_id is available, falling back to the existing name+season_year matching when public_id is NULL or when the public_id filter finds no match. This eliminates ambiguous matches for common team names (e.g., "Lincoln" returning dozens of results).

## Context
The three-tier gc_uuid resolver (`src/gamechanger/resolvers/gc_uuid_resolver.py`) receives `public_id` as a parameter but Tier 3 ignores it. Instead, it strips classification suffixes and searches by name + season_year, requiring exactly 1 match. For common names, this produces multiple matches and resolution fails. The report generator (`src/reports/generator.py:_resolve_gc_uuid`) uses public_id exact-match filtering and succeeds reliably. The resolver should use the same approach when public_id is available.

## Acceptance Criteria
- [ ] **AC-1**: Given a team with `public_id` available, when Tier 3 runs, then the search results are filtered by `result.public_id == public_id` (exact match) before applying any other filters
- [ ] **AC-2**: Given a team with `public_id` available and a matching search result, when the public_id filter matches exactly one result, then `result.id` is stored as the gc_uuid
- [ ] **AC-3**: Given a team with `public_id` available but no search result matches, when the public_id filter returns zero results, then fall back to the existing name+season_year matching logic
- [ ] **AC-4**: Given a team with `public_id = NULL`, when Tier 3 runs, then the existing name+season_year matching logic is used unchanged (no regression)
- [ ] **AC-5**: Given a team with `public_id` available but `season_year = NULL`, when Tier 3 runs, then the public_id filtering path proceeds (the season_year gate is relaxed for the public_id path per Technical Notes TN-3). The name+season_year fallback is skipped since season_year is required for it.

## Technical Approach
Modify `resolve_gc_uuid` to allow Tier 3 to proceed when `public_id` is available even if `season_year is None` (relax the current early-return gate at lines 111-115). Modify `_tier3_search` (or introduce a new function called before it) to check if `public_id` is not None. If available, filter the first page of POST /search results by `result.public_id == public_id` exact match. If found, return immediately. If not found on the first page, fall back to the existing stripped-name + season_year logic (when season_year is available). First-page-only is acceptable for the public_id path since the team name search is scoped enough that the matching public_id will appear in the first 25 results.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/resolvers/gc_uuid_resolver.py` -- modify Tier 3 to prefer public_id filtering
- `tests/test_gc_uuid_resolver.py` -- add tests for public_id filtering path (existing file)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
