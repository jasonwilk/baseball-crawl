#!/usr/bin/env bash
# Stop the host mitmproxy and finalize the current capture session.
set -euo pipefail
cd "$(dirname "$0")"

# --- Session finalization ---

SESSION_FOUND=false
SESSION_ID=""
SESSION_PROFILE=""
SESSION_STARTED_AT=""
STOPPED_AT=""
ENDPOINT_COUNT=0
UNIQUE_ENDPOINT_COUNT=0
ENDPOINT_LOG=""

if [ -L data/current ]; then
    # readlink returns the symlink target (e.g. "sessions/2026-03-06_143022"),
    # which is relative to data/. Prefix data/ to get the path from cwd (proxy/).
    SESSION_DIR="data/$(readlink data/current)"
    SESSION_JSON="${SESSION_DIR}/session.json"

    if [ -f "${SESSION_JSON}" ]; then
        SESSION_STATUS=$(jq -r '.status' "${SESSION_JSON}")

        if [ "${SESSION_STATUS}" = "active" ]; then
            STOPPED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

            # Count endpoints from the session's endpoint log.
            ENDPOINT_LOG="${SESSION_DIR}/endpoint-log.jsonl"
            if [ -f "${ENDPOINT_LOG}" ]; then
                ENDPOINT_COUNT=$(wc -l < "${ENDPOINT_LOG}" | tr -d ' ')
            else
                ENDPOINT_COUNT=0
            fi

            # Update session.json in place.
            jq \
                --arg stopped_at "${STOPPED_AT}" \
                --argjson endpoint_count "${ENDPOINT_COUNT}" \
                '.stopped_at = $stopped_at | .status = "closed" | .endpoint_count = $endpoint_count' \
                "${SESSION_JSON}" > "${SESSION_JSON}.tmp" && mv "${SESSION_JSON}.tmp" "${SESSION_JSON}"

            # Count unique method+path combinations.
            if [ -f "${ENDPOINT_LOG}" ] && [ "${ENDPOINT_COUNT}" -gt 0 ]; then
                UNIQUE_ENDPOINT_COUNT=$(jq -r '[.method, .path] | join(" ")' "${ENDPOINT_LOG}" | sort -u | wc -l | tr -d ' ')
            fi
        fi

        # Capture fields needed for the summary (read after potential update).
        SESSION_ID=$(basename "${SESSION_DIR}")
        SESSION_PROFILE=$(jq -r '.profile' "${SESSION_JSON}")
        SESSION_STARTED_AT=$(jq -r '.started_at' "${SESSION_JSON}")
        STOPPED_AT=$(jq -r '.stopped_at // ""' "${SESSION_JSON}")
        ENDPOINT_COUNT=$(jq -r '.endpoint_count // 0' "${SESSION_JSON}")
        ENDPOINT_LOG="${SESSION_DIR}/endpoint-log.jsonl"
        SESSION_FOUND=true

        # Count unique method+path combinations (if not already computed above).
        if [ "${UNIQUE_ENDPOINT_COUNT}" -eq 0 ] && [ -f "${ENDPOINT_LOG}" ] && [ "${ENDPOINT_COUNT}" -gt 0 ]; then
            UNIQUE_ENDPOINT_COUNT=$(jq -r '[.method, .path] | join(" ")' "${ENDPOINT_LOG}" | sort -u | wc -l | tr -d ' ')
        fi
    else
        echo "Warning: data/current symlink exists but session.json not found at ${SESSION_JSON}" >&2
    fi
    # Leave the current symlink in place (pointing to the now-closed session).
else
    echo "Warning: no active session found (data/current symlink does not exist). Session will not be finalized." >&2
fi

docker compose down
echo "mitmproxy stopped."

# --- Session summary ---

if [ "${SESSION_FOUND}" = "true" ]; then
    echo

    # Compute human-readable duration (best-effort; degrades gracefully on unsupported platforms).
    DURATION=""
    if [ -n "${SESSION_STARTED_AT}" ] && [ -n "${STOPPED_AT}" ]; then
        DURATION=$(
            _ts() {
                # Try macOS date first, fall back to GNU date.
                if date -j -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%s 2>/dev/null; then
                    return 0
                fi
                date -d "$1" +%s 2>/dev/null || echo ""
            }
            START_TS=$(_ts "${SESSION_STARTED_AT}")
            STOP_TS=$(_ts "${STOPPED_AT}")
            if [ -n "${START_TS}" ] && [ -n "${STOP_TS}" ]; then
                SECS=$(( STOP_TS - START_TS ))
                if [ "${SECS}" -ge 3600 ]; then
                    printf "%dh %dm" $(( SECS / 3600 )) $(( (SECS % 3600) / 60 ))
                elif [ "${SECS}" -ge 60 ]; then
                    printf "%dm %ds" $(( SECS / 60 )) $(( SECS % 60 ))
                else
                    printf "%ds" "${SECS}"
                fi
            fi
        ) 2>/dev/null || true
    fi

    echo "Session summary"
    echo "  ID:        ${SESSION_ID}"
    echo "  Profile:   ${SESSION_PROFILE}"
    echo "  Started:   ${SESSION_STARTED_AT}"
    if [ -n "${DURATION}" ]; then
        echo "  Stopped:   ${STOPPED_AT}  (${DURATION})"
    else
        echo "  Stopped:   ${STOPPED_AT}"
    fi

    if [ "${ENDPOINT_COUNT}" -eq 0 ]; then
        echo "  Traffic:   No GameChanger traffic captured"
    else
        echo "  Traffic:   ${ENDPOINT_COUNT} requests  |  ${UNIQUE_ENDPOINT_COUNT} unique endpoints"
    fi

    echo
    echo "Next steps:"
    echo "  Review discoveries:  scripts/proxy-endpoints.sh"
    echo "  Mark as reviewed:    scripts/proxy-review.sh mark ${SESSION_ID}"
fi
