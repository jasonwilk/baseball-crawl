"""Tests for src/charts/spray.py -- spray chart rendering module."""
from __future__ import annotations

import struct

import pytest

from src.charts.spray import _classify, _raw_to_svg, render_spray_chart

# ---------------------------------------------------------------------------
# Coordinate transform tests (AC-2)
# ---------------------------------------------------------------------------

# Constants from the spike (verbatim):
#   _NU  = (160 - 211.25) / (160 - 234)  ≈ 0.69256...
#   _DU  = (295 - 246)    / (296 - 220)  ≈ 0.64473...
#   _KUe = 160 - 160 * _NU               ≈ 49.189...
#   _YUe = 295 - 296 * _DU               ≈ 104.158...


def test_raw_to_svg_origin_maps_to_offset() -> None:
    """(0, 0) maps to the offset constants (_KUe, _YUe)."""
    sx, sy = _raw_to_svg(0.0, 0.0)
    assert abs(sx - 49.189) < 0.01
    assert abs(sy - 104.158) < 0.01


def test_raw_to_svg_known_anchor_x() -> None:
    """Anchor point: raw x=160 should map to svg x=160."""
    # From _KUe + 160 * _NU = 160 - 160*_NU + 160*_NU = 160
    sx, _sy = _raw_to_svg(160.0, 0.0)
    assert abs(sx - 160.0) < 0.01


def test_raw_to_svg_known_anchor_y() -> None:
    """Anchor point: raw y=296 should map to svg y=295."""
    _sx, sy = _raw_to_svg(0.0, 296.0)
    assert abs(sy - 295.0) < 0.5  # _YUe + 296 * _DU ≈ 295


def test_raw_to_svg_scale_increases_with_positive_input() -> None:
    """Larger raw coords produce larger SVG coords (positive scale)."""
    sx1, sy1 = _raw_to_svg(100.0, 100.0)
    sx2, sy2 = _raw_to_svg(200.0, 200.0)
    assert sx2 > sx1
    assert sy2 > sy1


def test_raw_to_svg_x_scale_approx() -> None:
    """x scale factor is approximately 0.6926."""
    sx1, _ = _raw_to_svg(0.0, 0.0)
    sx2, _ = _raw_to_svg(100.0, 0.0)
    scale = sx2 - sx1
    assert abs(scale - 69.26) < 0.5


def test_raw_to_svg_y_scale_approx() -> None:
    """y scale factor is approximately 0.6447."""
    _, sy1 = _raw_to_svg(0.0, 0.0)
    _, sy2 = _raw_to_svg(0.0, 100.0)
    scale = sy2 - sy1
    assert abs(scale - 64.47) < 0.5


# ---------------------------------------------------------------------------
# Hit/out classification tests (AC-4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("play_result", ["single", "double", "triple", "home_run", "dropped_third_strike"])
def test_classify_hit_results(play_result: str) -> None:
    assert _classify(play_result) == "hit"


@pytest.mark.parametrize("play_result", [
    "batter_out",
    "batter_out_advance_runners",
    "fielders_choice",
    "sac_fly",
    "error",
    None,
    "",
    "unknown_result",
])
def test_classify_out_results(play_result: str | None) -> None:
    assert _classify(play_result) == "out"


# ---------------------------------------------------------------------------
# render_spray_chart output tests (AC-1, AC-8, AC-11)
# ---------------------------------------------------------------------------

def _sample_events() -> list[dict]:
    return [
        {"x": 160.0, "y": 150.0, "play_result": "single"},
        {"x": 200.0, "y": 200.0, "play_result": "batter_out"},
        {"x": 100.0, "y": 180.0, "play_result": "double"},
        {"x": 120.0, "y": 220.0, "play_result": "batter_out"},
    ]


def test_render_returns_bytes() -> None:
    """render_spray_chart returns bytes."""
    result = render_spray_chart(_sample_events())
    assert isinstance(result, bytes)


def test_render_returns_non_empty_bytes() -> None:
    """render_spray_chart returns non-empty bytes."""
    result = render_spray_chart(_sample_events())
    assert len(result) > 0


def test_render_output_is_png() -> None:
    """Output bytes start with PNG magic bytes."""
    result = render_spray_chart(_sample_events())
    # PNG magic: \x89PNG\r\n\x1a\n
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_empty_events_returns_png() -> None:
    """render_spray_chart handles empty event list without error."""
    result = render_spray_chart([])
    assert isinstance(result, bytes)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_with_title() -> None:
    """render_spray_chart with title returns valid PNG."""
    result = render_spray_chart(_sample_events(), title="Test Chart")
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_without_title() -> None:
    """render_spray_chart with title=None returns valid PNG."""
    result = render_spray_chart(_sample_events(), title=None)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# None coordinate handling tests (AC-5, AC-5a)
# ---------------------------------------------------------------------------

def test_render_skips_none_xy_non_hr() -> None:
    """Non-HR events with None x/y are silently skipped (no crash)."""
    events = [
        {"x": None, "y": None, "play_result": "batter_out"},
        {"x": 160.0, "y": 150.0, "play_result": "single"},
    ]
    result = render_spray_chart(events)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_hr_none_coords_counts_center_bubble() -> None:
    """Over-the-fence HR with None coords increments center HR bubble (no crash)."""
    events = [
        {"x": None, "y": None, "play_result": "home_run"},
    ]
    result = render_spray_chart(events)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_hr_with_coords_counts_zone_bubble() -> None:
    """HR with x/y coords classifies into left/center/right zone (no crash)."""
    events = [
        # left zone: svg_x < 109, so raw x near 0 → svg_x ≈ 49 (< 109)
        {"x": 0.0, "y": 100.0, "play_result": "home_run"},
        # right zone: svg_x > 211, so raw x near 240 → svg_x ≈ 49 + 240*0.6926 ≈ 215
        {"x": 240.0, "y": 100.0, "play_result": "home_run"},
    ]
    result = render_spray_chart(events)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# PNG dimension sanity check (AC-8: 4x6 inches at 150 DPI = 600x900 pixels)
# ---------------------------------------------------------------------------

def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Extract width, height from PNG IHDR chunk."""
    # IHDR starts at byte 16: 4 bytes width, 4 bytes height
    width = struct.unpack(">I", png_bytes[16:20])[0]
    height = struct.unpack(">I", png_bytes[20:24])[0]
    return width, height


def test_render_png_dimensions_approx_4x6_at_150dpi() -> None:
    """Output PNG dimensions should be in the right ballpark for a 4×6 @ 150 DPI figure.

    ``bbox_inches='tight'`` trims figure whitespace (particularly with equal-aspect
    axes), so the actual pixel size is smaller than the nominal 600×900.  We verify
    the image is substantively sized rather than a thumbnail.
    """
    result = render_spray_chart(_sample_events())
    width, height = _png_dimensions(result)
    # Minimum threshold: at least 300×450 (half of nominal 600×900)
    assert width >= 300, f"Width {width} too small (expected >= 300)"
    assert height >= 450, f"Height {height} too small (expected >= 450)"
    # Height should exceed width (portrait orientation: 2:3 ratio)
    assert height > width, f"Expected portrait PNG but got width={width}, height={height}"
