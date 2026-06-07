# E-231-03: Force-Read-Findings-Before-Triage Gate

## Epic
[E-231: Harness Output-Reliability -- Detect, Defend, and Report](../E-231-harness-output-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, both review skills (`codex-review` and `codex-spec-review`) will carry a required pre-triage read-receipt gate: before any triage tool or action runs against a review result, the agent must persist the large review output to a file and confirm it read the FULL file (not a preview). This converts the read-findings-before-triage lesson into a structural gate.

## Context
In the E-230 dispatch, the main session fired a triage question off a 2KB preview of a 373KB persisted Codex result, mischaracterizing four valid findings as "2 LOW already-adjudicated." The behavioral lesson captured afterward (read-findings-before-triage) reminds but does not bind. Under a flaky channel, a preview can look like the whole result. A read-receipt gate -- requiring the agent to echo a value derived from the actual full file (e.g., its line count plus its last line) before triage may proceed -- makes the full read a structural precondition rather than a discipline an agent might skip.

## Acceptance Criteria
- [ ] **AC-1**: Given a review produces output to be triaged, when an agent reaches the triage step in `codex-review` SKILL.md, then the skill requires a read-receipt gate -- the review output is persisted to a file and triage is gated behind confirmation the full file was read (e.g., echoing the file's line count and last line from the actual file). The gate is a deliberate discipline aid / speed-bump, not a cryptographic guarantee (the receipt can in principle be produced without reading the middle); the skill text states this so the gate is not mistaken for proof.
- [ ] **AC-2**: The same read-receipt gate is present in `codex-spec-review` SKILL.md's triage step.
- [ ] **AC-3**: Both gates are written as required steps, not advisory suggestions (imperative MUST-language; triage may not proceed until the receipt is satisfied).
- [ ] **AC-4**: Both gates reference the motivating failure mode (acting on a preview/truncated view instead of the full persisted result, per the E-230 incident).
- [ ] **AC-5**: The gate cross-references a STABLE committed repo target -- the PM memory `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` -- and the E-231-01 output-integrity rule it structurally enforces. It MAY reference the read-findings-before-triage lesson conceptually, but MUST NOT link `feedback_read_findings_before_triage.md` by path (non-version-controlled main-session auto-memory, not linkable/verifiable from a worktree).

## Technical Approach
This is a context-layer change to two existing skill files. claude-architect owns skill content. The triage steps in `.claude/skills/codex-review/SKILL.md` and `.claude/skills/codex-spec-review/SKILL.md` gain an explicit, required read-receipt gate before any triage action. The implementer may also note (not necessarily gate) the triage steps in the plan/implement skills if review-finding triage occurs there; the two review skills are the required surface. The gate mechanism (persist-to-file + echo a full-file-derived value before triage) is described in this story's ACs and Context; the implementer chooses the exact receipt form.

Context-budget tension (per epic Technical Notes, Context-fundamentals governing constraint, and `.claude/skills/context-fundamentals/SKILL.md`): the gate requires reading the findings to COMPLETION -- a complete digest of every finding -- NOT brute-force ingestion of a large raw blob into context (e.g., a 373KB result would blow the red-zone budget). The objective is completeness of findings, not full-file token ingestion; the receipt proves the full file was processed without mandating that its raw bytes be held in context.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/skills/codex-review/SKILL.md` (add pre-triage read-receipt gate)
- `.claude/skills/codex-spec-review/SKILL.md` (add pre-triage read-receipt gate)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- skill content; verification by inspection of the triage steps per ACs)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Structural codification of the read-findings-before-triage lesson (committed sibling: `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`). Motivating incident: E-230 triage fired off a 2KB preview of a 373KB persisted Codex result.
