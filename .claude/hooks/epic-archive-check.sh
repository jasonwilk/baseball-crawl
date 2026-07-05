#!/bin/bash
# .claude/hooks/epic-archive-check.sh
# Claude Code PreToolUse hook: blocks git commit if completed/abandoned epics
# remain in the /epics/ directory (they should be archived to /.project/archive/).
#
# This hook fires before any Bash tool call in Claude Code.
# It checks if the command is a git commit, and if so, scans for stale epics.
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

# Check that the epics directory exists and contains epic.md files
EPICS_DIR="$CLAUDE_PROJECT_DIR/epics"
if [ ! -d "$EPICS_DIR" ]; then
  exit 0
fi

# Scan for completed or abandoned epics still in /epics/
# Match only the status line: a line containing just the backtick-wrapped status
# (e.g., "`COMPLETED`" or "`ABANDONED`" with optional whitespace).
# This avoids false positives from prose mentions of these words.
STALE_EPICS=$(grep -rlE '^\s*`(COMPLETED|ABANDONED)`\s*$' "$EPICS_DIR"/*/epic.md 2>/dev/null)

if [ -z "$STALE_EPICS" ]; then
  # No stale epics found -- allow the commit
  exit 0
fi

# Build a human-readable list of epic directories that need archiving
EPIC_LIST=""
for epic_file in $STALE_EPICS; do
  epic_dir=$(dirname "$epic_file")
  epic_name=$(basename "$epic_dir")
  EPIC_LIST="${EPIC_LIST}\n  - ${epic_name}"
done

REASON="Completed or abandoned epics must be archived before committing.\n\nMove these epic directories from /epics/ to /.project/archive/:${EPIC_LIST}\n\nTo archive: mv epics/<epic-dir> .project/archive/"

jq -n --arg reason "$REASON" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
exit 0
