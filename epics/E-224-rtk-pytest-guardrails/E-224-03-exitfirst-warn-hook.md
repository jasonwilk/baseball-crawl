# E-224-03: Create Warn-Only `-x`/`--exitfirst` Detection Hook

## Epic
[E-224: RTK/Pytest Interaction Guardrails](epic.md)

## Status
`TODO`

## Description
After this story is complete, a new PreToolUse hook (`pytest-exitfirst-warn.sh`) will detect `-x`/`--exitfirst` in pytest commands and emit a warning message. The hook allows the command to proceed (warn, not block). It is registered in `.claude/settings.json` alongside the existing pytest-verbose hook.

## Context
The existing `pytest-verbose.sh` hook rewrites commands to inject `-v`. This hook has a different concern: warn about `-x`/`--exitfirst` without modifying the command. SE recommended a separate file for independent configurability and to avoid complicating the existing hook's rewrite logic. The user's original request specified "warns (does not block)."

## Acceptance Criteria
- [ ] **AC-1**: `.claude/hooks/pytest-exitfirst-warn.sh` exists and is executable
- [ ] **AC-2**: The hook detects `-x`, `--exitfirst`, and combined flags containing `x` (e.g., `-xvs`, `-vxs`) in pytest commands, per the regex pattern in Technical Notes
- [ ] **AC-3**: The hook only fires on pytest invocations (same detection pattern as `pytest-verbose.sh`: `(^|&&\s*|;\s*)(python3? -m pytest|pytest)\b`)
- [ ] **AC-4**: When triggered, the hook outputs a JSON response with `permissionDecision: "allow"` and a `permissionDecisionReason` warning message explaining the RTK truncation risk, per the format in Technical Notes
- [ ] **AC-5**: When triggered, the hook does NOT include `updatedInput` — the command executes unmodified
- [ ] **AC-6**: When no `-x`/`--exitfirst` is detected, the hook exits silently (`exit 0`, no JSON output)
- [ ] **AC-7**: The hook is registered in `.claude/settings.json` under `PreToolUse` > `Bash` matcher, alongside the existing hooks
- [ ] **AC-8**: The hook gracefully handles missing `jq` (exits 0 silently, same pattern as `pytest-verbose.sh`)

## Technical Approach
Create a new hook script following the pattern established by `pytest-verbose.sh`. Use the same pytest detection regex. Add `-x`/`--exitfirst` detection per the regex in Technical Notes. Output the warn-only JSON format (allow + reason, no updatedInput). Register in `settings.json` by adding an entry to the existing `PreToolUse:Bash` hooks array.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `.claude/hooks/pytest-exitfirst-warn.sh` (create)
- `.claude/settings.json` (modify — add hook registration)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Hook script follows project patterns (compare `pytest-verbose.sh`)
- [ ] Hook is registered and will fire on pytest commands containing `-x`/`--exitfirst`
