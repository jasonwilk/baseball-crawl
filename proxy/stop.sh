#!/usr/bin/env bash
# Stop the host mitmproxy.
set -euo pipefail
cd "$(dirname "$0")"
docker compose down
echo "mitmproxy stopped."
