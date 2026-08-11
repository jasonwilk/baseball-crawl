"""Tests for game dedup logic in GameLoader (E-216-01).

Verifies that GameLoader.load_payload() detects when a game already exists
for the same date and team pair (in either home/away order) and reuses
the existing game_id for all stat upserts.

Test coverage:
- (a): Basic dedup detection -- same date, same teams, different game_id
- (b): Order-insensitive team matching (home/away swapped)
- (c): Doubleheader non-collision with different start_time
- (d): Doubleheader non-collision with score tiebreaker (NULL start_time)
- (e): NULL start_time fallback to score matching
- AC-4: INFO log emitted on dedup redirect
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from src.db.game_merge import GameMergeError
from src.gamechanger.loaders import ensure_season_row
from src.gamechanger.loaders.game_loader import (
    GameLoader,
    GameSummaryEntry,
    _is_same_listing_delta,
)
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.types import TeamRef
from src.reports.generator import (
    _query_recent_games,
    _query_record,
    _query_runs_avg,
)

# ---------------------------------------------------------------------------
# Schema fixture
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
# E-250-02: migration 008 drops seasons.season_type, team_opponents, and
# players.gc_athlete_profile_id -- apply it so the schema matches the fixtures.
_MIGRATION_008 = (
    _PROJECT_ROOT / "migrations" / "008_drop_identity_opponent_season_type.sql"
)
# E-253-05: migration 010 adds the partial UNIQUE game-dedup backstop on
# games(game_stream_id) WHERE game_stream_id IS NOT NULL.
_MIGRATION_010 = (
    _PROJECT_ROOT / "migrations" / "010_game_dedup_backstop.sql"
)
# E-264-01: migration 012 adds teams.innings_per_game, which ensure_team_row's
# INSERT now references -- apply it so the teams schema matches the loader writes.
_MIGRATION_012 = (
    _PROJECT_ROOT / "migrations" / "012_teams_innings_per_game.sql"
)
# Migration 013 adds game_perspectives.plays_final_{home,away}_score, which the
# twin merge COPIES onto the canonical game -- apply it so the merge's column
# list matches the schema.
_MIGRATION_013 = (
    _PROJECT_ROOT / "migrations" / "013_game_perspectives_plays_final_score.sql"
)


@pytest.fixture()
def db() -> sqlite3.Connection:
    """In-memory SQLite with schema applied and FK enforcement on."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_008.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_012.read_text(encoding="utf-8"))
    conn.executescript(_MIGRATION_013.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


def _apply_migration_010(conn: sqlite3.Connection) -> None:
    """Layer migration 010's partial UNIQUE backstop onto the base ``db`` fixture.

    The base fixture stops at 001+008; the AC-4 no-regression test needs the
    games(game_stream_id) backstop index active to prove the SELECT-then-INSERT
    collapse still works WITH the index present (the collapse redirects to the
    canonical game_id, so it never trips the index).
    """
    conn.executescript(_MIGRATION_010.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.commit()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OWN_TEAM_SLUG = "y24fFdnr3RAN"
_OWN_TEAM_UUID = "team-uuid-jv-001"
_OPP_TEAM_UUID = "16d38cf9-4f73-438c-83e4-1c28fbb23628"

_GAME_DATE = "2025-05-10"
_EVENT_ID_1 = "event-first-001"
_EVENT_ID_2 = "event-second-002"
_STREAM_ID_1 = "stream-aaa-001"
_STREAM_ID_2 = "stream-bbb-002"

_PLAYER_OWN_1 = "player-own-aaa-001"
_PLAYER_OWN_P1 = "player-own-pitcher-001"
_PLAYER_OPP_1 = "player-opp-ccc-001"
_PLAYER_OPP_P1 = "player-opp-pitcher-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_own_team(db: sqlite3.Connection) -> int:
    cur = db.execute(
        "INSERT OR IGNORE INTO teams (gc_uuid, public_id, name, membership_type, is_active, season_year) "
        "VALUES (?, ?, ?, 'member', 1, 2025)",
        (_OWN_TEAM_UUID, _OWN_TEAM_SLUG, _OWN_TEAM_UUID),
    )
    if cur.rowcount:
        return cur.lastrowid
    return db.execute("SELECT id FROM teams WHERE gc_uuid = ?", (_OWN_TEAM_UUID,)).fetchone()[0]


def _make_loader(db: sqlite3.Connection) -> GameLoader:
    pk = _insert_own_team(db)
    loader = GameLoader(
        db,
        owned_team_ref=TeamRef(id=pk, gc_uuid=_OWN_TEAM_UUID, public_id=_OWN_TEAM_SLUG),
    )
    # ScoutingLoader normally ensures the season row; load_payload() skips it.
    ensure_season_row(db, loader._season_id)
    return loader


def _make_summary(
    event_id: str = _EVENT_ID_1,
    game_stream_id: str = _STREAM_ID_1,
    home_away: str = "home",
    owning_score: int = 5,
    opponent_score: int = 2,
    start_time: str | None = None,
    game_date: str = _GAME_DATE,
    date_source_instant: str | None = None,
) -> GameSummaryEntry:
    # `date_source_instant` is what the stored `game_date` DERIVES from, so it
    # cannot be a constant swap at the call site (E-278-02 round 1). It defaults
    # to an afternoon instant on `game_date` -- fine for tests that do not care
    # about the derivation, and deliberately overridable by those that do, since
    # an afternoon instant's local date equals its UTC slice and therefore
    # cannot detect a UTC-slicing regression.
    if date_source_instant is None:
        date_source_instant = f"{game_date}T19:39:58.788Z"
    return GameSummaryEntry(
        event_id=event_id,
        game_stream_id=game_stream_id,
        home_away=home_away,
        owning_team_score=owning_score,
        opponent_team_score=opponent_score,
        opponent_id=_OPP_TEAM_UUID,
        date_source_instant=date_source_instant,
        start_time=start_time,
    )


def _make_boxscore() -> dict:
    """Minimal valid boxscore dict."""
    return {
        _OWN_TEAM_SLUG: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "team_stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_1,
                            "player_text": "(CF)",
                            "is_primary": True,
                            "stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 1, "SO": 0},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "team_stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OWN_P1,
                            "player_text": "(W)",
                            "stats": {"IP": 5, "H": 3, "R": 2, "ER": 2, "BB": 1, "SO": 7},
                        }
                    ],
                },
            ],
        },
        _OPP_TEAM_UUID: {
            "players": [],
            "groups": [
                {
                    "category": "lineup",
                    "team_stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OPP_1,
                            "player_text": "(1B)",
                            "is_primary": True,
                            "stats": {"AB": 4, "R": 1, "H": 1, "RBI": 0, "BB": 0, "SO": 2},
                        }
                    ],
                },
                {
                    "category": "pitching",
                    "team_stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
                    "extra": [],
                    "stats": [
                        {
                            "player_id": _PLAYER_OPP_P1,
                            "player_text": "(L)",
                            "stats": {"IP": 4, "H": 5, "R": 5, "ER": 4, "BB": 2, "SO": 4},
                        }
                    ],
                },
            ],
        },
    }


def _load_first_game(
    db: sqlite3.Connection,
    loader: GameLoader,
    *,
    start_time: str | None = None,
    owning_score: int = 5,
    opponent_score: int = 2,
) -> None:
    """Load the 'first' game so a row exists in the DB for dedup testing."""
    summary = _make_summary(
        event_id=_EVENT_ID_1,
        game_stream_id=_STREAM_ID_1,
        start_time=start_time,
        owning_score=owning_score,
        opponent_score=opponent_score,
    )
    loader.load_payload(_make_boxscore(), summary)


# ---------------------------------------------------------------------------
# (a): Basic dedup detection
# ---------------------------------------------------------------------------


def test_dedup_reuses_existing_game_id(
    db: sqlite3.Connection,
) -> None:
    """When a game already exists for the same date and team pair, the new
    boxscore reuses the existing game_id -- no duplicate games row created."""
    loader = _make_loader(db)
    _load_first_game(db, loader)

    # Second load: different event_id, same date/teams/score.
    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)
    loader.load_payload(_make_boxscore(), summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 1, f"Expected 1 game row (dedup), got {game_count}"

    row = db.execute("SELECT game_id FROM games").fetchone()
    assert row[0] == _EVENT_ID_1


def test_dedup_collapse_still_works_with_backstop_index(
    db: sqlite3.Connection,
) -> None:
    """E-253-05 AC-4: with migration 010's partial UNIQUE backstop active, the
    existing SELECT-then-INSERT cross-perspective collapse still yields ONE row
    and does NOT raise an IntegrityError.

    The collapse redirects the second load to the canonical game_id, so the
    upsert's ``ON CONFLICT(game_id) DO UPDATE`` updates the existing row rather
    than inserting a second row -- the backstop index is never tripped by the
    primary path.

    E-261-01 update: this test previously asserted the upsert *refreshed* the
    canonical row's game_stream_id to the incoming ``_STREAM_ID_2`` (the clobber).
    That clobber is the Defect A bug this story fixes -- the conflict clause is
    now keep-existing, so the canonical row's own ``_STREAM_ID_1`` is preserved.
    The core no-regression guarantee (one row, no IntegrityError) is unchanged.
    """
    _apply_migration_010(db)
    loader = _make_loader(db)
    _load_first_game(db, loader)  # game_stream_id = _STREAM_ID_1

    # Second perspective of the same real game: different event_id + stream_id,
    # same date/teams/score -> dedup collapses to the canonical row.
    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)
    loader.load_payload(_make_boxscore(), summary2)

    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    row = db.execute("SELECT game_id, game_stream_id FROM games").fetchone()
    assert row[0] == _EVENT_ID_1  # canonical game_id preserved
    assert row[1] == _STREAM_ID_1  # keep-existing: canonical stream id preserved (E-261-01)


def test_dedup_stats_use_canonical_game_id(
    db: sqlite3.Connection,
) -> None:
    """Stat rows are keyed to the existing (canonical) game_id, not the new one."""
    loader = _make_loader(db)
    _load_first_game(db, loader)

    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)
    loader.load_payload(_make_boxscore(), summary2)

    batting_ids = db.execute(
        "SELECT DISTINCT game_id FROM player_game_batting"
    ).fetchall()
    assert all(r[0] == _EVENT_ID_1 for r in batting_ids)

    pitching_ids = db.execute(
        "SELECT DISTINCT game_id FROM player_game_pitching"
    ).fetchall()
    assert all(r[0] == _EVENT_ID_1 for r in pitching_ids)


# ---------------------------------------------------------------------------
# (b): Order-insensitive team matching
# ---------------------------------------------------------------------------


def test_dedup_order_insensitive_team_matching(
    db: sqlite3.Connection,
) -> None:
    """Dedup detects the match even when home/away are swapped between the
    existing game and the incoming boxscore."""
    loader = _make_loader(db)
    # First game: own team is HOME.
    _load_first_game(db, loader)

    # Second game: own team is AWAY (swapped perspective), same date and teams.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        home_away="away",
        owning_score=5,
        opponent_score=2,
    )
    loader.load_payload(_make_boxscore(), summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 1, f"Expected dedup to 1 game, got {game_count}"


# ---------------------------------------------------------------------------
# (c): Doubleheader non-collision with start_time
# ---------------------------------------------------------------------------


def test_doubleheader_different_start_time_no_dedup(
    db: sqlite3.Connection,
) -> None:
    """Two games on the same date between the same teams with different
    start_time values are NOT deduped (doubleheader)."""
    loader = _make_loader(db)
    _load_first_game(db, loader, start_time="2025-05-10T14:00:00.000Z")

    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        start_time="2025-05-10T18:00:00.000Z",
    )
    loader.load_payload(_make_boxscore(), summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 2, f"Expected 2 games (doubleheader), got {game_count}"


# ---------------------------------------------------------------------------
# (d): Doubleheader non-collision with score tiebreaker
# ---------------------------------------------------------------------------


def test_doubleheader_different_score_null_start_time_no_dedup(
    db: sqlite3.Connection,
) -> None:
    """When start_time is NULL on both sides but total scores differ,
    the games are NOT deduped (doubleheader distinguished by score)."""
    loader = _make_loader(db)
    # First: 5-2 (total 7), no start_time.
    _load_first_game(db, loader, owning_score=5, opponent_score=2)

    # Second: 3-1 (total 4), no start_time.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        owning_score=3,
        opponent_score=1,
        start_time=None,
    )
    loader.load_payload(_make_boxscore(), summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 2, f"Expected 2 games (doubleheader by score), got {game_count}"


# ---------------------------------------------------------------------------
# (e): NULL start_time fallback to score matching → dedup
# ---------------------------------------------------------------------------


def test_null_start_time_same_score_triggers_dedup(
    db: sqlite3.Connection,
) -> None:
    """When start_time is NULL on both sides and score totals match,
    the game IS deduped."""
    loader = _make_loader(db)
    _load_first_game(db, loader, owning_score=5, opponent_score=2)

    # Second: same 5-2 score, no start_time.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        owning_score=5,
        opponent_score=2,
        start_time=None,
    )
    loader.load_payload(_make_boxscore(), summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 1, f"Expected dedup to 1 game, got {game_count}"


# ---------------------------------------------------------------------------
# AC-4: INFO log on dedup redirect
# ---------------------------------------------------------------------------


def test_dedup_logs_info_message(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture,
) -> None:
    """An INFO-level log message identifies both game_ids on dedup redirect."""
    loader = _make_loader(db)
    _load_first_game(db, loader)

    summary2 = _make_summary(event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2)

    with caplog.at_level(logging.INFO, logger="src.gamechanger.loaders.game_loader"):
        loader.load_payload(_make_boxscore(), summary2)

    dedup_msgs = [r for r in caplog.records if "Dedup" in r.message]
    assert len(dedup_msgs) >= 1, "Expected at least one Dedup INFO log message"
    msg = dedup_msgs[0]
    assert msg.levelno == logging.INFO
    assert _EVENT_ID_1 in msg.message
    assert _EVENT_ID_2 in msg.message


# ---------------------------------------------------------------------------
# No false-positive: different date → no dedup
# ---------------------------------------------------------------------------


def test_different_date_no_dedup(
    db: sqlite3.Connection,
) -> None:
    """Games on different dates between the same teams are NOT deduped."""
    loader = _make_loader(db)
    _load_first_game(db, loader)

    # Second game on a different date.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        game_date="2025-05-11",
    )
    loader.load_payload(_make_boxscore(), summary2)

    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert game_count == 2


# ---------------------------------------------------------------------------
# Ambiguous candidate skipped, real match found
# ---------------------------------------------------------------------------

_EVENT_ID_3 = "event-third-003"
_STREAM_ID_3 = "stream-ccc-003"


def test_dedup_skips_ambiguous_finds_real_match(
    db: sqlite3.Connection,
) -> None:
    """When multiple same-date/team-pair rows exist and one is ambiguous
    (NULL start_time/scores) while another is a real match, the dedup
    skips the ambiguous candidate and finds the correct duplicate."""
    loader = _make_loader(db)

    # Load game 1: has start_time, score 5-2.
    _load_first_game(
        db, loader,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=5,
        opponent_score=2,
    )

    # Load game 2: NULL start_time, NULL scores (ambiguous).
    summary2 = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        start_time=None,
        owning_score=0,
        opponent_score=0,
    )
    loader.load_payload(_make_boxscore(), summary2)

    # Should have 2 games now (game 1 and game 2 are distinct -- different
    # start_time and different scores).
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2

    # Load game 3: same start_time as game 1 → should dedup to game 1,
    # not be blocked by the ambiguous game 2.
    summary3 = _make_summary(
        event_id=_EVENT_ID_3,
        game_stream_id=_STREAM_ID_3,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=5,
        opponent_score=2,
    )
    loader.load_payload(_make_boxscore(), summary3)

    # Still 2 games -- game 3 deduped into game 1.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2

    # Verify the canonical game_id is game 1 (not game 2).
    game_ids = {r[0] for r in db.execute("SELECT game_id FROM games").fetchall()}
    assert _EVENT_ID_1 in game_ids
    assert _EVENT_ID_2 in game_ids
    assert _EVENT_ID_3 not in game_ids


# ---------------------------------------------------------------------------
# Cross-perspective dedup via provenance
# ---------------------------------------------------------------------------


def test_cross_perspective_dedup_ignores_start_time_mismatch(
    db: sqlite3.Connection,
) -> None:
    """When two tracked teams' scouts load the same real game with identical
    scores but different start_time values, the second load must dedup via
    the provenance+score signals and ignore the start_time disagreement.

    Regression for the 2026-04-06 Norris duplicate: GameChanger reported the
    same real game with a 30-minute start_time gap between the two
    perspectives (21:30Z vs 22:00Z). Pre-fix, ``_find_duplicate_game``'s
    tiebreaker assumed "different start_time = doubleheader" and inserted a
    duplicate row. Post-fix, the provenance check (``game_perspectives``
    shows the existing row was loaded from a different team's perspective)
    plus score match overrides the start_time signal.
    """
    loader_a = _make_loader(db)
    _load_first_game(
        db, loader_a,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=11,
        opponent_score=1,
    )

    # The opponent team was implicitly created by _load_first_game.
    # _ensure_team_row() deliberately inserts opponent rows with gc_uuid=NULL
    # (anti-contamination) and puts the boxscore identifier in the name column.
    # Query by name for the opponent; own team keeps its gc_uuid.
    team_b_row = db.execute(
        "SELECT id FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_TEAM_UUID,),
    ).fetchone()
    assert team_b_row is not None, "Opponent team should exist after first load"
    team_b_id = team_b_row[0]

    # Confirm game_perspectives recorded team A's perspective on the first load.
    team_a_id = db.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?",
        (_OWN_TEAM_UUID,),
    ).fetchone()[0]
    persp_rows = db.execute(
        "SELECT perspective_team_id FROM game_perspectives WHERE game_id = ?",
        (_EVENT_ID_1,),
    ).fetchall()
    assert (team_a_id,) in persp_rows, (
        "game_perspectives should have a row for team A after first load"
    )

    # Create a GameLoader with team B (the opponent) as the perspective.
    loader_b = GameLoader(
        db,
        owned_team_ref=TeamRef(id=team_b_id, gc_uuid=_OPP_TEAM_UUID, public_id=None),
    )

    # Simulate team B's scout: same date, same teams, same final score,
    # different start_time (30-minute offset -- the Norris failure shape).
    game_row = db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score "
        "FROM games WHERE game_id = ?",
        (_EVENT_ID_1,),
    ).fetchone()
    home_id, away_id, home_score, away_score = game_row

    canonical_id = loader_b._find_duplicate_game(
        game_id=_EVENT_ID_2,  # team B's scout produced a different GC event_id
        game_date=_GAME_DATE,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=home_score,
        away_score=away_score,
        start_time="2025-05-10T14:30:00.000Z",  # 30 min later than team A's row
    )

    assert canonical_id == _EVENT_ID_1, (
        f"Cross-perspective dedup must return {_EVENT_ID_1} (team A's canonical "
        f"game_id). Got {canonical_id}. Provenance shows team A loaded this row; "
        f"we are team B with matching scores -- start_time mismatch is expected "
        f"from per-perspective GC data and must not prevent dedup."
    )


def test_cross_perspective_no_dedup_when_scores_disagree(
    db: sqlite3.Connection,
) -> None:
    """Cross-perspective candidates with mismatched score totals are NOT
    deduped. Score disagreement across perspectives is a data-quality signal
    worth surfacing as distinct rows, not silently collapsed.

    E-261-03a SE-5b reconciliation (AC-5): this 11-1 vs 10-1 case is the SAME
    "one side off by 1" shape as Defect B's 12-4 vs 12-5, yet it must STILL NOT
    dedup here -- and it does not, because the tolerant same-game signal is
    schedule-count PRIMARY and DEFAULTS OFF with no count context. This test
    calls ``_find_duplicate_game`` directly and passes NO ``incoming_schedule_count``,
    so the tolerant guard never fires; only the exact-score cross-perspective
    branch runs, which correctly refuses the mismatch. Defect B collapses only
    because its load path supplies ``incoming_schedule_count == 1`` (see
    ``test_tolerant_signal_redirects_on_score_disagreement``). The two coexist by
    design: the discriminator is schedule-count, not score-tolerance."""
    loader_a = _make_loader(db)
    _load_first_game(
        db, loader_a,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=11,
        opponent_score=1,
    )

    team_b_id = db.execute(
        "SELECT id FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_TEAM_UUID,),
    ).fetchone()[0]
    loader_b = GameLoader(
        db,
        owned_team_ref=TeamRef(id=team_b_id, gc_uuid=_OPP_TEAM_UUID, public_id=None),
    )

    game_row = db.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
        (_EVENT_ID_1,),
    ).fetchone()
    home_id, away_id = game_row

    # Team B reports a different score (10-1 instead of 11-1). That's a
    # genuine data disagreement, not a cross-perspective duplicate.
    canonical_id = loader_b._find_duplicate_game(
        game_id=_EVENT_ID_2,
        game_date=_GAME_DATE,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=10,
        away_score=1,
        start_time="2025-05-10T14:00:00.000Z",  # same start_time this time
    )

    assert canonical_id is None, (
        "Cross-perspective with different score totals must not dedup; "
        f"got canonical_id={canonical_id}. A real doubleheader or a data "
        "disagreement deserves a distinct row."
    )


def test_cross_perspective_no_dedup_when_scoreline_differs_but_total_matches(
    db: sqlite3.Connection,
) -> None:
    """A real doubleheader where two distinct games happen to have the same
    total score (e.g. 11-1 and 10-2 both total 12) must NOT be collapsed.

    Cross-perspective dedup must compare per-team scores pairwise, not the
    sum. Using the sum would silently merge same-total-different-scoreline
    doubleheaders. Regression guard for the Codex review finding on the
    initial fix.
    """
    loader_a = _make_loader(db)
    _load_first_game(
        db, loader_a,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=11,
        opponent_score=1,
    )

    team_b_id = db.execute(
        "SELECT id FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_TEAM_UUID,),
    ).fetchone()[0]
    loader_b = GameLoader(
        db,
        owned_team_ref=TeamRef(id=team_b_id, gc_uuid=_OPP_TEAM_UUID, public_id=None),
    )

    game_row = db.execute(
        "SELECT home_team_id, away_team_id FROM games WHERE game_id = ?",
        (_EVENT_ID_1,),
    ).fetchone()
    home_id, away_id = game_row

    # Same total (12) but different scoreline: 10-2 vs existing 11-1.
    canonical_id = loader_b._find_duplicate_game(
        game_id=_EVENT_ID_2,
        game_date=_GAME_DATE,
        home_team_id=home_id,
        away_team_id=away_id,
        home_score=10,
        away_score=2,
        start_time="2025-05-10T18:00:00.000Z",  # second game of a doubleheader
    )

    assert canonical_id is None, (
        "Cross-perspective with same total but different per-team scoreline "
        f"must not dedup; got canonical_id={canonical_id}. 11-1 and 10-2 each "
        "total 12, but they are distinct games (real doubleheader)."
    )


# ---------------------------------------------------------------------------
# E-261-01: redirect-path game_stream_id clobber (Defect A)
# ---------------------------------------------------------------------------

_DEFECT_A_CANONICAL_ID = "opp-event-X"  # canonical row X, perspective = opponent
_DEFECT_A_TWIN_ID = "own-event-E"       # un-merged twin E, perspective = own team


def test_redirect_preserves_canonical_stream_id_and_does_not_error(
    db: sqlite3.Connection,
) -> None:
    """E-261-01 AC-1/AC-2 (Defect A, TN-2 recipe).

    Seeded state: a canonical row X (``game_stream_id='opp-event-X'``, loaded
    from the OPPONENT team's perspective) plus an un-merged twin row E
    (``game_stream_id='own-event-E'``, loaded from the OWN team's perspective),
    same date/pair/scores. ``game_stream_id`` is self-keyed to each row's own
    event_id (the real scouting/public shape -- non-null AND perspective-
    specific), and migration 010's partial UNIQUE index is active.

    When the OWN-perspective payload for event E is loaded, ``_find_duplicate_game``
    redirects E -> X. Pre-fix, ``_upsert_game`` wrote ``game_stream_id =
    excluded.game_stream_id`` = 'own-event-E' onto row X -- but twin E still owns
    that value, so the partial UNIQUE index raises and the load returns
    ``LoadResult(errors=1)``. Post-fix (keep-existing COALESCE), row X keeps its
    own 'opp-event-X', no UNIQUE violation fires, and ``errors == 0``.

    E-261-03b update: the redirect site now also MERGES the persisted twin E into
    the canonical row (``merge_duplicate_game``), so after the load exactly ONE
    ``games`` row survives (X) -- the pair is collapsed, not left dangling. This
    test still pins the E-261-01 guarantees (no UNIQUE error, ``errors == 0``,
    canonical ``game_stream_id`` preserved) and now also the single-row end state.

    Reverting the one-line keep-existing change in ``_upsert_game`` makes this
    test fail with the ``UNIQUE constraint failed: games.game_stream_id`` error.
    """
    _apply_migration_010(db)
    loader = _make_loader(db)
    team_a_id = loader._team_ref.id  # own team (perspective of twin E)

    # Resolve the opponent team B through the SAME cascade the payload load will
    # use, so the load matches this exact row instead of stubbing a fresh one.
    # TN-2 resolution trap: if the opponent resolves to a DIFFERENT team id than
    # the seeded rows reference, the natural-key dedup silently never matches and
    # the redirect never fires. Pre-creating team B via _ensure_team_row (name +
    # season match, idempotent) guarantees the id match without hand-guessing
    # season_year -- the robust alternative to threading opponent_name through.
    team_b_id = loader._ensure_team_row(_OPP_TEAM_UUID)  # opponent (perspective of canonical X)
    assert team_a_id != team_b_id

    season_id = loader._season_id
    # own team is HOME in _make_summary/_make_boxscore (home_away='home'),
    # score 5-2 -> home_score=5, away_score=2.
    for game_id in (_DEFECT_A_CANONICAL_ID, _DEFECT_A_TWIN_ID):
        db.execute(
            """
            INSERT INTO games
                (game_id, season_id, game_date, home_team_id, away_team_id,
                 home_score, away_score, status, game_stream_id)
            VALUES (?, ?, ?, ?, ?, 5, 2, 'completed', ?)
            """,
            (game_id, season_id, _GAME_DATE, team_a_id, team_b_id, game_id),
        )
    # Provenance: X from opponent B's perspective, E from own A's perspective.
    db.execute(
        "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
        (_DEFECT_A_CANONICAL_ID, team_b_id),
    )
    db.execute(
        "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
        (_DEFECT_A_TWIN_ID, team_a_id),
    )
    db.commit()

    # Load the OWN-perspective payload for event E (matching scores 5-2).
    summary = _make_summary(
        event_id=_DEFECT_A_TWIN_ID,
        game_stream_id=_DEFECT_A_TWIN_ID,
        owning_score=5,
        opponent_score=2,
    )
    result = loader.load_payload(_make_boxscore(), summary)

    # AC-2: no UNIQUE constraint failure; the load succeeds.
    assert result.errors == 0, (
        f"Expected 0 errors after keep-existing fix, got {result.errors}. "
        "A non-zero count means the redirect still clobbered the canonical "
        "game_stream_id and tripped migration 010's UNIQUE index."
    )

    # AC-1: canonical row X kept its own game_stream_id (not clobbered to E's).
    x_stream = db.execute(
        "SELECT game_stream_id FROM games WHERE game_id = ?",
        (_DEFECT_A_CANONICAL_ID,),
    ).fetchone()[0]
    assert x_stream == _DEFECT_A_CANONICAL_ID, (
        f"Canonical row's game_stream_id must be preserved as "
        f"{_DEFECT_A_CANONICAL_ID!r}, got {x_stream!r}."
    )

    # The redirect fired (E -> X recorded) and stats merged into the canonical id.
    assert loader.redirect_map.get(_DEFECT_A_TWIN_ID) == _DEFECT_A_CANONICAL_ID

    # E-261-03b: the twin E was merged into X -- exactly one row survives, and
    # the surviving row is the canonical X (twin E's game_id is gone).
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.execute(
        "SELECT 1 FROM games WHERE game_id = ?", (_DEFECT_A_TWIN_ID,)
    ).fetchone() is None
    assert db.execute(
        "SELECT 1 FROM games WHERE game_id = ?", (_DEFECT_A_CANONICAL_ID,)
    ).fetchone() is not None


# ---------------------------------------------------------------------------
# E-261-03a: Tolerant cross-perspective same-game signal + uniform guard
# ---------------------------------------------------------------------------

_OPP_NAME = _OPP_TEAM_UUID  # the opponent team's teams.name (identifier fallback)
_CANON_X = "opp-event-X"  # canonical cross-perspective row (opponent-loaded)


def _seed_canonical_row(
    db: sqlite3.Connection,
    loader: GameLoader,
    *,
    game_id: str,
    home_score: int | None,
    away_score: int | None,
    perspectives: tuple[str, ...],
    start_time: str | None = None,
) -> tuple[int, int]:
    """Seed one canonical ``games`` row + its ``game_perspectives`` rows directly.

    ``perspectives`` entries are ``"own"`` (own team) or ``"opp"`` (opponent).
    The opponent team is resolved through the SAME ``_ensure_team_row`` cascade
    the payload load will use (the TN-2 resolution trap -- see the Defect A test),
    so a subsequent ``load_payload`` matches this exact opponent id. Own team is
    HOME (matching ``_make_summary(home_away='home')``). Returns (team_a, team_b).
    """
    team_a = loader._team_ref.id
    team_b = loader._ensure_team_row(_OPP_TEAM_UUID)
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, home_score, away_score, status, game_stream_id, start_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)",
        (game_id, loader._season_id, _GAME_DATE, team_a, team_b,
         home_score, away_score, game_id, start_time),
    )
    for who in perspectives:
        pid = team_a if who == "own" else team_b
        db.execute(
            "INSERT INTO game_perspectives (game_id, perspective_team_id) "
            "VALUES (?, ?)",
            (game_id, pid),
        )
    db.commit()
    return team_a, team_b


def test_tolerant_signal_redirects_on_score_disagreement(
    db: sqlite3.Connection,
) -> None:
    """AC-1: with schedule-count == 1 and a single cross-perspective candidate,
    a one-run score disagreement (12-4 canonical vs incoming 12-5) still
    redirects to the canonical id and records the redirect in ``redirect_map``.

    This is Defect B (observed 12-4 vs 12-5, confirmed same game by identical
    18-batter lineup). The tolerant guard fires because the OWN schedule shows
    exactly one game vs this opponent on this date.
    """
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=12, away_score=4, perspectives=("opp",),
    )
    # Own crawl schedule: exactly ONE game vs this opponent on this date.
    loader._schedule_counts = {(_GAME_DATE, _OPP_NAME): 1}

    summary = _make_summary(
        event_id="own-new-E", game_stream_id="own-new-E",
        owning_score=12, opponent_score=5,  # own is HOME -> 12-5
    )
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    assert result.errors == 0
    assert loader.redirect_map.get("own-new-E") == _CANON_X
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    # AC-4 score ownership: cross-perspective redirect keeps canonical 12-4.
    assert db.execute(
        "SELECT home_score, away_score FROM games WHERE game_id = ?", (_CANON_X,)
    ).fetchone() == (12, 4)


def test_tolerant_signal_warns_on_score_disagreement(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-4: when the tolerant signal fires on disagreeing scores, a WARNING log
    records both scorelines and both game ids (operator data-quality trace)."""
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=12, away_score=4, perspectives=("opp",),
    )
    loader._schedule_counts = {(_GAME_DATE, _OPP_NAME): 1}
    summary = _make_summary(
        event_id="own-new-E", game_stream_id="own-new-E",
        owning_score=12, opponent_score=5,
    )
    with caplog.at_level(
        logging.WARNING, logger="src.gamechanger.loaders.game_loader"
    ):
        loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    warns = [r for r in caplog.records if "Tolerant same-game dedup" in r.message]
    assert len(warns) == 1
    msg = warns[0].message
    assert warns[0].levelno == logging.WARNING
    assert "own-new-E" in msg and _CANON_X in msg  # both game ids
    assert "12-5" in msg and "12-4" in msg  # both scorelines


def test_same_perspective_reload_updates_scores(
    db: sqlite3.Connection,
) -> None:
    """AC-4 (other direction): a SAME-perspective reload still UPDATES scores --
    the scorekeeper-correction path is preserved, not suppressed by the redirect
    score-ownership gate (which only pins CROSS-perspective redirects)."""
    loader = _make_loader(db)
    # First own-perspective load: 5-2 with a start_time.
    _load_first_game(
        db, loader, start_time="2025-05-10T14:00:00.000Z",
        owning_score=5, opponent_score=2,
    )
    # Corrected re-scout: same own perspective, SAME start_time (forces the
    # same-perspective redirect via the start_time tiebreaker), corrected 6-2.
    summary2 = _make_summary(
        event_id=_EVENT_ID_2, game_stream_id=_STREAM_ID_2,
        start_time="2025-05-10T14:00:00.000Z",
        owning_score=6, opponent_score=2,
    )
    loader.load_payload(_make_boxscore(), summary2)

    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    # Same-perspective reload updated the canonical scores to the correction.
    assert db.execute(
        "SELECT home_score, away_score FROM games WHERE game_id = ?", (_EVENT_ID_1,)
    ).fetchone() == (6, 2)


def test_uniform_guard_prevents_reduplication_post_merge(
    db: sqlite3.Connection,
) -> None:
    """AC-3: a canonical row already carrying BOTH perspectives (the post-merge
    state) does not re-accumulate a duplicate on a same-perspective reload, even
    when the reload's scores DISAGREE (so the legacy same-perspective score/
    start_time tiebreaker would NOT dedup). The schedule-count guard is applied
    perspective-agnostically across the whole candidate loop, not only the
    cross-perspective sub-branch, so it catches this."""
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("own", "opp"),
    )
    loader._schedule_counts = {(_GAME_DATE, _OPP_NAME): 1}

    # Same (own) perspective reload of the source event, DISAGREEING score (5-3,
    # total 8 vs canonical total 7), NO start_time -> the same-perspective branch
    # would fail to dedup and insert a duplicate without the uniform guard.
    summary = _make_summary(
        event_id="own-source-E", game_stream_id="own-source-E",
        owning_score=5, opponent_score=3, start_time=None,
    )
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    assert result.errors == 0
    assert loader.redirect_map.get("own-source-E") == _CANON_X
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_cross_perspective_doubleheader_not_collapsed(
    db: sqlite3.Connection,
) -> None:
    """AC-2: the DB already holds BOTH opponent-perspective rows of a real
    doubleheader; when the own perspective loads its two games (incoming
    schedule-count == 2), the tolerant guard NEVER fires and TWO rows remain --
    each own game deduping to its correct twin via exact-score matching."""
    loader = _make_loader(db)
    # Two opponent-perspective doubleheader rows: distinct scores + start_times.
    _seed_canonical_row(
        db, loader, game_id="opp-game-1",
        home_score=5, away_score=2, perspectives=("opp",),
        start_time="2025-05-10T14:00:00.000Z",
    )
    _seed_canonical_row(
        db, loader, game_id="opp-game-2",
        home_score=3, away_score=1, perspectives=("opp",),
        start_time="2025-05-10T18:00:00.000Z",
    )
    # Own schedule sees TWO games vs this opponent on this date (a doubleheader).
    loader._schedule_counts = {(_GAME_DATE, _OPP_NAME): 2}

    # Own loads game 1 (5-2 @ 14:00) then game 2 (3-1 @ 18:00).
    loader.load_payload(
        _make_boxscore(),
        _make_summary(
            event_id="own-game-1", game_stream_id="own-game-1",
            owning_score=5, opponent_score=2,
            start_time="2025-05-10T14:00:00.000Z",
        ),
        opponent_name=_OPP_NAME,
    )
    loader.load_payload(
        _make_boxscore(),
        _make_summary(
            event_id="own-game-2", game_stream_id="own-game-2",
            owning_score=3, opponent_score=1,
            start_time="2025-05-10T18:00:00.000Z",
        ),
        opponent_name=_OPP_NAME,
    )

    # Still exactly two games -- the doubleheader was never collapsed.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2
    assert loader.redirect_map.get("own-game-1") == "opp-game-1"
    assert loader.redirect_map.get("own-game-2") == "opp-game-2"


def test_tolerant_signal_declines_on_missing_opponent_name(
    db: sqlite3.Connection,
) -> None:
    """AC-6: fail-safe. Even with a matching schedule-count entry present, a
    None ``opponent_name`` leaves the count unresolved, so the tolerant signal
    DECLINES and the loader falls back to exact-score match -- a disagreeing
    cross-perspective pair is NOT merged (two rows), never merged on missing
    context."""
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=12, away_score=4, perspectives=("opp",),
    )
    loader._schedule_counts = {(_GAME_DATE, _OPP_NAME): 1}

    summary = _make_summary(
        event_id="own-new-E", game_stream_id="own-new-E",
        owning_score=12, opponent_score=5,
    )
    # opponent_name=None -> incoming_schedule_count stays None -> decline.
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=None)

    assert result.errors == 0
    assert loader.redirect_map == {}  # no redirect fired
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


# ---------------------------------------------------------------------------
# E-261-03b: In-pipeline twin merge + redirect-site error handling
# ---------------------------------------------------------------------------

_TWIN_E = "own-event-E"  # a persisted own-perspective twin of the canonical row


def test_twin_merge_repoints_child_rows(
    db: sqlite3.Connection,
) -> None:
    """AC-1: the persisted twin's child rows are re-pointed onto the canonical
    row by the in-pipeline merge. Uses a ``plays`` row (which the boxscore load
    never recreates) to prove re-pointing rather than a coincidental re-upsert."""
    _apply_migration_010(db)
    loader = _make_loader(db)
    team_a, team_b = _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("opp",),
    )
    _seed_canonical_row(
        db, loader, game_id=_TWIN_E,
        home_score=5, away_score=2, perspectives=("own",),
    )
    # Seed a play on the twin (own perspective) with a player the boxscore lacks.
    db.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, ?, ?)",
        ("plays-only-batter", "Plays", "Only"),
    )
    db.execute(
        "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
        "batting_team_id, perspective_team_id, batter_id) "
        "VALUES (?, 1, 1, 'top', ?, ?, ?, ?)",
        (_TWIN_E, loader._season_id, team_a, team_a, "plays-only-batter"),
    )
    db.commit()

    summary = _make_summary(
        event_id=_TWIN_E, game_stream_id=_TWIN_E,
        owning_score=5, opponent_score=2,
    )
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    assert result.errors == 0
    # One surviving row, and the play re-pointed onto the canonical id.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.execute(
        "SELECT game_id FROM plays WHERE batter_id = 'plays-only-batter'"
    ).fetchone()[0] == _CANON_X
    assert db.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = ?", (_TWIN_E,)
    ).fetchone()[0] == 0


def test_twin_merge_refusal_leaves_both_rows_and_loads(
    db: sqlite3.Connection, caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-2: when the merge helper REFUSES a non-disjoint pair (both rows carry
    the SAME perspective), the loader does not guess -- it logs a WARNING, leaves
    both rows intact, and still loads the game under the canonical id (errors=0)."""
    loader = _make_loader(db)
    # Both rows carry the OWN perspective -> not a disjoint twin -> merge refuses.
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("own",),
    )
    _seed_canonical_row(
        db, loader, game_id=_TWIN_E,
        home_score=5, away_score=2, perspectives=("own",),
    )

    summary = _make_summary(
        event_id=_TWIN_E, game_stream_id=_TWIN_E,
        owning_score=5, opponent_score=2,
    )
    with caplog.at_level(
        logging.WARNING, logger="src.gamechanger.loaders.game_loader"
    ):
        result = loader.load_payload(
            _make_boxscore(), summary, opponent_name=_OPP_NAME
        )

    assert result.errors == 0
    # Both rows survive -- the refusal left them intact.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2
    refusals = [r for r in caplog.records if "REFUSED" in r.message]
    assert len(refusals) == 1 and refusals[0].levelno == logging.WARNING
    assert _TWIN_E in refusals[0].message and _CANON_X in refusals[0].message


def test_twin_merge_error_rolls_back_and_returns_errors(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3: a ``sqlite3.Error`` raised mid-merge is caught -- the loader rolls
    back the partial merge writes (so they cannot bleed into the next game's
    commit) and returns ``LoadResult(errors=1)`` rather than propagating."""
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("opp",),
    )
    _seed_canonical_row(
        db, loader, game_id=_TWIN_E,
        home_score=5, away_score=2, perspectives=("own",),
    )

    import src.gamechanger.loaders.game_loader as gl

    def _partial_then_raise(conn, source_game_id, canonical_game_id):
        # A REAL partial write, then a mid-merge failure. If the loader does not
        # roll back, this DELETE would ride the next per-game commit (the
        # shared-connection partial-commit footgun AC-3 guards against).
        conn.execute(
            "DELETE FROM game_perspectives WHERE game_id = ?",
            (canonical_game_id,),
        )
        raise sqlite3.OperationalError("simulated mid-merge failure")

    monkeypatch.setattr(gl, "merge_duplicate_game", _partial_then_raise)

    summary = _make_summary(
        event_id=_TWIN_E, game_stream_id=_TWIN_E,
        owning_score=5, opponent_score=2,
    )
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    assert result.errors == 1
    # The partial DELETE was rolled back: canonical X keeps its opp perspective.
    assert db.execute(
        "SELECT COUNT(*) FROM game_perspectives WHERE game_id = ?", (_CANON_X,)
    ).fetchone()[0] == 1
    # Nothing merged/deleted -- both game rows remain.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


def test_twin_merge_idempotent_on_reload(
    db: sqlite3.Connection,
) -> None:
    """AC-5: loading the same payload twice on a (now healed) DB produces no
    further merges, no errors, and no new rows -- exercising the real twin merge
    on the first load and E-261-03a's uniform candidate-loop guard on the second
    (source event row is gone, canonical carries both perspectives)."""
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("opp",),
    )
    _seed_canonical_row(
        db, loader, game_id=_TWIN_E,
        home_score=5, away_score=2, perspectives=("own",),
    )
    loader._schedule_counts = {(_GAME_DATE, _OPP_NAME): 1}

    def _load() -> "object":
        return loader.load_payload(
            _make_boxscore(),
            _make_summary(
                event_id=_TWIN_E, game_stream_id=_TWIN_E,
                owning_score=5, opponent_score=2,
            ),
            opponent_name=_OPP_NAME,
        )

    # First load: merges twin E into canonical X -> one surviving row.
    r1 = _load()
    assert r1.errors == 0
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1

    # Second load: E row is gone; the uniform guard redirects to X; no re-merge,
    # no new row, no error (idempotent).
    r2 = _load()
    assert r2.errors == 0
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.execute(
        "SELECT 1 FROM games WHERE game_id = ?", (_CANON_X,)
    ).fetchone() is not None


def test_ambiguous_date_undercount_does_not_collapse_doubleheader(
    db: sqlite3.Connection,
) -> None:
    """Codex P1 regression (producer -> loader integration): a real doubleheader
    vs the opponent on this date where ONE sibling summary lost its opponent name
    must NOT collapse the OTHER sibling into a lone cross-perspective candidate.

    Drives the REAL ``_build_schedule_counts`` producer (not a hand-set count) so
    the test catches a producer regression: the fixed producer emits NO count for
    the ambiguous date, the surviving sibling's lookup misses, and the tolerant
    guard declines -- two rows survive. Were the producer to undercount to 1
    (the fail-open bug), the guard would fire and collapse the doubleheader.
    """
    loader = _make_loader(db)
    # A single cross-perspective candidate (game A of the doubleheader) in the DB.
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("opp",),
    )

    # Own schedule: a doubleheader vs the opponent on _GAME_DATE, but sibling B
    # lost its opponent name. Both summaries derive to the same local date.
    summary_a = _make_summary(
        event_id="own-game-A", game_stream_id="own-game-A",
        owning_score=5, opponent_score=3,  # DISAGREES with candidate X (5-2)
    )
    summary_b = _make_summary(
        event_id="own-game-B", game_stream_id="own-game-B",
        owning_score=8, opponent_score=1,
    )
    games_index = {"own-game-A": summary_a, "own-game-B": summary_b}
    opponent_name_index = {"own-game-A": _OPP_NAME}  # own-game-B name missing

    # Build the count via the REAL producer (lives on ScoutingLoader), then feed
    # its output to the GameLoader -- so this catches a producer-side regression.
    loader._schedule_counts = ScoutingLoader(db)._build_schedule_counts(
        games_index, opponent_name_index
    )
    # Producer failed CLOSED: the ambiguous date emits no count at all.
    assert loader._schedule_counts == {}

    # Loading the resolved sibling A: count lookup misses -> guard declines ->
    # the disagreeing-score cross-perspective candidate is NOT collapsed.
    result = loader.load_payload(
        _make_boxscore(), summary_a, opponent_name=_OPP_NAME
    )

    assert result.errors == 0
    assert loader.redirect_map == {}  # declined -- no collapse
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


def test_twin_merge_source_vanished_race_is_benign_no_op(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex P2 regression: a read-then-write TOCTOU where another writer deletes
    the source twin BETWEEN the ``_game_row_exists`` check and the merge makes
    ``merge_duplicate_game`` raise ``GameMergeError`` (source not found). That is a
    BENIGN race -- the twin is already gone (the healed end-state) -- and must NOT
    abort the load: it resolves as a no-op, loading under the canonical id."""
    _apply_migration_010(db)
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("opp",),
    )
    _seed_canonical_row(
        db, loader, game_id=_TWIN_E,
        home_score=5, away_score=2, perspectives=("own",),
    )

    import src.gamechanger.loaders.game_loader as gl

    def _delete_source_then_raise(conn, source_game_id, canonical_game_id):
        # Simulate a concurrent writer having deleted the source twin: the row is
        # gone from our connection's view, and the real helper's pre-write
        # validation would raise "source not found".
        conn.execute(
            "DELETE FROM game_perspectives WHERE game_id = ?", (source_game_id,)
        )
        conn.execute("DELETE FROM games WHERE game_id = ?", (source_game_id,))
        raise GameMergeError(f"Source game {source_game_id!r} not found")

    monkeypatch.setattr(gl, "merge_duplicate_game", _delete_source_then_raise)

    summary = _make_summary(
        event_id=_TWIN_E, game_stream_id=_TWIN_E,
        owning_score=5, opponent_score=2,
    )
    # Must NOT raise uncaught -- resolves as a benign no-op under the canonical id.
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    assert result.errors == 0
    assert loader.redirect_map.get(_TWIN_E) == _CANON_X
    # The twin is gone (already collapsed by the "concurrent" writer); the
    # canonical row survives -- the healed one-row end-state.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.execute(
        "SELECT 1 FROM games WHERE game_id = ?", (_CANON_X,)
    ).fetchone() is not None
    assert db.execute(
        "SELECT 1 FROM games WHERE game_id = ?", (_TWIN_E,)
    ).fetchone() is None


def test_twin_merge_unexpected_game_merge_error_fails_game_not_load(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex P2 (other branch): a ``GameMergeError`` while the source row is STILL
    present is NOT the benign vanished-source race -- it is not silently swallowed.
    The loader rolls back and fails THIS game (errors=1), leaving both rows intact,
    rather than letting the exception abort the whole load."""
    loader = _make_loader(db)
    _seed_canonical_row(
        db, loader, game_id=_CANON_X,
        home_score=5, away_score=2, perspectives=("opp",),
    )
    _seed_canonical_row(
        db, loader, game_id=_TWIN_E,
        home_score=5, away_score=2, perspectives=("own",),
    )

    import src.gamechanger.loaders.game_loader as gl

    def _raise_without_delete(conn, source_game_id, canonical_game_id):
        raise GameMergeError("simulated unexpected merge error")

    monkeypatch.setattr(gl, "merge_duplicate_game", _raise_without_delete)

    summary = _make_summary(
        event_id=_TWIN_E, game_stream_id=_TWIN_E,
        owning_score=5, opponent_score=2,
    )
    # Must NOT raise uncaught -- surfaces as a per-game failure.
    result = loader.load_payload(_make_boxscore(), summary, opponent_name=_OPP_NAME)

    assert result.errors == 1
    # Source still present -> nothing merged/deleted; both rows remain.
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 2


# ---------------------------------------------------------------------------
# E-268-01: orientation-tuple atomicity under a cross-perspective redirect (CC-2)
# ---------------------------------------------------------------------------


def test_cc2_redirect_preserves_orientation_tuple_and_reports(
    db: sqlite3.Connection,
) -> None:
    """E-268-01 AC-3 (HARD regression, TN-2): the CROSS-perspective redirect
    must write the four-field orientation tuple ``{home_team_id, away_team_id,
    home_score, away_score}`` ATOMICALLY.

    Repro (both validators' recipe): team A's scout loads the canonical row
    A-home 5-3; then team B's scout re-loads the SAME real game with its own
    ``home_away`` MISSING (None) -- so ``_resolve_home_away`` defaults B (own)
    to home, producing the FLIPPED incoming orientation B-home 3-5. The tolerant
    schedule-count signal (own count == 1, single candidate) fires the redirect
    with ``preserve_scores=True``.

    Pre-fix, ``_upsert_game`` froze the scores (keep-existing) but overwrote the
    two team-ids UNCONDITIONALLY from ``excluded.*`` -- a TORN write: the canonical
    5-3 scores were re-attributed to the now-swapped team-ids, so the surviving
    row read B-home 5-3. That silently re-credited A's 5-run WIN to B on BOTH
    perspectives' reports. Post-fix, the team-ids are gated on ``preserve_scores``
    exactly as the scores are, so the whole tuple keeps-existing: the row stays
    A-home 5-3.

    Asserts the surviving orientation AND that none of the three affected report
    reads -- ``_query_record`` (W-L), ``_query_runs_avg`` (runs for/against), and
    ``_query_recent_games`` (recent form) -- is mis-credited, for BOTH team A and
    team B (the epic states both reports are corrupted). Reverting the
    ``_upsert_game`` team-id gating makes every post-fix assertion below fail.
    """
    # --- Team A's scout seeds the canonical row: A-home 5-3 (own perspective). ---
    loader_a = _make_loader(db)
    team_a_id = loader_a._team_ref.id
    _load_first_game(db, loader_a, owning_score=5, opponent_score=3)

    # The opponent (team B) was created by the first load; resolve its id.
    team_b_id = db.execute(
        "SELECT id FROM teams WHERE name = ? AND membership_type = 'tracked'",
        (_OPP_TEAM_UUID,),
    ).fetchone()[0]
    season_id = loader_a._season_id

    # Sanity: the canonical row is A-home 5-3, single perspective = team A.
    assert db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score "
        "FROM games WHERE game_id = ?",
        (_EVENT_ID_1,),
    ).fetchone() == (team_a_id, team_b_id, 5, 3)

    # --- Team B's scout re-loads the SAME game with home_away MISSING. ---
    loader_b = GameLoader(
        db,
        owned_team_ref=TeamRef(
            id=team_b_id, gc_uuid=_OPP_TEAM_UUID, public_id=None
        ),
    )
    # B resolves its opponent (team A) BY NAME to team A's existing row -- the
    # TN-2 resolution trap: a mismatch would silently skip the natural-key dedup.
    assert (
        loader_b._ensure_team_row(_OWN_TEAM_UUID, opponent_name=_OWN_TEAM_UUID)
        == team_a_id
    )
    # Own crawl schedule: exactly ONE game vs this opponent (team A) on this date
    # -- the tolerant same-game signal that fires the redirect across the flipped
    # orientation (the positional exact-score branch does NOT match a flip).
    loader_b._schedule_counts = {(_GAME_DATE, _OWN_TEAM_UUID): 1}

    # B's summary: home_away=None -> own (B) defaults home; from B's perspective
    # owning_score is B's runs (3) and opponent_score is A's runs (5).
    summary_b = _make_summary(
        event_id=_EVENT_ID_2,
        game_stream_id=_STREAM_ID_2,
        home_away=None,
        owning_score=3,
        opponent_score=5,
    )
    result = loader_b.load_payload(
        _make_boxscore(), summary_b, opponent_name=_OWN_TEAM_UUID
    )

    assert result.errors == 0
    # The redirect fired: B's event id -> A's canonical id, one surviving row.
    assert loader_b.redirect_map.get(_EVENT_ID_2) == _EVENT_ID_1
    assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1

    # AC-1/AC-3: the orientation tuple is preserved atomically -- A stays HOME
    # with 5-3 (pre-fix this read (team_b_id, team_a_id, 5, 3) -> B-home 5-3).
    assert db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score "
        "FROM games WHERE game_id = ?",
        (_EVENT_ID_1,),
    ).fetchone() == (team_a_id, team_b_id, 5, 3)

    # --- Reports must credit the right team on BOTH perspectives (AC-3). ---
    # Team A (won 5-3): record W, runs 5 for / 3 against, recent form W.
    assert _query_record(db, team_a_id, season_id) == {
        "wins": 1, "losses": 0, "ties": 0,
    }  # E-278-01 widened this contract with a "ties" key
    assert _query_runs_avg(db, team_a_id, season_id) == (5.0, 3.0)
    recent_a = _query_recent_games(db, team_a_id, season_id)
    assert len(recent_a) == 1
    assert recent_a[0]["result"] == "W"
    assert (recent_a[0]["our_score"], recent_a[0]["their_score"]) == (5, 3)
    assert recent_a[0]["is_home"] is True

    # Team B (lost 3-5): record L, runs 3 for / 5 against, recent form L.
    assert _query_record(db, team_b_id, season_id) == {
        "wins": 0, "losses": 1, "ties": 0,
    }
    assert _query_runs_avg(db, team_b_id, season_id) == (3.0, 5.0)
    recent_b = _query_recent_games(db, team_b_id, season_id)
    assert len(recent_b) == 1
    assert recent_b[0]["result"] == "L"
    assert (recent_b[0]["our_score"], recent_b[0]["their_score"]) == (3, 5)
    assert recent_b[0]["is_home"] is False


def test_upsert_game_preserve_scores_keeps_orientation_tuple(
    db: sqlite3.Connection,
) -> None:
    """E-268-01 AC-1 (unit): with ``preserve_scores=True`` on an ON CONFLICT
    update, ALL FOUR orientation fields keep-existing -- even when the incoming
    row flips the team-ids AND changes both scores. Pins the team-id gating at
    the SQL level (the integration test above proves the end-to-end path)."""
    loader = _make_loader(db)
    team_a_id = loader._team_ref.id
    team_b_id = loader._ensure_team_row(_OPP_TEAM_UUID)
    game_id = "g-preserve-unit"

    # First insert: canonical A-home 5-3 (preserve_scores irrelevant on insert).
    loader._upsert_game(
        game_id, _GAME_DATE, team_a_id, team_b_id, 5, 3, game_id,
        preserve_scores=False,
    )
    # Cross-perspective redirect reload: FLIPPED orientation + different scores.
    loader._upsert_game(
        game_id, _GAME_DATE, team_b_id, team_a_id, 9, 1, "g-preserve-unit-2",
        preserve_scores=True,
    )

    # All four fields kept-existing: the flip and the 9-1 scores are ignored.
    assert db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score "
        "FROM games WHERE game_id = ?",
        (game_id,),
    ).fetchone() == (team_a_id, team_b_id, 5, 3)


def test_upsert_game_correction_path_takes_incoming_orientation(
    db: sqlite3.Connection,
) -> None:
    """E-268-01 AC-2 / AC-4 (GAP-5 over-gating guard): with
    ``preserve_scores=False`` (a first insert OR a same-perspective reload) ALL
    FOUR orientation fields TAKE the incoming values. Guards against over-gating
    the fix to ALWAYS keep-existing, which would pass AC-3 while silently
    breaking the same-perspective scorekeeper-correction path (AC-2)."""
    loader = _make_loader(db)
    team_a_id = loader._team_ref.id
    team_b_id = loader._ensure_team_row(_OPP_TEAM_UUID)
    game_id = "g-correction-unit"

    # First insert (no conflict): takes incoming A-home 5-3.
    loader._upsert_game(
        game_id, _GAME_DATE, team_a_id, team_b_id, 5, 3, game_id,
        preserve_scores=False,
    )
    assert db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score "
        "FROM games WHERE game_id = ?",
        (game_id,),
    ).fetchone() == (team_a_id, team_b_id, 5, 3)

    # Same-perspective reload (preserve_scores=False): a correction that flips
    # the orientation AND rewrites the scores -- ALL FOUR take the incoming values
    # (this would stay 5-3 / A-home if the fix over-gated to always keep-existing).
    loader._upsert_game(
        game_id, _GAME_DATE, team_b_id, team_a_id, 7, 2, "g-correction-unit-2",
        preserve_scores=False,
    )
    assert db.execute(
        "SELECT home_team_id, away_team_id, home_score, away_score "
        "FROM games WHERE game_id = ?",
        (game_id,),
    ).fetchone() == (team_b_id, team_a_id, 7, 2)


# ---------------------------------------------------------------------------
# E-278-02: same-perspective double-listing collapsed at load
# ---------------------------------------------------------------------------
#
# Fixture values are transcribed from the story's "Fixture specification"
# table (AC-7), which is the durable in-repo source. NO live API call and NO
# live DB query -- a dispatch worktree can reach neither, which is exactly why
# the table exists. Identifiers are invented per epic TN-10; the real team
# name, public_id and GC UUIDs must never appear here.
#
# ⚠️ ANTI-VACUITY, and it is a live hazard rather than a formality. Since
# E-278-04, `_find_duplicate_game` is NOT CALLED AT ALL when the derived
# `game_date` is the `1900-01-01` sentinel -- which is what an omitted
# `start_time`/`date_source_instant` or an unresolvable `timezone` now
# produces. A fixture with either defect would sail through every assertion
# below while exercising nothing, and would look exactly like a passing test.
# So every fixture here carries a real instant, and each test asserts the
# stored `game_date` is a real date rather than the sentinel. That claim
# was FALSE for three of these tests when first written -- the two
# "stays two rows" tests were the exposed pair, since a sentinel fixture
# makes them pass for the wrong reason -- so the assertions were added
# rather than the sentence softened.

_SENTINEL_DATE = "1900-01-01"

# Story Fixture specification, listings 1 and 2. The 0.96-second delta is the
# whole point; `end_ts` has no games column and is deliberately not modelled --
# constraint 4 measured it as a NON-discriminator (two hours apart on the real
# pair), so nothing here may key on it.
_DL_DATE = "2026-07-25"
_DL_START_1 = "2026-07-25T21:00:00.000Z"
_DL_START_2 = "2026-07-25T21:00:00.960Z"


def _load_listing(
    loader: GameLoader,
    *,
    event_id: str,
    stream_id: str,
    start_time: str,
    owning_score: int,
    opponent_score: int,
    game_date: str = _DL_DATE,
    date_source_instant: str | None = None,
) -> None:
    """Load one schedule listing through the real load path."""
    loader.load_payload(
        _make_boxscore(),
        _make_summary(
            event_id=event_id,
            game_stream_id=stream_id,
            owning_score=owning_score,
            opponent_score=opponent_score,
            start_time=start_time,
            game_date=game_date,
            date_source_instant=date_source_instant,
        ),
    )


def _stored_dates(db: sqlite3.Connection) -> list[str]:
    return [
        r[0] for r in db.execute(
            "SELECT game_date FROM games ORDER BY game_id"
        ).fetchall()
    ]


def test_same_perspective_double_listing_collapses_to_one_row(
    db: sqlite3.Connection,
) -> None:
    """AC-1: one real game listed twice, 0.96s apart, identical scores.

    Both listings share a perspective, so before this story the byte-equality
    tiebreaker found their start times unequal and filed them as a doubleheader.
    """
    loader = _make_loader(db)
    _load_listing(loader, event_id=_EVENT_ID_1, stream_id=_STREAM_ID_1,
                  start_time=_DL_START_1, owning_score=0, opponent_score=3)
    _load_listing(loader, event_id=_EVENT_ID_2, stream_id=_STREAM_ID_2,
                  start_time=_DL_START_2, owning_score=0, opponent_score=3)
    db.commit()

    dates = _stored_dates(db)
    assert len(dates) == 1, f"expected one collapsed row, got {dates}"
    # Anti-vacuity: a sentinel date would mean _find_duplicate_game was never
    # reached and this test proved nothing.
    # `_DL_DATE != _SENTINEL_DATE` used to be chained here and compared two
    # module constants -- unconditionally true, and it READ as the guard.
    # The real guard is that the STORED date is the fixture's date.
    assert dates[0] == _DL_DATE


def test_collapsed_pair_has_no_duplicated_stat_rows(
    db: sqlite3.Connection,
) -> None:
    """AC-10: the safety-relevant half of the double-count harm.

    A double-counted pitching appearance inflates pitch count, innings pitched
    and appearance order -- the inputs to rest-day compliance and the Most
    Likely Arms predictor. Asserting the `games`-row count alone does NOT cover
    this, which is why it is a separate criterion.
    """
    loader = _make_loader(db)
    _load_listing(loader, event_id=_EVENT_ID_1, stream_id=_STREAM_ID_1,
                  start_time=_DL_START_1, owning_score=0, opponent_score=3)
    _load_listing(loader, event_id=_EVENT_ID_2, stream_id=_STREAM_ID_2,
                  start_time=_DL_START_2, owning_score=0, opponent_score=3)
    db.commit()

    # ⚠️ THIS ASSERTION IS LOAD-BEARING AND WAS MISSING. Without it the test
    # passed against the UNFIXED codebase: `SELECT game_id ... fetchone()`
    # returns one of the two rows, and without a redirect the second listing
    # writes its stats under its OWN game_id -- so "one stat row per player
    # under this game_id" holds in the duplicated world too. The criterion that
    # actually matters (no double-counted pitching appearance) is only tested
    # once we know exactly one row survived.
    game_ids = [r[0] for r in db.execute("SELECT game_id FROM games").fetchall()]
    assert len(game_ids) == 1, f"expected one collapsed row, got {game_ids}"
    game_id = game_ids[0]
    assert _stored_dates(db) == [_DL_DATE]  # anti-vacuity: not the sentinel

    for table in ("player_game_batting", "player_game_pitching"):
        rows = db.execute(
            f"SELECT player_id, COUNT(*) FROM {table} "  # noqa: S608 -- fixed literals
            "WHERE game_id = ? GROUP BY player_id",
            (game_id,),
        ).fetchall()
        assert rows, f"{table} should carry the surviving game's lines"
        assert all(count == 1 for _, count in rows), (
            f"{table} carries a duplicated line under {game_id}: {rows}"
        )


def test_genuine_doubleheader_with_differing_scores_stays_two_rows(
    db: sqlite3.Connection,
) -> None:
    """AC-2: the FRESH-1..6 shape -- 7200s apart, scores differ on every pair.

    The predicate is exact score INEQUALITY, deliberately not expressed via
    `_SCORE_TOLERANCE_RUNS`: that constant governs the OFFLINE repair predicate
    and importing it here would couple the load path to a threshold AC-6 may
    change on the other surface.
    """
    loader = _make_loader(db)
    _load_listing(loader, event_id=_EVENT_ID_1, stream_id=_STREAM_ID_1,
                  start_time="2026-07-25T17:00:00.000Z",
                  owning_score=5, opponent_score=2)
    _load_listing(loader, event_id=_EVENT_ID_2, stream_id=_STREAM_ID_2,
                  start_time="2026-07-25T19:00:00.000Z",   # +7200s
                  owning_score=3, opponent_score=4)
    db.commit()

    dates = _stored_dates(db)
    assert len(dates) == 2, f"genuine doubleheader must stay two rows, got {dates}"
    assert dates == [_DL_DATE, _DL_DATE]  # anti-vacuity: neither is the sentinel


def test_agreeing_scores_far_apart_stay_two_rows(
    db: sqlite3.Connection,
) -> None:
    """The narrowing condition is load-bearing, not decoration.

    Two genuine doubleheader games CAN share a scoreline, so score agreement
    alone must not collapse anything. Without the sub-second bound this pair
    would merge -- which is the destructive direction.
    """
    loader = _make_loader(db)
    _load_listing(loader, event_id=_EVENT_ID_1, stream_id=_STREAM_ID_1,
                  start_time="2026-07-25T17:00:00.000Z",
                  owning_score=0, opponent_score=3)
    _load_listing(loader, event_id=_EVENT_ID_2, stream_id=_STREAM_ID_2,
                  start_time="2026-07-25T19:00:00.000Z",   # +7200s, same score
                  owning_score=0, opponent_score=3)
    db.commit()

    dates = _stored_dates(db)
    assert len(dates) == 2, (
        f"identical scores two hours apart are a doubleheader, not a "
        f"double-listing; got {dates}"
    )
    # Anti-vacuity, and this test is one of the EXPOSED ones: a fixture change
    # routing these to the sentinel makes _find_duplicate_game unreachable, two
    # rows persist for the wrong reason, and the assertion above still passes.
    assert dates == [_DL_DATE, _DL_DATE]


def test_sub_second_delta_with_differing_scores_stays_two_rows(
    db: sqlite3.Connection,
) -> None:
    """The trigger is load-bearing too: a near-zero delta alone must not merge.

    Score agreement TRIGGERS and the delta NARROWS; inverting that would make
    the delta the discriminator, which epic TN-5 forbids corpus-wide.
    """
    loader = _make_loader(db)
    _load_listing(loader, event_id=_EVENT_ID_1, stream_id=_STREAM_ID_1,
                  start_time=_DL_START_1, owning_score=0, opponent_score=3)
    _load_listing(loader, event_id=_EVENT_ID_2, stream_id=_STREAM_ID_2,
                  start_time=_DL_START_2, owning_score=7, opponent_score=1)
    db.commit()

    # Same exposure as the test above: two rows is the right OUTCOME, but only
    # a real date proves the dedup branch was actually reached to produce it.
    assert _stored_dates(db) == [_DL_DATE, _DL_DATE]


# ⚠️ EVENING instants, and they sit a calendar day AHEAD of the dates the test
# asserts. That is deliberate and must not be "corrected" back.
#
# 02:00Z is 21:00 the PREVIOUS evening in America/Chicago, so each instant's
# venue-local date is one day EARLIER than its own UTC slice:
#
#     2026-07-26T02:00:00.000Z -> local 2026-07-25, UTC slice 2026-07-26
#     2026-07-27T02:00:00.000Z -> local 2026-07-26, UTC slice 2026-07-27
#
# That gap is the whole point. The test previously used 19:39Z, where
# localization is a NO-OP (local date == UTC slice), so its assertion held
# identically under a regression to `date_source_instant[:10]` -- it could not
# detect the very derivation change its docstring says it guards.
_AC5_EVENING_INSTANT_DAY_1 = "2026-07-26T02:00:00.000Z"   # local 2026-07-25
_AC5_EVENING_INSTANT_DAY_2 = "2026-07-27T02:00:00.000Z"   # local 2026-07-26


def test_consecutive_day_listings_keep_distinct_dates(
    db: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-5, cross-story regression guard with a REACHABLE red.

    E-278-04 changed the derived `game_date`, which is the key
    `_find_duplicate_game` groups candidates by. An over-correcting derivation
    that collapsed a genuine consecutive-day pair onto one date would make them
    dedup candidates for the first time -- and this goes red there.

    The instants are EVENING ones so the guard is real in both directions: a
    UTC-slicing regression yields ["2026-07-26", "2026-07-27"] and fails here,
    and a collapse onto one date fails the length assertion. With the afternoon
    instants this test shipped with, only the second half could ever fire.
    """
    # The venue-local dates below depend on the operating tz; pin it so the
    # fixture cannot be silently re-interpreted by an ambient override.
    monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)
    loader = _make_loader(db)
    _load_listing(loader, event_id=_EVENT_ID_1, stream_id=_STREAM_ID_1,
                  start_time=_AC5_EVENING_INSTANT_DAY_1,
                  date_source_instant=_AC5_EVENING_INSTANT_DAY_1,
                  owning_score=0, opponent_score=3, game_date="2026-07-25")
    _load_listing(loader, event_id=_EVENT_ID_2, stream_id=_STREAM_ID_2,
                  start_time=_AC5_EVENING_INSTANT_DAY_2,
                  date_source_instant=_AC5_EVENING_INSTANT_DAY_2,
                  owning_score=0, opponent_score=3, game_date="2026-07-26")
    db.commit()

    dates = _stored_dates(db)
    assert len(dates) == 2
    assert sorted(dates) == ["2026-07-25", "2026-07-26"], (
        "consecutive-day listings must retain DIFFERENT game_date values"
    )


def test_delta_helper_never_raises_on_any_parseable_shape() -> None:
    """`_is_same_listing_delta` must fail closed for real, not just for its
    docstring.

    A bare date or a naive datetime PARSES cleanly, so it is neither absent nor
    unparseable and `_parse_instant`'s `except ValueError` never sees it --
    subtracting naive from aware then raised `TypeError`. There is no
    `try`/`except` between `_find_duplicate_game` and `ScoutingLoader`'s
    per-game loop, and `load_payload` commits per game, so that exception would
    have left earlier games committed and ABANDONED the rest of the team's
    scout: a silent partial crawl, not a wrong number.

    Unobserved on the wire (GC renders `...Z`) -- pinned anyway, because this
    epic exists because an unobserved shape in a GameChanger field is not a
    proven-impossible one.
    """
    aware = "2026-07-25T21:00:00.000Z"
    shapes = [
        None, "", "not-a-time",
        "2026-07-25",                 # bare date: parses, midnight, NAIVE
        "2026-07-25T21:00:00",        # naive datetime
        "2026-07-25T21:00:00.960Z",   # aware
        "2026-07-25T16:00:00.000-05:00",  # aware, non-UTC offset
    ]
    for a in shapes:
        for b in shapes:
            result = _is_same_listing_delta(a, b)  # must not raise
            assert isinstance(result, bool)

    # Naive input is read as UTC, mirroring `derive_local_date`, so a naive
    # instant 0.96s from an aware one is correctly INSIDE the window...
    assert _is_same_listing_delta("2026-07-25T21:00:00", aware.replace("00.000", "00.960")) is True
    # ...while a bare date really is hours away and is correctly outside it.
    # (False here is a computed answer, not a swallowed error.)
    assert _is_same_listing_delta("2026-07-25", aware) is False
