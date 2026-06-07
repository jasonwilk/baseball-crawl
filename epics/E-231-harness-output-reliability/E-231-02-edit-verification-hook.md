# E-231-02: PostToolUse Edit/Write Verification Hook (Anchor)

## Epic
[E-231: Harness Output-Reliability -- Detect, Defend, and Report](../E-231-harness-output-reliability/epic.md)

## Status
`TODO`

## Description
After this story is complete, a PostToolUse hook will re-read the target of every Edit/Write and confirm the change actually landed -- catching the silent partial-edit-success class, the one failure mode with no behavioral workaround. The hook distinguishes transient flakiness (re-read empty while the file should exist -> retry once, then warn) from a genuinely-absent edit (file readable but the new content missing -> loud detect-and-signal failure), so legitimate edits are not falsely flagged under channel flakiness. PostToolUse fires after the write is already on disk; the hook detects and signals -- it does not and cannot prevent or roll back the write (see epic Technical Notes, PostToolUse capability).

## Context
This is the anchor story. When the channel silently reports an Edit/Write as successful but the bytes did not fully land, an agent proceeds believing the file is correct -- there is no behavioral workaround because the agent's own read-back can also be dark. A PostToolUse hook is the only place to catch this deterministically. This is greenfield: no PostToolUse hook exists today, only PreToolUse hooks (`worktree-guard.sh`, `pii-check.sh`). CA verified that PostToolUse hooks can read both `tool_input` and `tool_response` on stdin, so the hook has access to the Edit's `new_string` / the Write's content to verify against the on-disk file. Hook design constraints (shape, cheapness, transient-vs-absent semantics, the detect-and-signal-only PostToolUse capability) are in epic Technical Notes.

## Acceptance Criteria
- [ ] **AC-1**: Given an Edit or Write completes, when the PostToolUse hook fires, then the hook re-reads the target file and verifies the change landed -- for Edit, that `new_string` is present in the file; for Write, that the file content matches what was written -- per the hook design constraints and Corrected hook baseline in epic Technical Notes.
- [ ] **AC-2**: The hook is registered in `.claude/settings.json` under a `PostToolUse` array with a matcher matching both `Edit` and `Write` (e.g., `Edit|Write`).
- [ ] **AC-3**: Given the re-read returns empty/unreadable while the file should exist (transient flakiness), when the hook evaluates the result, then it retries once and, if still unreadable, warns -- it does NOT hard-fail. (Verified against the transient-empty case.)
- [ ] **AC-4**: On a confirmed verification failure (the edited file does not contain `new_string` after the write), the PostToolUse hook emits JSON `{"decision":"block","reason":"<file>: new_string not found after Edit/Write — edit did not land"}`. Per documented PostToolUse semantics this surfaces the reason to the model and halts continuation to the next turn; it does NOT and cannot prevent or roll back the write (the tool has already executed). The signal MUST be non-silent and name the file. (Verified against the absent case.)
- [ ] **AC-5**: Given an Edit/Write that did land correctly, when the hook fires, then it passes without a false alarm. (Verified against the present case.)
- [ ] **AC-6**: The hook is cheap -- it uses lightweight checks (e.g., `test -s` + `grep`) rather than a full diff -- and follows the established hook plumbing per epic Technical Notes (Corrected hook baseline): read tool JSON from stdin via `INPUT=$(cat)`, extract fields with `jq`. Note the PostToolUse signal field shape differs from PreToolUse (see AC-4).
- [ ] **AC-7**: The epic records the definitive PostToolUse capability as a Technical Note (NOT left to the implementer to determine): PostToolUse cannot block or roll back a write (docs blocking table: PostToolUse 'Can block? NO'; fires after the tool succeeds). The hook therefore delivers detect-and-signal only, using top-level `decision:"block"`+`reason` (NOT `hookSpecificOutput.permissionDecision`, which is the PreToolUse shape). Rollback/prevention is explicitly out of scope. Testable because: the Technical Note exists in epic.md, AND the implemented hook uses top-level `decision`, AND no AC claims prevention/rollback.
- [ ] **AC-8**: Terse, fire-on-real-signal output (per epic Technical Notes, Context-fundamentals governing constraint, and `.claude/skills/context-fundamentals/SKILL.md`). The hook emits NO output on the success/present case and on the transient-empty retry-then-recover case; it emits output ONLY on a genuine real-absent failure (and, at most, a single terse warning when a transient empty persists after the one retry). A hook that cries wolf on transient empties is context poison and is not acceptable.
- [ ] **AC-9**: Fail-open-but-announced on the hook's own internal failure. Following the established hook precedent (existing hooks fail open when `jq` is absent), if the hook cannot run its verification (e.g., `jq` missing), it MUST fail open -- it MUST NOT brick or flag the edit -- but it emits one terse "verification unavailable" line so the gap is visible, not silent. A verification aid must never become a blocker on its own missing dependency.

## Technical Approach
This is a context-layer change: a new hook script under `.claude/hooks/` plus registration in `.claude/settings.json`. claude-architect owns the hook wiring and settings registration; software-engineer advises on the verification predicate (how to robustly compare `new_string` / written content against the re-read on-disk file, and how to draw the transient-vs-absent line). The hook reads the PostToolUse stdin JSON for `tool_input` (the Edit's `new_string` or Write's content and the file path) and `tool_response`, re-reads the on-disk file, and applies the transient-vs-absent logic from epic Technical Notes. Keep the predicate cheap. The three test cases (present / absent / transient-empty) drive AC-3 through AC-5.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/hooks/<name>.sh` (new; final name at implementer's discretion -- e.g., `edit-verify.sh`)
- `.claude/settings.json` (add `PostToolUse` array entry with `Edit|Write` matcher)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (hook verified against present / absent / transient-empty cases per AC-3 through AC-5)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Anchor story -- highest value because the silent partial-edit-success class is the only failure with no behavioral workaround. Does not block the other E-231 stories; all five are independent. The garbled-but-nonempty gap this hook cannot cover is handled by the discipline rule (E-231-01).
