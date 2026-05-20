"""Defensive positioning chart rendering module (E-230-01).

Render-layer module that produces matplotlib PNG bytes for the embedded
scouting-report Defensive Positioning section. Mirrors
``src/charts/spray.py``'s PNG-bytes contract: headless Agg backend,
caller-passed ``figsize``, and no in-image header (HTML owns the section
header and coverage cue per epic E-230 TN-3).

Public API::

    from src.charts.positioning import (
        POSITION_VIEWPORTS,
        render_position_chart,
        render_team_position_chart,
    )

    team_png = render_team_position_chart(
        conn, public_id, season_id, perspective_team_id=42,
    )
    lf_png = render_position_chart(
        conn, public_id, season_id, "LF", perspective_team_id=42,
    )

Both functions return ``bytes`` (PNG, ``dpi=150``) and operate entirely
in the engine 320×480 GC SVG coordinate space (no rescale).

Field-drawing primitives are imported from ``src.charts.spray``
(`_draw_field`, `_BG_COLOR`) to avoid drift if the spray field geometry
ever updates — see precedent at ``src/reports/positioning.py:32``.

Data reads route through four existing helpers in
``src.reports.positioning_card`` (no new queries):
``_query_team_id_from_public_id``, ``_query_team_aggregate``,
``_query_density_points``, ``_query_outlier_batters``. The fifth helper
in that module, ``_query_populated_zones``, is intentionally unused —
the chart layer here carries no compass ring (HTML owns those
affordances per TN-6), so the zone set is not needed.

Perspective threading (epic TN-4): callers MUST derive
``perspective_team_id`` once via ``_choose_perspective_team_id`` and pass
the same value into every chart call (1 team-level + 6 per-position).
``_query_team_aggregate`` does NOT take a perspective parameter — it
applies the same standalone-preferred chooser internally and returns
the chosen id in its result dict; by construction that equals the caller-
supplied value, so the SAME perspective threads through the density and
outlier-batter queries.
"""

from __future__ import annotations

import io
import logging
import sqlite3
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless rendering -- must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402

from src.charts.spray import _BG_COLOR, _draw_field  # noqa: E402
from src.reports.positioning import BASE_POSITIONS, COVERED_POSITIONS  # noqa: E402
from src.reports.positioning_card import (  # noqa: E402
    _query_density_points,
    _query_outlier_batters,
    _query_team_aggregate,
    _query_team_id_from_public_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-position viewports (epic TN-5)
# ---------------------------------------------------------------------------
# Each viewport is a ±60-px box around BASE_POSITIONS[position] in engine
# 320×480 SVG space. Tuple shape: (xmin, xmax, ymin_bottom, ymax_top).
#
# Y-axis inversion convention (mirrors src/charts/spray.py:480): SVG y=0
# sits at deep CF, so ax.set_ylim(ymin_bottom, ymax_top) with
# ymin_bottom > ymax_top flips the matplotlib y-axis to render CF up and
# home plate down. The same ``_FIELD_PATH_D`` boundary is drawn on every
# chart; matplotlib clips the path to the axis limits automatically.

_VIEWPORT_HALF_SIZE: float = 60.0


def _build_position_viewports() -> dict[str, tuple[float, float, float, float]]:
    """Compute the per-position ±60-px viewport tuples in engine SVG space.

    Anchored on ``BASE_POSITIONS[position]``; preserves the y-axis
    inversion (``ymin_bottom > ymax_top``).
    """
    out: dict[str, tuple[float, float, float, float]] = {}
    for position in COVERED_POSITIONS:
        base_x, base_y = BASE_POSITIONS[position]
        out[position] = (
            base_x - _VIEWPORT_HALF_SIZE,         # xmin
            base_x + _VIEWPORT_HALF_SIZE,         # xmax
            base_y + _VIEWPORT_HALF_SIZE,         # ymin_bottom (SVG y grows toward home)
            base_y - _VIEWPORT_HALF_SIZE,         # ymax_top    (SVG y=0 at deep CF)
        )
    return out


POSITION_VIEWPORTS: dict[str, tuple[float, float, float, float]] = (
    _build_position_viewports()
)
"""Per-position chart viewports in engine 320×480 SVG space.

Keys: ``LF``, ``CF``, ``RF``, ``3B``, ``SS``, ``2B``.
Value: ``(xmin, xmax, ymin_bottom, ymax_top)`` -- ``ymin_bottom > ymax_top``
preserves the y-axis inversion convention (SVG y=0 at deep CF)."""


# ---------------------------------------------------------------------------
# Engine-space crop for the full-field team chart
# ---------------------------------------------------------------------------
# SVG canvas is 320×480 with home plate at y≈295. The field boundary path
# bottoms out around y=318 (home plate triangle). 4-px padding mirrors
# src/charts/spray.py's xlim padding so stroke widths render fully.
_TEAM_CHART_XLIM_MIN: float = -4.0
_TEAM_CHART_XLIM_MAX: float = 324.0
_TEAM_CHART_YLIM_BOTTOM: float = 322.0  # ymin_bottom (just past home plate)
_TEAM_CHART_YLIM_TOP: float = -4.0      # ymax_top    (just past deep CF)


# ---------------------------------------------------------------------------
# Marker styling
# ---------------------------------------------------------------------------
# Density background: TN-9 mandates ax.scatter(s=4, c="#000", alpha=0.12).
_DENSITY_MARKER_SIZE: int = 4
_DENSITY_COLOR: str = "#000000"
_DENSITY_ALPHA: float = 0.12
_DENSITY_ZORDER: float = 1.0

# Star (team-aggregate centroid per position).
_STAR_MARKER: str = "*"
_STAR_SIZE_TEAM: int = 110
_STAR_SIZE_POSITION: int = 180
_STAR_COLOR: str = "#000000"
_STAR_EDGE_COLOR: str = "#FFFFFF"
_STAR_LINEWIDTH: float = 0.8
_STAR_ZORDER: float = 5.0

# Outlier "pill" — small marker + zone-letter label.
_OUTLIER_MARKER: str = "o"
_OUTLIER_SIZE_TEAM: int = 22
_OUTLIER_SIZE_POSITION: int = 32
_OUTLIER_COLOR: str = "#1F77B4"   # neutral blue, distinct from black stars
_OUTLIER_EDGE_COLOR: str = "#0B3D6B"
_OUTLIER_LINEWIDTH: float = 0.5
_OUTLIER_ZORDER: float = 6.0
_OUTLIER_LABEL_FONT_SIZE_TEAM: int = 5
_OUTLIER_LABEL_FONT_SIZE_POSITION: int = 7
_OUTLIER_LABEL_OFFSET_Y: float = -7.0   # px above marker (SVG y is inverted)
_OUTLIER_LABEL_ZORDER: float = 7.0

# Pill projection scale (engine 320×480 SVG px per signed ordinal-bucket
# unit). Calibrated so typical ±2–3 ordinal deviations stay inside the
# ±60-px per-position viewport. Mirrors the ratio used by
# ``src/reports/positioning_card.py::_pill_anchor_xy`` (18/22 in card
# viewBox space) adjusted to engine space.
_OUTLIER_SCALE_X: float = 14.0
_OUTLIER_SCALE_Y: float = 18.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _position_viewport(position: str) -> tuple[float, float, float, float]:
    """Look up the per-position viewport with a clear error for unknowns.

    Raises:
        ValueError: when ``position`` is not one of ``POSITION_VIEWPORTS``.
            The message names the offending value and lists all six
            supported positions so callers get an actionable hint.
    """
    if position not in POSITION_VIEWPORTS:
        supported = ", ".join(sorted(POSITION_VIEWPORTS.keys()))
        raise ValueError(
            f"Unsupported position {position!r}; "
            f"supported positions: {supported}"
        )
    return POSITION_VIEWPORTS[position]


def _draw_density(
    ax: plt.Axes,
    points: list[tuple[float, float]],
) -> None:
    """Draw the faint density-background scatter behind the field elements.

    Per TN-9: ``s=4, c="#000", alpha=0.12``. Same shape as
    ``src/charts/spray.py::_draw_events`` with smaller markers and uniform
    alpha. Empty ``points`` is a no-op (no exception raised).
    """
    if not points:
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.scatter(
        xs, ys,
        s=_DENSITY_MARKER_SIZE,
        c=_DENSITY_COLOR,
        alpha=_DENSITY_ALPHA,
        linewidths=0,
        zorder=_DENSITY_ZORDER,
    )


def _draw_stars(
    ax: plt.Axes,
    stars: list[tuple[float, float]],
    *,
    marker_size: int,
) -> None:
    """Draw one or more team-aggregate stars at engine SVG coordinates.

    The ``stars`` list contains ``(star_x, star_y)`` tuples. Empty input
    is a no-op (keeps the per-position chart safe when a position has no
    aggregate row).
    """
    if not stars:
        return
    xs = [s[0] for s in stars]
    ys = [s[1] for s in stars]
    ax.scatter(
        xs, ys,
        marker=_STAR_MARKER,
        s=marker_size,
        c=_STAR_COLOR,
        edgecolors=_STAR_EDGE_COLOR,
        linewidths=_STAR_LINEWIDTH,
        zorder=_STAR_ZORDER,
    )


def _draw_outlier_pills(
    ax: plt.Axes,
    outliers: list[dict[str, Any]],
    *,
    marker_size: int,
    label_font_size: int,
) -> None:
    """Project outlier deviations and scatter pills with zone-letter labels.

    Each ``outliers`` element is a dict shaped per
    ``_query_outlier_batters``: ``star_x``, ``star_y``,
    ``direction_deviation``, ``depth_deviation``, ``zone_id``.

    Projection mirrors ``src/reports/positioning_card.py::_pill_anchor_xy``
    adapted to engine SVG space::

        pill_x = star_x + direction_dev * _OUTLIER_SCALE_X
        pill_y = star_y - depth_dev * _OUTLIER_SCALE_Y
            # SVG y=0 at deep CF; depth-positive ("deep") projects upward
            # (toward smaller y).

    Outliers missing required keys are skipped silently — defensive parse
    so callers don't crash on a malformed row (warning logged via the
    module logger for diagnosis).
    """
    if not outliers:
        return

    pill_xs: list[float] = []
    pill_ys: list[float] = []
    labels: list[tuple[float, float, str]] = []
    for batter in outliers:
        star_x = batter.get("star_x")
        star_y = batter.get("star_y")
        direction_dev = batter.get("direction_deviation")
        depth_dev = batter.get("depth_deviation")
        zone_id = batter.get("zone_id")
        if (
            star_x is None or star_y is None
            or direction_dev is None or depth_dev is None
        ):
            logger.warning(
                "Skipping outlier with missing coordinates: zone_id=%r",
                zone_id,
            )
            continue
        px = star_x + direction_dev * _OUTLIER_SCALE_X
        py = star_y - depth_dev * _OUTLIER_SCALE_Y
        pill_xs.append(px)
        pill_ys.append(py)
        if zone_id:
            labels.append((px, py, str(zone_id)))

    if pill_xs:
        ax.scatter(
            pill_xs, pill_ys,
            marker=_OUTLIER_MARKER,
            s=marker_size,
            c=_OUTLIER_COLOR,
            edgecolors=_OUTLIER_EDGE_COLOR,
            linewidths=_OUTLIER_LINEWIDTH,
            zorder=_OUTLIER_ZORDER,
        )
    for px, py, letter in labels:
        ax.text(
            px, py + _OUTLIER_LABEL_OFFSET_Y, letter,
            ha="center", va="center",
            fontsize=label_font_size, fontweight="bold",
            color="#000000",
            zorder=_OUTLIER_LABEL_ZORDER,
        )


def _fig_to_png_bytes(fig: plt.Figure) -> bytes:
    """Serialize a matplotlib figure to PNG bytes and close it.

    Mirrors ``src/charts/spray.py::render_spray_chart`` finalization:
    ``dpi=150``, ``bbox_inches="tight"``, then ``plt.close(fig)`` to
    release resources.
    """
    buf = io.BytesIO()
    fig.savefig(
        buf, format="png", dpi=150, bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _annotate_outliers_with_star(
    outliers: list[dict[str, Any]],
    star_x: float,
    star_y: float,
) -> list[dict[str, Any]]:
    """Return a new list of outlier dicts annotated with the star anchor.

    The caller's query helper returns batter rows that lack the star
    coordinates (each row knows its own deviations but not the
    position's star). We inject ``star_x`` / ``star_y`` so the pill-
    drawing helper can project off a single anchor per call.
    """
    annotated: list[dict[str, Any]] = []
    for batter in outliers:
        merged = dict(batter)
        merged["star_x"] = star_x
        merged["star_y"] = star_y
        annotated.append(merged)
    return annotated


def _team_id_or_raise(conn: sqlite3.Connection, public_id: str) -> int:
    team_id = _query_team_id_from_public_id(conn, public_id)
    if team_id is None:
        raise ValueError(f"No team found for public_id={public_id!r}")
    return team_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_team_position_chart(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    *,
    perspective_team_id: int,
    title: str | None = None,
    figsize: tuple[float, float] = (6, 4),
) -> bytes:
    """Render the full-field team positioning chart as PNG bytes.

    Draws the field outline (320×480 engine SVG space) with a density
    background, then layers six team-aggregate stars (one per covered
    fielder position) and any per-position outlier pills on top.

    Args:
        conn: Open sqlite3 connection with v2 schema applied.
        public_id: Opponent's GameChanger ``public_id`` slug.
        season_id: Season slug (e.g. ``"2026-spring-hs"``).
        perspective_team_id: REQUIRED. The same id derived once via
            ``_choose_perspective_team_id`` at the caller and threaded
            into every chart call for this section (epic TN-4).
        title: Optional in-image title. Defaults to ``None`` — the
            scouting-report HTML owns the section header.
        figsize: matplotlib ``figsize`` tuple. Defaults to ``(6, 4)``
            per epic TN-3.

    Returns:
        PNG bytes (``dpi=150``).
    """
    team_id = _team_id_or_raise(conn, public_id)

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor(_BG_COLOR)
    fig.patch.set_facecolor(_BG_COLOR)
    ax.set_xlim(_TEAM_CHART_XLIM_MIN, _TEAM_CHART_XLIM_MAX)
    # ymin_bottom > ymax_top inverts the y-axis (SVG y=0 at deep CF).
    ax.set_ylim(_TEAM_CHART_YLIM_BOTTOM, _TEAM_CHART_YLIM_TOP)
    ax.set_aspect("equal")
    ax.axis("off")

    _draw_field(ax)

    # Density background uses the same pool for every chart (no new query).
    density_points = _query_density_points(
        conn, team_id, season_id, perspective_team_id,
    )
    _draw_density(ax, density_points)

    stars: list[tuple[float, float]] = []
    for position in COVERED_POSITIONS:
        aggregate = _query_team_aggregate(conn, team_id, season_id, position)
        if aggregate is None:
            continue
        star_x = aggregate["star_x"]
        star_y = aggregate["star_y"]
        stars.append((star_x, star_y))

        outliers = _query_outlier_batters(
            conn, team_id, season_id, position, perspective_team_id,
        )
        _draw_outlier_pills(
            ax,
            _annotate_outliers_with_star(outliers, star_x, star_y),
            marker_size=_OUTLIER_SIZE_TEAM,
            label_font_size=_OUTLIER_LABEL_FONT_SIZE_TEAM,
        )

    _draw_stars(ax, stars, marker_size=_STAR_SIZE_TEAM)

    if title is not None:
        ax.set_title(title, fontsize=9, pad=4, color="#333333")

    return _fig_to_png_bytes(fig)


def render_position_chart(
    conn: sqlite3.Connection,
    public_id: str,
    season_id: str,
    position: str,
    *,
    perspective_team_id: int,
    title: str | None = None,
    figsize: tuple[float, float] = (2.5, 2),
) -> bytes:
    """Render a single-position cropped positioning chart as PNG bytes.

    The axis is cropped to a ±60-px viewport (``POSITION_VIEWPORTS``)
    around ``BASE_POSITIONS[position]``. The same ``_FIELD_PATH_D``
    boundary used by the team chart is drawn; matplotlib clips the path
    to the viewport automatically — no per-position re-derivation of
    field geometry.

    Args:
        conn: Open sqlite3 connection with v2 schema applied.
        public_id: Opponent's GameChanger ``public_id`` slug.
        season_id: Season slug (e.g. ``"2026-spring-hs"``).
        position: One of ``LF``, ``CF``, ``RF``, ``3B``, ``SS``, ``2B``.
            Anything else raises ``ValueError``.
        perspective_team_id: REQUIRED. The same id derived once via
            ``_choose_perspective_team_id`` at the caller and threaded
            into every chart call for this section (epic TN-4).
        title: Optional in-image title. Defaults to ``None`` — the
            scouting-report HTML owns the per-card label.
        figsize: matplotlib ``figsize`` tuple. Defaults to ``(2.5, 2)``
            per epic TN-3.

    Returns:
        PNG bytes (``dpi=150``).

    Raises:
        ValueError: when ``position`` is not in ``POSITION_VIEWPORTS``.
    """
    xmin, xmax, ymin_bottom, ymax_top = _position_viewport(position)

    team_id = _team_id_or_raise(conn, public_id)

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor(_BG_COLOR)
    fig.patch.set_facecolor(_BG_COLOR)
    ax.set_xlim(xmin, xmax)
    # ymin_bottom > ymax_top inverts the y-axis (SVG y=0 at deep CF).
    ax.set_ylim(ymin_bottom, ymax_top)
    ax.set_aspect("equal")
    ax.axis("off")

    _draw_field(ax)

    # Density background: same pool as the team chart (no new query, per
    # TN-3 / TN-9). Axis-limit clipping handles the viewport crop.
    density_points = _query_density_points(
        conn, team_id, season_id, perspective_team_id,
    )
    _draw_density(ax, density_points)

    aggregate = _query_team_aggregate(conn, team_id, season_id, position)
    if aggregate is not None:
        star_x = aggregate["star_x"]
        star_y = aggregate["star_y"]
        _draw_stars(ax, [(star_x, star_y)], marker_size=_STAR_SIZE_POSITION)

        # Note: ``_query_populated_zones`` is not called here. The bundle
        # path uses it to dim empty compass-ring discs; the chart layer
        # in this module does NOT draw a compass ring (HTML owns those
        # affordances per TN-6 — chart pixels carry no text and the
        # per-card label is the position name only), so the zone set is
        # unused. The helper remains available for callers that do need
        # it (e.g. the quarter-letter bundle).

        outliers = _query_outlier_batters(
            conn, team_id, season_id, position, perspective_team_id,
        )
        _draw_outlier_pills(
            ax,
            _annotate_outliers_with_star(outliers, star_x, star_y),
            marker_size=_OUTLIER_SIZE_POSITION,
            label_font_size=_OUTLIER_LABEL_FONT_SIZE_POSITION,
        )

    if title is not None:
        ax.set_title(title, fontsize=9, pad=4, color="#333333")

    return _fig_to_png_bytes(fig)
