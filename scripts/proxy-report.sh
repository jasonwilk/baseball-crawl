#!/usr/bin/env bash
# Print a human-readable summary of the mitmproxy header parity report.
#
# Usage:
#   proxy-report.sh                  -- read from current session (proxy/data/current/)
#   proxy-report.sh --session <id>   -- read from a specific session
#   proxy-report.sh --all            -- read from the most recent closed session with data
#   proxy-report.sh --help           -- show this help
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SESSIONS_DIR="${REPO_ROOT}/proxy/data/sessions"
CURRENT_LINK="${REPO_ROOT}/proxy/data/current"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") [--session <id> | --all | --help]

Options:
  (none)            Read from the current session (proxy/data/current/)
  --session <id>    Read from a specific session directory
  --all             Read from the most recent closed session that has a header report
  --help            Show this help message

Note: header reports are point-in-time snapshots, not aggregatable.
EOF
}

# ---------------------------------------------------------------------------
# Output formatting (unchanged from original)
# ---------------------------------------------------------------------------

_print_report() {
    local report_file="$1"

    echo "Header Parity Report"
    echo "Generated: $(jq -r '.generated_at' "${report_file}")"
    echo

    jq -r '
.sources[] |
"--- Source: \(.source) ---\n" +

(if (.missing_in_captured | length) > 0
 then "  Missing in captured (present in BROWSER_HEADERS):\n" +
      (.missing_in_captured | map("    - " + .) | join("\n")) + "\n"
 else "  Missing in captured: (none)\n" end) +

(if (.extra_in_captured | length) > 0
 then "  Extra in captured (not in BROWSER_HEADERS):\n" +
      (.extra_in_captured | map("    - " + .) | join("\n")) + "\n"
 else "  Extra in captured: (none)\n" end) +

(if (.value_differences | length) > 0
 then "  Value differences:\n" +
      (.value_differences | map("    - \(.key):\n        captured:  \(.captured)\n        canonical: \(.canonical)") | join("\n")) + "\n"
 else "  Value differences: (none)\n" end)
' "${report_file}"
}

# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------

mode_current() {
    if [ ! -L "${CURRENT_LINK}" ]; then
        echo "Error: no current session found (proxy/data/current symlink does not exist)." >&2
        echo "Start the proxy with:  cd proxy && ./start.sh" >&2
        exit 1
    fi

    local report_file="${CURRENT_LINK}/header-report.json"
    if [ ! -f "${report_file}" ]; then
        echo "No header report in the current session (no GC traffic captured yet)."
        echo
        echo "  Browse GameChanger through the proxy to generate a report."
        exit 0
    fi

    _print_report "${report_file}"
}

mode_session() {
    local session_id="$1"
    local session_dir="${SESSIONS_DIR}/${session_id}"

    if [ ! -d "${session_dir}" ]; then
        echo "Error: session '${session_id}' does not exist at proxy/data/sessions/${session_id}" >&2
        exit 1
    fi

    local report_file="${session_dir}/header-report.json"
    if [ ! -f "${report_file}" ]; then
        echo "No header report for session '${session_id}' (file not found: proxy/data/sessions/${session_id}/header-report.json)." >&2
        exit 1
    fi

    _print_report "${report_file}"
}

mode_all() {
    # "All" means the most recent closed session that has a header-report.json.
    # Header reports are point-in-time snapshots -- not aggregatable.
    if [ ! -d "${SESSIONS_DIR}" ]; then
        echo "No sessions found (proxy/data/sessions/ does not exist)." >&2
        exit 1
    fi

    # Iterate sessions in reverse chronological order (reverse sort = newest first).
    mapfile -t session_dirs < <(find "${SESSIONS_DIR}" -mindepth 1 -maxdepth 1 -type d | sort -r)

    for session_dir in "${session_dirs[@]}"; do
        local session_json="${session_dir}/session.json"
        local report_file="${session_dir}/header-report.json"

        if [ ! -f "${session_json}" ]; then
            continue
        fi

        local status
        status=$(jq -r '.status' "${session_json}")

        if [ "${status}" = "closed" ] && [ -f "${report_file}" ]; then
            local session_id
            session_id=$(basename "${session_dir}")
            echo "(Showing report from most recent closed session: ${session_id})"
            echo
            _print_report "${report_file}"
            exit 0
        fi
    done

    echo "Error: no closed session with a header report found." >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

MODE="current"
SESSION_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --all)
            MODE="all"
            shift
            ;;
        --session)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --session requires a session ID argument" >&2
                exit 1
            fi
            MODE="session"
            SESSION_ID="$2"
            shift 2
            ;;
        *)
            echo "Error: unknown argument: $1" >&2
            echo
            usage
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

case "${MODE}" in
    current) mode_current ;;
    session) mode_session "${SESSION_ID}" ;;
    all)     mode_all ;;
esac
