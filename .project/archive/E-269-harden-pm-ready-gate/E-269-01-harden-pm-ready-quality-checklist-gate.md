# E-269-01: Harden the PM READY Quality-Checklist Gate (story-file existence + consultation completeness)

## Epic
[E-269: Harden the PM READY Quality-Checklist Gate](epic.md)

## Status
`DONE`

## Description
After this story is complete, the PM Quality Checklist in `.claude/agents/product-manager.md` binds two new items — story-file existence per Stories-table row, and consultation completeness against the Consultation Triggers table — and the existing soft consultation line is tightened to point at the new per-domain verdict. This closes the READY-gate leak that let E-267 and E-268 reach READY malformed (a phantom story row, and a silently-skipped api-scout consult on GameChanger-payload ACs).

## Context
The Quality Checklist (`.claude/agents/product-manager.md`, ~L254–269) is the single gate both the plan-skill path and the ad-hoc-spawn path cross before READY, and it currently verifies neither story-file existence per table row nor consultation completeness against the triggers table (PM def L80–86). See epic Background & Context and Technical Notes TN-1..TN-4 for the full diagnosis and design.

## Acceptance Criteria
<!-- Verifiable by reading the resulting `.claude/agents/product-manager.md`. -->
- [ ] **AC-1 (story-file existence item)**: The Quality Checklist contains a binding item requiring that every story listed in the epic's Stories TABLE has a real story file on disk carrying acceptance criteria, a Files-to-Create-or-Modify list, and a Definition of Done; a table row with no file, OR a stub with TBD/placeholder sections, FAILS the gate. The item's wording makes clear the check iterates the Stories-table rows (not the stories the PM happens to have in context), per Technical Notes TN-2.
- [ ] **AC-2 (consultation-completeness item)**: The Quality Checklist contains a binding item requiring, for each domain the epic touches per the Consultation Triggers table (PM def L80–86), an explicit per-domain verdict — CONSULTED (input captured in Technical Notes) or WAIVED (one-line reason) — and stating that a silent omission is not a waiver. The item explicitly notes that GameChanger payload / data-availability ACs trigger api-scout, per Technical Notes TN-2.
- [ ] **AC-3 (reconcile the soft line)**: The pre-existing consultation item (currently "Expert consultation completed (or 'No consultation required' noted)") is tightened to point at the AC-2 per-domain verdict, so the checklist carries no soft-blanket-vs-per-domain contradiction, per Technical Notes TN-3.
- [ ] **AC-4 (honest ceiling, no overclaim)**: The change states the honest ceiling per Technical Notes TN-4 (the gate converts a silent skip into an explicit, visible verdict; it does NOT guarantee a correct waiver and does not add a hard "must consult" gate) and does NOT contain language claiming the gate prevents all bad consultation decisions.
- [ ] **AC-5 (retrospective catch demonstration — planning-time artifact)**: This story's Notes section contains a written walkthrough (authored at planning time — see Notes) demonstrating that, applied to E-267's and E-268's READY-state inputs, each new item flags the actual defect: the story-file-existence item FAILS on E-268's phantom `E-268-01` (table row, no file), and the consultation-completeness item FAILS on E-267's api-scout consult skipped on the GameChanger-payload-semantics ACs. Each mapping cites the specific defect and the item that catches it. The dispatched implementer verifies the walkthrough still matches the checklist wording it ships (per Technical Notes TN-5, the walkthrough is planning documentation, not an implementation deliverable).
- [ ] **AC-6 (scope containment)**: The only IMPLEMENTATION file the story ships is `.claude/agents/product-manager.md`, and only its Quality Checklist section — no new rule file, no `workflow-discipline.md` change, no plan-skill change (per epic Non-Goals). The AC-5 walkthrough in this story's Notes is a planning-time artifact, not an implementation file change (per Technical Notes TN-5), so AC-5 and AC-6 are consistent.

## Technical Approach
Edit only the Quality Checklist section of `.claude/agents/product-manager.md` (~L254–269) to add the two binding items and tighten the existing consultation line, per epic Technical Notes TN-1..TN-4. The AC-5 walkthrough is already captured in this story's Notes at planning time (verify it still matches the shipped checklist wording). The exact wording of the checklist items is the implementer's (claude-architect's) call, provided the ACs above are verifiable in the result.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/agents/product-manager.md` (Quality Checklist section only) — the sole implementation deliverable
- (The AC-5 retrospective walkthrough already lives in this story's Notes as a planning-time artifact — NOT an implementation file change; see epic Technical Notes TN-5.)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The two new checklist items are present, binding, and non-contradictory with the tightened consultation line
- [ ] The AC-5 walkthrough is recorded and correctly maps each E-267/E-268 defect to the item that catches it
- [ ] Follows context-layer conventions (see CLAUDE.md)
- [ ] No regressions in existing tests (no code touched)

## Notes
Context-layer story — routes to claude-architect per the Routing Precedence in `.claude/rules/agent-routing.md`. This story hardens the very checklist the PM uses to gate READY.

### AC-5 retrospective-catch walkthrough (planning-time artifact)

Applying the two new binding Quality-Checklist items to the READY-state inputs of the two epics that leaked this session:

**E-268 (phantom story) — caught by the story-file-existence item.**
- READY-state input: the epic's Stories table listed row `E-268-01`, but no `E-268-01-*.md` story file existed on disk at the time it was set READY.
- New item AC-1 (story-file existence): "every story listed in the epic's Stories TABLE has a real story file on disk carrying acceptance criteria, a Files-to-Create-or-Modify list, and a Definition of Done; a table row with no file … FAILS the gate." Iterating the Stories-TABLE rows, `E-268-01` has no file → the item FAILS → E-268 cannot reach READY.
- Why the old checklist missed it: it iterated the stories the PM had in context, not the table rows, so a row without a file was invisible.

**E-267 (silently-skipped api-scout consult) — caught by the consultation-completeness item.**
- READY-state input: E-267 carried safety-critical GameChanger-payload / data-availability ACs (game-grain schedule threading, boxscore-shape corroboration) but recorded no api-scout verdict — the consult was simply absent, not waived.
- New item AC-2 (consultation completeness): "for each domain the epic touches per the Consultation Triggers table, record an explicit per-domain verdict — CONSULTED … or WAIVED … a silent omission is not a waiver," and "GameChanger payload / data-availability ACs trigger api-scout." E-267's payload ACs trigger api-scout; no per-domain verdict was recorded → the item FAILS → E-267 cannot reach READY until api-scout is CONSULTED (or an explicit, challengeable WAIVER is written).
- Why the old checklist missed it: L257 was a soft blanket self-attestation ("Expert consultation completed (or 'No consultation required' noted)") not bound to the triggers table, so a silently-skipped domain passed.

Both defects map to a specific new binding item that FAILS on the actual READY-state input, demonstrating the two items close the leak they were designed for. (Honest ceiling per epic TN-4: the consultation item converts a *silent* skip into an *explicit, visible* verdict the user can challenge; it does not guarantee a correct waiver.)
