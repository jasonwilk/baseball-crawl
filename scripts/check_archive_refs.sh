#!/bin/bash
# scripts/check_archive_refs.sh
# Archive-reference sweep -- does anything still spell a closing epic's
# pre-archive path?
#
#   usage: check_archive_refs.sh E-NNN [tree]
#
# Exit codes (the shape scripts/check_doc_pii.sh already established):
#   0  PASS     -- no surviving literal reference
#   1  BLOCKED  -- at least one surviving literal reference
#   2  INVALID  -- unusable argument; NOTHING WAS SWEPT
#
# 1 and 2 are distinct on purpose. A gate that never ran is INVALID, not a
# pass: zero findings and zero executions are otherwise the same counter state.
#
# WHAT A CLEAN EXIT MEANS, AND WHAT IT DOES NOT.
# A zero exit certifies exactly one thing: no literal `epics/<ID>-` reference
# survives outside .project/archive/. It does NOT mean "no stranded
# references". A line naming the epic by ID without spelling its path -- a
# bare `E-243`, a slug on its own, a prose mention -- is out of reach BY
# CONSTRUCTION and is not covered. Do not read a pass as more than it is.
#
# ONE EPIC PER INVOCATION, and the wildcard rejection is load-bearing rather
# than defensive hygiene. A repo-wide sweep for every epic-shaped path
# collides immediately with hard-coded epic-path literals in the test suite:
# the synthetic E-999-demo fixture in tests/test_doc_pii_hook.py, and
# separately the E-129 literals in tests/test_pii_scanner.py. The second set
# is NOT synthetic -- E-129 is archived, so those are live dead paths that are
# nonetheless EVIDENCE: they are test *inputs* to a prefix predicate, so the
# string's job is to be a path under the live epics tree, not to point at a
# directory that exists. Repointing them would change what the test exercises.
# Scoping to a single ID is what keeps false positives near zero.
#
# (Those two filenames are named here without spelling their epic paths. The
# gate makes a pre-archive path unspellable outside .project/archive/ once it
# lands, and a rationale comment is not exempt from the rule it explains.)
#
# THE SWEEP READS THE WORKING TREE, NOT THE INDEX, and both call sites want
# that. The in-window hold runs after the worktree rename and BEFORE
# `git add -A`, so the state it must see is unstaged by construction. The
# consequence at the pre-commit call site is worth knowing: where an author
# has staged a subset (`git add -p`, or staged-then-edited), tree and index
# diverge and this gate judges the tree.

set -u

usage() {
  echo "usage: check_archive_refs.sh E-NNN [tree]" >&2
}

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "[archive-refs: INVALID] expected 1 or 2 arguments, got $#" >&2
  usage
  exit 2
fi

EPIC_ID="$1"
TREE="${2-}"

# Exactly one well-formed epic ID. A `case` glob is used rather than a regex
# because a case pattern is anchored to the whole word by construction -- an
# unanchored regex is how a wildcard argument sneaks through a check like this.
# `E-*`, `*`, an empty string, a partial number and a four-digit number all
# land in the reject branch.
case "$EPIC_ID" in
  E-[0-9][0-9][0-9]) ;;
  *)
    echo "[archive-refs: INVALID] not a single well-formed epic ID: '$EPIC_ID'" >&2
    echo "[archive-refs: INVALID] one epic per invocation; wildcards are refused" >&2
    usage
    exit 2
    ;;
esac

if [ -z "$TREE" ]; then
  TREE=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "[archive-refs: INVALID] no tree argument and not inside a git work tree" >&2
    exit 2
  }
fi

if [ ! -d "$TREE" ]; then
  echo "[archive-refs: INVALID] not a directory: $TREE" >&2
  exit 2
fi

NEEDLE="epics/${EPIC_ID}-"

# -F is not incidental: the needle is DATA, and a future epic slug carrying a
# regex metacharacter must not silently become a pattern.
# -I skips binaries. -n gives the reviewer a line to open.
#
# .project/archive/ is excluded by POST-FILTER rather than by --exclude-dir,
# because --exclude-dir matches a BASENAME: `--exclude-dir=archive` would also
# exclude any unrelated directory named `archive` anywhere in the tree, and
# silently under-reporting is the one failure this gate cannot afford.
HITS=$(cd "$TREE" && grep -rnIF "$NEEDLE" . --exclude-dir=.git 2>/dev/null \
         | grep -v '^\./\.project/archive/')

if [ -n "$HITS" ]; then
  echo "[archive-refs: BLOCKED] surviving references to ${NEEDLE}" >&2
  printf '%s\n' "$HITS" >&2
  echo "" >&2
  echo "[archive-refs] Each hit is a criterion-versus-evidence call: a pointer to" >&2
  echo "[archive-refs] repoint, or a record of where something was observed, which" >&2
  echo "[archive-refs] editing would falsify. Route it; do not sweep it." >&2
  echo "[archive-refs]   epics/ , .project/        -> product-manager" >&2
  echo "[archive-refs]   .claude/**               -> claude-architect" >&2
  echo "[archive-refs]   src/ , tests/ , scripts/ -> software-engineer" >&2
  echo "[archive-refs]   docs/                    -> docs-writer" >&2
  exit 1
fi

echo "[archive-refs: PASS] no literal ${NEEDLE} reference outside .project/archive/"
exit 0
