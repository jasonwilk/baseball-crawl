# IDEA-070: Admin-UI delete-team path does not clean reports.team_id

## Status
`CANDIDATE`

## Summary
The admin-UI delete-team HTTP handler (`src/api/routes/admin.py::delete_team` → `_delete_team_cascade` → `src/reports/generator.py::cascade_delete_team`) does not gate on `is_team_eligible_for_cleanup` and the canonical `cascade_delete_team` helper does not clean `reports.team_id`. Since `reports.team_id NOT NULL REFERENCES teams(id)` (`migrations/001_initial_schema.sql:611`) has no `ON DELETE` clause, deleting a team that owns any `reports` rows via the admin UI would FK-violate on the final `DELETE FROM teams` step. The report-deletion code path at `admin.py:3261` already excludes such teams via `is_team_eligible_for_cleanup` Guard 3 (`src/reports/generator.py:1672`); the admin-UI delete path has no equivalent gate.

## Why It Matters
Two concerns:

1. **Data-loss protection for coaching reports.** Coach-generated reports (the `reports` table) are first-class artifacts. Deleting the underlying team — even via the admin UI — should either preserve the reports, preserve the team row as an FK anchor, or explicitly warn the operator about what will be lost. Silent FK crash is the worst of three options.
2. **Latent FK crash in the rare case.** When an admin deletes a team with attached reports, the cascade runs through the canonical helper (after E-221-05), encounters an unhandled `reports.team_id` FK constraint, and raises `IntegrityError` at the final `DELETE FROM teams` step. In practice we have not hit this because teams with reports are rare in our current dispatch patterns, but the bug is real.

This is the next layer of the same class of bug E-221-05 closed for the perspective-carrying stat tables (R8-P1-1/2/3): "every FK column referencing `teams(id)` must be cleaned by every delete path that targets a team row." E-221-05 consolidated the two cascade paths onto the canonical helper, which makes the fix cheaper — add either a new guard in `cascade_delete_team` or a new eligibility check in the admin-UI handler, and both paths inherit the protection.

## Rough Timing
Promotable at any time — no blockers. Natural triggers:
- First real occurrence (an admin deletes a team with reports and hits the FK crash).
- Next time we touch the cascade delete code for any other reason (natural consolidation opportunity).
- If the admin UI grows any additional delete paths or if we add new FK columns referencing `teams(id)` (because each new column is another chance to get this wrong).

## Dependencies & Blockers
None. E-221-05 already landed the canonical-helper consolidation that makes a single-source fix possible.

## Open Questions
- **Hard-block vs. soft-delete-first**: Should the admin-UI path hard-block the delete (following the report-deletion path's pattern via `is_team_eligible_for_cleanup`), or should it first delete the `reports` rows (and their child tables) before the teams cascade? The former protects the reports; the latter protects the operator's ability to delete a stale team.
- **Operator warning UI**: If the chosen fix deletes `reports` first, should the existing informed-consent confirmation template (`admin/confirm_delete.html`) be extended with a "the following reports will be deleted" section? This would parallel the existing cross-perspective impact panel.
- **Unified "what will happen" panel**: Related to the existing teams-row-retention case surfaced in E-221-05: both the reports-gap case and the teams-row-retained case are "here's what will and won't happen" scenarios. Worth considering whether they should both feed a unified preview panel in the confirmation template rather than bolting on separate UI for each.
- **Full FK audit**: Are there other FK columns referencing `teams(id)` that the canonical helper still does not clean? A grep audit before landing any fix would be prudent so we do not ship a partial fix.
- **`cleanup_orphan_teams` vs `cascade_delete_team` asymmetry (added 2026-04-13 from E-221 Phase 4a CR observation)**: CR's Phase 4a integration review flagged a pre-existing structural gap where `cleanup_orphan_teams` at `src/reports/generator.py:1574` and `cascade_delete_team` at `src/reports/generator.py:1518` both implement team-deletion paths but with subtly different cleanup coverage — notably around the reports-path orphan detection boundary. CR framed this as "not a new bug, possibly worth a future invariant audit." Same failure-mode shape as this idea's core concern: one team-deletion path has FK coverage another path lacks. Worth rolling into this idea's scope when it's promoted to an epic so the fix covers both paths in one pass rather than surfacing the same class of bug twice. The invariant to enforce: every team-deletion path must close the same set of FK references.

## Notes
Source: code-reviewer's E-221-05 round 1 review finding (2026-04-13). DISMISSED for E-221-05 scope per the implement skill Phase 3 Step 5 triage rule: "Invalid finding... targets code not modified by the story: Dismiss with explanation." E-221-05's charter was R8-P1-1 (perspective scoping) + absorbed IDEA-069 (cascade consolidation), not "every FK column must be cleaned by every delete path."

Related:
- E-221-05 (closed the cross-perspective cases of this bug class via canonical-helper delegation).
- `src/reports/generator.py::is_team_eligible_for_cleanup` Guard 3 (the existing gate the admin-UI path lacks).
- `migrations/001_initial_schema.sql:611` (`reports.team_id NOT NULL REFERENCES teams(id)` — the FK column without `ON DELETE`).

---
Created: 2026-04-13
Last reviewed: 2026-04-13
Review by: 2026-07-13
