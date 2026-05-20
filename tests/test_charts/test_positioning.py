"""Tests for src/charts/positioning.py — defensive positioning chart module.

Covers acceptance criteria E-230-01 AC-1 through AC-9:

* AC-1 / AC-2: module surface (functions exist, ``matplotlib.use("Agg")``
  set, default ``figsize`` values).
* AC-3 / AC-7: ``POSITION_VIEWPORTS`` shape + viewport math invariants.
* AC-4 / AC-5: PNG signature + length for the team chart and all 6
  per-position charts.
* AC-6: ``ValueError`` for unsupported positions.
* AC-8: density helper handles empty and non-empty inputs without error.

The four ``_query_*`` helpers are patched at the import site
(``src.charts.positioning``) so the tests never touch a real database.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")  # ensure headless before importing pyplot in tests
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from src.charts import positioning as positioning_mod  # noqa: E402
from src.charts.positioning import (  # noqa: E402
    POSITION_VIEWPORTS,
    _draw_density,
    _position_viewport,
    render_position_chart,
    render_team_position_chart,
)
from src.reports.positioning import BASE_POSITIONS, COVERED_POSITIONS  # noqa: E402

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MIN_PNG_LENGTH = 1024


# ---------------------------------------------------------------------------
# Canned query-helper outputs (used by render-path tests)
# ---------------------------------------------------------------------------


def _canned_aggregate(position: str, perspective_team_id: int) -> dict[str, Any]:
    """Return a synthetic team_position_aggregate row for ``position``."""
    base_x, base_y = BASE_POSITIONS[position]
    return {
        "position": position,
        # Slightly offset star from textbook anchor so the renderer sees a
        # non-trivial value (still well inside the viewport).
        "star_x": base_x + 3.0,
        "star_y": base_y - 4.0,
        "bip_count": 120,
        "is_low_confidence": 0,
        "perspective_team_id": perspective_team_id,
    }


def _canned_outliers(position: str) -> list[dict[str, Any]]:
    """Two synthetic outlier rows per position.

    Deviations are small ordinal-bucket values so the projected pill
    anchors stay inside the per-position ±60-px viewport.
    """
    return [
        {
            "player_id": 1001,
            "direction_deviation": 1,
            "depth_deviation": 1,
            "zone_id": "H",
            "jersey_number": "7",
            "first_name": "Test",
            "last_name": "Batter",
        },
        {
            "player_id": 1002,
            "direction_deviation": -2,
            "depth_deviation": -1,
            "zone_id": "A",
            "jersey_number": "12",
            "first_name": "Other",
            "last_name": "Hitter",
        },
    ]


def _canned_density_points() -> list[tuple[float, float]]:
    """A small synthetic density pool that lands inside the engine field."""
    return [
        (160.0, 150.0),
        (140.0, 180.0),
        (180.0, 200.0),
        (120.0, 220.0),
        (200.0, 230.0),
        (160.0, 250.0),
        (110.0, 150.0),
        (210.0, 150.0),
        (160.0, 120.0),
        (160.0, 280.0),
    ]


@pytest.fixture
def patched_queries():
    """Patch the four query helpers at the chart module's import site.

    Yields the perspective_team_id used in all canned data so tests can
    pass it directly into the public functions.
    """
    perspective_team_id = 42

    def fake_team_id(_conn, _public_id):
        return 99  # any non-None int

    def fake_aggregate(_conn, _team_id, _season_id, position):
        return _canned_aggregate(position, perspective_team_id)

    def fake_density(_conn, _team_id, _season_id, _persp):
        return _canned_density_points()

    def fake_outliers(_conn, _team_id, _season_id, position, _persp):
        return _canned_outliers(position)

    with patch.object(positioning_mod, "_query_team_id_from_public_id", side_effect=fake_team_id), \
         patch.object(positioning_mod, "_query_team_aggregate", side_effect=fake_aggregate), \
         patch.object(positioning_mod, "_query_density_points", side_effect=fake_density), \
         patch.object(positioning_mod, "_query_outlier_batters", side_effect=fake_outliers):
        yield perspective_team_id


# ---------------------------------------------------------------------------
# AC-1: module surface
# ---------------------------------------------------------------------------


def test_render_team_position_chart_is_callable() -> None:
    """AC-1: render_team_position_chart exists and is callable."""
    assert callable(render_team_position_chart)


def test_render_position_chart_is_callable() -> None:
    """AC-1: render_position_chart exists and is callable."""
    assert callable(render_position_chart)


def test_team_chart_default_figsize_is_6_by_4() -> None:
    """AC-1: render_team_position_chart default figsize is (6, 4)."""
    sig = render_team_position_chart.__defaults__ or ()
    # Defaults apply to keyword-only args after the * in the signature.
    # __kwdefaults__ is the safer surface to read.
    kwdefaults = render_team_position_chart.__kwdefaults__ or {}
    assert kwdefaults.get("figsize") == (6, 4)


def test_position_chart_default_figsize_is_2_5_by_2() -> None:
    """AC-1: render_position_chart default figsize is (2.5, 2)."""
    kwdefaults = render_position_chart.__kwdefaults__ or {}
    assert kwdefaults.get("figsize") == (2.5, 2)


def test_team_chart_title_defaults_to_none() -> None:
    """AC-1: title defaults to None on render_team_position_chart."""
    kwdefaults = render_team_position_chart.__kwdefaults__ or {}
    assert kwdefaults.get("title") is None


def test_position_chart_title_defaults_to_none() -> None:
    """AC-1: title defaults to None on render_position_chart."""
    kwdefaults = render_position_chart.__kwdefaults__ or {}
    assert kwdefaults.get("title") is None


# ---------------------------------------------------------------------------
# AC-2: Agg backend declared at module scope
# ---------------------------------------------------------------------------


def test_module_uses_agg_backend() -> None:
    """AC-2: matplotlib backend is Agg after importing the module."""
    # Importing the module triggers ``matplotlib.use("Agg")`` at module
    # scope; ``matplotlib.get_backend()`` reflects the active backend.
    assert matplotlib.get_backend().lower() == "agg"


# ---------------------------------------------------------------------------
# AC-3: POSITION_VIEWPORTS shape
# ---------------------------------------------------------------------------


def test_position_viewports_has_six_entries() -> None:
    """AC-3: POSITION_VIEWPORTS has one entry for each covered position."""
    assert set(POSITION_VIEWPORTS.keys()) == set(COVERED_POSITIONS)
    assert len(POSITION_VIEWPORTS) == 6


@pytest.mark.parametrize("position", list(COVERED_POSITIONS))
def test_position_viewport_is_four_tuple_of_floats(position: str) -> None:
    """AC-3: each viewport is a 4-tuple of numeric values."""
    viewport = POSITION_VIEWPORTS[position]
    assert isinstance(viewport, tuple)
    assert len(viewport) == 4
    for val in viewport:
        assert isinstance(val, (int, float))


# ---------------------------------------------------------------------------
# AC-7: viewport math invariants (parametrized across all 6 positions)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("position", list(COVERED_POSITIONS))
def test_viewport_xmin_lt_xmax(position: str) -> None:
    """AC-7: xmin < xmax for every position viewport."""
    xmin, xmax, _ymin_bottom, _ymax_top = POSITION_VIEWPORTS[position]
    assert xmin < xmax


@pytest.mark.parametrize("position", list(COVERED_POSITIONS))
def test_viewport_y_axis_is_inverted(position: str) -> None:
    """AC-7: ymin_bottom > ymax_top (SVG y=0 at deep CF inversion)."""
    _xmin, _xmax, ymin_bottom, ymax_top = POSITION_VIEWPORTS[position]
    assert ymin_bottom > ymax_top


@pytest.mark.parametrize("position", list(COVERED_POSITIONS))
def test_base_position_falls_inside_viewport(position: str) -> None:
    """AC-7: BASE_POSITIONS[position] lies inside the viewport rectangle."""
    xmin, xmax, ymin_bottom, ymax_top = POSITION_VIEWPORTS[position]
    base_x, base_y = BASE_POSITIONS[position]
    assert xmin <= base_x <= xmax
    # Y rectangle: ymax_top (smaller SVG y) <= base_y <= ymin_bottom.
    assert ymax_top <= base_y <= ymin_bottom


# ---------------------------------------------------------------------------
# AC-4: render_team_position_chart returns a valid PNG
# ---------------------------------------------------------------------------


def test_render_team_position_chart_returns_png_bytes(patched_queries) -> None:
    """AC-4: returned bytes start with PNG signature and length ≥ 1024."""
    perspective_team_id = patched_queries
    result = render_team_position_chart(
        conn=None,  # type: ignore[arg-type]
        public_id="test-opp",
        season_id="2026-spring-hs",
        perspective_team_id=perspective_team_id,
    )
    assert isinstance(result, bytes)
    assert result[:8] == PNG_SIGNATURE
    assert len(result) >= MIN_PNG_LENGTH


def test_render_team_position_chart_with_title(patched_queries) -> None:
    """AC-4: passing a title still returns a valid PNG."""
    perspective_team_id = patched_queries
    result = render_team_position_chart(
        conn=None,  # type: ignore[arg-type]
        public_id="test-opp",
        season_id="2026-spring-hs",
        perspective_team_id=perspective_team_id,
        title="Bears — Defensive Positioning",
    )
    assert result[:8] == PNG_SIGNATURE
    assert len(result) >= MIN_PNG_LENGTH


# ---------------------------------------------------------------------------
# AC-5: render_position_chart returns a valid PNG for each position
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("position", list(COVERED_POSITIONS))
def test_render_position_chart_returns_png_bytes(
    patched_queries, position: str,
) -> None:
    """AC-5: each per-position chart returns PNG bytes ≥ 1024."""
    perspective_team_id = patched_queries
    result = render_position_chart(
        conn=None,  # type: ignore[arg-type]
        public_id="test-opp",
        season_id="2026-spring-hs",
        position=position,
        perspective_team_id=perspective_team_id,
    )
    assert isinstance(result, bytes)
    assert result[:8] == PNG_SIGNATURE
    assert len(result) >= MIN_PNG_LENGTH


# ---------------------------------------------------------------------------
# AC-6: ValueError for unsupported positions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("position", ["P", "C", "DH", "lf", "", "1B"])
def test_render_position_chart_rejects_unsupported_position(
    patched_queries, position: str,
) -> None:
    """AC-6: unsupported position raises ValueError naming it + supported list."""
    perspective_team_id = patched_queries
    with pytest.raises(ValueError) as exc_info:
        render_position_chart(
            conn=None,  # type: ignore[arg-type]
            public_id="test-opp",
            season_id="2026-spring-hs",
            position=position,
            perspective_team_id=perspective_team_id,
        )
    msg = str(exc_info.value)
    assert repr(position) in msg
    # Message must mention each of the six supported positions.
    for supported in COVERED_POSITIONS:
        assert supported in msg


def test_position_viewport_helper_raises_for_unsupported() -> None:
    """AC-6: the internal helper raises ValueError with the same shape."""
    with pytest.raises(ValueError) as exc_info:
        _position_viewport("P")
    msg = str(exc_info.value)
    assert "'P'" in msg
    for supported in COVERED_POSITIONS:
        assert supported in msg


# ---------------------------------------------------------------------------
# AC-8: density helper handles empty + non-empty inputs
# ---------------------------------------------------------------------------


def test_draw_density_with_empty_points_is_a_noop() -> None:
    """AC-8: empty point list does not raise and produces no collections."""
    fig, ax = plt.subplots()
    try:
        # No exception raised:
        _draw_density(ax, [])
        # No scatter call ⇒ no PathCollection added.
        assert len(ax.collections) == 0
    finally:
        plt.close(fig)


def test_draw_density_with_points_adds_a_collection() -> None:
    """AC-8: non-empty point list produces a matplotlib collection."""
    fig, ax = plt.subplots()
    try:
        _draw_density(ax, _canned_density_points())
        # ax.scatter adds one PathCollection per call.
        assert len(ax.collections) == 1
        collection = ax.collections[0]
        # Collection holds exactly the points we passed in.
        offsets = collection.get_offsets()
        assert len(offsets) == len(_canned_density_points())
    finally:
        plt.close(fig)


def test_draw_density_alpha_matches_tn9() -> None:
    """AC-8 / TN-9: density alpha is 0.12 per the locked spec."""
    fig, ax = plt.subplots()
    try:
        _draw_density(ax, _canned_density_points())
        collection = ax.collections[0]
        # get_alpha returns a single float when uniform alpha was set.
        assert pytest.approx(0.12, abs=1e-6) == collection.get_alpha()
    finally:
        plt.close(fig)


# ---------------------------------------------------------------------------
# Defensive parsing: render path stays robust under missing rows
# ---------------------------------------------------------------------------


def test_team_chart_skips_positions_with_no_aggregate() -> None:
    """When some positions have no aggregate row, the team chart still renders.

    Defensive against partial-coverage opponents (e.g. only 4 of 6
    positions have enough BIP for a star). The chart MUST not crash and
    MUST still produce a valid PNG.
    """
    perspective_team_id = 42

    def fake_team_id(_conn, _public_id):
        return 99

    def fake_aggregate(_conn, _team_id, _season_id, position):
        # CF + RF intentionally missing.
        if position in ("CF", "RF"):
            return None
        return _canned_aggregate(position, perspective_team_id)

    def fake_density(_conn, _team_id, _season_id, _persp):
        return _canned_density_points()

    def fake_outliers(_conn, _team_id, _season_id, position, _persp):
        return _canned_outliers(position)

    with patch.object(positioning_mod, "_query_team_id_from_public_id", side_effect=fake_team_id), \
         patch.object(positioning_mod, "_query_team_aggregate", side_effect=fake_aggregate), \
         patch.object(positioning_mod, "_query_density_points", side_effect=fake_density), \
         patch.object(positioning_mod, "_query_outlier_batters", side_effect=fake_outliers):
        result = render_team_position_chart(
            conn=None,  # type: ignore[arg-type]
            public_id="test-opp",
            season_id="2026-spring-hs",
            perspective_team_id=perspective_team_id,
        )
    assert result[:8] == PNG_SIGNATURE
    assert len(result) >= MIN_PNG_LENGTH


def test_unknown_public_id_raises_value_error() -> None:
    """Missing team for the supplied public_id is surfaced as ValueError."""
    with patch.object(
        positioning_mod, "_query_team_id_from_public_id", return_value=None,
    ):
        with pytest.raises(ValueError) as exc_info:
            render_team_position_chart(
                conn=None,  # type: ignore[arg-type]
                public_id="missing-slug",
                season_id="2026-spring-hs",
                perspective_team_id=42,
            )
    assert "missing-slug" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Perspective threading (TN-4 correctness pin)
# ---------------------------------------------------------------------------


def test_caller_perspective_threads_to_dependent_queries() -> None:
    """TN-4: the caller's perspective_team_id flows to density + outlier
    helpers (the two perspective-aware helpers the chart layer reads).

    ``_query_team_aggregate`` does not take perspective as a parameter
    (it picks its own and returns it); the chart layer applies the
    caller's perspective to ``_query_density_points`` and
    ``_query_outlier_batters``.
    """
    perspective_team_id = 7777

    seen: dict[str, list[int]] = {
        "density_points": [],
        "outlier_batters": [],
    }

    def fake_team_id(_conn, _public_id):
        return 99

    def fake_aggregate(_conn, _team_id, _season_id, position):
        return _canned_aggregate(position, perspective_team_id)

    def fake_density(_conn, _team_id, _season_id, persp):
        seen["density_points"].append(persp)
        return _canned_density_points()

    def fake_outliers(_conn, _team_id, _season_id, position, persp):
        seen["outlier_batters"].append(persp)
        return _canned_outliers(position)

    with patch.object(positioning_mod, "_query_team_id_from_public_id", side_effect=fake_team_id), \
         patch.object(positioning_mod, "_query_team_aggregate", side_effect=fake_aggregate), \
         patch.object(positioning_mod, "_query_density_points", side_effect=fake_density), \
         patch.object(positioning_mod, "_query_outlier_batters", side_effect=fake_outliers):
        render_position_chart(
            conn=None,  # type: ignore[arg-type]
            public_id="test-opp",
            season_id="2026-spring-hs",
            position="CF",
            perspective_team_id=perspective_team_id,
        )

    assert seen["density_points"] == [perspective_team_id]
    assert seen["outlier_batters"] == [perspective_team_id]
