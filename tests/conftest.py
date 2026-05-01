"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.gamechanger.client import GameChangerClient
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult

_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
_SCHEMA_PATH = _MIGRATIONS_DIR / "001_initial_schema.sql"


def load_real_schema(conn: sqlite3.Connection) -> None:
    """Load the production schema into ``conn`` with FK enforcement enabled.

    Applies every ``NNN_*.sql`` migration file in numeric order so the loaded
    schema mirrors what ``run_migrations`` would produce on a fresh DB.  The
    helper does NOT touch the ``_migrations`` tracking table -- callers that
    need migration provenance should use ``run_migrations`` instead.

    SQLite's ``executescript`` implicitly commits and resets connection state,
    so setting ``PRAGMA foreign_keys=ON`` on the connection beforehand has no
    effect on the script it runs. The pragma must be prepended to the SQL
    string so that FK enforcement is active for every CREATE/INSERT in the
    migration. See ``.claude/rules/migrations.md`` ("executescript() and
    PRAGMAs") for the full rationale.
    """
    migration_files = sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    for path in migration_files:
        sql = path.read_text()
        conn.executescript("PRAGMA foreign_keys=ON;\n" + sql)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that run git commands in temp repos (deselect with '-m \"not integration\"')",
    )


# ---------------------------------------------------------------------------
# Plays-stage shared fixtures (E-229-01)
#
# Consumed by tests/test_plays_stage.py (E-229-01),
# tests/test_cli_data_scout_plays.py (E-229-02),
# tests/test_pipeline_scouting_sync_plays.py (E-229-03),
# tests/test_scout_plays_parity.py (E-229-05).
#
# Plays JSON shape sourced from
# docs/api/endpoints/get-game-stream-processing-event_id-plays.md.
# ---------------------------------------------------------------------------


@pytest.fixture()
def plays_json_factory():
    """Build a minimum plays JSON shape that ``PlaysParser`` accepts.

    Generates a deterministic sequence of ``num_plays`` "Single" plays in the
    top half of the 1st inning, alternating outs but with consistent
    batter/pitcher attribution.  The resulting dict mirrors the GameChanger
    plays endpoint's response shape (see
    ``docs/api/endpoints/get-game-stream-processing-event_id-plays.md``).

    Returns a callable so tests can build per-game JSON inline without
    repeating the boilerplate.
    """

    def _build(
        game_id: str,
        pitcher_id: str,
        batter_id: str,
        num_plays: int,
    ) -> dict[str, Any]:
        plays = []
        for order in range(num_plays):
            plays.append(
                {
                    "order": order,
                    "inning": 1,
                    "half": "top",
                    "name_template": {"template": "Single"},
                    "home_score": 0,
                    "away_score": 0,
                    "did_score_change": False,
                    "outs": 0,
                    "did_outs_change": False,
                    "at_plate_details": [
                        {"template": "Strike 1 looking"},
                        {"template": "Ball 1"},
                        {"template": "In play"},
                    ],
                    "final_details": [
                        {"template": f"${{{batter_id}}} singles to left field"},
                        {"template": f"${{{pitcher_id}}} pitching"},
                    ],
                    "messages": [],
                }
            )
        return {
            "sport": "baseball",
            "team_players": {},
            "plays": plays,
        }

    return _build


@pytest.fixture()
def mock_gc_client_with_plays():
    """Build a ``MagicMock`` ``GameChangerClient`` that returns canned plays JSON.

    Accepts a ``dict[str, dict]`` mapping ``game_id`` to plays JSON; the
    returned mock's ``.get(...)`` extracts the ``game_id`` from the request
    path (``/game-stream-processing/{game_id}/plays``) and returns the
    matching JSON.  Game IDs not present in the mapping raise ``KeyError``;
    tests that expect HTTP failures should configure ``side_effect`` directly.
    """

    def _build(plays_json_by_game_id: dict[str, dict]) -> MagicMock:
        client = MagicMock(spec=GameChangerClient)

        def _fake_get(path: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            # Path shape: /game-stream-processing/{game_id}/plays
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "game-stream-processing":
                game_id = parts[1]
                return plays_json_by_game_id[game_id]
            raise KeyError(f"unexpected path in mock_gc_client_with_plays: {path}")

        client.get.side_effect = _fake_get
        return client

    return _build


@pytest.fixture()
def seed_boxscore_for_plays():
    """Seed the minimum DB rows the plays loader + reconciler need.

    Inserts a ``games`` row, a ``game_perspectives`` row tagging the game
    with ``perspective_team_id`` (mirroring the upstream
    ``GameLoader._maybe_record_game_perspective`` write at
    ``src/gamechanger/loaders/game_loader.py:640-647``), plus per-pitcher
    ``player_game_pitching`` rows with ``appearance_order`` populated, plus
    per-batter ``player_game_batting`` rows.  The reconcile engine reads
    pitcher order from ``player_game_pitching.appearance_order`` (a DB
    column populated by the game loader from boxscore JSON during the
    upstream scouting load -- NOT read from a JSON file).  Seeding the
    column directly mirrors the real upstream pipeline behavior without
    seeding boxscore JSON files.

    Seeding ``game_perspectives`` is required because E2E tests mock the
    ``ScoutingLoader`` (so the real ``GameLoader`` never runs), which means
    a regression that breaks the upstream ``INSERT OR IGNORE`` would leave
    the test suite green.  Seeding it here keeps the fixture's outputs
    aligned with what the upstream pipeline would produce.

    The fixture assumes ``teams``, ``seasons``, and ``players`` rows already
    exist for the supplied IDs; callers seed those separately.
    """

    def _seed(
        conn: sqlite3.Connection,
        *,
        game_id: str,
        home_team_id: int,
        away_team_id: int,
        season_id: str,
        perspective_team_id: int,
        pitcher_appearances: list[dict[str, Any]] | None = None,
        batter_appearances: list[dict[str, Any]] | None = None,
        game_date: str = "2026-04-10",
    ) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO games "
            "(game_id, season_id, game_date, home_team_id, away_team_id, status) "
            "VALUES (?, ?, ?, ?, ?, 'completed')",
            (game_id, season_id, game_date, home_team_id, away_team_id),
        )

        # Mirror the upstream GameLoader write
        # (src/gamechanger/loaders/game_loader.py:640-647).
        conn.execute(
            "INSERT OR IGNORE INTO game_perspectives "
            "(game_id, perspective_team_id) VALUES (?, ?)",
            (game_id, perspective_team_id),
        )

        for entry in pitcher_appearances or []:
            conn.execute(
                "INSERT INTO player_game_pitching "
                "(game_id, team_id, player_id, perspective_team_id, "
                " appearance_order, ip_outs, h, r, er, bb, so, pitches, total_strikes, bf) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    entry["team_id"],
                    entry["player_id"],
                    perspective_team_id,
                    entry["appearance_order"],
                    entry.get("ip_outs", 0),
                    entry.get("h", 0),
                    entry.get("r", 0),
                    entry.get("er", 0),
                    entry.get("bb", 0),
                    entry.get("so", 0),
                    entry.get("pitches", 0),
                    entry.get("total_strikes", 0),
                    entry.get("bf", 0),
                ),
            )

        for entry in batter_appearances or []:
            conn.execute(
                "INSERT INTO player_game_batting "
                "(game_id, team_id, player_id, perspective_team_id, "
                " ab, r, h, bb, so, hbp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    game_id,
                    entry["team_id"],
                    entry["player_id"],
                    perspective_team_id,
                    entry.get("ab", 0),
                    entry.get("r", 0),
                    entry.get("h", 0),
                    entry.get("bb", 0),
                    entry.get("so", 0),
                    entry.get("hbp", 0),
                ),
            )

        conn.commit()

    return _seed


@pytest.fixture()
def seed_scout_result_skeleton():
    """Build a minimal in-memory ``ScoutingCrawlResult`` for plays-stage tests.

    Populates ``boxscores`` keyed by the supplied ``game_ids`` so callers can
    pass ``sorted(crawl_result.boxscores.keys())`` to ``run_plays_stage``
    exactly as the production pipeline does.  ``games`` is left empty by
    default; callers seed it if a test needs a particular shape.
    """

    def _build(
        *,
        public_id: str,
        team_id: int,
        game_ids: list[str],
        season_id: str = "2026-spring-hs",
    ) -> ScoutingCrawlResult:
        return ScoutingCrawlResult(
            team_id=team_id,
            season_id=season_id,
            public_id=public_id,
            games=[],
            roster=[],
            boxscores={gid: {} for gid in game_ids},
            games_crawled=len(game_ids),
            errors=0,
            skipped=False,
        )

    return _build
