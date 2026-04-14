#!/usr/bin/env bash
# Warn when pytest is invoked with -x/--exitfirst.
#
# Problem: RTK compression hides suite truncation — the summary may
# show "N passed" without indicating hundreds of untested files were
# skipped. This hook emits a warning but does NOT block the command.
#
# The rule file (.claude/rules/pytest-verbose.md) is the primary
# enforcement. This hook is a runtime backstop.

if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

# Only match pytest invocations
if ! echo "$CMD" | grep -qE '(^|&&\s*|;\s*)(python3? -m pytest|pytest)\b'; then
  exit 0
fi

# Check for -x, --exitfirst, or combined short flags containing x
if ! echo "$CMD" | grep -qE '(^|\s)--exitfirst(\s|$)|(^|\s)-[a-zA-Z]*x'; then
  exit 0
fi

jq -n '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "WARNING: -x/--exitfirst detected. RTK compression hides suite truncation \u2014 summary may show '\''N passed'\'' without indicating hundreds of untested files. Remove -x for full suite runs, or use '\''rtk proxy python -m pytest tests/ -v --timeout=30'\'' for uncompressed output."
  }
}'
