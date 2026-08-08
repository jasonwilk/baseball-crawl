#!/usr/bin/env bash
# codex-spec-review.sh -- Run a project-aware Codex review on a chunk spec file.
#
# CLI mode verified against installed codex version (2026-03-03):
#   `codex exec` is used (not `codex review`) because spec review is NOT diff-centric.
#   It evaluates a one-page spec against the project's workflow contracts.
#   The assembled prompt contains file paths and review instructions (not file contents).
#   Codex reads the rubric and the spec file itself via its repository access.
#   The prompt (plus optional runtime note) is passed via stdin using `-` as the PROMPT argument.
#
# Usage:
#   codex-spec-review.sh <spec-file> [--note "text"] [--note-file /path/to/file]
#
# Examples:
#   ./scripts/codex-spec-review.sh .project/specs/2026-08-05-rung-c-season-year-filter.md
#   ./scripts/codex-spec-review.sh .project/specs/<date>-<slug>.md --note "Focus on the destructive seams"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUBRIC_FILE="${REPO_ROOT}/.project/codex-spec-review.md"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") <spec-file> [--note "text"] [--note-file /path/to/file]

Arguments:
  <spec-file>            Path to the chunk spec markdown file to review.
                         Can be absolute or relative to the repo root.

Options:
  --note "text"          Include a short runtime context note in the Codex prompt.
                         Describe what the chunk does and what to focus on.
  --note-file /path      Read the runtime note from a file instead of inline text.

Examples:
  $(basename "$0") .project/specs/2026-08-05-rung-c-season-year-filter.md
  $(basename "$0") .project/specs/<date>-<slug>.md --note "Check the byte budget claims"
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
# Parse arguments
# ---------------------------------------------------------------------------
SPEC_FILE=""
RUNTIME_NOTE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --note)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --note requires a non-empty text argument." >&2
                usage
            fi
            RUNTIME_NOTE="$2"
            shift 2
            ;;
        --note-file)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --note-file requires a file path." >&2
                usage
            fi
            if [[ ! -f "$2" ]]; then
                echo "Error: note file not found: $2" >&2
                exit 1
            fi
            RUNTIME_NOTE="$(cat "$2")"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        -*)
            echo "Error: unknown option '$1'." >&2
            usage
            ;;
        *)
            if [[ -n "${SPEC_FILE}" ]]; then
                echo "Error: unexpected argument '$1' (spec-file already set to '${SPEC_FILE}')." >&2
                usage
            fi
            SPEC_FILE="$1"
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate required argument
# ---------------------------------------------------------------------------
if [[ -z "${SPEC_FILE}" ]]; then
    echo "Error: spec-file is required." >&2
    usage
fi

# Resolve to an absolute path. If the path is relative, try it from cwd first,
# then from REPO_ROOT.
if [[ "${SPEC_FILE}" != /* ]]; then
    if [[ -f "${SPEC_FILE}" ]]; then
        SPEC_FILE="$(cd "$(dirname "${SPEC_FILE}")" && pwd)/$(basename "${SPEC_FILE}")"
    elif [[ -f "${REPO_ROOT}/${SPEC_FILE}" ]]; then
        SPEC_FILE="${REPO_ROOT}/${SPEC_FILE}"
    fi
fi

if [[ ! -f "${SPEC_FILE}" ]]; then
    echo "Error: spec file does not exist: ${SPEC_FILE}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify the rubric exists
# ---------------------------------------------------------------------------
if [[ ! -f "${RUBRIC_FILE}" ]]; then
    echo "Error: rubric file not found: ${RUBRIC_FILE}" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Assemble prompt (file paths + review instructions + optional runtime note)
# No file contents are embedded -- Codex reads the rubric and the spec itself.
# ---------------------------------------------------------------------------
assemble_prompt() {
    echo "SPEC-REVIEW REQUEST"
    echo ""
    echo "Rubric: ${RUBRIC_FILE}"
    echo "Spec under review: ${SPEC_FILE}"

    if [[ -n "${RUNTIME_NOTE}" ]]; then
        echo ""
        echo "RUNTIME CONTEXT NOTE"
        echo "${RUNTIME_NOTE}"
    fi

    echo ""
    echo "Instructions:"
    echo "1. Read the rubric at the path above."
    echo "2. Read the spec file above."
    echo "3. Review the spec against the rubric. Follow its Evaluation Checklist exactly."
    echo "4. Check the spec's claims against the actual repository -- a spec is a CLAIM, not a fact."
    echo "5. Cite the spec's section heading for each finding."
    echo "6. If the spec is clean, state: \"No findings. This spec is ready to execute.\""
}

# ---------------------------------------------------------------------------
# Run Codex spec review
# ---------------------------------------------------------------------------
# On Ubuntu 24.04 devcontainers, bubblewrap sandboxing fails (AppArmor
# restricts unprivileged user namespaces). Set CODEX_SANDBOX_OFF=1 to bypass.
CODEX_SANDBOX_ARGS=()
if [[ "${CODEX_SANDBOX_OFF:-}" == "1" ]]; then
    CODEX_SANDBOX_ARGS=(--sandbox danger-full-access)
fi

# The review output is tee'd to RESULT_FILE so the read-receipt gate (skill Step
# 4) reads a stable file instead of a manual stdout redirect -- the documented
# fabrication hole, skipped on 44 of 48 invocations.
#
# mktemp, NOT a timestamp: two runs starting in the same second would resolve to
# one second-granular name, and the second tee would truncate the first, leaving
# run A's receipt describing run B's review -- precisely the fabrication class
# this receipt exists to close. mktemp also defeats a symlink pre-planted at a
# predictable path. Created HERE, after argument parsing, so a usage error does
# not litter /tmp.
RESULT_FILE="$(mktemp -t codex-spec-review.XXXXXX)"

# ANNOUNCE THE PATH BEFORE CODEX RUNS. This line is load-bearing and its POSITION
# is the whole point: a large review is truncated to a PREVIEW OF THE FIRST ~2KB
# by the calling tool, and the motivating incident was a ~373KB result -- so a
# receipt printed only after the stream is invisible in exactly the case it was
# built for. The skill's prescribed `timeout 1200` has the same shape: SIGTERM
# kills the script mid-stream and no trailing echo ever runs, stranding a partial
# result file nobody can name. Printing first survives both. Do NOT move it below
# the pipeline, and do not delete it as a duplicate of the trailing receipt.
echo "RESULT_FILE=${RESULT_FILE}"
echo ""

# Fail EARLY and legibly if the result file is not writable. Without this, a tee
# that cannot write exits immediately, codex takes SIGPIPE mid-review, and
# pipefail surfaces a non-zero rc -- which the skill maps to "the script itself
# failed", discarding a review that actually ran fine.
if ! : > "${RESULT_FILE}"; then
    echo "Error: cannot write the result file: ${RESULT_FILE}" >&2
    exit 1
fi

# set -o pipefail is preserved: codex's exit code (the rightmost non-zero)
# propagates through the zero-exit tee; we capture it, print the receipt
# regardless of pass/fail, then return it so the exit status still reflects codex.
rc=0
assemble_prompt \
    | codex exec --ephemeral "${CODEX_SANDBOX_ARGS[@]}" - \
    | tee "${RESULT_FILE}" || rc=$?
echo ""
echo "RESULT_FILE=${RESULT_FILE}"
if [[ -f "${RESULT_FILE}" ]]; then
    wc -l "${RESULT_FILE}"
    echo "tail -n1: $(tail -n1 "${RESULT_FILE}")"
fi
exit "${rc}"
