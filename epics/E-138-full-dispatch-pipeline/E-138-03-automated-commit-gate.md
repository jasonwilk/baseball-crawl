# E-138-03: Automated Commit Gate

## Epic
[E-138: Full Dispatch Pipeline](epic.md)

## Status
`TODO`

## Description
After this story is complete, the implement skill's Phase 5 closure sequence is wired to the full pipeline: after both review passes (codex + CR integration) complete, the pipeline runs the closure merge (epic worktree → main from E-137), PII scan, presents the commit summary, and waits for operator approval before committing. The "and review" pipeline ends with a clean, reviewed, operator-approved atomic commit.

## Context
Phase 5 currently handles closure mechanics (validate work, update epic, archive, commit). With the full pipeline, Phase 5 is the final stage — all review findings have been resolved in Phases 4a and 4b. Phase 5's commit step now follows the epic worktree → main merge sequence (from E-137) and requires no changes to the review flow itself.

The main work here is ensuring Phase 5 correctly chains after the new Phases 4a and 4b, and that the Workflow Summary diagram reflects the complete pipeline.

## Acceptance Criteria
- [ ] **AC-1**: Phase 5 Step 10 uses E-137's closure merge sequence (epic worktree → main patch → PII scan → user approval → commit → cleanup) and is documented as the final stage of the "and review" pipeline. Context-layer-only story changes (per E-137 TN-5) are committed in a separate follow-up commit after the epic commit.
- [ ] **AC-2**: The commit summary presented to the user includes: epic ID and title, number of stories, codex review outcome (clean/findings fixed/skipped), integration CR outcome (clean/findings fixed), and the file list.
- [ ] **AC-3**: The user must explicitly approve before the commit happens. "Skip" or silence does not auto-commit.
- [ ] **AC-4**: If the user rejects the commit (e.g., "wait" or "not yet"), the pipeline pauses. The epic worktree is preserved. The user can resume later with "commit" or inspect the changes.
- [ ] **AC-5**: The Workflow Summary diagram at the end of the implement skill reflects the complete pipeline: Phase 3 (dispatch + per-story CR) → Phase 4a (codex review + degradation) → Phase 4b (CR integration review) → Phase 5 (closure + commit).
- [ ] **AC-6**: The Phase 4/5 boundary is clean: Phase 4 handles all review/remediation; Phase 5 handles all closure mechanics (status updates, archive, commit). No review logic in Phase 5.

## Technical Approach
Phase 5's closure sequence was already modified by E-137-01 (epic worktree → main merge). This story ensures the Phases 4a → 4b → 5 pipeline is correctly documented as a continuous flow, the commit summary includes review outcomes, and the Workflow Summary diagram is updated end-to-end.

The commit rejection/pause behavior is simple: the pipeline waits for user input. If the user says "not yet," the session stays open with the epic worktree intact. The user can say "commit" later to resume. No persistent state needed.

## Dependencies
- **Blocked by**: E-138-02
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (Phase 5 commit summary, Workflow Summary diagram)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Workflow Summary diagram reflects complete pipeline end-to-end
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing Phase 5 closure mechanics

## Notes
Lightest story in E-138. Most of the heavy lifting was done in E-137-01 (closure merge) and E-138-01/02 (review pipeline). This story wires them together and updates the diagram.
