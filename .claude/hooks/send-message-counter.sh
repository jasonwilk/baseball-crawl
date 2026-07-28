#!/bin/bash
# .claude/hooks/send-message-counter.sh
# Claude Code PreToolUse hook: dispatch message-volume counter.
#
# Purpose: make dispatch SendMessage volume visible per-story. The E-256 dispatch
# produced ~640k characters of agent-to-agent prose with no running count; this makes
# the volume observable per-story instead of invisible.
#
# ⚰ RETIRED (2026-07-28, operator order): the WARN_AT/DENY_AT thresholds and their
# enforcement. This hook previously warned at 40 sends and HARD-DENIED SendMessage at
# 60 per staging boundary. Both are gone, for two operator-observed reasons:
#   1. The deny killed the E-278 dispatch mid-build (2026-07-28) — a hard stop on the
#      coordination channel halts the whole team, and the recovery cost exceeds any
#      value the cap returned. The E-276-fitted cap (largest story = 41 sends) did not
#      transfer to the next epic's largest story.
#   2. Agent-visible budgets distort behavior (operator, 2026-07-26: agents "avoiding
#      things because it 'costs a send' ... It changes base good behavior"). The warn
#      advisory was the same mechanism at lower intensity.
# What remains is PASSIVE TELEMETRY ONLY: a silent counter and the per-boundary TSV
# log below, for operator review after the fact. This hook never emits JSON and never
# blocks. Do not reintroduce a threshold here without an operator order.
#
# Registered on TWO PreToolUse events (see .claude/settings.json):
#   - SendMessage : silently increment a worktree-local send counter.
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
# Fail-open: if jq is unavailable, exit 0 (mirrors worktree-guard.sh). No-op when no
# epic worktree is present, so non-dispatch sessions are never affected.

# Fail open if jq is missing (same posture as worktree-guard.sh).
if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')

# Resolve the worktree for THE SESSION MAKING THIS CALL. Never `head -1`: with two
# dispatches live it handed the first worktree alphabetically to BOTH sessions
# (2026-07-27 -- one machine-global counter, and E-277's first staging boundary would
# have appended its row to E-275's TRACKED log, riding the sibling's closure patch).
# Prints nothing unless attribution is certain; callers treat empty as "do not count".
resolve_worktree() {
  # 1. Exact -- the caller's cwd is inside a worktree.
  if [ "${CWD#/tmp/.worktrees/baseball-crawl-E-}" != "$CWD" ]; then
    local rest="${CWD#/tmp/.worktrees/}"
    printf '%s' "/tmp/.worktrees/${rest%%/*}"
    return
  fi
  # 2. Unambiguous -- exactly one worktree exists. Identical to the old `head -1`
  #    for the single-dispatch case, the only case that code was right for.
  set -- /tmp/.worktrees/baseball-crawl-E-*
  if [ "$#" -eq 1 ] && [ -d "$1" ]; then
    printf '%s' "$1"
  fi
  # 3. Otherwise (none, or >1 with an uninformative cwd) -- print nothing. A wrong
  #    attribution is worse than no count: it denies the wrong session AND writes
  #    one epic's row into another epic's tracked log.
}

WORKTREE_DIR=$(resolve_worktree)

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
    # Unattributable send (no worktree, or several live and cwd does not say which).
    # Do not count rather than count into a sibling epic.
    [ -n "$WORKTREE_DIR" ] || exit 0
    LOG_DIR="$WORKTREE_DIR/.dispatch-log"
    COUNTER="$LOG_DIR/sends.count"
    mkdir -p "$LOG_DIR" 2>/dev/null
    # Silent count only -- no warn, no deny, no JSON output (see RETIRED note above).
    printf '%s' "$(( $(read_count) + 1 ))" > "$COUNTER"
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
      # Derive the epic from the COMMAND, not the filesystem: this `git add` names the
      # worktree it targets, so attribution stays exact with several dispatches live.
      [[ "$CMD" =~ (/tmp/\.worktrees/baseball-crawl-E-[0-9]+) ]] || exit 0
      WT="${BASH_REMATCH[1]}"
      EPIC_ID="${WT##*/baseball-crawl-}"
      LOG_DIR="$WT/.dispatch-log"
      COUNTER="$LOG_DIR/sends.count"
      LOG="$LOG_DIR/$EPIC_ID.tsv"
      mkdir -p "$LOG_DIR" 2>/dev/null
      # Blank, NOT 0, when no counter file exists -- sends were not counted (parallel
      # dispatch disables counting). Same doctrine as the `rounds` column above: a
      # blank means "not recorded" and never "zero sends".
      SENDS=""
      [ -f "$COUNTER" ] && SENDS=$(read_count)
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
      [ -f "$COUNTER" ] && printf '0' > "$COUNTER"   # reset only a counter that exists
    fi
    exit 0
    ;;

  *)
    exit 0
    ;;
esac
