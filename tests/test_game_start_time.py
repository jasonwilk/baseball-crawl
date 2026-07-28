"""Tests for start_time and timezone column support across all game loaders.

Covers, from E-253:
- AC-1: Migration adds start_time and timezone columns.
- AC-3: Scouting loader passes start_time and timezone via GameSummaryEntry.
- AC-4: Game loader preserves existing start_time/timezone when upserting with NULLs.

⚰ E-253's AC-2 ("Schedule loader writes start_time and timezone on INSERT and
UPDATE") and AC-5 ("all three loaders") are retired here, and the line naming
them was stale rather than merely dated: there is no schedule loader in
``src/gamechanger/loaders/`` and there are not three, and ``games.start_time``
has exactly ONE writer -- ``GameLoader._upsert_game``. E-278-04 depends on that
being true (see ``backfill_game_dates._MIDNIGHT_UTC_SUFFIXES``), so leaving a
docstring asserting otherwise would have contradicted a load-bearing claim.

And from E-278-04, the venue-local ``game_date`` derivation itself: timezone
alias resolution, fail-closed degradation on an unresolvable zone, full-day date
markers, and the guard keeping an unknown date out of the dedup key.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src.gamechanger.loaders.game_loader import (
    GameLoader,
    GameSummaryEntry,
    _derive_game_date,
)
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.gamechanger.types import TeamRef
from src.util.timezone import derive_local_date, resolve_timezone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_FILE = _PROJECT_ROOT / "migrations" / "001_initial_schema.sql"
# E-250-02: migration 008 drops seasons.season_type, team_opponents, and
# players.gc_athlete_profile_id -- apply it so the schema matches the fixtures.
_MIGRATION_008 = (
    _PROJECT_ROOT / "migrations" / "008_drop_identity_opponent_season_type.sql"
)
# E-264-01: migration 012 adds teams.innings_per_game, which ensure_team_row's
# INSERT now references -- apply it so the teams schema carries the new column.
_MIGRATION_012 = (
    _PROJECT_ROOT / "migrations" / "012_teams_innings_per_game.sql"
)


def _create_schema(db: sqlite3.Connection) -> None:
    """Create the full schema from the migration file and seed test data."""
    db.executescript(_MIGRATION_FILE.read_text(encoding="utf-8"))
    db.executescript(_MIGRATION_008.read_text(encoding="utf-8"))
    db.executescript(_MIGRATION_012.read_text(encoding="utf-8"))
    db.executescript(
        """
        INSERT OR IGNORE INTO seasons (season_id, name, year) VALUES ('2025', 'Spring 2025', 2025);
        INSERT OR IGNORE INTO programs (program_id, name, program_type) VALUES ('lsb-hs', 'LSB HS', 'hs');
        INSERT OR IGNORE INTO teams (id, name, gc_uuid, public_id, membership_type, season_year, program_id)
            VALUES (1, 'Own Team', 'own-uuid-1234', 'OwnTeamSlug', 'member', 2025, 'lsb-hs');
        INSERT OR IGNORE INTO teams (id, name, gc_uuid, public_id, membership_type, season_year)
            VALUES (2, 'Opponent Team', 'opp-uuid-5678', NULL, 'tracked', 2025);
        """
    )


def _fresh_db() -> sqlite3.Connection:
    """A second, independent database with the same schema and seed rows.

    Needed wherever two payloads must be loaded and their stored dates
    COMPARED: once E-278-04 makes both spellings of a zone yield the same date,
    two same-date/same-teams/same-score rows in ONE database are correctly
    collapsed by ``_find_duplicate_game`` and only one row survives -- which is
    the dedup fix working, but it destroys the comparison. Loading each payload
    into its own database keeps "when EACH is loaded" literal.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON;")
    _create_schema(conn)
    return conn


class _Unset:
    """Distinguishes "caller omitted start_time" from an explicit ``None``.

    A typed sentinel rather than a bare ``object()``: the parameter's annotation
    has to admit its own default, and ``str | None`` does not admit ``object()``.
    """


_UNSET = _Unset()


@pytest.fixture()
def db() -> sqlite3.Connection:
    return _fresh_db()


@pytest.fixture()
def own_team_ref() -> TeamRef:
    return TeamRef(id=1, gc_uuid="own-uuid-1234", public_id="OwnTeamSlug")


# ---------------------------------------------------------------------------
# AC-3: Scouting loader extracts start_time and timezone from public games
# ---------------------------------------------------------------------------


class TestScoutingLoaderStartTime:
    """Scouting loader passes start_time/timezone from the crawled games list
    through GameSummaryEntry."""

    def test_games_index_populates_start_time_fields(
        self, db: sqlite3.Connection
    ) -> None:
        """_build_games_index_from_data creates entries with start_time and timezone."""
        loader = ScoutingLoader(db)
        games_data = [
            {
                "id": "game-001",
                "game_status": "completed",
                "home_away": "home",
                "score": {"team": 5, "opponent_team": 3},
                "start_ts": "2025-04-26T16:00:00.000Z",
                "timezone": "America/Chicago",
            }
        ]

        index = loader._build_games_index_from_data(games_data)
        entry = index["game-001"]
        assert entry.start_time == "2025-04-26T16:00:00.000Z"
        assert entry.timezone == "America/Chicago"

    def test_games_index_handles_missing_start_fields(
        self, db: sqlite3.Connection
    ) -> None:
        """Missing start_ts/timezone produce None in the GameSummaryEntry."""
        loader = ScoutingLoader(db)
        games_data = [
            {
                "id": "game-002",
                "game_status": "completed",
                "home_away": "away",
                "score": {"team": 2, "opponent_team": 1},
                # no start_ts or timezone
            }
        ]

        index = loader._build_games_index_from_data(games_data)
        entry = index["game-002"]
        assert entry.start_time is None
        assert entry.timezone is None
        assert entry.is_full_day is False

    def test_games_index_carries_is_full_day(
        self, db: sqlite3.Connection
    ) -> None:
        """E-278-04 AC-2: the all-day flag reaches GameSummaryEntry.

        Before this story ``is_full_day`` was documented in our own API spec on
        the very payload this function reads and was read by NOTHING -- the only
        ``full_day`` reader in src/ was the AUTHENTICATED schedule crawler, on a
        differently-named key and a different payload shape. The record below is
        the four-part shape from the "Full-Day Events" section of
        docs/api/endpoints/get-public-teams-public_id-games.md.
        """
        loader = ScoutingLoader(db)
        games_data = [
            {
                "id": "game-fullday",
                "game_status": "completed",
                "home_away": "home",
                "score": {"team": 9, "opponent_team": 1},
                "is_full_day": True,
                "start_ts": "2026-05-31T00:00:00.000Z",
                "end_ts": "2026-06-01T00:00:00.000Z",
                "timezone": None,
            }
        ]

        entry = loader._build_games_index_from_data(games_data)["game-fullday"]

        assert entry.is_full_day is True
        assert entry.start_time == "2026-05-31T00:00:00.000Z"
        assert entry.timezone is None
        assert _derive_game_date(entry) == "2026-05-31"  # the marker, not 05-30

    def test_games_index_full_day_absent_key_defaults_false(
        self, db: sqlite3.Connection
    ) -> None:
        """A payload omitting the key entirely is a timed event.

        Every observed event carries ``is_full_day``, so absence is defensive
        parsing rather than an expected shape -- but defaulting it to True would
        silently switch every game onto the date-marker path.
        """
        loader = ScoutingLoader(db)
        games_data = [
            {
                "id": "game-nokey",
                "game_status": "completed",
                "home_away": "home",
                "score": {"team": 1, "opponent_team": 0},
                "start_ts": "2026-05-31T00:00:00.000Z",
                "timezone": "America/Chicago",
            }
        ]

        entry = loader._build_games_index_from_data(games_data)["game-nokey"]

        assert entry.is_full_day is False
        assert _derive_game_date(entry) == "2026-05-30"  # localized, correctly


# ---------------------------------------------------------------------------
# AC-4: Game loader preserves existing start_time/timezone during upsert
# ---------------------------------------------------------------------------


class TestGameLoaderPreservesStartTime:
    """Game loader uses COALESCE to preserve existing values when upserting with NULL."""

    def test_upsert_preserves_existing_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """When game already has start_time, upserting with NULL keeps the original."""
        # Pre-populate a game with start_time (as if schedule loader set it)
        db.execute(
            """
            INSERT INTO games (game_id, season_id, game_date, home_team_id,
                               away_team_id, status, start_time, timezone)
            VALUES ('game-100', '2025', '2025-04-26', 1, 2,
                    'scheduled', '2025-04-26T16:00:00.000Z', 'America/Chicago')
            """
        )
        db.commit()

        # Game loader upserts with NULL start_time (game-summaries has no time data)
        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        summary = GameSummaryEntry(
            event_id="game-100",
            game_stream_id="stream-100",
            home_away="home",
            owning_team_score=5,
            opponent_team_score=3,
            opponent_id="opp-uuid-5678",
            date_source_instant="2025-04-26T20:00:00Z",
            # start_time and timezone default to None
        )
        assert summary.start_time is None
        assert summary.timezone is None

        loader._upsert_game(
            "game-100", "2025-04-26", 1, 2, 5, 3, "stream-100",
        )
        db.commit()

        row = db.execute(
            "SELECT start_time, timezone, status FROM games WHERE game_id = 'game-100'"
        ).fetchone()
        # Preserved from the original insert
        assert row[0] == "2025-04-26T16:00:00.000Z"
        assert row[1] == "America/Chicago"
        # Status upgraded to completed
        assert row[2] == "completed"

    def test_upsert_writes_start_time_when_existing_is_null(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """When game has NULL start_time, upserting with a value sets it."""
        db.execute(
            """
            INSERT INTO games (game_id, season_id, game_date, home_team_id,
                               away_team_id, status, start_time, timezone)
            VALUES ('game-200', '2025', '2025-04-26', 1, 2,
                    'completed', NULL, NULL)
            """
        )
        db.commit()

        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        loader._upsert_game(
            "game-200", "2025-04-26", 1, 2, 5, 3, "stream-200",
            start_time="2025-04-26T18:00:00.000Z",
            timezone="America/Denver",
        )
        db.commit()

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-200'"
        ).fetchone()
        assert row[0] == "2025-04-26T18:00:00.000Z"
        assert row[1] == "America/Denver"

    def test_fresh_insert_with_null_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """Fresh INSERT with NULL start_time stores NULL."""
        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        loader._upsert_game(
            "game-300", "2025-04-26", 1, 2, 5, 3, "stream-300",
        )
        db.commit()

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-300'"
        ).fetchone()
        assert row[0] is None
        assert row[1] is None

    def test_load_payload_passes_start_time_from_summary(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """GameLoader.load_payload passes start_time/timezone from GameSummaryEntry through."""
        boxscore = {
            "OwnTeamSlug": {
                "stats": [{"AB": 4, "R": 1, "H": 2, "RBI": 1, "BB": 0, "SO": 1}],
                "extra": [],
                "lineup": [],
            },
            "opp-uuid-5678": {
                "stats": [{"AB": 3, "R": 0, "H": 1, "RBI": 0, "BB": 1, "SO": 2}],
                "extra": [],
                "lineup": [],
            },
        }

        summary = GameSummaryEntry(
            event_id="game-400",
            game_stream_id="stream-400",
            home_away="home",
            owning_team_score=1,
            opponent_team_score=0,
            opponent_id="opp-uuid-5678",
            date_source_instant="2025-04-26T20:00:00Z",
            start_time="2025-04-26T16:00:00.000Z",
            timezone="America/Chicago",
        )

        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
        loader.load_payload(boxscore, summary)

        row = db.execute(
            "SELECT start_time, timezone FROM games WHERE game_id = 'game-400'"
        ).fetchone()
        assert row[0] == "2025-04-26T16:00:00.000Z"
        assert row[1] == "America/Chicago"


# ---------------------------------------------------------------------------
# E-253-04: game_date is the venue-LOCAL calendar date of the game's START instant
# (E-278-05: this header said "scoring instant" -- no live path supplies one)
# ---------------------------------------------------------------------------


def _load_summary(
    db: sqlite3.Connection,
    own_team_ref: TeamRef,
    *,
    game_id: str,
    stream_id: str,
    date_source_instant: str,
    timezone: str | None,
    is_full_day: bool = False,
    start_time: str | None | _Unset = _UNSET,
    loader: GameLoader | None = None,
) -> str | None:
    """Load a minimal boxscore for one summary and return the stored game_date.

    Returns ``None`` when no row exists under *game_id* -- which happens when
    dedup REDIRECTED this summary onto an existing canonical row. That is a real
    outcome, not an error, so it is reported rather than swallowed: a caller
    comparing it to a date string fails loudly instead of reading a stale row.

    Pass *loader* to route several summaries through ONE GameLoader instance --
    i.e. a single load rather than several (E-278-04 AC-3).

    *start_time* defaults to mirroring *date_source_instant*, which is what the
    public feed produces for a timed game. Pass it explicitly for the ABSENT-
    instant shape: there ``_build_games_index_from_data`` yields an empty
    ``date_source_instant`` and a ``None`` ``start_time`` (they come from
    different expressions), and mirroring an empty string would store ``''``
    where production stores NULL.
    """
    if isinstance(start_time, _Unset):
        start_time = date_source_instant
    boxscore = {
        "OwnTeamSlug": {
            "stats": [{"AB": 4, "R": 1, "H": 2, "RBI": 1, "BB": 0, "SO": 1}],
            "extra": [],
            "lineup": [],
        },
        "opp-uuid-5678": {
            "stats": [{"AB": 3, "R": 0, "H": 1, "RBI": 0, "BB": 1, "SO": 2}],
            "extra": [],
            "lineup": [],
        },
    }
    summary = GameSummaryEntry(
        event_id=game_id,
        game_stream_id=stream_id,
        home_away="home",
        owning_team_score=1,
        opponent_team_score=0,
        opponent_id="opp-uuid-5678",
        date_source_instant=date_source_instant,
        start_time=start_time,
        timezone=timezone,
        is_full_day=is_full_day,
    )
    if loader is None:
        loader = GameLoader(db=db, owned_team_ref=own_team_ref)
    loader.load_payload(boxscore, summary)
    db.commit()
    row = db.execute(
        "SELECT game_date FROM games WHERE game_id = ?", (game_id,)
    ).fetchone()
    return row[0] if row else None


class TestGameDateLocalDerivation:
    """E-253-04: an evening game must file under the venue-local date, not the
    next UTC day (the old ``date_source_instant[:10]`` slice)."""

    def test_evening_game_uses_local_date_not_next_utc_day(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-2: 2026-06-21T03:00Z == 2026-06-20 22:00 America/Chicago (CDT).

        The UTC prefix is ``2026-06-21``; the correct local date is
        ``2026-06-20``.
        """
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-eve", stream_id="stream-eve",
            date_source_instant="2026-06-21T03:00:00.000Z",
            timezone="America/Chicago",
        )
        assert game_date == "2026-06-20", (
            "evening game must file under the local calendar date, not the "
            "next UTC day"
        )

    def test_missing_timezone_falls_back_to_operating_seam(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-3: no game timezone -> operating-tz seam (default America/Chicago).

        The seam returns a ZoneInfo; the loader bridges it to the IANA name via
        ``.key`` before calling ``derive_local_date`` (never passes the object).
        With no OPERATING_TIMEZONE set the default (America/Chicago) applies, so
        the same evening instant still resolves to the prior local day.
        """
        monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-noz", stream_id="stream-noz",
            date_source_instant="2026-06-21T03:00:00.000Z",
            timezone=None,
        )
        assert game_date == "2026-06-20"

    def test_operating_timezone_env_override_applies_on_fallback(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-3: the fallback honors an OPERATING_TIMEZONE override (proves the
        seam is consulted, not a hard-coded default). 2026-06-21T04:30Z falls
        between NY midnight (04:00Z, EDT UTC-4) and Chicago midnight (05:00Z,
        CDT UTC-5): NY has already rolled to 2026-06-21 while Chicago is still
        2026-06-20. Under the NY override the date must be 2026-06-21.
        """
        monkeypatch.setenv("OPERATING_TIMEZONE", "America/New_York")
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-ny", stream_id="stream-ny",
            date_source_instant="2026-06-21T04:30:00.000Z",
            timezone=None,
        )
        assert game_date == "2026-06-21"

    def test_absent_instant_falls_back_to_sentinel(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """An empty date_source_instant preserves the '1900-01-01' sentinel."""
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-none", stream_id="stream-none",
            date_source_instant="",
            timezone="America/Chicago",
        )
        assert game_date == "1900-01-01"


# ---------------------------------------------------------------------------
# E-278-04: timezone aliases, fail-closed degradation, and full-day events
# ---------------------------------------------------------------------------

# The AC-8 discriminating instant. 02:00Z on 2026-06-20 is 21:00 on 2026-06-19
# in America/Chicago (CDT, UTC-5): venue-local 2026-06-19, UTC 2026-06-20.
#
# Every test below that exercises AC-1 or AC-4a uses THIS instant, and the
# reason is load-bearing rather than stylistic: an afternoon instant such as
# 18:00Z has local date == UTC date, so an assertion built on one passes under
# every candidate fix INCLUDING doing nothing, and would certify nothing about
# the change. _UTC_SLICE below is asserted against explicitly so a future edit
# that quietly swaps in an afternoon instant fails instead of going vacuous.
_EVENING_UTC = "2026-06-20T02:00:00.000Z"
_EVENING_LOCAL_DATE = "2026-06-19"
_UTC_SLICE = "2026-06-20"

# The full-day shape, transcribed from the "Full-Day Events (`is_full_day:
# true`)" section of docs/api/endpoints/get-public-teams-public_id-games.md
# (live-verified 2026-07-27): start_ts at exactly midnight UTC, end_ts exactly
# 24h later, timezone null. The marker names 2026-05-31; localizing it as an
# instant would yield 2026-05-30, which is the -1-day defect.
_FULL_DAY_MARKER = "2026-05-31T00:00:00.000Z"
_FULL_DAY_DATE = "2026-05-31"
_FULL_DAY_LOCALIZED_WRONGLY = "2026-05-30"


class TestTimezoneAliasResolution:
    """AC-1: two spellings of one real zone must produce one date."""

    def test_legacy_alias_and_canonical_name_agree_on_evening_game(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-1/AC-8: `US/Central` and `America/Chicago` are one zone.

        The payloads differ ONLY in the timezone spelling. Before `tzdata` was a
        declared dependency the alias raised ZoneInfoNotFoundError, the
        derivation fell through with the datetime still in UTC, and the two
        perspectives of one real game split across two calendar dates. (Row
        counts were measured per environment and are not quoted here -- the dev
        and production populations are different ones.)

        The asserted date is the venue-local one AND is asserted to differ from
        the UTC slice, so neither "both return the UTC date" nor "both return
        the sentinel" can satisfy this test.

        Each payload is loaded into its OWN database. In one database these two
        would now correctly collapse to a single row -- same date, same teams,
        same scores -- which is the dedup fix working and would leave nothing to
        compare. See ``_fresh_db``.
        """
        aliased = _load_summary(
            db, own_team_ref,
            game_id="game-alias", stream_id="stream-alias",
            date_source_instant=_EVENING_UTC, timezone="US/Central",
        )
        with closing(_fresh_db()) as other_db:
            canonical = _load_summary(
                other_db, own_team_ref,
                game_id="game-alias", stream_id="stream-alias",
                date_source_instant=_EVENING_UTC, timezone="America/Chicago",
            )

        assert aliased == canonical == _EVENING_LOCAL_DATE
        assert aliased != _UTC_SLICE, "must be the venue-local date, not the UTC one"

    def test_pacific_alias_resolves_too(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-1: the corpus's other observed alias resolves as well."""
        aliased = _load_summary(
            db, own_team_ref,
            game_id="game-pac", stream_id="stream-pac",
            date_source_instant=_EVENING_UTC, timezone="US/Pacific",
        )
        with closing(_fresh_db()) as other_db:
            canonical = _load_summary(
                other_db, own_team_ref,
                game_id="game-pac", stream_id="stream-pac",
                date_source_instant=_EVENING_UTC, timezone="America/Los_Angeles",
            )

        assert aliased == canonical == _EVENING_LOCAL_DATE

    def test_never_observed_aliases_resolve_too(self) -> None:
        """AC-6: the fix removes the CLASS, not the two instances we saw.

        This is the assertion a normalization map cannot pass. A
        ``{US/Central -> America/Chicago, US/Pacific -> America/Los_Angeles}``
        table would satisfy every test above while remaining a denylist that
        fails open the first time GameChanger emits one of the several dozen
        other tzdata backward links. The zone field is per-EVENT and appears to
        be whatever the event's creator typed -- nothing bounds it, and an enum
        observed closed is not an enum proven closed.

        None of the names below appears in the measured 1064-event corpus, whose
        six distinct timezone strings are America/Chicago, US/Central,
        America/Denver, America/New_York, US/Pacific and America/Phoenix. That
        is the point: these resolve because the whole backward namespace ships,
        not because anyone enumerated them.
        """
        for alias, canonical in [
            ("US/Eastern", "America/New_York"),
            ("US/Mountain", "America/Denver"),
            ("US/Arizona", "America/Phoenix"),
            ("Canada/Eastern", "America/Toronto"),
        ]:
            assert derive_local_date(_EVENING_UTC, alias) == derive_local_date(
                _EVENING_UTC, canonical
            ), f"{alias} must resolve to the same zone as {canonical}"
            assert derive_local_date(_EVENING_UTC, alias) is not None


class TestUnresolvableTimezoneFailsClosed:
    """AC-4a / AC-4b / AC-4c: a zone we cannot resolve yields no date at all."""

    def test_stored_date_is_not_the_bare_utc_slice(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-4a: the DATE property, not a return-value property.

        Phrased about the stored date on purpose. Making `derive_local_date`
        return None is a NO-OP here -- `_derive_game_date`'s unparseable-instant
        fallback is `date_source_instant[:10]`, which is byte-identical to the
        old fail-open output by construction (a failed `astimezone` leaves the
        datetime in the tzinfo it was parsed with, and `.date()` on an aware
        datetime is its own written wall-clock date). A criterion phrased as
        "returns None" would go green on that no-op with the row still wrong.

        `Not/AZone` is deliberately synthetic: once tzdata is installed there is
        no real unresolvable alias left to test with.
        """
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-badtz", stream_id="stream-badtz",
            date_source_instant=_EVENING_UTC, timezone="Not/AZone",
        )

        assert game_date != _UTC_SLICE
        assert game_date == "1900-01-01"

    def test_does_not_substitute_the_operating_timezone(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-4c: no silent zone substitution -- the fail-OPEN loophole.

        Falling back to the operating zone would produce a date that differs
        from the UTC slice (satisfying AC-4a) while silently presenting an
        unverified zone's answer as venue-local. The override here is a zone
        whose local date for this instant (2026-06-19 in New York, 22:00 EDT)
        is ALSO not the UTC slice, so a substitution would pass AC-4a and only
        this assertion catches it.
        """
        monkeypatch.setenv("OPERATING_TIMEZONE", "America/New_York")
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-nosub", stream_id="stream-nosub",
            date_source_instant=_EVENING_UTC, timezone="Not/AZone",
        )

        # What a substitution would have produced -- proven reachable, not assumed.
        substituted = derive_local_date(_EVENING_UTC, "America/New_York")
        assert substituted == "2026-06-19"
        assert substituted != _UTC_SLICE

        assert game_date != substituted, (
            "an unresolvable zone must not be silently replaced by the "
            "operating zone and presented as a venue-local date"
        )
        assert game_date == "1900-01-01"

    def test_absent_timezone_still_uses_the_operating_default(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-4c's boundary: AC-4c governs a PRESENT-but-unresolvable zone.

        An ABSENT timezone is a different case -- no signal was given, so the
        documented operating-tz default applies, exactly as before this story.
        Pinned so a future reading of "fail closed" does not over-apply it and
        break every null-timezone timed game.
        """
        monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-notz", stream_id="stream-notz",
            date_source_instant=_EVENING_UTC, timezone=None,
        )

        assert game_date == _EVENING_LOCAL_DATE

    def test_degradation_is_visible_in_the_stored_row(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-4b: an operator can find these rows without reading logs.

        A log WARNING alone would NOT satisfy AC-4b -- that is precisely what
        today's fail-open path already emits, so a log-only signal is satisfied
        by the defect under repair.

        The durable signal is the stored row. ``game_date = '1900-01-01'``
        enumerates EVERY undated row with no false negatives, and each row
        carries the ``timezone`` that failed. Adding ``start_time IS NOT NULL``
        answers a different question -- which of them a backfill can repair --
        and is exactly right for that one.

        ⚰ Two earlier versions of this test each asserted a predicate that
        claimed to isolate the unresolvable-zone CAUSE: first
        ``start_time IS NOT NULL``, then ``timezone IS NOT NULL`` plus a
        resolvability check. Both were wrong, in OPPOSITE directions, and the
        second was wrong in a way that reads as more careful than the first --
        which is the trap. Neither stored field separates an absent instant from
        an unresolvable zone. The cause is not recoverable from the row; only
        the fact of degradation is, and that is what AC-4b asks for.
        """
        _load_summary(
            db, own_team_ref,
            game_id="game-signal", stream_id="stream-signal",
            date_source_instant=_EVENING_UTC, timezone="Not/AZone",
        )
        _load_summary(
            db, own_team_ref,
            game_id="game-noinstant", stream_id="stream-noinstant",
            date_source_instant="", start_time=None,
            timezone="America/Chicago",
        )

        # 1. Complete: both undated rows, whatever refused them.
        undated = db.execute(
            "SELECT game_id, start_time, timezone FROM games "
            "WHERE game_date = '1900-01-01' ORDER BY game_id"
        ).fetchall()
        assert [r[0] for r in undated] == ["game-noinstant", "game-signal"]

        # The zone that failed is on the row, so the operator can act on it.
        assert dict((r[0], r[2]) for r in undated)["game-signal"] == "Not/AZone"

        # 2. Repairable subset: only the row a backfill can reach. The other has
        # no instant, so `backfill_game_dates`'s tier-3 guard refuses it first.
        repairable = db.execute(
            "SELECT game_id FROM games "
            "WHERE game_date = '1900-01-01' AND start_time IS NOT NULL"
        ).fetchall()
        assert [r[0] for r in repairable] == ["game-signal"]

    def test_detection_query_finds_a_degraded_row_with_no_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-4b: why ``start_time IS NOT NULL`` cannot mean "unresolvable zone".

        ``_build_games_index_from_data`` fills ``date_source_instant`` from
        ``start_ts or end_ts`` but sources ``start_time`` from ``start_ts``
        ALONE. So an event with ``end_ts`` and no ``start_ts`` carries a truthy
        instant and a NULL ``start_time`` -- and with an unresolvable zone it is
        a genuine case-3 row that predicate would MISS.

        The row is still caught by the complete query (its ``game_date`` is the
        sentinel) and is correctly ABSENT from the repairable subset, because
        ``backfill_game_dates`` refuses a NULL ``start_time`` before it looks at
        anything else. Both facts are what make the two-query split honest.

        Asserted at the index/derivation level because that is where the two
        fields diverge; the shape is what matters, not the storage round-trip.
        """
        loader = ScoutingLoader(db)
        entry = loader._build_games_index_from_data([
            {
                "id": "game-endts-only",
                "game_status": "completed",
                "home_away": "home",
                "score": {"team": 1, "opponent_team": 0},
                "end_ts": "2026-06-20T05:00:00.000Z",  # note: no start_ts
                "timezone": "Not/AZone",
            }
        ])["game-endts-only"]

        assert entry.date_source_instant == "2026-06-20T05:00:00.000Z"
        assert entry.start_time is None          # the divergence
        assert _derive_game_date(entry) == "1900-01-01"   # still case 3
        # A genuinely unresolvable zone, so this is a real degradation and not
        # an artefact of the fixture.
        assert entry.timezone is not None and resolve_timezone(entry.timezone) is None

        # The assertions above prove the divergence is REACHABLE from a real
        # payload, which a storage round-trip would not show. The queries below
        # prove what the stored row then does about it -- the docstring names
        # both outcomes, so both are executed rather than left as implications.
        _load_summary(
            db, own_team_ref,
            game_id="game-endts-stored", stream_id="stream-endts-stored",
            date_source_instant=entry.date_source_instant,
            start_time=None, timezone="Not/AZone",
        )

        undated = db.execute(
            "SELECT game_id FROM games WHERE game_date = '1900-01-01'"
        ).fetchall()
        assert [r[0] for r in undated] == ["game-endts-stored"]  # caught

        repairable = db.execute(
            "SELECT game_id FROM games "
            "WHERE game_date = '1900-01-01' AND start_time IS NOT NULL"
        ).fetchall()
        assert repairable == []  # and correctly outside the repairable subset

    def test_sentinel_can_sit_over_a_preserved_start_time(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-4b: a case-2 row CAN carry a non-NULL ``start_time``.

        ``ON CONFLICT`` sets ``game_date = excluded.game_date`` unconditionally
        while ``start_time`` is ``COALESCE``d, so a game loaded WITH an instant
        and re-loaded WITHOUT one ends as a case-2 sentinel over a retained
        ``start_time`` -- the shape the retired prose called impossible.

        This is the row that defeats reading ``start_time IS NOT NULL`` as
        "unresolvable zone": it satisfies that predicate and its cause is an
        absent instant. It is still correctly IN the repairable subset -- the
        backfill really can re-derive it -- which is the point: that predicate
        answers repairability, never cause.
        """
        _load_summary(
            db, own_team_ref,
            game_id="game-reload", stream_id="stream-reload",
            date_source_instant=_EVENING_UTC, timezone="America/Chicago",
        )
        _load_summary(
            db, own_team_ref,
            game_id="game-reload", stream_id="stream-reload",
            date_source_instant="", start_time=None, timezone=None,
        )

        row = db.execute(
            "SELECT game_date, start_time, timezone FROM games "
            "WHERE game_id = 'game-reload'"
        ).fetchone()

        assert row[0] == "1900-01-01"
        assert row[1] == _EVENING_UTC        # preserved, not NULLed
        # It satisfies `start_time IS NOT NULL` while being case 2 -- so that
        # predicate cannot mean "unresolvable zone" in either direction.
        assert resolve_timezone(row[2]) is not None


class TestUnknownDateIsNotADedupKey:
    """E-278-04: the sentinel date must not group unrelated games together."""

    def test_two_undated_games_stay_two_rows(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """A wrong merge is the destructive direction; a missed one is not.

        ``_find_duplicate_game`` gates candidates on ``game_date = ?``, so
        without the guard at its call site every sentinel-dated game sharing a
        team pair is a candidate for every other -- and these two agree on
        nothing except that neither date could be determined. One reaches the
        sentinel through an absent instant, the other through an unresolvable
        timezone: DIFFERENT games, different real dates, and the second silently
        absorbed into the first before the guard existed (this test caught it).
        """
        _load_summary(
            db, own_team_ref,
            game_id="game-undated-a", stream_id="stream-undated-a",
            date_source_instant="", start_time=None,
            timezone="America/Chicago",
        )
        _load_summary(
            db, own_team_ref,
            game_id="game-undated-b", stream_id="stream-undated-b",
            date_source_instant=_EVENING_UTC, timezone="Not/AZone",
        )

        rows = db.execute(
            "SELECT game_id FROM games WHERE game_date = '1900-01-01' "
            "ORDER BY game_id"
        ).fetchall()
        assert [r[0] for r in rows] == ["game-undated-a", "game-undated-b"]

    def test_a_known_date_still_dedups(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """The guard must be scoped to the sentinel, not disable dedup at large.

        Two loads of the same real game on a known date still collapse to one
        row -- the anti-vacuity check on the test above, which would pass just
        as well if dedup had been switched off entirely.
        """
        assert _load_summary(
            db, own_team_ref,
            game_id="game-dd-1", stream_id="stream-dd-1",
            date_source_instant=_EVENING_UTC, timezone="America/Chicago",
        ) == _EVENING_LOCAL_DATE
        # Redirected onto game-dd-1, so no row of its own -- the collapse itself.
        assert _load_summary(
            db, own_team_ref,
            game_id="game-dd-2", stream_id="stream-dd-2",
            date_source_instant=_EVENING_UTC, timezone="US/Central",
        ) is None

        rows = db.execute(
            "SELECT game_id FROM games WHERE game_date = ?", (_EVENING_LOCAL_DATE,)
        ).fetchall()
        assert [r[0] for r in rows] == ["game-dd-1"]


class TestFullDayEvents:
    """AC-2 / AC-2b: an all-day event's start_ts is a DATE MARKER."""

    def test_full_day_marker_is_not_shifted_back_a_day(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-2: the stored date is the marker's date, not the previous day.

        Localizing a midnight-UTC marker moves it back into the previous evening
        in every western-hemisphere zone. The codebase already reasoned this
        through for the SYNTHETIC 1900-01-01 sentinel (scouting_loader's
        "would shift back a day ... -> 1899-12-31") and never extended it to
        real all-day events, which have the identical shape.
        """
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-fullday", stream_id="stream-fullday",
            date_source_instant=_FULL_DAY_MARKER, timezone=None,
            is_full_day=True,
        )

        assert game_date == _FULL_DAY_DATE
        assert game_date != _FULL_DAY_LOCALIZED_WRONGLY

    def test_full_day_ignores_the_timezone_entirely(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-2b (first half): the behavior keys on is_full_day, not on a null tz.

        Two payloads differing ONLY in timezone -- one null, one a resolvable
        IANA name -- must both take the full-day path. An implementation keyed on
        `timezone is None` passes the test above and fails this one.
        """
        null_tz = _load_summary(
            db, own_team_ref,
            game_id="game-fd", stream_id="stream-fd",
            date_source_instant=_FULL_DAY_MARKER, timezone=None,
            is_full_day=True,
        )
        with closing(_fresh_db()) as other_db:
            real_tz = _load_summary(
                other_db, own_team_ref,
                game_id="game-fd", stream_id="stream-fd",
                date_source_instant=_FULL_DAY_MARKER, timezone="America/Chicago",
                is_full_day=True,
            )

        assert null_tz == real_tz == _FULL_DAY_DATE

    def test_full_day_without_a_start_ts_gets_the_sentinel_not_end_ts(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """The marker is read from start_ts and from nowhere else.

        ``date_source_instant`` is filled upstream from ``end_ts`` when
        ``start_ts`` is absent, and on a full-day event ``end_ts`` is exactly 24
        hours later -- so reading the marker from it would date the game
        TOMORROW. Refusing is the correct answer: we have no marker.

        Unexercised in the wild (zero of 1064 reachable events lack a start_ts),
        which is precisely why it is pinned -- an unexercised branch is the one
        nobody notices going wrong.
        """
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-fd-noets", stream_id="stream-fd-noets",
            date_source_instant="2026-06-01T00:00:00.000Z",  # the end_ts
            start_time=None, timezone=None, is_full_day=True,
        )

        assert game_date == "1900-01-01"
        assert game_date != "2026-06-01", "must not date the game from end_ts"

    def test_null_timezone_timed_event_does_not_take_the_full_day_path(
        self, db: sqlite3.Connection, own_team_ref: TeamRef,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-2b (second half): the converse -- null tz + is_full_day false.

        A 7:00pm US Central start IS midnight UTC, so this row looks exactly
        like a full-day marker on every proxy anyone might reach for. It must
        still be localized: the full-day path would store 2026-05-31 where the
        venue-local date is 2026-05-30.
        """
        monkeypatch.delenv("OPERATING_TIMEZONE", raising=False)
        game_date = _load_summary(
            db, own_team_ref,
            game_id="game-timed-nulltz", stream_id="stream-timed-nulltz",
            date_source_instant=_FULL_DAY_MARKER, timezone=None,
            is_full_day=False,
        )

        assert game_date == _FULL_DAY_LOCALIZED_WRONGLY  # correct HERE: a real instant
        assert game_date != _FULL_DAY_DATE, (
            "a timed event must be localized; only is_full_day switches the path"
        )


class TestOppositePolarityMechanismsCoexist:
    """AC-3: the two corrections shift dates in OPPOSITE directions."""

    def test_alias_row_and_full_day_row_are_both_correct_in_one_load(
        self, db: sqlite3.Connection, own_team_ref: TeamRef
    ) -> None:
        """AC-3: neither mechanism's correction moves the other's population.

        The +1-day alias defect and the -1-day full-day defect are opposite in
        polarity, which is why a uniform date-shift repair would fix one
        population and corrupt the other. Both rows go through ONE GameLoader
        instance so this is a single load rather than two.
        """
        loader = GameLoader(db=db, owned_team_ref=own_team_ref)

        alias_date = _load_summary(
            db, own_team_ref, loader=loader,
            game_id="game-mix-alias", stream_id="stream-mix-alias",
            date_source_instant=_EVENING_UTC, timezone="US/Central",
        )
        full_day_date = _load_summary(
            db, own_team_ref, loader=loader,
            game_id="game-mix-fullday", stream_id="stream-mix-fullday",
            date_source_instant=_FULL_DAY_MARKER, timezone=None,
            is_full_day=True,
        )

        assert alias_date == _EVENING_LOCAL_DATE   # +1-day defect corrected
        assert full_day_date == _FULL_DAY_DATE     # -1-day defect corrected

        stored = dict(
            db.execute(
                "SELECT game_id, game_date FROM games WHERE game_id LIKE 'game-mix-%'"
            ).fetchall()
        )
        assert stored == {
            "game-mix-alias": _EVENING_LOCAL_DATE,
            "game-mix-fullday": _FULL_DAY_DATE,
        }


# ---------------------------------------------------------------------------
# AC-1: Migration file exists with correct DDL
# ---------------------------------------------------------------------------


class TestMigrationFile:
    """Schema includes start_time and timezone columns (consolidated in 001)."""

    def test_migration_file_exists(self) -> None:
        assert _MIGRATION_FILE.exists(), f"Migration file not found at {_MIGRATION_FILE}"

    def test_migration_includes_start_time_columns(self) -> None:
        content = _MIGRATION_FILE.read_text(encoding="utf-8")
        assert "start_time" in content
        assert "timezone" in content
