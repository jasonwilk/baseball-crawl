# E-125-07: Claude Hooks PII Scanner Invocation Update

## Epic
[E-125: Full-Project Code Review Remediation](epic.md)

## Status
`TODO`

## Description
After this story is complete, `.claude/hooks/pii-check.sh` will invoke the PII scanner via `python3 -m src.safety.pii_scanner` instead of running the script file directly. This aligns with E-125-06's removal of `sys.path` manipulation from `pii_scanner.py` and ensures the Claude Code pre-commit hook works correctly with the editable install.

## Context
Review 04 finding #7 identified that `src/safety/pii_scanner.py` uses `sys.path.insert()` to bootstrap imports, violating the python-style rule. E-125-06 removes the `sys.path` manipulation and updates `.githooks/pre-commit`. This companion story updates `.claude/hooks/pii-check.sh`, which also invokes the scanner directly via `python3 "$SCANNER" --staged` (line 32). Since `.claude/hooks/` is a context-layer path, this change must route to claude-architect per the routing precedence rule.

## Acceptance Criteria
- [ ] **AC-1**: `.claude/hooks/pii-check.sh` invokes the PII scanner via `python3 -m src.safety.pii_scanner --staged` (or equivalent module invocation) instead of `python3 "$SCANNER" --staged`
- [ ] **AC-2**: The hook still correctly blocks commits when PII is detected (deny JSON output on scanner failure)
- [ ] **AC-3**: The hook still allows commits when no PII is found (exit 0)

## Technical Approach
Replace the direct script invocation `python3 "$SCANNER" --staged` with `python3 -m src.safety.pii_scanner --staged`. The `SCANNER` variable and the file-existence check (`[ ! -f "$SCANNER" ]`) can either be updated to check for the module path or replaced with a simpler approach since module invocation doesn't require the file path. The `CLAUDE_PROJECT_DIR` variable is still useful for setting the working directory if needed.

## Dependencies
- **Blocked by**: None (can run in parallel with E-125-06; the invocation change is the same regardless of whether sys.path is removed first)
- **Blocks**: None

## Files to Create or Modify
- `.claude/hooks/pii-check.sh`

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Hook tested manually (commit with/without PII triggers correct behavior)
- [ ] No regressions in existing hooks

## Notes
- This is a minimal context-layer change -- one line in a shell script. Split from E-125-06 solely because `.claude/hooks/` is a context-layer path that must route to claude-architect.
- The `.githooks/pre-commit` equivalent change is handled by E-125-06 (software-engineer).
