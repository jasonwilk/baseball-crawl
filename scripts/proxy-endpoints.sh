#!/usr/bin/env bash
# Print a summary table of unique GameChanger API endpoints from the mitmproxy log.
# Reads data/mitmproxy/endpoint-log.jsonl (produced by endpoint_logger.py).
set -euo pipefail

LOG_FILE="data/mitmproxy/endpoint-log.jsonl"

if [ ! -f "$LOG_FILE" ]; then
    echo "No endpoints captured yet. Start the proxy and generate some traffic."
    echo
    echo "  ./scripts/proxy.sh start"
    echo "  Then browse GameChanger through the proxy."
    exit 0
fi

echo "Endpoint Discovery Summary"
echo

# Deduplicate by (method, path), count hits, show most recent status code.
# Sort alphabetically by method then path.
printf "%-7s %-60s %6s %6s\n" "METHOD" "PATH" "HITS" "STATUS"
printf "%-7s %-60s %6s %6s\n" "------" "----" "----" "------"

jq -r '[.method, .path, (.status_code | tostring)] | join("\t")' "$LOG_FILE" |
    awk -F'\t' '
    {
        key = $1 "\t" $2
        count[key]++
        status[key] = $3  # last seen status code (file order = chronological, so last = most recent)
    }
    END {
        for (key in count) {
            split(key, parts, "\t")
            printf "%-7s %-60s %6d %6s\n", parts[1], parts[2], count[key], status[key]
        }
    }
    ' | sort
