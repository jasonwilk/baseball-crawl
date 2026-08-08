#!/usr/bin/env bash
#
# check_doc_pii.sh -- PII byte-gate for docs/api (and any doc tree).
#
# Greps a target directory against a denylist of literal real identifiers and
# fails if any are present. This is the PII-FREE HARNESS half of a
# config/config.example split: the real identifiers live ONLY in the
# uncommitted, gitignored secrets/pii-denylist.txt (never in git); this script
# and the fake-token scripts/pii-denylist.example.txt are the committed halves.
#
# Usage:
#   [PII_DENYLIST_FILE=path] scripts/check_doc_pii.sh <docs-dir>
#
# Denylist resolution:
#   - PII_DENYLIST_FILE if set, else the default secrets/pii-denylist.txt.
#   - If that REAL denylist exists      -> REAL mode.
#   - Else fall back to the colocated   -> EXAMPLE mode (INCONCLUSIVE).
#     scripts/pii-denylist.example.txt
#
# Denylist format (shared by real + example):
#   <type> <pattern>   -- split on the FIRST space.
#     type=plain  -> grep -rnF   (fixed string; zero matches required)
#     type=regex  -> grep -rnE   (ERE; zero matches required)
#     type=prefix -> grep -rn <p> | grep -v "<p>-REDACTED"
#                    (real UUID prefix; catches full UUIDs + bare prose prefixes,
#                     allows only the approved "<p>-REDACTED" placeholder form)
#   Blank lines and lines starting with '#' are ignored.
#
# Exit codes:
#   0  REAL mode, zero matches            -> PASS
#   1  a denylisted identifier is present -> FAIL (prints file:line)
#   2  self-test failed / malformed input -> INVALID
#   3  real denylist absent, example used -> EXAMPLE MODE (INCONCLUSIVE)
#
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_REAL="secrets/pii-denylist.txt"
EXAMPLE_FILE="${SCRIPT_DIR}/pii-denylist.example.txt"

# --- excluded subtree --------------------------------------------------------
# .project/archive/agent-memory/ is the ONE subtree this gate does not sweep.
# It is a frozen archive of the retired agents' memory, which arrived there by
# `git mv` out of .claude/ -- a tree this gate has never governed. Nothing lands
# in it that was not already committed elsewhere, so sweeping it would block a
# pure move over content the gate never covered, and would keep blocking every
# later commit that stages anything under .project/.
#
# EXCLUDED BY POST-FILTER ON THE PATH, NOT BY --exclude-dir, and the difference
# is load-bearing: --exclude-dir matches a BASENAME, so --exclude-dir=agent-memory
# would ALSO blind the gate to a LIVE .claude/agent-memory/ if the gate were
# ever pointed at it.
#
# THE PREFIX IS BUILT FROM THE SCAN ROOT AND ANCHORED AT POSITION 1 of grep's
# path field. An earlier form matched the path SUFFIX-wise
# (`^[^:]*\.project/archive/agent-memory/`) and was strictly wider than the
# gate that protects it: `epics/E-999/.project/archive/agent-memory/x.md` was
# dropped by this filter, while the enforcing gate in .githooks/pre-commit
# anchors its own prefix test at the REPO ROOT and so never classified that
# nested lookalike as a candidate. An exclusion wider than its enforcing gate
# is a hole by construction -- keep the two anchored the same way.
#
# Matching is LITERAL (awk index(), not a regex), so a scan root containing a
# regex metacharacter cannot alter the prefix; and only the path field is
# considered, so a file whose CONTENT spells the excluded path is still
# reported. The self-test below proves all four directions.
EXCLUDE_PREFIX=""

drop_excluded() {
    if [ -z "$EXCLUDE_PREFIX" ]; then
        cat
        return
    fi
    awk -v p="$EXCLUDE_PREFIX" '
        { path = $0; sub(/:.*/, "", path) }
        index(path, p) == 1 { next }
        { print }
    '
}

# --- match primitives -------------------------------------------------------
# Each prints matching "file:line:text" lines to stdout; success/failure is
# judged by the caller on whether output is non-empty.
match_plain()  { grep -rnF -- "$2" "$1" 2>/dev/null | drop_excluded; }
match_regex()  { grep -rnE -- "$2" "$1" 2>/dev/null | drop_excluded; }
match_prefix() { grep -rn -- "$2" "$1" 2>/dev/null | grep -vF -- "${2}-REDACTED" | drop_excluded; }

# --- self-test (machinery-based, data-independent) --------------------------
# Proves the three matchers actually detect and exclude as specified. A gutted
# harness (matcher that returns nothing, or a prefix matcher that forgets the
# -REDACTED exclusion) fails here and exits 2 -- it can never reach exit 0.
self_test() {
  local d out saved_prefix
  d="$(mktemp -d)" || return 1
  # shellcheck disable=SC2064
  trap "rm -rf '$d'" RETURN

  # The fixtures below live under $d, so the exclusion prefix is scoped to $d
  # for the duration of the self-test and restored afterwards.
  saved_prefix="$EXCLUDE_PREFIX"
  EXCLUDE_PREFIX="$d/.project/archive/agent-memory/"
  # shellcheck disable=SC2064
  trap "rm -rf '$d'; EXCLUDE_PREFIX='$saved_prefix'" RETURN

  printf 'alpha SELFTESTPLAIN beta\n'          > "$d/a.txt"
  printf 'code SELFTESTRE4242 here\n'          > "$d/b.txt"
  printf 'real deadbeef-1234-5678 leak\n'      > "$d/c.txt"
  printf 'ok deadbeef-REDACTED placeholder\n'  > "$d/d.txt"
  # Exclusion fixtures: one file INSIDE the excluded subtree, and one whose
  # CONTENT merely spells that path. The second is the over-exclusion control --
  # a filter written against the whole line rather than the path field would
  # swallow it, and that mistake is invisible from the excluded file alone.
  mkdir -p "$d/.project/archive/agent-memory/retired-agent"
  printf 'alpha SELFTESTPLAIN beta\n' > "$d/.project/archive/agent-memory/retired-agent/e.txt"
  printf 'see .project/archive/agent-memory/ SELFTESTPLAIN\n' > "$d/f.txt"
  mkdir -p "$d/nested/.project/archive/agent-memory"
  printf 'alpha SELFTESTPLAIN beta\n' > "$d/nested/.project/archive/agent-memory/nested-lookalike.txt"

  # plain: must find the fixed string, must NOT find an absent one.
  out="$(match_plain "$d" 'SELFTESTPLAIN')";      [ -n "$out" ] || return 1
  out="$(match_plain "$d" 'NOSUCHTOKEN_ZZZ')";    [ -z "$out" ] || return 1
  # regex: ERE must match the digit run.
  out="$(match_regex "$d" 'SELFTESTRE[0-9]+')";   [ -n "$out" ] || return 1
  # prefix: must flag the real full UUID line...
  out="$(match_prefix "$d" 'deadbeef')"
  printf '%s\n' "$out" | grep -q 'deadbeef-1234-5678' || return 1
  # ...and must NOT flag the approved -REDACTED placeholder line.
  printf '%s\n' "$out" | grep -q 'deadbeef-REDACTED' && return 1

  # exclusion, BOTH directions -- a one-directional check cannot tell an
  # exclusion that works from a matcher that stopped matching.
  out="$(match_plain "$d" 'SELFTESTPLAIN')"
  #   (a) a hit inside .project/archive/agent-memory/ must be DROPPED
  printf '%s\n' "$out" | grep -q '/agent-memory/retired-agent/e.txt' && return 1
  #   (b) an ordinary hit must SURVIVE the filter
  printf '%s\n' "$out" | grep -q '/a.txt' || return 1
  #   (c) a hit whose CONTENT spells the excluded path must SURVIVE -- the
  #       filter judges the path field, never the matched text
  printf '%s\n' "$out" | grep -q '/f.txt' || return 1
  #   (d) a NESTED lookalike must SURVIVE -- i.e. a file at
  #       <root>/nested/.project/archive/agent-memory/... is NOT the excluded
  #       subtree and must still be reported. The prefix is anchored at the
  #       scan root, so only the real subtree is excluded. A suffix-wise filter
  #       drops this one, and the enforcing gate in .githooks/pre-commit --
  #       which anchors at the repo root -- would not have blocked it either,
  #       so that combination is a silent hole. This leg is what forbids it.
  printf '%s\n' "$out" | grep -q 'nested-lookalike.txt' || return 1

  return 0
}

# --- args -------------------------------------------------------------------
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "usage: [PII_DENYLIST_FILE=path] $0 <docs-dir>" >&2
  echo "INVALID: no target directory given" >&2
  exit 2
fi
if [ ! -d "$TARGET" ]; then
  echo "INVALID: target is not a directory: $TARGET" >&2
  exit 2
fi

# --- resolve the excluded subtree, relative to THIS scan root ----------------
# The carve-out lives at <.project>/archive/agent-memory/, so it only applies
# when the scan root IS a .project tree. Pointing the gate at `epics` (or
# anywhere else) yields no exclusion at all -- which is the correct answer, and
# is why the prefix is derived rather than pattern-matched out of the path.
case "$(basename "$TARGET")" in
  .project) EXCLUDE_PREFIX="${TARGET%/}/archive/agent-memory/" ;;
esac

# --- run self-test before trusting any result -------------------------------
if ! self_test; then
  echo "INVALID: self-test failed -- matcher machinery is broken; refusing to report a result" >&2
  exit 2
fi

# --- resolve denylist + mode ------------------------------------------------
REAL_FILE="${PII_DENYLIST_FILE:-$DEFAULT_REAL}"
MODE=""
DENYLIST=""
if [ -f "$REAL_FILE" ]; then
  MODE="REAL"
  DENYLIST="$REAL_FILE"
elif [ -f "$EXAMPLE_FILE" ]; then
  MODE="EXAMPLE"
  DENYLIST="$EXAMPLE_FILE"
else
  echo "INVALID: no denylist found (looked for '$REAL_FILE' and '$EXAMPLE_FILE')" >&2
  exit 2
fi

# --- parse denylist ---------------------------------------------------------
declare -a TYPES=() PATTERNS=()
lineno=0
while IFS= read -r raw || [ -n "$raw" ]; do
  lineno=$((lineno + 1))
  # strip trailing CR (tolerate CRLF files)
  raw="${raw%$'\r'}"
  case "$raw" in
    ''|'#'*) continue ;;
  esac
  type="${raw%% *}"
  pat="${raw#* }"
  if [ "$type" = "$raw" ] || [ -z "$pat" ]; then
    echo "INVALID: malformed denylist line $lineno (need '<type> <pattern>'): $raw" >&2
    exit 2
  fi
  case "$type" in
    plain|regex|prefix) ;;
    *)
      echo "INVALID: unknown denylist type '$type' on line $lineno (expected plain|regex|prefix)" >&2
      exit 2
      ;;
  esac
  TYPES+=("$type")
  PATTERNS+=("$pat")
done < "$DENYLIST"

N="${#PATTERNS[@]}"
if [ "$N" -eq 0 ]; then
  echo "INVALID: denylist '$DENYLIST' loaded 0 patterns" >&2
  exit 2
fi

echo "${MODE} mode; ${N} patterns loaded"

# --- scan -------------------------------------------------------------------
hits=""
for i in "${!PATTERNS[@]}"; do
  t="${TYPES[$i]}"
  p="${PATTERNS[$i]}"
  case "$t" in
    plain)  out="$(match_plain  "$TARGET" "$p")" ;;
    regex)  out="$(match_regex  "$TARGET" "$p")" ;;
    prefix) out="$(match_prefix "$TARGET" "$p")" ;;
  esac
  if [ -n "$out" ]; then
    hits="${hits}${out}"$'\n'
  fi
done

# --- verdict ----------------------------------------------------------------
if [ "$MODE" = "EXAMPLE" ]; then
  echo "INCONCLUSIVE: real denylist absent; ran with fake example sentinels only." >&2
  echo "  Point PII_DENYLIST_FILE at the real (uncommitted) secrets/pii-denylist.txt to certify." >&2
  exit 3
fi

if [ -n "$hits" ]; then
  echo "FAIL (REAL): denylisted identifier(s) present:" >&2
  printf '%s' "$hits" | sed '/^$/d' >&2
  exit 1
fi

echo "PASS (REAL, 0 matches)"
exit 0
