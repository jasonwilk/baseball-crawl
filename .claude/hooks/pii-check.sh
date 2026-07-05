#!/bin/bash
# .claude/hooks/pii-check.sh
# Claude Code PreToolUse hook: blocks git commit if staged files contain PII
#
# This hook fires before any Bash tool call in Claude Code.
# It checks if the command is a git commit, and if so, runs the PII scanner.
# Denial is communicated via JSON output, NOT via exit code.
# Always exits 0 -- even on denial.

# Require jq for JSON parsing. If not available, fail open.
if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only intercept git commit commands. Allow global options between `git` and
# `commit` so no invocation form can evade interception:
#   - separate-arg flags with a value: `git -C <dir>`, `git -c key=val`,
#     `git --git-dir <path>`, `git --work-tree <path>`, `git --namespace <ns>`
#     -- including quoted values with spaces: `git -C "a b"` / `git -C 'a b'`
#   - `=`-joined and argless long flags: `git --git-dir=<path>`, `git --no-pager`
# The value-flag list is kept EXPLICIT on purpose: a generic "consume a token
# after any --flag" rule would let `git --no-pager commit` swallow `commit` as
# the flag's argument and skip the hook (a false negative). With the explicit
# list, `--no-pager` is consumed by the argless `\s+--\S+` branch (one token
# only), leaving `commit` to match -- so real commits are never skipped.
if ! echo "$COMMAND" | grep -qE "(^|[;&|]\s*)git(\s+(-C|-c|--git-dir|--work-tree|--namespace)\s+(\"[^\"]*\"|'[^']*'|\S+)|\s+--\S+)*\s+commit"; then
  exit 0
fi

# Run PII scanner against staged files via module invocation
# Run scanner; capture output
SCAN_OUTPUT=$(cd "$CLAUDE_PROJECT_DIR" && python3 -m src.safety.pii_scanner --staged 2>&1)
SCAN_EXIT=$?

if [ $SCAN_EXIT -ne 0 ]; then
  # The scanner exits non-zero for BOTH an actual PII detection AND an
  # infrastructure failure (scanner crash, missing interpreter, import error),
  # so the exit code alone cannot tell them apart. Distinguish by the scanner's
  # OUTPUT: a real detection always prints the "[PII BLOCKED]" marker (via
  # report_violations); an infra failure never does. Both cases block the commit
  # (fail closed -- a broken scanner must not let a commit through), but with
  # distinct messages so an infra failure is not mislabeled as a PII hit.
  if echo "$SCAN_OUTPUT" | grep -qF '[PII BLOCKED]'; then
    # Actual PII detection -- block the tool call
    jq -n --arg reason "$SCAN_OUTPUT" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: ("PII detected in staged files. Move sensitive files to /ephemeral/ or remove PII before committing.\n\n" + $reason)
      }
    }'
  else
    # Scanner infrastructure failure (not a PII detection) -- block the commit
    # because the safety scan could not complete, and say so clearly.
    jq -n --arg reason "$SCAN_OUTPUT" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: ("PII scanner failed to run (infrastructure error -- NOT a PII detection). The commit is blocked because the safety scan could not complete. Fix the scanner, then retry the commit.\n\n" + $reason)
      }
    }'
  fi
  exit 0
fi

# No PII found -- allow the commit
exit 0
