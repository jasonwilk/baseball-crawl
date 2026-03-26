"""Render spray chart images replicating GameChanger's client-side SVG rendering.

Reverse-engineered from GC's gamechanger-sabertooth JS bundle:
  - SVG viewBox: 0 0 320 480
  - Coordinate transform: raw API coords -> SVG space via two-anchor linear map
  - Binary hit/out classification (with optional enhanced per-result-type colors)
  - Hardcoded SVG field geometry converted to matplotlib Path objects

Usage:
    python3 .project/research/spray-chart-spike/render.py
    python3 .project/research/spray-chart-spike/render.py --enhanced

Reads output/spray_events.json (produced by fetch.py)
Writes PNG images to output/
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path as MplPath

OUT_DIR = Path(__file__).parent / "output"
SPRAY_FILE = OUT_DIR / "spray_events.json"

# ---------------------------------------------------------------------------
# Coordinate transform (extracted verbatim from GC JS bundle)
# Two anchor points map raw API coords to SVG space (320x480, y=0 at top/CF)
# ---------------------------------------------------------------------------
_NU  = (160 - 211.25) / (160 - 234)   # x scale = 0.6926...
_DU  = (295 - 246)    / (296 - 220)   # y scale = 0.6447...
_KUe = 160 - 160 * _NU                # x offset = 49.189...
_YUe = 295 - 296 * _DU                # y offset = 104.158...


def raw_to_svg(x: float, y: float) -> tuple[float, float]:
    """Map raw API location coords to GC SVG space (320x480)."""
    return _KUe + x * _NU, _YUe + y * _DU


# ---------------------------------------------------------------------------
# Hit/out classification (GC's zre() function)
# ---------------------------------------------------------------------------
HIT_RESULTS = {"single", "double", "triple", "home_run", "dropped_third_strike"}

def classify(play_result: str | None) -> str:
    return "hit" if play_result in HIT_RESULTS else "out"


# ---------------------------------------------------------------------------
# GC color scheme (exact hex values from bundle)
# ---------------------------------------------------------------------------
GC_HIT_FILL    = "#00D682"
GC_HIT_STROKE  = "#009B4D"
GC_OUT_FILL    = "#B90018"
GC_OUT_STROKE  = "#61000D"
FIELD_LINE     = "#667C8C"
BASE_FILL      = "#9DB2C4"
BG_COLOR       = "#FFFFFF"   # GC uses transparent/white page background

# Enhanced mode: distinct colors per result type
ENHANCED_COLORS = {
    "single":                       ("#4FC3F7", "#0288D1"),   # light blue
    "double":                       ("#81C784", "#388E3C"),   # green
    "triple":                       ("#FFB74D", "#F57C00"),   # orange
    "home_run":                     ("#EF5350", "#B71C1C"),   # red
    "dropped_third_strike":         ("#CE93D8", "#7B1FA2"),   # purple
    "batter_out":                   ("#B90018", "#61000D"),   # GC out red
    "batter_out_advance_runners":   ("#C62828", "#7F0000"),   # dark red
    "fielders_choice":              ("#8D6E63", "#4E342E"),   # brown
    "error":                        ("#9C27B0", "#4A148C"),   # purple
    "sac_fly":                      ("#78909C", "#37474F"),   # blue-grey
}
ENHANCED_LABELS = {
    "single": "1B", "double": "2B", "triple": "3B", "home_run": "HR",
    "batter_out": "Out", "batter_out_advance_runners": "Out (adv)",
    "fielders_choice": "FC", "error": "Error", "sac_fly": "SF",
    "dropped_third_strike": "K (drop)",
}


# ---------------------------------------------------------------------------
# SVG field geometry (verbatim path data from GC bundle)
# Converted to matplotlib Path objects.
# SVG coords: y=0 at top (CF), y=480 at bottom. We plot in SVG space directly
# and invert the y-axis so home plate appears at bottom (as GC renders it).
# ---------------------------------------------------------------------------

def _svg_path(d: str) -> MplPath:
    """Parse a subset of SVG path data (M, L, C, Z) into a matplotlib Path."""
    import re
    # Proper SVG tokenizer: command letters and numbers are separate tokens
    tokens = re.findall(r'[MmCcLlZz]|[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', d)
    verts, codes = [], []
    i = 0
    cur = (0.0, 0.0)
    while i < len(tokens):
        cmd = tokens[i]; i += 1
        if cmd == 'M':
            x, y = float(tokens[i]), float(tokens[i+1]); i += 2
            verts.append((x, y)); codes.append(MplPath.MOVETO); cur = (x, y)
        elif cmd == 'L':
            x, y = float(tokens[i]), float(tokens[i+1]); i += 2
            verts.append((x, y)); codes.append(MplPath.LINETO); cur = (x, y)
        elif cmd == 'C':
            # Cubic bezier: consume coordinate triples until next command letter
            while i < len(tokens) and tokens[i] not in 'MmCcLlZz':
                x1,y1 = float(tokens[i]),float(tokens[i+1]); i+=2
                x2,y2 = float(tokens[i]),float(tokens[i+1]); i+=2
                x, y  = float(tokens[i]),float(tokens[i+1]); i+=2
                verts += [(x1,y1),(x2,y2),(x,y)]
                codes += [MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
                cur = (x, y)
        elif cmd == 'Z':
            verts.append(cur); codes.append(MplPath.CLOSEPOLY)
    return MplPath(verts, codes)


# Main field boundary (outfield arc + foul lines + home plate area)
_FIELD_PATH_D = (
    "M237.609577,229.299862 "
    "C228.432604,194.989366 197.163117,169.724719 160,169.724719 "
    "C122.803685,169.724719 91.5115345,195.034524 82.3658827,229.391832 "
    "C82.3652227,229.394311 55.2432618,202.321081 1,148.172141 "
    "C27.3762229,86.5315996 88.6341713,43 159.999502,43 "
    "C231.365829,43 292.622781,86.5315996 319,148.172141 "
    "L182.03012,284.895924 "
    "C183.325172,287.8707 184.40625,290.533196 184.40625,293.984533 "
    "C184.40625,307.446637 173.479,318.359787 159.999502,318.359787 "
    "C146.520004,318.359787 135.592754,307.446637 135.592754,293.984533 "
    "C135.592754,290.533196 136.675824,287.8707 137.96988,284.895924 "
    "L82.3714674,229.397407"
)

# Base polygon point strings -> list of (x,y) tuples
def _poly(pts: str) -> list[tuple]:
    nums = [float(v) for v in pts.split()]
    return [(nums[i], nums[i+1]) for i in range(0, len(nums), 2)]

_HOME_PTS = _poly("155.367018 291.902403 155.367018 296.46134 159.897659 301.020277 164.428299 296.46134 164.478766 291.902403")
_3B_PTS   = _poly("112.383633 246.011583 108.738565 249.658733 105.094234 246.011583 108.738565 242.364434")
_2B_PTS   = _poly("163.642157 194.690046 159.99709  198.337195 156.352759 194.690046 159.99709  191.042896")
_1B_PTS   = _poly("214.900682 246.011583 211.256351 249.658733 207.611283 246.011583 211.256351 242.364434")

# HR bubble fixed SVG positions
HR_POSITIONS = {"left": (30, 70), "center": (160, 25), "right": (290, 70)}


def draw_field(ax: plt.Axes) -> None:
    """Draw the GC field geometry onto an SVG-space axes (320x480, y inverted)."""
    lw = 0.75

    # Field boundary path
    try:
        field_path = _svg_path(_FIELD_PATH_D)
        patch = PathPatch(field_path, facecolor="none",
                          edgecolor=FIELD_LINE, linewidth=lw, zorder=2)
        ax.add_patch(patch)
    except Exception:
        pass  # Don't crash if path parsing fails

    # Base diamonds
    for pts in [_HOME_PTS, _3B_PTS, _2B_PTS, _1B_PTS]:
        poly = Polygon(pts, closed=True, facecolor=BASE_FILL,
                       edgecolor=FIELD_LINE, linewidth=0.5, zorder=3)
        ax.add_patch(poly)


def draw_hr_bubbles(ax: plt.Axes, events: list[dict]) -> None:
    """Count and draw HR zone bubbles (left/center/right field)."""
    hr_counts: dict[str, int] = {"left": 0, "center": 0, "right": 0}
    for ev in events:
        if ev.get("play_result") == "home_run":
            loc = ev.get("hr_location") or "center"
            zone = "center"
            if "left" in loc:   zone = "left"
            elif "right" in loc: zone = "right"
            hr_counts[zone] += 1

    for zone, count in hr_counts.items():
        if count == 0:
            continue
        x, y = HR_POSITIONS[zone]
        circle = plt.Circle((x, y), 12, color=GC_HIT_FILL,
                             ec=GC_HIT_STROKE, lw=1.14, zorder=5)
        ax.add_patch(circle)
        ax.text(x, y + 1, str(count), ha="center", va="center",
                fontsize=8, fontweight="bold", color="white", zorder=6)


def make_figure() -> tuple[plt.Figure, plt.Axes]:
    """Create a figure sized to match GC's 320x480 SVG proportion."""
    fig, ax = plt.subplots(figsize=(4, 6))  # 2:3 ratio = 320:480
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 320)
    ax.set_ylim(480, 0)   # Invert: SVG y=0 is top (CF), y=480 is bottom
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


# ---------------------------------------------------------------------------
# Chart renderers
# ---------------------------------------------------------------------------

def draw_spray_chart(
    events: list[dict],
    title: str,
    filename: str,
    enhanced: bool = False,
) -> None:
    if not events:
        print(f"  Skipping {filename} (no events)")
        return

    fig, ax = make_figure()
    draw_field(ax)

    # Separate outs and hits so hits render on top (GC render order)
    outs = [e for e in events if classify(e.get("play_result")) == "out"]
    hits = [e for e in events if classify(e.get("play_result")) == "hit"]
    hr_on_field = [e for e in events
                   if e.get("play_result") == "home_run"
                   and e.get("hr_location") in (None, "in_the_park", "")]

    for ev_list in [outs, hits]:
        for ev in ev_list:
            sx, sy = raw_to_svg(ev["x"], ev["y"])
            result = ev.get("play_result") or "batter_out"

            if enhanced:
                fill, stroke = ENHANCED_COLORS.get(result, (GC_OUT_FILL, GC_OUT_STROKE))
            else:
                if classify(result) == "hit":
                    fill, stroke = GC_HIT_FILL, GC_HIT_STROKE
                else:
                    fill, stroke = GC_OUT_FILL, GC_OUT_STROKE

            circle = plt.Circle((sx, sy), 4, color=fill, ec=stroke, lw=1.14, zorder=4)
            ax.add_patch(circle)

    # HR bubbles (non-in-the-park HRs counted by zone)
    draw_hr_bubbles(ax, events)

    # Title
    ax.set_title(title, fontsize=9, pad=4, color="#333")

    # Legend
    if enhanced:
        seen = {e.get("play_result") for e in events}
        patches = [
            mpatches.Patch(color=ENHANCED_COLORS.get(r, (GC_OUT_FILL,))[0],
                           label=ENHANCED_LABELS.get(r, r or "?"))
            for r in ENHANCED_COLORS if r in seen
        ]
        if patches:
            ax.legend(handles=patches, loc="lower right",
                      fontsize=6, framealpha=0.8,
                      bbox_to_anchor=(1.0, 0.0))
    else:
        patches = [
            mpatches.Patch(color=GC_HIT_FILL, label="Hit"),
            mpatches.Patch(color=GC_OUT_FILL, label="Out"),
        ]
        ax.legend(handles=patches, loc="lower right", fontsize=7, framealpha=0.8)

    out_path = OUT_DIR / filename
    fig.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path.name}  ({len(events)} events)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enhanced", action="store_true",
                        help="Use per-result-type colors instead of binary hit/out")
    args = parser.parse_args()

    if not SPRAY_FILE.exists():
        print(f"ERROR: {SPRAY_FILE} not found. Run fetch.py first.")
        return

    events = json.loads(SPRAY_FILE.read_text())
    mode = "enhanced" if args.enhanced else "gc-faithful"
    print(f"Loaded {len(events)} spray events  [mode: {mode}]\n")

    if not events:
        print("No events to render.")
        return

    prefix = "enh_" if args.enhanced else "gc_"

    print("Generating charts...")

    # Team chart
    draw_spray_chart(
        events,
        title=f"Freshman Grizzlies — All ({len(events)} BIP)",
        filename=f"{prefix}team_spray.png",
        enhanced=args.enhanced,
    )

    # Per-player charts
    by_player: dict[str, list] = defaultdict(list)
    for ev in events:
        by_player[ev["player_uuid"]].append(ev)

    count = 0
    for uuid, player_events in sorted(by_player.items(), key=lambda kv: -len(kv[1])):
        if len(player_events) < 3:
            continue
        draw_spray_chart(
            player_events,
            title=f"Player {uuid[:8]}…  ({len(player_events)} BIP)",
            filename=f"{prefix}player_{uuid[:8]}.png",
            enhanced=args.enhanced,
        )
        count += 1

    print(f"\nDone. Team chart + {count} player charts saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
