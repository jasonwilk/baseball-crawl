"""Parser for GameChanger plays API responses.

Pure-function module that transforms raw plays JSON into structured dataclass
records.  No database dependency -- accepts raw JSON + context IDs, returns
a list of ``ParsedPlay`` dataclass records ready for database insertion.

The parser:
- Classifies each at_plate_details event (pitch, baserunner, substitution, other)
- Extracts batter ID from final_details and tracks pitcher ID per half-inning
- Counts pitches and computes ``is_first_pitch_strike`` per TN-1
- Computes ``is_qab`` per TN-2 (all 7 conditions)
- Skips abandoned plate appearances (empty final_details)
- Logs unknown templates at WARNING level

Usage::

    from src.gamechanger.parsers.plays_parser import PlaysParser

    plays = PlaysParser.parse_game(
        raw_json=response_dict,
        game_id="abc-123",
        season_id="2026-spring-hs",
        home_team_id=1,
        away_team_id=2,
    )
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UUID extraction regex -- matches ${uuid} tokens in template strings.
# ---------------------------------------------------------------------------
_UUID_PATTERN = re.compile(r"\$\{([0-9a-f-]{36})\}")

# ---------------------------------------------------------------------------
# Template classification patterns (TN-4)
# ---------------------------------------------------------------------------

# Pitch events -- exact matches for the at_plate_details templates.
_PITCH_TEMPLATES: dict[str, str] = {
    "Ball 1": "ball",
    "Ball 2": "ball",
    "Ball 3": "ball",
    "Ball 4": "ball",
    "Strike 1 looking": "strike_looking",
    "Strike 2 looking": "strike_looking",
    "Strike 3 looking": "strike_looking",
    "Strike 1 swinging": "strike_swinging",
    "Strike 2 swinging": "strike_swinging",
    "Strike 3 swinging": "strike_swinging",
    "Foul": "foul",
    "Foul tip": "foul_tip",
    "In play": "in_play",
    "Foul bunt": "foul",
}

# Non-PA outcome markers -- these plays have no batter and should be
# silently skipped rather than triggering a batter-extraction warning.
_NON_PA_OUTCOMES = frozenset({"Runner Out", "Inning Ended"})

# Baserunner event detection keywords (must also contain ${uuid}).
_BASERUNNER_KEYWORDS = (
    "advances to",
    "scores",
    "steals",
    "remains at",
    "Pickoff attempt",
    "caught stealing",
    "picked off",
    "Balk",
    "gets placed",
    "out at",
    "out due to",
    "Outs changed",
)

# Substitution event start patterns.
_SUBSTITUTION_STARTS = ("Lineup changed:", "(Play Edit)")
_SUBSTITUTION_CONTAINS = ("in for pitcher", "Courtesy runner")

# Pitcher substitution detection keywords in at_plate_details.
# The new pitcher is always the first ${uuid} in the template.
# "Lineup changed: ${new} in at pitcher"
# "${new} in for pitcher ${old}"

# Explicit pitcher reference in final_details: "${uuid} pitching"
_PITCHER_EXPLICIT_PATTERN = re.compile(
    r"\$\{([0-9a-f-]{36})\}\s+pitching",
)

# HHB (hard-hit ball) detection patterns for QAB (case-insensitive).
_HHB_PATTERNS = (
    re.compile(r"line drive", re.IGNORECASE),
    re.compile(r"hard ground ball", re.IGNORECASE),
)

# QAB exclusion outcomes (TN-2).
_QAB_EXCLUDED_OUTCOMES = frozenset({
    "Intentional Walk",
    "Dropped 3rd Strike",
    "Catcher's Interference",
})

# XBH outcomes for QAB.
_XBH_OUTCOMES = frozenset({"Double", "Triple", "Home Run"})

# SAC outcomes for QAB.
_SAC_OUTCOMES = frozenset({"Sacrifice Bunt", "Sacrifice Fly"})

# FPS pitch results that count as strikes on the first pitch (TN-1).
_FPS_STRIKE_RESULTS = frozenset({
    "strike_looking",
    "strike_swinging",
    "foul",
    "foul_tip",
    "in_play",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ParsedEvent:
    """A single event within a plate appearance.

    Attributes:
        event_order: 0-indexed position within the PA's at_plate_details.
        event_type: One of 'pitch', 'baserunner', 'substitution', 'other'.
        pitch_result: Pitch classification (only set for pitch events).
        is_first_pitch: Whether this is the first pitch event in the PA.
        raw_template: Original template string from the API.
    """

    event_order: int
    event_type: str
    pitch_result: str | None
    is_first_pitch: bool
    raw_template: str


@dataclass
class ParsedPlay:
    """A parsed plate appearance ready for database insertion.

    Attributes:
        game_id: The ``event_id`` / ``game_id`` FK to the games table.
        play_order: 0-indexed play number within the game.
        inning: Inning number.
        half: ``'top'`` or ``'bottom'``.
        season_id: FK to seasons table.
        batting_team_id: FK to teams table (which team is batting).
        batter_id: Player UUID of the batter.
        pitcher_id: Player UUID of the pitcher (may be None).
        outcome: The name_template.template value (e.g. 'Walk', 'Single').
        pitch_count: Total pitch events in the PA.
        is_first_pitch_strike: 1 if the first pitch was a strike, else 0.
        is_qab: 1 if the PA qualifies as a quality at-bat, else 0.
        home_score: Cumulative home score after this play.
        away_score: Cumulative away score after this play.
        did_score_change: 1 if score changed on this play, else 0.
        outs_after: Running out count after this play.
        did_outs_change: 1 if outs changed on this play, else 0.
        events: List of classified events for the play_events table.
    """

    game_id: str
    play_order: int
    inning: int
    half: str
    season_id: str
    batting_team_id: int
    batter_id: str
    pitcher_id: str | None
    outcome: str
    pitch_count: int
    is_first_pitch_strike: int
    is_qab: int
    home_score: int
    away_score: int
    did_score_change: int
    outs_after: int
    did_outs_change: int
    events: list[ParsedEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class PlaysParser:
    """Stateless parser for GameChanger plays API responses.

    All methods are classmethods / staticmethods -- no instance state needed.
    """

    @classmethod
    def parse_game(
        cls,
        raw_json: dict[str, Any],
        game_id: str,
        season_id: str,
        home_team_id: int,
        away_team_id: int,
    ) -> list[ParsedPlay]:
        """Parse a raw plays API response into structured records.

        Args:
            raw_json: Full API response dict with ``sport``, ``team_players``,
                and ``plays`` keys.
            game_id: The ``event_id`` / ``game_id`` for FK linkage.
            season_id: Season identifier for denormalized storage.
            home_team_id: Internal team ID of the home team.
            away_team_id: Internal team ID of the away team.

        Returns:
            List of ``ParsedPlay`` records (abandoned PAs excluded).
        """
        plays_data = raw_json.get("plays", [])
        if not plays_data:
            return []

        # Pitcher state tracked per half-inning (TN-5).
        pitcher_state: dict[str, str | None] = {
            "top": None,
            "bottom": None,
        }

        parsed: list[ParsedPlay] = []

        for play in plays_data:
            final_details = play.get("final_details", [])

            # AC-9: Skip abandoned PAs (empty final_details).
            if not final_details:
                continue

            outcome = play.get("name_template", {}).get("template", "")
            play_order = play.get("order", 0)
            inning = play.get("inning", 0)
            half = play.get("half", "top")

            # Derive batting team from half.
            batting_team_id = away_team_id if half == "top" else home_team_id

            # Classify events and update pitcher state.
            events, pitcher_state, pitcher_at_first_pitch = cls._classify_events(
                play.get("at_plate_details", []),
                game_id=game_id,
                play_order=play_order,
                half=half,
                pitcher_state=pitcher_state,
            )

            # Skip non-PA markers (e.g. "Runner Out", "Inning Ended") that
            # have no batter UUID.  These are game-state events, not at-bats.
            if outcome in _NON_PA_OUTCOMES:
                logger.debug(
                    "Skipping non-PA outcome %r for game=%s play_order=%d.",
                    outcome,
                    game_id,
                    play_order,
                )
                continue

            # Extract batter from first UUID in first final_details template (AC-8).
            batter_id = cls._extract_batter_id(final_details)
            if batter_id is None:
                # If we can't identify the batter, skip this play.
                logger.warning(
                    "Could not extract batter_id for game=%s play_order=%d; skipping.",
                    game_id,
                    play_order,
                )
                continue

            # Determine pitcher (TN-1 + TN-5 reconciliation):
            # If a mid-PA pitcher sub occurred (pitcher_state changed after
            # first pitch), use the pitcher who threw pitch 1 (TN-1).
            # This applies even when pitcher_at_first_pitch is None (starter
            # unknown) -- the play stays NULL rather than being silently
            # reassigned to the reliever.
            # When no mid-PA sub occurred, explicit final_details overrides
            # tracked state (TN-5 step 4 -- ground truth correction).
            mid_pa_sub = pitcher_state.get(half) != pitcher_at_first_pitch
            if mid_pa_sub:
                pitcher_id = pitcher_at_first_pitch
            else:
                explicit_pitcher = cls._extract_pitcher_from_final_details(
                    final_details,
                )
                if explicit_pitcher is not None:
                    pitcher_id = explicit_pitcher
                    # Backfill pitcher_state so subsequent plays in this
                    # half inherit the pitcher when final_details omit the
                    # explicit reference (e.g., Singles, Fly Outs).  This
                    # handles the common case where the starting pitcher is
                    # never announced via a "Lineup changed" substitution.
                    pitcher_state[half] = explicit_pitcher
                else:
                    pitcher_id = pitcher_at_first_pitch or pitcher_state.get(half)

            # Count pitches (only pitch events).
            pitch_events = [e for e in events if e.event_type == "pitch"]
            pitch_count = len(pitch_events)

            # Compute FPS (AC-5, TN-1).
            is_fps = cls._compute_fps(pitch_events)

            # Compute QAB (AC-6, AC-7, TN-2).
            is_qab = cls._compute_qab(
                outcome=outcome,
                pitch_events=pitch_events,
                pitch_count=pitch_count,
                final_details=final_details,
            )

            # Score and outs.
            home_score = play.get("home_score", 0)
            away_score = play.get("away_score", 0)
            did_score_change = 1 if play.get("did_score_change", False) else 0
            outs_after = play.get("outs", 0)
            did_outs_change = 1 if play.get("did_outs_change", False) else 0

            parsed.append(ParsedPlay(
                game_id=game_id,
                play_order=play_order,
                inning=inning,
                half=half,
                season_id=season_id,
                batting_team_id=batting_team_id,
                batter_id=batter_id,
                pitcher_id=pitcher_id,
                outcome=outcome,
                pitch_count=pitch_count,
                is_first_pitch_strike=is_fps,
                is_qab=is_qab,
                home_score=home_score,
                away_score=away_score,
                did_score_change=did_score_change,
                outs_after=outs_after,
                did_outs_change=did_outs_change,
                events=events,
            ))

        # Post-parse backfill: retroactively assign pitcher_id to plays at
        # the start of a half that occurred before the first explicit pitcher
        # reference.  Within a half, the same pitcher is pitching for all
        # consecutive plays before any pitching change.
        for half_key in ("top", "bottom"):
            half_plays = [p for p in parsed if p.half == half_key]
            if not half_plays:
                continue
            # Find the first play with a known pitcher.
            first_known_pitcher: str | None = None
            first_known_idx: int | None = None
            for i, p in enumerate(half_plays):
                if p.pitcher_id is not None:
                    first_known_pitcher = p.pitcher_id
                    first_known_idx = i
                    break
            if first_known_pitcher is None or first_known_idx == 0:
                continue
            # Backfill preceding plays in the same half.
            for p in half_plays[:first_known_idx]:
                if p.pitcher_id is None:
                    p.pitcher_id = first_known_pitcher

        return parsed

    # ------------------------------------------------------------------
    # Event classification (TN-4)
    # ------------------------------------------------------------------

    @classmethod
    def _classify_events(
        cls,
        at_plate_details: list[dict[str, Any]],
        *,
        game_id: str,
        play_order: int,
        half: str,
        pitcher_state: dict[str, str | None],
    ) -> tuple[list[ParsedEvent], dict[str, str | None], str | None]:
        """Classify each at_plate_details entry and update pitcher state.

        Args:
            at_plate_details: Raw event dicts from the API.
            game_id: For logging context.
            play_order: For logging context.
            half: Current half-inning ('top' or 'bottom').
            pitcher_state: Mutable pitcher tracking dict (updated in-place
                and returned).

        Returns:
            Tuple of (classified events, updated pitcher state,
            pitcher_at_first_pitch).  ``pitcher_at_first_pitch`` is the
            pitcher_id active when the first pitch was thrown in this PA,
            or the current pitcher_state if no pitch events exist.  This
            ensures mid-PA subs (TN-1) credit the play to the pitcher who
            threw pitch 1, while pre-PA lineup changes still set the pitcher
            correctly.
        """
        events: list[ParsedEvent] = []
        first_pitch_found = False
        # Track the pitcher active at the moment the first pitch is thrown.
        # Pre-pitch substitutions (initial lineup changes) update this;
        # post-pitch substitutions do not.
        pitcher_at_first_pitch: str | None = pitcher_state.get(half)

        for i, detail in enumerate(at_plate_details):
            template = detail.get("template", "")

            event_type, pitch_result = cls._classify_template(
                template, game_id=game_id, play_order=play_order,
            )

            is_first_pitch = False
            if event_type == "pitch" and not first_pitch_found:
                is_first_pitch = True
                first_pitch_found = True
                # Snapshot pitcher at the moment of the first pitch.
                pitcher_at_first_pitch = pitcher_state.get(half)

            # Update pitcher state from substitution events (TN-5, step 2).
            if event_type == "substitution":
                new_pitcher_id = cls._extract_pitcher_sub(template)
                if new_pitcher_id is not None:
                    pitcher_state[half] = new_pitcher_id

            events.append(ParsedEvent(
                event_order=i,
                event_type=event_type,
                pitch_result=pitch_result,
                is_first_pitch=is_first_pitch,
                raw_template=template,
            ))

        return events, pitcher_state, pitcher_at_first_pitch

    @classmethod
    def _classify_template(
        cls,
        template: str,
        *,
        game_id: str,
        play_order: int,
    ) -> tuple[str, str | None]:
        """Classify a single at_plate_details template string.

        Returns:
            Tuple of (event_type, pitch_result).  pitch_result is None for
            non-pitch events.
        """
        # 1. Check pitch templates (exact match).
        pitch_result = _PITCH_TEMPLATES.get(template)
        if pitch_result is not None:
            return "pitch", pitch_result

        # 2. Check substitution patterns.
        if cls._is_substitution(template):
            return "substitution", None

        # 3. Check baserunner patterns (must contain UUID + keyword).
        if cls._is_baserunner(template):
            return "baserunner", None

        # 4. Unknown template -- log warning (AC-13).
        logger.warning(
            "Unknown at_plate_details template: game_id=%s play_order=%d template=%r",
            game_id,
            play_order,
            template,
        )
        return "other", None

    @staticmethod
    def _is_substitution(template: str) -> bool:
        """Check if a template is a substitution event."""
        for prefix in _SUBSTITUTION_STARTS:
            if template.startswith(prefix):
                return True
        for keyword in _SUBSTITUTION_CONTAINS:
            if keyword in template:
                return True
        return False

    # Keywords that classify as baserunner even without a UUID token.
    _UUID_FREE_BASERUNNER = frozenset({"Pickoff attempt", "Outs changed"})

    @classmethod
    def _is_baserunner(cls, template: str) -> bool:
        """Check if a template is a baserunner event.

        Baserunner events contain ``${uuid}`` tokens AND navigation keywords.
        Exception: "Pickoff attempt" and "Outs changed" templates may not
        contain a UUID.
        """
        has_uuid = "${" in template
        for keyword in _BASERUNNER_KEYWORDS:
            if keyword in template:
                if keyword in cls._UUID_FREE_BASERUNNER:
                    return True
                if has_uuid:
                    return True
        return False

    @staticmethod
    def _extract_pitcher_sub(template: str) -> str | None:
        """Extract the new pitcher's UUID from a substitution template.

        Patterns:
        - ``"Lineup changed: ${new} in at pitcher"`` -- new pitcher is the only/first UUID.
        - ``"${new} in for pitcher ${old}"`` -- new pitcher is the FIRST UUID.

        In both cases the new pitcher is the first ``${uuid}`` in the template.

        Returns:
            The new pitcher's UUID, or None if this substitution is not
            pitcher-related.
        """
        if "in at pitcher" in template or "in for pitcher" in template:
            uuids = _UUID_PATTERN.findall(template)
            if uuids:
                return uuids[0]
        return None

    # ------------------------------------------------------------------
    # Player ID extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_batter_id(final_details: list[dict[str, Any]]) -> str | None:
        """Extract the batter UUID from the first final_details template.

        The batter is always the first ``${uuid}`` in the first template.

        Returns:
            Batter UUID string, or None if not found.
        """
        if not final_details:
            return None
        first_template = final_details[0].get("template", "")
        uuids = _UUID_PATTERN.findall(first_template)
        return uuids[0] if uuids else None

    @staticmethod
    def _extract_pitcher_from_final_details(
        final_details: list[dict[str, Any]],
    ) -> str | None:
        """Extract explicit pitcher UUID from final_details.

        Looks for patterns like ``"${uuid} pitching"`` in any final_details
        template.  When present, this overrides the tracked pitcher state.

        Returns:
            Pitcher UUID string, or None if no explicit pitcher reference.
        """
        for detail in final_details:
            template = detail.get("template", "")
            match = _PITCHER_EXPLICIT_PATTERN.search(template)
            if match:
                return match.group(1)
        return None

    # ------------------------------------------------------------------
    # FPS computation (TN-1, AC-5)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_fps(pitch_events: list[ParsedEvent]) -> int:
        """Compute ``is_first_pitch_strike`` for a plate appearance.

        The first pitch event (the one with ``is_first_pitch=True``) determines
        the FPS value.  A strike, foul, foul tip, or in-play result on the
        first pitch = 1.

        Returns:
            1 if the first pitch was a strike, 0 otherwise.
        """
        for event in pitch_events:
            if event.is_first_pitch:
                return 1 if event.pitch_result in _FPS_STRIKE_RESULTS else 0
        # No pitch events (shouldn't happen for non-abandoned PAs).
        return 0

    # ------------------------------------------------------------------
    # QAB computation (TN-2, AC-6, AC-7)
    # ------------------------------------------------------------------

    @classmethod
    def _compute_qab(
        cls,
        *,
        outcome: str,
        pitch_events: list[ParsedEvent],
        pitch_count: int,
        final_details: list[dict[str, Any]],
    ) -> int:
        """Compute ``is_qab`` for a plate appearance.

        Returns 1 if any of the 7 QAB conditions are met, 0 otherwise.
        Explicitly excludes IBB, D3S, and CI outcomes.

        Returns:
            1 for quality at-bat, 0 otherwise.
        """
        # Exclusions first (TN-2).
        if outcome in _QAB_EXCLUDED_OUTCOMES:
            return 0

        # Condition 1: 2S+3 (AC-7).
        if cls._check_2s_plus_3(pitch_events):
            return 1

        # Condition 2: 6+ pitches.
        if pitch_count >= 6:
            return 1

        # Condition 3: XBH.
        if outcome in _XBH_OUTCOMES:
            return 1

        # Condition 4: HHB (hard-hit ball) -- case-insensitive substring.
        if cls._check_hhb(final_details):
            return 1

        # Condition 5: BB (Walk, not Intentional Walk).
        if outcome == "Walk":
            return 1

        # Condition 6 & 7: SAC Bunt / SAC Fly.
        if outcome in _SAC_OUTCOMES:
            return 1

        return 0

    @staticmethod
    def _check_2s_plus_3(pitch_events: list[ParsedEvent]) -> bool:
        """Check the 2S+3 QAB condition.

        Counts pitches after the batter reaches a 2-strike count.  Fouls on
        a 2-strike count count as pitches seen but do NOT advance the strike
        count.  The terminal pitch (the one that ends the PA) counts.

        Minimum total pitches for this condition: 5 (reach 2 strikes in 2
        pitches, then see 3 more).

        Returns:
            True if 3+ pitches were seen after reaching 2 strikes.
        """
        if len(pitch_events) < 5:
            return False

        strikes = 0
        pitches_after_2_strikes = 0

        for event in pitch_events:
            result = event.pitch_result
            if strikes >= 2:
                # Already at 2 strikes -- count every pitch.
                pitches_after_2_strikes += 1
            else:
                # Not yet at 2 strikes -- check if this pitch advances count.
                if result in ("strike_looking", "strike_swinging"):
                    strikes += 1
                elif result == "foul" and strikes < 2:
                    # Foul before 2 strikes advances the count.
                    strikes += 1
                elif result == "foul_tip":
                    # Foul tip always counts as a strike.
                    strikes += 1
                # Balls and in_play before 2 strikes don't advance strikes.

        return pitches_after_2_strikes >= 3

    @staticmethod
    def _check_hhb(final_details: list[dict[str, Any]]) -> bool:
        """Check for hard-hit ball (line drive or hard ground ball).

        Scans all final_details templates for case-insensitive matches
        of "line drive" or "hard ground ball".

        Returns:
            True if any HHB pattern matches.
        """
        for detail in final_details:
            template = detail.get("template", "")
            for pattern in _HHB_PATTERNS:
                if pattern.search(template):
                    return True
        return False
