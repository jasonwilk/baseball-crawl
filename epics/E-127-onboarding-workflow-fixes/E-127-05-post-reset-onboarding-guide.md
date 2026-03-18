# E-127-05: Post-Reset Onboarding Guide

## Epic
[E-127: Onboarding Workflow Fixes](epic.md)

## Status
`TODO`

## Description
After this story is complete, `docs/admin/post-reset-guide.md` will document the end-to-end operator workflow for going from a fresh `bb db reset` to a working local environment with real GameChanger data. This bridges the gap between "I just reset the database" and "I can see real team data on the dashboard."

## Context
The post-reset workflow involves multiple tools (CLI, admin UI, crawlers) that are documented individually but not as a connected workflow. During a real session (2026-03-18), the operator didn't know the admin UI add-team flow existed and manually SQL-updated the teams table. This guide connects the dots: reset -> credentials -> add teams via UI -> verify dev user access -> crawl. The workflow outline is in epic Technical Notes TN-5.

## Acceptance Criteria
- [ ] **AC-1**: A new file `docs/admin/post-reset-guide.md` exists with a step-by-step workflow covering: database reset, credential setup, adding teams via admin UI, verifying dev user access, and running initial crawl.
- [ ] **AC-2**: The guide references the admin UI add-team flow (`/admin/teams`) as the primary path for adding real teams (not manual SQL).
- [ ] **AC-3**: The guide mentions `bb creds import` (with multi-format support from E-127-01), `bb creds extract-key` (for client key setup from E-127-02), and `bb creds refresh` as the credential setup steps.
- [ ] **AC-4**: The guide notes that the dev user is auto-assigned to member teams (per E-127-03) and what to verify.
- [ ] **AC-5**: The guide follows the existing documentation style in `docs/admin/` (check existing files for tone and formatting conventions).

## Technical Approach
Read existing docs in `docs/admin/` for style reference. The guide should be concise and action-oriented -- a runbook, not an architecture doc. Reference existing commands and UI pages rather than duplicating their documentation. The workflow outline is in epic Technical Notes TN-5.

Key files to study: `docs/admin/` (existing admin guides for style).

## Dependencies
- **Blocked by**: None (docs-writer writes from story specs, not from implementation)
- **Blocks**: None

**Dispatch note**: This guide references behavior from E-127-01 (multi-format import), E-127-02 (extract-key), E-127-03 (dev user auto-assignment), and E-127-04 (admin nav). It is technically independent (docs-writer writes from specs) but should be dispatched last or reviewed after those stories merge to ensure accuracy.

## Files to Create or Modify
- `docs/admin/post-reset-guide.md` -- new file

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Guide is accurate and references correct commands/URLs
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
