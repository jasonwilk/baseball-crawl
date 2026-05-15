"""Tier 1 deterministic defensive positioning engine (E-228-02).

The engine reads ``spray_charts`` for a ``(team_id, season_id)`` scope --
grouping by ``perspective_team_id`` -- and computes positioning
recommendations per opposing batter per covered fielding position
(SS, 2B, 3B, LF, CF, RF). It writes the results to ``batter_positioning``
via delete-then-insert within one transaction. This module is the
auditable core of E-228: **no LLM in the decision path**.

Three stages (epic TN-3):

* **Stage A** -- compute the batter's optimal fielding point in SVG
  space from the BIP distribution, take the signed delta from
  :data:`BASE_POSITIONS`, and quantize each axis to a signed ordinal
  step bucket (``0`` / ``±1`` / ``±2``) via the per-axis ladders
  :data:`DIRECTION_DEVIATION_THRESHOLDS` and
  :data:`DEPTH_DEVIATION_THRESHOLDS`. Stage A is computed once per
  batter; deltas vary per position because :data:`BASE_POSITIONS` does.

* **Stage B** -- evaluated **per covered position**, not once per
  batter (epic TN-3 Stage B, round-2 rewrite). For each (batter,
  position) pair the engine restricts the batter's BIPs to the
  position's **responsibility subset** via the swappable seam
  :func:`bips_for_position` + :data:`POSITION_RESPONSIBILITY_SECTORS`
  (v1 ships fixed angular-zone + infield/outfield-depth geometry),
  then derives ``direction_shade`` from the dominant zone of that
  subset and ``depth_shade`` from the dominant
  :func:`src.charts.spray.contact_type_label` of that subset.
  Different positions can land on different ``direction_shade`` /
  ``depth_shade`` / ``call_state`` values for the same batter -- this
  is what makes ``team_state_call='MIXED'`` reachable from real data.

* **Stage C** -- apply the sample gates per position (epic TN-4
  applied to each position's subset) and quantize to one of the 8
  ``call_state`` enum keys: ``TRUE`` plus the six directional shades
  ``LEFT`` / ``LEFT_SHALLOW`` / ``LEFT_DEEP`` / ``RIGHT`` /
  ``RIGHT_SHALLOW`` / ``RIGHT_DEEP``, plus ``MIXED`` for the team-state
  call (epic TN-4a). The ``team_state_call`` is derived from the 6
  per-position ``call_state`` values and denormalized identically onto
  every row.

The direction vocabulary is **absolute** (left/center/right) -- batter
handedness is unavailable on every data path E-228 uses, so the engine
stores :func:`src.charts.spray.classify_field_zone` output directly
with no translation layer.

The display vocabulary block (e.g. ``LEFT_SHALLOW -> "SHADE LEFT IN"``)
is **not** in this module -- it lives in the render layer
(E-228-05) per epic TN-5's ownership split. This module writes only
absolute enum keys.

Public entry point::

    from src.reports.positioning import compute_positioning

    results = compute_positioning(conn, team_id=42, season_id="2026-spring-hs")
"""

from __future__ import annotations

import logging
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.charts.spray import (
    _raw_to_svg,
    classify_field_zone,
    contact_type_label,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Covered positions (epic Non-Goal: P/C/1B are situation-driven, not v1)
# ---------------------------------------------------------------------------
COVERED_POSITIONS: tuple[str, ...] = ("SS", "2B", "3B", "LF", "CF", "RF")


# ---------------------------------------------------------------------------
# Sample gate thresholds (epic TN-4)
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
BIP_THIN_THRESHOLD: int = 10
"""Batters with strictly fewer BIP than this fall to ``call_state='TRUE'`` and
``is_thin=1`` -- the 'not enough data' state. All six covered-position rows
are still written (the player-card render iterates positions)."""

# RECALIBRATE after first opponent dataset
BIP_DEPTH_THRESHOLD: int = 25
"""Below this BIP threshold the ``depth_shade`` is NULL (direction-lean only).
At or above, the depth knob is allowed to fire. ``depth_deviation`` follows
the same gate (NULL whenever ``depth_shade`` is NULL)."""

# RECALIBRATE after first opponent dataset
ZONE_MIN_BIP: int = 4
"""Per-zone gate: a candidate direction shade requires at least this many BIP
in the zone."""

# RECALIBRATE after first opponent dataset
ZONE_MIN_CONCENTRATION: float = 0.35
"""Per-zone gate: a candidate direction shade requires at least this share of
the batter's placed BIP in the zone (35%)."""

# RECALIBRATE after first opponent dataset
CONTACT_TYPE_MIN_COUNT: int = 4
"""Depth-knob gate: a dominant contact-type label requires at least this many
contact-type-tagged BIP to fire."""

# RECALIBRATE after first opponent dataset
CONTACT_TYPE_MIN_CONCENTRATION: float = 0.35
"""Depth-knob gate: a dominant contact-type label requires at least this share
(35%) of contact-type-tagged BIP to fire."""


# ---------------------------------------------------------------------------
# Stage A -- reference origin and per-axis quantization ladders
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
BASE_POSITIONS: dict[str, tuple[float, float]] = {
    # SVG-space (x, y) -- post-_raw_to_svg coordinates. Home plate is at
    # (160, 295); y=0 is the top of the canvas (deep CF).
    "SS": (135.0, 220.0),  # left side of 2B, on the dirt
    "2B": (185.0, 220.0),  # right side of 2B, on the dirt
    "3B": (110.0, 246.0),  # at the 3B bag
    "LF": (75.0, 130.0),   # standard LF depth
    "CF": (160.0, 100.0),  # straight-away CF depth
    "RF": (245.0, 130.0),  # standard RF depth
}
"""Stage A reference origin (epic TN-3 Stage A).

Per-position textbook base position in **SVG space**
(post-:func:`src.charts.spray._raw_to_svg`). Stage A computes the
batter's optimal fielding point (centroid of placed BIP) in SVG space,
takes ``centroid - BASE_POSITIONS[pos]``, and quantizes the per-axis
deltas via the two ladders below. Values are provisional; the migration
column comments in ``002_batter_positioning.sql`` reference this
definition rather than restating it (AC-1c single-source-of-truth)."""


# RECALIBRATE after first opponent dataset
DIRECTION_DEVIATION_THRESHOLDS: tuple[float, float] = (15.0, 40.0)
"""Stage A **direction (x / L-R axis) quantization ladder**.

Thresholds in SVG-space units on ``|delta_x|``. ``|d| < 15`` -> ``0``
(on base); ``15 <= |d| < 40`` -> ``±1`` (slight shade); ``|d| >= 40``
-> ``±2`` (significant shade). The sign of the bucket equals the sign
of the x-delta: negative = toward LF, positive = toward RF.

**This is one of two distinct per-axis ladders.** :data:`_raw_to_svg`
is anisotropic (x scale ~0.6926, y scale ~0.6447), so the SVG-delta
thresholds for x and y are not the same numbers. See also
:data:`DEPTH_DEVIATION_THRESHOLDS`. A single shared ladder would
silently re-introduce the anisotropy bug -- these are kept named and
documented as two distinct ladders by design (AC-1c anisotropy
guard)."""


# RECALIBRATE after first opponent dataset
DEPTH_DEVIATION_THRESHOLDS: tuple[float, float] = (10.0, 25.0)
"""Stage A **depth (y / in-out axis) quantization ladder**.

Thresholds in SVG-space units on the absolute depth offset, where
``depth_offset = BASE_POSITIONS[pos].y - centroid_y`` (positive =
deeper than base because SVG y=0 is at the top of the canvas, deep
CF). ``|d| < 10`` -> ``0`` (on base); ``10 <= |d| < 25`` -> ``±1``
(slight shade); ``|d| >= 25`` -> ``±2`` (significant shade). Sign:
negative = shallower than base, positive = deeper than base.

**This is the second of two distinct per-axis ladders.** It is named
and documented separately from :data:`DIRECTION_DEVIATION_THRESHOLDS`
because :data:`_raw_to_svg` is anisotropic (AC-1c anisotropy guard)."""


# ---------------------------------------------------------------------------
# MIXED rule -- adjacency lattice (epic TN-4a)
# ---------------------------------------------------------------------------
# RECALIBRATE after first opponent dataset
MIXED_NON_ADJACENT_PAIRS_THRESHOLD: int = 1
"""When at least one pair of qualifying (non-``TRUE``) per-position calls
lands in non-adjacent states on :data:`ADJACENCY_LATTICE`, the batter's
``team_state_call`` is ``MIXED``. Per TN-4a: '2 or more positions in
non-adjacent named states' -- a single such pair is sufficient evidence
of a 2+ split."""

ADJACENCY_LATTICE: tuple[str, ...] = (
    "LEFT_DEEP",
    "LEFT",
    "LEFT_SHALLOW",
    "TRUE",
    "RIGHT_SHALLOW",
    "RIGHT",
    "RIGHT_DEEP",
)
"""TN-4a adjacency chain. ``MIXED`` is *not* in the chain -- it is the
result of having 2+ positions land in non-adjacent named states on this
chain. Positions at ``TRUE`` (thin data / no tendency) do not by
themselves force ``MIXED``: they are excluded from the qualifying set
before adjacency is checked."""

_LATTICE_INDEX: dict[str, int] = {s: i for i, s in enumerate(ADJACENCY_LATTICE)}


# ---------------------------------------------------------------------------
# Stage B -- swappable zone-assignment seam (epic TN-3 Stage B)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZoneAssignment:
    """Output of the swappable zone-assignment seam (epic TN-3 Stage B).

    v1 ships a single ``zone`` label per BIP -- one of ``"left"``,
    ``"center"``, ``"right"`` -- from the fixed angular-sector
    geometry already in :mod:`src.charts.spray`. A future
    clustering-derived zone set replaces only the seam implementation
    (e.g. ``"deep_left_corner"``); the engine consumes this dataclass
    via its public ``zone`` attribute, so the swap is one layer.

    The engine MUST NOT reach past this dataclass into the seam's
    implementation -- direction/depth classification consumes only
    ``ZoneAssignment.zone`` (and the v1 ``"left"``/``"center"``/
    ``"right"`` vocabulary, which the engine compares against its own
    direction-shade conventions).
    """

    zone: str


def assign_zone(x: float, y: float) -> ZoneAssignment:
    """Zone-assignment seam (epic TN-3 Stage B).

    Pure geometry function. Given a raw API ``(x, y)`` coordinate for
    a BIP, returns the :class:`ZoneAssignment` for the v1 fixed
    angular-sector geometry. Wraps
    :func:`src.charts.spray.classify_field_zone`.

    **Seam contract**: the engine consumes only this function's return
    value, never the internals of :func:`classify_field_zone` or the
    underlying ``atan2`` math. Swap this function to change the zone
    geometry (e.g. to a clustering-derived zone set) without touching
    the engine.
    """
    return ZoneAssignment(zone=classify_field_zone(x, y))


# ---------------------------------------------------------------------------
# Per-position responsibility (epic TN-3 Stage B, round-2 rewrite)
# ---------------------------------------------------------------------------
# Each covered fielding position is responsible for a subset of the batter's
# BIPs -- the v1 responsibility geometry is the (direction_zone, depth_band)
# cross-product, where direction_zone is left/center/right from the swappable
# `assign_zone()` seam and depth_band is infield/outfield split by an SVG y
# threshold. Stage B's direction + depth knobs are then derived per position
# from the position-relevant subset (not the batter's whole spray), which is
# what makes different per-position `call_state` values (and `MIXED`) reachable
# from real data through `compute_positioning`.
#
# Geometry remains a swappable seam (epic TN-3 Stage B): swap
# `bips_for_position()` + `POSITION_RESPONSIBILITY_SECTORS` (and optionally
# `assign_zone()`) together to change to a clustering-derived zone set without
# touching the engine. v1 ships the fixed angular-and-depth-band geometry below.

# RECALIBRATE after first opponent dataset
INFIELD_OUTFIELD_SVG_Y_THRESHOLD: float = 200.0
"""Depth-band boundary in SVG space. ``svg_y >= 200`` is treated as the
infield band (closer to home plate at ``y=295``); ``svg_y < 200`` is the
outfield band (deeper, toward the top of the canvas at ``y=0``). The
value sits between SS/2B/3B base depths (~220-246) and LF/CF/RF base
depths (~100-130). Calibration may shift it as real BIP distributions
become available."""

# RECALIBRATE after first opponent dataset
POSITION_RESPONSIBILITY_SECTORS: dict[str, frozenset[tuple[str, str]]] = {
    # (direction_zone, depth_band) cells in each position's coverage area.
    # Outfielders cover their column of the outfield. Middle infielders
    # share the keystone (center, infield); the corner infielder owns its
    # corner alone. Cells are sets to keep the geometry seam compositional.
    "SS": frozenset({("left", "infield"), ("center", "infield")}),
    "2B": frozenset({("center", "infield"), ("right", "infield")}),
    "3B": frozenset({("left", "infield")}),
    "LF": frozenset({("left", "outfield")}),
    "CF": frozenset({("center", "outfield")}),
    "RF": frozenset({("right", "outfield")}),
}
"""Per-position responsibility cells (epic TN-3 Stage B).

Maps each covered position to its responsibility-sector cells in the
``(direction_zone, depth_band)`` space. Driven through the swappable
seam :func:`bips_for_position`, which filters a batter's BIPs to the
subset belonging to a position's responsibility. Provisional starting
values -- the seam interface stays constant when these cells change."""


def _depth_band(svg_y: float) -> str:
    """Classify a BIP's SVG y coordinate into the infield/outfield band."""
    return "infield" if svg_y >= INFIELD_OUTFIELD_SVG_Y_THRESHOLD else "outfield"


def bips_for_position(
    events: list[dict[str, Any]],
    position: str,
) -> list[dict[str, Any]]:
    """Per-position responsibility-subset seam (epic TN-3 Stage B).

    Pure filter function. Given the batter's placed BIP list and a
    covered position, returns the subset of BIPs that fall in
    ``position``'s responsibility cells per
    :data:`POSITION_RESPONSIBILITY_SECTORS`. Events with NULL ``x`` or
    ``y`` are skipped (they cannot be classified).

    **Seam contract**: the engine consumes only this function's return
    list, never the underlying responsibility-cell representation.
    Swap this function (along with :data:`POSITION_RESPONSIBILITY_SECTORS`
    and/or :func:`assign_zone`) to change the per-position
    responsibility geometry -- e.g. to a clustering-derived zone set
    -- without touching the engine.
    """
    cells = POSITION_RESPONSIBILITY_SECTORS[position]
    subset: list[dict[str, Any]] = []
    for ev in events:
        x = ev.get("x")
        y = ev.get("y")
        if x is None or y is None:
            continue
        zone = assign_zone(x, y).zone
        _, svg_y = _raw_to_svg(x, y)
        band = _depth_band(svg_y)
        if (zone, band) in cells:
            subset.append(ev)
    return subset


# ---------------------------------------------------------------------------
# Engine return shape (epic TN-1a -- the Tier 1 / Tier 2 interface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PerZoneContactEntry:
    """One (zone, contact_type) cell of the per-batter aggregation."""

    zone: str
    contact_type: str | None
    count: int


@dataclass(frozen=True)
class PerZoneAggregation:
    """Pre-aggregated zone / contact-type table for a batter (epic TN-1a).

    The Tier 2 LLM layer (E-228-07) is fed this object -- it never
    touches ``spray_charts`` or raw x/y. Reachable from the per-batter
    result so callers don't have to re-aggregate.
    """

    entries: tuple[PerZoneContactEntry, ...]
    zone_totals: dict[str, int]
    contact_type_totals: dict[str, int]


@dataclass(frozen=True)
class PerPositionRow:
    """One ``batter_positioning`` row's worth of non-PK columns (epic TN-1a).

    ``team_state_call``, ``bip_count``, ``hr_count``, and ``is_thin``
    are denormalized per-batter values written identically to all six
    of a batter's rows. ``call_state`` is *this position's* call and
    varies across positions. ``direction_shade`` / ``depth_shade`` /
    ``direction_deviation`` / ``depth_deviation`` are NULL when the
    corresponding gate fails (see TN-4 and the schema NULL rules).
    """

    position: str
    call_state: str
    team_state_call: str
    direction_shade: str | None
    depth_shade: str | None
    bip_count: int
    hr_count: int
    is_thin: int
    zone_concentration: float | None
    direction_deviation: int | None
    depth_deviation: int | None


@dataclass(frozen=True)
class BatterPositioningResult:
    """Per-batter Tier 1 result (epic TN-1a).

    Carries the four PK/provenance fields, the six per-position rows,
    the batter's team-state call, and the per-zone aggregation that
    feeds the Tier 2 LLM layer.
    """

    player_id: str
    team_id: int
    season_id: str
    perspective_team_id: int
    per_position_rows: tuple[PerPositionRow, ...]
    team_state_call: str
    zone_aggregation: PerZoneAggregation


# ---------------------------------------------------------------------------
# Stage A quantization helpers
# ---------------------------------------------------------------------------


def _quantize_axis(signed_delta: float, thresholds: tuple[float, float]) -> int:
    """Quantize a signed SVG-space delta to an ordinal step bucket.

    Bucket scheme per epic TN-3 Stage A: ``0`` = on base,
    ``±1`` = slight shade, ``±2`` = significant shade. The sign of the
    bucket equals the sign of ``signed_delta``.
    """
    mag = abs(signed_delta)
    sign = 1 if signed_delta > 0 else (-1 if signed_delta < 0 else 0)
    if mag < thresholds[0]:
        return 0
    if mag < thresholds[1]:
        return sign * 1
    return sign * 2


def _direction_shade_from_dominant(
    dominant_zone: str,
    dominant_count: int,
    subset_total: int,
) -> str | None:
    """Apply the per-zone direction gate (epic TN-4).

    Returns the direction shade (``"left"`` / ``"right"``) when the
    dominant zone of a position's subset is a left or right shade AND
    has at least :data:`ZONE_MIN_BIP` BIPs AND at least
    :data:`ZONE_MIN_CONCENTRATION` share of the subset. Returns
    ``None`` otherwise (``"center"`` is "play straight up" and never
    triggers a shade).

    Exposed as a separate helper so the strict 4-BIP and 35%
    thresholds can be unit-tested directly -- with v1's narrow
    per-position responsibility sectors (at most two cells, with the
    non-target cell being ``center``), the strict 35% bar is hard to
    reach end-to-end from real data, so the gate also serves as a
    defensive backstop for future seam swaps.
    """
    if dominant_zone not in ("left", "right"):
        return None
    if dominant_count < ZONE_MIN_BIP:
        return None
    if subset_total <= 0:
        return None
    if dominant_count / subset_total < ZONE_MIN_CONCENTRATION:
        return None
    return dominant_zone


def _depth_from_contact_type(ct: str) -> str:
    """Map a dominant contact-type label to a depth shade.

    Per epic TN-3 Stage B: GB -> shallower, LD -> normal, FB -> deeper.
    Bunts behave like GB (shallow); popups like FB (deep).
    """
    return {
        "gb": "in",
        "bu": "in",
        "ld": "normal",
        "fb": "deep",
        "pu": "deep",
    }.get(ct, "normal")


# ---------------------------------------------------------------------------
# MIXED rule (epic TN-4a)
# ---------------------------------------------------------------------------


def _are_adjacent(a: str, b: str) -> bool:
    """Adjacency on :data:`ADJACENCY_LATTICE` (neighbors or identical)."""
    return abs(_LATTICE_INDEX[a] - _LATTICE_INDEX[b]) <= 1


def _compute_team_state_call(per_position_calls: list[str]) -> str:
    """Derive the batter's team-state call from the 6 per-position calls.

    Epic TN-4a:

    * Qualifying = the per-position calls excluding ``TRUE``. ``TRUE``
      positions (thin data / no tendency) do not by themselves force
      ``MIXED``.
    * If at least one pair of qualifying calls lands in non-adjacent
      states on :data:`ADJACENCY_LATTICE`, team-state-call is
      ``MIXED``.
    * Otherwise, team-state-call is the dominant named state across
      qualifying calls (or ``TRUE`` if there are no qualifying calls).
    """
    qualifying = [c for c in per_position_calls if c != "TRUE"]
    if not qualifying:
        return "TRUE"

    for i, a in enumerate(qualifying):
        for b in qualifying[i + 1:]:
            if not _are_adjacent(a, b):
                return "MIXED"

    # All qualifying are pairwise adjacent -- pick the most common.
    return Counter(qualifying).most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Per-batter computation (Stages A + B + C)
# ---------------------------------------------------------------------------


def _compute_position_row(
    position: str,
    subset: list[dict[str, Any]],
    centroid_x: float | None,
    centroid_y: float | None,
    bip_count: int,
    hr_count: int,
    is_thin: int,
) -> PerPositionRow:
    """Run Stage B + Stage C for a single (batter, position) pair.

    Operates on the position-relevant BIP subset from
    :func:`bips_for_position`. Sample gates (epic TN-4) apply to the
    subset: subset < :data:`BIP_THIN_THRESHOLD` -> ``call_state='TRUE'``
    (no direction or depth); subset >= depth gate -> depth knob may
    fire. Stage A deviations use the per-batter centroid against this
    position's :data:`BASE_POSITIONS` entry, with the standard NULL
    rules (``direction_deviation`` NULL iff ``call_state='TRUE'`` and
    ``depth_deviation`` NULL iff ``depth_shade`` NULL).
    """
    subset_count = len(subset)

    # Per-batter denormalized fields (constant across this batter's 6 rows).
    common = {
        "position": position,
        "team_state_call": "",  # filled in after team-state derivation
        "bip_count": bip_count,
        "hr_count": hr_count,
        "is_thin": is_thin,
    }

    # Per-position thin gate (epic TN-4 applied per subset).
    if subset_count < BIP_THIN_THRESHOLD:
        return PerPositionRow(
            **common,
            call_state="TRUE",
            direction_shade=None,
            depth_shade=None,
            zone_concentration=None,
            direction_deviation=None,
            depth_deviation=None,
        )

    # Tally dominant zone and dominant contact type within the subset.
    subset_zone_counter: Counter[str] = Counter()
    subset_ct_counter: Counter[str] = Counter()
    for ev in subset:
        subset_zone_counter[assign_zone(ev["x"], ev["y"]).zone] += 1
        ct = contact_type_label(ev.get("play_type"))
        if ct is not None:
            subset_ct_counter[ct] += 1

    dominant_zone, dominant_count = subset_zone_counter.most_common(1)[0]
    zone_concentration = dominant_count / subset_count
    direction_shade = _direction_shade_from_dominant(
        dominant_zone, dominant_count, subset_count
    )

    # Per-position depth gate: subset >= depth-BIP threshold AND dominant
    # contact-type passes its concentration gate.
    depth_shade: str | None = None
    if subset_count >= BIP_DEPTH_THRESHOLD and subset_ct_counter:
        dominant_ct, dominant_ct_count = subset_ct_counter.most_common(1)[0]
        ct_total = sum(subset_ct_counter.values())
        if (
            dominant_ct_count >= CONTACT_TYPE_MIN_COUNT
            and ct_total > 0
            and dominant_ct_count / ct_total >= CONTACT_TYPE_MIN_CONCENTRATION
        ):
            depth_shade = _depth_from_contact_type(dominant_ct)

    # Quantize to call_state.
    if direction_shade is None:
        # No qualifying direction lean -> TRUE; deviations follow the NULL rule.
        return PerPositionRow(
            **common,
            call_state="TRUE",
            direction_shade=None,
            depth_shade=None,
            zone_concentration=zone_concentration,
            direction_deviation=None,
            depth_deviation=None,
        )

    direction_token = direction_shade.upper()  # 'LEFT' or 'RIGHT'
    if depth_shade == "in":
        call_state = f"{direction_token}_SHALLOW"
    elif depth_shade == "deep":
        call_state = f"{direction_token}_DEEP"
    else:
        # depth_shade in {None, 'normal'} -- both produce the plain direction
        # call. The NULL rule for `depth_deviation` distinguishes them.
        call_state = direction_token

    # Stage A deviations (per-position from per-batter centroid).
    base_x, base_y = BASE_POSITIONS[position]
    # centroid_x is guaranteed non-None here: direction_shade requires
    # subset_count > 0 placed events, which requires bip_count > 0.
    assert centroid_x is not None and centroid_y is not None
    delta_x = centroid_x - base_x
    # SVG y: smaller = deeper. depth_offset positive = deeper than base.
    depth_offset = base_y - centroid_y
    direction_deviation = _quantize_axis(
        delta_x, DIRECTION_DEVIATION_THRESHOLDS
    )
    depth_deviation = (
        _quantize_axis(depth_offset, DEPTH_DEVIATION_THRESHOLDS)
        if depth_shade is not None
        else None
    )

    return PerPositionRow(
        **common,
        call_state=call_state,
        direction_shade=direction_shade,
        depth_shade=depth_shade,
        zone_concentration=zone_concentration,
        direction_deviation=direction_deviation,
        depth_deviation=depth_deviation,
    )


def _compute_batter(
    player_id: str,
    team_id: int,
    season_id: str,
    perspective_team_id: int,
    events: list[dict[str, Any]],
) -> BatterPositioningResult:
    """Run the three-stage pipeline for one batter's events.

    Stage A (per-batter centroid + per-position quantized deltas), Stage
    B (per-position direction + depth via the swappable responsibility
    seam :func:`bips_for_position`), Stage C (per-position sample gates
    + 8-key ``call_state`` quantization), then TN-4a team-state call
    derivation and denormalization onto all 6 rows.
    """
    # Separate HR count (over-the-fence HRs have NULL x/y but still count
    # for hr_count). Placed events are those with usable coordinates.
    hr_count = sum(1 for e in events if e.get("play_result") == "home_run")
    placed_events = [
        e for e in events
        if e.get("x") is not None and e.get("y") is not None
    ]
    bip_count = len(placed_events)
    is_thin = 1 if bip_count < BIP_THIN_THRESHOLD else 0

    # --- Per-batter zone aggregation (Tier 2 input, epic TN-1a) -----------
    # Aggregation is per-batter (not per-position) because Tier 2 reads the
    # whole-spray summary to generate the rationale sentence.
    zone_counter: Counter[str] = Counter()
    contact_type_counter: Counter[str] = Counter()
    zone_ct_counter: Counter[tuple[str, str | None]] = Counter()
    for ev in placed_events:
        zone = assign_zone(ev["x"], ev["y"]).zone
        ct = contact_type_label(ev.get("play_type"))
        zone_counter[zone] += 1
        zone_ct_counter[(zone, ct)] += 1
        if ct is not None:
            contact_type_counter[ct] += 1

    aggregation = PerZoneAggregation(
        entries=tuple(
            PerZoneContactEntry(zone=z, contact_type=ct, count=c)
            for (z, ct), c in sorted(zone_ct_counter.items(),
                                     key=lambda kv: (kv[0][0], kv[0][1] or ""))
        ),
        zone_totals=dict(zone_counter),
        contact_type_totals=dict(contact_type_counter),
    )

    # --- Stage A: per-batter centroid (SVG space) -------------------------
    centroid_x: float | None = None
    centroid_y: float | None = None
    if placed_events:
        sum_x = 0.0
        sum_y = 0.0
        for ev in placed_events:
            sx, sy = _raw_to_svg(ev["x"], ev["y"])
            sum_x += sx
            sum_y += sy
        centroid_x = sum_x / bip_count
        centroid_y = sum_y / bip_count

    # --- Stage B + Stage C: per-position re-evaluation --------------------
    per_position_rows_partial: list[PerPositionRow] = []
    per_position_calls: list[str] = []
    for position in COVERED_POSITIONS:
        if bip_count < BIP_THIN_THRESHOLD:
            # AC-2: per-batter thin gate -- all 6 rows TRUE with is_thin=1.
            # No per-position re-evaluation when the whole batter is thin.
            row = PerPositionRow(
                position=position,
                call_state="TRUE",
                team_state_call="",
                direction_shade=None,
                depth_shade=None,
                bip_count=bip_count,
                hr_count=hr_count,
                is_thin=is_thin,
                zone_concentration=None,
                direction_deviation=None,
                depth_deviation=None,
            )
        else:
            subset = bips_for_position(placed_events, position)
            row = _compute_position_row(
                position=position,
                subset=subset,
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                bip_count=bip_count,
                hr_count=hr_count,
                is_thin=is_thin,
            )
        per_position_calls.append(row.call_state)
        per_position_rows_partial.append(row)

    # --- TN-4a: derive team-state call and denormalize onto all rows ------
    team_state_call = _compute_team_state_call(per_position_calls)
    per_position_rows = tuple(
        PerPositionRow(
            position=r.position,
            call_state=r.call_state,
            team_state_call=team_state_call,
            direction_shade=r.direction_shade,
            depth_shade=r.depth_shade,
            bip_count=r.bip_count,
            hr_count=r.hr_count,
            is_thin=r.is_thin,
            zone_concentration=r.zone_concentration,
            direction_deviation=r.direction_deviation,
            depth_deviation=r.depth_deviation,
        )
        for r in per_position_rows_partial
    )

    return BatterPositioningResult(
        player_id=player_id,
        team_id=team_id,
        season_id=season_id,
        perspective_team_id=perspective_team_id,
        per_position_rows=per_position_rows,
        team_state_call=team_state_call,
        zone_aggregation=aggregation,
    )


# ---------------------------------------------------------------------------
# Public entry point (epic TN-6 transaction contract)
# ---------------------------------------------------------------------------


_INSERT_SQL = """
INSERT INTO batter_positioning (
    player_id, team_id, season_id, perspective_team_id, position,
    call_state, team_state_call, direction_shade, depth_shade,
    bip_count, hr_count, is_thin, zone_concentration,
    direction_deviation, depth_deviation
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def compute_positioning(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> list[BatterPositioningResult]:
    """Tier 1 deterministic positioning engine -- pipeline-agnostic entry point.

    Reads ``spray_charts`` filtered by ``team_id`` AND ``season_id`` AND
    ``perspective_team_id`` (the perspective is discovered from the data
    itself -- the engine groups by ``perspective_team_id``), runs the
    three-stage pipeline per batter, and writes the per-position rows
    to ``batter_positioning`` via delete-then-insert within one
    transaction per ``(team_id, season_id, perspective_team_id)`` scope.

    Per epic TN-6: rows in ``spray_charts`` with a NULL ``season_id``
    are skipped and a WARNING is logged with the count. The engine
    commits its own writes.

    Args:
        conn: An open ``sqlite3.Connection`` with the
            ``batter_positioning`` migration applied (the
            ``002_batter_positioning.sql`` migration).
        team_id: ``teams(id)`` INTEGER -- the scouted opponent (batter's
            team).
        season_id: Season slug (e.g. ``"2026-spring-hs"``) -- the caller
            always has a concrete season_id in scope.

    Returns:
        One :class:`BatterPositioningResult` per (batter,
        perspective_team_id) combination found in the scope.

    Raises:
        sqlite3.Error: Any DB error during the recompute transaction
            triggers a ROLLBACK and re-raises. Prior committed state
            is preserved.
    """
    # Count NULL-season_id rows for the team (offensive only) so we can
    # log the skipped count at WARNING per TN-6.
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
            null_season_skipped,
            team_id,
            season_id,
        )

    # Fetch offensive spray events for the scope. Group by
    # (perspective_team_id, player_id) in Python.
    rows = conn.execute(
        """
        SELECT player_id, perspective_team_id, x, y, play_result, play_type
        FROM spray_charts
        WHERE team_id = ? AND chart_type = 'offensive' AND season_id = ?
        """,
        (team_id, season_id),
    ).fetchall()

    # Group: perspective_team_id -> player_id -> [event dicts]
    grouped: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        # sqlite3.Row supports both index and key access; convert for safety.
        # tuples are indexable.
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

    # Compute results per (perspective, player).
    results: list[BatterPositioningResult] = []
    for perspective, batters in grouped.items():
        for player_id, events in batters.items():
            result = _compute_batter(
                player_id=player_id,
                team_id=team_id,
                season_id=season_id,
                perspective_team_id=perspective,
                events=events,
            )
            results.append(result)

    # Delete-then-insert in a single transaction (TN-6 / TN-2 rebuild contract).
    #
    # The DELETE is scoped to (team_id, season_id) -- ALL perspectives for
    # this team and season are cleared, not just the perspectives present
    # in the current run. The engine rebuilds the full positioning state
    # for a team-in-a-season; any perspective that no longer has qualifying
    # spray data must disappear from `batter_positioning` too, otherwise
    # stale rows persist across rebuilds (Codex remediation, 2026-05-15).
    #
    # The transaction always runs, even when `results` is empty -- a
    # zero-row rebuild is a valid state for a team that has lost all
    # qualifying spray rows, and the DELETE-then-no-INSERT path correctly
    # leaves the table empty for the scope.
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """
            DELETE FROM batter_positioning
            WHERE team_id = ? AND season_id = ?
            """,
            (team_id, season_id),
        )
        for result in results:
            for row in result.per_position_rows:
                conn.execute(
                    _INSERT_SQL,
                    (
                        result.player_id,
                        result.team_id,
                        result.season_id,
                        result.perspective_team_id,
                        row.position,
                        row.call_state,
                        row.team_state_call,
                        row.direction_shade,
                        row.depth_shade,
                        row.bip_count,
                        row.hr_count,
                        row.is_thin,
                        row.zone_concentration,
                        row.direction_deviation,
                        row.depth_deviation,
                    ),
                )
        conn.execute("COMMIT")
    except Exception:  # noqa: BLE001
        conn.execute("ROLLBACK")
        raise

    return results
