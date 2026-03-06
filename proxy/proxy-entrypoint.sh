#!/usr/bin/env bash
# Wrapper entrypoint for mitmweb that conditionally enables upstream proxy mode.
#
# Reads MITMPROXY_PROFILE (default: mobile) and derives the proxy URL env var:
#   mobile  -> PROXY_URL_MOBILE
#   web     -> PROXY_URL_WEB
#
# When PROXY_ENABLED=true and the profile URL is set, starts mitmweb with
# --mode upstream:<url>. Otherwise starts in regular intercepting mode.
set -euo pipefail

profile="${MITMPROXY_PROFILE:-mobile}"
proxy_var="PROXY_URL_${profile^^}"
proxy_url="${!proxy_var:-}"

base_args=(
    "--web-host" "0.0.0.0"
    "--scripts" "/app/proxy/addons/loader.py"
    "--set" "web_password=${MITMWEB_PASSWORD:-}"
)

proxy_enabled=$(echo "${PROXY_ENABLED:-}" | tr '[:upper:]' '[:lower:]' | xargs)
if [[ "$proxy_enabled" == "true" ]]; then
    if [[ -n "$proxy_url" ]]; then
        exec mitmweb "${base_args[@]}" --mode "upstream:${proxy_url}"
    else
        echo "WARNING: PROXY_ENABLED is true but ${proxy_var} is not set -- starting without upstream mode" >&2
        exec mitmweb "${base_args[@]}"
    fi
else
    exec mitmweb "${base_args[@]}"
fi
