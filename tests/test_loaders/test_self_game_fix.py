"""Tests for the self-game (home == away) fix (E-245-04).

Two halves are exercised here:

* The FORWARD loader fix in ``game_loader.py`` -- the opponent always resolves
  to a DISTINCT team (by name when the stat block is absent, else an
  "Unknown Opponent" sentinel), and ``_upsert_game`` refuses to write a
  self-game (AC-1, AC-2).
* The CORRECTIVE re-ingest helpers in ``self_game_fix.py`` -- discovery of the
  corrupt rows and the IN-PLACE ``batting_team_id`` re-derivation that runs after
  a boxscore re-ingest corrects the games row (AC-3, AC-4).

All tests use an on-disk SQLite database with every migration applied. No
network calls -- the corrective re-ingest is simulated by running the FIXED
``GameLoader`` against an in-memory boxscore payload (the same path the live
crawl->load uses), then calling the in-place re-derivation directly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.game_loader import (
    _UNKNOWN_OPPONENT_NAME,
    GameLoader,
    GameSummaryEntry,
)
from src.gamechanger.loaders.plays_reload import reload_game_plays
from src.gamechanger.loaders.self_game_fix import (
    affected_team_ids,
    find_self_games,
    rederive_corrected_game_plays,
)
from src.gamechanger.types import TeamRef

_SEASON_ID = "2026"
_OWN_SLUG = "ownslug123"  # public_id slug (NOT a UUID -- own-team key detection)
_OWN_UUID = "0a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d"
_PLAYER_OWN = "0batter0-0001-0001-0001-000000000001"
_PLAYER_OWN_P = "0pitcher-0001-0001-0001-000000000001"


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    """Apply all migrations and seed the 2026 season + own (member) team."""
    db_path = tmp_path / "test.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) "
        "VALUES (?, 'Y2026', 2026)",
        (_SEASON_ID,),
    )
    # Own (scouted) team: id=1, has a public_id so the corrective CLI could
    # re-fetch it; season_year drives season derivation in GameLoader.
    conn.execute(
        "INSERT INTO teams (id, name, gc_uuid, public_id, membership_type, "
        "is_active, season_year) VALUES "
        "(1, 'Own Team', ?, ?, 'member', 1, 2026)",
        (_OWN_UUID, _OWN_SLUG),
    )
    conn.commit()
    return conn


def _make_loader(conn: sqlite3.Connection) -> GameLoader:
    return GameLoader(
        conn, owned_team_ref=TeamRef(id=1, gc_uuid=_OWN_UUID, public_id=_OWN_SLUG)
    )


def _own_only_boxscore() -> dict:
    """A boxscore carrying ONLY the scouted team's stat block (no opponent key).

    This is exactly the shape that produced self-games: the opponent never used
    GC scorekeeping, so its UUID key is absent.
    """
    return {
        _OWN_SLUG: {
            "players": [
                {
                    "id": _PLAYER_OWN,
                    "first_name": "Own",
                    "last_name": "Batter",
                    "number": "7",
                }
            ],
            "groups": [
                {
                    "category": "lineup",
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN,
                            "stats": {"AB": 3, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 1},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_P,
                            "stats": {"IP": 6, "H": 2, "R": 1, "ER": 1, "BB": 1, "SO": 8},
                        }
                    ],
                },
            ],
        }
    }


def _make_summary(
    event_id: str = "selfgame-001",
    home_away: str | None = "home",
) -> GameSummaryEntry:
    """Summary as the scouting path emits it: opponent_id hardcoded to ''."""
    return GameSummaryEntry(
        event_id=event_id,
        game_stream_id=event_id,
        home_away=home_away,
        owning_team_score=5,
        opponent_team_score=2,
        opponent_id="",  # scouting_loader hardcodes this (TN-6 root cause)
        date_source_instant="2026-04-10T19:00:00.000Z",
    )


# ---------------------------------------------------------------------------
# AC-1: opponent resolved by NAME when the stat block is absent -> home != away
# ---------------------------------------------------------------------------


def test_opponent_resolved_by_name_when_stat_block_absent(db: sqlite3.Connection) -> None:
    """AC-1: a name-only opponent yields a distinct opp team, so home != away."""
    loader = _make_loader(db)
    loader.load_payload(
        _own_only_boxscore(), _make_summary(), opponent_name="Real Opponent HS"
    )

    row = db.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = 'selfgame-001'"
    ).fetchone()
    assert row is not None
    home_id, away_id = row
    assert home_id != away_id, "home and away must be distinct (TN-6)"
    assert home_id == 1, "home_away='home' -> own team is home"

    # The opponent row exists, is named, and has NO per-player stat rows.
    opp_name = db.execute(
        "SELECT name FROM teams WHERE id = ?", (away_id,)
    ).fetchone()[0]
    assert opp_name == "Real Opponent HS"
    opp_stat_rows = db.execute(
        "SELECT COUNT(*) FROM player_game_batting WHERE team_id = ?", (away_id,)
    ).fetchone()[0]
    assert opp_stat_rows == 0, "name-only opponent carries no fabricated stat rows"


# ---------------------------------------------------------------------------
# AC-2: sentinel stub when truly unresolvable; invariant guard never emits self
# ---------------------------------------------------------------------------


def test_unresolvable_opponent_uses_sentinel_not_own_team(db: sqlite3.Connection) -> None:
    """AC-2: no name -> 'Unknown Opponent' sentinel, distinct from own team."""
    loader = _make_loader(db)
    loader.load_payload(_own_only_boxscore(), _make_summary(), opponent_name=None)

    home_id, away_id = db.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = 'selfgame-001'"
    ).fetchone()
    assert home_id != away_id, "sentinel must keep home != away (never own_team_id)"
    assert home_id == 1
    sentinel_name = db.execute(
        "SELECT name FROM teams WHERE id = ?", (away_id,)
    ).fetchone()[0]
    assert sentinel_name == _UNKNOWN_OPPONENT_NAME


def test_upsert_game_refuses_self_game(db: sqlite3.Connection) -> None:
    """AC-2: the _upsert_game invariant guard raises on home == away."""
    loader = _make_loader(db)
    with pytest.raises(ValueError, match="self-game"):
        loader._upsert_game(
            "would-be-self", "2026-04-10", 1, 1, 5, 2, "stream-x"
        )


def test_self_game_never_written_even_with_opponent_name(db: sqlite3.Connection) -> None:
    """AC-1/AC-2 end-to-end: loading the corrupt shape never yields a self-game."""
    loader = _make_loader(db)
    loader.load_payload(
        _own_only_boxscore(), _make_summary(), opponent_name="Some Other Team"
    )
    assert find_self_games(db) == [], "no self-game should exist after the fix"


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _seed_self_game(
    conn: sqlite3.Connection,
    game_id: str = "selfgame-001",
    perspective_team_id: int = 1,
) -> None:
    """Seed the CORRUPT pre-fix state: a self-game with collapsed plays.

    games row home == away == 1; two plays (top + bottom) both with
    batting_team_id collapsed to 1; each play has a play_events row carrying
    raw_template (which the correction must preserve).
    """
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, home_score, away_score, status, game_stream_id) "
        "VALUES (?, ?, '2026-04-10', 1, 1, 5, 2, 'completed', ?)",
        (game_id, _SEASON_ID, game_id),
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Own', 'Batter')",
        (_PLAYER_OWN,),
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Own', 'Pitch')",
        (_PLAYER_OWN_P,),
    )
    for order, half in ((0, "top"), (1, "bottom")):
        cur = conn.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome) "
            "VALUES (?, ?, 1, ?, ?, 1, ?, ?, ?, 'Single')",
            (game_id, order, half, _SEASON_ID, perspective_team_id, _PLAYER_OWN, _PLAYER_OWN_P),
        )
        play_id = cur.lastrowid
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type, raw_template) "
            "VALUES (?, 0, 'pitch', ?)",
            (play_id, f"Ball ({half})"),
        )
    conn.commit()


def test_find_self_games_and_affected_teams(db: sqlite3.Connection) -> None:
    """Discovery: find_self_games + affected_team_ids locate the corrupt rows."""
    _seed_self_game(db)
    assert find_self_games(db) == [("selfgame-001", 1)]
    assert affected_team_ids(db) == [1]


# ---------------------------------------------------------------------------
# AC-3: full corrective sequence (re-ingest corrects games row, then in-place
#       re-derivation fixes batting_team_id) with NO play_events clear
# ---------------------------------------------------------------------------


def test_corrective_sequence_fixes_self_game_in_place(db: sqlite3.Connection) -> None:
    """AC-3: boxscore re-ingest + in-place reload corrects games + batting_team_id."""
    _seed_self_game(db)
    events_before = db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]
    templates_before = {
        r[0] for r in db.execute("SELECT raw_template FROM play_events")
    }

    # Step 1: boxscore re-ingest via the FIXED loader (the live crawl->load path,
    # simulated in-memory). Corrects the games row to home != away by name.
    loader = _make_loader(db)
    loader.load_payload(
        _own_only_boxscore(), _make_summary(event_id="selfgame-001"),
        opponent_name="Real Opponent HS",
    )

    home_id, away_id = db.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = 'selfgame-001'"
    ).fetchone()
    assert home_id == 1 and away_id != 1, "games row corrected to home != away"
    opp_id = away_id

    # Step 2: in-place re-derivation of batting_team_id (TN-3b).
    summary = rederive_corrected_game_plays(db, ["selfgame-001"])
    assert summary["games_rederived"] == 1
    assert summary["games_with_errors"] == 0

    # top half -> away (opponent) bats; bottom half -> home (own) bats.
    rows = dict(
        db.execute(
            "SELECT half, batting_team_id FROM plays WHERE game_id = 'selfgame-001'"
        ).fetchall()
    )
    assert rows["top"] == opp_id, "top-half batting team re-derived to away (opp)"
    assert rows["bottom"] == 1, "bottom-half batting team re-derived to home (own)"

    # play_events were NOT cleared and raw_template is preserved (TN-6 / TN-3/M1).
    events_after = db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]
    templates_after = {
        r[0] for r in db.execute("SELECT raw_template FROM play_events")
    }
    assert events_after == events_before, "play_events must not be cleared"
    assert templates_after == templates_before, "raw_template must be preserved"


def test_corrective_sequence_clears_self_game_counter(db: sqlite3.Connection) -> None:
    """AC-3/AC-5 shape: after the correction the self-game count goes to 0."""
    _seed_self_game(db)
    assert len(find_self_games(db)) == 1
    loader = _make_loader(db)
    loader.load_payload(
        _own_only_boxscore(), _make_summary(event_id="selfgame-001"),
        opponent_name="Real Opponent HS",
    )
    rederive_corrected_game_plays(db, ["selfgame-001"])
    assert find_self_games(db) == [], "self-game counter must reach 0"


# ---------------------------------------------------------------------------
# AC-4: perspective scoping; no rows deleted/downgraded
# ---------------------------------------------------------------------------


def test_rederive_preserves_perspective_and_deletes_nothing(db: sqlite3.Connection) -> None:
    """AC-4: re-derivation is perspective-scoped and non-destructive.

    Two perspectives (the member team id=1 and a second tracked team id=2) carry
    plays for the same corrected game. The in-place re-derivation must re-derive
    BOTH against the corrected games row without changing any row's
    perspective_team_id and without deleting any plays/play_events rows.
    """
    # Second perspective team.
    db.execute(
        "INSERT INTO teams (id, name, membership_type, is_active, season_year) "
        "VALUES (2, 'Second Perspective', 'tracked', 1, 2026)"
    )
    db.commit()
    _seed_self_game(db, perspective_team_id=1)
    # Add a second-perspective top-half play for the same game.
    cur = db.execute(
        "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
        "batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome) "
        "VALUES ('selfgame-001', 2, 1, 'top', ?, 1, 2, ?, ?, 'Single')",
        (_SEASON_ID, _PLAYER_OWN, _PLAYER_OWN_P),
    )
    db.execute(
        "INSERT INTO play_events (play_id, event_order, event_type, raw_template) "
        "VALUES (?, 0, 'pitch', 'Ball (p2)')",
        (cur.lastrowid,),
    )
    db.commit()

    plays_before = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    events_before = db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0]

    # Correct the games row, then re-derive.
    loader = _make_loader(db)
    loader.load_payload(
        _own_only_boxscore(), _make_summary(event_id="selfgame-001"),
        opponent_name="Real Opponent HS",
    )
    opp_id = db.execute(
        "SELECT away_team_id FROM games WHERE game_id = 'selfgame-001'"
    ).fetchone()[0]
    summary = rederive_corrected_game_plays(db, ["selfgame-001"])
    assert summary["games_with_errors"] == 0

    # Nothing deleted.
    assert db.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == plays_before
    assert db.execute("SELECT COUNT(*) FROM play_events").fetchone()[0] == events_before

    # Perspective preserved on every row; each perspective's top half re-derived
    # to the opponent independently.
    p1_top = db.execute(
        "SELECT batting_team_id FROM plays WHERE perspective_team_id = 1 AND half = 'top'"
    ).fetchone()[0]
    p2_top = db.execute(
        "SELECT batting_team_id FROM plays WHERE perspective_team_id = 2 AND half = 'top'"
    ).fetchone()[0]
    assert p1_top == opp_id and p2_top == opp_id


def test_rederive_skips_game_with_no_plays(db: sqlite3.Connection) -> None:
    """A game with no plays rows is a no-op (found=False path)."""
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, status) VALUES ('no-plays', ?, '2026-04-10', 1, 1, 'completed')",
        (_SEASON_ID,),
    )
    db.commit()
    summary = rederive_corrected_game_plays(db, ["no-plays"])
    assert summary == {
        "games_rederived": 0,
        "plays_updated": 0,
        "games_with_errors": 0,
    }
