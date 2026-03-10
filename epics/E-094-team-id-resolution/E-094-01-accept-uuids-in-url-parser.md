# E-094-01: Accept UUIDs in URL Parser

## Epic
[E-094: Fix Team ID Resolution in Import and Crawl Pipeline](epic.md)

## Status
`TODO`

## Description
After this story is complete, `parse_team_url()` will accept GameChanger UUIDs (e.g., `72bb77d8-54ca-42d2-8547-9da4880d0cb4`) as valid input in addition to public_id slugs and full URLs. The function will return a result that indicates what type of identifier was provided, enabling callers to handle each type appropriately.

## Context
Currently `parse_team_url()` only returns a `public_id` string. It validates that the extracted value is alphanumeric 6-20 chars, which rejects UUIDs (they contain dashes and are 36 chars). The admin import route needs to accept UUIDs as input so operators can paste either format. The return value must distinguish the ID type so the import route (E-094-02) can decide whether to resolve the counterpart.

## Acceptance Criteria
- [ ] **AC-1**: Given a bare UUID string (e.g., `"72bb77d8-54ca-42d2-8547-9da4880d0cb4"`), `parse_team_url()` returns a result indicating the value is a UUID and provides the UUID string.
- [ ] **AC-2**: Given a bare public_id slug (e.g., `"a1GFM9Ku0BbF"`), `parse_team_url()` returns a result indicating the value is a public_id and provides the slug string.
- [ ] **AC-3**: Given a full GameChanger URL containing a public_id (e.g., `"https://web.gc.com/teams/a1GFM9Ku0BbF/2025-rebels-14u"`), the function returns a public_id result with the extracted slug.
- [ ] **AC-4**: Given an invalid input (empty string, random text, URL with no `/teams/` segment), `ValueError` is raised as before.
- [ ] **AC-5**: The return type is a structured result (dataclass or similar) with fields for the identifier value and its type, not a plain string. Existing callers that expect a plain string must be updated or the API change must be backward-compatible.
- [ ] **AC-6**: All existing `test_url_parser.py` tests pass (updated as needed for the new return type).
- [ ] **AC-7**: New tests cover UUID input (bare UUID, UUID with surrounding whitespace, UUID-like strings that are not valid UUIDs).

## Technical Approach
The function currently returns `str`. It needs to return a richer type that distinguishes UUID from public_id. UUIDs match the pattern `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (36 chars, hex digits and dashes in the 8-4-4-4-12 format). Public_id slugs are alphanumeric 6-20 chars. These formats are mutually exclusive.

The key files are `src/gamechanger/url_parser.py` (the parser) and `tests/test_url_parser.py` (existing tests). The admin route in `src/api/routes/admin.py` calls `parse_team_url()` but that caller update belongs to E-094-02.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-094-02

## Files to Create or Modify
- `src/gamechanger/url_parser.py` -- add UUID detection, structured return type
- `tests/test_url_parser.py` -- update existing tests for new return type, add UUID test cases

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-094-02**: The new return type from `parse_team_url()` -- E-094-02 needs to know the type name and how to distinguish UUID vs. public_id results to decide which resolution path to take.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- The UUID regex should validate the 8-4-4-4-12 hex format, not just "contains dashes." A string like `"abc-def"` should not be treated as a UUID.
- Consider whether URLs could contain UUIDs in the path (e.g., `https://web.gc.com/teams/72bb77d8-54ca-42d2-8547-9da4880d0cb4/...`). If so, the URL extraction path should also detect UUID format in the `/teams/` segment.
