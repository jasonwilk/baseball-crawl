"""Standalone scouting report renderer.

Produces a self-contained HTML scouting report from a structured data dict.
All CSS is inlined, spray charts are embedded as base64 data URIs, and the
output has no external dependencies -- it can be saved to disk and opened
in any browser offline.

Public API::

    from src.reports.renderer import render_report

    html = render_report(data)

The ``data`` dict shape is documented in :func:`render_report`.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.api.helpers import format_avg, format_date, ip_display
logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "api" / "templates"
_TEMPLATE_NAME = "reports/scouting_report.html"

# Thresholds per coaching consultation and AC-7
_MIN_PA_BATTING = 20
_MIN_IP_OUTS_PITCHING = 45  # 15 IP = 45 outs

# Spray chart minimum BIP threshold (consistent with dashboard display)
_MIN_BIP_SPRAY = 3


def _build_jinja_env() -> Environment:
    """Create a Jinja2 environment with the required filters."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    env.filters["ip_display"] = ip_display
    env.filters["format_avg"] = format_avg
    env.filters["format_date"] = format_date
    return env


def _encode_spray_chart(events: list[dict], title: str | None = None) -> str:
    """Render a spray chart and return a base64-encoded data URI string."""
    from src.charts.spray import render_spray_chart

    png_bytes = render_spray_chart(events, title=title)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _compute_pa(player: dict) -> int:
    """Compute plate appearances from batting stat fields."""
    return (
        (player.get("ab") or 0)
        + (player.get("bb") or 0)
        + (player.get("hbp") or 0)
        + (player.get("shf") or 0)
    )


def render_report(data: dict[str, Any]) -> str:
    """Render a standalone scouting report HTML string.

    Args:
        data: Report data dict with the following keys:

            - ``team``: dict with ``name`` (str), ``season_year`` (int|None),
              ``record`` (dict with ``wins``, ``losses``) or None
            - ``generated_at``: str, ISO datetime of report generation
            - ``expires_at``: str, ISO datetime of report expiration
            - ``freshness_date``: str|None, date of most recent game in data
              (ISO ``YYYY-MM-DD``)
            - ``game_count``: int, number of games in the data
            - ``recent_form``: list of dicts with ``result`` ("W"/"L"/"T"),
              ``our_score`` (int), ``their_score`` (int) -- last 5 games,
              most recent first. May be empty or absent.
            - ``pitching``: list of player stat dicts (see pitching table
              columns). Each dict should include ``jersey_number``, ``name``,
              ``era``, ``k9``, ``whip``, ``games``, ``ip_outs``, ``h``,
              ``er``, ``bb``, ``so``, ``pitches``, ``strike_pct``.
            - ``batting``: list of player stat dicts. Each dict should include
              ``jersey_number``, ``name``, ``games``, ``ab``, ``h``, ``bb``,
              ``hbp``, ``shf``, ``doubles``, ``triples``, ``hr``, ``so``,
              ``sb``, ``rbi``.
            - ``spray_charts``: dict mapping player_id (str) to list of
              event dicts (each with ``x``, ``y``, ``play_result``,
              ``play_type``). May be empty or absent.
            - ``roster``: list of dicts with ``jersey_number``, ``name``,
              ``position``.

    Returns:
        Complete HTML string ready to be written to a file.
    """
    env = _build_jinja_env()
    template = env.get_template(_TEMPLATE_NAME)

    # Shallow-copy so we don't mutate the caller's data
    batting = [dict(b) for b in data.get("batting") or []]
    for player in batting:
        pa = _compute_pa(player)
        player["_pa"] = pa
        player["_small_sample"] = pa < _MIN_PA_BATTING

    pitching = [dict(p) for p in data.get("pitching") or []]
    for pitcher in pitching:
        ip_outs = pitcher.get("ip_outs") or 0
        pitcher["_small_sample"] = ip_outs < _MIN_IP_OUTS_PITCHING

    # Build spray chart data URIs for players meeting the BIP threshold
    spray_data: dict[str, str] = {}  # player name -> data URI
    spray_charts_raw = data.get("spray_charts") or {}
    spray_player_lookup: dict[str, dict] = {}

    # Build a lookup from player_id to player dict for name resolution
    for player in batting:
        pid = player.get("player_id")
        if pid is not None:
            spray_player_lookup[pid] = player

    for player_id, events in spray_charts_raw.items():
        if not events or len(events) < _MIN_BIP_SPRAY:
            continue
        player = spray_player_lookup.get(player_id)
        player_name = player["name"] if player else f"Player {player_id}"
        jersey = player.get("jersey_number") if player else None
        title = f"#{jersey} {player_name}" if jersey else player_name
        try:
            data_uri = _encode_spray_chart(events, title=title)
            spray_data[player_id] = data_uri
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to render spray chart for player %s", player_id,
                exc_info=True,
            )

    # Format recent form as a compact string
    recent_form = data.get("recent_form") or []
    recent_form_str = ""
    if recent_form:
        parts = []
        for game in recent_form[:5]:
            result = game.get("result", "?")
            our = game.get("our_score", "?")
            their = game.get("their_score", "?")
            parts.append(f"{result} {our}-{their}")
        recent_form_str = ", ".join(parts)

    context = {
        "team": data.get("team") or {},
        "generated_at": data.get("generated_at", ""),
        "expires_at": data.get("expires_at", ""),
        "freshness_date": data.get("freshness_date"),
        "game_count": data.get("game_count", 0),
        "recent_form_str": recent_form_str,
        "pitching": pitching,
        "batting": batting,
        "spray_data": spray_data,
        "roster": data.get("roster") or [],
        "has_pitching": bool(pitching),
        "has_batting": bool(batting),
        "has_spray": bool(spray_data),
        "has_recent_form": bool(recent_form_str),
    }

    return template.render(**context)
