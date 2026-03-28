#!/usr/bin/env bash
# Ensure pytest always runs with -v flag.
#
# Problem: `rtk pytest` (default mode) hides test failures entirely,
# showing "No tests collected" for both passing and failing runs.
# With -v, failures are correctly displayed.
#
# This hook injects -v into pytest commands. When RTK is installed,
# the RTK rewrite hook runs in parallel and also rewrites the command.
# Since hooks run in parallel (not sequentially), the outcome depends
# on which hook's updatedInput Claude Code selects. The .claude/rules/
# pytest-verbose.md rule is the primary enforcement -- this hook is a
# backstop for cases where the agent forgets -v or RTK isn't installed.

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

# Already has -v -- nothing to do
if echo "$CMD" | grep -qE '(^|\s)-[a-z]*v'; then
  exit 0
fi

# Inject -v at the end
REWRITTEN="$CMD -v"

ORIGINAL_INPUT=$(echo "$INPUT" | jq -c '.tool_input')
UPDATED_INPUT=$(echo "$ORIGINAL_INPUT" | jq --arg cmd "$REWRITTEN" '.command = $cmd')

jq -n \
  --argjson updated "$UPDATED_INPUT" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "permissionDecisionReason": "Pytest -v flag injected (rtk pytest hides failures without it)",
      "updatedInput": $updated
    }
  }'
