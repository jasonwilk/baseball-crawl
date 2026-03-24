# E-151-01: Editable gc_uuid on Edit Team Page

## Epic
[E-151: GC UUID Manual Edit](epic.md)

## Status
`TODO`

## Description
After this story is complete, the admin Edit Team page will display `gc_uuid` as an editable text input instead of read-only text. The admin can set, change, or clear a team's `gc_uuid` with UUID format validation and uniqueness enforcement. Invalid or duplicate values re-render the form with an error banner preserving all submitted field values (per Technical Notes TN-4).

## Context
The Edit Team page currently displays `gc_uuid` as read-only. The POST handler (`update_team`) saves name, program_id, classification, and membership_type but not gc_uuid. The `_update_team_integer` helper function builds the SQL UPDATE statement. Both need to be extended. The template needs the read-only display converted to an editable input.

## Acceptance Criteria
- [ ] **AC-1**: Given a team with no `gc_uuid`, when the admin enters a valid UUID in the gc_uuid field and saves, then the team's `gc_uuid` is updated in the database and the handler redirects to the team list with a success flash message (preserving existing redirect behavior).
- [ ] **AC-2**: Given a team with an existing `gc_uuid`, when the admin changes it to a different valid UUID and saves, then the team's `gc_uuid` is updated to the new value and the handler redirects to the team list.
- [ ] **AC-3**: Given a team with an existing `gc_uuid`, when the admin clears the field (submits empty) and saves, then `gc_uuid` is set to NULL in the database and the handler redirects to the team list.
- [ ] **AC-4**: Given the admin enters a new or changed value that is a malformed string (not a valid UUID format, per Technical Notes TN-1), when they save, then the form re-renders with an error banner at the top of the form indicating invalid UUID format (per Technical Notes TN-4), all submitted field values are preserved, and no database update occurs.
- [ ] **AC-5**: Given the admin enters a UUID that is already assigned to a different team (per Technical Notes TN-2), when they save, then the form re-renders with an error banner indicating the UUID is already in use (per Technical Notes TN-4), all submitted field values are preserved, and no database update occurs.
- [ ] **AC-6**: Given the admin enters a new UUID with mixed case or leading/trailing whitespace, when they save, then the value is normalized (trimmed and lowercased) before validation and storage.
- [ ] **AC-7**: Existing edit page functionality (name, program, classification, membership_type) is unaffected -- saving without changing gc_uuid preserves the current value. The success redirect target (`/admin/teams`) is unchanged.
- [ ] **AC-8**: Given a team with a legacy non-UUID placeholder gc_uuid (e.g., `lsb-varsity-uuid-2026`), when the admin edits other fields without changing the gc_uuid value, then the save succeeds and the placeholder gc_uuid is preserved as-is (per Technical Notes TN-1 conditional validation).
- [ ] **AC-9**: Tests verify: (a) valid UUID saves successfully, (b) empty input stores NULL, (c) malformed new UUID is rejected with error, (d) duplicate UUID is rejected with error, (e) existing fields are unaffected when gc_uuid is added/changed, (f) mixed-case UUID is normalized to lowercase before storage, (g) unchanged placeholder gc_uuid is preserved without validation error.

## Technical Approach
The `update_team` POST handler in `src/api/routes/admin.py` needs a new `gc_uuid` Form parameter with the same pattern as existing fields. The value should be normalized per Technical Notes TN-3, validated for UUID format per TN-1, and the IntegrityError from the unique index should be caught per TN-2. On validation or uniqueness failure, the handler re-renders the form with error context per TN-4 (preserving submitted values, not redirecting). On success, the existing redirect to `/admin/teams` is preserved. The GET handler (`edit_team_form`) also needs `error=""` added to its template context so the template can unconditionally reference the variable (per TN-4). The template at `src/api/templates/admin/edit_team.html` needs the read-only gc_uuid display converted to a text input with monospace styling, plus an error banner block that renders when the `error` context variable is non-empty.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/api/routes/admin.py` -- add `gc_uuid` Form param to `update_team` (POST), UUID validation, IntegrityError handling, extend `_update_team_integer`; add `error=""` to `edit_team_form` (GET) template context per TN-4
- `src/api/templates/admin/edit_team.html` -- convert read-only gc_uuid display to editable text input with error display
- `tests/test_admin_gc_uuid_edit.py` -- new test file for gc_uuid edit validation and persistence

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
- No migration needed -- `gc_uuid` column already exists on `teams` table.
- No downstream cascade needed when gc_uuid changes -- the next pipeline run picks it up automatically (confirmed by SE).
- The add-team flow (Phase 2 confirm page) already handles gc_uuid input; this story adds the same capability to the edit page.
- Production data may contain legacy non-UUID placeholder gc_uuid values (e.g., `lsb-varsity-uuid-2026`). The `load_config_from_db` function in `src/gamechanger/config.py` already has defensive logic to skip these at runtime. The edit page must not block saves when these values are unchanged (see TN-1 conditional validation).
