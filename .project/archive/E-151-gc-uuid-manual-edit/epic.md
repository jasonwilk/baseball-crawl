# E-151: GC UUID Manual Edit

## Status
`COMPLETED`
<!-- Lifecycle: DRAFT → READY → ACTIVE → COMPLETED (or BLOCKED / ABANDONED) -->

## Overview
Enable manual editing of a team's `gc_uuid` on the admin Edit Team page. Teams missing their `gc_uuid` (reverse bridge returned 403 at add time, or created by the opponent resolver without one) currently require direct SQL to fix. This removes that operational friction by adding an editable field with UUID format validation and uniqueness enforcement.

## Background & Context
The admin Edit Team page (`/admin/teams/{id}/edit`) displays `gc_uuid` as read-only text. If a team is missing its `gc_uuid`, there is no UI path to set it -- the operator must run direct SQL against the database. This is the only team property that cannot be corrected through the admin UI.

The `gc_uuid` is critical for authenticated API calls (crawl, sync, bridge resolution). A team without it cannot participate in authenticated pipelines. The value is a standard UUID string; the column has a partial unique index (`idx_teams_gc_uuid`) that enforces uniqueness for non-NULL values.

**Expert consultation**: SE confirmed the edit handler uses typed `Form(...)` parameters (not `await request.form()`), the partial unique index requires IntegrityError handling, empty string should normalize to NULL, and no downstream cascade is needed when gc_uuid changes -- the next pipeline run picks it up automatically.

## Goals
- Admin can set, change, or clear a team's `gc_uuid` from the Edit Team page
- UUID format is validated before save (reject malformed values with a clear error)
- Uniqueness is enforced (reject UUIDs already assigned to another team with a clear error)
- Empty input stores NULL (team has no gc_uuid)

## Non-Goals
- Automatic bridge resolution when gc_uuid is set (the next pipeline run handles this)
- Bulk gc_uuid assignment across multiple teams
- gc_uuid validation against the GameChanger API (we validate format only, not existence)
- Changes to the add-team flow (Phase 2 confirm page already handles gc_uuid)

## Success Criteria
- A team with no gc_uuid can have one assigned through the edit page
- A team with an existing gc_uuid can have it changed or cleared
- Malformed UUIDs are rejected with an error banner on the re-rendered form
- Duplicate UUIDs are rejected with an error banner identifying the conflict
- Existing edit page functionality (name, program, classification, membership_type) is unaffected

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-151-01 | Editable gc_uuid on Edit Team Page | DONE | None | software-engineer |

## Dispatch Team
- software-engineer

## Technical Notes

### TN-1: UUID Format Validation (Conditional)

UUID format validation applies only when the submitted value **differs from the current DB value**. If the submitted gc_uuid (after trimming) exactly matches the team's current `gc_uuid` in the database, skip validation entirely and preserve the value as-is. This handles legacy placeholder values (e.g., `lsb-varsity-uuid-2026`) that exist in production data -- admins can edit other fields without being forced to fix or clear a non-UUID gc_uuid in the same save.

The comparison must be against the raw DB string (not lowercased), so placeholders are matched exactly. Lowercasing normalization only applies to the new-value path.

Validation cases:
- **Empty after trim**: Always valid → store NULL (per TN-3).
- **Unchanged from DB**: Always valid → preserve as-is, no format check.
- **New or changed value**: Validate UUID format (reject if malformed), normalize to lowercase.

### TN-2: Uniqueness Enforcement

The partial unique index `idx_teams_gc_uuid ON teams(gc_uuid) WHERE gc_uuid IS NOT NULL` means SQLite will raise `IntegrityError` on duplicate non-NULL values. The handler should catch this and re-render the edit form with an error banner (per TN-4) rather than returning a generic error redirect.

### TN-3: Empty-to-NULL Normalization

Empty string input should normalize to NULL: `gc_uuid_value = gc_uuid.strip() or None`. This is the established pattern used in `_normalize_confirm_inputs` for the add-team flow.

### TN-4: Error Re-Render Pattern

When UUID validation or uniqueness enforcement fails, the POST handler re-renders `edit_team.html` directly (not a redirect) with HTTP 200, matching the confirm-page pattern. The template context must include:

- `edit_team`: A synthetic dict merging the user's submitted form values (name, program_id, classification, membership_type, gc_uuid) with read-only fields from a DB fetch (id, public_id, is_active, last_synced). This preserves the user's in-progress edits.
- `programs`: Fetched from DB (needed for the program dropdown).
- `opponent_link_count`: Fetched from DB (needed for the opponent connections section).
- `error`: A string describing the validation failure (e.g., "Invalid UUID format" or "This UUID is already assigned to another team"). Empty string when no error.

The GET handler (`edit_team_form`) must also pass `error: ""` to the template context so the template can unconditionally reference the variable.

The error is displayed as a top-of-form banner (not per-field inline), consistent with the established admin error pattern.

## Open Questions
None -- all questions resolved via SE consultation.

## History
- 2026-03-24: Created. SE consulted on edit handler patterns, validation approach, unique index constraint, and downstream effects.
- 2026-03-24: Set to READY after 2 internal review iterations + 1 Codex spec review iteration.

### Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Internal iteration 1 -- CR spec audit | 4 | 4 | 0 |
| Internal iteration 1 -- Holistic team (PM) | 0 | 0 | 0 |
| Internal iteration 1 -- Holistic team (SE) | 4 | 4 | 0 |
| Internal iteration 2 -- CR spec audit | 1 | 1 | 0 |
| Internal iteration 2 -- Holistic team (PM) | 0 | 0 | 0 |
| Internal iteration 2 -- Holistic team (SE) | 1 | 1 | 0 |
| Codex iteration 1 | 3 | 1 | 2 |
| **Total** | **13** | **11** | **2** |

- 2026-03-24: E-151-01 completed. All 9 ACs verified by PM. Epic set to COMPLETED.

### Implementation Review Scorecard
| Review Pass | Findings | Accepted | Dismissed |
|---|---|---|---|
| Per-story CR -- E-151-01 | 1 | 1 | 0 |
| CR integration review | 1 | 1 | 0 |
| Codex code review | 3 | 3 | 0 |
| **Total** | **5** | **5** | **0** |

### Documentation Assessment
No documentation impact. This epic adds an editable field to an existing admin page. No `docs/admin/` files exist to update, and the change does not introduce a new feature, endpoint, architecture change, schema change, or new user workflow -- it extends an existing edit form with one additional field.

### Context-Layer Assessment
1. **New convention, pattern, or constraint established?** No -- the conditional UUID validation pattern (TN-1) is specific to this form, not a project-wide convention.
2. **Architectural decision with ongoing implications?** No -- minor form field addition with no architectural impact.
3. **Footgun, failure mode, or boundary discovered?** No -- the legacy placeholder handling was already known and documented in TN-1.
4. **Change to agent behavior, routing, or coordination?** No.
5. **Domain knowledge discovered that should influence future epics?** No.
6. **New CLI command, workflow, or operational procedure introduced?** No.

All six triggers: **No**. No context-layer codification needed.

### Ideas Backlog Review
No CANDIDATE ideas are newly unblocked by this epic. E-151 is a narrow admin UI fix with no downstream dependencies.

### Vision Signals
29 unprocessed signals exist in `docs/vision-signals.md`. No new signals from this epic. Signals are advisory -- does not block archival.
