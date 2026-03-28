# E-171-01: Enrich Search Result Cards

## Epic
[E-171: Enrich Resolve Search Results](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin resolve search result cards will display season year prominently (not tiny gray), player count, and staff names — giving the operator enough information to confidently disambiguate between multiple search results.

## Context
E-168 shipped the `POST /search`-based resolve workflow. The normalized search dicts already contain `num_players` and `staff` fields that are not rendered. Season year is rendered but uses `text-xs text-gray-400`, making it nearly invisible — a problem when multiple seasons of the same team appear in results.

## Acceptance Criteria
- [ ] **AC-1**: Given search results are displayed, each result card shows the season year in a visually prominent style (e.g., bold badge, colored pill, or larger text) — clearly distinguishable from the current `text-xs text-gray-400` treatment. Season year is the most visually prominent metadata field after the team name.
- [ ] **AC-2**: Given search results are displayed, each result card shows the player count (e.g., "14 players") when `num_players` is present and non-zero.
- [ ] **AC-3**: Given search results are displayed, each result card shows staff names (comma-separated) in smaller text when the `staff` list is non-empty. `staff` is a list of strings per `docs/api/endpoints/post-search.md`.
- [ ] **AC-4**: Given a search result where `num_players` is null/zero or `staff` is empty, those fields are omitted from the card without layout breakage.
- [ ] **AC-5**: All new template output uses Jinja2 autoescaping (no `| safe` filter on user-controlled data), per `/.claude/rules/jinja-safety.md`.
- [ ] **AC-6**: Existing test coverage in `tests/test_admin_resolve.py` continues to pass. New or updated tests verify that the enriched fields (season year prominence, player count, staff) appear in rendered search result HTML.

## Technical Approach
The resolve page template (`src/api/templates/admin/opponent_resolve.html`) needs the search result card markup updated to promote season year visually and add `num_players` and `staff` display. The normalized dict keys and display hierarchy are documented in epic Technical Notes. No route handler changes are needed — all data is already passed to the template.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/admin/opponent_resolve.html` — update search result card markup
- `tests/test_admin_resolve.py` — add/update tests for enriched result card rendering

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- `season_name` (e.g., "spring") is also available in the normalized dict — include alongside `season_year` if it fits naturally (e.g., "2026 Spring"), but season year is the priority.
