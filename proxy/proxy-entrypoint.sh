#!/usr/bin/env bash
# Wrapper entrypoint for mitmweb that conditionally enables upstream proxy mode.
#
# Runs as root (set via docker-compose.yml user: "0:0") to fix cert directory
# permissions, then drops to the mitmproxy user before exec'ing mitmweb.
#
# Reads MITMPROXY_PROFILE (default: mobile) and derives the proxy URL env var:
#   mobile  -> PROXY_URL_MOBILE
#   web     -> PROXY_URL_WEB
#
# When PROXY_ENABLED=true and the profile URL is set, starts mitmweb with
# --mode upstream:<url>. Otherwise starts in regular intercepting mode.
set -euo pipefail

# Fix cert directory permissions so certs persist across container recreations.
# The bind mount (./certs:/home/mitmproxy/.mitmproxy) may be owned by the host
# user (UID 501 on macOS). The mitmproxy user (UID 1000) needs write access.
cert_dir="/home/mitmproxy/.mitmproxy"
chown -R mitmproxy:mitmproxy "$cert_dir"

profile="${MITMPROXY_PROFILE:-mobile}"
proxy_var="PROXY_URL_${profile^^}"
proxy_url="${!proxy_var:-}"

base_args=(
    "--web-host" "0.0.0.0"
    "--scripts" "/app/proxy/addons/loader.py"
    "--set" "web_password=${MITMWEB_PASSWORD:-}"
)

# Drop privileges: exec mitmweb as the mitmproxy user.
# The stock Alpine-based mitmproxy image includes su-exec. Fall back to gosu or
# running as root if neither is available (acceptable for a local dev tool).
if command -v su-exec &>/dev/null; then
    run_as="su-exec mitmproxy"
elif command -v gosu &>/dev/null; then
    run_as="gosu mitmproxy"
else
    echo "WARNING: su-exec/gosu not found -- running mitmweb as root" >&2
    run_as=""
fi

proxy_enabled=$(echo "${PROXY_ENABLED:-}" | tr '[:upper:]' '[:lower:]' | xargs)
if [[ "$proxy_enabled" == "true" ]]; then
    if [[ -n "$proxy_url" ]]; then
        # mitmproxy doesn't support embedded credentials in upstream URLs.
        # Split http://user:pass@host:port into --mode upstream:http://host:port
        # and --upstream-auth user:pass.
        upstream_host=$(echo "$proxy_url" | sed 's|://[^@]*@|://|')
        upstream_auth=$(echo "$proxy_url" | sed -n 's|.*://\([^@]*\)@.*|\1|p')
        upstream_args=("--mode" "upstream:${upstream_host}" "--ssl-insecure")
        if [[ -n "$upstream_auth" ]]; then
            upstream_args+=("--upstream-auth" "$upstream_auth")
        fi
        exec $run_as mitmweb "${base_args[@]}" "${upstream_args[@]}"
    else
        echo "WARNING: PROXY_ENABLED is true but ${proxy_var} is not set -- starting without upstream mode" >&2
        exec $run_as mitmweb "${base_args[@]}"
    fi
else
    exec $run_as mitmweb "${base_args[@]}"
fi
