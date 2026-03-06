#!/usr/bin/env bash
# Manage mitmproxy session review status.
#
# Usage:
#   proxy-review.sh list               -- list all sessions with review status
#   proxy-review.sh mark <session-id>  -- mark a specific session as reviewed
#   proxy-review.sh mark --all         -- mark all closed sessions as reviewed
#   proxy-review.sh --help             -- show this help
#
# Sessions are stored in proxy/data/sessions/. Each session has a session.json
# file with a `reviewed` field. The `current` symlink marks the most recent session.
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
Usage: $(basename "$0") <subcommand> [args]

Subcommands:
  list               List all sessions with their review status
  mark <session-id>  Mark a specific session as reviewed
  mark --all         Mark all closed sessions as reviewed
  --help             Show this help message

Session data is stored in proxy/data/sessions/.
EOF
}

# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------

cmd_list() {
    if [ ! -d "${SESSIONS_DIR}" ]; then
        echo "No sessions found (proxy/data/sessions/ does not exist)."
        return 0
    fi

    # Collect session.json files, sorted by session ID (directory name = timestamp).
    mapfile -t session_files < <(find "${SESSIONS_DIR}" -name "session.json" | sort)

    if [ ${#session_files[@]} -eq 0 ]; then
        echo "No sessions found."
        return 0
    fi

    # Determine which session the current symlink points to.
    current_id=""
    if [ -L "${CURRENT_LINK}" ]; then
        current_target=$(readlink "${CURRENT_LINK}")
        current_id=$(basename "${current_target}")
    fi

    # Print table header.
    printf "%-22s  %-8s  %-10s  %5s  %s\n" "SESSION_ID" "PROFILE" "STATUS" "ENDPTS" "REVIEWED"
    printf "%-22s  %-8s  %-10s  %5s  %s\n" "----------" "-------" "------" "------" "--------"

    for session_json in "${session_files[@]}"; do
        session_id=$(jq -r '.session_id' "${session_json}")
        profile=$(jq -r '.profile' "${session_json}")
        status=$(jq -r '.status' "${session_json}")
        endpoint_count=$(jq -r '.endpoint_count' "${session_json}")
        reviewed=$(jq -r '.reviewed' "${session_json}")

        # Add * marker if this session is the current symlink target.
        if [ "${session_id}" = "${current_id}" ]; then
            status_display="${status} *"
        else
            status_display="${status}"
        fi

        printf "%-22s  %-8s  %-10s  %5s  %s\n" \
            "${session_id}" \
            "${profile}" \
            "${status_display}" \
            "${endpoint_count}" \
            "${reviewed}"
    done
}

# ---------------------------------------------------------------------------
# mark subcommand
# ---------------------------------------------------------------------------

cmd_mark() {
    local target="${1:-}"

    if [ -z "${target}" ]; then
        echo "Error: mark requires a session-id or --all" >&2
        echo "Usage: $(basename "$0") mark <session-id> | --all" >&2
        exit 1
    fi

    if [ "${target}" = "--all" ]; then
        _mark_all
    else
        _mark_session "${target}"
    fi
}

_mark_session() {
    local session_id="$1"
    local session_dir="${SESSIONS_DIR}/${session_id}"
    local session_json="${session_dir}/session.json"

    if [ ! -d "${session_dir}" ]; then
        echo "Error: session '${session_id}' does not exist at proxy/data/sessions/${session_id}" >&2
        exit 1
    fi

    if [ ! -f "${session_json}" ]; then
        echo "Error: session.json not found for session '${session_id}'" >&2
        exit 1
    fi

    jq '.reviewed = true' "${session_json}" > "${session_json}.tmp" && mv "${session_json}.tmp" "${session_json}"
    echo "Marked session ${session_id} as reviewed."
}

_mark_all() {
    if [ ! -d "${SESSIONS_DIR}" ]; then
        echo "No sessions found (proxy/data/sessions/ does not exist)."
        return 0
    fi

    mapfile -t session_files < <(find "${SESSIONS_DIR}" -name "session.json" | sort)

    if [ ${#session_files[@]} -eq 0 ]; then
        echo "No sessions found."
        return 0
    fi

    local marked=0
    for session_json in "${session_files[@]}"; do
        status=$(jq -r '.status' "${session_json}")
        if [ "${status}" = "closed" ]; then
            session_id=$(jq -r '.session_id' "${session_json}")
            jq '.reviewed = true' "${session_json}" > "${session_json}.tmp" && mv "${session_json}.tmp" "${session_json}"
            echo "Marked session ${session_id} as reviewed."
            marked=$((marked + 1))
        fi
    done

    if [ "${marked}" -eq 0 ]; then
        echo "No closed sessions to mark."
    else
        echo "Marked ${marked} session(s) as reviewed."
    fi
}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

if [ $# -eq 0 ] || [ "${1}" = "--help" ] || [ "${1}" = "-h" ]; then
    usage
    exit 0
fi

subcommand="$1"
shift

case "${subcommand}" in
    list)
        cmd_list
        ;;
    mark)
        cmd_mark "${1:-}"
        ;;
    *)
        echo "Error: unknown subcommand '${subcommand}'" >&2
        echo
        usage
        exit 1
        ;;
esac
