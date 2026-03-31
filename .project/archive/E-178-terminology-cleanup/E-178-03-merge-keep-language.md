# E-178-03: Merge Page "Keep" Language + Minor Text Fixes

## Epic
[E-178: Teams Page UX Overhaul](epic.md)

## Status
`DONE`

## Description
After this story is complete, the merge page uses "keep"/"remove" instead of "canonical"/"duplicate" in all user-visible text, and a minor confusing error message is cleaned up. The merge page becomes immediately understandable without database knowledge.

## Context
The merge page (`merge_teams.html`) uses "canonical" throughout -- a database term that means nothing to a coach. UXD and coach both confirmed that "keep"/"remove" is instant clarity: "Which team do you want to keep?" Additionally, one error message in the add-team flow includes "(concurrent insert)" -- a database implementation detail that confuses operators.

## Acceptance Criteria

**Merge page "keep" language:**
- [ ] **AC-1**: The "Canonical" badge reads "Keeping".
- [ ] **AC-2**: The "Select Canonical Team" heading reads "Which team do you want to keep?".
- [ ] **AC-3**: The radio label "Keep (canonical team) -- this team's data wins" reads "Keep this team -- this team's data wins".
- [ ] **AC-4**: The "Rows to reassign to canonical" label reads "Rows to reassign to kept team".
- [ ] **AC-5**: The confirmation text "delete the duplicate and reassign all its data to the canonical team" reads "delete the duplicate and reassign all its data to the kept team".
- [ ] **AC-6**: The hidden input `name="canonical_id"` is unchanged (internal identifier, not user-visible).
- [ ] **AC-7**: No user-visible text on the merge page contains the word "canonical" (case-insensitive). Template variable names and hidden input names are excluded.

**Minor text fix:**
- [ ] **AC-8**: The error message "Team already exists (concurrent insert)." reads "Team already exists." (parenthetical removed).

**Tests:**
- [ ] **AC-9**: Tests that assert on merge page text are updated for the new labels. All existing tests pass with no regressions.

## Technical Approach
Template string replacements in `merge_teams.html` for all user-visible "canonical" text. One route handler string change in `admin.py` for the "(concurrent insert)" error message. The hidden input name (`canonical_id`) and all Python variable names stay unchanged. Test assertions in `test_admin_merge.py` that reference old labels need updating.

## Dependencies
- **Blocked by**: E-178-01 (merge_teams.html terminology must be clean first -- "Last synced" → "Last updated")
- **Blocks**: None

## Files to Create or Modify
- `src/api/templates/admin/merge_teams.html` -- replace all user-visible "canonical" text with "keep"/"keeping"/"kept team"
- `src/api/routes/admin.py` -- remove "(concurrent insert)" from error message at line ~1800
- `tests/test_admin_merge.py` -- update assertions for new merge page labels

## Agent Hint
software-engineer

## Definition of Done
- [ ] No user-visible "canonical" text on the merge page
- [ ] "(concurrent insert)" removed from error message
- [ ] All acceptance criteria pass; no regressions
- [ ] Code follows project style (see CLAUDE.md)

## Notes
- The hidden input `name="canonical_id"`, Python variables, and route handler parameter names all stay as "canonical_id" -- renaming internal identifiers is churn with no user benefit.
- The "Change Selection" link text on the merge page does not contain "canonical" and is not in scope.
- Coach validated "keep"/"remove" as immediately clear. "Which team do you want to keep?" was specifically highlighted as the right framing.
