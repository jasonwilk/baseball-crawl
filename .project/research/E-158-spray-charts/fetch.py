"""Fetch spray chart data from GameChanger API for the Freshman Grizzlies.

Usage:
    python3 .project/research/spray-chart-spike/fetch.py

Writes raw JSON responses to .project/research/spray-chart-spike/output/
One file per game: raw_<event_id_short>.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Bootstrap src imports
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.gamechanger.client import GameChangerClient

# Freshman Grizzlies - our only member team with played games
TEAM_GC_UUID = "ec2827f3-9eb5-4473-b39a-be4a9e4d656e"

# Played games: (event_id, opponent_team_id, date)
GAMES = [
    ("374ca73f-342c-4f24-a5ca-af155e09e9d9", "2026-03-25"),
    ("757c024c-de8d-4b44-b159-7704a6ff0640", "2026-03-21"),
    ("155bc5ef-3347-4b23-b4ed-4ea8f1e3e9c7", "2026-03-20"),
    ("91d00308-a64a-4738-bb7a-7f5be266e1c1", "2026-03-19"),
]

OUT_DIR = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

# Unusual Accept header -- this endpoint does NOT use a vendor-typed Accept header
ACCEPT = "application/json, text/plain, */*"


def fetch_game(client: GameChangerClient, event_id: str, date: str) -> dict:
    path = f"/teams/{TEAM_GC_UUID}/schedule/events/{event_id}/player-stats"
    print(f"  Fetching {date} ({event_id[:8]}...)  ", end="", flush=True)
    data = client.get(path, accept=ACCEPT)
    out_path = OUT_DIR / f"raw_{event_id[:8]}_{date}.json"
    out_path.write_text(json.dumps(data, indent=2))
    print(f"-> saved {out_path.name}")
    return data


def main() -> None:
    print("Initializing GameChanger client...")
    client = GameChangerClient()

    all_spray: list[dict] = []

    for event_id, date in GAMES:
        try:
            data = fetch_game(client, event_id, date)
        except Exception as exc:
            print(f"ERROR: {exc}")
            continue

        # Extract spray events from this game
        spray = data.get("spray_chart_data", {})
        offense = spray.get("offense", {})
        for player_uuid, events in offense.items():
            for ev in events:
                attrs = ev.get("attributes", {})
                for defender in attrs.get("defenders", []):
                    loc = defender.get("location", {})
                    if loc.get("x") is not None and loc.get("y") is not None:
                        all_spray.append({
                            "game_date": date,
                            "player_uuid": player_uuid,
                            "play_result": attrs.get("playResult"),
                            "play_type": attrs.get("playType"),
                            "fielder_position": defender.get("position"),
                            "error": defender.get("error", False),
                            "x": loc["x"],
                            "y": loc["y"],
                        })

    # Save combined spray data
    combined_path = OUT_DIR / "spray_events.json"
    combined_path.write_text(json.dumps(all_spray, indent=2))
    print(f"\nTotal spray events: {len(all_spray)}")

    # Print coordinate range so we can understand the scale
    if all_spray:
        xs = [e["x"] for e in all_spray]
        ys = [e["y"] for e in all_spray]
        print(f"x range: {min(xs):.1f} to {max(xs):.1f}  (mean={sum(xs)/len(xs):.1f})")
        print(f"y range: {min(ys):.1f} to {max(ys):.1f}  (mean={sum(ys)/len(ys):.1f})")

        print("\nPlay result breakdown:")
        from collections import Counter
        for result, count in Counter(e["play_result"] for e in all_spray).most_common():
            print(f"  {result}: {count}")

        print("\nPlay type breakdown:")
        for ptype, count in Counter(e["play_type"] for e in all_spray).most_common():
            print(f"  {ptype}: {count}")

    print(f"\nRaw files in: {OUT_DIR}")


if __name__ == "__main__":
    main()
