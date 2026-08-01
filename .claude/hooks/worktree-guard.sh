#!/bin/bash
# .claude/hooks/worktree-guard.sh
# Claude Code PreToolUse hook: guards Write/Edit operations on the main checkout.
#
# Two modes, selected by whether git reports a registered epic worktree:
#
# 1. DISPATCH ACTIVE (git reports an epic worktree at <root>/baseball-crawl-E-*,
#    where <root> is /tmp/.worktrees unless BB_WORKTREE_ROOT overrides it):
#    Blocks ALL Write/Edit to /workspaces/baseball-crawl/ with NO allowlist.
#      - Own-memory deliverables AND closure-time memory writes go to the worktree
#        copy (.claude/agent-memory/ included) and ride the closure patch.
#    This fails closed -- any new path added to the project is automatically protected.
#    The main session's git/Bash operations are unaffected (hook only intercepts Write/Edit).
#
# 2. NO DISPATCH (git reports no epic worktree):
#    Blocks Write/Edit to implementation paths only (always-on denylist):
#      - src/, tests/, migrations/, scripts/
#    All other main-checkout writes are allowed (agents like claude-architect
#    legitimately Write/Edit to .claude/rules/, docs/, etc. outside dispatch).
#
# Detection: `git worktree list --porcelain` -- the authoritative registry, NOT a
# directory glob. A leftover DIRECTORY that git does not report no longer selects
# mode 1, so a passive hook or an audit command that creates a path under the root
# can no longer wedge every agent's main-checkout writes (E-279-01) -- EXCEPT
# where the registry is unreadable and the glob fallback below runs, which is
# still directory-driven and still wedgeable. The wedge is closed on the
# authoritative path, not everywhere.
#
# A stale REGISTRY ENTRY from a crashed dispatch -- directory gone, entry still
# registered, which git annotates `prunable` -- DOES still enforce the stricter
# mode; clear it with `git worktree remove <path>`, which is scoped to that one
# entry. Deleting the directory alone no longer clears dispatch mode (and never
# cleared the registry): under this detection that leaves the entry standing and
# the session still blocked.
#
# `git worktree prune` is NOT an interchangeable alternative: it takes NO path
# argument -- it cannot be aimed -- and is repo-GLOBAL, so one run removes EVERY
# prunable entry at once, including other epics' under concurrent dispatch.
#
# CHECK, DO NOT CLASSIFY, and note who this is addressed to. `git worktree list`
# annotates a stale entry `prunable`; an entry WITHOUT that annotation is live.
# Clearing is the operator's or the main session's action, never an agent's (see
# the ban in .claude/rules/worktree-isolation.md, which binds agents working in a
# worktree). Do not reason from "the guard is blocking me" to "the dispatch must
# be stale" -- being blocked is the NORMAL state during a live dispatch.
# The danger is not only deletion: if a LIVE worktree's directory is even
# transiently missing, `prune` drops its registry entry, restoring the directory
# does NOT bring it back, and THIS GUARD then falls silently to mode 2 -- leaving
# the epic unprotected for the rest of the dispatch.
#
# The directory glob survives ONLY as the fallback for a registry that cannot be
# read or that answers anomalously, where it reproduces exactly the pre-E-279
# behavior -- which is what makes this change safe to land mid-closure.
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

# Where epic worktrees live. ONE variable governs BOTH detection branches (the
# registry match and the glob fallback) so they can never disagree about where
# worktrees are.
#
# BB_WORKTREE_ROOT exists for HERMETIC TESTING and nothing else: it lets a test
# plant a real directory somewhere harmless and prove the guard ignores it,
# without creating one under the real /tmp/.worktrees (which would put every
# agent in the session into mode 1 for as long as it existed -- the very defect
# this hook was changed to close). PRODUCTION NEVER SETS IT; unset, the root is
# the literal /tmp/.worktrees and behavior is byte-identical to production.
# A wrong-but-existing root does NOT silently disable dispatch detection: the
# mismatch check below fails closed instead.
WT_ROOT="${BB_WORKTREE_ROOT:-/tmp/.worktrees}"

# Configuration precondition, evaluated BEFORE the registry is read: a root that
# was SET but does not exist is a typo, not an answer about dispatch. Fail closed
# -- loudly and immediately -- rather than letting a misconfiguration read as "no
# dispatch running".
#
# SET-ONLY, and this is load-bearing: an absent DEFAULT root is NORMAL
# (/tmp/.worktrees need not exist when no dispatch has ever run on this machine).
# Generalizing this branch to the default root would deny every main-checkout
# Write/Edit in every session with no dispatch running -- and because
# /tmp/.worktrees usually exists on a machine that has dispatched before, it
# would pass local testing and brick a fresh boot or a clean container.
if [ -n "${BB_WORKTREE_ROOT:-}" ] && [ ! -d "$WT_ROOT" ]; then
  jq -n --arg root "$WT_ROOT" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("BB_WORKTREE_ROOT is set to \"" + $root + "\", which does not exist. The worktree guard cannot determine whether a dispatch is active, so it is failing closed and blocking main-checkout Write/Edit. Fix or unset BB_WORKTREE_ROOT in .claude/settings.json.")
    }
  }'
  exit 0
fi

# Detect dispatch mode: ask git which worktrees are REGISTERED. A directory that
# git does not report is not a dispatch.
WORKTREE_DIR=""
if WT_LIST=$(git -C "${MAIN_PREFIX%/}" worktree list --porcelain 2>/dev/null) \
   && printf '%s\n' "$WT_LIST" | grep -qxF "worktree ${MAIN_PREFIX%/}"; then
  # Registry is readable AND answered ABOUT THIS CHECKOUT: authoritative, empty
  # answer included.
  #
  # The positive control is the MAIN CHECKOUT's own line, matched whole (-x) and
  # literal (-F) -- NOT merely "some `worktree ` line". A run that genuinely
  # answered about this repository always lists this repository, so a list
  # lacking it did not answer about this repository at all.
  #
  # Testing for ANY `^worktree ` line was a FAIL-OPEN, and reachable without an
  # adversary or a stubbed binary: an inherited GIT_DIR or GIT_COMMON_DIR
  # pointing at another repository makes `git -C <main> worktree list
  # --porcelain` report THAT repository -- exit 0, `worktree ` lines present,
  # this checkout absent. The weaker control passed, nothing matched
  # `baseball-crawl-E-*`, and the guard fell to mode 2 and allowed every
  # main-checkout path outside the mode-2 denylist -- the whole context layer --
  # silently, for as long as the variable was set.
  #
  # Why it survived review: an instrument failure and a valid "no dispatch"
  # answer produce IDENTICAL output here. Both are exit 0 with no epic worktree
  # listed, so ALLOW is the correct response to one of them. A control can only
  # separate them if it is a line the VALID answer always carries.
  #
  # If this checkout is ever reached through a symlinked path, git reports the
  # RESOLVED path, this match fails, and detection degrades to the glob fallback
  # below -- the pre-E-279 behavior. That cost is TWO-SIDED:
  # ⚰ RETIRED: "A false negative here costs strictness, never permissiveness."
  # False by construction. It is true of the LIVE case only, which is exactly
  # why it read as safe -- a one-sided safety claim that holds in the common
  # case is the hardest kind to challenge. Kept verbatim and marked rather than
  # paraphrased: a silently corrected claim is one a future reader reintroduces,
  # and a grep for the retired words must land on a line whose FIRST token says
  # it is dead. Resolve this hit by reading it; do not verify by counting
  # (.claude/rules/doc-sweep.md).
  #   - LIVE dispatch: the glob finds the directory and denies. Cost is
  #     strictness only, and the old sentence was right about this case.
  #   - CRASHED dispatch (registry entry standing, directory gone -- git
  #     annotates it `prunable`): the registry WOULD have denied and the glob
  #     CANNOT, because there is no directory left to find. The degradation is
  #     PERMISSIVE here and it costs AC-2's guarantee.
  # The trade is still the right one -- it needs a symlinked main checkout AND a
  # crashed dispatch, and resolving paths would put a realpath dependency on a
  # deliberately zero-dependency hot path. But it is a trade, not a free
  # fallback, and stating it one-sidedly is what made it look free.
  while IFS= read -r WT_LINE; do
    case "$WT_LINE" in
      "worktree $WT_ROOT/baseball-crawl-E-"*)
        WORKTREE_DIR="${WT_LINE#worktree }"
        break
        ;;
    esac
  done <<< "$WT_LIST"

  # Mismatch check: when the root was SET, an epic worktree registered somewhere
  # OTHER than that root means the configured root is wrong. Fail closed -- a
  # loud false block beats silently running unguarded beside a live dispatch.
  # Inert when BB_WORKTREE_ROOT is unset, so production is unaffected.
  if [ -z "$WORKTREE_DIR" ] && [ -n "${BB_WORKTREE_ROOT:-}" ] \
     && printf '%s\n' "$WT_LIST" | grep -q '^worktree .*/baseball-crawl-E-'; then
    jq -n --arg root "$WT_ROOT" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: ("An epic worktree is registered with git, but not under BB_WORKTREE_ROOT (\"" + $root + "\") -- so the configured root is wrong. The guard is failing closed and blocking main-checkout Write/Edit rather than running unguarded during a live dispatch. Fix or unset BB_WORKTREE_ROOT in .claude/settings.json.")
      }
    }'
    exit 0
  fi
else
  # Registry unreadable (git absent, non-zero exit) or anomalous -- zero exit
  # with no `worktree` line at all, OR zero exit with worktree lines that do not
  # include THIS checkout (the GIT_DIR case above): fall back to the pre-E-279
  # directory glob, which is conservative in the same direction as before.
  WORKTREE_DIR=$(ls -d "$WT_ROOT"/baseball-crawl-E-* 2>/dev/null | head -1)
fi

if [ -n "$WORKTREE_DIR" ]; then
  # --- DISPATCH ACTIVE: block ALL main-checkout Write/Edit (no allowlist) ---
  # Own-memory deliverables and closure-time memory writes go to the worktree copy
  # and ride the closure patch; consultation-mode memory writes happen in mode 2
  # (no worktree REGISTERED -- a leftover directory is no longer mode 1) and are
  # unaffected.
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
