"""Tests for `bb data merge-duplicate-games` (E-261-04, the operator repair pass).

The command performs two OFFLINE repair actions over an already-persisted DB:
(1) detect + merge cross-perspective duplicate game pairs via
``merge_duplicate_game()``, and (2) restore ``game_stream_id`` values poisoned by
the pre-fix redirect clobber. Dry-run by default; --execute applies; failure
model is continue-per-item with a non-zero exit iff any item failed.

Covers:
- AC-1: dry-run prints the plan (ids, dates, teams, scores, child-table counts,
  per-pair play counts) and writes NOTHING.
- AC-2: --execute merges via the helper, CLI commits, re-run is idempotent.
- AC-3: an ambiguous group is REFUSED (WARN, unmerged) without a non-zero exit;
  and a pair failing the near/matching play-count corroboration is REFUSED
  (AC-6 detection: Codex P1-2).
- AC-4: stream-id restore scoping -- tracked-only games restored, member-
  perspective games never touched, idempotent re-run.
- AC-5: continue-per-item -- an injected item failure is rolled back, the run
  continues, and the command exits non-zero.
- AC-6: the CLI imports and REUSES ``is_offline_same_game`` from
  ``src/db/game_merge.py`` rather than re-inlining the predicate.

All tests use an on-disk temp DB with the full migration set (via
``load_real_schema``); the CLI opens its own connection against ``--db``.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.db import game_merge
from tests.conftest import load_real_schema

runner = CliRunner()

_SEASON = "2026"
_DATE = "2026-04-10"
_BATTER = "ba11e100-0001-0001-0001-000000000001"
_PITCHER = "01c4e100-0001-0001-0001-000000000001"

# Team ids: 1 = our member team, 2 = a tracked opponent, 3 = another tracked team.
_MEMBER = 1
_TRACKED = 2
_TRACKED_2 = 3


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _make_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "merge.db"
    conn = sqlite3.connect(str(db_file))
    load_real_schema(conn)
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES (?, 'Spring 2026', 2026)",
        (_SEASON,),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, 'LSB', 'member')",
        (_MEMBER,),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, 'Opp A', 'tracked')",
        (_TRACKED,),
    )
    conn.execute(
        "INSERT INTO teams (id, name, membership_type) VALUES (?, 'Opp B', 'tracked')",
        (_TRACKED_2,),
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Bat', 'Ter')",
        (_BATTER,),
    )
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) VALUES (?, 'Pit', 'Cher')",
        (_PITCHER,),
    )
    conn.commit()
    conn.close()
    return db_file


def _insert_game(
    conn: sqlite3.Connection,
    game_id: str,
    *,
    home: int,
    away: int,
    home_score: int,
    away_score: int,
    created_at: str,
    game_stream_id: str | None = None,
    game_date: str = _DATE,
) -> None:
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, home_score, away_score, status, game_stream_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)",
        (
            game_id,
            _SEASON,
            game_date,
            home,
            away,
            home_score,
            away_score,
            game_stream_id if game_stream_id is not None else game_id,
            created_at,
        ),
    )


def _add_perspective(conn: sqlite3.Connection, game_id: str, perspective: int) -> None:
    conn.execute(
        "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?, ?)",
        (game_id, perspective),
    )


def _add_plays(
    conn: sqlite3.Connection, game_id: str, perspective: int, n: int
) -> None:
    """Insert n plays (+ one play_events child each) from a perspective."""
    for i in range(n):
        cur = conn.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome) "
            "VALUES (?, ?, 1, 'top', ?, ?, ?, ?, ?, 'Single')",
            (game_id, i, _SEASON, perspective, perspective, _BATTER, _PITCHER),
        )
        conn.execute(
            "INSERT INTO play_events (play_id, event_order, event_type, pitch_result) "
            "VALUES (?, 0, 'pitch', 'in_play')",
            (cur.lastrowid,),
        )


def _seed_twin_pair(
    conn: sqlite3.Connection,
    *,
    canonical_id: str,
    source_id: str,
    canonical_persp: int = _MEMBER,
    source_persp: int = _TRACKED,
    canonical_score: tuple[int, int] = (12, 4),
    source_score: tuple[int, int] = (12, 5),
    canonical_plays: int = 20,
    source_plays: int = 20,
) -> None:
    """A clean cross-perspective twin: disjoint single perspectives, near scores
    and play counts (passes is_offline_same_game). Canonical is created FIRST."""
    _insert_game(
        conn,
        canonical_id,
        home=_MEMBER,
        away=_TRACKED,
        home_score=canonical_score[0],
        away_score=canonical_score[1],
        created_at="2026-04-10 10:00:00",
    )
    _insert_game(
        conn,
        source_id,
        home=_TRACKED,
        away=_MEMBER,
        home_score=source_score[0],
        away_score=source_score[1],
        created_at="2026-04-10 11:00:00",
    )
    _add_perspective(conn, canonical_id, canonical_persp)
    _add_perspective(conn, source_id, source_persp)
    _add_plays(conn, canonical_id, canonical_persp, canonical_plays)
    _add_plays(conn, source_id, source_persp, source_plays)


def _open(db_file: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _game_ids(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT game_id FROM games")}


def _invoke(db_file: Path, *args: str):
    return runner.invoke(app, ["data", "merge-duplicate-games", "--db", str(db_file), *args])


# ---------------------------------------------------------------------------
# AC-1: dry-run prints the plan and writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_prints_plan_and_writes_nothing(tmp_path: Path) -> None:
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    _seed_twin_pair(conn, canonical_id="game-canon", source_id="game-source")
    conn.commit()
    before = _game_ids(conn)
    conn.close()

    result = _invoke(db_file)

    assert result.exit_code == 0, result.output
    out = result.output
    # Plan surfaces the ids, date, teams, scores, child-table counts, play counts.
    assert "game-source -> game-canon" in out
    assert _DATE in out
    assert "teams=(1, 2)" in out
    assert "scores src=(12, 5) canon=(12, 4)" in out
    assert "plays src=20 canon=20" in out
    assert "child rows:" in out
    assert "plays=20" in out
    assert "DRY RUN" in out

    # Nothing was written.
    conn = _open(db_file)
    assert _game_ids(conn) == before
    conn.close()


def test_no_vestigial_dry_run_flag(tmp_path: Path) -> None:
    # Codex P3: the command must NOT advertise an inert `--dry-run` flag that a
    # `--dry-run --execute` combination would silently override toward EXECUTE.
    # Matching the `fix-self-games` precedent, dry-run is the default and
    # `--execute` is the ONLY writer, so `--dry-run` is rejected as unknown and
    # no flag combination can silently execute writes against a dry-run intent.
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    _seed_twin_pair(conn, canonical_id="game-canon", source_id="game-source")
    conn.commit()
    before = _game_ids(conn)
    conn.close()

    result = _invoke(db_file, "--dry-run")
    assert result.exit_code != 0  # typer rejects the unknown option
    assert "--dry-run" in result.output  # names the offending option

    # And the (now impossible) contradictory combo never runs: DB untouched.
    conn = _open(db_file)
    assert _game_ids(conn) == before
    conn.close()


# ---------------------------------------------------------------------------
# AC-2: --execute merges via the helper, commits, idempotent re-run
# ---------------------------------------------------------------------------


def test_execute_merges_and_is_idempotent(tmp_path: Path) -> None:
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    _seed_twin_pair(conn, canonical_id="game-canon", source_id="game-source")
    conn.commit()
    conn.close()

    result = _invoke(db_file, "--execute")
    assert result.exit_code == 0, result.output
    assert "MERGED game-source -> game-canon" in result.output

    conn = _open(db_file)
    # Source game deleted; canonical survives with both perspectives.
    assert _game_ids(conn) == {"game-canon"}
    persps = {
        row[0]
        for row in conn.execute(
            "SELECT perspective_team_id FROM game_perspectives WHERE game_id = 'game-canon'"
        )
    }
    assert persps == {_MEMBER, _TRACKED}
    # All 40 plays (20 + 20 re-pointed) now hang off the canonical game.
    assert conn.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = 'game-canon'"
    ).fetchone()[0] == 40
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()

    # Idempotent: a second run reports zero remaining pairs, exit 0.
    result2 = _invoke(db_file, "--execute")
    assert result2.exit_code == 0, result2.output
    assert "0 duplicate pair(s) to merge" in result2.output


# ---------------------------------------------------------------------------
# AC-3: refusals (ambiguous group; failed play-count corroboration)
# ---------------------------------------------------------------------------


def test_three_row_group_refused_without_nonzero_exit(tmp_path: Path) -> None:
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    # Three rows share the same date/team-pair -> ambiguous, REFUSE.
    for i, persp in enumerate((_MEMBER, _TRACKED, _MEMBER)):
        gid = f"tri-{i}"
        _insert_game(
            conn,
            gid,
            home=_MEMBER,
            away=_TRACKED,
            home_score=5,
            away_score=3,
            created_at=f"2026-04-10 1{i}:00:00",
        )
        _add_perspective(conn, gid, persp)
        _add_plays(conn, gid, persp, 10)
    conn.commit()
    before = _game_ids(conn)
    conn.close()

    result = _invoke(db_file, "--execute")
    # Refusal alone must NOT fail the run.
    assert result.exit_code == 0, result.output
    assert "refused" in result.output.lower()
    # Nothing merged.
    conn = _open(db_file)
    assert _game_ids(conn) == before
    conn.close()


def test_pair_failing_playcount_corroboration_refused(tmp_path: Path) -> None:
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    # Disjoint single perspectives + near scores, but play counts are far apart
    # (20 vs 3 -> ratio 0.15 < 0.85). Codex P1-2: the play-count safeguard is a
    # REQUIRED inclusion gate -> REFUSE.
    _seed_twin_pair(
        conn,
        canonical_id="pc-canon",
        source_id="pc-source",
        canonical_plays=20,
        source_plays=3,
    )
    conn.commit()
    before = _game_ids(conn)
    conn.close()

    # Detection: this pair is refused, not planned.
    conn = _open(db_file)
    plan = game_merge.plan_duplicate_game_merges(conn)
    conn.close()
    assert plan.merges == []
    assert len(plan.refusals) == 1
    assert "play" in plan.refusals[0].reason.lower()

    result = _invoke(db_file, "--execute")
    assert result.exit_code == 0, result.output
    conn = _open(db_file)
    assert _game_ids(conn) == before  # nothing merged
    conn.close()


# ---------------------------------------------------------------------------
# AC-4: stream-id restore scoping + idempotency
# ---------------------------------------------------------------------------


def test_stream_id_restore_scoping_and_idempotency(tmp_path: Path) -> None:
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    # Two "real" games whose ids the poisoned rows point at (corroboration).
    # Their OWN game_stream_id is some distinct real stream id, so the poisoned
    # values below stay globally unique under migration 010's partial UNIQUE
    # index on games(game_stream_id).
    _insert_game(
        conn,
        "real-game",
        home=_MEMBER,
        away=_TRACKED,
        home_score=1,
        away_score=0,
        created_at="2026-04-01 10:00:00",
        game_stream_id="real-game-stream",
        game_date="2026-04-01",
    )
    _add_perspective(conn, "real-game", _MEMBER)
    _insert_game(
        conn,
        "real-game-2",
        home=_MEMBER,
        away=_TRACKED,
        home_score=6,
        away_score=2,
        created_at="2026-04-01 12:00:00",
        game_stream_id="real-game-2-stream",
        game_date="2026-04-01",
    )
    _add_perspective(conn, "real-game-2", _MEMBER)

    # Poisoned tracked-only game: game_stream_id equals real-game's game_id.
    _insert_game(
        conn,
        "poisoned-tracked",
        home=_TRACKED,
        away=_TRACKED_2,
        home_score=2,
        away_score=2,
        created_at="2026-04-02 10:00:00",
        game_stream_id="real-game",
        game_date="2026-04-02",
    )
    _add_perspective(conn, "poisoned-tracked", _TRACKED)

    # Poisoned game that ALSO carries a member perspective -> must NOT be touched.
    # Distinct poisoned value (equals real-game-2's game_id) to avoid the UNIQUE.
    _insert_game(
        conn,
        "poisoned-member",
        home=_MEMBER,
        away=_TRACKED,
        home_score=3,
        away_score=1,
        created_at="2026-04-03 10:00:00",
        game_stream_id="real-game-2",
        game_date="2026-04-03",
    )
    _add_perspective(conn, "poisoned-member", _MEMBER)

    # A tracked game whose game_stream_id differs but corroborates nothing ->
    # must NOT be restored (hard corroboration, never a bare value-differs).
    _insert_game(
        conn,
        "bare-differ",
        home=_TRACKED,
        away=_TRACKED_2,
        home_score=4,
        away_score=4,
        created_at="2026-04-04 10:00:00",
        game_stream_id="some-unrelated-stream-id",
        game_date="2026-04-04",
    )
    _add_perspective(conn, "bare-differ", _TRACKED)
    conn.commit()
    conn.close()

    result = _invoke(db_file, "--execute")
    assert result.exit_code == 0, result.output
    assert "RESTORED poisoned-tracked" in result.output

    conn = _open(db_file)

    def _stream(gid: str) -> str:
        return conn.execute(
            "SELECT game_stream_id FROM games WHERE game_id = ?", (gid,)
        ).fetchone()[0]

    # Tracked-only poisoned row self-keyed.
    assert _stream("poisoned-tracked") == "poisoned-tracked"
    # Member-perspective poisoned row untouched.
    assert _stream("poisoned-member") == "real-game-2"
    # Bare value-differs (no corroboration) untouched.
    assert _stream("bare-differ") == "some-unrelated-stream-id"
    conn.close()

    # Idempotent: a second run restores nothing.
    result2 = _invoke(db_file, "--execute")
    assert result2.exit_code == 0, result2.output
    assert "0 stream-id restore(s)" in result2.output


# ---------------------------------------------------------------------------
# AC-5: continue-per-item failure model -> rollback + continue + non-zero exit
# ---------------------------------------------------------------------------


def test_continue_per_item_failure_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = _make_db(tmp_path)
    conn = _open(db_file)
    # Two independent clean twin pairs on different dates.
    _seed_twin_pair(conn, canonical_id="ok-canon", source_id="ok-source")
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
        "home_score, away_score, status, game_stream_id, created_at) "
        "VALUES ('bad-canon', ?, '2026-05-01', ?, ?, 7, 2, 'completed', 'bad-canon', "
        "'2026-05-01 10:00:00')",
        (_SEASON, _MEMBER, _TRACKED),
    )
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, away_team_id, "
        "home_score, away_score, status, game_stream_id, created_at) "
        "VALUES ('bad-source', ?, '2026-05-01', ?, ?, 7, 3, 'completed', 'bad-source', "
        "'2026-05-01 11:00:00')",
        (_SEASON, _TRACKED, _MEMBER),
    )
    _add_perspective(conn, "bad-canon", _MEMBER)
    _add_perspective(conn, "bad-source", _TRACKED)
    _add_plays(conn, "bad-canon", _MEMBER, 15)
    _add_plays(conn, "bad-source", _TRACKED, 15)
    conn.commit()
    conn.close()

    # Inject a failure on the SECOND pair's merge only, leaving the first intact.
    real_merge = game_merge.merge_duplicate_game

    def _failing_merge(conn, source_game_id, canonical_game_id):  # noqa: ANN001, ANN202
        if source_game_id == "bad-source":
            # Partially write, then fail -- proves the CLI rolls the partial back.
            conn.execute(
                "UPDATE plays SET game_id = ? WHERE game_id = ?",
                (canonical_game_id, source_game_id),
            )
            raise sqlite3.OperationalError("injected merge failure")
        return real_merge(conn, source_game_id, canonical_game_id)

    monkeypatch.setattr(
        "src.cli.data.merge_duplicate_game", _failing_merge, raising=False
    )
    # The CLI imports the name into its function scope from src.db.game_merge, so
    # patch the source too (belt and suspenders across import styles).
    monkeypatch.setattr(game_merge, "merge_duplicate_game", _failing_merge)

    result = _invoke(db_file, "--execute")

    # One item failed -> non-zero exit, but the run CONTINUED (first pair merged).
    assert result.exit_code == 1, result.output
    assert "MERGED ok-source -> ok-canon" in result.output
    assert "ERROR merging bad-source" in result.output

    conn = _open(db_file)
    # First pair merged; failed pair's partial write was rolled back (both rows
    # still present, plays still on the source).
    assert "ok-source" not in _game_ids(conn)
    assert {"bad-canon", "bad-source"} <= _game_ids(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM plays WHERE game_id = 'bad-source'"
    ).fetchone()[0] == 15
    conn.close()


# ---------------------------------------------------------------------------
# AC-6: the CLI reuses is_offline_same_game rather than re-inlining it
# ---------------------------------------------------------------------------


def test_cli_reuses_offline_predicate_not_reinlined() -> None:
    # The offline same-game decision lives ONLY in src/db/game_merge.py. The CLI
    # plan path (plan_duplicate_game_merges) must call is_offline_same_game, and
    # src/cli/data.py must NOT re-inline the predicate.
    game_merge_src = Path(game_merge.__file__).read_text()
    tree = ast.parse(game_merge_src)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "is_offline_same_game" in called_names, (
        "plan_duplicate_game_merges must reuse is_offline_same_game"
    )

    cli_src = (Path(game_merge.__file__).parent.parent / "cli" / "data.py").read_text()
    # The CLI imports the plan functions; it must NOT define its own predicate or
    # re-inline the score/play-count corroboration constants.
    assert "plan_duplicate_game_merges" in cli_src
    assert "_SCORE_TOLERANCE_RUNS" not in cli_src
    assert "_PLAY_COUNT_NEAR_RATIO" not in cli_src
    assert "def is_offline_same_game" not in cli_src
