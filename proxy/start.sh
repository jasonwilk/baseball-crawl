#!/usr/bin/env bash
# Start mitmproxy on the Mac host for iPhone traffic capture.
#
# Run from the proxy/ directory or from the project root:
#   ./proxy/start.sh
#
# Ports:
#   8080 - proxy listener (all interfaces, iPhone can reach it)
#   8081 - mitmweb UI (localhost only)
#
# Certs are stored in proxy/certs/ so the iPhone trust persists across restarts.
set -euo pipefail

cd "$(dirname "$0")"

# Create certs dir if it doesn't exist.
mkdir -p certs

docker compose up -d

echo
echo "mitmproxy is running on the host."
echo
echo "  Proxy:     0.0.0.0:8080"
echo "  mitmweb:   http://localhost:8081"
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
