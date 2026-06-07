# E-231-01: Output-Integrity Discipline Rule

## Epic
[E-231: Harness Output-Reliability -- Detect, Defend, and Report](../E-231-harness-output-reliability/epic.md)

## Status
`DONE`

## Description
After this story is complete, every agent and the main session will load an always-on discipline rule that defines the tool-output failure taxonomy (empty / truncated / garbled), prescribes how to detect and respond to it (independent-channel cross-check, retry, escalate), and prohibits the two behaviors that turned channel flakiness into thrash during E-230: asserting/relaying unseen content, and co-batching a report with the same-batch command whose output it reports.

## Context
This rule covers the failure class that tooling CANNOT catch: garbled-but-nonempty output (wrong line numbers, stale content, a different file's bytes, a command echoed instead of executed). A PostToolUse hook can flag an empty read or an edit that did not land, but it cannot tell that a nonempty read returned the wrong bytes -- only an agent applying discipline can. This rule is the behavioral half of the detect-and-defend layer; E-231-02 is the tooling half. It is also the structural sibling of the committed clean-reread-before-defect discipline (`.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`) and the read-findings-before-triage lesson: a memory reminds, a "**"-loaded rule binds every agent every session.

## Acceptance Criteria
- [ ] **AC-1**: Given the rule file is created under `.claude/rules/`, when any agent or the main session starts a session, then the rule is loaded because its front-matter declares `paths: "**"`.
- [ ] **AC-2**: The rule names the three failure modes explicitly -- **empty**, **truncated**, and **garbled** -- and gives concrete examples of garbled output (wrong line numbers, stale/mismatched content, a different file's bytes, a command echoed instead of executed).
- [ ] **AC-3**: The rule prescribes the concrete response protocol per epic Technical Notes (Cross-check protocol): when a target known/expected to be non-empty returns empty/truncated/garbled output, treat it as a FAILURE; cross-check via an independent channel (e.g., `wc -l` / `wc -c` / `sed -n` / `cat -n`); retry; if a clean result still cannot be obtained, escalate rather than asserting. When two channels disagree, the clean read wins over a flaky empty/garbled result (a "no files found" Glob is not proof of absence under a flaky channel).
- [ ] **AC-4**: The rule prohibits asserting or relaying any file content or tool outcome the agent has not seen cleanly in its own context.
- [ ] **AC-5**: The rule prohibits co-batching a relay/report with the same-batch command whose output it reports (report actual output already in context, never expected output).
- [ ] **AC-6**: The rule cross-references a STABLE committed repo target -- the PM memory `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md` (the clean-reread-before-defect discipline this rule generalizes) -- and the related E-231-02 hook and E-231-03 triage gate. It MAY reference the read-findings-before-triage lesson conceptually, but MUST NOT link `feedback_read_findings_before_triage.md` by path (that file lives in non-version-controlled main-session auto-memory and is not linkable/verifiable from a worktree).
- [ ] **AC-7**: Context-budget leanness (per epic Technical Notes, Context-fundamentals governing constraint, and `.claude/skills/context-fundamentals/SKILL.md`). Because the rule is `paths: "**"` (always-loaded for every agent on every session, on top of the ambient context-layer baseline), it is minimal and tight -- it cross-references existing memories/rules (e.g., the committed `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`) rather than restating their content, and is concise enough to justify its permanent always-loaded per-session token cost (not an essay).

## Technical Approach
This is a context-layer rule file. claude-architect owns the design and final content per the context-layer routing precedence. The rule belongs in `.claude/rules/` with `"**"` front-matter so it loads for every agent and the main session. The failure taxonomy, the independent-channel cross-check protocol, and the two prohibitions (assert-unseen, co-batch-report) are specified in the epic Technical Notes; this story's job is to codify them as a binding rule. The final filename is the implementer's choice (e.g., `tool-output-integrity.md`).

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/tool-output-integrity.md` (new; final name at implementer's discretion)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (N/A -- context-layer rule file; verification is by inspection of front-matter scope and content per ACs)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The rule covers the garbled-but-nonempty gap that no hook can detect (epic Technical Notes, Non-Goals). It is the behavioral complement to E-231-02's tooling and the structural codification of the clean-reread-before-defect discipline (committed at `.claude/agent-memory/product-manager/feedback_clean_reread_before_defect.md`) and the read-findings-before-triage lesson (referenced conceptually -- its memory file is non-version-controlled main-session auto-memory).
