# E-091: Fix E-088 Opponent Data Model Defects

## Status
`READY`

## Overview
Fix three confirmed defects in the E-088 Opponent Data Model implementation identified by Codex code review and validated by SE and DE triage. All fixes are small, application-level only, with no schema changes required.

## Background & Context
Codex code review of E-088 (Opponent Data Model and Resolution) identified 4 findings. SE and DE triaged independently with consensus: fix 3 (#1, #2, #4), defer 1 (#3 -- CLI test coverage for thin Typer wiring). Findings #2 and #3 were already recorded as SHOULD FIX during E-088 closure (epic History, 2026-03-10). No expert consultation required -- all fixes are scoped by the SE and DE assessments against already-understood code.

## Goals
- Prevent accidental overwrite of auto-resolved opponent links via the admin connect endpoint
- Store hidden opponents in the database instead of silently dropping them (13 of 70 observed opponents affected)
- Eliminate false duplicate `public_id` warnings when different teams share the same opponent

## Non-Goals
- Schema changes (none needed per both SE and DE)
- CLI-level test coverage for `bb data resolve-opponents` (F3 -- deferred by consensus; thin Typer wiring, no data integrity risk)
- Partial unique index on `public_id` for defense-in-depth (DE suggestion -- deferred; application-level fix is sufficient for now)

## Success Criteria
- Auto-resolved opponent links are protected from manual overwrite
- Hidden opponents appear in the database with `is_hidden=1`
- Cross-team duplicate `public_id` warnings are eliminated
- All existing tests continue to pass

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-091-01 | Guard connect endpoint against overwriting resolved links | TODO | None | - |
| E-091-02 | Store hidden opponents instead of skipping them | TODO | None | - |
| E-091-03 | Scope duplicate public_id check to our_team_id | TODO | E-091-01 | - |

## Dispatch Team
- software-engineer

## Technical Notes
- TN-1: SE and DE both confirm no schema changes needed for any finding.
- TN-2: F2 and F3 were already identified by the code-reviewer during E-088 dispatch (recorded in epic History as SHOULD FIX). This epic addresses F2; F3 is deferred per consensus.
- TN-3: F1 is admin-only with single operator and UI already hides the button -- P2 is appropriate despite Codex P1 classification.
- TN-4: DE suggested optional partial unique index (migration 007) for F4 defense-in-depth. Excluded from scope -- the application-level fix is sufficient for now, and the index can be added later if cross-team scenarios grow.
- TN-5: SE notes the guard in E-091-01 should check whether `public_id` is already set (non-NULL), not `resolution_method`. DE suggests checking `resolution_method != "auto"`. Either approach works; implementing agent decides.

## Open Questions
None.

## History
- 2026-03-10: Created from Codex code review of E-088. SE and DE triage consensus: fix F1 (P2), F2 (P2), F4 (P5); defer F3. All three stories are independent, single-wave parallel dispatch.
- 2026-03-10: PM + SE refinement pass. Two findings applied: (1) E-091-02 story updated to address `ResolveResult.skipped_hidden` counter becoming dead code after the early-return removal -- rename to `stored_hidden`. (2) E-091-03 story updated to note `is_duplicate_opponent_public_id` is dead code (zero callers) -- SE may fix or delete. E-091-01 passed clean.
- 2026-03-10: Codex spec review triage (4 findings). F1 (file conflict): serialized E-091-01 → E-091-03 since both touch admin.py and test_admin_opponents.py; wave is now 01+02 parallel → 03. F2 (title ambiguity): renamed E-091-01 title from "Auto-Resolved" to "Resolved", added "regardless of resolution method" to AC-1. F3 (counter rename gap): added AC-5 to E-091-02 covering `skipped_hidden` → `stored_hidden` rename. F4 (confirm page path): revised E-091-03 AC-1/AC-2 to cover both confirm GET and save POST paths, AC-3 notes both call sites use the same scoped function.
