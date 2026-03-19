# E-138-02: Post-Codex Code-Reviewer Integration Pass

## Epic
[E-138: Full Dispatch Pipeline](epic.md)

## Status
`TODO`

## Description
After this story is complete, the implement skill includes a NEW Phase 4b: a code-reviewer integration review of the full epic diff. This holistic review catches cross-story interactions, naming inconsistencies, and architectural issues that per-story CR (Phase 3) cannot detect. The integration review runs after codex review (Phase 4a) and before the commit gate (Phase 5).

## Context
Per-story CR during dispatch (Phase 3) reviews each story's changes in isolation. It is effective for story-level bugs and AC verification but cannot catch issues that emerge when multiple stories' changes interact. The integration review fills this gap by reviewing the combined epic diff.

Jason confirmed this is valuable: "review with the entire change with @code-reviewer and start a team to remediate anything that comes up." Per TN-3, the integration review has a different scope and purpose than per-story review.

## Acceptance Criteria
- [ ] **AC-1**: A new Phase 4b is added to the implement skill, positioned after Phase 4a (codex review) and before Phase 5 (closure).
- [ ] **AC-2**: Phase 4b routes the full epic diff to the code-reviewer with a context block per TN-3: full diff (`git diff main` from epic worktree), story manifest, Technical Notes, and the epic's Goals and Success Criteria sections. Note: the epic worktree diff covers code stories only; context-layer-only stories are committed separately per E-137 TN-5.
- [ ] **AC-3**: The code-reviewer assignment template distinguishes integration review from per-story review. The template includes: "This is an integration review of the full epic diff. Focus on cross-story interactions, naming consistency, import conflicts, and architectural issues. Per-story bugs have already been reviewed during dispatch."
- [ ] **AC-4**: Integration review findings are routed to a newly spawned implementer (selected via agent routing table based on finding domain) for remediation. The implementer is spawned WITHOUT `isolation: "worktree"` and works in the epic worktree directory.
- [ ] **AC-5**: The 2-round circuit breaker applies per TN-4. If round 2 still has findings, escalate to the user.
- [ ] **AC-6**: All real findings are fixed per E-137's triage simplification. Only false positives are dismissed.
- [ ] **AC-7**: For large epics where the full diff may exceed CR's context window, the assignment template organizes changes by story and instructs CR to request specific file contents as needed.
- [ ] **AC-8**: Phase 4b is skipped if "and review" was not specified (the pipeline only runs when explicitly triggered).

## Technical Approach
Add a new Phase 4b section to the implement skill between the existing Phase 4 and Phase 5. The code-reviewer is already spawned as infrastructure during Phase 2 — no new spawning needed. The main session generates the full epic diff from the epic worktree and constructs the integration review context block.

The integration review assignment template should be clearly distinct from the per-story review template (Phase 3 Step 5) to avoid confusion. Include the story manifest so the CR understands the scope of each story's contribution.

## Dependencies
- **Blocked by**: E-138-01
- **Blocks**: E-138-03

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (new Phase 4b)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-138-03**: Phase 4b complete with all integration review findings resolved. Phase 5 (closure/commit) is the next and final pipeline stage.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Integration review template is clearly distinct from per-story review template
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing Phase 3 per-story review

## Notes
Pure context-layer story (only the implement skill). Runs without worktree isolation.
