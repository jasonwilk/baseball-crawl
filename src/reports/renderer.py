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


def _encode_spray_chart(
    events: list[dict],
    title: str | None = None,
    figsize: tuple[float, float] = (3, 3),
) -> str:
    """Render a spray chart and return a base64-encoded data URI string."""
    from src.charts.spray import render_spray_chart

    png_bytes = render_spray_chart(events, title=title, figsize=figsize)
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
            "workload_subline": top_pitcher.get("_workload_subline", ""),
            "rest_date": top_pitcher.get("_rest_date", ""),
            "p7d_display": top_pitcher.get("_p7d_display", "\u2014"),
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
        return _encode_spray_chart(all_events, title="Team Spray Chart", figsize=(6, 6))
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


def _format_pct(value: float | None) -> str:
    """Format a ratio as a percentage string, e.g. 0.625 -> '62.5%'."""
    if value is None:
        return "\u2014"
    return f"{value * 100:.1f}%"


def _format_rate(value: float | None) -> str:
    """Format a rate stat to one decimal, e.g. 3.82 -> '3.8'."""
    if value is None:
        return "\u2014"
    return f"{value:.1f}"


def _format_plays_pitching(pitching: list[dict]) -> None:
    """Add formatted plays-derived pitching columns (mutates in place)."""
    for p in pitching:
        p["_fps_pct"] = _format_pct(p.get("fps_pct"))
        p["_pitches_per_bf"] = _format_rate(p.get("pitches_per_bf"))


def _format_plays_batting(batting: list[dict]) -> None:
    """Add formatted plays-derived batting columns (mutates in place)."""
    for b in batting:
        b["_qab_pct"] = _format_pct(b.get("qab_pct"))
        b["_pitches_per_pa"] = _format_rate(b.get("pitches_per_pa"))


def _format_short_date(iso_date: str) -> str:
    """Format an ISO date as ``'Mar 28'`` for print/PDF fallback."""
    import datetime as _dt

    try:
        d = _dt.datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{d.strftime('%b')} {d.day}"
    except (ValueError, TypeError):
        return iso_date


def _enrich_pitchers_workload(
    pitching: list[dict],
    workload: dict[str, dict],
) -> None:
    """Merge workload data into pitcher dicts for standalone report rendering.

    Adds ``_rest_date``, ``_rest_display``, ``_p7d_display``, and
    ``_workload_subline`` keys.  The report template uses ``_rest_date`` in a
    ``data-date`` attribute for JS upgrade; ``_rest_display`` is the
    server-rendered fallback (formatted date).
    """
    for pitcher in pitching:
        pid = pitcher.get("player_id")
        w = workload.get(pid) if pid else None
        if w is None:
            pitcher["_rest_date"] = ""
            pitcher["_rest_display"] = "\u2014"
            pitcher["_p7d_display"] = "\u2014"
            pitcher["_workload_subline"] = "No recent outings"
            continue

        last_date = w["last_outing_date"]
        days_ago = w["last_outing_days_ago"]

        # Server-rendered date (PDF/print fallback)
        if last_date:
            pitcher["_rest_date"] = last_date
            pitcher["_rest_display"] = _format_short_date(last_date)
        else:
            pitcher["_rest_date"] = ""
            pitcher["_rest_display"] = "\u2014"

        # P(7d) display -- branch on appearances_7d first (see E-210 TN)
        appearances = w["appearances_7d"]
        pitches_7d = w["pitches_7d"]
        if appearances is None:
            pitcher["_p7d_display"] = "\u2014"
        elif pitches_7d is None:
            pitcher["_p7d_display"] = f"?p ({appearances}g)"
        else:
            pitcher["_p7d_display"] = f"{pitches_7d}p ({appearances}g)"

        # Workload sub-line for key-player callout
        if days_ago is None:
            pitcher["_workload_subline"] = "No recent outings"
        else:
            pitcher["_workload_subline"] = (
                f"Last: {pitcher['_rest_display']} \u00b7 {pitcher['_p7d_display']}"
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

    # Enrich batting (including plays-derived stats formatting)
    _compute_batting_enrichments(batting)
    _format_plays_batting(batting)
    _compute_batting_heat(batting)

    # Enrich pitching (including plays-derived stats formatting)
    for pitcher in pitching:
        ip_outs = pitcher.get("ip_outs") or 0
        pitcher["_small_sample"] = ip_outs < _MIN_IP_OUTS_PITCHING
    _format_plays_pitching(pitching)
    _compute_pitching_heat(pitching)

    # Enrich pitchers with workload data
    pitching_workload = data.get("pitching_workload") or {}
    generation_date = data.get("generation_date") or ""
    _enrich_pitchers_workload(pitching, pitching_workload)

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

    # Sort spray charts by PA descending (most plate appearances first)
    spray_data = dict(
        sorted(
            spray_data.items(),
            key=lambda item: _compute_pa(batting_lookup.get(item[0], {})),
            reverse=True,
        )
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

    # Plays-derived team-level stats
    has_plays_data = data.get("has_plays_data", False)
    plays_game_count = data.get("plays_game_count", 0)
    game_count = data.get("game_count", 0)
    team_fps_pct = _format_pct(data.get("team_fps_pct"))
    team_pitches_per_pa = _format_rate(data.get("team_pitches_per_pa"))

    # Matchup section context (E-228-14).
    # ``matchup_data`` may be:
    #   - None: hide section entirely (our_team_id None or confidence=suppress).
    #   - EnrichedMatchup: full LLM-prose surface available.
    #   - MatchupAnalysis (bare): LLM unavailable or enrich failed (AC-6).
    matchup_ctx = _build_matchup_context(data.get("matchup_data"))

    context = {
        "team": data.get("team") or {},
        "generated_at": data.get("generated_at", ""),
        "expires_at": data.get("expires_at", ""),
        "freshness_date": data.get("freshness_date"),
        "game_count": game_count,
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
        "has_plays_data": has_plays_data,
        "plays_game_count": plays_game_count,
        "team_fps_pct": team_fps_pct,
        "team_pitches_per_pa": team_pitches_per_pa,
        "generation_date": generation_date,
        "starter_prediction": data.get("starter_prediction"),
        "enriched_prediction": data.get("enriched_prediction"),
        "show_predicted_starter": data.get("show_predicted_starter", True),
        "matchup": matchup_ctx,
    }

    return template.render(**context)


# ===========================================================================
# Matchup Game Plan section helpers (E-228-14)
# ===========================================================================
#
# Field classification (per AC-6 -- degrade-by-hiding for LLM-prose):
#
# LLM-prose (HIDDEN when LLM unavailable or enrich_matchup failed):
#   - game_plan_intro
#   - hitter_cues (per top-3 hitter)
#   - sb_profile_prose
#   - first_inning_prose
#   - loss_recipe_prose
#
# Deterministic engine output (ALWAYS rendered, regardless of LLM availability):
#   - threat_list (top-3 hitters: name, jersey, PA, supporting_stats)
#   - pull_tendency_notes (renderer formats citations from raw fields)
#   - sb_profile_summary (counts/rates)
#   - first_inning_summary (rates)
#   - loss_recipe_buckets (per-bucket counts)
#   - eligible_opposing_pitchers / eligible_lsb_pitchers
#   - data_notes (italic gray Note lines, mapped to sub-sections by .subsection)


_DATA_NOTE_SUBSECTIONS = (
    "top_hitters",
    "opposing_pitchers",
    "sb_profile",
    "first_inning",
    "loss_recipe",
    "lsb_pitchers",
)


def _format_pull_pct(pull_pct: float) -> str:
    """Format pull_pct as a whole-number percent (AC-4)."""
    return f"{int(round(pull_pct * 100))}%"


def _build_matchup_context(matchup_data: Any) -> dict[str, Any] | None:
    """Build the template-friendly matchup context dict.

    Returns None when no Game Plan section should render. Returns a dict
    when the Game Plan section should render -- the dict carries every
    field the template needs, with LLM-prose fields set to None when
    only a bare ``MatchupAnalysis`` is available (AC-6 fallback).
    """
    if matchup_data is None:
        return None

    # Late import to avoid circular import.
    from src.reports.llm_matchup import EnrichedMatchup
    from src.reports.matchup import MatchupAnalysis

    if isinstance(matchup_data, EnrichedMatchup):
        analysis: MatchupAnalysis = matchup_data.analysis
        game_plan_intro: str | None = matchup_data.game_plan_intro or None
        # Map hitter cues by player_id for template lookup.
        cue_by_pid: dict[str, str] = {
            cue.player_id: cue.cue
            for cue in matchup_data.hitter_cues
            if cue.cue
        }
        sb_profile_prose: str | None = matchup_data.sb_profile_prose or None
        first_inning_prose: str | None = matchup_data.first_inning_prose or None
        loss_recipe_prose: str | None = matchup_data.loss_recipe_prose or None
        has_llm_prose = True
    elif isinstance(matchup_data, MatchupAnalysis):
        analysis = matchup_data
        game_plan_intro = None
        cue_by_pid = {}
        sb_profile_prose = None
        first_inning_prose = None
        loss_recipe_prose = None
        has_llm_prose = False
    else:
        # Defensive: unexpected type -- hide the section.
        logger.warning(
            "Unexpected matchup_data type %s; hiding Game Plan section.",
            type(matchup_data).__name__,
        )
        return None

    # Suppress short-circuit (AC-5): never render when engine suppressed.
    if analysis.confidence == "suppress":
        return None

    # Build top-3 hitter rows. Each row carries enough for either rendering
    # path: name + jersey + PA badge + cue (LLM) OR raw stats (fallback).
    threat_rows: list[dict[str, Any]] = []
    for hitter in analysis.threat_list:
        threat_rows.append({
            "player_id": hitter.player_id,
            "name": hitter.name,
            "jersey_number": hitter.jersey_number,
            "pa": hitter.pa,
            "cue": cue_by_pid.get(hitter.player_id),  # None when bare
            "supporting_stats": list(hitter.supporting_stats),
        })

    # Pull-tendency notes -- renderer formats citation parenthetical
    # directly from raw fields (AC-4).
    pull_rows: list[dict[str, Any]] = []
    for note in analysis.pull_tendency_notes:
        pull_rows.append({
            "player_id": note.player_id,
            "name": note.name,
            "jersey_number": note.jersey_number,
            "pull_pct_display": _format_pull_pct(note.pull_pct),
            "bip_count": note.bip_count,
        })

    # Eligible-pitcher rows (light treatment -- AC-3 sub-sections 2 + 6).
    def _pitcher_row(p: Any) -> dict[str, Any]:
        return {
            "player_id": p.player_id,
            "name": p.name,
            "jersey_number": p.jersey_number,
            "last_outing_date": p.last_outing_date,
            "days_rest": p.days_rest,
            "last_outing_pitches": p.last_outing_pitches,
            "workload_7d": p.workload_7d,
        }

    opposing_pitchers = [
        _pitcher_row(p) for p in (analysis.eligible_opposing_pitchers or [])
    ]
    lsb_pitchers: list[dict[str, Any]] | None
    if analysis.eligible_lsb_pitchers is None:
        lsb_pitchers = None
    else:
        lsb_pitchers = [_pitcher_row(p) for p in analysis.eligible_lsb_pitchers]

    # Group data_notes by subsection. Multiple notes for the same
    # sub-section render in input order (AC-3).
    notes_by_subsection: dict[str, list[str]] = {
        key: [] for key in _DATA_NOTE_SUBSECTIONS
    }
    for note in analysis.data_notes:
        if note.subsection in notes_by_subsection:
            notes_by_subsection[note.subsection].append(note.message)
        else:
            # Defensive: drop unknown subsection rather than crashing.
            logger.warning(
                "Unknown data_note.subsection=%r; dropping note %r",
                note.subsection, note.message,
            )

    # Loss recipe buckets -- expose per-bucket counts (deterministic) plus
    # the LLM prose (when available).
    buckets = analysis.loss_recipe_buckets
    loss_recipe = {
        "starter_shelled_count": buckets.starter_shelled_early.count,
        "bullpen_couldnt_hold_count": buckets.bullpen_couldnt_hold.count,
        "close_game_lost_late_count": buckets.close_game_lost_late.count,
        "uncategorized_count": buckets.uncategorized_count,
        "total_losses": buckets.total_losses,
    }

    return {
        "confidence": analysis.confidence,
        "game_plan_intro": game_plan_intro,
        "has_llm_prose": has_llm_prose,
        "threat_rows": threat_rows,
        "pull_tendency_notes": pull_rows,
        "opposing_pitchers": opposing_pitchers,
        "lsb_pitchers": lsb_pitchers,
        "sb_profile_summary": dict(analysis.sb_profile_summary or {}),
        "sb_profile_prose": sb_profile_prose,
        "first_inning_summary": dict(analysis.first_inning_summary or {}),
        "first_inning_prose": first_inning_prose,
        "loss_recipe": loss_recipe,
        "loss_recipe_prose": loss_recipe_prose,
        "notes_by_subsection": notes_by_subsection,
    }
