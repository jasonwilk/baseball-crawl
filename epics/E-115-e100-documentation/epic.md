# E-115: E-100 Documentation Updates

## Status
`READY`

## Overview
Update admin documentation to reflect the team model overhaul shipped in E-100. The operations guide and architecture doc both describe the pre-E-100 team management model (is_owned, TEXT team_id, two-section layout, single-step add-team form). These sections must be rewritten to describe the implemented reality: membership_type, INTEGER PK, flat team list, two-phase add-team flow, programs table, and classification replacing level.

## Background & Context
E-100 (Team Model Overhaul) completed a fresh-start schema rewrite and admin UI redesign. During the E-100 closure documentation assessment, three triggers fired:

1. **New feature ships**: Two-phase add-team flow, flat team list, membership_type model
2. **Database schema changes**: Complete schema rewrite (programs, INTEGER PK, team_opponents, enriched stat columns, spray_charts)
3. **Epic changes how system works**: Membership model, admin team management, pipeline all changed

Two admin docs are now stale:
- `docs/admin/operations.md` -- "Admin Team Management" section describes is_owned, two-section layout, single-step add form, TEXT team_id
- `docs/admin/architecture.md` -- "Schema Changes" section documents migration 005 (obsolete), "Admin Interface" section describes E-042 routes with TEXT team_id

No `docs/coaching/` impact -- dashboards are unchanged.

No expert consultation required -- this is a documentation-only epic updating prose to match shipped code. The docs-writer reads source code to verify the implemented reality.

## Goals
- `docs/admin/operations.md` "Admin Team Management" section accurately describes the E-100 team management workflow
- `docs/admin/architecture.md` "Schema Changes" and "Admin Interface" sections accurately describe the E-100 schema and routes

## Non-Goals
- Documenting enriched stat columns, spray_charts, or provenance model in admin docs (no operator workflow touches these yet)
- Creating new documentation pages
- Updating `docs/coaching/` (no coaching-facing changes in E-100)
- Documenting the pipeline changes (no operator-facing workflow change -- `bb data crawl/load` commands work the same)

## Success Criteria
- Operations guide "Admin Team Management" section describes: two-phase add-team flow, flat team list with membership badges, membership_type (member/tracked), classification replacing level, program assignment, gc_uuid discovery via bridge
- Architecture doc "Schema Changes" section replaces migration 005 with the E-100 schema rewrite summary
- Architecture doc "Admin Interface" section uses INTEGER `{id}` routes and describes the current route set
- All references to `is_owned`, `level` (as a team field), and TEXT `team_id` are removed from both docs
- "Last updated" footers reference E-115

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-115-01 | Update operations.md team management section | TODO | None | docs-writer |
| E-115-02 | Update architecture.md schema and admin sections | TODO | None | docs-writer |

## Dispatch Team
- docs-writer

## Technical Notes

### What Changed in E-100
The docs-writer should read the source files to verify current reality, but here is a summary of the key changes to document:

**Schema (001_initial_schema.sql -- fresh-start rewrite):**
- `programs` table added (program_id TEXT PK, name, program_type, org_name)
- `teams` table: INTEGER AUTOINCREMENT PK (`id`), `membership_type` replaces `is_owned`, `classification` replaces `level`, `gc_uuid` and `public_id` as separate UNIQUE columns, `program_id` FK
- `team_opponents` junction table added
- Old migrations 002-008 archived; single `001_initial_schema.sql` contains all DDL

**Admin UI:**
- Team list is a flat table (no Lincoln/Opponents split). Columns: name, program, division (classification), membership badge, active/inactive, opponent count, edit link
- Two-phase add-team flow: Phase 1 = URL input only. Phase 2 = confirm page with resolved team info, gc_uuid status, membership radio (default: tracked), program/division dropdowns
- Edit page: name, program, division (classification), membership radio, active toggle
- All routes use INTEGER `{id}` path parameters
- Division dropdown uses optgroup (HS: varsity/JV/freshman/reserve; USSSA: 8U-14U; Other: legion)

**Routes (all under /admin/):**
- `GET /admin/teams` -- team list + Phase 1 add form
- `POST /admin/teams` -- Phase 1 submit (resolve + redirect to confirm)
- `GET /admin/teams/confirm` -- Phase 2 confirm page
- `POST /admin/teams/confirm` -- Phase 2 save
- `GET /admin/teams/{id}/edit` -- edit form
- `POST /admin/teams/{id}/edit` -- save edits
- `POST /admin/teams/{id}/toggle-active` -- toggle active status
- `POST /admin/teams/{id}/discover-opponents` -- discover opponents from schedule

### Source Files for Verification
The docs-writer should read these files to verify the implemented reality:
- `/workspaces/baseball-crawl/migrations/001_initial_schema.sql` -- current DDL
- `/workspaces/baseball-crawl/src/api/routes/admin.py` -- admin route handlers
- `/workspaces/baseball-crawl/src/api/templates/admin/teams.html` -- team list template
- `/workspaces/baseball-crawl/src/api/templates/admin/confirm_team.html` -- confirm page template
- `/workspaces/baseball-crawl/src/api/templates/admin/edit_team.html` -- edit page template

## Open Questions
- None

## History
- 2026-03-16: Created. Documentation assessment gate fired during E-100 closure on 3 triggers. Scoped to operations.md and architecture.md updates only.
