# E-168-03: Update Opponent Resolution Flow Documentation

## Epic
[E-168: Switch Opponent Resolution to POST /search](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/api/flows/opponent-resolution.md` will document the POST /search resolution path alongside the existing progenitor chain, covering both the admin resolve workflow and the auto-resolver search fallback. The doc will accurately reflect the two-pass resolution strategy.

## Context
The current flow doc describes only the 3-step progenitor chain and the null-progenitor gap. With E-168-01 switching the admin search and E-168-02 adding the auto-resolver fallback, the doc needs to reflect both resolution paths and how POST /search closes the null-progenitor gap.

## Acceptance Criteria
- [ ] **AC-1**: The flow doc describes POST /search as a resolution path for null-progenitor opponents (auto-resolver fallback) with the auto-accept criteria (exact name + season year + single result).
- [ ] **AC-2**: The flow doc describes the admin resolve workflow using POST /search (replacing the GET /search/opponent-import reference).
- [ ] **AC-3**: The "Null-Progenitor Fallback" section is updated to reflect that POST /search is the primary automated fallback, with manual resolution as the final fallback.
- [ ] **AC-4**: The resolution statistics section documents the two-pass architecture (progenitor chain + search fallback) and that search-resolved opponents use `resolution_method='search'`.
- [ ] **AC-5**: The doc cross-references `docs/api/endpoints/post-search.md` for the endpoint spec.
- [ ] **AC-6**: The `Last updated` and `Source` metadata at the top of the doc reflect this update (date in YYYY-MM-DD format, source: E-168-03).
- [ ] **AC-7**: `docs/api/README.md` is updated to reflect that POST /search is used for opponent resolution (removing any mobile-only or unknown-schema characterization).
- [ ] **AC-8**: `docs/api/endpoints/get-search-opponent-import.md` is updated to note that GET /search/opponent-import is no longer the primary search mechanism for opponent resolution (replaced by POST /search in E-168-01).
- [ ] **AC-9**: `docs/api/endpoints/post-search.md` is updated: (a) the description no longer characterizes POST /search as "distinct from" GET /search/opponent-import for opponent flows (POST /search now handles opponent resolution), and (b) the `see_also` cross-reference to GET /search/opponent-import is updated to reflect that GET is no longer the primary opponent search mechanism.

## Technical Approach
Read the current `docs/api/flows/opponent-resolution.md` and update it to add a new section for the POST /search resolution path. Update the null-progenitor fallback section. Add cross-references to the POST /search endpoint doc. Preserve the existing progenitor chain documentation as the primary path. Also update `docs/api/README.md` to correct the POST /search characterization, and add a deprecation note to `docs/api/endpoints/get-search-opponent-import.md`.

## Dependencies
- **Blocked by**: E-168-01, E-168-02
- **Blocks**: None

## Files to Create or Modify
- `docs/api/flows/opponent-resolution.md` (modify)
- `docs/api/README.md` (modify: update POST /search characterization)
- `docs/api/endpoints/get-search-opponent-import.md` (modify: note replacement by POST /search)
- `docs/api/endpoints/post-search.md` (modify: review and update if stale cross-references exist)

## Agent Hint
api-scout

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- documentation only)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests (N/A)

## Notes
- The experimental `resolve_unlinked()` follow→bridge→unfollow flow can remain documented as a legacy/experimental path until it's formally deprecated.
