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

# The Bug Pattern Checklist and Security checklist are single-sourced from the
# code-reviewer agent definition at prompt-assembly time (a live read), so the
# Codex prompt never drifts from CR's rubric. Resolved from REPO_ROOT (the main
# checkout) -- NOT --workdir, which redirects only the git diff, never the
# rubric source. The delimiter markers are the extraction contract documented
# in code-reviewer.md itself.
CR_RUBRIC_FILE="${REPO_ROOT}/.claude/agents/code-reviewer.md"
BUG_PATTERN_START="<!-- BUG-PATTERN-CHECKLIST:START -->"
BUG_PATTERN_END="<!-- BUG-PATTERN-CHECKLIST:END -->"
SECURITY_START="<!-- SECURITY-CHECKLIST:START -->"
SECURITY_END="<!-- SECURITY-CHECKLIST:END -->"

# Deterministic result file: the review output is tee'd here so the read-receipt
# gate (codex-review skill Step 4) reads a stable file instead of a manual
# stdout redirect. In /tmp to avoid any git/worktree interaction.
RESULT_FILE="/tmp/codex-review-$(date +%s).txt"

WORKDIR=""

usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") [--workdir <path>] <mode> [args]

Options:
  --workdir <path>     Run git commands from the specified directory instead of
                       the script's own REPO_ROOT. In 'uncommitted' mode, the
                       diff is generated as 'git diff --diff-filter=ACMR main'
                       from <path> (pure deletions are excluded so they do not
                       exhaust Codex's budget on large removal epics).

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
# Verify the code-reviewer rubric and its delimiter markers honor the full
# contract code-reviewer.md declares (E-258-01 AC-5): each of the four markers
# appears EXACTLY ONCE, and each START precedes its matching END. Fail closed
# otherwise -- extract_block() would silently take only the first of duplicated
# markers, or emit an EMPTY block on an END-before-START pair, shipping a
# partial/empty checklist instead of failing. The Codex prompt must carry the
# Bug Pattern and Security checklists from exactly one source (the CR rubric),
# never zero and never partial.
# ---------------------------------------------------------------------------
if [[ ! -f "${CR_RUBRIC_FILE}" ]]; then
    echo "Error: code-reviewer rubric not found: ${CR_RUBRIC_FILE}" >&2
    exit 1
fi
for _marker in "${BUG_PATTERN_START}" "${BUG_PATTERN_END}" "${SECURITY_START}" "${SECURITY_END}"; do
    _count=$(grep -cF -- "${_marker}" "${CR_RUBRIC_FILE}" || true)
    if [[ "${_count}" -ne 1 ]]; then
        echo "Error: delimiter marker must appear exactly once in ${CR_RUBRIC_FILE} (found ${_count}): ${_marker}" >&2
        echo "The single-source Codex rubric extraction requires the delimiter contract (exactly one START and one END per pair, START before END; see code-reviewer.md)." >&2
        exit 1
    fi
done
for _pair in "${BUG_PATTERN_START}|${BUG_PATTERN_END}" "${SECURITY_START}|${SECURITY_END}"; do
    _start="${_pair%%|*}"
    _end="${_pair##*|}"
    _sl=$(grep -nF -- "${_start}" "${CR_RUBRIC_FILE}" | head -1 | cut -d: -f1 || true)
    _el=$(grep -nF -- "${_end}" "${CR_RUBRIC_FILE}" | head -1 | cut -d: -f1 || true)
    if [[ -z "${_sl}" || -z "${_el}" || "${_sl}" -ge "${_el}" ]]; then
        echo "Error: delimiter START must precede its END in ${CR_RUBRIC_FILE} (START line=${_sl:-none}, END line=${_el:-none}): ${_start}" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Extract the content between two literal delimiter markers (exclusive of the
# marker lines) from a file. Uses awk index() (literal substring match), so the
# HTML-comment markers' special characters need no escaping. Prints nothing if
# the markers are absent -- callers validate marker presence up front.
# ---------------------------------------------------------------------------
extract_block() {
    local start="$1" end="$2" file="$3"
    awk -v s="${start}" -v e="${end}" '
        index($0, e) { exit }
        grab { print }
        index($0, s) { grab = 1 }
    ' "${file}"
}

# ---------------------------------------------------------------------------
# Assemble prompt: embedded rubric + single-sourced CR checklists + diff +
# review request. Everything is embedded directly in the prompt so that codex
# in --ephemeral mode can access it without repository file access. The Bug
# Pattern and Security checklists are read live from code-reviewer.md at
# assembly time (single source of truth), so the Codex prompt cannot drift from
# CR's rubric.
# ---------------------------------------------------------------------------
assemble_review_prompt() {
    local diff_content="$1"
    local mode_label="$2"
    local rubric_content
    rubric_content="$(cat "${RUBRIC_FILE}")"
    local bug_pattern_block
    bug_pattern_block="$(extract_block "${BUG_PATTERN_START}" "${BUG_PATTERN_END}" "${CR_RUBRIC_FILE}")"
    local security_block
    security_block="$(extract_block "${SECURITY_START}" "${SECURITY_END}" "${CR_RUBRIC_FILE}")"

    echo "CODE-REVIEW REQUEST"
    echo ""
    echo "REVIEW RUBRIC"
    echo "${rubric_content}"

    echo ""
    echo "CODE-REVIEWER BUG PATTERN CHECKLIST (single-sourced live from code-reviewer.md)"
    echo "${bug_pattern_block}"

    echo ""
    echo "CODE-REVIEWER SECURITY CHECKLIST (single-sourced live from code-reviewer.md)"
    echo "${security_block}"

    echo ""
    echo "CHANGES TO REVIEW (mode: ${mode_label})"
    echo "${diff_content}"

    echo ""
    echo "Instructions:"
    echo "1. Review the changes above against the rubric and both checklists. Follow the Review Priorities in order."
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
        # Epic worktree mode: all changes relative to main (staged + unstaged).
        # Default to --diff-filter=ACMR (added/copied/modified/renamed) so pure
        # deletions do not consume Codex's budget on large removal epics and
        # degrade the review to static-only (E-239's 2.57M-char diff dropped to
        # ~445K under ACMR). Deletions have no content to review.
        local worktree_diff
        worktree_diff="$(run_git diff --diff-filter=ACMR main 2>/dev/null || true)"
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

# ---------------------------------------------------------------------------
# Run the review: pipe the assembled prompt to codex, tee the streamed output
# to the deterministic RESULT_FILE (so the read-receipt gate reads a stable
# file, not a manual stdout redirect), and emit a receipt to stdout. Output
# still streams live. set -o pipefail is preserved: codex's exit code (the
# rightmost non-zero) propagates through the zero-exit tee; we capture it,
# print the receipt regardless of pass/fail, then return it so the script's
# exit status still reflects codex.
# ---------------------------------------------------------------------------
run_codex_review() {
    local diff_content="$1" mode_label="$2"
    local rc=0
    assemble_review_prompt "${diff_content}" "${mode_label}" \
        | codex exec --ephemeral "${CODEX_SANDBOX_ARGS[@]}" - \
        | tee "${RESULT_FILE}" || rc=$?
    echo ""
    echo "RESULT_FILE=${RESULT_FILE}"
    if [[ -f "${RESULT_FILE}" ]]; then
        wc -l "${RESULT_FILE}"
        echo "tail -n1: $(tail -n1 "${RESULT_FILE}")"
    fi
    return "${rc}"
}

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
        run_codex_review "${DIFF_CONTENT}" "${MODE_LABEL}"
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
        run_codex_review "${DIFF_CONTENT}" "base ${BRANCH}"
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
        run_codex_review "${DIFF_CONTENT}" "commit ${SHA}"
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
