# E-115-02: Update architecture.md Schema and Admin Sections

## Epic
[E-115: E-100 Documentation Updates](epic.md)

## Status
`DONE`

## Description
After this story is complete, `docs/admin/architecture.md` will accurately describe the E-100 schema and admin interface. The "Schema Changes" section will replace the migration 005 documentation with a summary of the fresh-start schema rewrite (programs table, INTEGER PK teams, team_opponents, key column changes). The "Admin Interface" section will describe the current route set with INTEGER `{id}` parameters and the two-phase add-team flow. References to E-042-era modules will be updated to reflect any changes.

## Context
The current architecture doc's "Schema Changes" section documents only migration 005 (`public_id` on teams) from E-042. E-100 replaced the entire migration history with a single `001_initial_schema.sql`. The "Admin Interface" section lists E-042 routes with TEXT `team_id` parameters and describes modules (`url_parser.py`, `team_resolver.py`) that may have changed. Both sections need rewriting.

## Acceptance Criteria
- [ ] **AC-1**: The "Schema Changes" section replaces the migration 005 documentation with a summary of the E-100 fresh-start schema. It describes: programs table, teams table with INTEGER AUTOINCREMENT PK and key columns (membership_type, classification, gc_uuid, public_id, program_id), and team_opponents junction table. The INTEGER PK rationale (separating internal identity from external GC identifiers) is explained briefly.
- [ ] **AC-2**: The "Admin Interface" route table uses INTEGER `{id}` path parameters and includes the two confirm routes (`GET /admin/teams/confirm`, `POST /admin/teams/confirm`). Route descriptions match the current implementation.
- [ ] **AC-3**: The "New Modules" subsection is reviewed against source and updated. `url_parser.py` and `team_resolver.py` descriptions should reflect their current behavior (verify against source files).
- [ ] **AC-4**: All references to `is_owned`, `level`, and TEXT `team_id` are removed from both sections.
- [ ] **AC-5**: The "Last updated" footer references E-115.

## Technical Approach
Read the current `docs/admin/architecture.md` and the source files listed in the epic Technical Notes ("Source Files for Verification") to verify the implemented reality. Rewrite the "Schema Changes" and "Admin Interface" sections. Preserve the rest of the document (System Overview, Components, Data Flow, Directory Structure, Tech Stack, Cross-References) unchanged unless they contain stale `is_owned`/`level`/TEXT `team_id` references (grep and fix if found).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/architecture.md`

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Documentation matches implemented source code
- [ ] No regressions to other sections of the document

## Notes
The schema summary should be concise -- this is admin documentation, not an API spec. Focus on what an operator needs to understand (table purposes, key columns, why INTEGER PK), not the full DDL.
