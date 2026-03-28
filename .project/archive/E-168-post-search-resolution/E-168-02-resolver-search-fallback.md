# E-168-02: Add POST /search Fallback to OpponentResolver

## Epic
[E-168: Switch Opponent Resolution to POST /search](epic.md)

## Status
`DONE`

## Description
After this story is complete, the `OpponentResolver` will attempt to resolve unlinked opponents via `POST /search` after the primary progenitor chain completes. Opponents matching the auto-accept criteria (exact name + season year + single result) are resolved automatically with `resolution_method='search'`. Ambiguous or unmatched opponents remain unlinked for manual resolution.

## Context
~14% of opponents have null `progenitor_team_id` and cannot be resolved by the existing progenitor chain. They fall through as unlinked rows in `opponent_links`. The experimental `resolve_unlinked()` follow→bridge→unfollow flow is unreliable. `POST /search` returns both `id` (gc_uuid) and `public_id` per result, enabling name-based resolution for these opponents.

The fallback is conservative by design: it only auto-resolves when there's an unambiguous match. This avoids misidentification (e.g., "Lincoln" matching 50 teams) while closing the gap on clearly identifiable opponents.

## Acceptance Criteria
- [ ] **AC-1**: Given the resolver completes the progenitor chain pass, when unlinked opponents exist (no `resolution_method`, not hidden), then a second pass runs that calls `POST /search` for each unlinked opponent using the opponent's name.
- [ ] **AC-2**: Given POST /search returns results for an unlinked opponent, when exactly one result matches the opponent name (case-insensitive exact match) AND the result's `season.year` matches the `season_year` of the member team currently being resolved (from the per-team loop iteration; NULL `season_year` falls back to current calendar year), then the opponent is auto-resolved using the result's `id` as `gc_uuid` and `public_id` as the public slug.
- [ ] **AC-3**: Given POST /search returns results but zero or multiple results pass the name+year filter, when the fallback processes this opponent, then the opponent remains unlinked (no status change, no `resolution_method` set).
- [ ] **AC-4**: Given a search-resolved opponent, when the `opponent_links` row is updated, then `resolution_method` is `'search'` and the corresponding `teams` row has `gc_uuid` and `public_id` populated from the search result (whether the row was newly created by `ensure_team_row()` or pre-existing as a name-only stub — see TN-8).
- [ ] **AC-5**: Given the search fallback encounters a non-credential API error on one opponent (`GameChangerAPIError` for 5xx, `RateLimitError` for 429, network errors), when the error is caught, then it is logged and the fallback continues to the next opponent (no abort).
- [ ] **AC-6**: Given the search fallback encounters a `CredentialExpiredError` or any subclass (`ForbiddenError` for 403, `LoginFailedError`), when the error is raised, then it propagates to the caller (same as the progenitor chain behavior).
- [ ] **AC-7**: Given opponents that were previously resolved by the progenitor chain (`resolution_method='auto'`), when the search fallback runs, then those opponents are not re-processed (the fallback only targets unlinked opponents).
- [ ] **AC-8**: Given opponents with `resolution_method='manual'`, when the search fallback runs, then those opponents are not re-processed.
- [ ] **AC-9**: The `ResolveResult` dataclass includes a count for search-resolved opponents, and the `logger.info` summary at the end of `resolve()` includes this count.
- [ ] **AC-10**: Tests cover: single exact match (resolves), multiple matches (stays unlinked), zero matches (stays unlinked), case-insensitive matching, API error handling, and credential expiry propagation.

## Technical Approach
Add a search fallback pass that runs **inside the per-team loop**, after `_resolve_team` completes for the current member team's opponents. For each member team, the fallback queries `opponent_links` rows where `our_team_id` matches the current member team, `resolution_method` is null, and `is_hidden=0`. For each unlinked opponent:

1. Calls `POST /search` with `{"name": opponent_name}` per TN-1, using the JSON POST client method added by E-168-01
2. Filters results client-side: exact name match (case-insensitive) + `season.year` == member team's `season_year`
3. If exactly 1 match: calls `ensure_team_row()` with the result's `gc_uuid` and `public_id`, ensures the returned teams row has both identifiers populated (see TN-8 for the step-3 backfill limitation), then upserts the `opponent_links` row with `resolution_method='search'`
4. If 0 or 2+ matches: skips (opponent stays unlinked)

The search fallback needs its own upsert SQL statement (or a parameterized version) since the existing `_UPSERT_RESOLVED_SQL` hardcodes `resolution_method='auto'`. The search fallback upsert should use `'search'` and include the same manual-link protection (COALESCE) as the existing statement.

Rate limiting: use the existing `_DELAY_SECONDS` (1.5s) between search calls, consistent with the progenitor chain timing.

## Dependencies
- **Blocked by**: E-168-01 (provides the JSON POST client method)
- **Blocks**: E-168-03

## Files to Create or Modify
- `src/gamechanger/crawlers/opponent_resolver.py` (modify: add search fallback pass, update `ResolveResult`)
- `tests/test_crawlers/test_opponent_resolver.py` (modify: add tests for search fallback)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The existing `resolve_unlinked()` follow→bridge→unfollow flow is NOT removed in this story. It can be deprecated separately once the search fallback is proven in production.
- The search fallback should fetch member team's `season_year` once at the start of the pass, not per-opponent. The resolver already has access to `team.internal_id` from the config.
- Only page 0 of search results is used (25 results). If the auto-accept criteria don't match within 25 results, the opponent stays unlinked. Pagination is out of scope.
- Both admin resolve (E-168-01) and this auto-resolver fallback use `resolution_method='search'`. See TN-7 for the design rationale.
- `client.py` is NOT in this story's file list -- the JSON POST client method is added by E-168-01. This story uses it.
