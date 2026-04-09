#!/usr/bin/env bash
# codex-review.sh -- Run a project-aware Codex code review.
#
# Uses `codex exec --ephemeral -` (NOT `codex review`) because `codex review`
# does not support custom review instructions alongside its diff-scope flags
# (--uncommitted, --base, --commit). The [PROMPT] argument is mutually
# exclusive with those flags. This script embeds both the rubric content and
# the diff into a prompt piped to `codex exec`, which accepts arbitrary prompt
# content via stdin. No repository file access is needed in ephemeral mode.
#
# Verified against codex v0.107.0 (2026-03-03):
#   `codex review --uncommitted` works but accepts NO custom instructions
#   `codex exec --ephemeral -` accepts piped prompt content (used here)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUBRIC_FILE="${REPO_ROOT}/.project/codex-review.md"

WORKDIR=""

usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") [--workdir <path>] <mode> [args]

Options:
  --workdir <path>     Run git commands from the specified directory instead of
                       the script's own REPO_ROOT. In 'uncommitted' mode, the
                       diff is generated as 'git diff main' from <path>.

Modes:
  uncommitted          Review staged, unstaged, and untracked changes
  base <branch>        Review diff against the specified base branch
  commit <sha>         Review a specific commit

Examples:
  $(basename "$0") uncommitted
  $(basename "$0") base main
  $(basename "$0") commit abc1234
  $(basename "$0") --workdir /tmp/.worktrees/baseball-crawl-E-137 uncommitted
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
# Assemble prompt: embedded rubric + diff + review request
# Both the rubric and the diff are embedded directly in the prompt so that
# codex in --ephemeral mode can access them without repository file access.
# ---------------------------------------------------------------------------
assemble_review_prompt() {
    local diff_content="$1"
    local mode_label="$2"
    local rubric_content
    rubric_content="$(cat "${RUBRIC_FILE}")"

    echo "CODE-REVIEW REQUEST"
    echo ""
    echo "REVIEW RUBRIC"
    echo "${rubric_content}"

    echo ""
    echo "CHANGES TO REVIEW (mode: ${mode_label})"
    echo "${diff_content}"

    echo ""
    echo "Instructions:"
    echo "1. Review the changes above against the rubric. Follow its Review Priorities in order."
    echo "2. Cite file and line number for every finding."
    echo "3. Group findings by priority level."
    echo "4. If the review is clean, state explicitly: \"No findings.\""
}

# ---------------------------------------------------------------------------
# Parse optional --workdir before the mode argument
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --workdir)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --workdir requires a path argument." >&2
                usage
            fi
            WORKDIR="$2"
            if [[ ! -d "${WORKDIR}" ]]; then
                echo "Error: --workdir path does not exist: ${WORKDIR}" >&2
                exit 1
            fi
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helper: run git commands from WORKDIR if set, otherwise from REPO_ROOT
# ---------------------------------------------------------------------------
run_git() {
    if [[ -n "${WORKDIR}" ]]; then
        git -C "${WORKDIR}" "$@"
    else
        git "$@"
    fi
}

# ---------------------------------------------------------------------------
# Generate diff content for each mode
# ---------------------------------------------------------------------------
generate_uncommitted_diff() {
    local diff_output=""

    if [[ -n "${WORKDIR}" ]]; then
        # Epic worktree mode: all changes relative to main (staged + unstaged)
        local worktree_diff
        worktree_diff="$(run_git diff main 2>/dev/null || true)"
        if [[ -n "${worktree_diff}" ]]; then
            diff_output+="${worktree_diff}"$'\n'
        fi
        # Note: git diff main compares the working tree to main. In the epic
        # worktree, the working tree contains all accumulated story patches
        # (applied via git apply and staged via git add -A), so this single
        # diff captures the complete epic changeset. No separate --cached
        # pass is needed.
    else
        # Standard mode: separate staged, unstaged, untracked
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
    fi

    echo "${diff_output}"
}

generate_base_diff() {
    local branch="$1"
    run_git diff "${branch}"...HEAD 2>/dev/null || true
}

generate_commit_diff() {
    local sha="$1"
    run_git show "${sha}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Parse mode and execute (remaining args after --workdir was consumed)
# ---------------------------------------------------------------------------
MODE="${1:-}"

# On Ubuntu 24.04 devcontainers, bubblewrap sandboxing fails (AppArmor
# restricts unprivileged user namespaces). Set CODEX_SANDBOX_OFF=1 to bypass.
CODEX_SANDBOX_ARGS=()
if [[ "${CODEX_SANDBOX_OFF:-}" == "1" ]]; then
    CODEX_SANDBOX_ARGS=(--sandbox danger-full-access)
fi

case "${MODE}" in
    uncommitted)
        DIFF_CONTENT="$(generate_uncommitted_diff)"
        if [[ -z "${DIFF_CONTENT}" ]]; then
            echo "No uncommitted changes to review."
            exit 0
        fi
        MODE_LABEL="uncommitted"
        if [[ -n "${WORKDIR}" ]]; then
            MODE_LABEL="uncommitted (workdir: ${WORKDIR})"
        fi
        assemble_review_prompt "${DIFF_CONTENT}" "${MODE_LABEL}" | codex exec --ephemeral "${CODEX_SANDBOX_ARGS[@]}" -
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
        assemble_review_prompt "${DIFF_CONTENT}" "base ${BRANCH}" | codex exec --ephemeral "${CODEX_SANDBOX_ARGS[@]}" -
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
        assemble_review_prompt "${DIFF_CONTENT}" "commit ${SHA}" | codex exec --ephemeral "${CODEX_SANDBOX_ARGS[@]}" -
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
