# E-138-01: Codex Review with Graceful Degradation

## Epic
[E-138: Full Dispatch Pipeline](epic.md)

## Status
`DONE`

## Description
After this story is complete, the implement skill's Phase 4 runs codex review against the epic worktree diff with graceful degradation: if headless codex times out or fails, the pipeline generates a review prompt, pauses for the operator to run it async, and resumes when findings are pasted (or "skip" is entered).

This story also fixes the codex prompt bug where codex in ephemeral mode may lack file access to read the rubric.

## Context
Phase 4 currently invokes the codex-review skill in headless mode. It does not handle timeout gracefully (exit 124 is reported to the user and the pipeline stops) and does not offer a prompt-generation fallback. The codex-review skill already has both headless and prompt-generation paths — this story wires the implement skill to use them as a degradation chain.

The codex prompt bug (TN-6) is folded into this story because the prompt-generation path is the degradation target — if the prompt doesn't work, the degradation path fails.

## Acceptance Criteria
- [ ] **AC-1**: Phase 4 invokes the codex-review skill with the epic worktree path (via `--workdir` from E-137-07). The diff is generated from the epic worktree, not the main checkout. Note: the epic worktree diff covers code stories only; context-layer-only stories are committed separately per E-137 TN-5.
- [ ] **AC-2**: If headless codex succeeds with findings: triage and remediate per TN-1 flow. Real findings are fixed (per E-137's triage simplification). Only false positives are dismissed.
- [ ] **AC-3**: If headless codex succeeds with no findings ("clean review"): skip to Phase 4b.
- [ ] **AC-4**: If headless codex times out (exit 124) or fails (non-zero exit): the pipeline falls to the prompt-generation path per TN-2. A codex review prompt is generated and presented to the user.
- [ ] **AC-5**: The pipeline pause UX communicates clearly with a message appropriate to the failure reason: for timeout — "Pipeline paused at codex review. Headless review timed out."; for other failures — "Pipeline paused at codex review. Headless review failed: [error]." In both cases, followed by: "Run this prompt async and paste findings when ready. Enter 'skip' to proceed without codex review."
- [ ] **AC-6**: When the user pastes findings: the pipeline resumes, parses the findings, and enters the triage/remediation flow.
- [ ] **AC-7**: When the user enters "skip" (or equivalent): the pipeline advances to Phase 4b without codex findings.
- [ ] **AC-8**: The codex prompt bug is fixed per TN-6: the rubric content is embedded in the prompt (or an explicit file-read instruction is included) so codex in ephemeral mode can access it.
- [ ] **AC-9**: Remediation spawns a new implementer (using the agent routing table based on finding domain) into the epic worktree directory. The implementer is spawned WITHOUT `isolation: "worktree"` and given the epic worktree path as their working directory. All story worktrees are already cleaned up by this point. The original dispatch team implementers may have been shut down, so a new spawn is the reliable path.
- [ ] **AC-10**: The 2-round circuit breaker applies to codex remediation per TN-4.

## Technical Approach
Rewrite Phase 4 in the implement skill to implement the degradation chain described in TN-1 and TN-2. The codex-review skill already supports both headless and prompt-generation paths — this story wires Phase 4 to use them in sequence.

For the codex prompt bug (TN-6), modify `scripts/codex-review.sh` to embed the rubric content in the prompt instead of referencing it by path. This ensures codex can access it regardless of execution mode.

For remediation, the implementer works directly in the epic worktree. Since all story worktrees are cleaned up by the time Phase 4 runs, the implementer is spawned without `isolation: "worktree"` and given the epic worktree path as their working directory.

## Dependencies
- **Blocked by**: None (E-137 is an epic-level dependency, not a story-level one)
- **Blocks**: E-138-02

## Files to Create or Modify
- `.claude/skills/implement/SKILL.md` (Phase 4 rewrite)
- `.claude/skills/codex-review/SKILL.md` (degradation chain integration)
- `scripts/codex-review.sh` (rubric embedding fix)

## Agent Hint
claude-architect

## Handoff Context
- **Produces for E-138-02**: The updated Phase 4 with codex review complete. Phase 4b (CR integration) is the next pipeline stage and needs to know the exit state of Phase 4a (findings remediated, clean review, or skipped).

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Degradation chain works: headless → timeout → prompt → pause → resume
- [ ] Codex prompt includes rubric content (bug fix verified)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing codex-review functionality

## Notes
This is the most complex story in E-138. It touches three files (mixed context-layer + script). Per routing precedence, this goes to claude-architect WITH worktree isolation.

## History
- 2026-03-19: Completed. All 10 ACs verified PASS. Additionally modified `.claude/rules/worktree-isolation.md` (not in original Files to Create or Modify) per dispatch signal from E-137 round 3 review — documents the Phase 4 remediation exception allowing implementers to work in the epic worktree during post-review remediation.
