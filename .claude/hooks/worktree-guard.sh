#!/bin/bash
# .claude/hooks/worktree-guard.sh
# Claude Code PreToolUse hook: blocks Write/Edit to implementation paths on main checkout
#
# Protected paths: src/, tests/, migrations/, scripts/
# Detection: file_path starts with /workspaces/baseball-crawl/ AND matches a protected prefix
# Worktree paths (/tmp/.worktrees/...) never match, so worktree writes pass unconditionally.
#
# Denial is communicated via JSON output, NOT via exit code.
# Always exits 0 -- even on denial.

# Require jq for JSON parsing. If not available, fail open.
if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# No file_path means nothing to check -- allow
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

MAIN_PREFIX="/workspaces/baseball-crawl/"

# Only check files in the main checkout
if [[ "$FILE_PATH" != "$MAIN_PREFIX"* ]]; then
  exit 0
fi

# Extract the path relative to the main checkout
REL_PATH="${FILE_PATH#$MAIN_PREFIX}"

# Block writes to protected implementation paths
if [[ "$REL_PATH" == src/* ]] || \
   [[ "$REL_PATH" == tests/* ]] || \
   [[ "$REL_PATH" == migrations/* ]] || \
   [[ "$REL_PATH" == scripts/* ]]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Implementation files (src/, tests/, migrations/, scripts/) must be modified in a worktree, not the main checkout. Check your working directory -- you should be in /tmp/.worktrees/baseball-crawl-E-NNN/."
    }
  }'
  exit 0
fi

# All other paths in the main checkout are allowed
exit 0
