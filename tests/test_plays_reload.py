"""Tests for src/gamechanger/loaders/plays_reload.py (E-245-02).

The reload re-derives already-loaded games IN PLACE from the stored
``play_events.raw_template`` -- recovering stranded annotated pitches,
populating ``pitch_type`` / ``pitch_speed_mph``, and recomputing the parent
``plays`` flags -- with no API re-fetch and no DELETE.

Covers:
- AC-4: dropped pitches reclassified, type/speed populated, pitch_count
  recomputed; player_game_* rows left untouched.
- AC-5: is_first_pitch / is_first_pitch_strike RE-DERIVED (not trusted).
- AC-6: is_qab OR-merge incl. HHB-only-QAB survival.
- AC-7: idempotency (run twice -> no change on the second run).
- AC-8: perspective_team_id preserved.
- AC-9: batting_team_id re-derived from the FRESH games-row home/away.
- Scope isolation: reload of one (game, perspective) leaves others untouched.
- Batch driver summary + per-game error isolation.

All tests use an on-disk SQLite database with all migrations applied. No real
network calls (the reload reads only from the DB).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.plays_reload import (
    reload_all_games,
    reload_game_plays,
)

_SEASON_ID = "2026-spring-hs"
_GAME_ID = "reload-game-001"
_GAME_ID_2 = "reload-game-002"
_BATTER = "ba11e100-0001-0001-0001-000000000001"
_PITCHER = "01c4e100-0001-0001-0001-000000000001"


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and seed seasons/teams/players/games."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, ?, ?)",
        (_SEASON_ID, "Spring 2026 HS", "spring-hs", 2026),
    )
    # Two distinct teams (home != away).
    conn.execute(
        "INSERT INTO teams (id, name, membership_type, is_active) "
        "VALUES (1, 'Home Team', 'member', 1)",
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type, is_active) "
        "VALUES (2, 'Away Team', 'tracked', 1)",
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (_BATTER, "Bat", "Ter"),
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        (_PITCHER, "Pit", "Cher"),
    )
    for gid in (_GAME_ID, _GAME_ID_2):
        conn.execute(
            "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
            "away_team_id, status) VALUES (?, ?, '2026-04-10', 1, 2, 'completed')",
            (gid, _SEASON_ID),
        )
    conn.commit()
    return conn


def _insert_play(
    db: sqlite3.Connection,
    *,
    game_id: str = _GAME_ID,
    perspective_team_id: int = 1,
    batting_team_id: int = 2,
    half: str = "top",
    play_order: int = 0,
    outcome: str = "Strikeout",
    pitch_count: int = 0,
    is_first_pitch_strike: int = 0,
    is_qab: int = 0,
) -> int:
    """Insert a parent plays row, returning its id."""
    cur = db.execute(
        """
        INSERT INTO plays (
            game_id, play_order, inning, half, season_id,
            batting_team_id, perspective_team_id, batter_id, pitcher_id,
            outcome, pitch_count, is_first_pitch_strike, is_qab
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id, play_order, half, _SEASON_ID,
            batting_team_id, perspective_team_id, _BATTER, _PITCHER,
            outcome, pitch_count, is_first_pitch_strike, is_qab,
        ),
    )
    db.commit()
    return cur.lastrowid


def _insert_event(
    db: sqlite3.Connection,
    play_id: int,
    event_order: int,
    event_type: str,
    raw_template: str,
    *,
    pitch_result: str | None = None,
    is_first_pitch: int = 0,
) -> None:
    """Insert a play_events row simulating the pre-reload (buggy) state."""
    db.execute(
        """
        INSERT INTO play_events (
            play_id, event_order, event_type, pitch_result,
            is_first_pitch, raw_template
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (play_id, event_order, event_type, pitch_result, is_first_pitch, raw_template),
    )
    db.commit()


def _events(db: sqlite3.Connection, play_id: int) -> list[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT * FROM play_events WHERE play_id = ? ORDER BY event_order",
        (play_id,),
    ).fetchall()
    db.row_factory = None
    return rows


def _play(db: sqlite3.Connection, play_id: int) -> sqlite3.Row:
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM plays WHERE id = ?", (play_id,)).fetchone()
    db.row_factory = None
    return row


# ---------------------------------------------------------------------------
# AC-4: reclassify dropped pitches, populate type/speed, recompute pitch_count
# ---------------------------------------------------------------------------


class TestRecoverDroppedPitches:
    def test_dropped_annotated_pitches_reclassified(self, db):
        """A strikeout whose 3 annotated pitches were stranded as 'other'."""
        play_id = _insert_play(db, outcome="Strikeout")
        # Pre-reload buggy state: annotated pitches stored as 'other'.
        _insert_event(db, play_id, 0, "other", "Strike 1 looking (Curveball)")
        _insert_event(db, play_id, 1, "other", "Foul (75 MPH)")
        _insert_event(db, play_id, 2, "other", "Strike 3 swinging (88 MPH Slider)")

        result = reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        assert result.found is True
        assert result.plays_updated == 1
        assert result.events_recovered == 3

        evs = _events(db, play_id)
        assert [e["event_type"] for e in evs] == ["pitch", "pitch", "pitch"]
        assert [e["pitch_result"] for e in evs] == [
            "strike_looking", "foul", "strike_swinging",
        ]
        assert [e["pitch_type"] for e in evs] == ["Curveball", None, "Slider"]
        assert [e["pitch_speed_mph"] for e in evs] == [None, 75, 88]

        play = _play(db, play_id)
        assert play["pitch_count"] == 3

    def test_player_game_rows_left_untouched(self, db):
        """Boxscore-derived player_game_batting rows are not rewritten (AC-4)."""
        db.execute(
            """
            INSERT INTO player_game_batting (
                game_id, player_id, team_id, perspective_team_id,
                ab, r, h, rbi, bb, so
            ) VALUES (?, ?, 2, 1, 4, 1, 2, 1, 0, 1)
            """,
            (_GAME_ID, _BATTER),
        )
        db.commit()
        play_id = _insert_play(db)
        _insert_event(db, play_id, 0, "other", "In play (Fastball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        row = db.execute(
            "SELECT ab, h, rbi FROM player_game_batting WHERE game_id = ?",
            (_GAME_ID,),
        ).fetchone()
        assert row == (4, 2, 1)

    def test_no_refetch_pure_db(self, db):
        """Reload takes only a connection -- no network/file dependency (AC-4)."""
        play_id = _insert_play(db)
        _insert_event(db, play_id, 0, "other", "Ball 1 (Fastball)")
        # If this required an API/file it would raise; it must not.
        result = reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()
        assert result.found is True


# ---------------------------------------------------------------------------
# AC-5: is_first_pitch / is_first_pitch_strike re-derived, not trusted
# ---------------------------------------------------------------------------


class TestFirstPitchRederivation:
    def test_first_pitch_moves_to_recovered_annotated_pitch(self, db):
        """The annotated true-first pitch reclaims is_first_pitch; FPS flips."""
        # Buggy stored state: annotated Strike dropped to 'other'; the later
        # bare Ball was logged as the (wrong) first pitch -> FPS recorded 0.
        play_id = _insert_play(
            db, outcome="Walk", pitch_count=1, is_first_pitch_strike=0,
        )
        _insert_event(
            db, play_id, 0, "other", "Strike 1 looking (Curveball)",
            is_first_pitch=0,
        )
        _insert_event(
            db, play_id, 1, "pitch", "Ball 1",
            pitch_result="ball", is_first_pitch=1,
        )

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        evs = _events(db, play_id)
        # True first pitch is now event 0 (the recovered strike).
        assert evs[0]["is_first_pitch"] == 1
        assert evs[1]["is_first_pitch"] == 0
        play = _play(db, play_id)
        assert play["pitch_count"] == 2
        assert play["is_first_pitch_strike"] == 1


# ---------------------------------------------------------------------------
# AC-6: is_qab OR-merge incl. HHB-only-QAB survival
# ---------------------------------------------------------------------------


class TestQabOrMerge:
    def test_hhb_only_qab_survives_reparse(self, db):
        """An HHB-only QAB (stored is_qab=1, pitch_count 0 pre-reload) survives.

        On reload the recovered pitch_count is small (no 2S+3, < 6 pitches) so
        the only thing keeping is_qab true is the stored value -- it must NOT be
        dropped by a from-scratch recompute (final_details unavailable).
        """
        play_id = _insert_play(
            db, outcome="Single", pitch_count=0, is_qab=1,
        )
        _insert_event(db, play_id, 0, "other", "In play (75 MPH Fastball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        play = _play(db, play_id)
        assert play["pitch_count"] == 1
        assert play["is_qab"] == 1  # survived

    def test_qab_gained_from_recovered_6plus_pitches(self, db):
        """A PA that reaches 6+ recovered pitches gains is_qab (false-neg fix)."""
        play_id = _insert_play(
            db, outcome="Strikeout", pitch_count=0, is_qab=0,
        )
        for i in range(6):
            _insert_event(db, play_id, i, "other", f"Foul ({70 + i} MPH)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        play = _play(db, play_id)
        assert play["pitch_count"] == 6
        assert play["is_qab"] == 1

    def test_qab_stays_false_when_no_condition_met(self, db):
        """Few recovered pitches, no stored QAB -> is_qab stays 0."""
        play_id = _insert_play(
            db, outcome="Ground Out", pitch_count=0, is_qab=0,
        )
        _insert_event(db, play_id, 0, "other", "In play (Fastball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        assert _play(db, play_id)["is_qab"] == 0

    def test_excluded_outcome_with_long_count_stays_not_qab(self, db):
        """A Dropped 3rd Strike at 6+ recovered pitches must NOT become a QAB.

        The forward _compute_qab excludes IBB / Dropped 3rd Strike / Catcher's
        Interference before any pitch-count condition; the OR-merge must apply
        the same exclusion so the long count does not flip is_qab to 1.
        """
        play_id = _insert_play(
            db, outcome="Dropped 3rd Strike", pitch_count=0, is_qab=0,
        )
        for i in range(6):
            _insert_event(db, play_id, i, "other", f"Foul ({70 + i} MPH)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        play = _play(db, play_id)
        assert play["pitch_count"] == 6
        assert play["is_qab"] == 0  # excluded outcome -- not flipped

    def test_unaffected_excluded_play_not_corrupted(self, db):
        """A correctly-parsed excluded PA on an unaffected game is left at 0.

        Guards the batch-pass corruption case: the reload visits every play,
        so a previously-correct is_qab=0 on an excluded long-count PA must not
        be flipped to 1 by the merge.
        """
        play_id = _insert_play(
            db,
            outcome="Intentional Walk",
            pitch_count=6,
            is_qab=0,
        )
        # Already correctly classified as pitches (no annotation bug here).
        for i in range(6):
            _insert_event(
                db, play_id, i, "pitch", "Ball 1",
                pitch_result="ball", is_first_pitch=(1 if i == 0 else 0),
            )

        result = reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        play = _play(db, play_id)
        assert result.events_recovered == 0  # nothing was stranded
        assert play["pitch_count"] == 6
        assert play["is_qab"] == 0  # NOT corrupted to 1


# ---------------------------------------------------------------------------
# AC-7: idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_run_is_noop(self, db):
        play_id = _insert_play(db, outcome="Strikeout")
        _insert_event(db, play_id, 0, "other", "Strike 1 looking (Curveball)")
        _insert_event(db, play_id, 1, "other", "Strike 3 swinging (Slider)")

        first = reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()
        play_after_first = dict(_play(db, play_id))
        evs_after_first = [dict(e) for e in _events(db, play_id)]

        second = reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()
        play_after_second = dict(_play(db, play_id))
        evs_after_second = [dict(e) for e in _events(db, play_id)]

        assert first.events_recovered == 2
        # Second run recovers nothing new (already pitches).
        assert second.events_recovered == 0
        assert play_after_first == play_after_second
        assert evs_after_first == evs_after_second


# ---------------------------------------------------------------------------
# AC-8: perspective preserved
# ---------------------------------------------------------------------------


class TestPerspectivePreserved:
    def test_perspective_team_id_unchanged(self, db):
        play_id = _insert_play(db, perspective_team_id=1)
        _insert_event(db, play_id, 0, "other", "Ball 1 (Fastball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        assert _play(db, play_id)["perspective_team_id"] == 1


# ---------------------------------------------------------------------------
# AC-9: batting_team_id re-derived from FRESH games-row home/away
# ---------------------------------------------------------------------------


class TestBattingTeamRederivation:
    def test_batting_team_rederived_from_fresh_games_row(self, db):
        """Stale stored batting_team_id is corrected from the games row.

        This is the mechanism E-245-04 relies on after it flips a self-game's
        home/away: the reload re-reads home/away and re-derives per half.
        """
        # Stored batting_team_id is WRONG (1) for a top-half play (away bats).
        play_id = _insert_play(
            db, half="top", batting_team_id=1,
        )
        _insert_event(db, play_id, 0, "other", "Ball 1 (Fastball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        # games row: home=1, away=2; top half -> away (2) bats.
        assert _play(db, play_id)["batting_team_id"] == 2

    def test_bottom_half_uses_home_team(self, db):
        play_id = _insert_play(db, half="bottom", batting_team_id=2)
        _insert_event(db, play_id, 0, "other", "Ball 1 (Fastball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        assert _play(db, play_id)["batting_team_id"] == 1


# ---------------------------------------------------------------------------
# Scope isolation (multi-game / multi-perspective)
# ---------------------------------------------------------------------------


class TestScopeIsolation:
    def test_other_game_untouched(self, db):
        """Reloading one game does not alter a different game's plays."""
        target = _insert_play(db, game_id=_GAME_ID)
        _insert_event(db, target, 0, "other", "Strike 1 looking (Curveball)")
        other = _insert_play(db, game_id=_GAME_ID_2)
        _insert_event(db, other, 0, "other", "Strike 1 looking (Curveball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        assert _play(db, target)["pitch_count"] == 1
        # Untouched: still the buggy stored state.
        assert _play(db, other)["pitch_count"] == 0
        assert _events(db, other)[0]["event_type"] == "other"

    def test_other_perspective_untouched(self, db):
        """Reloading one perspective leaves the other perspective's plays alone."""
        p1 = _insert_play(db, perspective_team_id=1, play_order=0)
        _insert_event(db, p1, 0, "other", "Strike 1 looking (Curveball)")
        p2 = _insert_play(db, perspective_team_id=2, play_order=1)
        _insert_event(db, p2, 0, "other", "Strike 1 looking (Curveball)")

        reload_game_plays(db, _GAME_ID, perspective_team_id=1)
        db.commit()

        assert _play(db, p1)["pitch_count"] == 1
        assert _play(db, p2)["pitch_count"] == 0
        assert _events(db, p2)[0]["event_type"] == "other"

    def test_missing_game_or_perspective_returns_not_found(self, db):
        result = reload_game_plays(db, "no-such-game", perspective_team_id=1)
        assert result.found is False
        assert result.plays_updated == 0


# ---------------------------------------------------------------------------
# Batch driver (reload_all_games)
# ---------------------------------------------------------------------------


class TestReloadAllGames:
    def test_batch_summary_counts(self, db):
        p1 = _insert_play(db, game_id=_GAME_ID, perspective_team_id=1)
        _insert_event(db, p1, 0, "other", "Strike 1 looking (Curveball)")
        _insert_event(db, p1, 1, "other", "Strike 3 swinging (Slider)")
        # A second game that is already correct (bare pitch) -- no-op.
        p2 = _insert_play(
            db, game_id=_GAME_ID_2, perspective_team_id=1,
            pitch_count=1, is_first_pitch_strike=1,
        )
        _insert_event(
            db, p2, 0, "pitch", "Strike 1 looking",
            pitch_result="strike_looking", is_first_pitch=1,
        )

        summary = reload_all_games(db)

        assert summary["games_processed"] == 2
        assert summary["games_changed"] == 1  # only the annotated game
        assert summary["events_recovered"] == 2
        assert summary["games_with_errors"] == 0
        # The already-correct game is unchanged.
        assert _play(db, p2)["pitch_count"] == 1
        assert _play(db, p2)["is_first_pitch_strike"] == 1

    def test_empty_db_returns_zero_summary(self, db):
        summary = reload_all_games(db)
        assert summary["games_processed"] == 0
        assert summary["events_recovered"] == 0

    def test_per_game_error_isolated(self, db, monkeypatch):
        """A failure on one game is isolated; the batch continues (error path)."""
        p1 = _insert_play(db, game_id=_GAME_ID, perspective_team_id=1)
        _insert_event(db, p1, 0, "other", "Strike 1 looking (Curveball)")
        p2 = _insert_play(db, game_id=_GAME_ID_2, perspective_team_id=1)
        _insert_event(db, p2, 0, "other", "Strike 1 looking (Slider)")

        import src.gamechanger.loaders.plays_reload as mod

        real = mod.reload_game_plays
        calls: list[str] = []

        def flaky(conn, game_id, perspective_team_id):
            calls.append(game_id)
            if game_id == _GAME_ID:
                raise RuntimeError("boom")
            return real(conn, game_id, perspective_team_id)

        monkeypatch.setattr(mod, "reload_game_plays", flaky)
        summary = mod.reload_all_games(db)

        assert summary["games_with_errors"] == 1
        assert summary["games_processed"] == 1  # the other game still ran
        # The failed game was rolled back -- still buggy state.
        assert _play(db, p1)["pitch_count"] == 0
        assert _play(db, p2)["pitch_count"] == 1
