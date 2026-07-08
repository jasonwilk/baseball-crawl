#!/bin/bash
# .claude/hooks/edit-verify.sh
# Claude Code PostToolUse hook: verifies that an Edit/Write actually landed.
#
# This is the FIRST PostToolUse hook in the project (all others are PreToolUse).
# It fires AFTER the tool has already written to disk. Per documented Claude Code
# semantics, PostToolUse CANNOT block or roll back the write -- it is
# detect-and-signal ONLY. A top-level {"decision":"block","reason":...} surfaces
# the reason to the model and halts continuation to the next turn, but the write
# has already executed and is not undone. (Note: this differs from PreToolUse,
# which denies via hookSpecificOutput.permissionDecision.)
#
# Failure class caught: silent partial-edit-success -- the channel reports the
# Edit/Write as "success" but the bytes did not fully land. This is the one
# failure mode with no behavioral workaround (an agent's own read-back can also
# be dark), so a deterministic re-read here is the only place to catch it.
#
# Transient-vs-absent discipline (so legitimate edits are never falsely flagged
# under channel flakiness):
#   - re-read empty/unreadable while the file should exist (transient) -> retry
#     once, then emit ONE terse warning; NEVER hard-fail.
#   - file readable & non-empty but the written content genuinely missing
#     (real-absent) -> loud detect-and-signal block.
#
# Output discipline (context-budget): emits NOTHING on the success case and on
# the transient-empty-then-recover case. Emits only on a genuine real-absent
# failure (block JSON) or, at most, a single terse warning line. A hook that
# cries wolf on transient empties is context poison.
#
# Always exits 0. The block is communicated via JSON on stdout, never via exit
# code (exit 2 would only echo stderr to the model and cannot block PostToolUse).

# Fail OPEN but ANNOUNCED if jq is unavailable -- a verification aid must never
# become a blocker on its own missing dependency, but the gap must be visible.
if ! command -v jq &>/dev/null; then
  echo "edit-verify: verification unavailable (jq not found)" >&2
  exit 0
fi

INPUT=$(cat)

TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Only Edit and Write carry a single-file landing to verify.
case "$TOOL" in
  Edit)  VALUE=$(echo "$INPUT" | jq -r '.tool_input.new_string // ""') ;;
  Write) VALUE=$(echo "$INPUT" | jq -r '.tool_input.content // ""') ;;
  *)     exit 0 ;;
esac

# Nothing to verify: no path, or an empty new_string/content (e.g. a deletion
# Edit or an intentionally-empty Write). Pass silently.
if [ -z "$FILE_PATH" ] || [ -z "$VALUE" ]; then
  exit 0
fi

# --- Agent-memory carve-out (AC-7 / agentic-flow-review §4.2) ----------------
# The harness injects `originSessionId` (and other) frontmatter into agent-memory
# files AFTER the Write/Edit returns, so a post-write read can NEVER byte-match
# the content the tool reported writing -- byte-equality is structurally
# impossible here and every such block was a false positive (all 11 corpus blocks
# were this). Skip verification for memory paths: both the harness auto-memory
# tree (`*/projects/*/memory/*`) and the project agent-memory tree
# (`*/.claude/agent-memory/*`).
case "$FILE_PATH" in
  */projects/*/memory/*|*/.claude/agent-memory/*)
    exit 0
    ;;
esac

# --- Unified content read with transient-retry (AC-3) ----------------------
# Read the SAME content the presence check will test, up front. After a
# successful Edit/Write the file should exist and be non-empty (VALUE is
# non-empty), so an empty read here means the file is missing/empty/unreadable
# OR the read came back transiently dark. Treat any empty read as transient:
# retry once. A persistently-empty read WARNS and never blocks. Crucially, the
# retry covers the exact read used by the presence test below -- so a
# transiently-dark `cat` cannot fall through into a false "did not land" block
# (AC-3, AC-8).
FILE_CONTENT=$(cat -- "$FILE_PATH" 2>/dev/null)
if [ -z "$FILE_CONTENT" ]; then
  sleep 0.15
  FILE_CONTENT=$(cat -- "$FILE_PATH" 2>/dev/null)
  if [ -z "$FILE_CONTENT" ]; then
    # Still empty/unreadable after the retry -> WARN, do NOT hard-fail.
    echo "edit-verify: verification uncertain for $FILE_PATH (empty/unreadable after retry)" >&2
    exit 0
  fi
fi

# --- Presence check (AC-1, AC-4) -------------------------------------------
# FILE_CONTENT is non-empty here. Cheap, diff-free; the predicate branches by
# tool type because what "landed correctly" means differs:
#   - Write: the written content IS the whole file -> require whole-file
#     EQUALITY. A substring test would let a failed Write that left stale
#     surrounding bytes pass silently (e.g. Write "body\n" over a file still
#     holding "prefix\nbody\nsuffix\n"), defeating the hook's anchor purpose.
#   - Edit: new_string is a legitimate sub-span of the file -> literal multiline
#     SUBSTRING test. Bash's [[ == *substr* ]] (variable quoted) is used
#     deliberately over `grep -F`, whose embedded-newline-as-alternation
#     semantics would match ANY single line of a multiline block.
# Both sides are captured via $() (above and at read time), so trailing-newline
# differences are tolerated symmetrically -- preserving the no-false-alarm
# priority of AC-5/AC-8.
#
# ACCEPTED limitations (deliberately NOT chased; documented so they are visible,
# not silent):
#   - Exact trailing-newline-count mismatch (e.g. "a\n\n" written vs "a\n" on
#     disk) is NOT caught: $() strips trailing newlines symmetrically, and a
#     byte-exact comparison would risk the false alarms AC-8 forbids. Accepted.
#   - Empty Write / deletion Edit (empty VALUE) remains a silent no-op: it is
#     out of new_string/content-presence scope (handled by the early no-op
#     above). Accepted.
MISMATCH=0
if [ "$TOOL" = "Write" ]; then
  [[ "$FILE_CONTENT" != "$VALUE" ]] && MISMATCH=1
else
  [[ "$FILE_CONTENT" != *"$VALUE"* ]] && MISMATCH=1
fi

if [ "$MISMATCH" = "1" ]; then
  # Real-absent / not-landed: file is readable and non-empty, but the written
  # content did not land as expected -> detect-and-signal (block). Include the
  # byte-length delta (expected content vs. what the file holds) and a recovery
  # step so the mismatch is actionable, not just flagged (AC-7).
  VALUE_LEN=${#VALUE}
  CONTENT_LEN=${#FILE_CONTENT}
  jq -n --arg file "$FILE_PATH" --arg vlen "$VALUE_LEN" --arg clen "$CONTENT_LEN" \
    '{decision: "block", reason: ($file + ": new_string not found after Edit/Write — edit did not land (expected content was " + $vlen + " bytes; the file currently holds " + $clen + " bytes). Recovery: re-Read the file and re-apply the Edit/Write; if the file already contains the intended content, the write DID land and this was a transient dark read — retry the operation.")}'
  exit 0
fi

# Verified present -- pass silently (no output, per output discipline).
exit 0
