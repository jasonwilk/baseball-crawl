"""Spray chart rendering module for the baseball-crawl dashboard.

Generates a PNG spray chart image from a list of ball-in-play events,
replicating GameChanger's exact field geometry, coordinate transforms,
and binary hit/out color scheme with play-type marker differentiation.

The rendering logic (coordinate transform, field geometry paths, hit/out
classification, HR zone bubbles) is ported from the spike at
``.project/research/E-158-spray-charts/render.py``, which was
reverse-engineered from GC's gamechanger-sabertooth JS bundle.

Public API::

    from src.charts.spray import render_spray_chart

    png_bytes = render_spray_chart(events, title="Varsity — All BIP")

Each event dict must contain at minimum:

- ``x`` (float | None): raw API x coordinate
- ``y`` (float | None): raw API y coordinate
- ``play_result`` (str): e.g. ``"single"``, ``"batter_out"``, ``"home_run"``
- ``play_type`` (str | None): e.g. ``"ground_ball"``, ``"line_drive"``, ``"fly_ball"``
"""

from __future__ import annotations

import io
import logging
import math
import re

import matplotlib

matplotlib.use("Agg")  # headless rendering -- must precede pyplot import

import matplotlib.lines as mlines  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch, Polygon  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Coordinate transform (extracted verbatim from GC JS bundle)
# Two anchor points map raw API coords to SVG space (320x480, y=0 at top/CF)
# ---------------------------------------------------------------------------
_NU = (160 - 211.25) / (160 - 234)  # x scale ≈ 0.6926
_DU = (295 - 246) / (296 - 220)     # y scale ≈ 0.6447
_KUe = 160 - 160 * _NU              # x offset ≈ 49.189
_YUe = 295 - 296 * _DU              # y offset ≈ 104.158


def _raw_to_svg(x: float, y: float) -> tuple[float, float]:
    """Map raw API location coords to GC SVG space (320×480)."""
    return _KUe + x * _NU, _YUe + y * _DU


# ---------------------------------------------------------------------------
# Hit/out classification (GC's zre() function)
# ---------------------------------------------------------------------------
_HIT_RESULTS: frozenset[str] = frozenset(
    {"single", "double", "triple", "home_run", "dropped_third_strike"}
)


def _classify(play_result: str | None) -> str:
    """Return ``'hit'`` or ``'out'`` for a play result string."""
    return "hit" if play_result in _HIT_RESULTS else "out"


# ---------------------------------------------------------------------------
# GC color scheme (exact hex values from bundle)
# ---------------------------------------------------------------------------
_HIT_FILL = "#00D682"
_HIT_STROKE = "#009B4D"
_OUT_FILL = "#B90018"
_OUT_STROKE = "#61000D"
_FIELD_LINE = "#667C8C"
_BASE_FILL = "#9DB2C4"
_BG_COLOR = "#FFFFFF"
_LEGEND_GRAY = "#888888"

# ---------------------------------------------------------------------------
# Play type → marker shape mapping (TN-1)
# ---------------------------------------------------------------------------
_PLAY_TYPE_MARKERS: dict[str, str] = {
    "ground_ball": "o",
    "hard_ground_ball": "o",
    "bunt": "v",
    "line_drive": "^",
    "hard_line_drive": "^",
    "fly_ball": "D",
    "popup": "s",
    "pop_fly": "s",
    "pop_up": "s",
}
_FALLBACK_MARKER = "o"


def _marker_for_play_type(play_type: str | None) -> str:
    """Return the matplotlib marker code for a play_type value."""
    if play_type is None:
        return _FALLBACK_MARKER
    return _PLAY_TYPE_MARKERS.get(play_type, _FALLBACK_MARKER)


# ---------------------------------------------------------------------------
# Baseball stat formatting (TN-3)
# ---------------------------------------------------------------------------


def format_baseball_stat(numerator: float, denominator: float) -> str:
    """Format a rate stat using baseball convention.

    ``.342`` for values < 1.0, ``1.000`` for values >= 1.0.
    Returns ``"-"`` when denominator is zero.
    """
    if not denominator:
        return "-"
    val = numerator / denominator
    if val >= 1.0:
        return f"{val:.3f}"
    rounded = round(val * 1000)
    if rounded >= 1000:
        return f"{val:.3f}"
    return f".{rounded:03d}"


# ---------------------------------------------------------------------------
# Field zone classification (TN-4)
# ---------------------------------------------------------------------------
# Home plate in SVG space
_HOME_X = 160
_HOME_Y = 295

# Equal angular thirds of fair territory (~11.8°)
ZONE_ANGLE_THRESHOLD = 0.206


def classify_field_zone(x: float, y: float) -> str:
    """Classify a ball-in-play into Left/Center/Right field zone.

    Coordinates are raw API values, transformed to SVG space internally.
    Returns ``"left"``, ``"center"``, or ``"right"``.
    """
    svg_x, svg_y = _raw_to_svg(x, y)
    dx = svg_x - _HOME_X
    dy = svg_y - _HOME_Y
    angle = math.atan2(dx, -dy)
    if angle < -ZONE_ANGLE_THRESHOLD:
        return "left"
    elif angle > ZONE_ANGLE_THRESHOLD:
        return "right"
    return "center"


# ---------------------------------------------------------------------------
# Contact type classification (TN-5)
# ---------------------------------------------------------------------------
_CONTACT_TYPE_MAP: dict[str, str] = {
    "ground_ball": "gb",
    "hard_ground_ball": "gb",
    "line_drive": "ld",
    "hard_line_drive": "ld",
    "fly_ball": "fb",
    "popup": "pu",
    "pop_fly": "pu",
    "pop_up": "pu",
    "bunt": "bu",
}


def contact_type_label(play_type: str | None) -> str | None:
    """Map a play_type API value to a contact type category.

    Returns one of ``"gb"``, ``"ld"``, ``"fb"``, ``"pu"``, ``"bu"``,
    or ``None`` if the play_type is unmapped or None.
    """
    if play_type is None:
        return None
    return _CONTACT_TYPE_MAP.get(play_type)


# ---------------------------------------------------------------------------
# SVG field geometry (verbatim path data from GC bundle)
# ---------------------------------------------------------------------------

def _svg_path(d: str) -> MplPath:
    """Parse a subset of SVG path data (M, L, C, Z) into a matplotlib Path."""
    tokens = re.findall(
        r'[MmCcLlZz]|[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', d
    )
    verts: list[tuple[float, float]] = []
    codes: list[int] = []
    i = 0
    cur = (0.0, 0.0)
    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd == "M":
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            verts.append((x, y))
            codes.append(MplPath.MOVETO)
            cur = (x, y)
        elif cmd == "L":
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            verts.append((x, y))
            codes.append(MplPath.LINETO)
            cur = (x, y)
        elif cmd == "C":
            while i < len(tokens) and tokens[i] not in "MmCcLlZz":
                x1, y1 = float(tokens[i]), float(tokens[i + 1])
                i += 2
                x2, y2 = float(tokens[i]), float(tokens[i + 1])
                i += 2
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                verts += [(x1, y1), (x2, y2), (x, y)]
                codes += [MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
                cur = (x, y)
        elif cmd == "Z":
            verts.append(cur)
            codes.append(MplPath.CLOSEPOLY)
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


def _poly(pts: str) -> list[tuple[float, float]]:
    nums = [float(v) for v in pts.split()]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]


_HOME_PTS = _poly(
    "155.367018 291.902403 155.367018 296.46134 "
    "159.897659 301.020277 164.428299 296.46134 164.478766 291.902403"
)
_3B_PTS = _poly(
    "112.383633 246.011583 108.738565 249.658733 "
    "105.094234 246.011583 108.738565 242.364434"
)
_2B_PTS = _poly(
    "163.642157 194.690046 159.99709 198.337195 "
    "156.352759 194.690046 159.99709 191.042896"
)
_1B_PTS = _poly(
    "214.900682 246.011583 211.256351 249.658733 "
    "207.611283 246.011583 211.256351 242.364434"
)

# HR bubble fixed SVG positions (left/center/right field zones)
_HR_POSITIONS: dict[str, tuple[int, int]] = {
    "left": (30, 70),
    "center": (160, 25),
    "right": (290, 70),
}

# x-coordinate boundaries that determine left/right zone vs center
_HR_LEFT_MAX_X = 109
_HR_RIGHT_MIN_X = 211


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_field(ax: plt.Axes) -> None:
    """Draw the GC field geometry onto SVG-space axes (320×480, y inverted)."""
    lw = 0.75
    try:
        field_path = _svg_path(_FIELD_PATH_D)
        patch = PathPatch(
            field_path, facecolor="none", edgecolor=_FIELD_LINE, linewidth=lw, zorder=2
        )
        ax.add_patch(patch)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to parse field path; field boundary will be omitted.")

    for pts in [_HOME_PTS, _3B_PTS, _2B_PTS, _1B_PTS]:
        poly = Polygon(
            pts, closed=True, facecolor=_BASE_FILL,
            edgecolor=_FIELD_LINE, linewidth=0.5, zorder=3,
        )
        ax.add_patch(poly)


def _draw_hr_bubbles(ax: plt.Axes, events: list[dict]) -> None:
    """Count and draw HR zone bubbles for non-in-the-park home runs."""
    hr_counts: dict[str, int] = {"left": 0, "center": 0, "right": 0}
    for ev in events:
        if ev.get("play_result") != "home_run":
            continue
        x = ev.get("x")
        y = ev.get("y")
        if x is None or y is None:
            # Over-the-fence HR with no fielder location -- default center (AC-5)
            hr_counts["center"] += 1
        else:
            # Classify by transformed SVG x coordinate
            svg_x, _ = _raw_to_svg(x, y)
            if svg_x < _HR_LEFT_MAX_X:
                zone = "left"
            elif svg_x > _HR_RIGHT_MIN_X:
                zone = "right"
            else:
                zone = "center"
            hr_counts[zone] += 1

    for zone, count in hr_counts.items():
        if count == 0:
            continue
        bx, by = _HR_POSITIONS[zone]
        circle = plt.Circle(
            (bx, by), 12, color=_HIT_FILL, ec=_HIT_STROKE, lw=1.14, zorder=5
        )
        ax.add_patch(circle)
        ax.text(
            bx, by + 1, str(count),
            ha="center", va="center",
            fontsize=8, fontweight="bold", color="white", zorder=6,
        )


def _draw_events(ax: plt.Axes, events: list[dict]) -> None:
    """Draw BIP events as scatter markers grouped by (outcome, play_type).

    Outs render before hits (z-order 4 vs 4.5) to preserve GC render order.
    Marker shape encodes contact type; color encodes outcome (TN-2).
    """
    # Group events by (outcome, marker) for efficient scatter calls
    groups: dict[tuple[str, str], tuple[list[float], list[float]]] = {}
    for ev in events:
        x = ev.get("x")
        y = ev.get("y")
        if x is None or y is None:
            continue
        sx, sy = _raw_to_svg(x, y)
        outcome = _classify(ev.get("play_result"))
        marker = _marker_for_play_type(ev.get("play_type"))
        key = (outcome, marker)
        if key not in groups:
            groups[key] = ([], [])
        groups[key][0].append(sx)
        groups[key][1].append(sy)

    # Marker size: 36 (6^2) gives ~6pt diameter, distinguishable at mobile widths
    marker_size = 36

    # Render outs first (lower z-order), then hits on top
    for outcome, zorder in [("out", 4), ("hit", 4.5)]:
        if outcome == "hit":
            fill, stroke = _HIT_FILL, _HIT_STROKE
        else:
            fill, stroke = _OUT_FILL, _OUT_STROKE
        for (grp_outcome, marker), (xs, ys) in groups.items():
            if grp_outcome != outcome:
                continue
            ax.scatter(
                xs, ys,
                marker=marker,
                s=marker_size,
                c=fill,
                edgecolors=stroke,
                linewidths=0.75,
                zorder=zorder,
            )


def _draw_legend(ax: plt.Axes) -> None:
    """Draw a two-row legend: Row 1 = outcome colors, Row 2 = play type shapes."""
    # Row 1: Outcome colors (hit/out) using circles
    hit_handle = mlines.Line2D(
        [], [], marker="o", color="none", markerfacecolor=_HIT_FILL,
        markeredgecolor=_HIT_STROKE, markersize=6, label="Hit",
    )
    out_handle = mlines.Line2D(
        [], [], marker="o", color="none", markerfacecolor=_OUT_FILL,
        markeredgecolor=_OUT_STROKE, markersize=6, label="Out",
    )
    outcome_legend = ax.legend(
        handles=[hit_handle, out_handle],
        loc="lower right",
        fontsize=6,
        framealpha=0.8,
        ncols=2,
        bbox_to_anchor=(1.0, 0.04),
        handletextpad=0.3,
        columnspacing=0.8,
    )
    ax.add_artist(outcome_legend)

    # Row 2: Play type shapes in neutral gray
    gb_handle = mlines.Line2D(
        [], [], marker="o", color="none", markerfacecolor=_LEGEND_GRAY,
        markeredgecolor=_LEGEND_GRAY, markersize=5, label="Ground Ball",
    )
    ld_handle = mlines.Line2D(
        [], [], marker="^", color="none", markerfacecolor=_LEGEND_GRAY,
        markeredgecolor=_LEGEND_GRAY, markersize=5, label="Line Drive",
    )
    fb_handle = mlines.Line2D(
        [], [], marker="D", color="none", markerfacecolor=_LEGEND_GRAY,
        markeredgecolor=_LEGEND_GRAY, markersize=5, label="Fly Ball",
    )
    pu_handle = mlines.Line2D(
        [], [], marker="s", color="none", markerfacecolor=_LEGEND_GRAY,
        markeredgecolor=_LEGEND_GRAY, markersize=5, label="Popup",
    )
    bu_handle = mlines.Line2D(
        [], [], marker="v", color="none", markerfacecolor=_LEGEND_GRAY,
        markeredgecolor=_LEGEND_GRAY, markersize=5, label="Bunt",
    )
    ax.legend(
        handles=[gb_handle, ld_handle, fb_handle, pu_handle, bu_handle],
        loc="lower right",
        fontsize=5,
        framealpha=0.8,
        ncols=5,
        bbox_to_anchor=(1.0, 0.0),
        handletextpad=0.2,
        columnspacing=0.5,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_spray_chart(
    events: list[dict],
    title: str | None = None,
) -> bytes:
    """Render a spray chart PNG from a list of ball-in-play events.

    Replicates GameChanger's exact field geometry, coordinate transforms,
    and binary hit/out color scheme.  Events with ``x=None`` or ``y=None``
    skip the marker-rendering loop (no coordinate transform possible); for
    ``home_run`` events with None coordinates the HR zone bubble count is
    still incremented (center zone).

    Marker shape encodes contact type (play_type); marker color encodes
    outcome (hit/out).  See TN-1 for the play_type → marker mapping.

    Args:
        events: List of event dicts.  Each must contain:
            - ``x`` (float | None): raw API x coordinate
            - ``y`` (float | None): raw API y coordinate
            - ``play_result`` (str | None): e.g. ``"single"``, ``"batter_out"``
            - ``play_type`` (str | None): e.g. ``"ground_ball"``, ``"fly_ball"``
        title: Optional chart title rendered above the image.  When ``None``
            no title is drawn (dashboard routes use the HTML card heading).

    Returns:
        PNG image as raw bytes.
    """
    fig, ax = plt.subplots(figsize=(3, 4))
    ax.set_facecolor(_BG_COLOR)
    fig.patch.set_facecolor(_BG_COLOR)
    ax.set_xlim(0, 320)
    ax.set_ylim(480, 0)  # invert: SVG y=0 is top (CF), y=480 is bottom
    ax.set_aspect("equal")
    ax.axis("off")

    _draw_field(ax)
    _draw_events(ax, events)
    _draw_hr_bubbles(ax, events)

    if title is not None:
        ax.set_title(title, fontsize=9, pad=4, color="#333")

    _draw_legend(ax)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()
