#!/bin/bash
# .claude/hooks/send-message-counter.sh
# Claude Code PreToolUse hook: dispatch message-volume counter.
#
# Purpose: make dispatch SendMessage volume visible and bounded. The E-256 dispatch
# produced ~640k characters of agent-to-agent prose with no running count; this makes
# the volume observable per-story instead of invisible.
#
# Registered on TWO PreToolUse events (see .claude/settings.json):
#   - SendMessage : increment a worktree-local send counter; warn at 15, deny at 25.
#   - Bash        : when the command is a `git add` TARGETING the epic worktree (the
#                   per-story staging boundary), append one dispatch-log row
#                   (epic ID, staging-boundary sequence index, sends) and reset the
#                   counter to zero -- bracketing the just-finished story.
#
# Files (worktree-local, under <worktree>/.dispatch-log/):
#   - sends.count   transient send counter (gitignored)
#   - E-NNN.tsv     dispatch log, one row per staging boundary (TRACKED -> rides the
#                   closure patch; no committed cross-epic aggregate)
#
# THE `rounds` COLUMN HAS NO PRODUCER, AND THAT IS STRUCTURAL, NOT AN OVERSIGHT. This
# hook sees a PreToolUse `git add` event; nothing in it says which review round the
# story is in, so the column has been blank on every row of every log since E-260. A
# blank therefore means "not recorded" and NEVER "zero rounds". Either fill it by hand
# at closure or drop it -- but do not read it as data.
#
# AND A ROW IS A STAGING BOUNDARY, NOT A STORY. A late fix folded into a second
# boundary splits one story across two rows: E-276 story 01 cost 41 sends, logged as
# 37 + 4. Any threshold conversation citing "37" is citing the FIRST row of a split
# story, and a reader who reads rows as stories will under-count.
#
# THRESHOLD PROVENANCE (OPERATOR-OWNED). The operator is the SOLE person who may edit
# either number below; agents MUST NOT change them.
#   WARN_AT=40  set by the operator on E-276's data, with DENY_AT below.
#   DENY_AT=60  set by the operator on E-276's data, REPLACING the E-256 placeholder of
#               25. The "revisit with data" that stood here has been DONE -- do not
#               start it again on the strength of this comment.
#
#   The data: E-276's five stories cost 41 / 18 / 32 / 11 / 8 sends (story 01's 41 was
#   logged as 37 + 4 across a folded boundary -- see the note above, and the per-row
#   figures in .dispatch-log/E-276.tsv). The cap is counted PER STAGING BOUNDARY, so it
#   has to accommodate the LARGEST SINGLE story, never the average -- an average-fitted
#   cap denies the one story that most needs the sends. WARN_AT moved up with it for a
#   separate reason: a warn threshold far below the deny cap fires on nearly every
#   story, and a signal that always fires carries none.
#
#   ⚠️ THIS BLOCK WAS FALSIFIED BY THE COMMIT THAT RAISED THE VALUES (2026-07-26), with
#   nobody at fault and no sentence edited -- it simply stopped being true, and the
#   edit that did it was correct and necessary. That is the argument for keeping a
#   value and its provenance in one place: co-location is what makes the staleness
#   visible at the moment of the change.
#
# Fail-open: if jq is unavailable, exit 0 (mirrors worktree-guard.sh). No-op when no
# epic worktree is present, so non-dispatch sessions are never affected.
# Denial/warning is communicated via JSON output; the hook always exits 0.

WARN_AT=40
DENY_AT=60

# Fail open if jq is missing (same posture as worktree-guard.sh).
if ! command -v jq &>/dev/null; then
  exit 0
fi

# No-op unless a dispatch worktree exists -- never interferes with non-dispatch sessions.
WORKTREE_DIR=$(ls -d /tmp/.worktrees/baseball-crawl-E-* 2>/dev/null | head -1)
if [ -z "$WORKTREE_DIR" ]; then
  exit 0
fi

EPIC_ID=$(basename "$WORKTREE_DIR" | sed 's/^baseball-crawl-//')   # E-NNN
LOG_DIR="$WORKTREE_DIR/.dispatch-log"
COUNTER="$LOG_DIR/sends.count"
LOG="$LOG_DIR/$EPIC_ID.tsv"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

read_count() {
  local c=0
  if [ -f "$COUNTER" ]; then
    c=$(cat "$COUNTER" 2>/dev/null)
    [[ "$c" =~ ^[0-9]+$ ]] || c=0
  fi
  printf '%s' "$c"
}

case "$TOOL_NAME" in
  SendMessage)
    mkdir -p "$LOG_DIR" 2>/dev/null
    NEW=$(( $(read_count) + 1 ))

    if [ "$NEW" -ge "$DENY_AT" ]; then
      # Hard stop. Pin the counter at the cap and deny with the operator-action message.
      printf '%s' "$DENY_AT" > "$COUNTER"
      REASON="SendMessage BLOCKED — dispatch send cap reached (25 sends since the last staging boundary).
This is a HARD STOP and an OPERATOR decision point, not an in-session one: do NOT reinterpret,
rephrase, or route around this rule to keep sending.
To proceed, the operator must either:
  (1) reset the count by deleting the counter file:  <worktree>/.dispatch-log/sends.count
  (2) or raise the threshold in .claude/hooks/send-message-counter.sh (operator-owned;
      see the provenance comment — 25 is a single-epic placeholder).
Until the operator acts, further SendMessage calls are denied."
      jq -n --arg reason "$REASON" '{
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: $reason
        }
      }'
      exit 0
    fi

    printf '%s' "$NEW" > "$COUNTER"

    if [ "$NEW" -ge "$WARN_AT" ]; then
      # Advisory only -- non-blocking, no operator-action text.
      jq -n --arg msg "Dispatch send count: $NEW of $DENY_AT since the last staging boundary (advisory)." '{
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "allow",
          permissionDecisionReason: $msg
        }
      }'
      exit 0
    fi

    # Below the warn threshold -- silent pass.
    exit 0
    ;;

  Bash)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
    # Staging boundary: a `git add` whose command TARGETS the epic worktree. Keying on
    # the worktree prefix excludes the main-checkout closure git-adds (Step 7a and
    # Step-8 sub-step 8), which would otherwise fire phantom rows / reset early.
    # Accepted residual: Phase-5 remediation worktree adds also match -- harmless, and
    # consistent with the best-effort rounds/sequence posture.
    if [[ "$CMD" == *"/tmp/.worktrees/baseball-crawl-E-"* ]] && [[ "$CMD" =~ (^|[^[:alnum:]])git[[:space:]]+add([[:space:]]|$) ]]; then
      mkdir -p "$LOG_DIR" 2>/dev/null
      SENDS=$(read_count)
      # Staging-boundary sequence index = existing data rows + 1.
      SEQ=1
      if [ -f "$LOG" ]; then
        EXISTING=$(grep -c '^E-' "$LOG" 2>/dev/null)
        [[ "$EXISTING" =~ ^[0-9]+$ ]] || EXISTING=0
        SEQ=$(( EXISTING + 1 ))
      else
        printf 'epic\tseq\tsends\trounds\n' > "$LOG"   # rounds: no producer -- see header note
      fi
      printf '%s\t%s\t%s\t\n' "$EPIC_ID" "$SEQ" "$SENDS" >> "$LOG"
      printf '0' > "$COUNTER"   # reset for the next story
    fi
    exit 0
    ;;

  *)
    exit 0
    ;;
esac
