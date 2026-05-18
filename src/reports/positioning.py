"""Tier 1 deterministic defensive positioning engine (E-229-02).

The engine computes positioning recommendations from the team-aggregate
reference frame: a whole-spray centroid per opponent, projected
position-scaled per epic TN-8 onto each of 6 fielder positions to
produce the per-position "star." Per-batter rows carry signed deviations
from each position's star (NOT a per-position-subset re-evaluation -
the E-228 R2 tautology is structurally avoided).

Public entry point::

    from src.reports.positioning import compute_positioning

    results = compute_positioning(conn, team_id=42, season_id="2026-spring-hs")

The engine is the SOLE writer for both ``batter_positioning`` and
``team_position_aggregate`` (epic TN-2). Render and Tier 2 LLM consume;
they never recompute.

Atomicity (epic TN-6): both tables refresh for an opponent in a single
SQLite transaction. The engine commits its own writes; callers do not
wrap.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from src.charts.spray import _raw_to_svg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Covered positions
# ---------------------------------------------------------------------------
COVERED_POSITIONS: tuple[str, ...] = ("LF", "CF", "RF", "3B", "SS", "2B")


# ---------------------------------------------------------------------------
# Sample-size thresholds (epic TN-4 / TN-5)
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
BIP_THIN_THRESHOLD: int = 10
"""Per-batter thin gate (TN-5): batters with strictly fewer than this many
placed BIP earn no outlier zone marker. Their BIPs DO contribute to the
team-aggregate centroid (they shape the star without earning a per-batter
shift)."""

# RECALIBRATE after first opponent dataset
LOW_CONFIDENCE_THRESHOLD: int = 50
"""Opponent-level confidence boundary (TN-4): opponents with strictly fewer
than this many placed BIP across all batters get ``is_low_confidence = 1``
on every ``team_position_aggregate`` row. At/above the threshold the flag
is 0."""


# ---------------------------------------------------------------------------
# Textbook base positions (epic TN-8 anchor + render-layer reference dot)
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
BASE_POSITIONS: dict[str, tuple[float, float]] = {
    # SVG-space (x, y) -- post-_raw_to_svg coordinates. Home plate is at
    # (160, 295); y=0 is the top of the canvas (deep CF).
    "LF": (75.0, 130.0),   # standard LF depth
    "CF": (160.0, 100.0),  # straight-away CF depth
    "RF": (245.0, 130.0),  # standard RF depth
    "3B": (110.0, 246.0),  # at the 3B bag
    "SS": (135.0, 220.0),  # left of 2B, on the dirt
    "2B": (185.0, 220.0),  # right of 2B, on the dirt
}
"""Textbook base position per covered position in SVG space (epic TN-8).

The engine uses these as the no-lean anchor for the position-scaled
projection: when the opponent's whole-spray centroid lands exactly at
the centroids-of-all-fielders mean (``_BASE_POSITION_ANCHOR``), every
position's star equals its ``BASE_POSITIONS`` value. As the opponent
centroid drifts, each star moves in the same SVG direction, scaled by
that position's range factor (``POSITION_SCALE_FACTORS``).

Render layer continues to use this constant to draw the faint textbook
reference dot per epic TN-14."""


# Anchor for the no-lean centroid: the mean of all six BASE_POSITIONS.
# If the opponent's whole-spray centroid sits here, every star equals
# its textbook BASE_POSITIONS value.
_BASE_POSITION_ANCHOR: tuple[float, float] = (
    sum(p[0] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS),
    sum(p[1] for p in BASE_POSITIONS.values()) / len(BASE_POSITIONS),
)


# ---------------------------------------------------------------------------
# Position-scaled projection factors (epic TN-8)
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
POSITION_SCALE_FACTORS: dict[str, tuple[float, float]] = {
    # (x_factor, y_factor) per position. Outfielders cover more SVG range
    # than infielders, so the same centroid displacement = bigger physical
    # adjustment for LF than for 2B. Middle infielders share the keystone
    # and shade less aggressively than the corner.
    "LF": (1.0, 1.0),
    "CF": (1.0, 1.0),
    "RF": (1.0, 1.0),
    "3B": (0.4, 0.4),
    "SS": (0.5, 0.5),
    "2B": (0.5, 0.5),
}
"""Per-position scaling factors for the team-aggregate projection (TN-8).

Outfielders: 1.0 (full transfer of the centroid lean). Middle infielders
(SS, 2B): 0.5 (half-shade — the keystone is shared). Corner infielder
(3B): 0.4 (slight shade — corner positions are anchored by the bag).
These are provisional anchors; the first-real-opponent calibration pass
(epic Rollout) tunes them."""


# ---------------------------------------------------------------------------
# Per-axis quantization ladders (epic TN-15)
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
DIRECTION_DEVIATION_THRESHOLDS: tuple[float, float] = (15.0, 40.0)
"""Direction (L-R, SVG x) ordinal-bucket thresholds. ``|d| < 15`` -> 0
(on star); ``15 <= |d| < 40`` -> ±1 (slight shade); ``|d| >= 40`` -> ±2
(significant shade). Sign of bucket equals sign of the x-delta:
negative = toward LF, positive = toward RF.

Two distinct ladders exist (this and DEPTH_*) because :func:`_raw_to_svg`
is anisotropic; a single shared ladder would silently re-introduce the
anisotropy bug."""

# RECALIBRATE after first opponent dataset
DEPTH_DEVIATION_THRESHOLDS: tuple[float, float] = (10.0, 25.0)
"""Depth (in-out, SVG y) ordinal-bucket thresholds. ``|d| < 10`` -> 0;
``10 <= |d| < 25`` -> ±1; ``|d| >= 25`` -> ±2.

Sign convention (TN-15): negative = "in" (toward home plate),
positive = "deep" (toward CF wall). The depth offset is computed as
``star_y - batter_centroid_y`` so that a batter centered closer to home
plate (larger SVG y) yields a negative depth_offset (in)."""


# ---------------------------------------------------------------------------
# Zone vocabulary (epic TN-3 sign-rule table)
# ---------------------------------------------------------------------------
# Sign convention (TN-3): direction negative = left, positive = right;
# depth negative = in (toward home), positive = deep (toward CF wall).
# `(0, 0)` deviation -> NULL (the star itself, no zone label).
_ZONE_SIGN_TABLE: dict[tuple[int, int], str] = {
    (-1, -1): "A",  # in + left
    (-1,  0): "B",  # left
    (-1,  1): "C",  # deep + left
    ( 0, -1): "D",  # in
    ( 0,  1): "E",  # deep
    ( 1, -1): "F",  # in + right
    ( 1,  0): "G",  # right
    ( 1,  1): "H",  # deep + right
}


def _sign(n: int) -> int:
    """Return -1 / 0 / 1 for negative / zero / positive integer."""
    if n < 0:
        return -1
    if n > 0:
        return 1
    return 0


def _quantize_to_zone(
    direction_dev: int,
    depth_dev: int,
) -> str | None:
    """Map ``(direction_deviation, depth_deviation)`` to zone letter A-H.

    Per epic TN-3: only the SIGN of each axis determines the letter;
    magnitude is ignored (the field-plot position carries magnitude per
    TN-5). ``(0, 0)`` -> NULL (the batter is at the star).
    """
    return _ZONE_SIGN_TABLE.get((_sign(direction_dev), _sign(depth_dev)))


def _quantize_axis(signed_delta: float, thresholds: tuple[float, float]) -> int:
    """Quantize a signed SVG-space delta to an ordinal step bucket.

    Bucket scheme: 0 = on star, ±1 = slight shade, ±2 = significant
    shade. Sign of bucket equals sign of ``signed_delta``.
    """
    mag = abs(signed_delta)
    sign = 1 if signed_delta > 0 else (-1 if signed_delta < 0 else 0)
    if mag < thresholds[0]:
        return 0
    if mag < thresholds[1]:
        return sign * 1
    return sign * 2


# ---------------------------------------------------------------------------
# Engine result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PerPositionRow:
    """One ``batter_positioning`` row's worth of non-PK columns.

    Per-batter fields ``bip_count``, ``hr_count``, ``is_thin`` are
    denormalized identically across the batter's 6 rows (TN-5 / TN-7).
    The per-position fields ``direction_deviation``, ``depth_deviation``,
    ``zone_id`` vary across positions because the team-aggregate star
    varies across positions.
    """

    position: str
    direction_deviation: int
    depth_deviation: int
    zone_id: str | None
    is_thin: int
    bip_count: int
    hr_count: int


@dataclass(frozen=True)
class TeamAggregateRow:
    """One ``team_position_aggregate`` row.

    Holds the per-position star (in SVG space), the opponent BIP count,
    and the engine-time low-confidence flag. The engine emits 6 rows per
    opponent (one per covered position).
    """

    position: str
    star_x: float
    star_y: float
    bip_count: int
    is_low_confidence: int


# Note: renderer (E-229-05) and LLM (E-229-09) consumers still read v1 fields -- `bb report generate` will crash mid-epic until those stories land.
@dataclass(frozen=True)
class BatterPositioningResult:
    """Per-batter Tier 1 result.

    Carries the four PK/provenance fields and the six per-position rows.
    The Tier 2 LLM contract input shape (E-229-09) consumes this object;
    fields beyond the 6 per-position rows may be added there.
    """

    player_id: str
    team_id: int
    season_id: str
    perspective_team_id: int
    per_position_rows: tuple[PerPositionRow, ...]
    bip_count: int
    hr_count: int
    is_thin: int


# ---------------------------------------------------------------------------
# Stage 1: team-aggregate centroid + position-scaled projection (TN-8)
# ---------------------------------------------------------------------------


def _compute_team_aggregate(
    placed_events: list[dict[str, Any]],
) -> dict[str, TeamAggregateRow]:
    """Compute per-position team-aggregate stars from the whole-spray centroid.

    Per epic TN-8: the whole-spray centroid (in SVG space) represents
    the opponent's directional lean. Each position's star is the
    textbook ``BASE_POSITIONS`` for that position offset in the
    direction of the lean, SCALED by per-position range
    (``POSITION_SCALE_FACTORS``).

    All batters' placed BIPs contribute to the centroid regardless of
    individual ``is_thin`` status (per AC-4).

    Returns a dict keyed by position; one row per covered position. When
    there are zero placed events, the centroid anchor is the textbook
    no-lean anchor and every star equals its textbook ``BASE_POSITIONS``
    value.
    """
    total_bip = len(placed_events)
    is_low_confidence = 1 if total_bip < LOW_CONFIDENCE_THRESHOLD else 0

    if placed_events:
        sum_x = 0.0
        sum_y = 0.0
        for ev in placed_events:
            sx, sy = _raw_to_svg(ev["x"], ev["y"])
            sum_x += sx
            sum_y += sy
        centroid_x = sum_x / total_bip
        centroid_y = sum_y / total_bip
    else:
        # No data: centroid coincides with the no-lean anchor so every
        # star resolves to its textbook BASE_POSITIONS value.
        centroid_x = _BASE_POSITION_ANCHOR[0]
        centroid_y = _BASE_POSITION_ANCHOR[1]

    lean_x = centroid_x - _BASE_POSITION_ANCHOR[0]
    lean_y = centroid_y - _BASE_POSITION_ANCHOR[1]

    rows: dict[str, TeamAggregateRow] = {}
    for position in COVERED_POSITIONS:
        base_x, base_y = BASE_POSITIONS[position]
        fx, fy = POSITION_SCALE_FACTORS[position]
        star_x = base_x + lean_x * fx
        star_y = base_y + lean_y * fy
        rows[position] = TeamAggregateRow(
            position=position,
            star_x=star_x,
            star_y=star_y,
            bip_count=total_bip,
            is_low_confidence=is_low_confidence,
        )
    return rows


# ---------------------------------------------------------------------------
# Stage 2: per-batter deviation against each position's star (TN-3 / TN-15)
# ---------------------------------------------------------------------------


def _compute_batter_deviations(
    placed_events: list[dict[str, Any]],
    hr_count: int,
    team_aggregate: dict[str, TeamAggregateRow],
) -> tuple[tuple[PerPositionRow, ...], int, int]:
    """Compute the 6 per-position deviation rows for a single batter.

    The batter's centroid (in SVG space) is taken once. Each position's
    deviation is then computed against THAT position's team-aggregate
    star (NOT a per-position-subset re-evaluation - AC-9). The signed
    deviations are quantized into ordinal buckets, then mapped to the
    A-H zone vocabulary via the sign-rule table (TN-3).

    Returns ``(per_position_rows, bip_count, is_thin)``.

    Sign convention (TN-15):
      * direction negative = left (toward LF), positive = right (toward RF)
      * depth negative = "in" (toward home plate), positive = "deep"
        (toward CF wall)

    The depth offset is computed as ``star_y - batter_centroid_y`` so
    that a batter sitting at a larger SVG y (closer to home plate) yields
    a negative ``depth_deviation`` (in).
    """
    bip_count = len(placed_events)
    is_thin = 1 if bip_count < BIP_THIN_THRESHOLD else 0

    if placed_events:
        sum_x = 0.0
        sum_y = 0.0
        for ev in placed_events:
            sx, sy = _raw_to_svg(ev["x"], ev["y"])
            sum_x += sx
            sum_y += sy
        batter_x = sum_x / bip_count
        batter_y = sum_y / bip_count
    else:
        # No placed events for this batter - deviations are all zero
        # against every star (the batter sits at the star).
        batter_x = None
        batter_y = None

    rows: list[PerPositionRow] = []
    for position in COVERED_POSITIONS:
        star = team_aggregate[position]
        if batter_x is None or batter_y is None:
            direction_dev = 0
            depth_dev = 0
        else:
            delta_x = batter_x - star.star_x
            depth_offset = star.star_y - batter_y
            direction_dev = _quantize_axis(
                delta_x, DIRECTION_DEVIATION_THRESHOLDS,
            )
            depth_dev = _quantize_axis(
                depth_offset, DEPTH_DEVIATION_THRESHOLDS,
            )

        zone_id = _quantize_to_zone(direction_dev, depth_dev)

        rows.append(
            PerPositionRow(
                position=position,
                direction_deviation=direction_dev,
                depth_deviation=depth_dev,
                zone_id=zone_id,
                is_thin=is_thin,
                bip_count=bip_count,
                hr_count=hr_count,
            )
        )

    return tuple(rows), bip_count, is_thin


# ---------------------------------------------------------------------------
# Persistence (epic TN-6 atomicity)
# ---------------------------------------------------------------------------


_BATTER_INSERT_SQL = """
INSERT INTO batter_positioning (
    player_id, team_id, season_id, perspective_team_id, position,
    direction_deviation, depth_deviation, zone_id,
    is_thin, bip_count, hr_count
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_AGGREGATE_INSERT_SQL = """
INSERT INTO team_position_aggregate (
    team_id, season_id, perspective_team_id, position,
    star_x, star_y, bip_count, is_low_confidence
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def _persist(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    results: list[BatterPositioningResult],
    aggregates_by_perspective: dict[int, dict[str, TeamAggregateRow]],
) -> None:
    """Atomic delete-then-insert for both tables (epic TN-6).

    Single SQLite transaction wraps both DELETE-by-scope and INSERTs.
    The DELETE scope is ``(team_id, season_id)`` -- ALL perspectives
    rebuild together so stale perspectives that dropped out between runs
    disappear (delete-then-insert scope rule: DELETE scope == INSERT
    scope). The transaction always runs even when ``results`` is empty;
    a zero-row rebuild is a valid state.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "DELETE FROM batter_positioning WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        )
        conn.execute(
            "DELETE FROM team_position_aggregate WHERE team_id = ? AND season_id = ?",
            (team_id, season_id),
        )

        for perspective_team_id, aggregate_rows in aggregates_by_perspective.items():
            for position in COVERED_POSITIONS:
                row = aggregate_rows[position]
                conn.execute(
                    _AGGREGATE_INSERT_SQL,
                    (
                        team_id,
                        season_id,
                        perspective_team_id,
                        row.position,
                        row.star_x,
                        row.star_y,
                        row.bip_count,
                        row.is_low_confidence,
                    ),
                )

        for result in results:
            for row in result.per_position_rows:
                conn.execute(
                    _BATTER_INSERT_SQL,
                    (
                        result.player_id,
                        result.team_id,
                        result.season_id,
                        result.perspective_team_id,
                        row.position,
                        row.direction_deviation,
                        row.depth_deviation,
                        row.zone_id,
                        row.is_thin,
                        row.bip_count,
                        row.hr_count,
                    ),
                )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_positioning(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> list[BatterPositioningResult]:
    """Compute team-aggregate stars + per-batter deviations and persist atomically.

    Reads offensive ``spray_charts`` for ``(team_id, season_id)``,
    groups by ``perspective_team_id``, computes the team-aggregate
    centroid + per-position stars (TN-8) and per-batter deviations
    against those stars (TN-3 / TN-15), then writes both
    ``team_position_aggregate`` (6 rows per perspective) and
    ``batter_positioning`` (6 rows per batter per perspective) in a
    single SQLite transaction (TN-6).

    Per TN-6: rows in ``spray_charts`` with a NULL ``season_id`` are
    skipped; a WARNING is logged with the count. The engine commits its
    own writes.

    Args:
        conn: An open ``sqlite3.Connection`` with the
            ``002_batter_positioning.sql`` v2 migration applied.
        team_id: ``teams(id)`` INTEGER -- the scouted opponent.
        season_id: Season slug (e.g. ``"2026-spring-hs"``).

    Returns:
        One :class:`BatterPositioningResult` per
        ``(perspective_team_id, player_id)`` combination in scope.

    Raises:
        sqlite3.Error: Any DB error during the recompute triggers a
            ROLLBACK and re-raises. Prior committed state is preserved.
    """
    null_season_skipped = conn.execute(
        """
        SELECT COUNT(*) FROM spray_charts
        WHERE team_id = ? AND chart_type = 'offensive' AND season_id IS NULL
        """,
        (team_id,),
    ).fetchone()[0]
    if null_season_skipped:
        logger.warning(
            "compute_positioning: skipped %d spray_charts row(s) with NULL "
            "season_id (team_id=%d, season_id=%s)",
            null_season_skipped, team_id, season_id,
        )

    rows = conn.execute(
        """
        SELECT player_id, perspective_team_id, x, y, play_result, play_type
        FROM spray_charts
        WHERE team_id = ? AND chart_type = 'offensive' AND season_id = ?
        """,
        (team_id, season_id),
    ).fetchall()

    # Group by perspective -> player -> events. Track HR-with-NULL-coords
    # separately (over-the-fence HRs have no placed coords but count for
    # hr_count). Placed events are those with usable (x, y).
    grouped: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        if isinstance(row, sqlite3.Row):
            player_id = row["player_id"]
            perspective = row["perspective_team_id"]
            event = {
                "x": row["x"],
                "y": row["y"],
                "play_result": row["play_result"],
                "play_type": row["play_type"],
            }
        else:
            player_id, perspective, x, y, play_result, play_type = row
            event = {
                "x": x,
                "y": y,
                "play_result": play_result,
                "play_type": play_type,
            }
        grouped.setdefault(perspective, {}).setdefault(player_id, []).append(event)

    # Compute aggregates per perspective and per-batter rows.
    aggregates_by_perspective: dict[int, dict[str, TeamAggregateRow]] = {}
    results: list[BatterPositioningResult] = []
    for perspective, batters in grouped.items():
        # All placed events for the perspective feed the centroid.
        all_placed: list[dict[str, Any]] = []
        for events in batters.values():
            all_placed.extend(
                e for e in events
                if e.get("x") is not None and e.get("y") is not None
            )
        aggregates = _compute_team_aggregate(all_placed)
        aggregates_by_perspective[perspective] = aggregates

        for player_id, events in batters.items():
            placed = [
                e for e in events
                if e.get("x") is not None and e.get("y") is not None
            ]
            hr_count = sum(1 for e in events if e.get("play_result") == "home_run")
            per_position_rows, bip_count, is_thin = _compute_batter_deviations(
                placed, hr_count, aggregates,
            )
            results.append(
                BatterPositioningResult(
                    player_id=player_id,
                    team_id=team_id,
                    season_id=season_id,
                    perspective_team_id=perspective,
                    per_position_rows=per_position_rows,
                    bip_count=bip_count,
                    hr_count=hr_count,
                    is_thin=is_thin,
                )
            )

    _persist(conn, team_id, season_id, results, aggregates_by_perspective)

    return results
