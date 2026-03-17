#!/usr/bin/env bash
# Bulk endpoint collector -- grabs raw payloads while credentials are fresh.
# Usage: ./scripts/collect-endpoints.sh
# Reads gc-token and gc-device-id from secrets/gamechanger-curl.txt

set -euo pipefail

OUTDIR="data/raw/bulk-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTDIR"

# Extract credentials from the curl file
CURL_FILE="secrets/gamechanger-curl.txt"
GC_TOKEN=$(grep -oP "gc-token: \K[^'\"]*" "$CURL_FILE" | head -1 || true)
GC_DEVICE_ID=$(grep -oP "gc-device-id: \K[^'\"]*" "$CURL_FILE" | head -1 || true)

if [[ -z "$GC_TOKEN" || -z "$GC_DEVICE_ID" ]]; then
  echo "ERROR: Could not extract gc-token or gc-device-id from $CURL_FILE"
  exit 1
fi

echo "Credentials loaded. Output dir: $OUTDIR"

BASE="https://api.team-manager.gc.com"

# Load entity UUIDs from environment variables (or .env file).
# These resolve to real GameChanger entities and must not be hardcoded.
if [[ -f .env ]]; then
  # Source .env for any vars not already set in the environment
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

TEAM="${GC_TEAM_UUID:?ERROR: GC_TEAM_UUID not set. Export it or add to .env}"
ORG="${GC_ORG_UUID:?ERROR: GC_ORG_UUID not set. Export it or add to .env}"
EVENT="${GC_EVENT_UUID:?ERROR: GC_EVENT_UUID not set. Export it or add to .env}"
STREAM="${GC_STREAM_UUID:?ERROR: GC_STREAM_UUID not set. Export it or add to .env}"

# Common headers matching the web browser profile from the curl capture
do_get() {
  local url="$1"
  local outfile="$2"
  local accept="${3:-application/json, text/plain, */*}"

  echo -n "  GET $url -> $outfile ... "
  local http_code
  http_code=$(curl -s -o "$OUTDIR/$outfile" -w "%{http_code}" \
    "$url" \
    -H "accept: $accept" \
    -H 'accept-language: en-US,en;q=0.9' \
    -H 'cache-control: no-cache' \
    -H 'dnt: 1' \
    -H 'gc-app-name: web' \
    -H "gc-device-id: $GC_DEVICE_ID" \
    -H "gc-token: $GC_TOKEN" \
    -H 'origin: https://web.gc.com' \
    -H 'pragma: no-cache' \
    -H 'priority: u=1, i' \
    -H 'referer: https://web.gc.com/' \
    -H 'sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"' \
    -H 'sec-ch-ua-mobile: ?0' \
    -H 'sec-ch-ua-platform: "macOS"' \
    -H 'sec-fetch-dest: empty' \
    -H 'sec-fetch-mode: cors' \
    -H 'sec-fetch-site: same-site' \
    -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')
  echo "$http_code ($(wc -c < "$OUTDIR/$outfile" | tr -d ' ') bytes)"
  sleep 1.5
}

echo ""
echo "=== /me endpoints ==="
do_get "$BASE/me/user" "me-user.json"
do_get "$BASE/me/teams-summary" "me-teams-summary.json"
do_get "$BASE/me/associated-players" "me-associated-players.json"
do_get "$BASE/me/archived-teams" "me-archived-teams.json"
do_get "$BASE/me/related-organizations" "me-related-organizations.json"
do_get "$BASE/me/widgets" "me-widgets.json"
do_get "$BASE/me/schedule" "me-schedule.json"

echo ""
echo "=== /organizations endpoints ==="
do_get "$BASE/organizations/$ORG/teams" "org-teams.json"
do_get "$BASE/organizations/$ORG/events" "org-events.json"
do_get "$BASE/organizations/$ORG/game-summaries" "org-game-summaries.json"
do_get "$BASE/organizations/$ORG/standings" "org-standings.json"
do_get "$BASE/organizations/$ORG/opponents" "org-opponents.json"
do_get "$BASE/organizations/$ORG/opponent-players" "org-opponent-players.json"
do_get "$BASE/organizations/$ORG/team-records" "org-team-records.json"
do_get "$BASE/organizations/$ORG/users" "org-users.json"
do_get "$BASE/organizations/$ORG/scoped-features" "org-scoped-features.json"

echo ""
echo "=== /teams endpoints ==="
do_get "$BASE/teams/$TEAM" "team.json"
do_get "$BASE/teams/$TEAM/players" "team-players.json"
do_get "$BASE/teams/$TEAM/users" "team-users.json"
do_get "$BASE/teams/$TEAM/schedule" "team-schedule.json"
do_get "$BASE/teams/$TEAM/game-summaries" "team-game-summaries.json"
do_get "$BASE/teams/$TEAM/opponents" "team-opponents.json"
do_get "$BASE/teams/$TEAM/opponents/players" "team-opponents-players.json"
do_get "$BASE/teams/$TEAM/associations" "team-associations.json"
do_get "$BASE/teams/$TEAM/relationships" "team-relationships.json"
do_get "$BASE/teams/$TEAM/external-associations" "team-external-associations.json"
do_get "$BASE/teams/$TEAM/scoped-features" "team-scoped-features.json"
do_get "$BASE/teams/$TEAM/team-notification-setting" "team-notification-setting.json"

echo ""
echo "=== /teams/schedule/events (per-game) ==="
do_get "$BASE/teams/$TEAM/schedule/events/$EVENT/player-stats" "event-player-stats.json"
do_get "$BASE/teams/$TEAM/schedule/events/$EVENT/rsvp-responses" "event-rsvp-responses.json"
do_get "$BASE/teams/$TEAM/schedule/events/$EVENT/video-stream/live-status" "event-video-live-status.json"
do_get "$BASE/teams/$TEAM/schedule/events/$EVENT/video-stream" "event-video-stream.json"
do_get "$BASE/teams/$TEAM/schedule/events/$EVENT/video-stream/assets?includeProcessing=true" "event-video-assets.json"

echo ""
echo "=== /game-streams endpoints ==="
do_get "$BASE/game-streams/gamestream-recap-story/$EVENT?game_stream_id=$STREAM&team_id=$TEAM" "gamestream-recap-story.json"
do_get "$BASE/game-streams/gamestream-viewer-payload-lite/$EVENT?stream_id=$STREAM" "gamestream-viewer-payload-lite.json"
do_get "$BASE/game-streams/$STREAM/events?initial=true" "gamestream-events.json"

echo ""
echo "=== /events endpoints ==="
do_get "$BASE/events/$EVENT/highlight-reel" "event-highlight-reel.json"

echo ""
echo "=== Done ==="
echo "Collected $(ls "$OUTDIR" | wc -l) payloads in $OUTDIR"
echo ""
echo "Files:"
ls -lhS "$OUTDIR"
