"""Plays-vs-boxscore reconciliation scoreboard (E-257-01).

The standing, repeatable form of the one-off ``recon.sql`` baseline captured in
``.project/research/E-245-plays-boxscore-reconciliation-baseline.md``.  It
measures how faithfully the plays-derived stats reconstruct GameChanger's
official box scores -- the concrete metric behind CLAUDE.md's north-star
Operating Principle ("Always Get Closer to Byte-Identical Play Ingestion").

Following the project's established pure-core pattern for read-only analytics,
the core is a connection-in / result-dataclass-out function:
:func:`compute_scoreboard` takes an open SQLite connection and returns a
:class:`ScoreboardResult`.  The human Rich table, the ``--json`` block, and any
regression gate (E-257-02) all fall out of that one dataclass.  This module
MEASURES only -- it never writes and it never gates.

What it computes (see the E-245 baseline for the full derivation):

* **Per-stat fidelity** for pitching ``{BF, SO, BB, H, HBP}`` and batting
  ``{AB, H, BB, SO, HBP}``.  Grain is the player-game unit
  ``(game_id, perspective_team_id, player_id)``, perspective-scoped (the honest
  grain for *report* fidelity -- reports query plays perspective-scoped).  Units
  with a boxscore row but zero matching plays rows (the "no-plays" coverage gap)
  are EXCLUDED from the fidelity denominator and counted separately.  For each
  stat: ``exact_pct`` (share of fidelity units whose plays value equals the
  boxscore value) and ``abs_delta`` (sum of ``|plays - boxscore|``).
* **Three axis counters** (the north-star "trend toward zero" targets):
  ``dropped_pitch_events`` (annotated pitches stranded as ``event_type='other'``
  -- see :func:`is_dropped_pitch_event`), ``no_plays_units`` (boxscore units with
  zero matching plays -- pitcher + batter total), and ``self_games``
  (``home_team_id == away_team_id`` -- an opponent-resolution failure).
* **Perspective-only misses** -- the subset of ``no_plays_units`` that DO have
  plays in the same game under a *different* perspective (a perspective-join
  miss, not truly-absent data).  DISPLAY-ONLY: a diagnostic breakdown of the
  ``no_plays_units`` total, never a separately-gated JSON counter (TN-5).

Stat-definition source of truth (TN-7): the outcome-membership sets and the
AB-exclusion set below are the CANONICAL definitions -- the E-245 baseline doc
mirrors them (not the reverse).  The reconciliation engine
(``src/reconciliation/engine.py``) holds a private parallel copy for its own
derivation; ``tests/test_recon_scoreboard.py`` pins these constants to their
literal sets AND asserts the engine's copy still agrees, so the two plays->stat
derivations cannot silently drift apart.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.gamechanger.parsers.plays_parser import (
    _PITCH_ANNOTATION_PATTERN,
    _PITCH_TEMPLATES,
)

# ---------------------------------------------------------------------------
# Canonical plays-derived stat definitions (TN-7)
# ---------------------------------------------------------------------------
# These are the code-canonical outcome->stat mappings the scoreboard uses to
# derive plays-side aggregates from ``plays.outcome``.  A test pins each to its
# literal expected set (drift guard) and a fixture exercises each mapping
# behaviourally.  The strings are the exact ``plays.outcome`` values GameChanger
# emits (see the plays parser vocabulary), NOT the UI abbreviations.

# H = Single + Double + Triple + Home Run
HIT_OUTCOMES = frozenset({"Single", "Double", "Triple", "Home Run"})
# SO = Strikeout + Dropped 3rd Strike
SO_OUTCOMES = frozenset({"Strikeout", "Dropped 3rd Strike"})
# BB = Walk + Intentional Walk
BB_OUTCOMES = frozenset({"Walk", "Intentional Walk"})
# HBP = Hit By Pitch
HBP_OUTCOMES = frozenset({"Hit By Pitch"})

# AB = PA - (BB + IBB + HBP + Sac Bunt + Sac Fly + Catcher's Interference).
# A plate appearance whose outcome is in this set yields a PA but NOT an at-bat;
# every other PA (including one with a NULL/blank outcome) counts as an AB, so
# ``AB = row_count - COUNT(outcome IN AB_EXCLUSION_OUTCOMES)`` -- matching the
# reconciliation engine's ``if outcome not in _AB_EXCLUSIONS`` derivation, under
# which a NULL outcome counts as an AB.
AB_EXCLUSION_OUTCOMES = frozenset({
    "Walk",
    "Intentional Walk",
    "Hit By Pitch",
    "Sacrifice Fly",
    "Sacrifice Bunt",
    "Catcher's Interference",
})

# Stat display order per side.  ``BF``/``AB`` are row-count-derived; the rest are
# outcome-membership counts.
PITCHING_STATS: tuple[str, ...] = ("BF", "SO", "BB", "H", "HBP")
BATTING_STATS: tuple[str, ...] = ("AB", "H", "BB", "SO", "HBP")

# Only batting AB and H carry the abandoned-PA / quick-scored residual (cause-5
# in the E-245 baseline; baseball-coach confirmed the residual is strictly
# batting AB/H -- no pitching stat and no batting BB/SO).  The human table labels
# these rows as a KNOWN residual; it never suppresses them (AC-3 / TN-3).
BATTING_RESIDUAL_STATS: frozenset[str] = frozenset({"AB", "H"})


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatFidelity:
    """Per-stat plays-vs-boxscore fidelity over the no-plays-excluded units.

    Attributes:
        stat: The stat label (e.g. ``"BF"``, ``"AB"``).
        fidelity_units: Boxscore units that HAVE plays (the exact% denominator).
        exact_units: Units whose plays value equals the boxscore value.
        abs_delta: Sum of ``|plays - boxscore|`` over the fidelity units.
        is_residual: True only for batting ``AB``/``H`` -- the stats carrying the
            known abandoned-PA / quick-scored residual (TN-3).
    """

    stat: str
    fidelity_units: int
    exact_units: int
    abs_delta: int
    is_residual: bool = False

    @property
    def exact_pct(self) -> float:
        """Share of fidelity units that match exactly, as a percent (1 dp).

        Vacuously ``100.0`` when there are no fidelity units -- a real gate
        (E-257-02) reads ``fidelity_units`` to reject a vacuous scoreboard.
        """
        if self.fidelity_units == 0:
            return 100.0
        return round(self.exact_units / self.fidelity_units * 100, 1)


@dataclass(frozen=True)
class ScoreboardResult:
    """Outcome of a scoreboard computation.

    Attributes:
        pitching: Per-stat fidelity for ``PITCHING_STATS`` (in that order).
        batting: Per-stat fidelity for ``BATTING_STATS`` (in that order).
        dropped_pitch_events: Annotated pitches stranded as ``event_type='other'``
            (axis 1).
        no_plays_units: Boxscore units (pitcher + batter) with zero matching
            plays rows (axis 2, the coverage gap).
        self_games: Games with ``home_team_id == away_team_id`` (axis 3).
        perspective_only_misses: Subset of ``no_plays_units`` whose player DOES
            have plays in the same game under a different perspective.
            DISPLAY-ONLY (TN-5): a diagnostic breakdown of ``no_plays_units``,
            never a separately-gated counter.
    """

    pitching: tuple[StatFidelity, ...]
    batting: tuple[StatFidelity, ...]
    dropped_pitch_events: int
    no_plays_units: int
    self_games: int
    perspective_only_misses: int


# ---------------------------------------------------------------------------
# Dropped-pitch detection (axis 1)
# ---------------------------------------------------------------------------


def is_dropped_pitch_event(raw_template: str | None) -> bool:
    """True if an ``event_type='other'`` row is really a stranded annotated pitch.

    GameChanger's pitch-type charting mode appends a trailing ``(PitchType)`` /
    ``(101 MPH Curveball)`` annotation to each pitch template (e.g.
    ``"Strike 1 looking (Curveball)"``).  The pre-E-245 parser matched only the
    un-suffixed form, so annotated pitches fell through to ``event_type='other'``
    -- see ``.project/archive/agent-memory/data-engineer/pitch_type_annotation_parser_gap.md``.

    The exact predicate mirrors the pitch branch of the parser's own classifier
    (``PlaysParser._classify_template`` steps 1-2), reusing its canonical grammar
    -- ``_PITCH_TEMPLATES`` (the base-form vocabulary) and
    ``_PITCH_ANNOTATION_PATTERN`` (the single-trailing-``(...)`` splitter): a row
    is a dropped pitch exactly when its ``raw_template`` is a bare pitch OR
    strips (via the trailing-annotation pattern) to a base that is a known pitch
    template.  This is the same criterion ``plays_reload`` uses to recover such
    rows, so the counter tracks precisely the events a reload would recover.  It
    can never over-count the way a naive ``LIKE '%(%)%'`` would (which matches
    ANY parenthetical, including substitution/baserunner templates and a LEADING
    ``(Play Edit)``), because a non-pitch base is rejected.  It reuses the
    parser's constants rather than calling ``_classify_template`` directly so it
    does not emit the classifier's ``Unknown template`` WARNING for every
    genuinely-``other`` row on a real DB.
    """
    if not raw_template:
        return False
    # Step 1: bare pitch template (exact match).
    if raw_template in _PITCH_TEMPLATES:
        return True
    # Step 2: annotated pitch -- strip a single trailing "(...)" group and match
    # the base against the pitch vocabulary (a leading parenthetical does NOT
    # match, since the pattern anchors the group at the very end).
    annotation_match = _PITCH_ANNOTATION_PATTERN.match(raw_template)
    if annotation_match is not None and annotation_match.group(1) in _PITCH_TEMPLATES:
        return True
    return False


# ---------------------------------------------------------------------------
# Plays-side aggregate SQL (net-new; reads only plays / play_events / the
# per-game boxscore tables)
# ---------------------------------------------------------------------------


def _in_clause(values: frozenset[str]) -> tuple[str, list[str]]:
    """Return a ``(?, ?, ...)`` placeholder clause and the bound params.

    The params are derived from the SAME sorted tuple used to size the clause,
    so placeholder count and bind order always agree (``IN`` membership is
    order-independent).
    """
    ordered = sorted(values)
    return "(" + ", ".join("?" for _ in ordered) + ")", ordered


def _pitching_plays_aggregate(
    conn: sqlite3.Connection,
) -> dict[tuple[str, int, str], dict[str, int]]:
    """Plays-derived pitching aggregate keyed by ``(game_id, persp, pitcher_id)``.

    ``BF`` is the plate-appearance row count; the rest are outcome-membership
    counts.  Rows with a NULL ``pitcher_id`` (non-PA markers) are dropped.
    """
    so_clause, so_params = _in_clause(SO_OUTCOMES)
    bb_clause, bb_params = _in_clause(BB_OUTCOMES)
    h_clause, h_params = _in_clause(HIT_OUTCOMES)
    hbp_clause, hbp_params = _in_clause(HBP_OUTCOMES)
    sql = f"""
        SELECT game_id, perspective_team_id, pitcher_id,
               COUNT(*) AS bf,
               SUM(CASE WHEN outcome IN {so_clause} THEN 1 ELSE 0 END) AS so,
               SUM(CASE WHEN outcome IN {bb_clause} THEN 1 ELSE 0 END) AS bb,
               SUM(CASE WHEN outcome IN {h_clause} THEN 1 ELSE 0 END) AS h,
               SUM(CASE WHEN outcome IN {hbp_clause} THEN 1 ELSE 0 END) AS hbp
        FROM plays
        WHERE pitcher_id IS NOT NULL
        GROUP BY game_id, perspective_team_id, pitcher_id
    """
    params = [*so_params, *bb_params, *h_params, *hbp_params]
    out: dict[tuple[str, int, str], dict[str, int]] = {}
    for game_id, persp, pid, bf, so, bb, h, hbp in conn.execute(sql, params):
        out[(game_id, persp, pid)] = {
            "BF": bf, "SO": so, "BB": bb, "H": h, "HBP": hbp,
        }
    return out


def _batting_plays_aggregate(
    conn: sqlite3.Connection,
) -> dict[tuple[str, int, str], dict[str, int]]:
    """Plays-derived batting aggregate keyed by ``(game_id, persp, batter_id)``.

    ``AB = row_count - COUNT(outcome IN AB_EXCLUSION_OUTCOMES)`` so a NULL/blank
    outcome counts as an AB (matching the reconciliation engine's ``not in``
    derivation); the rest are outcome-membership counts.
    """
    ab_clause, ab_params = _in_clause(AB_EXCLUSION_OUTCOMES)
    h_clause, h_params = _in_clause(HIT_OUTCOMES)
    bb_clause, bb_params = _in_clause(BB_OUTCOMES)
    so_clause, so_params = _in_clause(SO_OUTCOMES)
    hbp_clause, hbp_params = _in_clause(HBP_OUTCOMES)
    sql = f"""
        SELECT game_id, perspective_team_id, batter_id,
               COUNT(*) - SUM(CASE WHEN outcome IN {ab_clause} THEN 1 ELSE 0 END) AS ab,
               SUM(CASE WHEN outcome IN {h_clause} THEN 1 ELSE 0 END) AS h,
               SUM(CASE WHEN outcome IN {bb_clause} THEN 1 ELSE 0 END) AS bb,
               SUM(CASE WHEN outcome IN {so_clause} THEN 1 ELSE 0 END) AS so,
               SUM(CASE WHEN outcome IN {hbp_clause} THEN 1 ELSE 0 END) AS hbp
        FROM plays
        GROUP BY game_id, perspective_team_id, batter_id
    """
    params = [*ab_params, *h_params, *bb_params, *so_params, *hbp_params]
    out: dict[tuple[str, int, str], dict[str, int]] = {}
    for game_id, persp, pid, ab, h, bb, so, hbp in conn.execute(sql, params):
        out[(game_id, persp, pid)] = {
            "AB": ab, "H": h, "BB": bb, "SO": so, "HBP": hbp,
        }
    return out


def _score_side(
    box_rows: list[tuple],
    plays_agg: dict[tuple[str, int, str], dict[str, int]],
    stat_order: tuple[str, ...],
    residual_stats: frozenset[str],
) -> tuple[tuple[StatFidelity, ...], int, int]:
    """Compare one side's boxscore units against the plays aggregate.

    Args:
        box_rows: ``(game_id, perspective_team_id, player_id, *stat_values)``
            in ``stat_order`` column order.
        plays_agg: The plays-side aggregate keyed by the same unit tuple.
        stat_order: The stats to score, in display order.
        residual_stats: Stats to flag ``is_residual`` on.

    Returns:
        ``(per_stat_fidelity, no_plays_units, perspective_only_misses)``.  A
        boxscore unit with no plays row is excluded from every stat's fidelity
        counts and added to ``no_plays_units``; if the same ``(game, player)``
        has plays under any other perspective it is also a perspective-only miss.
    """
    fidelity_units = dict.fromkeys(stat_order, 0)
    exact_units = dict.fromkeys(stat_order, 0)
    abs_delta = dict.fromkeys(stat_order, 0)

    # (game_id, player_id) that have plays under ANY perspective -- lets a
    # no-plays unit under one perspective be recognised as a perspective-only
    # miss when the player has plays under a different perspective.
    plays_game_player = {(game_id, pid) for (game_id, _persp, pid) in plays_agg}

    no_plays = 0
    perspective_only = 0
    for row in box_rows:
        game_id, persp, player_id = row[0], row[1], row[2]
        box_values = dict(zip(stat_order, (v or 0 for v in row[3:])))
        plays_values = plays_agg.get((game_id, persp, player_id))
        if plays_values is None:
            no_plays += 1
            if (game_id, player_id) in plays_game_player:
                perspective_only += 1
            continue
        for stat in stat_order:
            fidelity_units[stat] += 1
            delta = box_values[stat] - plays_values[stat]
            if delta == 0:
                exact_units[stat] += 1
            abs_delta[stat] += abs(delta)

    fidelity = tuple(
        StatFidelity(
            stat=stat,
            fidelity_units=fidelity_units[stat],
            exact_units=exact_units[stat],
            abs_delta=abs_delta[stat],
            is_residual=stat in residual_stats,
        )
        for stat in stat_order
    )
    return fidelity, no_plays, perspective_only


def compute_scoreboard(conn: sqlite3.Connection) -> ScoreboardResult:
    """Compute the plays-vs-boxscore reconciliation scoreboard.

    Read-only: issues only ``SELECT`` statements and never writes to the
    database.

    Args:
        conn: Open SQLite connection to the database to measure.

    Returns:
        A :class:`ScoreboardResult` with per-stat fidelity for both sides and
        the three axis counters (plus the display-only perspective-only split).
    """
    pitching_plays = _pitching_plays_aggregate(conn)
    batting_plays = _batting_plays_aggregate(conn)

    pitching_box = conn.execute(
        "SELECT game_id, perspective_team_id, player_id, bf, so, bb, h, hbp "
        "FROM player_game_pitching"
    ).fetchall()
    batting_box = conn.execute(
        "SELECT game_id, perspective_team_id, player_id, ab, h, bb, so, hbp "
        "FROM player_game_batting"
    ).fetchall()

    pitching_fidelity, pitch_no_plays, pitch_persp_only = _score_side(
        pitching_box, pitching_plays, PITCHING_STATS, frozenset()
    )
    batting_fidelity, bat_no_plays, bat_persp_only = _score_side(
        batting_box, batting_plays, BATTING_STATS, BATTING_RESIDUAL_STATS
    )

    # Axis 1: annotated pitches stranded as event_type='other'.  The exact
    # predicate lives in is_dropped_pitch_event; the SQL only narrows to the
    # candidate 'other' rows.
    dropped_pitch_events = sum(
        1
        for (raw_template,) in conn.execute(
            "SELECT raw_template FROM play_events WHERE event_type = 'other'"
        )
        if is_dropped_pitch_event(raw_template)
    )

    # Axis 3: opponent-resolution self-games.
    self_games = conn.execute(
        "SELECT COUNT(*) FROM games WHERE home_team_id = away_team_id"
    ).fetchone()[0]

    return ScoreboardResult(
        pitching=pitching_fidelity,
        batting=batting_fidelity,
        dropped_pitch_events=dropped_pitch_events,
        no_plays_units=pitch_no_plays + bat_no_plays,
        self_games=self_games,
        perspective_only_misses=pitch_persp_only + bat_persp_only,
    )


# ---------------------------------------------------------------------------
# JSON serialization (stable keys -- pinned by tests; consumed by E-257-02's
# ratchet and E-256's closure smoke)
# ---------------------------------------------------------------------------


def _stat_block(stats: tuple[StatFidelity, ...]) -> dict[str, dict[str, object]]:
    """Serialize a per-side fidelity tuple to a stable ``{stat: {...}}`` block."""
    return {
        s.stat: {
            "exact_pct": s.exact_pct,
            "abs_delta": s.abs_delta,
            "fidelity_units": s.fidelity_units,
            "exact_units": s.exact_units,
            "is_residual": s.is_residual,
        }
        for s in stats
    }


def to_json_dict(result: ScoreboardResult) -> dict[str, object]:
    """Serialize a :class:`ScoreboardResult` to a stable, JSON-safe dict.

    The ``axis_counters`` sub-object has EXACTLY the three keys
    ``dropped_pitch_events`` / ``no_plays_units`` / ``self_games`` (AC-4).  The
    perspective-only split is intentionally omitted -- it is a display-only
    breakdown of ``no_plays_units`` (TN-5), not a gated counter.  The per-stat
    block field names are equally locked so E-257-02's cell-by-cell ratchet has
    a stable shape to diff against.
    """
    return {
        "pitching": _stat_block(result.pitching),
        "batting": _stat_block(result.batting),
        "axis_counters": {
            "dropped_pitch_events": result.dropped_pitch_events,
            "no_plays_units": result.no_plays_units,
            "self_games": result.self_games,
        },
    }


# ---------------------------------------------------------------------------
# Committed baseline + one-way ratchet regression gate (E-257-02)
# ---------------------------------------------------------------------------
# The gate makes the north-star bind mechanically: a fresh run diffs against a
# committed baseline JSON snapshot and fails (non-zero exit) when a GATED number
# regresses.  Binding point is a MANUAL operator diagnostic against the live DB
# (TN-2) -- NOT a CI gate; ``./data/app.db`` is absent from worktrees/CI.
#
# Gated set (baseball-coach CONFIRMED, TN-3) -- a FLAT, equal-weight ratchet over
# the outcome/decision stats only:
#   * batting abs-Δ:  {AB, H, BB, SO}
#   * pitching abs-Δ: {H, SO, BB}
#   * ratcheted axis counters: dropped_pitch_events, no_plays_units
#   * self_games: a HARD ZERO (any > 0 fails), NOT ratcheted
# Deliberately NOT gated: pitching BF (workload/denominator; gap is mostly
# perspective noise), HBP on either side (smallest sample -- shown as context),
# and FPS/pitch-level fidelity (guarded via the dropped_pitch_events counter, not
# blended into the regression score).  The abandoned-PA residual on batting
# {AB, H} is EXEMPT structurally: it is baked into the committed baseline floor,
# and the one-way ratchet only fires ABOVE the floor (hold-steady passes).

GATED_BATTING_STATS: tuple[str, ...] = ("AB", "H", "BB", "SO")
GATED_PITCHING_STATS: tuple[str, ...] = ("H", "SO", "BB")
RATCHETED_AXIS_COUNTERS: tuple[str, ...] = ("dropped_pitch_events", "no_plays_units")

# Distinct process exit codes so a cron/operator can tell the failure modes
# apart (and none is 2, Typer's usage-error code).
EXIT_REGRESSION: int = 1
EXIT_BASELINE_ABSENT: int = 3
EXIT_BASELINE_MALFORMED: int = 4


class BaselineError(Exception):
    """A committed baseline file exists but is unreadable, malformed, or missing
    expected gated keys.

    Distinct from the baseline-ABSENT case (``load_baseline`` returns ``None``):
    a present-but-corrupt baseline is an operator-actionable condition, not a
    crash.  The CLI turns this into a distinct non-zero exit with an actionable
    message (symmetric with the AC-8 absent-baseline handling).
    """


def default_baseline_path() -> Path:
    """Repo-root-relative path to the committed baseline JSON.

    The real baseline at ``.project/baselines/reconciliation-scoreboard.json`` is
    operator-produced via ``--update-baseline`` against the live DB (an E-257
    closure step); it is NOT created by the implementer and may be absent until
    then (see :func:`load_baseline` / the AC-8 bootstrap).
    """
    return (
        Path(__file__).resolve().parents[2]
        / ".project"
        / "baselines"
        / "reconciliation-scoreboard.json"
    )


@dataclass(frozen=True)
class GateViolation:
    """A single gated number that regressed against the baseline.

    Attributes:
        name: Dotted identifier, e.g. ``"batting.H"``, ``"axis.no_plays_units"``,
            or ``"self_games"``.
        kind: ``"abs_delta"`` | ``"axis_counter"`` | ``"self_games"``.
        baseline: The baseline (floor) value, or ``None`` for the
            baseline-independent ``self_games`` hard-zero rule.
        current: The fresh-run value that violated the rule.
    """

    name: str
    kind: str
    baseline: int | None
    current: int

    def describe(self) -> str:
        if self.kind == "self_games":
            return (
                f"self_games = {self.current} (must be 0 -- a self-game is always "
                "an opponent-resolution bug, never an acceptable floor)"
            )
        return f"{self.name} rose {self.baseline} -> {self.current}"


@dataclass(frozen=True)
class GateResult:
    """Outcome of a ratchet-gate evaluation."""

    violations: tuple[GateViolation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


def _validate_baseline_shape(data: object) -> dict:
    """Confirm a loaded baseline carries every value the gate diffs against.

    Raises :class:`BaselineError` when a gated stat's ``abs_delta`` or a required
    axis counter is missing (a partial/hand-truncated baseline), so a corrupt
    baseline surfaces as an actionable operator message rather than a raw
    ``KeyError`` from :func:`evaluate_gate`.
    """
    try:
        for side, stats in (
            ("batting", GATED_BATTING_STATS),
            ("pitching", GATED_PITCHING_STATS),
        ):
            for stat in stats:
                _ = data[side][stat]["abs_delta"]  # type: ignore[index]
        for counter in (*RATCHETED_AXIS_COUNTERS, "self_games"):
            _ = data["axis_counters"][counter]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise BaselineError(
            f"baseline is missing an expected gated value ({exc})"
        ) from exc
    return data  # type: ignore[return-value]


def load_baseline(path: Path) -> dict | None:
    """Load + validate a committed baseline JSON, or ``None`` when absent.

    A ``None`` return is the AC-8 baseline-ABSENT signal (first-ever use, before
    any ``--update-baseline`` run).  A present-but-corrupt baseline (unparseable
    JSON, or valid JSON missing a gated value) raises :class:`BaselineError`
    instead -- the CLI maps each to its own distinct non-zero exit with an
    actionable message, never a raw traceback or a silent pass.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise BaselineError(f"baseline JSON could not be read ({exc})") from exc
    return _validate_baseline_shape(data)


def evaluate_gate(current: dict, baseline: dict) -> GateResult:
    """One-way ratchet: fail when a GATED number regressed vs the baseline.

    Compares ONLY the per-stat + axis-counter VALUE block (the shape
    :func:`to_json_dict` emits); the baseline's metadata header (git SHA,
    game-count, date) is never read, so it is ignored by construction (AC-1 --
    "same schema" = the compared value block, not byte-identical files).

    The ratchet is structurally one-way: a gated stat's ``abs_delta`` or a
    ratcheted axis counter fires ONLY on an INCREASE; a shrink or hold-steady is
    an improvement and never trips it.  ``self_games`` is exempt from the ratchet
    and gated as a HARD ZERO instead: any ``current > 0`` fails regardless of the
    baseline (aligning E-256's ``self_games == 0`` closure smoke).

    Args:
        current: A fresh-run value dict (``to_json_dict`` output).
        baseline: A committed baseline dict (value block + optional metadata).

    Returns:
        A :class:`GateResult`; ``passed`` is True iff no gated number regressed.
    """
    violations: list[GateViolation] = []

    for side, stats in (
        ("batting", GATED_BATTING_STATS),
        ("pitching", GATED_PITCHING_STATS),
    ):
        for stat in stats:
            cur = current[side][stat]["abs_delta"]
            base = baseline[side][stat]["abs_delta"]
            if cur > base:
                violations.append(
                    GateViolation(f"{side}.{stat}", "abs_delta", base, cur)
                )

    for counter in RATCHETED_AXIS_COUNTERS:
        cur = current["axis_counters"][counter]
        base = baseline["axis_counters"][counter]
        if cur > base:
            violations.append(
                GateViolation(f"axis.{counter}", "axis_counter", base, cur)
            )

    # self_games: hard zero, baseline-independent.
    cur_self = current["axis_counters"]["self_games"]
    if cur_self > 0:
        violations.append(
            GateViolation("self_games", "self_games", None, cur_self)
        )

    return GateResult(tuple(violations))


def write_baseline(path: Path, result: ScoreboardResult, metadata: dict) -> None:
    """Overwrite the baseline JSON with a fresh snapshot (for a reviewed commit).

    Writes the ``to_json_dict`` value block under a ``metadata`` header (git SHA,
    DB game-count, snapshot date) so the JSON commit diff is the human review
    point.  No agent auto-refreshes the baseline -- only the operator runs
    ``--update-baseline`` against the live DB and commits the diff.  The metadata
    is caller-supplied so this stays a pure, testable write.
    """
    payload = {"metadata": dict(metadata), **to_json_dict(result)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
