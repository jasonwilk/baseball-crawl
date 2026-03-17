# E-118: Fix Documentation Bugs in Operations Guide

## Status
`COMPLETED`

## Overview
Fix three factual errors in `docs/admin/operations.md` discovered by Codex review of E-115 output. All three are line-level corrections in a single file -- wrong endpoint URL, invalid input example, and wrong follow-up path.

## Background & Context
E-115 delivered documentation updates for the E-100 schema rewrite. Codex review of E-115's output identified three bugs in `docs/admin/operations.md` where the documentation does not match the actual code behavior. Each bug was confirmed against the source code.

No expert consultation required -- these are factual corrections to match existing code, not new features or domain decisions.

## Goals
- Correct all three confirmed documentation bugs so `docs/admin/operations.md` accurately reflects the code

## Non-Goals
- Rewriting or restructuring the operations guide beyond the three fixes
- Updating any other documentation files
- Changing application code

## Success Criteria
- All three incorrect references in `docs/admin/operations.md` are replaced with correct information matching the source code

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-118-01 | Fix three documentation bugs in operations guide | DONE | None | docs-writer |

## Dispatch Team
- docs-writer

## Technical Notes

### Bug 1: Wrong bridge endpoint URL (~line 52)
The doc references `GET /teams/{team_uuid}/public-team-profile-id` (forward bridge). The actual code in `src/gamechanger/bridge.py:34-54` (`resolve_public_id_to_uuid()`) calls `GET /teams/public/{public_id}/id` (reverse bridge). Fix: update the endpoint reference.

### Bug 2: Bare UUID listed as accepted input (~line 69)
The "What the URL parser accepts" list includes bare UUIDs. While `url_parser.py` does parse them, the admin add-team flow at `src/api/routes/admin.py:915-918` explicitly rejects bare UUIDs with an error. Fix: remove the bare UUID line.

### Bug 3: Wrong follow-up path for discovered placeholders (~line 102)
The doc says to use `/admin/opponents` to connect a placeholder to a GameChanger URL. But discovered opponents are in the `teams` table (via `bulk_create_opponents` in `src/api/db.py:765`), while `/admin/opponents` renders `opponent_links` rows -- a different table. Fix: replace with the correct path (paste the GameChanger URL via the Add Team form at `/admin/teams`).

## Open Questions
None.

## History
- 2026-03-17: Created from Codex review findings on E-115 output
- 2026-03-17: COMPLETED. Fixed 3 doc bugs in operations.md found by Codex review of E-115. Bug 1 (wrong bridge URL) and Bug 2 (bare UUID) were already correct from E-115-01. Bug 3 (wrong /admin/opponents follow-up path) fixed — now points to Add Team form. No documentation impact (epic IS the doc fix). Context-layer assessment: no new conventions (no), no new agent capabilities (no), no new rules/skills (no), no CLAUDE.md updates needed (no), no settings changes (no), no memory structure changes (no).
