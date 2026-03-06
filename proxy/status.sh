#!/usr/bin/env bash
# Show host mitmproxy status, including upstream proxy mode and active profile.
set -euo pipefail
cd "$(dirname "$0")"

docker compose ps
echo

echo "Host port 8080 listeners:"
lsof -nP -iTCP:8080 -sTCP:LISTEN 2>/dev/null || echo "  No listeners on port 8080"
echo

# Inspect the running container for upstream proxy status and profile.
container_id=$(docker compose ps -q mitmproxy 2>/dev/null || true)
if [[ -z "$container_id" ]]; then
    echo "Upstream proxy: container not running"
    exit 0
fi

# Check whether mitmweb was started with --mode upstream in its command args.
cmd_args=$(docker inspect --format '{{range .Args}}{{.}} {{end}}' "$container_id" 2>/dev/null || true)

# Determine active profile from container env.
profile=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container_id" 2>/dev/null \
    | grep '^MITMPROXY_PROFILE=' | cut -d= -f2 || true)
profile="${profile:-mobile}"

case "$profile" in
    mobile)
        zone_label="mobile zone"
        ;;
    web)
        zone_label="web/residential zone"
        ;;
    *)
        zone_label="${profile} zone"
        ;;
esac

if echo "$cmd_args" | grep -q -- '--mode upstream'; then
    echo "Upstream proxy: enabled (${zone_label})"
else
    echo "Upstream proxy: disabled"
fi
echo "Profile: ${profile}"
