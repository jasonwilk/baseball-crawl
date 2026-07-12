#!/bin/bash
# .claude/hooks/worktree-guard.sh
# Claude Code PreToolUse hook: guards Write/Edit operations on the main checkout.
#
# Two modes, selected by whether an epic worktree exists:
#
# 1. DISPATCH ACTIVE (epic worktree at /tmp/.worktrees/baseball-crawl-E-* exists):
#    Blocks ALL Write/Edit to /workspaces/baseball-crawl/ with NO allowlist.
#      - Own-memory deliverables AND closure-time memory writes go to the worktree
#        copy (.claude/agent-memory/ included) and ride the closure patch.
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

# Normalize the path before any guard comparison: collapse repeated slashes so an
# absolute double-slash form UNDER the main-checkout prefix (e.g.
# /workspaces/baseball-crawl//src/foo.py) cannot bypass the prefix/denylist/allowlist
# checks below. Without this, the extra slash after the prefix would leave REL_PATH as
# "/src/foo.py" (a leading slash), which fails the "src/*" denylist glob and would slip
# a guarded write past the hook. (A relative double-slash like "src//foo.py" is a
# separate matter -- it never matches the main-checkout prefix, so it exits early above.)
FILE_PATH=$(printf '%s' "$FILE_PATH" | tr -s '/')

MAIN_PREFIX="/workspaces/baseball-crawl/"

# Only check files in the main checkout -- worktree writes always pass
if [[ "$FILE_PATH" != "$MAIN_PREFIX"* ]]; then
  exit 0
fi

# Extract the path relative to the main checkout
REL_PATH="${FILE_PATH#$MAIN_PREFIX}"

# Reject any path containing a `..` segment before mode dispatch. The `tr -s '/'`
# above collapses duplicate slashes, but a parent-dir segment can still resolve
# PAST the guard: in no-dispatch mode "docs/../src/foo.py" sidesteps the src/
# denylist (REL_PATH matches no glob yet the write lands in src/). In dispatch
# mode every main-checkout write is denied regardless, so this mainly hardens the
# no-dispatch denylist. No legitimate main-checkout Write/Edit uses
# a ".." segment (canonical tooling writes clean, fully-resolved paths), so deny
# fail-closed in BOTH modes. Wrapping REL_PATH in slashes matches ".." only as a
# whole path segment -- never a filename that merely contains two dots
# (e.g. "foo..bar.md"). This is zero-dependency (no realpath), so it holds even
# when the jq-required tooling is minimal.
case "/$REL_PATH/" in
  */../*)
    jq -n '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: "Path contains a \"..\" segment, which can resolve past the worktree guard. Write to a clean, fully-resolved path (under the epic worktree during dispatch, or the main checkout outside dispatch)."
      }
    }'
    exit 0
    ;;
esac

# Detect dispatch mode: check for epic worktree directories
WORKTREE_DIR=$(ls -d /tmp/.worktrees/baseball-crawl-E-* 2>/dev/null | head -1)

if [ -n "$WORKTREE_DIR" ]; then
  # --- DISPATCH ACTIVE: block ALL main-checkout Write/Edit (no allowlist) ---
  # Own-memory deliverables and closure-time memory writes go to the worktree copy
  # and ride the closure patch; consultation-mode memory writes happen in mode 2
  # (no worktree present) and are unaffected.
  jq -n --arg worktree "$WORKTREE_DIR" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Dispatch is active (worktree: " + $worktree + "). During dispatch, ALL Write/Edit to the main checkout is blocked -- use the epic worktree path instead (own-memory writes included: they ride the closure patch).")
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
