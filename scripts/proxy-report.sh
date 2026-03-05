#!/usr/bin/env bash
# Print a human-readable summary of the mitmproxy header parity report.
# Reads proxy/data/header-report.json (produced by header_capture.py).
set -euo pipefail

REPORT_FILE="proxy/data/header-report.json"

if [ ! -f "$REPORT_FILE" ]; then
    echo "No traffic captured yet. Start the proxy and generate some traffic."
    echo
    echo "  proxy/start.sh"
    echo "  Then browse GameChanger through the proxy."
    exit 0
fi

echo "Header Parity Report"
echo "Generated: $(jq -r '.generated_at' "$REPORT_FILE")"
echo

jq -r '
.sources[] |
"--- Source: \(.source) ---\n" +

(if (.missing_in_captured | length) > 0
 then "  Missing in captured (present in BROWSER_HEADERS):\n" +
      (.missing_in_captured | map("    - " + .) | join("\n")) + "\n"
 else "  Missing in captured: (none)\n" end) +

(if (.extra_in_captured | length) > 0
 then "  Extra in captured (not in BROWSER_HEADERS):\n" +
      (.extra_in_captured | map("    - " + .) | join("\n")) + "\n"
 else "  Extra in captured: (none)\n" end) +

(if (.value_differences | length) > 0
 then "  Value differences:\n" +
      (.value_differences | map("    - \(.key):\n        captured:  \(.captured)\n        canonical: \(.canonical)") | join("\n")) + "\n"
 else "  Value differences: (none)\n" end)
' "$REPORT_FILE"
