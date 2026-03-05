#!/usr/bin/env bash
# Follow mitmproxy logs.
set -euo pipefail
cd "$(dirname "$0")"
docker compose logs -f mitmproxy
