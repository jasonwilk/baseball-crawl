#!/usr/bin/env bash
# Operator CLI for mitmproxy proxy management.
# Subcommands: start, stop, status.
set -euo pipefail

usage() {
    echo "Usage: $0 {start|stop|status}"
    echo
    echo "  start   Start mitmproxy alongside the app stack"
    echo "  stop    Stop mitmproxy only (app stack keeps running)"
    echo "  status  Show mitmproxy service status and port bindings"
    exit 1
}

get_lan_ip() {
    # Inside a devcontainer, hostname -I returns the container IP, not the host LAN IP.
    # Print a placeholder -- the operator must check their host's IP manually.
    echo "<your-host-lan-ip>"
}

cmd_start() {
    docker compose --profile proxy up -d

    local lan_ip
    lan_ip=$(get_lan_ip)

    echo
    echo "mitmproxy is running."
    echo
    echo "  Proxy address:  ${lan_ip}:8080"
    echo "  mitmweb UI:     http://localhost:8081"
    echo
    echo "  Find your host LAN IP: run 'ipconfig' (Windows) or"
    echo "  'ipconfig getifaddr en0' (macOS) on the HOST, not in the container."
    echo
    echo "iPhone setup:"
    echo "  1. Settings > Wi-Fi > [network] > Configure Proxy > Manual"
    echo "     Server: ${lan_ip}   Port: 8080"
    echo "  2. Visit mitm.it in Safari to install the CA certificate"
    echo "  3. Settings > General > VPN & Device Management > mitmproxy > Install"
    echo "  4. Settings > General > About > Certificate Trust Settings > enable mitmproxy"
}

cmd_stop() {
    docker compose stop mitmproxy
    echo "mitmproxy stopped. App stack is still running."
}

cmd_status() {
    docker compose ps mitmproxy
}

case "${1:-}" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    *)      usage ;;
esac
