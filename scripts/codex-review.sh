#!/usr/bin/env bash
# codex-review.sh -- Run a project-aware Codex code review.
#
# Uses `codex exec --ephemeral -` (NOT `codex review`) because `codex review`
# does not support custom review instructions alongside its diff-scope flags
# (--uncommitted, --base, --commit). The [PROMPT] argument is mutually
# exclusive with those flags. This script assembles the project rubric + diff
# into a single prompt and pipes it to `codex exec`, which accepts arbitrary
# prompt content via stdin. This mirrors the pattern used by codex-spec-review.sh.
#
# Verified against codex v0.107.0 (2026-03-03):
#   `codex review --uncommitted` works but accepts NO custom instructions
#   `codex exec --ephemeral -` accepts piped prompt content (used here)

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

# ---------------------------------------------------------------------------
# Verify codex is installed
# ---------------------------------------------------------------------------
if ! command -v codex &>/dev/null; then
    echo "Error: 'codex' is not installed or not in PATH." >&2
    echo "Install with: npm i -g @openai/codex" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify the rubric file exists
# ---------------------------------------------------------------------------
if [[ ! -f "${RUBRIC_FILE}" ]]; then
    echo "Error: rubric file not found: ${RUBRIC_FILE}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Assemble prompt: rubric + diff + review request
# ---------------------------------------------------------------------------
assemble_review_prompt() {
    local diff_content="$1"
    local mode_label="$2"

    echo "======================================================================"
    echo "CODE-REVIEW RUBRIC"
    echo "======================================================================"
    cat "${RUBRIC_FILE}"

    echo ""
    echo "======================================================================"
    echo "CHANGES TO REVIEW (mode: ${mode_label})"
    echo "======================================================================"
    echo "${diff_content}"

    echo ""
    echo "======================================================================"
    echo "REVIEW REQUEST"
    echo "======================================================================"
    echo "Please review the changes above against the code-review rubric."
    echo "Follow the rubric's Review Priorities in order."
    echo "Cite file and line number for every finding."
    echo "Group findings by priority level."
    echo "If the review is clean, state explicitly: \"No findings.\""
}

# ---------------------------------------------------------------------------
# Generate diff content for each mode
# ---------------------------------------------------------------------------
generate_uncommitted_diff() {
    local diff_output=""
    local staged
    staged="$(git diff --cached 2>/dev/null || true)"
    local unstaged
    unstaged="$(git diff 2>/dev/null || true)"
    local untracked
    untracked="$(git ls-files --others --exclude-standard 2>/dev/null || true)"

    if [[ -n "${staged}" ]]; then
        diff_output+="--- Staged changes ---"$'\n'"${staged}"$'\n'$'\n'
    fi
    if [[ -n "${unstaged}" ]]; then
        diff_output+="--- Unstaged changes ---"$'\n'"${unstaged}"$'\n'$'\n'
    fi
    if [[ -n "${untracked}" ]]; then
        diff_output+="--- Untracked files ---"$'\n'"${untracked}"$'\n'
    fi

    echo "${diff_output}"
}

generate_base_diff() {
    local branch="$1"
    git diff "${branch}"...HEAD 2>/dev/null || true
}

generate_commit_diff() {
    local sha="$1"
    git show "${sha}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Parse mode and execute
# ---------------------------------------------------------------------------
MODE="${1:-}"

case "${MODE}" in
    uncommitted)
        DIFF_CONTENT="$(generate_uncommitted_diff)"
        if [[ -z "${DIFF_CONTENT}" ]]; then
            echo "No uncommitted changes to review."
            exit 0
        fi
        assemble_review_prompt "${DIFF_CONTENT}" "uncommitted" | codex exec --ephemeral -
        ;;
    base)
        BRANCH="${2:-}"
        if [[ -z "${BRANCH}" ]]; then
            echo "Error: 'base' mode requires a branch name." >&2
            usage
        fi
        DIFF_CONTENT="$(generate_base_diff "${BRANCH}")"
        if [[ -z "${DIFF_CONTENT}" ]]; then
            echo "No diff against '${BRANCH}' to review."
            exit 0
        fi
        assemble_review_prompt "${DIFF_CONTENT}" "base ${BRANCH}" | codex exec --ephemeral -
        ;;
    commit)
        SHA="${2:-}"
        if [[ -z "${SHA}" ]]; then
            echo "Error: 'commit' mode requires a commit SHA." >&2
            usage
        fi
        DIFF_CONTENT="$(generate_commit_diff "${SHA}")"
        if [[ -z "${DIFF_CONTENT}" ]]; then
            echo "Error: could not retrieve commit '${SHA}'." >&2
            exit 1
        fi
        assemble_review_prompt "${DIFF_CONTENT}" "commit ${SHA}" | codex exec --ephemeral -
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
