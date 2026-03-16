# IDEA-034: Program CRUD Admin Page

## Status
`CANDIDATE`

## Summary
Add an admin UI page for creating, editing, and deleting programs. E-100 created the programs table and seeded one program (Lincoln Standing Bear HS), but the admin UI only has a dropdown for existing programs — no way to create new ones from the UI.

## Why It Matters
As the operator adds teams from USSSA, Legion, or other organizations, new programs need to be created. Currently this requires direct SQL. An admin page would make program management self-service.

## Rough Timing
Before the operator onboards non-HS teams. Promote when:
- USSSA or Legion teams are about to be added
- IDEA-033 (bulk import) is promoted — bulk import + program creation naturally go together

## Dependencies & Blockers
- [x] E-100 (programs table and model) — DONE
- [ ] Need to know what fields programs need beyond the current schema (program_id, name, program_type, org_name)

## Open Questions
- Should program_id (the slug) be auto-generated from the name, or operator-specified?
- Is delete needed, or just soft-delete / archive? (Programs with teams can't be hard-deleted due to FK.)
- Should program editing be a separate page or inline in the team list?

## Notes
- E-100 Non-Goal: "Program CRUD admin page: No admin UI for creating/editing programs in E-100. Programs are created via direct SQL or a follow-up epic."
- Currently one seeded program: `lsb-hs` (Lincoln Standing Bear HS).

---
Created: 2026-03-16
Last reviewed: 2026-03-16
Review by: 2026-06-14
