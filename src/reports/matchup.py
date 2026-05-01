"""Matchup analysis section -- helper module (E-228).

This module is the home of the matchup analysis engine.

E-228-01 shipped the feature-flag helper (``is_matchup_enabled``).
E-228-12 (this file's expansion) ships the deterministic engine:

- ``MatchupInputs`` / ``MatchupAnalysis`` dataclasses.
- ``compute_matchup(inputs) -> MatchupAnalysis`` -- a pure function that
  produces the v1 signal set: top-3 opposing hitters with one mental
  cue each, pull-tendency notes (full opposing roster), stolen-base
  profile, first-inning scoring tendency, 3-bucket loss recipe,
  eligible opposing pitchers, eligible LSB pitchers.
- ``build_matchup_inputs(conn, opponent_team_id, our_team_id, season_id,
  *, reference_date)`` -- the input builder that performs all DB
  queries and assembles the ``MatchupInputs`` dataclass.

The two-tier enrichment wrapper (Tier 2 LLM) ships in ``llm_matchup.py``
per E-228-13, mirroring the predicted-starter pattern in
``src/reports/llm_analysis.py``.

Engine purity (AC-2 / AC-T1): ``compute_matchup`` must not import
``sqlite3`` or ``httpx`` and must not perform any file I/O.  The input
builder is the only path that touches the database; the engine consumes
the dataclass it produces.

Perspective-provenance (AC-15): all per-player stat-table queries in
the input builder filter by ``perspective_team_id``.  Opponent stats
use the opponent's perspective; LSB stats (when ``our_team_id`` is set)
use the LSB team's perspective.  The engine never crosses perspectives.
"""

from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover -- typing only
    import sqlite3

logger = logging.getLogger(__name__)


def is_matchup_enabled() -> bool:
    """Return True when the ``FEATURE_MATCHUP_ANALYSIS`` env var is enabled.

    Mirrors :func:`src.reports.starter_prediction.is_predicted_starter_enabled`.

    The flag gates three call sites:

    1. Admin form rendering -- the matchup checkbox is hidden when False.
    2. CLI flag parsing -- ``bb report generate --our-team`` emits a
       "feature disabled" warning and proceeds without matchup when False.
    3. Generator entry -- :func:`src.reports.generator.generate_report`
       ignores ``our_team_id`` (treats it as None) when False.

    Recognised truthy values: ``"1"``, ``"true"``, ``"yes"`` (case-insensitive).
    Anything else (including unset, empty string, ``"0"``, ``"false"``,
    ``"no"``) is treated as disabled.
    """
    return os.environ.get("FEATURE_MATCHUP_ANALYSIS", "").lower() in (
        "1", "true", "yes",
    )


# ---------------------------------------------------------------------------
# Engine constants (module-level, leading underscore per AC-7 / AC-16)
# ---------------------------------------------------------------------------

_PULL_THRESHOLD = 0.55
_MIN_BIP_FOR_PULL_NOTE = 10
_MIN_PA_FOR_RANKING = 10
_MIN_SB_ATTEMPTS_FOR_PROFILE = 5
_MIN_GAMES_FOR_FIRST_INNING = 5
_MIN_LOSSES_FOR_RECIPE = 3

# Confidence-tier inputs (AC-13).
_HIGH_CONFIDENCE_GAMES = 8
_HIGH_CONFIDENCE_PA = 30

# Top-3 hitter shape.
_TOP_HITTER_LIMIT = 3
_LOW_PA_SOFTEN_THRESHOLD = 20

# Eligible-pitcher list shape (AC-11).
_ELIGIBLE_PITCHER_LIMIT = 5
_THIN_PITCHER_POOL = 3

# Loss-recipe heuristics (AC-8 + Context section).
_STARTER_SHELLED_MAX_OUTS = 12  # ip_outs strictly less than 12 = shelled early
_STARTER_SHELLED_MIN_ER = 4
_BULLPEN_HOLD_MIN_OUTS = 12     # starter went 4+ innings (ip_outs >= 12)
_BULLPEN_HOLD_MIN_ER = 3        # bullpen ER >= 3
_CLOSE_GAME_MARGIN = 2          # |margin| <= 2

# Per-hitter cue-kind thresholds.
_HIGH_FPS_SWING_RATE = 0.55
_LOW_BB_PCT = 0.05
_HIGH_BB_PCT = 0.12
_HIGH_SLG = 0.450
_HIGH_K_PCT = 0.25


# ---------------------------------------------------------------------------
# Public dataclasses (AC-1)
# ---------------------------------------------------------------------------


@dataclass
class PlayerSprayProfile:
    """Per-player roster spray summary used by the engine for pull-tendency notes.

    Built by the input builder from ``get_players_spray_events_batch``
    output for ALL opposing roster members with at least one spray
    event.  The engine reads ``pull_pct`` and ``bip_count`` to decide
    which players warrant a pull-tendency note (AC-7).
    """

    player_id: str
    name: str
    jersey_number: str | None
    pull_pct: float
    bip_count: int


@dataclass
class DataNote:
    """A small data-thinness note attached to a specific sub-section.

    The renderer (E-228-14) uses the ``subsection`` field to place each
    note at the bottom of the corresponding sub-section.  Values: one of
    ``"top_hitters"``, ``"opposing_pitchers"``, ``"sb_profile"``,
    ``"first_inning"``, ``"loss_recipe"``, ``"lsb_pitchers"``.
    """

    message: str
    subsection: str


@dataclass
class ThreatHitter:
    """Top-3 opposing hitter with one mental cue and supporting stats.

    Engine emits up to three of these (per AC-4).  ``cue_kind`` is one
    of ``attack_early``, ``pitch_around``, ``expand_zone``, or
    ``default``.  The LLM Tier 2 wrapper renders the prose; engine only
    produces the structure.
    """

    player_id: str
    name: str
    jersey_number: str | None
    pa: int
    obp: float
    slg: float
    ops: float
    bb_pct: float
    k_pct: float
    fps_swing_rate: float
    chase_rate: float
    swing_rate_by_count: dict[str, float]
    cue_kind: str
    supporting_stats: list[str]


@dataclass
class PullTendencyNote:
    """A pull-tendency note for a roster member (AC-7).

    Emitted by the engine when ``pull_pct >= 0.55`` and ``bip_count >= 10``
    on the corresponding ``PlayerSprayProfile`` entry.
    """

    player_id: str
    name: str
    jersey_number: str | None
    pull_pct: float
    bip_count: int


@dataclass
class LossRecipeBucket:
    """Counts and grounding tuples for a single loss-recipe bucket.

    ``grounding`` carries up to a few ``(game_date, opposing_score,
    opponent_score, starter_name, key_stat)`` tuples that the LLM
    wrapper uses to ground its prose.  Engine does NOT produce prose
    for any bucket -- that is the LLM's job.
    """

    count: int = 0
    grounding: list[tuple[str, int | None, int | None, str | None, str | None]] = field(
        default_factory=list,
    )


@dataclass
class LossRecipe:
    """3-bucket loss-recipe classification + uncategorized counter."""

    starter_shelled_early: LossRecipeBucket = field(default_factory=LossRecipeBucket)
    bullpen_couldnt_hold: LossRecipeBucket = field(default_factory=LossRecipeBucket)
    close_game_lost_late: LossRecipeBucket = field(default_factory=LossRecipeBucket)
    uncategorized_count: int = 0
    total_losses: int = 0


@dataclass
class EligiblePitcher:
    """A pitcher's availability summary for the eligible-pitchers list (AC-11)."""

    player_id: str
    name: str
    jersey_number: str | None
    last_outing_date: str | None
    days_rest: int | None
    last_outing_pitches: int | None
    workload_7d: int | None


@dataclass
class MatchupInputs:
    """Input bundle consumed by ``compute_matchup``.

    Carries every fact the engine needs.  Built by
    ``build_matchup_inputs()`` against the live database.

    Attributes:
        opponent_team: Dict with id, name, public_id (or None).
        opponent_top_hitters: Output of ``get_top_hitters`` for the
            opponent (already filtered by ``min_pa`` and limited to a
            workable pool).  Each entry includes per-hitter pitch
            tendencies merged in by the builder.
        opponent_pitching: Output of ``get_pitching_workload`` keyed by
            ``player_id`` (with names attached).
        opponent_losses: Pre-classified loss rows the engine buckets.
            Each row carries: ``game_id``, ``game_date``,
            ``opposing_score``, ``opponent_score``, ``margin``,
            ``starter_name``, ``starter_ip_outs``, ``starter_er``,
            ``starter_decision``, ``bullpen_er``.
        opponent_sb_profile: Output of ``get_sb_tendency`` for the
            opponent.
        opponent_first_inning_pattern: Output of
            ``get_first_inning_pattern`` for the opponent.
        opponent_roster_spray: Per-roster ``PlayerSprayProfile`` entries
            (full opposing roster, NOT just top-3 hitters), AC-3.
            Roster members with zero spray events are excluded.
        lsb_team: Dict with id, name (or ``None`` when ``our_team_id`` is
            None).
        lsb_pitching: ``get_pitching_workload`` output for the LSB team
            with names attached, or ``None`` when ``our_team_id`` is
            None.
        reference_date: Anchor date for rest/availability math.
        season_id: Season slug.
    """

    opponent_team: dict[str, Any]
    opponent_top_hitters: list[dict[str, Any]]
    opponent_pitching: list[dict[str, Any]]
    opponent_losses: list[dict[str, Any]]
    opponent_sb_profile: dict[str, Any]
    opponent_first_inning_pattern: dict[str, Any]
    opponent_roster_spray: list[PlayerSprayProfile]
    lsb_team: dict[str, Any] | None
    lsb_pitching: list[dict[str, Any]] | None
    reference_date: datetime.date
    season_id: str


@dataclass
class MatchupAnalysis:
    """Output of ``compute_matchup`` -- consumed by E-228-13 LLM wrapper.

    Contains the deterministic structure for the Game Plan section.
    The LLM Tier 2 wrapper produces all prose; this dataclass carries
    only structured signals.
    """

    confidence: str  # "high" | "moderate" | "low" | "suppress"
    threat_list: list[ThreatHitter] = field(default_factory=list)
    pull_tendency_notes: list[PullTendencyNote] = field(default_factory=list)
    sb_profile_summary: dict[str, Any] = field(default_factory=dict)
    first_inning_summary: dict[str, Any] = field(default_factory=dict)
    loss_recipe_buckets: LossRecipe = field(default_factory=LossRecipe)
    eligible_opposing_pitchers: list[EligiblePitcher] = field(default_factory=list)
    eligible_lsb_pitchers: list[EligiblePitcher] | None = None
    data_notes: list[DataNote] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine helpers (pure)
# ---------------------------------------------------------------------------


def _classify_cue(hitter: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (cue_kind, supporting_stats) for one hitter.

    See AC-5 for the v1 cue kinds.  ``supporting_stats`` is a small list
    of human-readable bullet strings the LLM can quote in its prose.
    """
    pa = hitter.get("pa") or 0
    bb_pct = (hitter.get("bb") or 0) / pa if pa > 0 else 0.0
    k_pct = (hitter.get("so") or 0) / pa if pa > 0 else 0.0
    slg = float(hitter.get("slg") or 0.0)
    fps_seen = hitter.get("fps_seen") or 0
    fps_swing = hitter.get("fps_swing_count") or 0
    fps_swing_rate = (fps_swing / fps_seen) if fps_seen > 0 else 0.0

    supporting: list[str] = []
    if pa > 0:
        supporting.append(f"{pa} PA")
    if fps_seen > 0:
        supporting.append(
            f"{fps_swing_rate * 100:.0f}% first-pitch swing"
        )
    if pa > 0:
        supporting.append(f"{bb_pct * 100:.0f}% BB")
        supporting.append(f"{k_pct * 100:.0f}% K")
    if slg > 0:
        supporting.append(f".{int(slg * 1000):03d} SLG")

    # AC-5 cue ordering: pitch_around > expand_zone > attack_early > default.
    if bb_pct >= _HIGH_BB_PCT and slg >= _HIGH_SLG:
        return "pitch_around", supporting
    if k_pct >= _HIGH_K_PCT:
        return "expand_zone", supporting
    if fps_swing_rate >= _HIGH_FPS_SWING_RATE or bb_pct <= _LOW_BB_PCT:
        return "attack_early", supporting
    return "default", supporting


def _build_threat_hitters(
    top_hitters: list[dict[str, Any]],
) -> tuple[list[ThreatHitter], list[DataNote]]:
    """Rank, classify, and emit the top-3 hitters + per-hitter data notes.

    Engine consumes hitter dicts (each carrying merged pitch-tendency
    fields) and produces ``ThreatHitter`` records sorted by OPS DESC,
    PA DESC.  Hitters with ``pa < _MIN_PA_FOR_RANKING`` are excluded
    from the top-3 list (AC-4) but the engine still emits a low-PA
    softening note for any returned hitter under ``_LOW_PA_SOFTEN_THRESHOLD``
    (AC-6).
    """
    eligible = [h for h in top_hitters if (h.get("pa") or 0) >= _MIN_PA_FOR_RANKING]
    # Already sorted by OPS desc / PA desc from get_top_hitters; defensive
    # re-sort here in case caller passed an unsorted list.
    eligible.sort(
        key=lambda h: (
            -(float(h.get("ops") or 0.0)),
            -(int(h.get("pa") or 0)),
            h.get("player_id") or "",
        ),
    )
    selected = eligible[:_TOP_HITTER_LIMIT]

    notes: list[DataNote] = []
    threats: list[ThreatHitter] = []
    for h in selected:
        cue_kind, supporting = _classify_cue(h)
        pa = h.get("pa") or 0
        bb_pct = (h.get("bb") or 0) / pa if pa > 0 else 0.0
        k_pct = (h.get("so") or 0) / pa if pa > 0 else 0.0
        fps_seen = h.get("fps_seen") or 0
        fps_swing = h.get("fps_swing_count") or 0
        fps_swing_rate = (fps_swing / fps_seen) if fps_seen > 0 else 0.0

        threats.append(ThreatHitter(
            player_id=h.get("player_id") or "",
            name=h.get("name") or "Unknown Player",
            jersey_number=h.get("jersey_number"),
            pa=int(pa),
            obp=float(h.get("obp") or 0.0),
            slg=float(h.get("slg") or 0.0),
            ops=float(h.get("ops") or 0.0),
            bb_pct=round(bb_pct, 4),
            k_pct=round(k_pct, 4),
            fps_swing_rate=round(fps_swing_rate, 4),
            chase_rate=float(h.get("chase_rate") or 0.0),
            swing_rate_by_count=dict(h.get("swing_rate_by_count") or {}),
            cue_kind=cue_kind,
            supporting_stats=supporting,
        ))
        if pa < _LOW_PA_SOFTEN_THRESHOLD:
            notes.append(DataNote(
                message=(
                    f"Early read only: {h.get('name') or 'Unknown Player'} "
                    f"has {pa} PA on the season."
                ),
                subsection="top_hitters",
            ))
    return threats, notes


def _build_pull_tendency_notes(
    roster_spray: list[PlayerSprayProfile],
) -> list[PullTendencyNote]:
    """Emit a ``PullTendencyNote`` per roster member meeting the threshold."""
    notes: list[PullTendencyNote] = []
    for profile in roster_spray:
        if (
            profile.pull_pct >= _PULL_THRESHOLD
            and profile.bip_count >= _MIN_BIP_FOR_PULL_NOTE
        ):
            notes.append(PullTendencyNote(
                player_id=profile.player_id,
                name=profile.name,
                jersey_number=profile.jersey_number,
                pull_pct=round(profile.pull_pct, 4),
                bip_count=profile.bip_count,
            ))
    return notes


def _bucket_losses(losses: list[dict[str, Any]]) -> LossRecipe:
    """Classify each loss into one of the 3 buckets or uncategorized.

    See AC-8 / Context section for the heuristics.  Engine emits
    grounding tuples for downstream LLM prose; engine does NOT produce
    prose itself.
    """
    recipe = LossRecipe()
    recipe.total_losses = len(losses)
    for loss in losses:
        starter_outs = loss.get("starter_ip_outs") or 0
        starter_er = loss.get("starter_er") or 0
        starter_decision = loss.get("starter_decision")
        bullpen_er = loss.get("bullpen_er") or 0
        margin = loss.get("margin") or 0

        grounding_tuple = (
            loss.get("game_date") or "",
            loss.get("opposing_score"),
            loss.get("opponent_score"),
            loss.get("starter_name"),
            None,  # key_stat -- LLM may pull from grounding fields
        )

        is_shelled = (
            starter_outs < _STARTER_SHELLED_MAX_OUTS
            and starter_er >= _STARTER_SHELLED_MIN_ER
            and starter_decision == "L"
        )
        is_bullpen = (
            not is_shelled
            and starter_outs >= _BULLPEN_HOLD_MIN_OUTS
            and bullpen_er >= _BULLPEN_HOLD_MIN_ER
        )
        is_close = (
            not is_shelled
            and not is_bullpen
            and abs(margin) <= _CLOSE_GAME_MARGIN
        )

        if is_shelled:
            bucket = recipe.starter_shelled_early
        elif is_bullpen:
            bucket = recipe.bullpen_couldnt_hold
        elif is_close:
            bucket = recipe.close_game_lost_late
        else:
            recipe.uncategorized_count += 1
            continue
        bucket.count += 1
        # Cap grounding to the first 5 entries per bucket so LLM prompts
        # stay bounded; LLM will cite a small sample anyway.
        if len(bucket.grounding) < 5:
            key_stat: str | None
            if bucket is recipe.starter_shelled_early:
                key_stat = (
                    f"starter {starter_outs // 3}.{starter_outs % 3} IP, "
                    f"{starter_er} ER"
                )
            elif bucket is recipe.bullpen_couldnt_hold:
                key_stat = f"bullpen {bullpen_er} ER"
            else:
                key_stat = f"margin {margin:+d}"
            bucket.grounding.append((
                grounding_tuple[0], grounding_tuple[1], grounding_tuple[2],
                grounding_tuple[3], key_stat,
            ))
    return recipe


def _build_eligible_pitchers(
    pitching: list[dict[str, Any]] | None,
    reference_date: datetime.date,
) -> list[EligiblePitcher]:
    """Project the pitching-workload list onto the engine's pitcher dataclass."""
    if not pitching:
        return []
    selected: list[EligiblePitcher] = []
    for entry in pitching[:_ELIGIBLE_PITCHER_LIMIT]:
        last_str = entry.get("last_outing_date")
        days_rest: int | None = entry.get("last_outing_days_ago")
        if days_rest is None and last_str:
            try:
                last_date = datetime.date.fromisoformat(last_str)
                days_rest = (reference_date - last_date).days
            except (ValueError, TypeError):
                days_rest = None
        selected.append(EligiblePitcher(
            player_id=entry.get("player_id") or "",
            name=entry.get("name") or "Unknown Player",
            jersey_number=entry.get("jersey_number"),
            last_outing_date=last_str,
            days_rest=days_rest,
            last_outing_pitches=entry.get("last_outing_pitches"),
            workload_7d=entry.get("pitches_7d"),
        ))
    return selected


def _decide_confidence(
    inputs: MatchupInputs,
    threat_list: list[ThreatHitter],
    loss_recipe: LossRecipe,
) -> str:
    """Return the confidence tier per AC-13.

    - ``"suppress"`` when both opponent_top_hitters and opponent_losses
      are empty.
    - ``"low"`` when at least one of those is non-empty but no losses
      bucket out and no top-3 hitter clears ``_MIN_PA_FOR_RANKING``.
    - ``"high"`` when >= 8 opponent games AND every top-3 hitter has
      >= 30 PA.
    - ``"moderate"`` otherwise.
    """
    if (
        len(inputs.opponent_top_hitters) == 0
        and len(inputs.opponent_losses) == 0
    ):
        return "suppress"

    bucketed = (
        loss_recipe.starter_shelled_early.count
        + loss_recipe.bullpen_couldnt_hold.count
        + loss_recipe.close_game_lost_late.count
    )
    has_qualified_hitter = len(threat_list) > 0
    if not has_qualified_hitter and bucketed == 0:
        return "low"

    games_played = (
        inputs.opponent_first_inning_pattern.get("games_played") or 0
    )
    if (
        games_played >= _HIGH_CONFIDENCE_GAMES
        and len(threat_list) >= _TOP_HITTER_LIMIT
        and all(t.pa >= _HIGH_CONFIDENCE_PA for t in threat_list)
    ):
        return "high"
    return "moderate"


def _emit_subsection_data_notes(
    inputs: MatchupInputs,
    eligible_opp_pitchers: list[EligiblePitcher],
    eligible_lsb_pitchers: list[EligiblePitcher] | None,
) -> list[DataNote]:
    """Per-sub-section thinness notes (AC-16)."""
    notes: list[DataNote] = []

    if len(eligible_opp_pitchers) < _THIN_PITCHER_POOL:
        notes.append(DataNote(
            message=(
                f"Thin opposing-pitcher pool: only {len(eligible_opp_pitchers)} "
                f"candidate(s) cleared rest/workload."
            ),
            subsection="opposing_pitchers",
        ))

    sb_attempts = inputs.opponent_sb_profile.get("sb_attempts") or 0
    if sb_attempts < _MIN_SB_ATTEMPTS_FOR_PROFILE:
        notes.append(DataNote(
            message=(
                f"Small SB sample: {sb_attempts} attempt(s) on the season."
            ),
            subsection="sb_profile",
        ))

    games_played = inputs.opponent_first_inning_pattern.get("games_played") or 0
    if games_played < _MIN_GAMES_FOR_FIRST_INNING:
        notes.append(DataNote(
            message=f"Thin first-inning sample: {games_played} game(s).",
            subsection="first_inning",
        ))

    total_losses = len(inputs.opponent_losses)
    if total_losses < _MIN_LOSSES_FOR_RECIPE:
        notes.append(DataNote(
            message=f"Small loss sample: {total_losses} loss(es) on the season.",
            subsection="loss_recipe",
        ))

    if eligible_lsb_pitchers is not None:
        if len(eligible_lsb_pitchers) < _THIN_PITCHER_POOL:
            notes.append(DataNote(
                message=(
                    f"Thin LSB pitching: only {len(eligible_lsb_pitchers)} "
                    f"candidate(s) cleared rest/workload."
                ),
                subsection="lsb_pitchers",
            ))

    return notes


# ---------------------------------------------------------------------------
# Main engine (pure -- AC-2)
# ---------------------------------------------------------------------------


def compute_matchup(inputs: MatchupInputs) -> MatchupAnalysis:
    """Produce a deterministic ``MatchupAnalysis`` from a ``MatchupInputs`` bundle.

    PURE FUNCTION (AC-2): no DB access, no HTTP, no file I/O.  Engine
    code-level purity is asserted by ``tests/test_matchup.py`` -- adding
    ``import sqlite3``, ``import httpx``, or ``open()`` to this module's
    engine call graph WILL break that test.

    Args:
        inputs: A ``MatchupInputs`` dataclass produced by
            :func:`build_matchup_inputs`.  All DB queries happen in the
            input builder; this function consumes only the dataclass.

    Returns:
        A ``MatchupAnalysis`` dataclass.  When the suppress trigger
        fires (no top hitters AND no losses), the returned analysis has
        ``confidence="suppress"`` and otherwise-empty fields; the
        renderer hides the entire Game Plan section in that case.

    See ``epics/E-228-matchup-strategy-report/E-228-12.md`` for the
    full AC list.  See ``.claude/rules/perspective-provenance.md`` for
    the contract that governs how inputs were assembled.
    """
    # AC-7: pull-tendency notes from full opposing roster spray data.
    pull_notes = _build_pull_tendency_notes(inputs.opponent_roster_spray)

    # AC-4 + AC-5 + AC-6: top-3 hitter ranking + per-hitter cue + low-PA notes.
    threat_list, hitter_notes = _build_threat_hitters(
        inputs.opponent_top_hitters,
    )

    # AC-8: 3-bucket loss recipe.
    loss_recipe = _bucket_losses(inputs.opponent_losses)

    # AC-11 + AC-12: eligible pitcher lists.
    eligible_opp = _build_eligible_pitchers(
        inputs.opponent_pitching, inputs.reference_date,
    )
    eligible_lsb: list[EligiblePitcher] | None
    if inputs.lsb_pitching is None:
        eligible_lsb = None
    else:
        eligible_lsb = _build_eligible_pitchers(
            inputs.lsb_pitching, inputs.reference_date,
        )

    # AC-9 / AC-10: SB and first-inning summaries pass through the
    # builder-collected dicts (engine adds nothing on top).
    sb_summary = dict(inputs.opponent_sb_profile)
    first_inning_summary = dict(inputs.opponent_first_inning_pattern)

    # AC-13: confidence tier.
    confidence = _decide_confidence(inputs, threat_list, loss_recipe)

    # AC-16: per-sub-section thinness notes.
    section_notes = _emit_subsection_data_notes(
        inputs, eligible_opp, eligible_lsb,
    )

    data_notes = list(hitter_notes) + list(section_notes)

    if confidence == "suppress":
        # Renderer hides the section; expose only the confidence tier
        # plus empty containers so downstream code doesn't have to
        # special-case None.  ``eligible_lsb_pitchers`` is forced to
        # ``None`` here -- on suppress we have nothing to render, so the
        # LSB block must be hidden too even if ``our_team_id`` was set.
        # SB / first-inning summaries are zeroed out for contract
        # cleanliness: nothing about the section should be observable
        # downstream (matches the "no-trace" guarantee in the renderer).
        return MatchupAnalysis(
            confidence="suppress",
            threat_list=[],
            pull_tendency_notes=[],
            sb_profile_summary={},
            first_inning_summary={},
            loss_recipe_buckets=LossRecipe(),
            eligible_opposing_pitchers=[],
            eligible_lsb_pitchers=None,
            data_notes=[],
        )

    return MatchupAnalysis(
        confidence=confidence,
        threat_list=threat_list,
        pull_tendency_notes=pull_notes,
        sb_profile_summary=sb_summary,
        first_inning_summary=first_inning_summary,
        loss_recipe_buckets=loss_recipe,
        eligible_opposing_pitchers=eligible_opp,
        eligible_lsb_pitchers=eligible_lsb,
        data_notes=data_notes,
    )


# ---------------------------------------------------------------------------
# Input builder (DB-touching -- AC-3)
# ---------------------------------------------------------------------------


def _classify_pull(events: list[dict[str, Any]]) -> tuple[float, int]:
    """Compute (pull_pct, bip_count) from raw spray events.

    GC spray coordinates: ``x`` ranges roughly 0..1 with the field's
    home-plate origin near the middle; pull-side is the side a batter
    drives the ball toward.  Without batter handedness available in
    every record, v1 uses a coordinate-side heuristic: a ball is
    "pulled" when ``x < 0.45`` for left-handed visual frame OR
    ``x > 0.55`` for right-handed (we approximate by treating the
    farther side as pull).  This matches the "pull-tendency note"
    semantics used by the existing report renderer (see
    ``src/reports/renderer.py`` spray heat-map logic) where pull is
    sourced from the same coordinate space.

    For v1 we treat ``x`` outside ``[0.45, 0.55]`` as a directional
    hit; pull_pct is the fraction of directional hits that fall on the
    same dominant side -- whichever side has the majority count.  This
    is a deterministic, handedness-free approximation that the engine
    consumes; downstream stories can refine when handedness becomes
    routinely available.
    """
    if not events:
        return 0.0, 0
    bip = 0
    left = 0
    right = 0
    for ev in events:
        x = ev.get("x")
        if x is None:
            continue
        bip += 1
        try:
            xv = float(x)
        except (TypeError, ValueError):
            continue
        if xv < 0.45:
            left += 1
        elif xv > 0.55:
            right += 1
    if bip == 0:
        return 0.0, 0
    dominant = max(left, right)
    return dominant / bip, bip


def _attach_pitch_tendencies(
    conn: sqlite3.Connection,
    hitters: list[dict[str, Any]],
    season_id: str,
    perspective_team_id: int,
) -> list[dict[str, Any]]:
    """Merge per-hitter pitch-tendency aggregates into each hitter dict.

    Imports inside this helper keep the module-level engine call graph
    free of DB-specific imports.
    """
    from src.api.db import get_hitter_pitch_tendencies

    enriched: list[dict[str, Any]] = []
    for h in hitters:
        pid = h.get("player_id")
        tend: dict[str, Any] = {}
        if pid:
            tend = get_hitter_pitch_tendencies(
                pid, season_id, perspective_team_id, db=conn,
            )
        merged = dict(h)
        merged.update({
            "fps_seen": tend.get("fps_seen", 0),
            "fps_swing_count": tend.get("fps_swing_count", 0),
            "two_strike_pa": tend.get("two_strike_pa", 0),
            "full_count_pa": tend.get("full_count_pa", 0),
            "chase_rate": tend.get("chase_rate", 0.0),
            "swing_rate_by_count": tend.get("swing_rate_by_count", {}),
        })
        enriched.append(merged)
    return enriched


def _build_loss_rows(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> list[dict[str, Any]]:
    """Assemble the pre-classified loss rows the engine buckets.

    Walks ``games`` to find losses (final score < opponent score), then
    joins ``player_game_pitching`` rows under ``perspective_team_id =
    team_id`` to find the starter and bullpen ER for each loss.
    """
    cursor = conn.execute(
        """
        SELECT
            g.game_id,
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            CASE WHEN g.home_team_id = :team_id THEN g.home_score
                 ELSE g.away_score END AS opponent_score,
            CASE WHEN g.home_team_id = :team_id THEN g.away_score
                 ELSE g.home_score END AS opposing_score
        FROM games g
        WHERE g.season_id = :season_id
          AND g.status = 'completed'
          AND (g.home_team_id = :team_id OR g.away_team_id = :team_id)
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
        """,
        {"team_id": team_id, "season_id": season_id},
    )
    rows = cursor.fetchall()

    losses: list[dict[str, Any]] = []
    for row in rows:
        opp_score = row["opponent_score"]
        opposing_score = row["opposing_score"]
        if opp_score is None or opposing_score is None:
            continue
        if opp_score >= opposing_score:
            continue
        margin = (opp_score or 0) - (opposing_score or 0)

        # Pitching rows under this team's own perspective.
        # Note: ``pgp.team_id = ? AND pgp.perspective_team_id = ?`` are
        # bound to the SAME ``team_id`` value intentionally -- this
        # constrains the result to rows the team itself loaded (own
        # perspective), excluding cross-perspective duplicates loaded
        # under another team's scouting pipeline.
        p_rows = conn.execute(
            """
            SELECT
                pgp.player_id,
                pgp.appearance_order,
                pgp.ip_outs,
                pgp.er,
                pgp.decision,
                p.first_name || ' ' || p.last_name AS name
            FROM player_game_pitching pgp
            JOIN players p ON p.player_id = pgp.player_id
            WHERE pgp.game_id = ?
              AND pgp.team_id = ?
              AND pgp.perspective_team_id = ?
            ORDER BY pgp.appearance_order ASC NULLS LAST
            """,
            (row["game_id"], team_id, team_id),
        ).fetchall()

        starter_name: str | None = None
        starter_outs = 0
        starter_er = 0
        starter_decision: str | None = None
        bullpen_er = 0
        for pr in p_rows:
            if pr["appearance_order"] == 1:
                starter_name = pr["name"]
                starter_outs = pr["ip_outs"] or 0
                starter_er = pr["er"] or 0
                starter_decision = pr["decision"]
            elif pr["appearance_order"] is not None and pr["appearance_order"] > 1:
                bullpen_er += pr["er"] or 0
            else:
                # appearance_order is NULL: best-effort -- treat the
                # earliest entry with no order as starter, others as
                # bullpen.
                if starter_name is None:
                    starter_name = pr["name"]
                    starter_outs = pr["ip_outs"] or 0
                    starter_er = pr["er"] or 0
                    starter_decision = pr["decision"]
                else:
                    bullpen_er += pr["er"] or 0

        losses.append({
            "game_id": row["game_id"],
            "game_date": row["game_date"],
            "opposing_score": opposing_score,
            "opponent_score": opp_score,
            "margin": margin,
            "starter_name": starter_name,
            "starter_ip_outs": starter_outs,
            "starter_er": starter_er,
            "starter_decision": starter_decision,
            "bullpen_er": bullpen_er,
        })
    return losses


def _build_pitching_eligibility_rows(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    reference_date: datetime.date,
) -> list[dict[str, Any]]:
    """Project ``get_pitching_workload`` into a list with names attached.

    Sorted by ``last_outing_date`` ASC (most-rested first); ties broken by
    ``workload_7d`` ASC (less recent volume preferred), then by name for
    full determinism.  This ordering matters because the engine caps the
    eligible-pitcher list at the top-5 entries -- the most-rested
    pitchers should win that cap, not the most-recently-used ones.
    """
    from src.api.db import get_pitching_workload

    workload = get_pitching_workload(
        team_id, season_id, reference_date.isoformat(), db=conn,
    )
    if not workload:
        return []
    # Attach names + jersey_number from team_rosters / players for each entry.
    placeholders = ",".join("?" for _ in workload)
    rows = conn.execute(
        f"""
        SELECT
            p.player_id,
            p.first_name || ' ' || p.last_name AS name,
            tr.jersey_number,
            wl_meta.last_pitches AS last_outing_pitches
        FROM players p
        LEFT JOIN team_rosters tr
            ON tr.player_id = p.player_id
            AND tr.team_id = ?
            AND tr.season_id = ?
        LEFT JOIN (
            SELECT
                pgp.player_id,
                pgp.pitches AS last_pitches
            FROM player_game_pitching pgp
            JOIN games g ON g.game_id = pgp.game_id
            WHERE pgp.team_id = ?
              AND pgp.perspective_team_id = ?
              AND g.season_id = ?
              AND (pgp.player_id, g.game_date) IN (
                  SELECT pgp2.player_id, MAX(g2.game_date)
                  FROM player_game_pitching pgp2
                  JOIN games g2 ON g2.game_id = pgp2.game_id
                  WHERE pgp2.team_id = ?
                    AND pgp2.perspective_team_id = ?
                    AND g2.season_id = ?
                  GROUP BY pgp2.player_id
              )
        ) wl_meta ON wl_meta.player_id = p.player_id
        WHERE p.player_id IN ({placeholders})
        """,
        (
            team_id, season_id,
            team_id, team_id, season_id,
            team_id, team_id, season_id,
            *workload.keys(),
        ),
    ).fetchall()
    by_pid: dict[str, dict[str, Any]] = {}
    for r in rows:
        by_pid[r["player_id"]] = {
            "player_id": r["player_id"],
            "name": r["name"] or "Unknown Player",
            "jersey_number": r["jersey_number"],
            "last_outing_pitches": r["last_outing_pitches"],
        }

    result: list[dict[str, Any]] = []
    for pid, wl in workload.items():
        meta = by_pid.get(pid, {
            "player_id": pid,
            "name": "Unknown Player",
            "jersey_number": None,
            "last_outing_pitches": None,
        })
        result.append({
            **meta,
            "last_outing_date": wl.get("last_outing_date"),
            "last_outing_days_ago": wl.get("last_outing_days_ago"),
            "pitches_7d": wl.get("pitches_7d"),
            "appearances_7d": wl.get("appearances_7d"),
        })
    # Sort most-rested first: oldest last_outing_date (ASC) leads, then
    # smaller pitches_7d (ASC) as the tie-break (less recent volume),
    # then name (ASC) for full determinism.  Entries with no recorded
    # outing date sort to the END so they don't crowd the top-5 cap.
    def _sort_key(e: dict[str, Any]) -> tuple[int, str, int, str]:
        date_str = e.get("last_outing_date") or ""
        # 0 if a date is present, 1 if absent -- pushes empty-date rows
        # to the end of the ASC sort.
        date_present = 0 if date_str else 1
        return (
            date_present,
            date_str,
            int(e.get("pitches_7d") or 0),
            e.get("name") or "",
        )

    result.sort(key=_sort_key)
    return result


def _build_roster_spray_profiles(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
) -> list[PlayerSprayProfile]:
    """Build a ``PlayerSprayProfile`` per opposing roster member with spray data.

    Reads the team's roster from ``team_rosters``, batch-fetches all
    spray events via ``get_players_spray_events_batch``, and computes
    per-player ``pull_pct`` and ``bip_count``.  Roster members with no
    spray events are excluded.

    Passes ``team_id`` as the ``perspective_team_id`` to
    ``get_players_spray_events_batch`` so that a player who appears on
    multiple teams in the same season only contributes events captured
    under THIS team's perspective (AC-3, Codex Phase 4b MUST FIX 1).
    """
    from src.api.db import get_players_spray_events_batch

    roster_rows = conn.execute(
        """
        SELECT
            tr.player_id,
            tr.jersey_number,
            p.first_name || ' ' || p.last_name AS name
        FROM team_rosters tr
        JOIN players p ON p.player_id = tr.player_id
        WHERE tr.team_id = ?
          AND tr.season_id = ?
        ORDER BY tr.jersey_number ASC NULLS LAST, name ASC
        """,
        (team_id, season_id),
    ).fetchall()
    if not roster_rows:
        return []
    pids = [r["player_id"] for r in roster_rows]
    spray_by_pid = get_players_spray_events_batch(
        pids, season_id, perspective_team_id=team_id, db=conn,
    )
    profiles: list[PlayerSprayProfile] = []
    for r in roster_rows:
        events = spray_by_pid.get(r["player_id"]) or []
        if not events:
            continue
        pull_pct, bip = _classify_pull(events)
        if bip == 0:
            continue
        profiles.append(PlayerSprayProfile(
            player_id=r["player_id"],
            name=r["name"] or "Unknown Player",
            jersey_number=r["jersey_number"],
            pull_pct=round(pull_pct, 4),
            bip_count=bip,
        ))
    return profiles


def build_matchup_inputs(
    conn: "sqlite3.Connection",
    opponent_team_id: int,
    our_team_id: int | None,
    season_id: str,
    *,
    reference_date: datetime.date,
) -> MatchupInputs:
    """Assemble a ``MatchupInputs`` dataclass for the matchup engine.

    All DB queries the engine consumes flow through this builder.  The
    engine itself is pure (AC-2) -- it never opens a connection.

    Helpers called (perspective in parentheses):

    - :func:`src.api.db.get_top_hitters` (opponent perspective).
    - :func:`src.api.db.get_hitter_pitch_tendencies` (opponent perspective)
      via ``_attach_pitch_tendencies``.
    - :func:`src.api.db.get_sb_tendency` (opponent perspective).
    - :func:`src.api.db.get_first_inning_pattern` (perspective-agnostic;
      deduplicates plays by (game_id, half)).
    - :func:`src.api.db.get_pitching_workload` (opponent perspective for
      opposing pitching; LSB perspective for ``lsb_pitching``).
    - :func:`src.api.db.get_players_spray_events_batch` (opponent
      perspective; opposing roster pulled via ``team_rosters``).
    - Inline SQL for opponent losses (own-team-perspective filter on
      ``player_game_pitching``).

    Args:
        conn: Open ``sqlite3.Connection`` -- the builder uses it for
            every query and never closes it.  All helpers that accept
            ``db=...`` share this connection.
        opponent_team_id: INTEGER PK of the opposing team.
        our_team_id: INTEGER PK of the LSB team, or ``None``.  When
            ``None``, the returned inputs have ``lsb_team=None`` and
            ``lsb_pitching=None``.
        season_id: Season slug to scope every query.
        reference_date: Anchor date for rest/availability math.

    Returns:
        A ``MatchupInputs`` dataclass with all sub-fields populated.

    Perspective-provenance contract: every per-player query above runs
    under the opponent's perspective for opponent-side facts and the
    LSB team's perspective for LSB-side facts (when ``our_team_id`` is
    set).  ``get_first_inning_pattern`` deduplicates by (game_id, half)
    so cross-perspective duplicates do not double-count.
    """
    import sqlite3 as _sqlite3

    from src.api.db import (
        get_first_inning_pattern,
        get_sb_tendency,
        get_top_hitters,
    )

    conn.row_factory = _sqlite3.Row  # ensure dict-like rows

    # Opponent team header.
    team_row = conn.execute(
        "SELECT id, name, public_id FROM teams WHERE id = ?",
        (opponent_team_id,),
    ).fetchone()
    opponent_team = (
        {"id": team_row["id"], "name": team_row["name"], "public_id": team_row["public_id"]}
        if team_row
        else {"id": opponent_team_id, "name": "Unknown Team", "public_id": None}
    )

    # AC-4: top-N hitters (we fetch up to 5 to give the engine room
    # if a top hitter is filtered later; engine takes top-3).
    top_hitters_raw = get_top_hitters(
        opponent_team_id, season_id, limit=5, min_pa=_MIN_PA_FOR_RANKING, db=conn,
    )
    top_hitters = _attach_pitch_tendencies(
        conn, top_hitters_raw, season_id, opponent_team_id,
    )

    # AC-3 / AC-7: full opposing roster spray profiles.
    opponent_roster_spray = _build_roster_spray_profiles(
        conn, opponent_team_id, season_id,
    )

    # AC-9: SB profile from the opponent's perspective.
    opponent_sb_profile = get_sb_tendency(
        opponent_team_id, season_id,
        perspective_team_id=opponent_team_id, db=conn,
    )

    # AC-10: first-inning pattern.
    opponent_first_inning_pattern = get_first_inning_pattern(
        opponent_team_id, season_id, db=conn,
    )

    # AC-8: opponent loss rows for the engine's bucket logic.
    opponent_losses = _build_loss_rows(conn, opponent_team_id, season_id)

    # AC-11: opposing eligible pitchers (workload + name attached).
    opponent_pitching = _build_pitching_eligibility_rows(
        conn, opponent_team_id, season_id, reference_date,
    )

    # AC-12: optional LSB block.
    lsb_team: dict[str, Any] | None = None
    lsb_pitching: list[dict[str, Any]] | None = None
    if our_team_id is not None:
        lsb_row = conn.execute(
            "SELECT id, name FROM teams WHERE id = ?",
            (our_team_id,),
        ).fetchone()
        lsb_team = (
            {"id": lsb_row["id"], "name": lsb_row["name"]}
            if lsb_row
            else {"id": our_team_id, "name": "Unknown Team"}
        )
        lsb_pitching = _build_pitching_eligibility_rows(
            conn, our_team_id, season_id, reference_date,
        )

    return MatchupInputs(
        opponent_team=opponent_team,
        opponent_top_hitters=top_hitters,
        opponent_pitching=opponent_pitching,
        opponent_losses=opponent_losses,
        opponent_sb_profile=opponent_sb_profile,
        opponent_first_inning_pattern=opponent_first_inning_pattern,
        opponent_roster_spray=opponent_roster_spray,
        lsb_team=lsb_team,
        lsb_pitching=lsb_pitching,
        reference_date=reference_date,
        season_id=season_id,
    )
