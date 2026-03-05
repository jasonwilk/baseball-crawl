#!/usr/bin/env bash
# Show host mitmproxy status.
set -euo pipefail
cd "$(dirname "$0")"
docker compose ps
echo
echo "Host port 8080 listeners:"
lsof -nP -iTCP:8080 -sTCP:LISTEN 2>/dev/null || echo "  No listeners on port 8080"
