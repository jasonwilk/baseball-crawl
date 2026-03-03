#!/usr/bin/env bash
# codex-spec-review.sh -- Run a project-aware Codex spec review on a planning artifact directory.
#
# CLI mode verified against installed codex version (2026-03-03):
#   `codex exec` is used (not `codex review`) because spec review is NOT diff-centric.
#   It evaluates planning artifacts (epic and story markdown files) against workflow contracts.
#   The assembled prompt (rubric + file contents + optional runtime note) is passed via stdin
#   using `-` as the PROMPT argument to `codex exec`.
#
# Usage:
#   codex-spec-review.sh <epic-dir> [--note "text"] [--note-file /path/to/file]
#
# Examples:
#   ./scripts/codex-spec-review.sh epics/E-034-codex-review
#   ./scripts/codex-spec-review.sh epics/E-034-codex-review --note "Focus on AC testability"
#   ./scripts/codex-spec-review.sh epics/E-034-codex-review --note-file /tmp/pm-context.txt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUBRIC_FILE="${REPO_ROOT}/.project/codex-spec-review.md"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") <epic-dir> [--note "text"] [--note-file /path/to/file]

Arguments:
  <epic-dir>             Path to the epic directory to review (must contain epic.md).
                         Can be absolute or relative to the repo root.

Options:
  --note "text"          Include a short runtime context note in the Codex prompt.
                         Describe what the epic accomplishes, what changed, and
                         what you want Codex to focus on.
  --note-file /path      Read the runtime note from a file instead of inline text.

Examples:
  $(basename "$0") epics/E-034-codex-review
  $(basename "$0") epics/E-034-codex-review --note "Focus on AC testability in E-034-03"
  $(basename "$0") /workspaces/baseball-crawl/epics/E-034-codex-review --note-file /tmp/context.txt
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
EPIC_DIR=""
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
            if [[ -n "${EPIC_DIR}" ]]; then
                echo "Error: unexpected argument '$1' (epic-dir already set to '${EPIC_DIR}')." >&2
                usage
            fi
            EPIC_DIR="$1"
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate required argument
# ---------------------------------------------------------------------------
if [[ -z "${EPIC_DIR}" ]]; then
    echo "Error: epic-dir is required." >&2
    usage
fi

# Resolve to absolute path. If the path is relative, try it from cwd first,
# then from REPO_ROOT.
if [[ "${EPIC_DIR}" != /* ]]; then
    if [[ -d "${EPIC_DIR}" ]]; then
        EPIC_DIR="$(cd "${EPIC_DIR}" && pwd)"
    elif [[ -d "${REPO_ROOT}/${EPIC_DIR}" ]]; then
        EPIC_DIR="$(cd "${REPO_ROOT}/${EPIC_DIR}" && pwd)"
    fi
fi

if [[ ! -d "${EPIC_DIR}" ]]; then
    echo "Error: epic directory does not exist: ${EPIC_DIR}" >&2
    exit 1
fi

if [[ ! -f "${EPIC_DIR}/epic.md" ]]; then
    echo "Error: epic.md not found in ${EPIC_DIR}" >&2
    echo "  The target directory must be an epic directory containing an epic.md file." >&2
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
# Assemble prompt (rubric + epic file contents + optional runtime note)
# No files are created or persisted -- everything is assembled in memory.
# ---------------------------------------------------------------------------
assemble_prompt() {
    echo "======================================================================"
    echo "SPEC-REVIEW RUBRIC"
    echo "======================================================================"
    cat "${RUBRIC_FILE}"

    echo ""
    echo "======================================================================"
    echo "PLANNING ARTIFACTS TO REVIEW (epic directory: ${EPIC_DIR})"
    echo "======================================================================"

    local found_files=0
    while IFS= read -r -d '' md_file; do
        echo ""
        echo "--- FILE: ${md_file} ---"
        cat "${md_file}"
        found_files=1
    done < <(find "${EPIC_DIR}" -maxdepth 1 -name "*.md" -print0 | sort -z)

    if [[ "${found_files}" -eq 0 ]]; then
        echo "Warning: no .md files found in ${EPIC_DIR}" >&2
    fi

    if [[ -n "${RUNTIME_NOTE}" ]]; then
        echo ""
        echo "======================================================================"
        echo "RUNTIME CONTEXT NOTE FROM PM"
        echo "======================================================================"
        echo "${RUNTIME_NOTE}"
    fi

    echo ""
    echo "======================================================================"
    echo "REVIEW REQUEST"
    echo "======================================================================"
    echo "Please review the planning artifacts above against the spec-review rubric."
    echo "Follow the rubric's Evaluation Checklist exactly."
    echo "Cite story ID and AC label for each finding."
    echo "If the spec is clean, state: \"No findings. This epic is ready to mark READY.\""
}

# ---------------------------------------------------------------------------
# Run Codex spec review
# ---------------------------------------------------------------------------
assemble_prompt | codex exec --ephemeral -
