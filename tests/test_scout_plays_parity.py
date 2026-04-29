"""Scouting-pipeline-parity invariant test for plays (E-229-05).

Encodes the CLAUDE.md "Scouting pipeline parity" architectural invariant for
the plays stage as an executable test: when the same fixture inputs are run
through both the CLI scout path (`_scout_live` via `typer.testing.CliRunner`)
and the web scout path (`run_scouting_sync`), the resulting DB state on the
three plays-touching tables must be equivalent:

- ``plays``
- ``play_events``
- ``reconciliation_discrepancies``

The parity assertion compares column subsets pinned against
``migrations/001_initial_schema.sql`` (timestamps, autoincrement ids, and
per-run UUIDs are excluded).  When the invariant breaks in the future, the
diff-formatter helper produces a clear human-readable failure message.

This test is the canary that fails when an accidental change to one path
(CLI or web) drifts away from the other.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from migrations.apply_migrations import run_migrations
from src.cli import app
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
from src.gamechanger.loaders import LoadResult
from src.pipeline import trigger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PUBLIC_ID = "tracked-opp"
_SEASON_ID = "2026-spring-hs"
_GAME_ID_1 = "11111111-1111-1111-1111-111111111111"
_GAME_ID_2 = "22222222-2222-2222-2222-222222222222"
_BATTER_1 = "ba000001-aaaa-bbbb-cccc-000000000001"
_BATTER_2 = "ba000002-aaaa-bbbb-cccc-000000000002"
_PITCHER_1 = "01000001-aaaa-bbbb-cccc-000000000001"
_PITCHER_2 = "01000002-aaaa-bbbb-cccc-000000000002"

_FAKE_CREDENTIALS = {
    "GAMECHANGER_REFRESH_TOKEN_WEB": "fake-refresh-token",
    "GAMECHANGER_CLIENT_ID_WEB": "07cb985d-ff6c-429d-992c-b8a0d44e6fc3",
    "GAMECHANGER_CLIENT_KEY_WEB": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "GAMECHANGER_DEVICE_ID_WEB": "abcdefabcdefabcdefabcdefabcdefab",
    "GAMECHANGER_BASE_URL": "https://api.team-manager.gc.com",
    "GAMECHANGER_APP_NAME_WEB": "web",
}


# ---------------------------------------------------------------------------
# Diff-formatter helper (AC-9)
# ---------------------------------------------------------------------------


def format_row_diff(
    cli_rows: list[tuple],
    web_rows: list[tuple],
    table_name: str,
    *,
    columns: list[str] | None = None,
    natural_key: tuple[int, ...] | None = None,
) -> str:
    """Format a human-readable diff between two row sets.

    Returns the empty string when ``cli_rows == web_rows``.  Otherwise
    returns a multi-line message naming the table, the per-side row counts,
    and either the missing rows or the value-mismatched rows.

    When ``columns`` and ``natural_key`` are supplied, rows that share a
    natural-key projection on both sides surface as a "value mismatch on
    natural key K: column 'NAME' (cli=X, web=Y)" line per differing column,
    making AC-9(c) (a shared-row value mismatch names the column and both
    values) actionable.  Rows whose natural key is missing entirely from the
    other side print as "rows only on cli side" / "rows only on web side"
    (the legacy behavior).

    Args:
        cli_rows: Row tuples from the CLI run (already projected to compare
            columns and sorted by natural key).
        web_rows: Row tuples from the web run (same projection + sort).
        table_name: Table name used in the failure message header.
        columns: Column names matching the tuple positions.  When supplied
            together with ``natural_key``, the formatter surfaces the
            differing column name(s) for shared-natural-key rows.
        natural_key: Indices into the tuple that form the natural key
            (e.g., ``(0, 1, 2)`` for ``(game_id, perspective_team_id,
            play_order)``).  When supplied together with ``columns``, the
            formatter surfaces value mismatches on shared natural keys.

    Returns:
        Empty string on equality; otherwise a multi-line diff string.
    """
    if cli_rows == web_rows:
        return ""

    lines = [
        f"Plays-stage parity broken on table `{table_name}`:",
        f"  cli rows: {len(cli_rows)}",
        f"  web rows: {len(web_rows)}",
    ]

    cli_set = set(cli_rows)
    web_set = set(web_rows)

    only_cli = [r for r in cli_rows if r not in web_set]
    only_web = [r for r in web_rows if r not in cli_set]

    # When natural-key + columns are supplied, surface value mismatches on
    # rows that share a natural key on both sides (the AC-9(c) contract).
    if columns is not None and natural_key is not None:
        def _key(r: tuple) -> tuple:
            return tuple(r[i] for i in natural_key)

        cli_by_key: dict[tuple, list[tuple]] = {}
        for r in only_cli:
            cli_by_key.setdefault(_key(r), []).append(r)
        web_by_key: dict[tuple, list[tuple]] = {}
        for r in only_web:
            web_by_key.setdefault(_key(r), []).append(r)

        shared_keys = sorted(set(cli_by_key) & set(web_by_key))
        if shared_keys:
            lines.append(
                f"  value mismatches on shared natural keys ({len(shared_keys)}):"
            )
            for k in shared_keys[:10]:
                cli_r = cli_by_key[k][0]
                web_r = web_by_key[k][0]
                lines.append(f"    natural key {k}:")
                for idx, col in enumerate(columns):
                    if idx in natural_key:
                        continue
                    if cli_r[idx] != web_r[idx]:
                        lines.append(
                            f"      column '{col}' "
                            f"(cli={cli_r[idx]!r}, web={web_r[idx]!r})"
                        )
            if len(shared_keys) > 10:
                lines.append(f"    ... and {len(shared_keys) - 10} more")

            # Strip the rows whose mismatch we just surfaced from the
            # only_cli/only_web lists so we don't double-print them as
            # "rows only on X side".
            shared_set = set(shared_keys)
            only_cli = [r for r in only_cli if _key(r) not in shared_set]
            only_web = [r for r in only_web if _key(r) not in shared_set]

    if only_cli:
        lines.append(f"  rows only on cli side ({len(only_cli)}):")
        for r in only_cli[:10]:  # cap output for huge diffs
            lines.append(f"    {r}")
        if len(only_cli) > 10:
            lines.append(f"    ... and {len(only_cli) - 10} more")
    if only_web:
        lines.append(f"  rows only on web side ({len(only_web)}):")
        for r in only_web[:10]:
            lines.append(f"    {r}")
        if len(only_web) > 10:
            lines.append(f"    ... and {len(only_web) - 10} more")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff-formatter unit tests (AC-9)
# ---------------------------------------------------------------------------


def test_format_row_diff_identical_returns_empty_string():
    """AC-9(a): identical row sets produce empty diff."""
    rows = [(1, "a"), (2, "b")]
    assert format_row_diff(rows, list(rows), "plays") == ""


def test_format_row_diff_missing_row_named():
    """AC-9(b): row missing from one side is named in the diff."""
    cli = [(1, "a"), (2, "b")]
    web = [(1, "a")]
    diff = format_row_diff(cli, web, "plays")
    assert diff != ""
    assert "plays" in diff
    assert "rows only on cli side" in diff
    assert "(2, 'b')" in diff


def test_format_row_diff_value_mismatch_names_both():
    """AC-9(c): when a shared natural key has a value mismatch, the column name and both values surface."""
    cli = [(1, "a", "expected")]
    web = [(1, "a", "actual")]
    diff = format_row_diff(
        cli,
        web,
        "plays",
        columns=["game_id", "perspective_team_id", "outcome"],
        natural_key=(0, 1),
    )
    assert diff != ""
    assert "plays" in diff
    # AC-9(c): the differing column name is surfaced explicitly.
    assert "'outcome'" in diff
    # Both values appear in the diff.
    assert "expected" in diff
    assert "actual" in diff


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _patch_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.gamechanger.client.dotenv_values",
        lambda *_a, **_kw: _FAKE_CREDENTIALS,
    )


def _patch_token_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_tm = MagicMock()
    mock_tm.get_access_token.return_value = "fake-access-token"
    mock_tm.force_refresh.return_value = "fake-access-token"
    monkeypatch.setattr("src.gamechanger.client.TokenManager", lambda **_: mock_tm)


def _seed_db(
    db_path: Path,
    seed_boxscore_for_plays,
) -> tuple[int, int]:
    """Apply migrations and seed teams/season/players/games + boxscore rows.

    Returns ``(perspective_team_id, opponent_team_id)``.  The home team uses
    the perspective.
    """
    run_migrations(db_path=db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        # Force deterministic ids so both runs share the same perspective.
        conn.execute(
            "INSERT INTO teams (id, name, membership_type, public_id, "
            "season_year, gc_uuid) "
            "VALUES (1, 'Tracked Opp', 'tracked', ?, 2026, "
            "'aaaa1111-cccc-dddd-eeee-ffff00000001')",
            (_PUBLIC_ID,),
        )
        conn.execute(
            "INSERT INTO teams (id, name, membership_type, gc_uuid) "
            "VALUES (2, 'Other Side', 'tracked', "
            "'aaaa2222-cccc-dddd-eeee-ffff00000002')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO seasons (season_id, name, season_type, year) "
            "VALUES (?, 'Spring 2026', 'spring-hs', 2026)",
            (_SEASON_ID,),
        )
        for pid, fn, ln in [
            (_BATTER_1, "Batter", "One"),
            (_BATTER_2, "Batter", "Two"),
            (_PITCHER_1, "Pitcher", "One"),
            (_PITCHER_2, "Pitcher", "Two"),
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
                "VALUES (?, ?, ?)",
                (pid, fn, ln),
            )
        conn.commit()

        # Seed boxscore + games rows for both games via the shared fixture.
        # Per AC-3, populating `appearance_order` is required for reconcile.
        seed_boxscore_for_plays(
            conn,
            game_id=_GAME_ID_1,
            home_team_id=1,
            away_team_id=2,
            season_id=_SEASON_ID,
            perspective_team_id=1,
            pitcher_appearances=[
                {
                    "team_id": 2,
                    "player_id": _PITCHER_1,
                    "appearance_order": 1,
                    "ip_outs": 9,
                    "bf": 3,
                    "pitches": 9,
                    "total_strikes": 6,
                },
            ],
            batter_appearances=[
                {"team_id": 2, "player_id": _BATTER_1, "ab": 3, "h": 3},
            ],
        )
        seed_boxscore_for_plays(
            conn,
            game_id=_GAME_ID_2,
            home_team_id=1,
            away_team_id=2,
            season_id=_SEASON_ID,
            perspective_team_id=1,
            pitcher_appearances=[
                {
                    "team_id": 2,
                    "player_id": _PITCHER_2,
                    "appearance_order": 1,
                    "ip_outs": 6,
                    "bf": 2,
                    "pitches": 6,
                    "total_strikes": 4,
                },
            ],
            batter_appearances=[
                {"team_id": 2, "player_id": _BATTER_2, "ab": 2, "h": 2},
            ],
        )

        # Pre-seed a scouting_runs row so the web path's freshness gate
        # doesn't short-circuit before plays runs.
        conn.execute(
            "INSERT INTO scouting_runs "
            "(team_id, season_id, status, last_checked) "
            "VALUES (1, ?, 'running', '2099-12-31T00:00:00.000Z')",
            (_SEASON_ID,),
        )
        conn.commit()

    return 1, 2


def _make_crawl_result(boxscore_keys: list[str]) -> ScoutingCrawlResult:
    """Build a deterministic ScoutingCrawlResult with given boxscore game IDs."""
    return ScoutingCrawlResult(
        team_id=1,
        season_id=_SEASON_ID,
        public_id=_PUBLIC_ID,
        games=[{"id": gid, "game_status": "completed"} for gid in boxscore_keys],
        roster=[],
        boxscores={gid: {} for gid in boxscore_keys},
        games_crawled=len(boxscore_keys),
    )


def _make_fake_get(plays_json_by_game: dict[str, dict]):
    """Build a fake `client.get(...)` callable returning canned plays JSON."""

    def _fake_get(path: str, *args, **kwargs):
        if "plays" in path:
            for gid, payload in plays_json_by_game.items():
                if gid in path:
                    return payload
            raise KeyError(f"unexpected plays path: {path}")
        return {}

    return _fake_get


def _client_factory(fake_get):
    def _factory(*args, **kwargs):
        c = MagicMock()
        c.get.side_effect = fake_get
        return c
    return _factory


def _extract_plays_rows(db_path: Path, perspective_team_id: int) -> list[tuple]:
    """Extract `plays` rows for parity comparison (AC-4 column subset)."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        return conn.execute(
            """
            SELECT game_id, perspective_team_id, play_order, batter_id,
                   pitcher_id, outcome, is_first_pitch_strike, is_qab,
                   pitch_count
            FROM plays
            WHERE perspective_team_id = ?
            ORDER BY game_id, play_order
            """,
            (perspective_team_id,),
        ).fetchall()


def _extract_play_events_rows(
    db_path: Path,
    perspective_team_id: int,
) -> list[tuple]:
    """Extract `play_events` rows joined to `plays` via natural key (AC-5)."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        return conn.execute(
            """
            SELECT p.game_id, p.perspective_team_id, p.play_order,
                   pe.event_order, pe.event_type, pe.pitch_result,
                   pe.is_first_pitch
            FROM play_events pe
            JOIN plays p ON pe.play_id = p.id
            WHERE p.perspective_team_id = ?
            ORDER BY p.game_id, p.play_order, pe.event_order
            """,
            (perspective_team_id,),
        ).fetchall()


def _extract_reconciliation_rows(
    db_path: Path,
    perspective_team_id: int,
) -> list[tuple]:
    """Extract `reconciliation_discrepancies` rows for parity comparison (AC-6)."""
    with closing(sqlite3.connect(str(db_path))) as conn:
        return conn.execute(
            """
            SELECT game_id, perspective_team_id, team_id, player_id,
                   signal_name, category, boxscore_value, plays_value
            FROM reconciliation_discrepancies
            WHERE perspective_team_id = ?
            ORDER BY game_id, team_id, player_id, signal_name
            """,
            (perspective_team_id,),
        ).fetchall()


# ---------------------------------------------------------------------------
# Parity test (AC-1 through AC-8)
# ---------------------------------------------------------------------------


def test_plays_stage_parity_cli_vs_web(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plays_json_factory,
    seed_boxscore_for_plays,
) -> None:
    """The CLI and web scout paths produce equivalent plays/play_events/reconciliation data.

    This is the executable form of CLAUDE.md's "Scouting pipeline parity"
    architectural invariant for the plays stage.  When this test fails, the
    invariant has been broken: a future change to one path drifted away from
    the other.  The diff-formatter helper output names the offending table
    and rows.
    """
    _patch_credentials(monkeypatch)
    _patch_token_manager(monkeypatch)

    cli_db = tmp_path / "cli.db"
    web_db = tmp_path / "web.db"

    # Seed identical state into both DBs.
    cli_team_id, _ = _seed_db(cli_db, seed_boxscore_for_plays)
    web_team_id, _ = _seed_db(web_db, seed_boxscore_for_plays)
    assert cli_team_id == web_team_id == 1

    # Identical canned plays JSON for both paths -- AC-2 guarantees the same
    # `perspective_team_id` is used on both runs, so plays are tagged
    # identically.
    plays_by_game = {
        _GAME_ID_1: plays_json_factory(_GAME_ID_1, _PITCHER_1, _BATTER_1, num_plays=3),
        _GAME_ID_2: plays_json_factory(_GAME_ID_2, _PITCHER_2, _BATTER_2, num_plays=2),
    }

    cr = _make_crawl_result([_GAME_ID_1, _GAME_ID_2])
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = cr
    mock_crawler.scout_all_in_memory.return_value = [cr]
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=5, errors=0)
    mock_spray_crawler = MagicMock()
    spray_result = MagicMock()
    spray_result.files_written = 0
    spray_result.files_skipped = 0
    spray_result.errors = 0
    spray_result.games_crawled = 0
    spray_result.games_skipped = 0
    spray_result.spray_data = {}
    mock_spray_crawler.crawl_team.return_value = spray_result

    fake_get = _make_fake_get(plays_by_game)

    # ---------------- CLI run ----------------
    runner = CliRunner()
    with (
        patch(
            "src.gamechanger.client.GameChangerClient",
            side_effect=_client_factory(fake_get),
        ),
        patch(
            "src.gamechanger.crawlers.scouting.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.gamechanger.loaders.scouting_loader.ScoutingLoader"),
        patch("src.cli.data._load_scouted_team_in_memory", return_value=0),
        patch(
            "src.gamechanger.crawlers.scouting_spray.ScoutingSprayChartCrawler",
            return_value=mock_spray_crawler,
        ),
        patch("src.cli.data._resolve_db_path", return_value=cli_db),
    ):
        cli_result = runner.invoke(app, ["data", "scout", "--team", _PUBLIC_ID])
    assert cli_result.exit_code == 0, cli_result.output

    # ---------------- Web run ----------------
    # Per AC-7, patch the imported binding inside `src.pipeline.trigger`.
    # This is the canonical seam used by tests/test_trigger.py:214.  Patching
    # `src.api.db.get_db_path` does NOT work because the trigger module
    # imports the symbol at module load time.
    web_crawl_job_id = 0
    with closing(sqlite3.connect(str(web_db))) as conn:
        cur = conn.execute(
            "INSERT INTO crawl_jobs (team_id, sync_type, status, started_at) "
            "VALUES (1, 'scouting_crawl', 'running', datetime('now'))",
        )
        web_crawl_job_id = cur.lastrowid
        conn.commit()

    with (
        patch("src.pipeline.trigger.get_db_path", return_value=web_db),
        patch(
            "src.pipeline.trigger._refresh_auth_token",
            side_effect=_client_factory(fake_get),
        ),
        patch(
            "src.pipeline.trigger.ScoutingCrawler",
            return_value=mock_crawler,
        ),
        patch("src.pipeline.trigger.ScoutingLoader", return_value=mock_loader),
        patch("src.pipeline.trigger.resolve_gc_uuid", return_value=None),
        patch("src.pipeline.trigger._run_spray_stages"),
    ):
        trigger.run_scouting_sync(1, _PUBLIC_ID, web_crawl_job_id)

    # ---------------- Compare ----------------
    # Column lists + natural keys mirror the SELECTs in the _extract_*
    # helpers above; AC-9(c) -- value mismatches on shared natural keys
    # surface the column name + both sides' values.
    plays_columns = [
        "game_id", "perspective_team_id", "play_order", "batter_id",
        "pitcher_id", "outcome", "is_first_pitch_strike", "is_qab",
        "pitch_count",
    ]
    plays_natural_key = (0, 1, 2)  # (game_id, perspective_team_id, play_order)

    play_events_columns = [
        "game_id", "perspective_team_id", "play_order", "event_order",
        "event_type", "pitch_result", "is_first_pitch",
    ]
    play_events_natural_key = (0, 1, 2, 3)
    # (game_id, perspective_team_id, play_order, event_order)

    recon_columns = [
        "game_id", "perspective_team_id", "team_id", "player_id",
        "signal_name", "category", "boxscore_value", "plays_value",
    ]
    recon_natural_key = (0, 1, 2, 3, 4, 5)
    # (game_id, perspective_team_id, team_id, player_id, signal_name, category)

    cli_plays = _extract_plays_rows(cli_db, perspective_team_id=1)
    web_plays = _extract_plays_rows(web_db, perspective_team_id=1)
    plays_diff = format_row_diff(
        cli_plays, web_plays, "plays",
        columns=plays_columns, natural_key=plays_natural_key,
    )
    assert plays_diff == "", plays_diff
    # Sanity: both paths actually loaded plays.
    assert len(cli_plays) == 5  # 3 + 2 plays from the two seeded games

    cli_events = _extract_play_events_rows(cli_db, perspective_team_id=1)
    web_events = _extract_play_events_rows(web_db, perspective_team_id=1)
    events_diff = format_row_diff(
        cli_events, web_events, "play_events",
        columns=play_events_columns, natural_key=play_events_natural_key,
    )
    assert events_diff == "", events_diff
    assert len(cli_events) > 0  # at-plate-detail events were inserted

    cli_recon = _extract_reconciliation_rows(cli_db, perspective_team_id=1)
    web_recon = _extract_reconciliation_rows(web_db, perspective_team_id=1)
    recon_diff = format_row_diff(
        cli_recon, web_recon, "reconciliation_discrepancies",
        columns=recon_columns, natural_key=recon_natural_key,
    )
    assert recon_diff == "", recon_diff
