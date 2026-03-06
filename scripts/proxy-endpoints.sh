#!/usr/bin/env bash
# Print a summary table of unique GameChanger API endpoints from the mitmproxy log.
#
# Usage:
#   proxy-endpoints.sh                  -- read from current session (proxy/data/current/)
#   proxy-endpoints.sh --session <id>   -- read from a specific session
#   proxy-endpoints.sh --all            -- aggregate across all sessions
#   proxy-endpoints.sh --unreviewed     -- aggregate across unreviewed sessions only
#   proxy-endpoints.sh --help           -- show this help
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
Usage: $(basename "$0") [--session <id> | --all | --unreviewed | --help]

Options:
  (none)            Read from the current session (proxy/data/current/)
  --session <id>    Read from a specific session directory
  --all             Aggregate endpoints across all sessions
  --unreviewed      Aggregate endpoints from sessions not yet reviewed
  --help            Show this help message
EOF
}

# ---------------------------------------------------------------------------
# Output formatting (unchanged from original)
# ---------------------------------------------------------------------------

_print_summary() {
    # Reads JSONL from stdin; deduplicates by (method, path).
    echo "Endpoint Discovery Summary"
    echo

    printf "%-7s %-60s %6s %6s\n" "METHOD" "PATH" "HITS" "STATUS"
    printf "%-7s %-60s %6s %6s\n" "------" "----" "----" "------"

    jq -r '[.method, .path, (.status_code | tostring)] | join("\t")' |
        awk -F'\t' '
        {
            key = $1 "\t" $2
            count[key]++
            status[key] = $3  # last seen status code (file order = chronological, so last = most recent)
        }
        END {
            for (key in count) {
                split(key, parts, "\t")
                printf "%-7s %-60s %6d %6s\n", parts[1], parts[2], count[key], status[key]
            }
        }
        ' | sort
}

_no_data_message() {
    echo "No endpoint data captured yet for this selection."
    echo
    echo "  Start the proxy:  cd proxy && ./start.sh"
    echo "  Then browse GameChanger through the proxy."
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

    local log_file="${CURRENT_LINK}/endpoint-log.jsonl"
    if [ ! -f "${log_file}" ]; then
        _no_data_message
        exit 0
    fi

    _print_summary < "${log_file}"
}

mode_session() {
    local session_id="$1"
    local session_dir="${SESSIONS_DIR}/${session_id}"

    if [ ! -d "${session_dir}" ]; then
        echo "Error: session '${session_id}' does not exist at proxy/data/sessions/${session_id}" >&2
        exit 1
    fi

    local log_file="${session_dir}/endpoint-log.jsonl"
    if [ ! -f "${log_file}" ]; then
        echo "No endpoint data for session '${session_id}' (file not found: proxy/data/sessions/${session_id}/endpoint-log.jsonl)." >&2
        exit 1
    fi

    _print_summary < "${log_file}"
}

mode_all() {
    if [ ! -d "${SESSIONS_DIR}" ]; then
        echo "No sessions found (proxy/data/sessions/ does not exist)."
        exit 0
    fi

    # Collect log files across all sessions (glob sorts alphabetically = chronological).
    mapfile -t log_files < <(find "${SESSIONS_DIR}" -name "endpoint-log.jsonl" | sort)

    if [ ${#log_files[@]} -eq 0 ]; then
        _no_data_message
        exit 0
    fi

    cat "${log_files[@]}" | _print_summary
}

mode_unreviewed() {
    if [ ! -d "${SESSIONS_DIR}" ]; then
        echo "No sessions found (proxy/data/sessions/ does not exist)."
        exit 0
    fi

    mapfile -t session_files < <(find "${SESSIONS_DIR}" -name "session.json" | sort)

    if [ ${#session_files[@]} -eq 0 ]; then
        echo "No sessions found."
        exit 0
    fi

    # Collect endpoint logs from sessions where reviewed == false.
    local unreviewed_count=0
    local unreviewed_logs=()
    for session_json in "${session_files[@]}"; do
        reviewed=$(jq -r '.reviewed' "${session_json}")
        if [ "${reviewed}" = "false" ]; then
            unreviewed_count=$((unreviewed_count + 1))
            local session_dir
            session_dir=$(dirname "${session_json}")
            local log_file="${session_dir}/endpoint-log.jsonl"
            if [ -f "${log_file}" ]; then
                unreviewed_logs+=("${log_file}")
            fi
        fi
    done

    if [ "${unreviewed_count}" -eq 0 ]; then
        echo "All sessions reviewed."
        exit 0
    fi

    if [ ${#unreviewed_logs[@]} -eq 0 ]; then
        echo "${unreviewed_count} unreviewed session(s), but none captured endpoint data."
        exit 0
    fi

    cat "${unreviewed_logs[@]}" | _print_summary
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
        --unreviewed)
            MODE="unreviewed"
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
    current)    mode_current ;;
    session)    mode_session "${SESSION_ID}" ;;
    all)        mode_all ;;
    unreviewed) mode_unreviewed ;;
esac
