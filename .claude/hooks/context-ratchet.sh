#!/bin/bash
# .claude/hooks/context-ratchet.sh
#
# MANUAL operator diagnostic -- NOT a registered hook (do not add to settings.json).
# The context-layer size ratchet: counts lines across the four context-layer subtrees
# and diffs them against a committed, operator-owned baseline, failing (non-zero) when
# the layer has grown past baseline. This is the mechanism trigger 7 of
# .claude/rules/context-layer-assessment.md points at.
#
# Same instrument shape as E-257's `bb report reconcile-scoreboard`
# (src/reports/recon_scoreboard.py), pointed at the configuration instead of the DB:
#   - The baseline is OPERATOR-OWNED. No agent auto-refreshes it. `--update-baseline`
#     is the operator-only re-snapshot after a reviewed, legitimate change, and the
#     committed JSON diff is the human review point.
#   - A baseline-ABSENT state BOOTSTRAPS (exit 3, "run --update-baseline first"),
#     distinct from the growth signal (exit 1) and a malformed baseline (exit 4).
#
# Counting surface: *.md + *.sh files under the four subtrees. This glob is PINNED so
# the diagnostic's number and the `git diff --stat` window E-260-08 uses to verify the
# epic's net-negative measurement cover the same surface.
#
# Exit codes:
#   0  at or below baseline (PASS)
#   1  growth past baseline (FAIL -- needs an operator-signed exception)
#   2  cannot run (jq missing)
#   3  baseline absent (bootstrap -- run --update-baseline first)
#   4  baseline present but malformed / missing a value

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 2

BASELINE=".project/baselines/context-layer-ratchet.json"
SUBTREES=(.claude/rules .claude/agents .claude/skills .claude/agent-memory)

if ! command -v jq &>/dev/null; then
  echo "context-ratchet: jq is required but was not found -- cannot evaluate." >&2
  exit 2
fi

# Lines across *.md + *.sh files under a subtree (the pinned surface).
count_subtree() {
  find "$1" -type f \( -name '*.md' -o -name '*.sh' \) -exec cat {} + 2>/dev/null | wc -l | tr -d ' '
}

declare -A CUR
TOTAL=0
for d in "${SUBTREES[@]}"; do
  c=$(count_subtree "$d")
  [[ "$c" =~ ^[0-9]+$ ]] || c=0
  CUR["$d"]=$c
  TOTAL=$((TOTAL + c))
done

# --- --update-baseline: operator-only re-snapshot ---
if [[ "${1:-}" == "--update-baseline" ]]; then
  mkdir -p "$(dirname "$BASELINE")"
  jq -n \
    --arg generated "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson rules  "${CUR[.claude/rules]}" \
    --argjson agents "${CUR[.claude/agents]}" \
    --argjson skills "${CUR[.claude/skills]}" \
    --argjson memory "${CUR[.claude/agent-memory]}" \
    --argjson total  "$TOTAL" \
    '{
       metadata: {
         generated: $generated,
         note: "OPERATOR-OWNED. Line counts of *.md + *.sh files across the four context-layer subtrees. No agent auto-refreshes this; the operator runs --update-baseline after a reviewed change and commits the JSON diff (the human review point)."
       },
       counts: {
         ".claude/rules": $rules,
         ".claude/agents": $agents,
         ".claude/skills": $skills,
         ".claude/agent-memory": $memory,
         "total": $total
       }
     }' > "$BASELINE"
  echo "context-ratchet: baseline written to $BASELINE"
  echo "  Operator: review and commit the JSON diff -- this snapshot is the accepted floor."
  exit 0
fi

# --- diff current vs committed baseline ---
if [[ ! -f "$BASELINE" ]]; then
  echo "context-ratchet: baseline absent ($BASELINE) -- bootstrap state."
  echo "  Run:  .claude/hooks/context-ratchet.sh --update-baseline"
  echo "  then review + commit the JSON. Current counts (for reference):"
  for d in "${SUBTREES[@]}"; do printf '    %-22s %6s\n' "$d" "${CUR[$d]}"; done
  printf '    %-22s %6s\n' "total" "$TOTAL"
  exit 3
fi

if ! jq -e '.counts' "$BASELINE" >/dev/null 2>&1; then
  echo "context-ratchet: baseline present but malformed / unreadable ($BASELINE)." >&2
  exit 4
fi

base_val() { jq -r --arg k "$1" '.counts[$k] // "MISSING"' "$BASELINE"; }

status=0
printf '\n  %-22s %9s %9s %9s\n' "subtree" "baseline" "current" "delta"
printf '  %-22s %9s %9s %9s\n' "----------------------" "---------" "---------" "---------"
check() {
  local name="$1" cur="$2" base
  base=$(base_val "$name")
  if [[ "$base" == "MISSING" || ! "$base" =~ ^[0-9]+$ ]]; then
    echo "context-ratchet: baseline missing a numeric value for '$name'." >&2
    exit 4
  fi
  local delta=$((cur - base))
  local flag=""
  if (( cur > base )); then flag="  << GROWTH"; status=1; fi
  printf '  %-22s %9s %9s %+9d%s\n' "$name" "$base" "$cur" "$delta" "$flag"
}
for d in "${SUBTREES[@]}"; do check "$d" "${CUR[$d]}"; done
check "total" "$TOTAL"

echo
if (( status == 0 )); then
  echo "  PASS -- the context layer is at or below baseline."
else
  echo "  FAIL -- the context layer grew past baseline. Net growth needs an operator-signed"
  echo "  exception (context-layer-assessment.md trigger 7): offset the growth, or the"
  echo "  operator reviews it and runs --update-baseline to re-snapshot the accepted floor."
fi
exit "$status"
