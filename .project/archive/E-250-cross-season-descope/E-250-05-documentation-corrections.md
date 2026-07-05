# E-250-05: Documentation corrections (architecture + roadmap + operations)

## Epic
[E-250: Root-Level Cross-Season / Multi-Season De-Scope](../E-250-cross-season-descope/epic.md)

## Status
`DONE`

## Description
After this story is complete, the human-facing docs reflect the schema and guard removals in E-250-02: the `team_opponents` row is gone from the architecture doc, the roadmap no longer instructs readers to "leave the column inert" for `gc_athlete_profile_id` (now dropped), and the operations runbook's delete-report cascade documents only the two surviving eligibility guards.

## Context
`docs/ROADMAP.md:205` currently says to leave `gc_athlete_profile_id` inert and "close the idea/epic" — the DROP in E-250-02 contradicts the "leave inert" instruction, so the doc must change in the same landing to stay internally consistent. `docs/admin/architecture.md:211` documents the now-dropped `team_opponents` table. `docs/admin/operations.md:497-506` documents the report-delete cascade as a 4-condition guard set (including `team_opponents` links and shared-games), but E-250-02 removes guards 2 and 4 — leaving only `is_active` and no-other-reports (Codex #8).

## Acceptance Criteria
- [ ] **AC-1**: `docs/admin/architecture.md` — the `team_opponents` table row/description (vetting pass cited :211) is removed or updated to reflect that the table no longer exists.
- [ ] **AC-2**: `docs/ROADMAP.md` — the "leave the column inert" instruction for `gc_athlete_profile_id` (vetting pass cited :205) is updated to reflect that the column is now DROPPED (E-250-02) and the identity epic E-104 is ABANDONED (E-250-07); no doc statement contradicts the drop.
- [ ] **AC-3**: `docs/admin/operations.md` — the "What happens when you delete a report" cascade documentation (~:497-506) is updated from FOUR conditions to the TWO that survive E-250-02's guard removal: "team is not active (`is_active = 0`)" and "no other reports reference this team". The "No `team_opponents` links" row (~:504) and the "No shared games with tracked teams" row (~:506) are removed, since guards 2 and 4 no longer exist (Codex #8). Any surrounding prose describing the 4-condition cascade is updated to match.
- [ ] **AC-4**: No remaining doc statement in the three files presents `team_opponents`, `gc_athlete_profile_id`, or the removed cleanup guards as present/inert/live.

## Technical Approach
Locate the current occurrences (line numbers are from the vetting pass and may have drifted), then correct them to describe the post-drop reality. Keep the edits minimal and factual — these are current-reality corrections, not roadmap re-planning.

## Dependencies
- **Blocked by**: E-250-02 (the schema removals these docs must reflect), E-250-07 (AC-2 prose asserts E-104 IS abandoned — that archive must happen first; Codex #3)
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/architecture.md` — remove/correct the `team_opponents` row (:211)
- `docs/ROADMAP.md` — correct the "leave the column inert" line (:205)
- `docs/admin/operations.md` — update the delete-report cascade from 4 conditions to 2 (~:497-506; remove the `team_opponents` and shared-games guard rows)

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Kept separate from the context-layer story (E-250-04) because `docs/**` is docs-writer's domain, not context-layer. The "same commit" consistency the brief flagged for ROADMAP:205 is satisfied by the epic's single atomic closure commit — all stories land together.
