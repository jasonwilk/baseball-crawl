# synthetic-test-data
"""Tests for src/db/backfill_game_dates.py + the bb data backfill-game-dates CLI.

Exercises the 3-tier re-derivation (E-253-11): tier-1 (start_time + timezone),
tier-2 (start_time, timezone NULL -> operating-tz fallback), tier-3 (start_time
NULL -> untouched + counted), plus idempotency, dry-run, and the CLI exit-code
convention (AC-5).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.db.backfill_game_dates import backfill_game_dates
from tests.conftest import load_real_schema

runner = CliRunner()

# 2026-06-21T03:00Z == 2026-06-20 22:00 America/Chicago (CDT, UTC-5): the venue-
# local date (2026-06-20) differs from the raw UTC prefix (2026-06-21). The
# stored game_date below carries the OLD mis-derived UTC value.
_EVENING_UTC = "2026-06-21T03:00:00.000Z"
_UTC_DATE = "2026-06-21"       # the mis-derived stored value
_LOCAL_DATE = "2026-06-20"     # the corrected venue-local value


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.execute("INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)")
    conn.execute("INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB', 'member')")
    conn.execute("INSERT INTO teams (id, name, membership_type) VALUES (2, 'Opp', 'tracked')")
    yield conn
    conn.close()


def _seed_game(
    db: sqlite3.Connection,
    game_id: str,
    *,
    game_date: str,
    start_time: str | None,
    timezone: str | None,
) -> None:
    db.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, start_time, timezone) VALUES (?, '2026', ?, 1, 2, ?, ?)",
        (game_id, game_date, start_time, timezone),
    )
    db.commit()


def _game_date(db: sqlite3.Connection, game_id: str) -> str:
    return db.execute(
        "SELECT game_date FROM games WHERE game_id = ?", (game_id,)
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Unit tests: 3-tier re-derivation
# ---------------------------------------------------------------------------


def test_tier1_timezone_present_rederives_local_date(db: sqlite3.Connection) -> None:
    """AC-3 tier-1: start_time + timezone present -> venue-local re-derivation."""
    _seed_game(db, "g1", game_date=_UTC_DATE, start_time=_EVENING_UTC,
               timezone="America/Chicago")

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["rows_updated"] == 1
    assert _game_date(db, "g1") == _LOCAL_DATE


def test_tier2_timezone_null_uses_operating_default(db: sqlite3.Connection) -> None:
    """AC-3 tier-2: start_time present, timezone NULL -> operating-tz fallback
    (default America/Chicago) produces the operating-local date."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure no override so the default (America/Chicago) applies.
        import os
        os.environ.pop("OPERATING_TIMEZONE", None)
        _seed_game(db, "g2", game_date=_UTC_DATE, start_time=_EVENING_UTC,
                   timezone=None)

        summary = backfill_game_dates(db, dry_run=False)

    assert summary["rows_updated"] == 1
    assert _game_date(db, "g2") == _LOCAL_DATE


def test_tier2_honors_operating_timezone_override(db: sqlite3.Connection) -> None:
    """AC-3 tier-2: the fallback consults the seam, not a hard-coded default.
    04:30Z sits between NY midnight (04:00Z) and Chicago midnight (05:00Z), so
    under an America/New_York override the local date is 2026-06-21."""
    import os
    _seed_game(db, "g2ny", game_date="2026-06-20",
               start_time="2026-06-21T04:30:00.000Z", timezone=None)
    with patch.dict(os.environ, {"OPERATING_TIMEZONE": "America/New_York"}):
        summary = backfill_game_dates(db, dry_run=False)
    assert summary["rows_updated"] == 1
    assert _game_date(db, "g2ny") == "2026-06-21"


def test_tier3_null_start_time_untouched_and_counted(db: sqlite3.Connection) -> None:
    """AC-2 tier-3: start_time NULL -> game_date untouched, counted as skipped."""
    _seed_game(db, "g3", game_date="1900-01-01", start_time=None, timezone=None)

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["skipped_no_start_time"] == 1
    assert summary["rows_updated"] == 0
    assert _game_date(db, "g3") == "1900-01-01"  # untouched, not fabricated


def test_unparseable_start_time_untouched_and_counted(db: sqlite3.Connection) -> None:
    """A present-but-unparseable start_time cannot be corrected -> counted, kept."""
    _seed_game(db, "g4", game_date=_UTC_DATE, start_time="not-a-timestamp",
               timezone="America/Chicago")

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["skipped_unparseable"] == 1
    assert summary["rows_updated"] == 0
    assert _game_date(db, "g4") == _UTC_DATE


# ---------------------------------------------------------------------------
# E-278-04 AC-5a / AC-5b: the two classes the repair path refuses to guess at
# ---------------------------------------------------------------------------


def test_alias_row_is_rederived_to_the_correct_local_date(
    db: sqlite3.Connection,
) -> None:
    """AC-5a: a backfill over an alias row does not move it to a WRONG date.

    ``US/Central`` names the same zone as ``America/Chicago``. Before ``tzdata``
    was a declared dependency it raised ZoneInfoNotFoundError here, the shared
    converter fell through with the datetime still in UTC, and this row would
    have been "corrected" to the UTC date it already held -- the instrument
    reproducing the very bug it was measuring, and reporting agreement.

    Both spellings are asserted to land on the same venue-local date, and that
    date is asserted to differ from the stored UTC one, so a no-op cannot pass.
    """
    _seed_game(db, "alias", game_date=_UTC_DATE, start_time=_EVENING_UTC,
               timezone="US/Central")
    _seed_game(db, "canon", game_date=_UTC_DATE, start_time=_EVENING_UTC,
               timezone="America/Chicago")

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["rows_updated"] == 2
    assert summary["skipped_unresolvable_timezone"] == 0
    assert _game_date(db, "alias") == _game_date(db, "canon") == _LOCAL_DATE
    assert _LOCAL_DATE != _UTC_DATE  # AC-8: an evening instant, so this can fail


def test_unresolvable_timezone_row_is_left_alone_and_counted(
    db: sqlite3.Connection,
) -> None:
    """AC-5a: a zone this runtime cannot resolve yields no date, so no UPDATE.

    Counted under its OWN key rather than folded into ``skipped_unparseable``,
    whose name is a claim -- it would be asserting the start_time could not be
    parsed, which is false here.

    Note what is NOT done: the operating-tz default is not substituted. That
    would write an unverified zone's answer over a row that told us which zone
    it meant.
    """
    _seed_game(db, "badtz", game_date=_UTC_DATE, start_time=_EVENING_UTC,
               timezone="Not/AZone")

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["skipped_unresolvable_timezone"] == 1
    assert summary["skipped_unparseable"] == 0
    assert summary["rows_updated"] == 0
    assert _game_date(db, "badtz") == _UTC_DATE  # untouched


def test_midnight_utc_null_timezone_row_is_not_rederived(
    db: sqlite3.Connection,
) -> None:
    """AC-5b: the stored shape of an all-day event is left alone.

    ``games`` persists no full-day marker, so this row -- midnight-UTC
    start_time, NULL timezone -- is INDISTINGUISHABLE here from a genuine
    midnight-UTC start. Tier 2 would apply the operating zone to what may be a
    date MARKER and shift it back a day, re-committing the -1-day defect
    E-278-04 removed from the load path.

    The stored date below is the marker's own date. A tier-2 re-derivation would
    move it to 2026-05-30; the assertion is that it does not.
    """
    _seed_game(db, "fullday", game_date="2026-05-31",
               start_time="2026-05-31T00:00:00.000Z", timezone=None)

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["skipped_ambiguous_full_day"] == 1
    assert summary["rows_updated"] == 0
    assert _game_date(db, "fullday") == "2026-05-31"
    assert _game_date(db, "fullday") != "2026-05-30"


def test_guard_is_the_intersection_not_either_half(
    db: sqlite3.Connection,
) -> None:
    """AC-5b: the refusal is narrow, and both halves of the cut are load-bearing.

    Measured over a 928-row corpus, midnight-UTC ALONE selected 50 rows for 2
    real full-day events -- a 25x over-count, because a 7:00pm US Central start
    IS midnight UTC. The intersection with a NULL timezone selected exactly 2.

    So a midnight-UTC row that CARRIES a timezone is an ordinary evening game
    and must still be repaired, and a NULL-timezone row at a non-midnight
    instant is an unambiguous instant and must still be repaired. Only the
    intersection is refused. Without this test the guard could quietly widen to
    "skip every NULL timezone" or "skip every midnight UTC" and stay green.
    """
    # Midnight UTC, but a timezone is present -> a real 7pm Central start.
    _seed_game(db, "evening-central", game_date="2026-05-31",
               start_time="2026-05-31T00:00:00.000Z", timezone="America/Chicago")
    # NULL timezone, but not midnight UTC -> an unambiguous instant.
    _seed_game(db, "null-tz-timed", game_date=_UTC_DATE,
               start_time=_EVENING_UTC, timezone=None)

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["skipped_ambiguous_full_day"] == 0
    assert summary["rows_updated"] == 2
    assert _game_date(db, "evening-central") == "2026-05-30"
    assert _game_date(db, "null-tz-timed") == _LOCAL_DATE


def test_already_correct_row_is_unchanged(db: sqlite3.Connection) -> None:
    """A row already holding the venue-local date is a no-op (not counted as an
    update) -- the differ-only UPDATE guard."""
    _seed_game(db, "g5", game_date=_LOCAL_DATE, start_time=_EVENING_UTC,
               timezone="America/Chicago")

    summary = backfill_game_dates(db, dry_run=False)

    assert summary["rows_updated"] == 0
    assert summary["rows_unchanged"] == 1


def test_idempotent_second_run_is_noop(db: sqlite3.Connection) -> None:
    """AC-1: re-running after a correction updates nothing."""
    _seed_game(db, "g6", game_date=_UTC_DATE, start_time=_EVENING_UTC,
               timezone="America/Chicago")

    first = backfill_game_dates(db, dry_run=False)
    assert first["rows_updated"] == 1

    second = backfill_game_dates(db, dry_run=False)
    assert second["rows_updated"] == 0
    assert second["rows_unchanged"] == 1
    assert _game_date(db, "g6") == _LOCAL_DATE


def test_dry_run_counts_but_does_not_write(db: sqlite3.Connection) -> None:
    """AC-5: dry-run previews (rows_updated counted) but writes nothing."""
    _seed_game(db, "g7", game_date=_UTC_DATE, start_time=_EVENING_UTC,
               timezone="America/Chicago")

    summary = backfill_game_dates(db, dry_run=True)

    assert summary["rows_updated"] == 1        # would-update count
    assert _game_date(db, "g7") == _UTC_DATE   # but the DB is unchanged


# ---------------------------------------------------------------------------
# CLI: exit-code convention (AC-5)
# ---------------------------------------------------------------------------


def _seed_disk_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    load_real_schema(conn)
    conn.execute("INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)")
    conn.execute("INSERT INTO teams (id, name, membership_type) VALUES (1, 'LSB', 'member')")
    conn.execute("INSERT INTO teams (id, name, membership_type) VALUES (2, 'Opp', 'tracked')")
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, start_time, timezone) "
        "VALUES ('gc', '2026', ?, 1, 2, ?, 'America/Chicago')",
        (_UTC_DATE, _EVENING_UTC),
    )
    conn.commit()
    conn.close()


def test_cli_dry_run_exit_zero_and_no_write(tmp_path: Path) -> None:
    """AC-5: default dry-run exits 0, previews, writes nothing."""
    db_path = tmp_path / "app.db"
    _seed_disk_db(db_path)

    result = runner.invoke(app, ["data", "backfill-game-dates", "--db", str(db_path)])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.output
    assert "WOULD be updated: 1" in result.output

    conn = sqlite3.connect(str(db_path))
    stored = conn.execute("SELECT game_date FROM games WHERE game_id = 'gc'").fetchone()[0]
    conn.close()
    assert stored == _UTC_DATE  # unchanged by dry-run


def test_cli_execute_exit_zero_and_writes(tmp_path: Path) -> None:
    """AC-1/AC-5: --execute applies the correction and exits 0."""
    db_path = tmp_path / "app.db"
    _seed_disk_db(db_path)

    result = runner.invoke(
        app, ["data", "backfill-game-dates", "--db", str(db_path), "--execute"]
    )
    assert result.exit_code == 0
    assert "EXECUTE" in result.output

    conn = sqlite3.connect(str(db_path))
    stored = conn.execute("SELECT game_date FROM games WHERE game_id = 'gc'").fetchone()[0]
    conn.close()
    assert stored == _LOCAL_DATE


def test_cli_exits_nonzero_on_failure(tmp_path: Path) -> None:
    """AC-5: a failure in the backfill surfaces as a non-zero exit."""
    db_path = tmp_path / "app.db"
    _seed_disk_db(db_path)

    with patch(
        "src.db.backfill_game_dates.backfill_game_dates",
        side_effect=RuntimeError("boom"),
    ):
        result = runner.invoke(
            app, ["data", "backfill-game-dates", "--db", str(db_path)]
        )
    assert result.exit_code == 1
    assert "Error backfilling game_date" in result.output
