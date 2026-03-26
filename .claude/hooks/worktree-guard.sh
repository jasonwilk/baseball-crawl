#!/bin/bash
# .claude/hooks/worktree-guard.sh
# Claude Code PreToolUse hook: guards Write/Edit operations on the main checkout.
#
# Two modes, selected by whether an epic worktree exists:
#
# 1. DISPATCH ACTIVE (epic worktree at /tmp/.worktrees/baseball-crawl-E-* exists):
#    Blocks ALL Write/Edit to /workspaces/baseball-crawl/ EXCEPT the allowlist:
#      - .claude/agent-memory/*  (agents write to their own memory in main checkout)
#    This fails closed -- any new path added to the project is automatically protected.
#    The main session's git/Bash operations are unaffected (hook only intercepts Write/Edit).
#
# 2. NO DISPATCH (no epic worktree):
#    Blocks Write/Edit to implementation paths only (always-on denylist):
#      - src/, tests/, migrations/, scripts/
#    All other main-checkout writes are allowed (agents like claude-architect
#    legitimately Write/Edit to .claude/rules/, docs/, etc. outside dispatch).
#
# Detection: glob for /tmp/.worktrees/baseball-crawl-E-* directories.
# A stale worktree from a crashed dispatch safely enforces the stricter mode;
# the user can clear it by removing the worktree directory.
#
# Worktree paths (/tmp/.worktrees/...) always pass -- never blocked.
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

# Only check files in the main checkout -- worktree writes always pass
if [[ "$FILE_PATH" != "$MAIN_PREFIX"* ]]; then
  exit 0
fi

# Extract the path relative to the main checkout
REL_PATH="${FILE_PATH#$MAIN_PREFIX}"

# Detect dispatch mode: check for epic worktree directories
WORKTREE_DIR=$(ls -d /tmp/.worktrees/baseball-crawl-E-* 2>/dev/null | head -1)

if [ -n "$WORKTREE_DIR" ]; then
  # --- DISPATCH ACTIVE: allowlist mode ---
  # Only agent-memory writes are permitted in the main checkout during dispatch.
  if [[ "$REL_PATH" == .claude/agent-memory/* ]]; then
    exit 0
  fi

  jq -n --arg worktree "$WORKTREE_DIR" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Dispatch is active (worktree: " + $worktree + "). During dispatch, Write/Edit to the main checkout is blocked -- use the epic worktree path instead. Only .claude/agent-memory/ is allowed in the main checkout during dispatch.")
    }
  }'
  exit 0
fi

# --- NO DISPATCH: always-on denylist for implementation paths ---
if [[ "$REL_PATH" == src/* ]] || \
   [[ "$REL_PATH" == tests/* ]] || \
   [[ "$REL_PATH" == migrations/* ]] || \
   [[ "$REL_PATH" == scripts/* ]]; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Implementation files (src/, tests/, migrations/, scripts/) must be modified in a worktree, not the main checkout. Create an epic worktree first."
    }
  }'
  exit 0
fi

# All other paths allowed (no dispatch, non-implementation path)
exit 0
