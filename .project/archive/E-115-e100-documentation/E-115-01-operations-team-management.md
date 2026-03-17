# E-115-01: Update operations.md Team Management Section

## Epic
[E-115: E-100 Documentation Updates](epic.md)

## Status
`DONE`

## Description
After this story is complete, the "Admin Team Management" section of `docs/admin/operations.md` will accurately describe the E-100 team management workflow: two-phase add-team flow, flat team list with membership badges, membership_type model, classification replacing level, program assignment, and gc_uuid discovery via reverse bridge. All references to `is_owned`, `level` (as a team field), two-section layout, and single-step add form will be removed.

## Context
The current "Admin Team Management" section was written for E-042 and describes the pre-E-100 model: `is_owned` distinguishes Lincoln teams from opponents, a two-section layout splits teams into "Lincoln Program" and "Tracked Opponents", adding a team is a single-step form with a "team type" selector, and routes use TEXT `team_id`. E-100 replaced all of this with a team-first model.

## Acceptance Criteria
- [ ] **AC-1**: The "Admin Team Management" section describes the two-phase add-team flow: Phase 1 (URL input only, no team type selector), Phase 2 (confirm page with resolved team info, gc_uuid status, membership radio defaulting to tracked, program and division dropdowns).
- [ ] **AC-2**: The team list description reflects a flat table with columns: team name, program, division, membership badge, active/inactive, opponent count, edit link. No "Lincoln Program" / "Tracked Opponents" split.
- [ ] **AC-3**: All references to `is_owned` are replaced with `membership_type` (member/tracked). All references to `level` (as a team field) are replaced with `classification` (displayed as "Division").
- [ ] **AC-4**: The "Database-Driven Crawl Configuration" subsection's SQL query uses `membership_type='member'` instead of `is_owned = 1`, and references `teams.id` and `teams.name` instead of `team_id`.
- [ ] **AC-5**: The editing and activate/deactivate subsections use INTEGER `{id}` in route paths and describe the current edit form fields (name, program, division, membership radio, active toggle).
- [ ] **AC-6**: The "Discovered placeholder upgrade" note is reviewed against the current implementation and updated or removed as appropriate.
- [ ] **AC-7**: The "Last updated" footer references E-115.

## Technical Approach
Read the current `docs/admin/operations.md` and the source files listed in the epic Technical Notes ("Source Files for Verification") to verify the implemented reality. Rewrite the "Admin Team Management" section and its subsections. Preserve the rest of the document (Deployment, Credential Rotation, Database Backup, Troubleshooting, Monitoring) unchanged.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/operations.md`

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Documentation matches implemented source code
- [ ] No regressions to other sections of the document

## Notes
The "What the URL parser accepts" subsection is likely still accurate (url_parser.py was not rewritten in E-100) but should be verified against source.
