#!/bin/bash
# .claude/hooks/worktree-guard.sh
# Claude Code PreToolUse hook: write-safety guard for Write/Edit.
#
# Two denials:
#   1. Any path with a `..` segment -- it can resolve somewhere other than where
#      it reads, so no path check downstream of here means anything.
#   2. Any path outside the repo, except the session scratchpad (/tmp/claude-*/)
#      and the Claude config/memory tree (~/.claude/).
#
# Denial is communicated via JSON on stdout, NOT via exit code. Always exits 0.

# Require jq for JSON parsing. If not available, fail open.
command -v jq &>/dev/null || exit 0

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

FILE_PATH=$(jq -r '.tool_input.file_path // ""')
[ -z "$FILE_PATH" ] && exit 0

# Collapse repeated slashes so a `//` form cannot dodge the prefix matches below.
FILE_PATH=$(printf '%s' "$FILE_PATH" | tr -s '/')

# Wrapping in slashes matches `..` only as a whole segment, never a filename
# that merely contains two dots ("foo..bar.md").
case "/$FILE_PATH/" in
  */../*) deny 'Path contains a ".." segment, which can resolve somewhere other than where it reads. Write to a clean, fully-resolved absolute path.' ;;
esac

# settings.json already invokes this hook via "$CLAUDE_PROJECT_DIR", as two
# sibling hooks do in their bodies. The literal default is load-bearing: with
# the var unset, a bare "$CLAUDE_PROJECT_DIR"/* expands to /* and the guard
# fails open on every path.
REPO="${CLAUDE_PROJECT_DIR:-/workspaces/baseball-crawl}"
REPO=$(printf '%s' "$REPO" | tr -s '/')   # same normalization as FILE_PATH
REPO="${REPO%/}"
# A root that strips to empty (CLAUDE_PROJECT_DIR=/) would leave the case arm
# below as `/*`, matching every absolute path. Refuse instead -- an unusable
# root is a misconfiguration, not permission to allow everything.
[ -z "$REPO" ] && deny "CLAUDE_PROJECT_DIR is \"$CLAUDE_PROJECT_DIR\", which is not a usable repository root. Refusing the write rather than allowing every path."
CLAUDE_HOME="${HOME:-/home/vscode}"

case "$FILE_PATH" in
  "$REPO"/*) exit 0 ;;
  /tmp/claude-*/*) exit 0 ;;
  "$CLAUDE_HOME"/.claude/*) exit 0 ;;
esac

deny "Refusing to write outside the repository: $FILE_PATH. Allowed roots are $REPO/, the session scratchpad (/tmp/claude-*/), and $CLAUDE_HOME/.claude/. Paths must be absolute."
