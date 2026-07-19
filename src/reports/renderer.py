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
import html
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.api.helpers import era_basis_innings, format_avg, format_date, ip_display
logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "api" / "templates"
_TEMPLATE_NAME = "reports/scouting_report.html"

# Thresholds per coaching consultation and E-187
_MIN_PA_BATTING = 5
_MIN_IP_OUTS_PITCHING = 18  # 6 IP = 18 outs

# ERA-basis disclosure copy (E-264 TN-7). Verbatim -- do NOT paraphrase. Printed
# once under the Pitching table ONLY when the basis is assumed (fallback 7). The
# footnote deliberately says "game length", never the raw field innings_per_game.
ERA_ASSUMED_FOOTNOTE = (
    "* Game length not available from GameChanger for this team -- "
    "ERA assumed on a 7-inning basis."
)

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

# Footer trust-block coverage-severity thresholds (E-235-07 / TN-7, COACH-1).
# Severity is keyed off coverage % (N/M) ALONE: quiet >= 80%, flagged 50-79%,
# loud < 50%. Independent of the degraded-confidence signal.
_COVERAGE_QUIET_MIN = 0.80
_COVERAGE_FLAGGED_MIN = 0.50

# The generic, coach-facing degraded-confidence line (TN-7, COACH-1). Verbatim
# per the baseball-coach; the SPECIFIC operator flags (season fallback /
# name-only match) are NOT exposed to the coach -- only the fact of degraded
# confidence. Operator flags live on the admin list (story 06).
_DEGRADED_CONFIDENCE_LINE = (
    "⚠️ Data accuracy may be limited. "
    "Contact your operator to verify before the game."
)


def _build_jinja_env() -> Environment:
    """Create a Jinja2 environment with the required filters."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    env.filters["ip_display"] = ip_display
    env.filters["format_avg"] = format_avg
    env.filters["format_date"] = format_date
    # E-265-02 / spec §9: expose the existing rate formatters as template
    # filters so the Outings section can format E-265-01's raw dataclass floats
    # at the render boundary (formatting stays out of the derivation layer).
    env.filters["pct"] = _format_pct     # 0-1 ratio -> "75.0%" (em-dash on None)
    env.filters["rate"] = _format_rate   # 1-decimal (em-dash on None)
    env.filters["rate2"] = _format_era   # 2-decimal ERA/WHIP grain (em-dash on None)
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


def _total_bases(player: dict) -> int:
    """Compute total bases from a batter's line: ``h + 2B + 2*3B + 3*HR``.

    ``h`` is total hits (singles included), so each extra-base hit adds only
    the bases beyond the single already counted in ``h`` -- algebraically
    identical to ``1*1B + 2*2B + 3*3B + 4*HR`` and to the equivalent
    ``h - 2B - 3B - HR + 2*2B + 3*3B + 4*HR`` form previously inlined at the
    call sites.  Missing components coerce to 0.
    """
    h = player.get("h") or 0
    doubles = player.get("doubles") or 0
    triples = player.get("triples") or 0
    hr = player.get("hr") or 0
    return h + doubles + 2 * triples + 3 * hr


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
        tb = _total_bases(p)
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
        # ERA ranking uses the team's GC game-length basis in lockstep with the
        # displayed ERA (E-264 TN-5); K/9 stays on 27 (9-inning basis).
        basis = era_basis_innings(p.get("innings_per_game"))
        p["_era_raw"] = (er * basis * 3) / ip_outs if ip_outs else 0.0
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
        tb = _total_bases(top_batter)
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
            pa = batter.get("_pa", 0)
            jersey_number = batter.get("jersey_number")

            avg = format_baseball_stat(h, ab)
            obp = format_baseball_stat(h + bb + hbp, ab + bb + hbp + shf)
            slg = format_baseball_stat(_total_bases(batter), ab)
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


def _format_era(value: float | None) -> str:
    """Format an ERA/WHIP-grain rate to two decimals, e.g. 3.5 -> '3.50'.

    Matches the sitewide 2-decimal ERA/WHIP convention (E-265-03 spec \u00a79);
    returns an em-dash on None like the other rate formatters.
    """
    if value is None:
        return "\u2014"
    return f"{value:.2f}"


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
            pitcher["_rest_display"] = format_date(last_date)
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


def _build_trust_block(data: dict[str, Any]) -> dict[str, Any]:
    """Build the footer trust-block context (E-235-07 / TN-7).

    Consumes the inputs story 03 threaded into the render ``data`` dict (M, N,
    K, spray availability, generated date, ``degraded_confidence``) and derives
    the coach-facing footer fields:

    - ``m`` / ``n``: games played to date (M) and games we have data for (N).
    - ``k`` / ``has_pitch_detail``: pitch-detail game count and a K>0 flag
      (when K==0 the template shows "No pitch-detail data", not "for 0 games"
      -- COACH-2).
    - ``coverage_pct`` / ``coverage_known``: N/M ratio, ``None`` when M is
      unavailable (the footer then degrades to N + the freshness date with no
      broken ratio -- AC-4 / Open Questions).
    - ``severity``: ``quiet`` (>=80%), ``flagged`` (50-79%), ``loud`` (<50%),
      keyed off coverage % ALONE (COACH-1). Defaults to ``quiet`` when coverage
      is unknown (no alarming state without the data to justify it).
    - ``degraded_confidence`` / ``degraded_line``: the generic warning, shown
      in ALL severity states whenever the flag is set, INDEPENDENT of coverage
      (COACH-1). Never names the specific operator flags.

    Coverage severity and degraded confidence are deliberately INDEPENDENT
    signals -- the template must render the degraded line in quiet/flagged/loud
    alike.
    """
    m = data.get("completed_games")            # M -- games played to date
    n = data.get("completed_games_with_data")  # N -- games we have data for
    k = data.get("plays_game_count") or 0      # K -- pitch-detail game count

    coverage_pct: float | None = None
    severity = "quiet"
    if m is not None and m > 0 and n is not None:
        coverage_pct = n / m
        if coverage_pct >= _COVERAGE_QUIET_MIN:
            severity = "quiet"
        elif coverage_pct >= _COVERAGE_FLAGGED_MIN:
            severity = "flagged"
        else:
            severity = "loud"

    degraded_confidence = bool(data.get("degraded_confidence"))
    return {
        "m": m,
        "n": n,
        "k": k,
        "has_pitch_detail": k > 0,
        "spray_available": bool(data.get("spray_available")),
        "coverage_pct": coverage_pct,
        "coverage_known": coverage_pct is not None,
        "severity": severity,
        "degraded_confidence": degraded_confidence,
        "degraded_line": _DEGRADED_CONFIDENCE_LINE if degraded_confidence else None,
    }


def _era_basis_disclosure(pitching: list[dict]) -> dict[str, Any]:
    """Derive the team-level ERA-basis label from the pitcher rows (E-264 TN-7).

    ``innings_per_game`` is a team-season constant carried identically on every
    ``get_season_pitching`` row (E-264-01), so the first row's value is the whole
    team's basis. A NULL value -- or a missing key on hand-built rows -- means the
    basis was never fetched, so it is ``assumed`` and the compute site fell back
    to 7 (``era_basis_innings``). Returns the pieces the template composes into
    ``ERA (N-inn)`` / ``ERA (N-inn)*`` plus the one-time footnote.

    Args:
        pitching: The report's pitcher rows (may be empty).

    Returns:
        ``{"basis": int, "assumed": bool, "footnote": str | None}``. ``footnote``
        is populated ONLY when ``assumed`` (AC-3).
    """
    raw = pitching[0].get("innings_per_game") if pitching else None
    assumed = raw is None
    return {
        "basis": era_basis_innings(raw),
        "assumed": assumed,
        "footnote": ERA_ASSUMED_FOOTNOTE if assumed else None,
    }


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

    # Plays-derived team-level stats (E-245 TN-5: two distinct coverage counts).
    has_plays_data = data.get("has_plays_data", False)
    plays_game_count = data.get("plays_game_count", 0)        # K -- games-with-plays (QAB%)
    pitch_charted_game_count = data.get("pitch_charted_game_count", 0)  # N -- charted games
    has_charted_data = pitch_charted_game_count > 0
    game_count = data.get("game_count", 0)                    # M -- games to date
    team_fps_pct = _format_pct(data.get("team_fps_pct"))
    team_pitches_per_pa = _format_rate(data.get("team_pitches_per_pa"))
    team_qab_pct = _format_pct(data.get("team_qab_pct"))

    # Outings (E-265/E-266): the list feeds the interleave; the map is the
    # per-Pitching-row join key (E-266-01 TN-5).
    pitcher_outings = data.get("pitcher_outings") or []

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
        # ERA-basis disclosure (E-264 TN-7): team-level basis + assumed flag the
        # template renders on the Pitching ERA header, the key-player card, and
        # the conditional footnote.
        "era_basis": _era_basis_disclosure(pitching),
        "has_spray": bool(spray_data),
        "has_recent_form": bool(recent_form_str),
        "has_plays_data": has_plays_data,
        "plays_game_count": plays_game_count,
        "pitch_charted_game_count": pitch_charted_game_count,
        "has_charted_data": has_charted_data,
        "team_fps_pct": team_fps_pct,
        "team_pitches_per_pa": team_pitches_per_pa,
        "team_qab_pct": team_qab_pct,
        "generation_date": generation_date,
        "starter_prediction": data.get("starter_prediction"),
        "enriched_prediction": data.get("enriched_prediction"),
        "show_predicted_starter": data.get("show_predicted_starter", True),
        # Outings Breakdown (E-265 / E-266). Default False so a render_report
        # call made WITHOUT the key (older callers, tests) leaves the section
        # unrendered -- the byte-identical-when-unset contract.
        "show_pitcher_outings": data.get("show_pitcher_outings", False),
        "pitcher_outings": pitcher_outings,
        # E-266-01 (TN-5): the interleave join map. The template does an O(1)
        # `pitcher_outings_map.get(pitcher.player_id)` per Pitching row to place
        # each pitcher's detail row immediately after its row -- a no-outings
        # pitcher is an explicit `.get()->None` guard, not a silent Jinja
        # Undefined. Built unconditionally (it is only emitted behind the flag).
        "pitcher_outings_map": {p.player_id: p for p in pitcher_outings},
        # Footer trust block (E-235-07 / TN-7).
        "trust_block": _build_trust_block(data),
    }

    return template.render(**context)


def render_no_games_page(team_name: str, completed_games: int = 0,
                         completed_games_with_data: int = 0) -> str:
    """Render the minimal no-completed-games page (E-235-03 gate (a), TN-7).

    Produced when a generation finds zero completed games WITH data. It is a
    self-contained, shareable HTML page carrying the coach-facing message --
    NOT a 404 and NOT a silent empty "ready" report. The public serve route
    serves it like any other report file (for ``reports.status = 'no_games'``).

    The coach-facing copy branches on M (``completed_games``, games played to
    date) vs N (``completed_games_with_data``, games we have box score data for;
    always 0 when this page is produced) per E-236 TN-5 / coach C1:

    - M == 0: no games on record yet for the team this season.
    - M > 0, N == 0: games were played, but no box score data is available --
      the modal pre-game scouting case (opponent has scheduled/played games but
      no scorebook). The copy interpolates M (games played), NOT N (0).

    Args:
        team_name: The team's display name (interpolated into the message,
            HTML-escaped).
        completed_games: M -- completed games played to date.
        completed_games_with_data: N -- completed games with box score data
            (0 by construction when this page is produced).

    Returns:
        Complete HTML string ready to be written to a file.
    """
    safe_name = html.escape(team_name or "this team")
    # Coach wording is authoritative (TN-5 / C1); keep it verbatim. The copy
    # MUST NOT say "check back later" (at pre-game, "later" is irrelevant).
    if completed_games > 0 and completed_games_with_data == 0:
        heading = "No box score data"
        message = (
            f"{safe_name} has played {completed_games} games this season, "
            "but no box score data is available in GameChanger."
        )
    else:
        heading = "No games on record"
        message = f"No games on record for {safe_name} this season."
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{heading} — {safe_name}</title>\n"
        "<style>\n"
        "  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;\n"
        "         background: #f8fafc; color: #1e293b; margin: 0; padding: 2rem; }\n"
        "  .card { max-width: 32rem; margin: 4rem auto; background: #fff;\n"
        "          border: 1px solid #e2e8f0; border-radius: 0.75rem;\n"
        "          padding: 2rem; text-align: center;\n"
        "          box-shadow: 0 1px 3px rgba(0,0,0,0.06); }\n"
        "  h1 { font-size: 1.25rem; margin: 0 0 0.75rem; }\n"
        "  p { font-size: 1rem; line-height: 1.5; margin: 0; color: #475569; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="card">\n'
        f"<h1>{heading} — {safe_name}</h1>\n"
        f"<p>{message}</p>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )
