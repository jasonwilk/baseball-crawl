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

# Only intercept git commit commands
if ! echo "$COMMAND" | grep -qE '^git\s+commit'; then
  exit 0
fi

# Run PII scanner against staged files
SCANNER="$CLAUDE_PROJECT_DIR/src/safety/pii_scanner.py"

if [ ! -f "$SCANNER" ]; then
  # Scanner not yet installed (E-019-03 pending); allow commit
  exit 0
fi

# Run scanner; capture output
SCAN_OUTPUT=$(python3 "$SCANNER" --staged 2>&1)
SCAN_EXIT=$?

if [ $SCAN_EXIT -ne 0 ]; then
  # PII detected -- block the tool call
  jq -n --arg reason "$SCAN_OUTPUT" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("PII detected in staged files. Move sensitive files to /ephemeral/ or remove PII before committing.\n\n" + $reason)
    }
  }'
  exit 0
fi

# No PII found -- allow the commit
exit 0
