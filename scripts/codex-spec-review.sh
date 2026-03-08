#!/usr/bin/env bash
# codex-spec-review.sh -- Run a project-aware Codex spec review on a planning artifact directory.
#
# CLI mode verified against installed codex version (2026-03-03):
#   `codex exec` is used (not `codex review`) because spec review is NOT diff-centric.
#   It evaluates planning artifacts (epic and story markdown files) against workflow contracts.
#   The assembled prompt contains file paths and review instructions (not file contents).
#   Codex reads the rubric and epic files itself via its repository access.
#   The prompt (plus optional runtime note) is passed via stdin using `-` as the PROMPT argument.
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
# Assemble prompt (file paths + review instructions + optional runtime note)
# No file contents are embedded -- Codex reads the rubric and epic files itself.
# ---------------------------------------------------------------------------
assemble_prompt() {
    # Warn if the epic directory has no .md files (likely a misconfigured path).
    local md_count
    md_count=$(find "${EPIC_DIR}" -maxdepth 1 -name "*.md" | wc -l)
    if [[ "${md_count}" -eq 0 ]]; then
        echo "Warning: no .md files found in ${EPIC_DIR}" >&2
    fi

    echo "SPEC-REVIEW REQUEST"
    echo ""
    echo "Rubric: ${RUBRIC_FILE}"
    echo "Planning artifacts: ${EPIC_DIR}/ (all *.md files)"

    if [[ -n "${RUNTIME_NOTE}" ]]; then
        echo ""
        echo "RUNTIME CONTEXT NOTE FROM PM"
        echo "${RUNTIME_NOTE}"
    fi

    echo ""
    echo "Instructions:"
    echo "1. Read the rubric at the path above."
    echo "2. Read all .md files in the planning artifacts directory above."
    echo "3. Review the planning artifacts against the rubric. Follow its Evaluation Checklist exactly."
    echo "4. Cite story ID and AC label for each finding."
    echo "5. If the spec is clean, state: \"No findings. This epic is ready to mark READY.\""
}

# ---------------------------------------------------------------------------
# Run Codex spec review
# ---------------------------------------------------------------------------
assemble_prompt | codex exec --ephemeral -
