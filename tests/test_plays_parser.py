"""Tests for the PlaysParser module (E-195-02).

Covers:
- Template classification (pitch, baserunner, substitution, other)
- Batter and pitcher ID extraction
- Pitch counting
- FPS (first pitch strike) computation
- QAB (quality at-bat) computation with all 7 conditions
- Abandoned play skipping
- Pitcher state tracking across innings
- Unknown template handling
- Edge cases: IBB, D3S, foul bunt, HHB, SAC bunt/fly, 2S+3
- Real-fixture tests against game-plays-fresh.json (AC-11)

Run with:
    pytest tests/test_plays_parser.py -v
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src.gamechanger.parsers.plays_parser import (
    ParsedEvent,
    ParsedPlay,
    PlaysParser,
)

# ---------------------------------------------------------------------------
# Helper to build a minimal play dict
# ---------------------------------------------------------------------------

_BATTER_UUID = "aaaaaaaa-1111-2222-3333-444444444444"
_PITCHER_UUID = "bbbbbbbb-1111-2222-3333-444444444444"
_PITCHER2_UUID = "cccccccc-1111-2222-3333-444444444444"
_FIELDER_UUID = "dddddddd-1111-2222-3333-444444444444"
_RUNNER_UUID = "eeeeeeee-1111-2222-3333-444444444444"


def _make_play(
    *,
    order: int = 0,
    inning: int = 1,
    half: str = "top",
    outcome: str = "Single",
    at_plate_details: list[dict[str, str]] | None = None,
    final_details: list[dict[str, str]] | None = None,
    home_score: int = 0,
    away_score: int = 0,
    did_score_change: bool = False,
    outs: int = 0,
    did_outs_change: bool = False,
) -> dict:
    """Build a minimal play dict matching the API shape."""
    if final_details is None:
        final_details = [
            {"template": f"${{{_BATTER_UUID}}} singles on a line drive to center fielder ${{{_FIELDER_UUID}}}"}
        ]
    if at_plate_details is None:
        at_plate_details = [
            {"template": "Strike 1 looking"},
            {"template": "In play"},
        ]
    return {
        "order": order,
        "inning": inning,
        "half": half,
        "name_template": {"template": outcome},
        "home_score": home_score,
        "away_score": away_score,
        "did_score_change": did_score_change,
        "outs": outs,
        "did_outs_change": did_outs_change,
        "at_plate_details": at_plate_details,
        "final_details": final_details,
        "messages": [],
    }


def _make_raw_json(plays: list[dict]) -> dict:
    """Wrap plays in a minimal top-level response."""
    return {
        "sport": "baseball",
        "team_players": {
            "shortSlug": [
                {"id": _BATTER_UUID, "first_name": "Test", "last_name": "Batter", "number": "1"},
                {"id": _RUNNER_UUID, "first_name": "Test", "last_name": "Runner", "number": "2"},
            ],
            "00000000-0000-0000-0000-000000000002": [
                {"id": _PITCHER_UUID, "first_name": "Test", "last_name": "Pitcher", "number": "10"},
                {"id": _PITCHER2_UUID, "first_name": "Relief", "last_name": "Pitcher", "number": "11"},
                {"id": _FIELDER_UUID, "first_name": "Test", "last_name": "Fielder", "number": "20"},
            ],
        },
        "plays": plays,
    }


_GAME_ID = "test-game-001"
_SEASON_ID = "2026"
_HOME_TEAM_ID = 1
_AWAY_TEAM_ID = 2


def _parse_full(plays: list[dict]):
    """Convenience: wrap plays in JSON and parse, returning the full result.

    Use this when the test cares about the derived final score; use
    :func:`_parse` when it only cares about the parsed plays.
    """
    return PlaysParser.parse_game(
        _make_raw_json(plays),
        game_id=_GAME_ID,
        season_id=_SEASON_ID,
        home_team_id=_HOME_TEAM_ID,
        away_team_id=_AWAY_TEAM_ID,
    )


def _parse(plays: list[dict]) -> list[ParsedPlay]:
    """Convenience: wrap plays in JSON and parse, returning just the plays."""
    return _parse_full(plays).plays


# ---------------------------------------------------------------------------
# Tests: Basic parsing
# ---------------------------------------------------------------------------


class TestBasicParsing:
    """Verify fundamental parse_game behavior."""

    def test_empty_plays_returns_empty_list(self):
        raw = _make_raw_json([])
        result = PlaysParser.parse_game(
            raw, _GAME_ID, _SEASON_ID, _HOME_TEAM_ID, _AWAY_TEAM_ID,
        )
        assert result.plays == []

    def test_single_play_parses_correctly(self):
        plays = [_make_play()]
        result = _parse(plays)
        assert len(result) == 1
        play = result[0]
        assert play.game_id == _GAME_ID
        assert play.play_order == 0
        assert play.inning == 1
        assert play.half == "top"
        assert play.outcome == "Single"
        assert play.batter_id == _BATTER_UUID
        assert play.season_id == _SEASON_ID

    def test_batting_team_derived_from_half_top(self):
        """Top of inning: away team is batting."""
        plays = [_make_play(half="top")]
        result = _parse(plays)
        assert result[0].batting_team_id == _AWAY_TEAM_ID

    def test_batting_team_derived_from_half_bottom(self):
        """Bottom of inning: home team is batting."""
        plays = [_make_play(half="bottom")]
        result = _parse(plays)
        assert result[0].batting_team_id == _HOME_TEAM_ID

    def test_score_fields_captured(self):
        plays = [_make_play(
            home_score=3, away_score=2,
            did_score_change=True,
            outs=1, did_outs_change=True,
        )]
        result = _parse(plays)
        play = result[0]
        assert play.home_score == 3
        assert play.away_score == 2
        assert play.did_score_change == 1
        assert play.outs_after == 1
        assert play.did_outs_change == 1

    def test_multiple_plays_maintain_order(self):
        plays = [
            _make_play(order=0, outcome="Single"),
            _make_play(order=1, outcome="Fly Out"),
            _make_play(order=2, outcome="Walk"),
        ]
        result = _parse(plays)
        assert len(result) == 3
        assert [p.play_order for p in result] == [0, 1, 2]
        assert [p.outcome for p in result] == ["Single", "Fly Out", "Walk"]


# ---------------------------------------------------------------------------
# Tests: Abandoned PA skipping (AC-9)
# ---------------------------------------------------------------------------


class TestAbandonedPAs:
    """Verify abandoned plate appearances are excluded."""

    def test_empty_final_details_skipped(self):
        plays = [
            _make_play(order=0, outcome="Single"),
            _make_play(
                order=1,
                outcome=f"${{{_BATTER_UUID}}} at bat",
                final_details=[],
                at_plate_details=[],
            ),
        ]
        result = _parse(plays)
        assert len(result) == 1
        assert result[0].play_order == 0

    def test_only_abandoned_plays_returns_empty(self):
        plays = [
            _make_play(order=0, final_details=[], at_plate_details=[]),
        ]
        result = _parse(plays)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: Event classification (AC-4)
# ---------------------------------------------------------------------------


class TestEventClassification:
    """Verify template classification into pitch/baserunner/substitution/other."""

    @pytest.mark.parametrize("template,expected_type,expected_result", [
        ("Ball 1", "pitch", "ball"),
        ("Ball 2", "pitch", "ball"),
        ("Ball 3", "pitch", "ball"),
        ("Ball 4", "pitch", "ball"),
        ("Strike 1 looking", "pitch", "strike_looking"),
        ("Strike 2 looking", "pitch", "strike_looking"),
        ("Strike 3 looking", "pitch", "strike_looking"),
        ("Strike 1 swinging", "pitch", "strike_swinging"),
        ("Strike 2 swinging", "pitch", "strike_swinging"),
        ("Strike 3 swinging", "pitch", "strike_swinging"),
        ("Foul", "pitch", "foul"),
        ("Foul tip", "pitch", "foul_tip"),
        ("In play", "pitch", "in_play"),
        ("Foul bunt", "pitch", "foul"),
    ])
    def test_pitch_event_classification(self, template, expected_type, expected_result):
        plays = [_make_play(at_plate_details=[{"template": template}])]
        result = _parse(plays)
        event = result[0].events[0]
        assert event.event_type == expected_type
        assert event.pitch_result == expected_result

    def test_baserunner_event_classification(self):
        template = f"${{{_RUNNER_UUID}}} steals 2nd"
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": template},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        events = result[0].events
        assert events[0].event_type == "pitch"
        assert events[1].event_type == "baserunner"
        assert events[1].pitch_result is None
        assert events[2].event_type == "pitch"

    def test_pickoff_attempt_classified_as_baserunner(self):
        """Pickoff attempt doesn't necessarily contain a UUID."""
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": "Pickoff attempt at 1st"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[1].event_type == "baserunner"

    def test_outs_changed_classified_as_baserunner(self):
        """'Outs changed to N' is a UUID-free game-state event."""
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": "Outs changed to 1"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[1].event_type == "baserunner"

    def test_substitution_lineup_changed(self):
        template = f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"
        plays = [_make_play(at_plate_details=[
            {"template": template},
            {"template": "Ball 1"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].event_type == "substitution"
        assert result[0].events[0].pitch_result is None

    def test_substitution_play_edit(self):
        template = f"(Play Edit) ${{{_PITCHER_UUID}}} in for ${{{_PITCHER2_UUID}}}"
        plays = [_make_play(at_plate_details=[
            {"template": template},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].event_type == "substitution"

    def test_substitution_in_for_pitcher(self):
        template = f"${{{_PITCHER2_UUID}}} in for pitcher ${{{_PITCHER_UUID}}}"
        plays = [_make_play(at_plate_details=[
            {"template": template},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].event_type == "substitution"

    def test_substitution_courtesy_runner(self):
        template = f"Courtesy runner ${{{_RUNNER_UUID}}} in for ${{{_BATTER_UUID}}}"
        plays = [_make_play(at_plate_details=[
            {"template": template},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].event_type == "substitution"

    def test_foul_bunt_classified_as_foul_pitch(self):
        """AC-4: Foul bunt is a pitch event with pitch_result=foul."""
        plays = [_make_play(at_plate_details=[
            {"template": "Foul bunt"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].event_type == "pitch"
        assert result[0].events[0].pitch_result == "foul"


# ---------------------------------------------------------------------------
# Tests: Unknown template handling (AC-10, AC-13)
# ---------------------------------------------------------------------------


class TestUnknownTemplates:
    """Verify unknown templates are classified as 'other' and logged."""

    def test_unknown_template_classified_as_other(self):
        plays = [_make_play(at_plate_details=[
            {"template": "Something completely unexpected"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].event_type == "other"
        assert result[0].events[0].pitch_result is None

    def test_unknown_template_logged_as_warning(self, caplog):
        """AC-13: Unknown templates produce WARNING log with game_id and play_order."""
        with caplog.at_level(logging.WARNING):
            plays = [_make_play(
                order=7,
                at_plate_details=[
                    {"template": "Mysterious event happened"},
                    {"template": "In play"},
                ],
            )]
            _parse(plays)

        assert any(
            "Unknown at_plate_details template" in record.message
            and "test-game-001" in record.message
            and "play_order=7" in record.message
            and "Mysterious event happened" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# Tests: Pitch counting
# ---------------------------------------------------------------------------


class TestPitchCounting:
    """Verify pitch_count only includes pitch events."""

    def test_counts_only_pitch_events(self):
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": f"${{{_RUNNER_UUID}}} steals 2nd"},
            {"template": "Strike 1 looking"},
            {"template": "Foul"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].pitch_count == 4  # Ball, Strike, Foul, In play (not steal)

    def test_substitution_not_counted(self):
        plays = [_make_play(at_plate_details=[
            {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
            {"template": "Ball 1"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].pitch_count == 2

    def test_foul_bunt_counted_as_pitch(self):
        plays = [_make_play(at_plate_details=[
            {"template": "Foul bunt"},
            {"template": "Strike 2 swinging"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].pitch_count == 3


# ---------------------------------------------------------------------------
# Tests: FPS (AC-5, TN-1)
# ---------------------------------------------------------------------------


class TestFPS:
    """Verify is_first_pitch_strike computation."""

    @pytest.mark.parametrize("first_pitch,expected_fps", [
        ("Strike 1 looking", 1),
        ("Strike 1 swinging", 1),
        ("Foul", 1),
        ("Foul tip", 1),
        ("In play", 1),
        ("Ball 1", 0),
    ])
    def test_fps_by_first_pitch_type(self, first_pitch, expected_fps):
        plays = [_make_play(at_plate_details=[
            {"template": first_pitch},
        ])]
        result = _parse(plays)
        assert result[0].is_first_pitch_strike == expected_fps

    def test_fps_skips_non_pitch_events(self):
        """Baserunner event before first pitch should be skipped for FPS."""
        plays = [_make_play(at_plate_details=[
            {"template": f"${{{_RUNNER_UUID}}} steals 2nd"},
            {"template": "Strike 1 looking"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].is_first_pitch_strike == 1

    def test_fps_skips_substitution_events(self):
        """Substitution event before first pitch should be skipped."""
        plays = [_make_play(at_plate_details=[
            {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
            {"template": "Ball 1"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].is_first_pitch_strike == 0

    def test_fps_computed_for_hbp_outcome(self):
        """AC-5: FPS computed for HBP (exclusion from FPS% at query time)."""
        plays = [_make_play(
            outcome="Hit By Pitch",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Ball 2"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} is hit by pitch, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_first_pitch_strike == 0  # Ball 1 is not a strike

    def test_fps_computed_for_intentional_walk(self):
        """AC-5: FPS computed for IBB (exclusion from FPS% at query time)."""
        plays = [_make_play(
            outcome="Intentional Walk",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Ball 2"},
                {"template": "Ball 3"},
                {"template": "Ball 4"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} walks, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_first_pitch_strike == 0

    def test_fps_first_pitch_marked_in_events(self):
        """Only the first pitch event has is_first_pitch=True."""
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": "Strike 1 looking"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        events = result[0].events
        assert events[0].is_first_pitch is True
        assert events[1].is_first_pitch is False
        assert events[2].is_first_pitch is False

    def test_foul_bunt_as_first_pitch_is_strike(self):
        """Foul bunt on first pitch counts as FPS."""
        plays = [_make_play(at_plate_details=[
            {"template": "Foul bunt"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].is_first_pitch_strike == 1


# ---------------------------------------------------------------------------
# Tests: QAB (AC-6, AC-7, TN-2)
# ---------------------------------------------------------------------------


class TestQAB:
    """Verify is_qab computation with all 7 conditions and exclusions."""

    def test_qab_walk(self):
        """Condition: BB (Walk)."""
        plays = [_make_play(
            outcome="Walk",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Ball 2"},
                {"template": "Ball 3"},
                {"template": "Ball 4"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} walks, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_xbh_double(self):
        """Condition: XBH (Double)."""
        plays = [_make_play(outcome="Double")]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_xbh_triple(self):
        """Condition: XBH (Triple)."""
        plays = [_make_play(outcome="Triple")]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_xbh_home_run(self):
        """Condition: XBH (Home Run)."""
        plays = [_make_play(outcome="Home Run")]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_sac_bunt(self):
        """Condition: SAC Bunt."""
        plays = [_make_play(
            outcome="Sacrifice Bunt",
            at_plate_details=[
                {"template": "Foul bunt"},
                {"template": "In play"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} sacrifice bunts to third baseman ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_sac_fly(self):
        """Condition: SAC Fly."""
        plays = [_make_play(
            outcome="Sacrifice Fly",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "In play"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} hits a sacrifice fly to right fielder ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_hhb_line_drive(self):
        """Condition: HHB (line drive)."""
        plays = [_make_play(
            outcome="Single",
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} singles on a line drive to center fielder ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_hhb_hard_ground_ball(self):
        """Condition: HHB (hard ground ball)."""
        plays = [_make_play(
            outcome="Single",
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} singles on a hard ground ball to shortstop ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_hhb_case_insensitive(self):
        """HHB detection is case-insensitive."""
        plays = [_make_play(
            outcome="Single",
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} singles on a Line Drive to center fielder ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_six_plus_pitches(self):
        """Condition: 6+ pitches."""
        plays = [_make_play(
            outcome="Fly Out",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Strike 1 looking"},
                {"template": "Ball 2"},
                {"template": "Foul"},
                {"template": "Ball 3"},
                {"template": "In play"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} flies out to right fielder ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1
        assert result[0].pitch_count == 6

    def test_qab_2s_plus_3_basic(self):
        """Condition: 2S+3 (3 pitches after reaching 2-strike count).

        Sequence: Strike, Strike, Foul, Foul, In play = 5 pitches.
        After 2 strikes: Foul, Foul, In play = 3 pitches after 2S.
        """
        plays = [_make_play(
            outcome="Fly Out",
            at_plate_details=[
                {"template": "Strike 1 looking"},
                {"template": "Strike 2 swinging"},
                {"template": "Foul"},
                {"template": "Foul"},
                {"template": "In play"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} flies out to left fielder ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 1

    def test_qab_2s_plus_3_fouls_dont_advance_past_2_strikes(self):
        """Fouls on 2-strike count count as pitches but don't advance strikes."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Strike 1 swinging"},
                {"template": "Strike 2 swinging"},
                {"template": "Foul"},
                {"template": "Foul"},
                {"template": "Strike 3 swinging"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        # 3 pitches after 2 strikes: Foul, Foul, Strike 3 = 3
        assert result[0].is_qab == 1

    def test_qab_2s_plus_3_minimum_5_pitches(self):
        """2S+3 requires minimum 5 total pitches."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Strike 1 swinging"},
                {"template": "Strike 2 swinging"},
                {"template": "Strike 3 looking"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out looking, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        # Only 3 pitches total -- doesn't meet 5-pitch minimum.
        # Only 1 pitch after 2 strikes -- doesn't meet 3-pitch threshold.
        assert result[0].is_qab == 0

    def test_qab_2s_plus_3_with_balls(self):
        """2S+3 with balls mixed in."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Strike 1 looking"},
                {"template": "Ball 2"},
                {"template": "Strike 2 swinging"},
                {"template": "Ball 3"},
                {"template": "Foul"},
                {"template": "Strike 3 looking"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out looking, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        # After 2 strikes (at pitch 4): Ball 3, Foul, Strike 3 = 3 pitches
        assert result[0].is_qab == 1

    def test_qab_2s_plus_3_foul_tip_advances_strike_count(self):
        """Foul tip always counts as a strike for advancing the count."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Strike 1 swinging"},
                {"template": "Foul tip"},  # This is strike 2
                {"template": "Ball 1"},
                {"template": "Foul"},
                {"template": "Strike 3 swinging"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        # Strike 1, Foul tip (strike 2), then: Ball, Foul, Strike 3 = 3 after 2S
        assert result[0].is_qab == 1

    def test_qab_not_enough_after_2_strikes(self):
        """Less than 3 pitches after 2 strikes = no 2S+3."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Strike 1 swinging"},
                {"template": "Ball 2"},
                {"template": "Strike 2 swinging"},
                {"template": "Strike 3 looking"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out looking, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        # After 2 strikes: only Strike 3 = 1 pitch. Not 3.
        # 5 pitches but only 5 pitch_count (doesn't hit 6).
        assert result[0].is_qab == 0

    # --- QAB Exclusions ---

    def test_qab_excluded_intentional_walk(self):
        """AC-6: IBB is explicitly excluded from QAB."""
        plays = [_make_play(
            outcome="Intentional Walk",
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "Ball 2"},
                {"template": "Ball 3"},
                {"template": "Ball 4"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} walks, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 0

    def test_qab_excluded_dropped_3rd_strike(self):
        """D3S is excluded from QAB."""
        plays = [_make_play(
            outcome="Dropped 3rd Strike",
            at_plate_details=[
                {"template": "Strike 1 looking"},
                {"template": "Foul"},
                {"template": "Strike 2 swinging"},
                {"template": "Foul"},
                {"template": "Foul"},
                {"template": "Strike 3 swinging"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} reaches on dropped 3rd strike"},
            ],
        )]
        result = _parse(plays)
        # Even though it has 6 pitches, D3S is excluded.
        assert result[0].is_qab == 0

    def test_qab_excluded_catchers_interference(self):
        """CI is excluded from QAB."""
        plays = [_make_play(
            outcome="Catcher's Interference",
            at_plate_details=[
                {"template": "Ball 1"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} reaches on catcher's interference"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 0

    def test_qab_not_triggered_for_ground_out(self):
        """Regular ground out with 2 pitches is not QAB."""
        plays = [_make_play(
            outcome="Ground Out",
            at_plate_details=[
                {"template": "Strike 1 looking"},
                {"template": "In play"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} grounds out to first baseman ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].is_qab == 0


# ---------------------------------------------------------------------------
# Tests: Pitcher identification (AC-8, TN-5)
# ---------------------------------------------------------------------------


class TestPitcherIdentification:
    """Verify pitcher ID extraction and state tracking."""

    def test_pitcher_from_explicit_final_details(self):
        """Explicit '${uuid} pitching' in final_details is used."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Strike 1 looking"},
                {"template": "Strike 2 swinging"},
                {"template": "Strike 3 swinging"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        assert result[0].pitcher_id == _PITCHER_UUID

    def test_pitcher_from_substitution_tracked_state(self):
        """Pitcher state set by substitution event is used when no explicit ref."""
        plays = [
            _make_play(
                order=0,
                half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles on a ground ball to shortstop ${{{_FIELDER_UUID}}}"},
                ],
            ),
            _make_play(
                order=1,
                half="top",
                at_plate_details=[
                    {"template": "In play"},
                ],
                # No explicit pitcher ref in final_details.
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} flies out to center fielder ${{{_FIELDER_UUID}}}"},
                ],
            ),
        ]
        result = _parse(plays)
        # Second play should use tracked pitcher state.
        assert result[1].pitcher_id == _PITCHER_UUID

    def test_pitcher_state_persists_across_innings_same_half(self):
        """Pitcher state persists across innings within the same half (TN-5)."""
        plays = [
            # Inning 1 top: set pitcher via substitution.
            _make_play(
                order=0, inning=1, half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "In play"},
                ],
            ),
            # Inning 2 top: pitcher should still be the same.
            _make_play(
                order=1, inning=2, half="top",
                at_plate_details=[
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} flies out to center fielder ${{{_FIELDER_UUID}}}"},
                ],
            ),
        ]
        result = _parse(plays)
        assert result[1].pitcher_id == _PITCHER_UUID

    def test_pitcher_state_independent_per_half(self):
        """Top and bottom have independent pitcher tracking."""
        plays = [
            # Top 1: set top pitcher.
            _make_play(
                order=0, inning=1, half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "In play"},
                ],
            ),
            # Bottom 1: no pitcher set yet.
            _make_play(
                order=1, inning=1, half="bottom",
                at_plate_details=[
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles on a ground ball to shortstop ${{{_FIELDER_UUID}}}"},
                ],
            ),
        ]
        result = _parse(plays)
        # Top pitcher set.
        assert result[0].pitcher_id == _PITCHER_UUID
        # Bottom pitcher not set -- should be None.
        assert result[1].pitcher_id is None

    def test_pitcher_substitution_mid_game(self):
        """Pitcher substitution updates tracked state for subsequent plays."""
        plays = [
            _make_play(
                order=0, inning=1, half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "In play"},
                ],
            ),
            _make_play(
                order=1, inning=3, half="top",
                at_plate_details=[
                    {"template": f"${{{_PITCHER2_UUID}}} in for pitcher ${{{_PITCHER_UUID}}}"},
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} flies out to center fielder ${{{_FIELDER_UUID}}}"},
                ],
            ),
            _make_play(
                order=2, inning=3, half="top",
                at_plate_details=[
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} grounds out to first baseman ${{{_FIELDER_UUID}}}"},
                ],
            ),
        ]
        result = _parse(plays)
        assert result[0].pitcher_id == _PITCHER_UUID
        assert result[1].pitcher_id == _PITCHER2_UUID
        assert result[2].pitcher_id == _PITCHER2_UUID

    def test_mid_pa_pitcher_change_credits_original_pitcher(self):
        """Mid-PA pitching change credits the play to the pitcher who started the PA.

        TN-1: FPS is credited to the pitcher who threw pitch 1, even if a
        mid-PA pitching change occurs.  The substitution updates state for
        subsequent plays but must not retroactively reassign the current PA.

        Critically, even when final_details contains an explicit
        ``"${reliever} pitching"`` reference, the pitcher_at_first_pitch
        snapshot takes priority -- final_details would reference the
        reliever, which would undo the mid-PA protection.
        """
        plays = [
            # Play 0: establish pitcher A.
            _make_play(
                order=0, inning=1, half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
            ),
            # Play 1: pitcher A throws pitch 1, then mid-PA sub to pitcher B.
            # final_details references reliever (pitcher B) with "pitching" --
            # but pitcher A should still get credit.
            _make_play(
                order=1, inning=1, half="top",
                at_plate_details=[
                    {"template": "Ball 1"},
                    {"template": f"${{{_PITCHER2_UUID}}} in for pitcher ${{{_PITCHER_UUID}}}"},
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} grounds out to first baseman ${{{_FIELDER_UUID}}}, ${{{_PITCHER2_UUID}}} pitching"},
                ],
            ),
            # Play 2: next PA should use pitcher B (the reliever).
            _make_play(
                order=2, inning=1, half="top",
                at_plate_details=[
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles on a ground ball to shortstop ${{{_FIELDER_UUID}}}"},
                ],
            ),
        ]
        result = _parse(plays)
        # Play 0: pitcher A established.
        assert result[0].pitcher_id == _PITCHER_UUID
        # Play 1: mid-PA sub -- credited to pitcher A (who threw pitch 1),
        # NOT pitcher B even though final_details says "pitcher B pitching".
        assert result[1].pitcher_id == _PITCHER_UUID
        # Play 2: subsequent PA -- now pitcher B.
        assert result[2].pitcher_id == _PITCHER2_UUID

    def test_explicit_pitcher_overrides_tracked_state(self):
        """Explicit pitcher in final_details overrides tracked state (TN-5 step 4)."""
        plays = [
            # Set up tracked pitcher.
            _make_play(
                order=0, half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "In play"},
                ],
            ),
            # Explicit ref to a different pitcher.
            _make_play(
                order=1, half="top",
                outcome="Walk",
                at_plate_details=[
                    {"template": "Ball 1"},
                    {"template": "Ball 2"},
                    {"template": "Ball 3"},
                    {"template": "Ball 4"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} walks, ${{{_PITCHER2_UUID}}} pitching"},
                ],
            ),
        ]
        result = _parse(plays)
        assert result[1].pitcher_id == _PITCHER2_UUID

    def test_pitcher_null_when_unidentifiable(self):
        """Pitcher ID is None when no substitution and no explicit ref."""
        plays = [_make_play(
            at_plate_details=[{"template": "In play"}],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} singles on a ground ball to shortstop ${{{_FIELDER_UUID}}}"},
            ],
        )]
        result = _parse(plays)
        assert result[0].pitcher_id is None

    def test_null_pitcher_stays_null_on_mid_pa_sub(self):
        """When starter is unknown (None), mid-PA sub must not assign reliever.

        TN-1: if the pitcher who threw pitch 1 is unknown, the play stays
        NULL rather than being silently reassigned to the reliever via
        explicit final_details.
        """
        plays = [
            # Play 0: no pitcher identification at all -- pitch thrown with
            # pitcher_state empty, then mid-PA sub to pitcher B.
            _make_play(
                order=0, inning=1, half="top",
                at_plate_details=[
                    {"template": "Ball 1"},
                    {"template": f"${{{_PITCHER2_UUID}}} in for pitcher ${{{_PITCHER_UUID}}}"},
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} grounds out, ${{{_PITCHER2_UUID}}} pitching"},
                ],
            ),
        ]
        result = _parse(plays)
        # Starter unknown + mid-PA sub -> pitcher stays None per TN-1.
        assert result[0].pitcher_id is None

    def test_pitcher_backfill_from_final_details(self):
        """Explicit pitcher in final_details backfills pitcher_state for subsequent plays.

        Scenario: bottom-half starting pitcher is never announced via a
        "Lineup changed: ... in at pitcher" substitution event.  The first
        play is a Strikeout whose final_details contains "${uuid} pitching".
        The second play is a Single with NO pitcher reference in
        final_details.  After the fix, the second play should inherit the
        pitcher discovered in the first play's final_details.
        """
        plays = [
            # Play 0 (bottom): Strikeout with explicit pitcher in final_details.
            # No "Lineup changed" event -- pitcher discovered only via final_details.
            _make_play(
                order=0, inning=1, half="bottom",
                outcome="Strikeout",
                at_plate_details=[
                    {"template": "Strike 1 looking"},
                    {"template": "Strike 2 swinging"},
                    {"template": "Strike 3 swinging"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
                ],
            ),
            # Play 1 (bottom): Single with NO pitcher reference in final_details.
            # Should inherit pitcher from play 0 via backfilled pitcher_state.
            _make_play(
                order=1, inning=1, half="bottom",
                outcome="Single",
                at_plate_details=[
                    {"template": "Ball 1"},
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles on a ground ball to shortstop ${{{_FIELDER_UUID}}}"},
                ],
            ),
        ]
        result = _parse(plays)
        # Play 0: pitcher identified from final_details.
        assert result[0].pitcher_id == _PITCHER_UUID
        # Play 1: pitcher inherited via backfilled pitcher_state.
        assert result[1].pitcher_id == _PITCHER_UUID

    def test_pitcher_backfill_retroactive_for_initial_plays(self):
        """Post-parse backfill assigns pitcher to plays before the first explicit reference.

        Scenario: 4 bottom-half plays.  Plays 0-1 have no pitcher in
        final_details.  Play 2 is a Strikeout with explicit pitcher A.
        Play 3 has no pitcher reference.  After backfill, all 4 plays
        should have pitcher_id = pitcher A.
        """
        plays = [
            # Play 0: Single, no pitcher reference.
            _make_play(
                order=0, inning=1, half="bottom",
                outcome="Single",
                at_plate_details=[{"template": "In play"}],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles to left field"},
                ],
            ),
            # Play 1: Single, no pitcher reference.
            _make_play(
                order=1, inning=1, half="bottom",
                outcome="Single",
                at_plate_details=[{"template": "In play"}],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles to right field"},
                ],
            ),
            # Play 2: Strikeout with explicit pitcher A.
            _make_play(
                order=2, inning=1, half="bottom",
                outcome="Strikeout",
                at_plate_details=[
                    {"template": "Strike 1 looking"},
                    {"template": "Strike 2 swinging"},
                    {"template": "Strike 3 swinging"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
                ],
            ),
            # Play 3: Single, no pitcher reference (inherits from state).
            _make_play(
                order=3, inning=1, half="bottom",
                outcome="Single",
                at_plate_details=[{"template": "In play"}],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles to center field"},
                ],
            ),
        ]
        result = _parse(plays)
        # All 4 plays should have pitcher A.
        for i, play in enumerate(result):
            assert play.pitcher_id == _PITCHER_UUID, f"Play {i} should have pitcher_id set"

    def test_backfill_does_not_override_mid_pa_attribution(self):
        """Post-parse backfill must not overwrite pitcher_id set by mid-PA logic.

        Scenario: pitcher A is established via play 0 (explicit final_details).
        Play 1 has a mid-PA pitching change (A -> B) -- mid-PA logic credits
        play 1 to pitcher A (the pitcher who threw pitch 1).  Play 2 has
        explicit pitcher B.  The backfill should NOT overwrite play 1's
        pitcher_id because it is already non-None (set by mid-PA logic).
        """
        plays = [
            # Play 0: establishes pitcher A via final_details.
            _make_play(
                order=0, inning=1, half="bottom",
                outcome="Single",
                at_plate_details=[{"template": "In play"}],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles to left field, ${{{_PITCHER_UUID}}} pitching"},
                ],
            ),
            # Play 1: mid-PA pitching change A -> B.
            # pitcher_at_first_pitch = A, then sub brings in B.
            # mid-PA logic credits play to A.
            _make_play(
                order=1, inning=1, half="bottom",
                outcome="Strikeout",
                at_plate_details=[
                    {"template": "Strike 1 looking"},
                    {"template": f"Lineup changed: ${{{_PITCHER2_UUID}}} in at pitcher for ${{{_PITCHER_UUID}}}"},
                    {"template": "Strike 2 swinging"},
                    {"template": "Strike 3 swinging"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER2_UUID}}} pitching"},
                ],
            ),
            # Play 2: explicit pitcher B in final_details.
            _make_play(
                order=2, inning=1, half="bottom",
                outcome="Single",
                at_plate_details=[{"template": "In play"}],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} singles to center, ${{{_PITCHER2_UUID}}} pitching"},
                ],
            ),
        ]
        result = _parse(plays)
        # Play 0: pitcher A from explicit final_details.
        assert result[0].pitcher_id == _PITCHER_UUID
        # Play 1: mid-PA logic credits original pitcher A (not overwritten by backfill).
        assert result[1].pitcher_id == _PITCHER_UUID
        # Play 2: explicit pitcher B.
        assert result[2].pitcher_id == _PITCHER2_UUID


# ---------------------------------------------------------------------------
# Tests: Non-PA outcome skipping
# ---------------------------------------------------------------------------


class TestNonPAOutcomeSkip:
    """Non-PA outcomes (Runner Out, Inning Ended) are silently skipped."""

    def test_runner_out_skipped(self):
        """Runner Out plays are skipped without a batter-extraction warning."""
        plays = [
            _make_play(
                order=0, outcome="Runner Out",
                at_plate_details=[
                    {"template": f"${{{_RUNNER_UUID}}} out at second"},
                ],
                final_details=[
                    {"template": f"${{{_RUNNER_UUID}}} out at second, shortstop to second baseman"},
                ],
            ),
        ]
        result = _parse(plays)
        assert len(result) == 0

    def test_inning_ended_skipped(self):
        """Inning Ended plays are skipped without a batter-extraction warning."""
        plays = [
            _make_play(
                order=0, outcome="Inning Ended",
                at_plate_details=[],
                final_details=[
                    {"template": "Inning ended"},
                ],
            ),
        ]
        result = _parse(plays)
        assert len(result) == 0

    def test_non_pa_skip_does_not_affect_adjacent_plays(self):
        """Plays adjacent to skipped non-PA outcomes parse correctly."""
        plays = [
            _make_play(
                order=0, inning=1, half="top",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "In play"},
                ],
            ),
            _make_play(
                order=1, inning=1, half="top", outcome="Runner Out",
                at_plate_details=[
                    {"template": f"${{{_RUNNER_UUID}}} out at third"},
                ],
                final_details=[
                    {"template": f"${{{_RUNNER_UUID}}} out at third, catcher to third baseman"},
                ],
            ),
            _make_play(
                order=2, inning=1, half="top",
                at_plate_details=[{"template": "In play"}],
            ),
        ]
        result = _parse(plays)
        # Runner Out is skipped; plays 0 and 2 are parsed.
        assert len(result) == 2
        assert result[0].play_order == 0
        assert result[1].play_order == 2


# ---------------------------------------------------------------------------
# Tests: Final-score recovery -- the two rejected seeding rules
# ---------------------------------------------------------------------------


class TestFinalScoreRejectedRules:
    """Guard the seeding rule against the two rules that were tried and rejected.

    Both cases come from real payloads.  Each test is paired with a mutation
    that re-demonstrates it: seeding from ``plays[-1]`` fails the first,
    seeding from ``max()`` fails the second.
    """

    def test_inert_phantom_does_not_zero_final_score(self):
        """A trailing inert phantom carrying 0/0 must not zero the final score.

        Every observed payload ends with a phantom play that has empty
        ``final_details``, ``did_score_change: false``, and -- critically --
        ``home_score``/``away_score`` of INTEGER ZERO, not null.  A "last raw
        play" or "last non-NULL score" rule reads that phantom and sets every
        game's final to 0-0.
        """
        plays = [
            _make_play(
                order=0, inning=7, half="bottom",
                home_score=5, away_score=3, did_score_change=True,
            ),
            # The trailing inert phantom: empty final_details AND no score
            # change, carrying integer 0/0.
            _make_play(
                order=1, inning=8, half="top",
                at_plate_details=[], final_details=[],
                home_score=0, away_score=0, did_score_change=False,
            ),
        ]
        result = _parse_full(plays)

        assert result.final_home_score == 5
        assert result.final_away_score == 3

    def test_non_monotone_payload_does_not_overshoot_final_score(self):
        """A rescinded run leaves a non-monotone score; ``max()`` overshoots it.

        When a scorekeeper enters a run and then corrects it away, the running
        score in the payload goes DOWN.  ``max()`` over all raw plays latches
        onto the retracted run and reports 6-6 where the official final is 6-5.
        """
        plays = [
            # The scorekeeper's entered-then-rescinded run: away reads 6 here.
            _make_play(
                order=0, inning=6, half="top",
                home_score=6, away_score=6, did_score_change=True,
            ),
            # The correction, and the game's last real play: away is back to 5.
            _make_play(
                order=1, inning=6, half="bottom",
                home_score=6, away_score=5, did_score_change=False,
            ),
        ]
        result = _parse_full(plays)

        assert result.final_home_score == 6
        assert result.final_away_score == 5


# ---------------------------------------------------------------------------
# Tests: Final-score recovery across every parser skip path
# ---------------------------------------------------------------------------


class TestFinalScoreAcrossSkipPaths:
    """The game-ending run is recovered whichever skip path drops its play.

    Walk-offs end on an abandoned plate appearance; run-rule endings reach the
    parser through the ``Runner Out`` / ``Inning Ended`` path instead.  A fix
    keyed to one path leaves the other broken and still looks correct, so each
    path is asserted separately: the final play must produce NO extra ``plays``
    row AND still contribute the correct final score.
    """

    # A completed play preceding the game-ending one, at 7-7.
    @staticmethod
    def _opening_play() -> dict:
        return _make_play(
            order=0, inning=7, half="bottom",
            home_score=7, away_score=7, did_score_change=False,
        )

    def test_final_abandoned_pa_recovers_walk_off_run(self):
        """Path (a): the walk-off run lands on an abandoned PA.

        The plate appearance is unresolved -- empty ``final_details`` -- so the
        parser skips it, but ``did_score_change`` is true, which is what marks
        it as the run-carrier rather than the trailing phantom.  Emptiness
        alone cannot tell the two apart.
        """
        plays = [
            self._opening_play(),
            _make_play(
                order=1, inning=7, half="bottom",
                at_plate_details=[{"template": "In play"}],
                final_details=[],
                home_score=8, away_score=7, did_score_change=True,
            ),
        ]
        result = _parse_full(plays)

        assert len(result.plays) == 1
        assert result.final_home_score == 8
        assert result.final_away_score == 7

    def test_final_runner_out_recovers_run_rule_ending(self):
        """Path (b): a run-rule ending finishing on a ``Runner Out`` marker."""
        plays = [
            self._opening_play(),
            _make_play(
                order=1, inning=7, half="bottom", outcome="Runner Out",
                at_plate_details=[
                    {"template": f"${{{_RUNNER_UUID}}} out at home"},
                ],
                final_details=[
                    {"template": f"${{{_RUNNER_UUID}}} out at home, left fielder to catcher"},
                ],
                home_score=8, away_score=7, did_score_change=True,
                outs=3, did_outs_change=True,
            ),
        ]
        result = _parse_full(plays)

        assert len(result.plays) == 1
        assert result.final_home_score == 8
        assert result.final_away_score == 7

    def test_final_inning_ended_recovers_run_rule_ending(self):
        """Path (b): the same ending arriving as an ``Inning Ended`` marker."""
        plays = [
            self._opening_play(),
            _make_play(
                order=1, inning=7, half="bottom", outcome="Inning Ended",
                at_plate_details=[],
                final_details=[{"template": "Inning ended"}],
                home_score=8, away_score=7, did_score_change=True,
                outs=3, did_outs_change=True,
            ),
        ]
        result = _parse_full(plays)

        assert len(result.plays) == 1
        assert result.final_home_score == 8
        assert result.final_away_score == 7

    def test_final_unextractable_batter_recovers_run(self):
        """Path (c): ``final_details`` carrying no batter UUID.

        The parser cannot identify the batter, so it skips the play -- but the
        run it carries still belongs in the final score.
        """
        plays = [
            self._opening_play(),
            _make_play(
                order=1, inning=7, half="bottom",
                at_plate_details=[{"template": "In play"}],
                final_details=[{"template": "Run scored on a wild pitch"}],
                home_score=8, away_score=7, did_score_change=True,
            ),
        ]
        result = _parse_full(plays)

        assert len(result.plays) == 1
        assert result.final_home_score == 8
        assert result.final_away_score == 7

    def test_run_carrier_recovered_through_trailing_phantom(self):
        """The real shape: run-carrier, then the inert phantom after it.

        Both have empty ``final_details``.  Only ``did_score_change``
        separates them, and the backwards walk must step past the phantom to
        reach the carrier.
        """
        plays = [
            self._opening_play(),
            # The walk-off run, on an abandoned PA.
            _make_play(
                order=1, inning=7, half="bottom",
                at_plate_details=[{"template": "In play"}],
                final_details=[],
                home_score=8, away_score=7, did_score_change=True,
            ),
            # The trailing phantom, carrying integer 0/0.
            _make_play(
                order=2, inning=8, half="top",
                at_plate_details=[], final_details=[],
                home_score=0, away_score=0, did_score_change=False,
            ),
        ]
        result = _parse_full(plays)

        assert len(result.plays) == 1
        assert result.final_home_score == 8
        assert result.final_away_score == 7


# ---------------------------------------------------------------------------
# Tests: Final-score derivation returns None rather than a fabricated 0
# ---------------------------------------------------------------------------


class TestFinalScoreAbsence:
    """``None`` means "not derivable" and must never collapse into a real 0."""

    def test_empty_payload_yields_no_final_score(self):
        result = _parse_full([])

        assert result.plays == []
        assert result.final_home_score is None
        assert result.final_away_score is None

    def test_all_inert_payload_yields_no_final_score(self):
        """Every play inert: nothing to parse and nothing to seed from."""
        plays = [
            _make_play(
                order=0, at_plate_details=[], final_details=[],
                home_score=0, away_score=0, did_score_change=False,
            ),
            _make_play(
                order=1, at_plate_details=[], final_details=[],
                home_score=0, away_score=0, did_score_change=False,
            ),
        ]
        result = _parse_full(plays)

        assert result.plays == []
        assert result.final_home_score is None
        assert result.final_away_score is None

    def test_final_play_missing_score_keys_does_not_write_zero(self):
        """Absent score keys yield None, NOT the parser's per-play 0 default.

        ``ParsedPlay.home_score`` defaults an absent key to 0 because the
        column is NOT NULL.  The derived final must not inherit that default:
        a stored 0 would be indistinguishable from a real 0-0 game.
        """
        last = _make_play(order=1, inning=7, half="bottom")
        del last["home_score"]
        del last["away_score"]
        earlier = _make_play(order=0, home_score=4, away_score=2)

        result = _parse_full([earlier, last])

        # The walk stops at the terminal non-inert play and reports what it
        # found there -- it does not keep walking back to the earlier 4-2.
        assert result.final_home_score is None
        assert result.final_away_score is None


# ---------------------------------------------------------------------------
# Tests: All 24 outcome types handled (AC-12)
# ---------------------------------------------------------------------------


class TestOutcomeVocabulary:
    """Verify all 24 confirmed outcome types are handled without error."""

    _ALL_OUTCOMES = [
        "Walk", "Single", "Double", "Triple",
        "Home Run", "Strikeout", "Fly Out", "Ground Out",
        "Pop Out", "Line Out", "Hit By Pitch", "Error",
        "Fielder's Choice", "Runner Out", "Sacrifice Bunt", "Sacrifice Fly",
        "Dropped 3rd Strike", "Infield Fly", "Intentional Walk", "Double Play",
        "Batter Out", "Inning Ended", "FC Double Play", "Catcher's Interference",
    ]

    # Non-PA outcomes are deliberately skipped by the parser.
    _NON_PA_OUTCOMES = {"Runner Out", "Inning Ended"}

    @pytest.mark.parametrize("outcome", _ALL_OUTCOMES)
    def test_outcome_handled_without_error(self, outcome):
        plays = [_make_play(outcome=outcome)]
        result = _parse(plays)
        if outcome in self._NON_PA_OUTCOMES:
            assert len(result) == 0
        else:
            assert len(result) == 1
            assert result[0].outcome == outcome

    def test_unrecognized_outcome_stored_as_is(self):
        """Future-proofing: unknown outcome types are stored, not rejected."""
        plays = [_make_play(outcome="Unknown Future Outcome")]
        result = _parse(plays)
        assert result[0].outcome == "Unknown Future Outcome"


# ---------------------------------------------------------------------------
# Tests: Events list structure (AC-2, AC-3)
# ---------------------------------------------------------------------------


class TestEventsStructure:
    """Verify ParsedPlay events list is correctly populated."""

    def test_events_list_populated(self):
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": "Strike 1 looking"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert len(result[0].events) == 3

    def test_event_order_sequential(self):
        plays = [_make_play(at_plate_details=[
            {"template": "Ball 1"},
            {"template": "Strike 1 looking"},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        orders = [e.event_order for e in result[0].events]
        assert orders == [0, 1, 2]

    def test_event_raw_template_preserved(self):
        template = "Strike 1 looking"
        plays = [_make_play(at_plate_details=[
            {"template": template},
            {"template": "In play"},
        ])]
        result = _parse(plays)
        assert result[0].events[0].raw_template == template


# ---------------------------------------------------------------------------
# Tests: Multi-game / integration-like
# ---------------------------------------------------------------------------


class TestMultiPlayGame:
    """Integration-like tests with multi-play game scenarios."""

    def test_realistic_half_inning(self):
        """Parse a realistic 3-out half inning."""
        plays = [
            _make_play(
                order=0, inning=1, half="top",
                outcome="Walk",
                at_plate_details=[
                    {"template": f"Lineup changed: ${{{_PITCHER_UUID}}} in at pitcher"},
                    {"template": "Ball 1"},
                    {"template": "Ball 2"},
                    {"template": "Ball 3"},
                    {"template": "Ball 4"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} walks, ${{{_PITCHER_UUID}}} pitching"},
                ],
            ),
            _make_play(
                order=1, inning=1, half="top",
                outcome="Double",
                at_plate_details=[
                    {"template": "Strike 1 looking"},
                    {"template": "In play"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} doubles on a line drive to left fielder ${{{_FIELDER_UUID}}}"},
                ],
                did_score_change=True,
                home_score=0, away_score=1,
            ),
            _make_play(
                order=2, inning=1, half="top",
                outcome="Strikeout",
                at_plate_details=[
                    {"template": "Strike 1 swinging"},
                    {"template": "Ball 1"},
                    {"template": "Ball 2"},
                    {"template": "Foul"},
                    {"template": "Strike 2 looking"},
                    {"template": "Foul"},
                    {"template": "Strike 3 swinging"},
                ],
                final_details=[
                    {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
                ],
                outs=1, did_outs_change=True,
            ),
        ]

        result = _parse(plays)
        assert len(result) == 3

        # Play 0: Walk = QAB.
        assert result[0].outcome == "Walk"
        assert result[0].is_qab == 1
        assert result[0].is_first_pitch_strike == 0  # Ball 1
        assert result[0].pitch_count == 4
        assert result[0].pitcher_id == _PITCHER_UUID

        # Play 1: Double = QAB (XBH). FPS = 1 (Strike 1 looking).
        assert result[1].outcome == "Double"
        assert result[1].is_qab == 1
        assert result[1].is_first_pitch_strike == 1
        assert result[1].pitch_count == 2
        assert result[1].did_score_change == 1

        # Play 2: Strikeout, 7 pitches = QAB (6+). Also 2S+3.
        assert result[2].outcome == "Strikeout"
        assert result[2].is_qab == 1
        assert result[2].pitch_count == 7
        assert result[2].outs_after == 1

    def test_game_with_abandoned_pa_excluded_from_count(self):
        """Mixed game: valid plays + abandoned PA at end."""
        plays = [
            _make_play(order=0, outcome="Single"),
            _make_play(order=1, outcome="Fly Out"),
            _make_play(order=2, final_details=[], at_plate_details=[]),
        ]
        result = _parse(plays)
        assert len(result) == 2

    def test_foul_on_1_strike_advances_count_for_2s_plus_3(self):
        """Foul before 2 strikes advances the strike count to 2, then count starts."""
        plays = [_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Strike 1 swinging"},
                {"template": "Foul"},       # This is strike 2.
                {"template": "Ball 1"},     # After 2S: pitch 1.
                {"template": "Foul"},       # After 2S: pitch 2 (does NOT advance).
                {"template": "Strike 3 swinging"},  # After 2S: pitch 3.
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out swinging, ${{{_PITCHER_UUID}}} pitching"},
            ],
        )]
        result = _parse(plays)
        # After strike 1, foul (now 2 strikes), then 3 pitches after 2S.
        assert result[0].is_qab == 1


# ---------------------------------------------------------------------------
# Tests: ParsedPlay and ParsedEvent dataclass fields (AC-2, AC-3)
# ---------------------------------------------------------------------------


class TestDataclassFields:
    """Verify that ParsedPlay and ParsedEvent have all required fields."""

    def test_parsed_play_has_all_fields(self):
        plays = [_make_play()]
        result = _parse(plays)
        play = result[0]
        assert hasattr(play, "game_id")
        assert hasattr(play, "play_order")
        assert hasattr(play, "inning")
        assert hasattr(play, "half")
        assert hasattr(play, "season_id")
        assert hasattr(play, "batting_team_id")
        assert hasattr(play, "batter_id")
        assert hasattr(play, "pitcher_id")
        assert hasattr(play, "outcome")
        assert hasattr(play, "pitch_count")
        assert hasattr(play, "is_first_pitch_strike")
        assert hasattr(play, "is_qab")
        assert hasattr(play, "home_score")
        assert hasattr(play, "away_score")
        assert hasattr(play, "did_score_change")
        assert hasattr(play, "outs_after")
        assert hasattr(play, "did_outs_change")
        assert hasattr(play, "events")

    def test_parsed_event_has_all_fields(self):
        plays = [_make_play()]
        result = _parse(plays)
        event = result[0].events[0]
        assert hasattr(event, "event_order")
        assert hasattr(event, "event_type")
        assert hasattr(event, "pitch_result")
        assert hasattr(event, "is_first_pitch")
        assert hasattr(event, "raw_template")


# ---------------------------------------------------------------------------
# Tests: Real fixture -- game-plays-fresh.json (AC-11)
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "game-plays-fresh.json"

# Constants for the fixture file's redacted UUIDs.
_FIXTURE_PLAYER_UUID = "00000000-0000-0000-0000-000000000001"
_FIXTURE_GAME_ID = "fixture-game-001"
_FIXTURE_SEASON_ID = "2026-fixture"
_FIXTURE_HOME_TEAM_ID = 10
_FIXTURE_AWAY_TEAM_ID = 20


def _load_fixture() -> dict:
    """Load the real fixture JSON file."""
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


class TestRealFixture:
    """Validate parsing against the real game-plays-fresh.json fixture (AC-11).

    The fixture contains the first 3 plays of a 58-play game:
      - Play 0 (order=0): Walk with pitcher substitution event (4 balls).
      - Play 1 (order=1): Walk with pickoff attempt and baserunner advance
        (Strike, Pickoff, advance, Ball, Foul, Ball, Ball, Foul, Ball = 7 pitches).
      - Play 2 (order=2): Fly Out (Ball, In play = 2 pitches).
    """

    @pytest.fixture()
    def parsed_plays(self) -> list[ParsedPlay]:
        """Parse the real fixture once for all tests in this class."""
        raw = _load_fixture()
        return PlaysParser.parse_game(
            raw,
            game_id=_FIXTURE_GAME_ID,
            season_id=_FIXTURE_SEASON_ID,
            home_team_id=_FIXTURE_HOME_TEAM_ID,
            away_team_id=_FIXTURE_AWAY_TEAM_ID,
        ).plays

    def test_correct_play_count_excludes_abandoned(self, parsed_plays: list[ParsedPlay]):
        """All 3 plays in the fixture have final_details; none should be skipped."""
        assert len(parsed_plays) == 3

    def test_game_id_populated_on_all_plays(self, parsed_plays: list[ParsedPlay]):
        """game_id should be set from the parameter on every parsed play."""
        for play in parsed_plays:
            assert play.game_id == _FIXTURE_GAME_ID

    def test_play_0_pitch_count(self, parsed_plays: list[ParsedPlay]):
        """Play 0: Walk with 4 balls (substitution event is not a pitch)."""
        assert parsed_plays[0].pitch_count == 4

    def test_play_1_pitch_count(self, parsed_plays: list[ParsedPlay]):
        """Play 1: Walk with 7 pitch events (pickoff + advance are not pitches).

        Pitch sequence: Strike 1 looking, Ball 1, Foul, Ball 2, Ball 3, Foul, Ball 4.
        """
        assert parsed_plays[1].pitch_count == 7

    def test_play_2_pitch_count(self, parsed_plays: list[ParsedPlay]):
        """Play 2: Fly Out with Ball 1, In play = 2 pitches."""
        assert parsed_plays[2].pitch_count == 2

    def test_play_0_fps_is_zero(self, parsed_plays: list[ParsedPlay]):
        """Play 0: First pitch event is Ball 1 (after substitution). FPS = 0."""
        assert parsed_plays[0].is_first_pitch_strike == 0

    def test_play_1_fps_is_one(self, parsed_plays: list[ParsedPlay]):
        """Play 1: First pitch event is Strike 1 looking. FPS = 1."""
        assert parsed_plays[1].is_first_pitch_strike == 1

    def test_play_2_fps_is_zero(self, parsed_plays: list[ParsedPlay]):
        """Play 2: First pitch event is Ball 1. FPS = 0."""
        assert parsed_plays[2].is_first_pitch_strike == 0

    def test_play_0_qab_walk(self, parsed_plays: list[ParsedPlay]):
        """Play 0: Walk outcome triggers QAB."""
        assert parsed_plays[0].outcome == "Walk"
        assert parsed_plays[0].is_qab == 1

    def test_play_1_qab_walk_and_6_plus_pitches(self, parsed_plays: list[ParsedPlay]):
        """Play 1: Walk (QAB) AND 7 pitches >= 6 (QAB). Either condition suffices."""
        assert parsed_plays[1].outcome == "Walk"
        assert parsed_plays[1].is_qab == 1
        assert parsed_plays[1].pitch_count >= 6

    def test_play_2_not_qab(self, parsed_plays: list[ParsedPlay]):
        """Play 2: Fly Out with 2 pitches. No QAB conditions met."""
        assert parsed_plays[2].outcome == "Fly Out"
        assert parsed_plays[2].is_qab == 0

    def test_play_0_has_substitution_event(self, parsed_plays: list[ParsedPlay]):
        """Play 0 contains a 'Lineup changed' substitution event."""
        event_types = [e.event_type for e in parsed_plays[0].events]
        assert "substitution" in event_types

    def test_play_1_has_baserunner_events(self, parsed_plays: list[ParsedPlay]):
        """Play 1 contains pickoff + advance baserunner events."""
        event_types = [e.event_type for e in parsed_plays[1].events]
        assert event_types.count("baserunner") == 2

    def test_all_plays_are_top_of_inning_1(self, parsed_plays: list[ParsedPlay]):
        """All 3 fixture plays are top of inning 1."""
        for play in parsed_plays:
            assert play.inning == 1
            assert play.half == "top"

    def test_batting_team_is_away_for_top(self, parsed_plays: list[ParsedPlay]):
        """Top of inning: away team bats."""
        for play in parsed_plays:
            assert play.batting_team_id == _FIXTURE_AWAY_TEAM_ID

    def test_pitcher_identified_from_explicit_reference(self, parsed_plays: list[ParsedPlay]):
        """Plays 0 and 1 have explicit '${uuid} pitching' in final_details."""
        assert parsed_plays[0].pitcher_id == _FIXTURE_PLAYER_UUID
        assert parsed_plays[1].pitcher_id == _FIXTURE_PLAYER_UUID

    def test_pitcher_tracked_across_play_without_explicit_ref(self, parsed_plays: list[ParsedPlay]):
        """Play 2 has no explicit pitcher ref; should use tracked state from play 0's substitution."""
        assert parsed_plays[2].pitcher_id == _FIXTURE_PLAYER_UUID

    def test_batter_extracted_for_all_plays(self, parsed_plays: list[ParsedPlay]):
        """All plays have a batter_id extracted from final_details."""
        for play in parsed_plays:
            assert play.batter_id == _FIXTURE_PLAYER_UUID

    def test_score_fields_from_fixture(self, parsed_plays: list[ParsedPlay]):
        """Verify score fields match the fixture data."""
        for play in parsed_plays:
            assert play.home_score == 0
            assert play.away_score == 0
        # Plays 0 and 1: no score change.
        assert parsed_plays[0].did_score_change == 0
        assert parsed_plays[1].did_score_change == 0
        # Play 2: no score change.
        assert parsed_plays[2].did_score_change == 0

    def test_outs_from_fixture(self, parsed_plays: list[ParsedPlay]):
        """Play 2 is a fly out; outs_after=1 and did_outs_change=1."""
        assert parsed_plays[0].outs_after == 0
        assert parsed_plays[0].did_outs_change == 0
        assert parsed_plays[2].outs_after == 1
        assert parsed_plays[2].did_outs_change == 1


# ---------------------------------------------------------------------------
# Tests: Pitch annotation grammar (E-245 AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------


class TestPitchAnnotationGrammar:
    """Annotated pitch templates classify as pitches and capture type/speed."""

    def test_type_only_annotation_classifies_as_pitch(self):
        """'(Curveball)' -- type only: classified as pitch, type captured."""
        plays = _parse([_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Strike 1 looking (Curveball)"},
                {"template": "Strike 2 looking (Slider)"},
                {"template": "Strike 3 swinging (Changeup)"},
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out swinging, "
                             f"${{{_PITCHER_UUID}}} pitching"},
            ],
        )])
        play = plays[0]
        assert play.pitch_count == 3
        for ev in play.events:
            assert ev.event_type == "pitch"
            assert ev.pitch_speed_mph is None
        types = [ev.pitch_type for ev in play.events]
        assert types == ["Curveball", "Slider", "Changeup"]

    def test_speed_and_type_annotation(self):
        """'(101 MPH Curveball)' -- speed + type both captured."""
        plays = _parse([_make_play(
            at_plate_details=[
                {"template": "Strike 1 looking (101 MPH Curveball)"},
                {"template": "In play (75 MPH Fastball)"},
            ],
        )])
        events = plays[0].events
        assert events[0].event_type == "pitch"
        assert events[0].pitch_result == "strike_looking"
        assert events[0].pitch_speed_mph == 101
        assert events[0].pitch_type == "Curveball"
        assert events[1].pitch_result == "in_play"
        assert events[1].pitch_speed_mph == 75
        assert events[1].pitch_type == "Fastball"

    def test_speed_only_annotation(self):
        """'(75 MPH)' -- speed only: speed captured, type None."""
        plays = _parse([_make_play(
            at_plate_details=[
                {"template": "Ball 1 (75 MPH)"},
                {"template": "Foul (88 MPH)"},
            ],
        )])
        events = plays[0].events
        assert events[0].event_type == "pitch"
        assert events[0].pitch_result == "ball"
        assert events[0].pitch_speed_mph == 75
        assert events[0].pitch_type is None
        assert events[1].pitch_result == "foul"
        assert events[1].pitch_speed_mph == 88
        assert events[1].pitch_type is None

    def test_bare_pitch_leaves_type_and_speed_null(self):
        """A bare pitch leaves both annotation columns NULL (AC-2)."""
        plays = _parse([_make_play(
            at_plate_details=[
                {"template": "Ball 1"},
                {"template": "In play"},
            ],
        )])
        for ev in plays[0].events:
            assert ev.event_type == "pitch"
            assert ev.pitch_type is None
            assert ev.pitch_speed_mph is None

    def test_all_forms_interleaved_in_one_game(self):
        """Bare + all three annotation forms interleave within one PA (AC-1)."""
        plays = _parse([_make_play(
            outcome="Strikeout",
            at_plate_details=[
                {"template": "Ball 1"},                              # bare
                {"template": "Strike 1 looking (Curveball)"},        # type only
                {"template": "Foul (75 MPH)"},                       # speed only
                {"template": "Strike 3 swinging (88 MPH Slider)"},   # speed+type
            ],
            final_details=[
                {"template": f"${{{_BATTER_UUID}}} strikes out swinging, "
                             f"${{{_PITCHER_UUID}}} pitching"},
            ],
        )])
        play = plays[0]
        assert play.pitch_count == 4
        assert all(ev.event_type == "pitch" for ev in play.events)
        # First pitch is the bare Ball 1 -- FPS = 0.
        assert play.events[0].is_first_pitch is True
        assert play.is_first_pitch_strike == 0
        # Per-event annotation capture.
        assert (play.events[1].pitch_type, play.events[1].pitch_speed_mph) == ("Curveball", None)
        assert (play.events[2].pitch_type, play.events[2].pitch_speed_mph) == (None, 75)
        assert (play.events[3].pitch_type, play.events[3].pitch_speed_mph) == ("Slider", 88)

    def test_annotated_first_pitch_strike_counts_for_fps(self):
        """An annotated strike on pitch 1 yields FPS = 1 (regression guard)."""
        plays = _parse([_make_play(
            at_plate_details=[
                {"template": "Strike 1 looking (Fastball)"},
                {"template": "In play"},
            ],
        )])
        play = plays[0]
        assert play.events[0].is_first_pitch is True
        assert play.is_first_pitch_strike == 1

    def test_unclear_type_token_captured(self):
        """'(Unclear)' renders as a literal type token and is captured as-is."""
        plays = _parse([_make_play(
            at_plate_details=[
                {"template": "Ball 1 (Unclear)"},
                {"template": "In play"},
            ],
        )])
        events = plays[0].events
        assert events[0].event_type == "pitch"
        assert events[0].pitch_type == "Unclear"
        assert events[0].pitch_speed_mph is None

    def test_non_pitch_with_parens_not_misclassified(self):
        """A '(Play Edit)' substitution is NOT stripped into a pitch (AC-3)."""
        # "(Play Edit) ${a} in for ${b}" -- leading paren, substitution.
        sub_template = (
            f"(Play Edit) ${{{_PITCHER2_UUID}}} in for ${{{_PITCHER_UUID}}}"
        )
        event_type, pitch_result, ptype, speed = PlaysParser._classify_template(
            sub_template, game_id=_GAME_ID, play_order=0,
        )
        assert event_type == "substitution"
        assert pitch_result is None
        assert ptype is None
        assert speed is None

    def test_baserunner_with_trailing_parens_not_a_pitch(self):
        """A non-pitch template ending in '(...)' is not stripped to a pitch (AC-3).

        Synthetic guard: the post-strip base ('Runner shenanigans') is not a
        known pitch template, so the strip must NOT fire -- it falls through to
        the normal (here: 'other') classification rather than becoming a pitch.
        """
        event_type, pitch_result, ptype, speed = PlaysParser._classify_template(
            "Runner shenanigans (Fastball)", game_id=_GAME_ID, play_order=0,
        )
        assert event_type != "pitch"
        assert pitch_result is None
        assert ptype is None
        assert speed is None
