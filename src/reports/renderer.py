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

# Thresholds per coaching consultation and E-187
_MIN_PA_BATTING = 5
_MIN_IP_OUTS_PITCHING = 18  # 6 IP = 18 outs

# Spray chart minimum BIP thresholds
_MIN_BIP_SPRAY = 3
_MIN_BIP_TEAM_SPRAY = 20

# Heat-map percentile thresholds: percentile -> level
# 0-19% -> 1, 20-39% -> 2, 40-69% -> 3, 70-100% -> 4
_HEAT_THRESHOLDS = [(0.70, 4), (0.40, 3), (0.20, 2), (0.0, 1)]

# Graduated heat intensity tiers (TN-2a)
# (min_qualified_count, max_heat_level) -- iterate top-down, first match wins
_BATTING_HEAT_TIERS = [(9, 4), (7, 3), (5, 2), (3, 1)]   # 0-2: max=0
_PITCHING_HEAT_TIERS = [(6, 4), (4, 3), (3, 2), (2, 1)]  # 0-1: max=0

# Key-player thresholds
_KEY_PITCHER_MIN_OUTS = 18   # 6 IP
_KEY_BATTER_MIN_PA = 5


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


def _percentile_rank(value: float, values: list[float]) -> float:
    """Compute the percentile rank of ``value`` within ``values``.

    Returns a float in [0, 1]. Uses the "percentage of values <= this value"
    method. For a single-element list, returns 1.0.
    """
    if not values:
        return 0.0
    count_le = sum(1 for v in values if v <= value)
    return count_le / len(values)


def _percentile_to_level(pct: float) -> int:
    """Map a percentile (0-1) to a heat level (1-4)."""
    for threshold, level in _HEAT_THRESHOLDS:
        if pct >= threshold:
            return level
    return 1


def _safe_div(numerator: float, denominator: float) -> float:
    """Safe division returning 0.0 when denominator is zero."""
    return numerator / denominator if denominator else 0.0


def _max_heat_for_depth(
    qualified_count: int,
    tiers: list[tuple[int, int]],
) -> int:
    """Return the maximum heat level allowed for a given number of qualified players.

    Iterates *tiers* top-down; returns the max_level from the first entry
    whose threshold is met.  Falls back to 0 (no heat) when the count is
    below the lowest tier.
    """
    for min_count, max_level in tiers:
        if qualified_count >= min_count:
            return max_level
    return 0


def _compute_batting_enrichments(batting: list[dict]) -> None:
    """Add computed columns to each batter dict (mutates in place).

    Adds: _pa, _k_pct, _bb_pct, _xbh, _sb_cs, _small_sample.
    """
    for player in batting:
        pa = _compute_pa(player)
        player["_pa"] = pa
        player["_small_sample"] = pa < _MIN_PA_BATTING

        # Rate stats
        if pa > 0:
            player["_k_pct"] = f"{(player.get('so') or 0) / pa * 100:.1f}%"
            player["_bb_pct"] = f"{(player.get('bb') or 0) / pa * 100:.1f}%"
        else:
            player["_k_pct"] = "-"
            player["_bb_pct"] = "-"

        # XBH
        player["_xbh"] = (
            (player.get("doubles") or 0)
            + (player.get("triples") or 0)
            + (player.get("hr") or 0)
        )

        # SB-CS formatted string
        sb = player.get("sb") or 0
        cs = player.get("cs") or 0
        player["_sb_cs"] = f"{sb}-{cs}"


def _compute_batting_heat(batting: list[dict]) -> None:
    """Compute heat-map levels for batting stats (mutates in place).

    Heat levels are computed within the non-small-sample subset.
    Small-sample players get all-zero heat.
    """
    qualified = [p for p in batting if not p.get("_small_sample")]

    # Collect raw stat values for qualified players
    avg_vals = []
    obp_vals = []
    slg_vals = []
    for p in qualified:
        ab = p.get("ab") or 0
        pa = p["_pa"]
        h = p.get("h") or 0
        bb = p.get("bb") or 0
        hbp = p.get("hbp") or 0
        tb = (
            h
            - (p.get("doubles") or 0)
            - (p.get("triples") or 0)
            - (p.get("hr") or 0)
            + (p.get("doubles") or 0) * 2
            + (p.get("triples") or 0) * 3
            + (p.get("hr") or 0) * 4
        )
        p["_avg_raw"] = _safe_div(h, ab)
        p["_obp_raw"] = _safe_div(h + bb + hbp, pa)
        p["_slg_raw"] = _safe_div(tb, ab)
        avg_vals.append(p["_avg_raw"])
        obp_vals.append(p["_obp_raw"])
        slg_vals.append(p["_slg_raw"])

    # Compute THR composite scores for qualified players
    thr_vals = []
    for p in qualified:
        thr = p["_obp_raw"] * 0.40 + p["_slg_raw"] * 0.35 + p["_avg_raw"] * 0.25
        p["_thr_score"] = round(thr, 4)
        thr_vals.append(p["_thr_score"])

    # Assign heat levels to qualified players, clamped by graduated depth cap
    cap = _max_heat_for_depth(len(qualified), _BATTING_HEAT_TIERS)
    for p in qualified:
        heat = {}
        heat["avg"] = min(_percentile_to_level(_percentile_rank(p["_avg_raw"], avg_vals)), cap)
        heat["obp"] = min(_percentile_to_level(_percentile_rank(p["_obp_raw"], obp_vals)), cap)
        heat["slg"] = min(_percentile_to_level(_percentile_rank(p["_slg_raw"], slg_vals)), cap)
        heat["thr"] = min(_percentile_to_level(_percentile_rank(p["_thr_score"], thr_vals)), cap)
        p["_heat"] = heat

    # Small-sample players: zero heat, no THR score
    for p in batting:
        if p.get("_small_sample"):
            p["_heat"] = {"avg": 0, "obp": 0, "slg": 0, "thr": 0}
            p["_thr_score"] = 0.0
        # Clean up internal raw fields
        p.pop("_avg_raw", None)
        p.pop("_obp_raw", None)
        p.pop("_slg_raw", None)


def _compute_pitching_heat(pitching: list[dict]) -> None:
    """Compute heat-map levels for pitching stats (mutates in place).

    Heat levels are computed within the non-small-sample subset.
    ERA and WHIP are inverted (lower = better = higher heat).
    """
    qualified = [p for p in pitching if not p.get("_small_sample")]

    era_vals = []
    k9_vals = []
    whip_vals = []
    for p in qualified:
        ip_outs = p.get("ip_outs") or 0
        er = p.get("er") or 0
        so = p.get("so") or 0
        bb = p.get("bb") or 0
        h = p.get("h") or 0
        p["_era_raw"] = (er * 27) / ip_outs if ip_outs else 0.0
        p["_k9_raw"] = (so * 27) / ip_outs if ip_outs else 0.0
        p["_whip_raw"] = (bb + h) * 3 / ip_outs if ip_outs else 0.0
        era_vals.append(p["_era_raw"])
        k9_vals.append(p["_k9_raw"])
        whip_vals.append(p["_whip_raw"])

    # For inverted stats (ERA, WHIP), negate values so lower = better = higher rank
    neg_era_vals = [-v for v in era_vals]
    neg_whip_vals = [-v for v in whip_vals]

    # Compute pitching THR composite
    thr_vals = []
    for p in qualified:
        era_pct = _percentile_rank(-p["_era_raw"], neg_era_vals)
        k9_pct = _percentile_rank(p["_k9_raw"], k9_vals)
        whip_pct = _percentile_rank(-p["_whip_raw"], neg_whip_vals)
        thr = era_pct * 0.40 + k9_pct * 0.30 + whip_pct * 0.30
        p["_thr_score"] = round(thr, 4)
        thr_vals.append(p["_thr_score"])

    cap = _max_heat_for_depth(len(qualified), _PITCHING_HEAT_TIERS)
    for p in qualified:
        heat = {}
        # ERA inverted: lower ERA -> higher percentile -> higher heat
        heat["era"] = min(
            _percentile_to_level(_percentile_rank(-p["_era_raw"], neg_era_vals)),
            cap,
        )
        heat["k9"] = min(
            _percentile_to_level(_percentile_rank(p["_k9_raw"], k9_vals)),
            cap,
        )
        heat["whip"] = min(
            _percentile_to_level(_percentile_rank(-p["_whip_raw"], neg_whip_vals)),
            cap,
        )
        heat["thr"] = min(
            _percentile_to_level(_percentile_rank(p["_thr_score"], thr_vals)),
            cap,
        )
        p["_heat"] = heat

    for p in pitching:
        if p.get("_small_sample"):
            p["_heat"] = {"era": 0, "k9": 0, "whip": 0, "thr": 0}
            p["_thr_score"] = 0.0
        p.pop("_era_raw", None)
        p.pop("_k9_raw", None)
        p.pop("_whip_raw", None)


def _compute_key_players(
    batting: list[dict], pitching: list[dict]
) -> dict[str, dict | None]:
    """Identify top pitcher (by IP) and top batter (by OBP) among qualified players."""
    # Top pitcher: highest ip_outs among non-small-sample
    top_pitcher = None
    for p in pitching:
        if p.get("_small_sample"):
            continue
        ip_outs = p.get("ip_outs") or 0
        if ip_outs < _KEY_PITCHER_MIN_OUTS:
            continue
        if top_pitcher is None or ip_outs > (top_pitcher.get("ip_outs") or 0):
            top_pitcher = p

    if top_pitcher is not None:
        ip_outs = top_pitcher.get("ip_outs") or 0
        top_pitcher = {
            "name": top_pitcher.get("name", "Unknown"),
            "era": top_pitcher.get("era", "-"),
            "k9": top_pitcher.get("k9", "-"),
            "ip": ip_display(ip_outs),
        }

    # Top batter: highest OBP among non-small-sample
    top_batter = None
    best_obp = -1.0
    for b in batting:
        if b.get("_small_sample"):
            continue
        pa = b["_pa"]
        if pa < _KEY_BATTER_MIN_PA:
            continue
        h = b.get("h") or 0
        bb = b.get("bb") or 0
        hbp = b.get("hbp") or 0
        obp = _safe_div(h + bb + hbp, pa)
        if obp > best_obp:
            best_obp = obp
            top_batter = b

    if top_batter is not None:
        pa = top_batter["_pa"]
        h = top_batter.get("h") or 0
        bb = top_batter.get("bb") or 0
        hbp = top_batter.get("hbp") or 0
        ab = top_batter.get("ab") or 0
        tb = (
            h
            - (top_batter.get("doubles") or 0)
            - (top_batter.get("triples") or 0)
            - (top_batter.get("hr") or 0)
            + (top_batter.get("doubles") or 0) * 2
            + (top_batter.get("triples") or 0) * 3
            + (top_batter.get("hr") or 0) * 4
        )
        obp_val = _safe_div(h + bb + hbp, pa)
        slg_val = _safe_div(tb, ab)
        top_batter = {
            "name": top_batter.get("name", "Unknown"),
            "obp": f".{int(obp_val * 1000):03d}" if pa > 0 else "-",
            "slg": f".{int(slg_val * 1000):03d}" if ab > 0 else "-",
            "pa": pa,
        }

    return {"top_pitcher": top_pitcher, "top_batter": top_batter}


def _build_team_spray_uri(spray_charts_raw: dict[str, list[dict]]) -> str | None:
    """Aggregate all player spray events into a team spray chart.

    Returns a base64 data URI if total events >= threshold, else None.
    """
    all_events = []
    for events in spray_charts_raw.values():
        if events:
            all_events.extend(events)
    if len(all_events) < _MIN_BIP_TEAM_SPRAY:
        return None
    try:
        return _encode_spray_chart(all_events, title="Team Spray Chart")
    except Exception:  # noqa: BLE001
        logger.warning("Failed to render team spray chart", exc_info=True)
        return None


def _build_spray_player_stats(
    spray_charts_raw: dict[str, list[dict]],
    batting_lookup: dict[str, dict],
) -> dict[str, dict]:
    """Build per-player stats dict for spray chart display.

    Returns a dict mapping player_id to enriched stats including:
    avg, obp, slg (str), pa, bip_count (int), jersey_number (str|None),
    zones (dict[str, int]), contacts (dict[str, int]).
    """
    from src.charts.spray import classify_field_zone, contact_type_label, format_baseball_stat

    result: dict[str, dict] = {}
    for player_id, events in spray_charts_raw.items():
        batter = batting_lookup.get(player_id)
        if batter:
            h = batter.get("h") or 0
            ab = batter.get("ab") or 0
            bb = batter.get("bb") or 0
            hbp = batter.get("hbp") or 0
            shf = batter.get("shf") or 0
            doubles = batter.get("doubles") or 0
            triples = batter.get("triples") or 0
            hr = batter.get("hr") or 0
            pa = batter.get("_pa", 0)
            jersey_number = batter.get("jersey_number")

            avg = format_baseball_stat(h, ab)
            obp = format_baseball_stat(h + bb + hbp, ab + bb + hbp + shf)
            slg = format_baseball_stat(
                h + doubles + 2 * triples + 3 * hr, ab,
            )
        else:
            avg = "-"
            obp = "-"
            slg = "-"
            pa = 0
            jersey_number = None

        # Zone classification
        zones = {"left": 0, "center": 0, "right": 0}
        contacts = {"gb": 0, "ld": 0, "fb": 0, "pu": 0, "bu": 0}
        for ev in (events or []):
            x = ev.get("x")
            y = ev.get("y")
            if x is not None and y is not None:
                zones[classify_field_zone(x, y)] += 1
            ct = contact_type_label(ev.get("play_type"))
            if ct:
                contacts[ct] += 1

        result[player_id] = {
            "avg": avg,
            "obp": obp,
            "slg": slg,
            "pa": pa,
            "bip_count": len(events) if events else 0,
            "jersey_number": jersey_number,
            "zones": zones,
            "contacts": contacts,
        }
    return result


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
              ``our_score`` (int), ``their_score`` (int), ``opponent_name``
              (str), ``is_home`` (bool) -- last 5 games, most recent first.
              May be empty or absent.
            - ``pitching``: list of player stat dicts (see pitching table
              columns). Each dict should include ``jersey_number``, ``name``,
              ``era``, ``k9``, ``whip``, ``games``, ``ip_outs``, ``h``,
              ``er``, ``bb``, ``so``, ``pitches``, ``strike_pct``.
            - ``batting``: list of player stat dicts. Each dict should include
              ``jersey_number``, ``name``, ``games``, ``ab``, ``h``, ``bb``,
              ``hbp``, ``shf``, ``doubles``, ``triples``, ``hr``, ``so``,
              ``sb``, ``cs``, ``rbi``.
            - ``spray_charts``: dict mapping player_id (str) to list of
              event dicts (each with ``x``, ``y``, ``play_result``,
              ``play_type``). May be empty or absent.
            - ``roster``: list of dicts with ``jersey_number``, ``name``,
              ``position``.
            - ``runs_scored_avg``: float or None
            - ``runs_allowed_avg``: float or None

    Returns:
        Complete HTML string ready to be written to a file.
    """
    env = _build_jinja_env()
    template = env.get_template(_TEMPLATE_NAME)

    # Shallow-copy so we don't mutate the caller's data
    batting = [dict(b) for b in data.get("batting") or []]
    pitching = [dict(p) for p in data.get("pitching") or []]

    # Enrich batting
    _compute_batting_enrichments(batting)
    _compute_batting_heat(batting)

    # Enrich pitching
    for pitcher in pitching:
        ip_outs = pitcher.get("ip_outs") or 0
        pitcher["_small_sample"] = ip_outs < _MIN_IP_OUTS_PITCHING
    _compute_pitching_heat(pitching)

    # Key players
    key_players = _compute_key_players(batting, pitching)

    # Build batting lookup for spray stats
    batting_lookup: dict[str, dict] = {}
    for player in batting:
        pid = player.get("player_id")
        if pid is not None:
            batting_lookup[pid] = player

    # Build spray chart data URIs for players meeting the BIP threshold
    spray_data: dict[str, str] = {}  # player_id -> data URI
    spray_charts_raw = data.get("spray_charts") or {}

    for player_id, events in spray_charts_raw.items():
        if not events or len(events) < _MIN_BIP_SPRAY:
            continue
        try:
            data_uri = _encode_spray_chart(events, title=None)
            spray_data[player_id] = data_uri
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to render spray chart for player %s", player_id,
                exc_info=True,
            )

    # Team spray chart
    team_spray_uri = _build_team_spray_uri(spray_charts_raw)

    # Spray player stats
    spray_player_stats = _build_spray_player_stats(spray_charts_raw, batting_lookup)

    # Format recent form as a compact string (backward compat)
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

    # Runs averages
    runs_scored_raw = data.get("runs_scored_avg")
    runs_allowed_raw = data.get("runs_allowed_avg")
    runs_scored_avg = f"{runs_scored_raw:.1f}" if runs_scored_raw is not None else None
    runs_allowed_avg = (
        f"{runs_allowed_raw:.1f}" if runs_allowed_raw is not None else None
    )

    context = {
        "team": data.get("team") or {},
        "generated_at": data.get("generated_at", ""),
        "expires_at": data.get("expires_at", ""),
        "freshness_date": data.get("freshness_date"),
        "game_count": data.get("game_count", 0),
        "recent_form": recent_form,
        "recent_form_str": recent_form_str,
        "pitching": pitching,
        "batting": batting,
        "spray_data": spray_data,
        "spray_player_stats": spray_player_stats,
        "team_spray_uri": team_spray_uri,
        "key_players": key_players,
        "runs_scored_avg": runs_scored_avg,
        "runs_allowed_avg": runs_allowed_avg,
        "roster": data.get("roster") or [],
        "has_pitching": bool(pitching),
        "has_batting": bool(batting),
        "has_spray": bool(spray_data),
        "has_recent_form": bool(recent_form_str),
    }

    return template.render(**context)
