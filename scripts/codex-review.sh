#!/usr/bin/env bash
# codex-review.sh -- Run a project-aware Codex code review.
#
# CLI flags verified against installed codex version (2026-03-03):
#   --uncommitted   Review staged, unstaged, and untracked changes
#   --base <BRANCH> Review changes against a base branch
#   --commit <SHA>  Review a specific commit
#   PROMPT argument (or "-" for stdin) passes review instructions
# No discrepancies found between design spec and installed CLI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUBRIC_FILE="${REPO_ROOT}/.project/codex-review.md"

usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") <mode> [args]

Modes:
  uncommitted          Review staged, unstaged, and untracked changes
  base <branch>        Review diff against the specified base branch
  commit <sha>         Review a specific commit

Examples:
  $(basename "$0") uncommitted
  $(basename "$0") base main
  $(basename "$0") commit abc1234
EOF
    exit 1
}

# Verify codex is installed
if ! command -v codex &>/dev/null; then
    echo "Error: 'codex' is not installed or not in PATH." >&2
    echo "Install with: npm i -g @openai/codex" >&2
    exit 1
fi

# Verify the rubric file exists
if [[ ! -f "${RUBRIC_FILE}" ]]; then
    echo "Error: rubric file not found: ${RUBRIC_FILE}" >&2
    exit 1
fi

MODE="${1:-}"

case "${MODE}" in
    uncommitted)
        codex review --uncommitted - <"${RUBRIC_FILE}"
        ;;
    base)
        BRANCH="${2:-}"
        if [[ -z "${BRANCH}" ]]; then
            echo "Error: 'base' mode requires a branch name." >&2
            usage
        fi
        codex review --base "${BRANCH}" - <"${RUBRIC_FILE}"
        ;;
    commit)
        SHA="${2:-}"
        if [[ -z "${SHA}" ]]; then
            echo "Error: 'commit' mode requires a commit SHA." >&2
            usage
        fi
        codex review --commit "${SHA}" - <"${RUBRIC_FILE}"
        ;;
    *)
        if [[ -z "${MODE}" ]]; then
            echo "Error: no mode specified." >&2
        else
            echo "Error: unknown mode '${MODE}'." >&2
        fi
        usage
        ;;
esac
