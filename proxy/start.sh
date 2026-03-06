#!/usr/bin/env bash
# Start mitmproxy on the Mac host for traffic capture.
#
# Usage:
#   ./start.sh [--profile mobile|web]
#
# Profiles:
#   mobile (default) -- captures iPhone traffic via PROXY_URL_MOBILE
#   web              -- captures browser traffic via PROXY_URL_WEB
#
# When PROXY_ENABLED=true and the profile's URL var is set, mitmproxy starts
# in upstream proxy mode. Otherwise it runs as a regular intercepting proxy.
#
# Ports:
#   8080 - proxy listener (all interfaces, iPhone can reach it)
#   8081 - mitmweb UI (localhost only)
#
# Certs are stored in proxy/certs/ so the iPhone trust persists across restarts.
set -euo pipefail

cd "$(dirname "$0")"

# Parse --profile argument.
MITMPROXY_PROFILE="mobile"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --profile requires an argument (mobile or web)" >&2
                exit 1
            fi
            MITMPROXY_PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Error: unknown argument: $1" >&2
            echo "Usage: $0 [--profile mobile|web]" >&2
            exit 1
            ;;
    esac
done

# Validate profile.
case "$MITMPROXY_PROFILE" in
    mobile|web)
        ;;
    *)
        echo "Error: invalid profile '${MITMPROXY_PROFILE}'. Valid profiles: mobile, web" >&2
        exit 1
        ;;
esac

export MITMPROXY_PROFILE

# Create certs dir if it doesn't exist. Use permissive mode so the container's
# mitmproxy user (UID 1000) can write CA certs regardless of host UID.
mkdir -p -m 777 certs

# --- Session lifecycle ---

# Warn if a current session is still active (unclean shutdown).
# A closed session leaves the symlink in place by design -- only warn for active ones.
if [ -L data/current ]; then
    PREV_SESSION_JSON="data/$(readlink data/current)/session.json"
    if [ -f "${PREV_SESSION_JSON}" ]; then
        PREV_STATUS=$(jq -r '.status' "${PREV_SESSION_JSON}")
        if [ "${PREV_STATUS}" = "active" ]; then
            echo "Warning: a previous session is still active (data/current symlink exists)." >&2
            echo "         The previous session will remain status 'active' as a signal of unclean shutdown." >&2
        fi
    fi
fi

# Create session directory.
SESSION_ID=$(date -u +%Y-%m-%d_%H%M%S)
SESSION_DIR="data/sessions/${SESSION_ID}"
mkdir -p "${SESSION_DIR}"

# Write session.json metadata.
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq -n \
    --arg session_id "${SESSION_ID}" \
    --arg profile "${MITMPROXY_PROFILE}" \
    --arg started_at "${STARTED_AT}" \
    '{
        session_id: $session_id,
        profile: $profile,
        started_at: $started_at,
        stopped_at: null,
        status: "active",
        endpoint_count: 0,
        reviewed: false,
        review_notes: ""
    }' > "${SESSION_DIR}/session.json"

# Create (or update) the current symlink to point to the new session.
# Use a relative path so it works both on the host and inside the container.
ln -sfn "sessions/${SESSION_ID}" data/current

# Export PROXY_SESSION_DIR for the mitmproxy container.
# The container mounts the project root at /app, so proxy/data maps to /app/proxy/data.
export PROXY_SESSION_DIR="/app/proxy/data/sessions/${SESSION_ID}"

docker compose up -d

echo
echo "mitmproxy is running on the host."
echo
echo "  Profile:    ${MITMPROXY_PROFILE}"
echo "  Session:    ${SESSION_ID}"
echo "  Proxy:      0.0.0.0:8080"
echo "  mitmweb:    http://localhost:8081"
echo

# Try to detect LAN IP (macOS).
lan_ip=""
if command -v ipconfig &>/dev/null; then
    lan_ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
fi
if [[ -n "$lan_ip" ]]; then
    echo "  LAN IP:    $lan_ip"
    echo
fi

echo "iPhone setup:"
echo "  1. Settings > Wi-Fi > [network] > Configure Proxy > Manual"
echo "     Server: ${lan_ip:-<your-lan-ip>}   Port: 8080"
echo "  2. Visit mitm.it in Safari to install the CA certificate"
echo "  3. Settings > General > VPN & Device Management > mitmproxy > Install"
echo "  4. Settings > General > About > Certificate Trust Settings > enable mitmproxy"
echo
echo "Devcontainer access:  http_proxy=http://host.docker.internal:8080"
