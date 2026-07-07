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

# --- match primitives -------------------------------------------------------
# Each prints matching "file:line:text" lines to stdout; success/failure is
# judged by the caller on whether output is non-empty.
match_plain()  { grep -rnF -- "$2" "$1" 2>/dev/null; }
match_regex()  { grep -rnE -- "$2" "$1" 2>/dev/null; }
match_prefix() { grep -rn -- "$2" "$1" 2>/dev/null | grep -vF -- "${2}-REDACTED"; }

# --- self-test (machinery-based, data-independent) --------------------------
# Proves the three matchers actually detect and exclude as specified. A gutted
# harness (matcher that returns nothing, or a prefix matcher that forgets the
# -REDACTED exclusion) fails here and exits 2 -- it can never reach exit 0.
self_test() {
  local d out
  d="$(mktemp -d)" || return 1
  # shellcheck disable=SC2064
  trap "rm -rf '$d'" RETURN

  printf 'alpha SELFTESTPLAIN beta\n'          > "$d/a.txt"
  printf 'code SELFTESTRE4242 here\n'          > "$d/b.txt"
  printf 'real deadbeef-1234-5678 leak\n'      > "$d/c.txt"
  printf 'ok deadbeef-REDACTED placeholder\n'  > "$d/d.txt"

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
