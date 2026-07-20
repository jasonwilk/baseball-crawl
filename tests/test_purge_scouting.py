"""Tests for ``bb db purge-scouting`` (E-267-06).

The purge is the most destructive command in the system and runs against LIVE
production data, so the high-value coverage here is the safety machinery rather
than feature completeness:

- AC-1 / AC-8: every PURGE table empties, every KEEP table survives, an existing
  user's login capability is intact, and the on-disk report HTML is unlinked.
- AC-3: FK enforcement is LIVE, proven by deliberately reordering a delete and
  asserting it RAISES -- the difference between "FK-safe order is enforced" and
  "FK-safe order is merely intended" is silent orphaning that looks like a pass.
- AC-7: the KEEP/PURGE partition is re-derived from ``sqlite_master`` so a future
  migration cannot add a table that falls through it unclassified.
- AC-9: the production guard refuses without ``--force``, including the
  whitespace/case variant (IDEA-101) that motivated routing through
  ``is_production()`` instead of ``reset.py``'s ``.lower() ==`` body.
- AC-10: a mid-purge failure rolls back to no half-state, and a missing on-disk
  file does not abort the purge.

Report-path resolution is pointed at ``tmp_path`` via the module's ``_REPO_ROOT``
seam -- no test ever touches the real ``data/reports/`` tree.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from migrations.apply_migrations import run_migrations
from src.db import purge_scouting as purge_mod
from src.db.purge_scouting import (
    KEEP_TABLES,
    PURGE_DELETE_ORDER,
    PURGE_TABLES,
    check_purge_production_guard,
    purge_scouting_data,
)

# ---------------------------------------------------------------------------
# Fixtures / seeding
# ---------------------------------------------------------------------------

_REPORT_REL_PATH = "reports/report-abc.html"


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """A migrated database file (the purge opens its own connection to it)."""
    path = tmp_path / "purge.db"
    run_migrations(db_path=path)
    return path


@pytest.fixture()
def repo_root(tmp_path: Path):
    """Point the module's report-path resolution at tmp_path, not the repo."""
    with patch.object(purge_mod, "_REPO_ROOT", tmp_path):
        yield tmp_path


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _seed(db_path: Path, repo_root: Path) -> None:
    """Seed identity/auth rows, scouting rows, and one on-disk report HTML."""
    conn = _conn(db_path)

    # --- identity + auth (KEEP) ---------------------------------------------
    user_id = conn.execute(
        "INSERT INTO users (email, role) VALUES ('coach@example.com', 'user')"
    ).lastrowid
    conn.execute(
        "INSERT INTO passkey_credentials (credential_id, user_id, public_key) "
        "VALUES ('cred-1', ?, 'pubkey')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO magic_link_tokens (token, user_id, expires_at) "
        "VALUES ('tok-1', ?, '2099-01-01T00:00:00Z')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) "
        "VALUES ('sess-1', ?, '2099-01-01T00:00:00Z')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO webauthn_challenges (kind, lookup_key, challenge) "
        "VALUES ('login', 'lk-1', 'chal')"
    )

    # --- scouting / report data (PURGE) -------------------------------------
    conn.execute(
        "INSERT INTO seasons (season_id, name, year) VALUES ('2026', '2026', 2026)"
    )
    team_id = conn.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('Team A', 'tracked', 1, 2026)"
    ).lastrowid
    opp_id = conn.execute(
        "INSERT INTO teams (name, membership_type, is_active, season_year) "
        "VALUES ('Opp', 'tracked', 1, 2026)"
    ).lastrowid
    conn.execute(
        "INSERT INTO players (player_id, first_name, last_name) "
        "VALUES ('p-1', 'John', 'Doe')"
    )
    conn.execute(
        "INSERT INTO team_rosters (team_id, player_id, season_id) "
        "VALUES (?, 'p-1', '2026')",
        (team_id,),
    )
    conn.execute(
        "INSERT INTO games (game_id, season_id, game_date, home_team_id, "
        "away_team_id, status) VALUES ('g-1', '2026', '2026-04-10', ?, ?, "
        "'completed')",
        (team_id, opp_id),
    )
    conn.execute(
        "INSERT INTO game_perspectives (game_id, perspective_team_id) "
        "VALUES ('g-1', ?)",
        (team_id,),
    )
    conn.execute(
        "INSERT INTO player_game_batting (game_id, player_id, team_id, "
        "perspective_team_id, ab) VALUES ('g-1', 'p-1', ?, ?, 3)",
        (team_id, team_id),
    )
    conn.execute(
        "INSERT INTO player_game_pitching (game_id, player_id, team_id, "
        "perspective_team_id, ip_outs) VALUES ('g-1', 'p-1', ?, ?, 6)",
        (team_id, team_id),
    )
    play_id = conn.execute(
        "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
        "batting_team_id, perspective_team_id, batter_id) "
        "VALUES ('g-1', 1, 1, 'top', '2026', ?, ?, 'p-1')",
        (team_id, team_id),
    ).lastrowid
    conn.execute(
        "INSERT INTO play_events (play_id, event_order, event_type) "
        "VALUES (?, 1, 'pitch')",
        (play_id,),
    )
    conn.execute(
        "INSERT INTO spray_charts (game_id, player_id, team_id, "
        "perspective_team_id, chart_type, event_gc_id) "
        "VALUES ('g-1', 'p-1', ?, ?, 'offensive', 'e-1')",
        (team_id, team_id),
    )
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (game_id, run_id, "
        "perspective_team_id, team_id, player_id, signal_name, category, status) "
        "VALUES ('g-1', 'run-1', ?, ?, 'p-1', 'so', 'batting', 'MATCH')",
        (team_id, team_id),
    )
    conn.execute(
        "INSERT INTO scouting_runs (team_id, season_id, run_type, started_at, "
        "status) VALUES (?, '2026', 'full', '2026-04-10T00:00:00Z', 'completed')",
        (team_id,),
    )
    conn.execute(
        "INSERT INTO opponent_links (our_team_id, root_team_id, opponent_name) "
        "VALUES (?, 'root-1', 'Opp')",
        (team_id,),
    )
    conn.execute(
        "INSERT INTO crawl_jobs (team_id, sync_type, status) "
        "VALUES (?, 'scouting_crawl', 'completed')",
        (team_id,),
    )
    conn.execute(
        "INSERT INTO coaching_assignments (user_id, team_id, role) "
        "VALUES (?, ?, 'head')",
        (user_id, team_id),
    )
    conn.execute(
        "INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)",
        (user_id, team_id),
    )
    report_id = conn.execute(
        "INSERT INTO reports (slug, team_id, title, status, expires_at, "
        "report_path) VALUES ('slug-1', ?, 'Report', 'ready', "
        "'2099-01-01T00:00:00Z', ?)",
        (team_id, _REPORT_REL_PATH),
    ).lastrowid
    conn.execute(
        "INSERT INTO report_generation_runs (report_id, overall_status) "
        "VALUES (?, 'completed')",
        (report_id,),
    )
    conn.execute(
        "INSERT INTO scheduled_report_runs (game_date, own_team_id, "
        "opponent_root_team_id, resolution_outcome) "
        "VALUES ('2026-04-10', ?, 'root-1', 'auto_resolved')",
        (team_id,),
    )
    conn.commit()
    conn.close()

    # The on-disk report HTML, under the patched _REPO_ROOT.
    html = repo_root / "data" / _REPORT_REL_PATH
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html>report</html>")


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
    finally:
        conn.close()


def _nonempty_tables(db_path: Path, tables) -> set[str]:
    return {t for t in tables if _count(db_path, t) > 0}


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-8: the partition holds and logins survive
# ---------------------------------------------------------------------------


def test_purge_empties_every_purge_table(db_path: Path, repo_root: Path) -> None:
    """AC-1/AC-8(a): every PURGE table is empty afterwards.

    Includes ``user_team_access``, which is PURGE (authorization), NOT keep --
    the intuitive-but-wrong classification.
    """
    _seed(db_path, repo_root)
    # EVERY purge table must be non-empty before the purge, or the assertions
    # below pass vacuously -- the same trap that made the E-267-02 child-surface
    # assertions meaningless until they were seeded.
    seeded = _nonempty_tables(db_path, PURGE_TABLES)
    assert seeded == PURGE_TABLES, f"unseeded purge tables: {PURGE_TABLES - seeded}"

    purge_scouting_data(db_path=db_path, force=True)

    for table in PURGE_TABLES:
        assert _count(db_path, table) == 0, f"{table} should be empty after purge"


def test_purge_preserves_identity_and_auth(db_path: Path, repo_root: Path) -> None:
    """AC-1/AC-2/AC-8(b,c): KEEP tables survive and login capability is intact."""
    _seed(db_path, repo_root)

    purge_scouting_data(db_path=db_path, force=True)

    for table in KEEP_TABLES:
        assert _count(db_path, table) > 0, f"{table} must survive the purge"

    conn = sqlite3.connect(str(db_path))
    try:
        # Login capability: each auth path still resolves to a live users row.
        for sql, params in (
            (
                "SELECT u.email FROM users u JOIN passkey_credentials p "
                "ON p.user_id = u.id WHERE p.credential_id = ?",
                ("cred-1",),
            ),
            (
                "SELECT u.email FROM users u JOIN magic_link_tokens m "
                "ON m.user_id = u.id WHERE m.token = ?",
                ("tok-1",),
            ),
            (
                "SELECT u.email FROM users u JOIN sessions s "
                "ON s.user_id = u.id WHERE s.session_id = ?",
                ("sess-1",),
            ),
        ):
            row = conn.execute(sql, params).fetchone()
            assert row is not None and row[0] == "coach@example.com"

        # AC-2: the lsb-hs bootstrap programs row survives.
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM programs WHERE program_id = 'lsb-hs'"
            ).fetchone()[0]
            == 1
        )
    finally:
        conn.close()


def test_purge_unlinks_report_html(db_path: Path, repo_root: Path) -> None:
    """AC-5/AC-8(d): the on-disk report file is removed, regardless of expiry.

    The seeded report expires in 2099 -- i.e. it is NOT expired -- so a purge
    built on ``cleanup_expired_reports()`` (which filters ``expires_at < now``)
    would leave this file behind.
    """
    _seed(db_path, repo_root)
    html = repo_root / "data" / _REPORT_REL_PATH
    assert html.is_file()

    result = purge_scouting_data(db_path=db_path, force=True)

    assert not html.exists()
    assert result.files_removed == 1
    assert result.file_errors == 0


# ---------------------------------------------------------------------------
# AC-3: FK enforcement is LIVE, not merely intended
# ---------------------------------------------------------------------------


def test_foreign_keys_are_live_a_misordered_delete_raises(
    db_path: Path, repo_root: Path
) -> None:
    """AC-3: reordering a delete RAISES -- proving FK enforcement is on.

    This is the load-bearing test of the story. ``PRAGMA foreign_keys`` defaults
    to OFF in sqlite3, and ``reset.py`` never enables it, so a naive mirror would
    pass every other test in this file while silently orphaning rows. Deleting
    ``teams`` before its children must fail; if this test ever goes green with
    the raise removed, FK enforcement has been turned off somewhere.
    """
    _seed(db_path, repo_root)

    # ``teams`` first (instead of near-last) -- children still reference it.
    bad_order = ("teams", *PURGE_DELETE_ORDER)
    with patch.object(purge_mod, "PURGE_DELETE_ORDER", bad_order):
        with pytest.raises(sqlite3.IntegrityError):
            purge_scouting_data(db_path=db_path, force=True)

    # And the failed purge left everything intact (rollback, AC-6).
    assert _nonempty_tables(db_path, PURGE_TABLES) == PURGE_TABLES


def test_purge_refuses_when_foreign_keys_are_off(
    db_path: Path, repo_root: Path
) -> None:
    """AC-3: the runtime FK assertion fails loudly rather than orphaning."""
    _seed(db_path, repo_root)

    def _fk_off_connection(path):
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys=OFF;")
        return conn

    with patch.object(purge_mod, "get_connection", _fk_off_connection):
        with pytest.raises(RuntimeError, match="foreign_keys is OFF"):
            purge_scouting_data(db_path=db_path, force=True)

    assert _nonempty_tables(db_path, PURGE_TABLES) == PURGE_TABLES


# ---------------------------------------------------------------------------
# AC-7: partition drift-proofing
# ---------------------------------------------------------------------------


def test_partition_covers_every_live_table(db_path: Path) -> None:
    """AC-7: every live table is classified exactly once, KEEP xor PURGE.

    Re-derived from ``sqlite_master`` rather than from a hardcoded list, so a
    future migration that adds a table fails HERE instead of silently falling
    through the purge unclassified. ``_migrations`` is included (KEEP); only
    sqlite internals (``sqlite_sequence`` and friends) are excluded.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        live = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not row[0].startswith("sqlite_")
        }
    finally:
        conn.close()

    assert "_migrations" in live and "_migrations" in KEEP_TABLES

    unclassified = live - KEEP_TABLES - PURGE_TABLES
    assert not unclassified, (
        f"tables not classified as KEEP or PURGE: {sorted(unclassified)} -- a "
        "migration added a table without updating the purge partition"
    )
    stale = (KEEP_TABLES | PURGE_TABLES) - live
    assert not stale, f"partition names a table that no longer exists: {sorted(stale)}"
    assert not (KEEP_TABLES & PURGE_TABLES), "a table is both KEEP and PURGE"
    assert len(PURGE_DELETE_ORDER) == len(PURGE_TABLES), "duplicate in delete order"


def test_keep_set_has_no_foreign_key_into_a_purged_table(db_path: Path) -> None:
    """The KEEP set must be FK-CLOSED with respect to the purge.

    This is the invariant AC-2 (identity and logins survive) actually rests on,
    and nothing else enforces it. If a future migration added, say, a
    ``users`` -> ``teams`` FK, then with FK enforcement ON (AC-3) the purge would
    abort permanently, and with it off the surviving auth rows would reference
    deleted rows.

    AC-7's drift test does NOT cover this: it catches a new unclassified TABLE,
    not a new FK crossing the partition boundary. Derived at runtime from
    ``PRAGMA foreign_key_list`` so the schema itself is the source of truth.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        edges = [
            (table, row[2])
            for table in sorted(KEEP_TABLES)
            for row in conn.execute(f"PRAGMA foreign_key_list({table})")  # noqa: S608
        ]
    finally:
        conn.close()

    # Anti-vacuity: if the pragma returned nothing at all, the assertion below
    # would pass trivially and this test would guard nothing.
    assert edges, "no FKs found on any KEEP table -- the check would be vacuous"

    crossing = [(src, dst) for src, dst in edges if dst in PURGE_TABLES]
    assert not crossing, (
        f"KEEP table(s) reference purged table(s): {crossing} -- the purge would "
        "either abort on the FK or leave surviving auth data pointing at deleted "
        "rows. Reclassify, or the purge partition is unsafe."
    )


# ---------------------------------------------------------------------------
# AC-9: production guard (GAP-2)
# ---------------------------------------------------------------------------


def test_production_without_force_refuses_and_deletes_nothing(
    db_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-9(a): APP_ENV=production without --force refuses; DB untouched."""
    _seed(db_path, repo_root)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(SystemExit) as exc:
        purge_scouting_data(db_path=db_path)

    assert exc.value.code == 1
    assert _nonempty_tables(db_path, PURGE_TABLES) == PURGE_TABLES
    assert (repo_root / "data" / _REPORT_REL_PATH).is_file()


def test_production_with_force_proceeds(
    db_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-9(b): --force is the sanctioned production escape hatch."""
    _seed(db_path, repo_root)
    monkeypatch.setenv("APP_ENV", "production")

    purge_scouting_data(db_path=db_path, force=True)

    assert _nonempty_tables(db_path, PURGE_TABLES) == set()


@pytest.mark.parametrize(
    "app_env", [" production ", "Production", "PRODUCTION", " PrOdUcTiOn\t"]
)
def test_production_guard_catches_whitespace_and_case_variants(
    db_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    """AC-9(c): the IDEA-101 bypass class -- variants must STILL refuse.

    This is the entire reason AC-4 mandates a fresh guard through
    ``is_production()`` rather than reusing ``reset.py``'s
    ``os.environ.get("APP_ENV", "development").lower() == "production"`` body:
    that comparison does not strip, so ``" production "`` sails past it and the
    guard fails OPEN on the most destructive command in the system.
    """
    _seed(db_path, repo_root)
    monkeypatch.setenv("APP_ENV", app_env)

    with pytest.raises(SystemExit):
        purge_scouting_data(db_path=db_path)

    assert _nonempty_tables(db_path, PURGE_TABLES) == PURGE_TABLES


def test_guard_is_a_noop_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-production (incl. unset APP_ENV) does not require --force."""
    for value in ("development", "test", "staging", ""):
        monkeypatch.setenv("APP_ENV", value)
        check_purge_production_guard(force=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    check_purge_production_guard(force=False)


# ---------------------------------------------------------------------------
# AC-10: rollback + unlink isolation
# ---------------------------------------------------------------------------


def test_mid_purge_failure_rolls_back_to_no_half_state(
    db_path: Path, repo_root: Path
) -> None:
    """AC-10(a)/AC-6: an injected failure part-way through leaves NO half-state.

    The failure is injected by appending a non-existent table to the delete
    order, so it fires only AFTER all 20 real deletes have executed inside the
    transaction -- the maximal half-state, and the one the single-transaction
    contract must undo completely.
    """
    _seed(db_path, repo_root)

    doomed_order = (*PURGE_DELETE_ORDER, "table_that_does_not_exist")
    with patch.object(purge_mod, "PURGE_DELETE_ORDER", doomed_order):
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            purge_scouting_data(db_path=db_path, force=True)

    assert _nonempty_tables(db_path, PURGE_TABLES) == PURGE_TABLES
    # The rollback also means the report file must still be there: unlinking is
    # not rollback-able, which is why it is deferred until after the commit.
    assert (repo_root / "data" / _REPORT_REL_PATH).is_file()


def test_missing_report_file_does_not_abort_the_purge(
    db_path: Path, repo_root: Path
) -> None:
    """AC-10(b)/AC-5: a report_path with no file on disk is not fatal."""
    _seed(db_path, repo_root)
    (repo_root / "data" / _REPORT_REL_PATH).unlink()

    result = purge_scouting_data(db_path=db_path, force=True)

    assert _nonempty_tables(db_path, PURGE_TABLES) == set()
    assert result.files_removed == 0
    assert result.file_errors == 0  # absent != error; the end state is correct


def test_unlink_error_is_isolated_and_counted(
    db_path: Path, repo_root: Path
) -> None:
    """AC-5: an unremovable file is counted, isolated, and non-fatal."""
    _seed(db_path, repo_root)

    with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
        result = purge_scouting_data(db_path=db_path, force=True)

    assert _nonempty_tables(db_path, PURGE_TABLES) == set()
    assert result.file_errors == 1
    assert result.files_removed == 0


def _add_report(db_path: Path, slug: str, report_path: str) -> None:
    """Add one extra report row carrying an arbitrary ``report_path``."""
    conn = _conn(db_path)
    team_id = conn.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO reports (slug, team_id, title, status, expires_at, "
        "report_path) VALUES (?, ?, 'R', 'ready', '2099-01-01T00:00:00Z', ?)",
        (slug, team_id, report_path),
    )
    conn.commit()
    conn.close()


@pytest.mark.parametrize("kind", ["absolute", "traversal", "traversal_nested"])
def test_report_path_outside_the_base_is_refused_not_unlinked(
    db_path: Path, repo_root: Path, kind: str
) -> None:
    """A report_path that escapes the reports base is refused and counted.

    ``Path("/base") / "/abs/path"`` DISCARDS the base (pathlib semantics), and a
    ``..`` prefix escapes on resolution -- so without a containment check
    ``.is_file()`` passes and ``unlink()`` deletes a file outside the tree.
    Not reachable today (report_path is generated internally), but this command
    enumerates EVERY report row, so containment is asserted, not assumed.

    The escape target is a real file INSIDE tmp_path but OUTSIDE
    ``<root>/data`` -- never a real system path, so a regression deletes a
    fixture rather than something that matters.
    """
    victim = repo_root / "outside.html"
    hostile_path = {
        "absolute": str(victim),
        "traversal": "../outside.html",
        "traversal_nested": "reports/../../outside.html",
    }[kind]

    _seed(db_path, repo_root)
    # A real file at the escape target, so a missing containment check would
    # visibly delete it rather than silently no-op on a nonexistent path.
    victim.write_text("do not delete me")
    assert (repo_root / "data" / hostile_path).resolve() == victim.resolve()
    _add_report(db_path, "slug-hostile", hostile_path)

    result = purge_scouting_data(db_path=db_path, force=True)

    assert victim.is_file(), f"{hostile_path} escaped the reports base and was deleted"
    assert result.file_errors == 1
    assert result.files_removed == 1  # the legitimate report file still went
    assert _nonempty_tables(db_path, PURGE_TABLES) == set()


def test_report_enumeration_reads_inside_the_write_transaction(
    db_path: Path, repo_root: Path
) -> None:
    """The report SELECT runs inside the same transaction as the DELETEs.

    Three processes share this WAL file, so enumerating BEFORE the transaction
    opens would let a report row inserted in the gap be deleted while its HTML
    is orphaned. ``BEGIN IMMEDIATE`` closes that window; this asserts the
    enumeration genuinely happens inside it rather than merely before the
    deletes.
    """
    _seed(db_path, repo_root)
    observed: list[bool] = []
    real = purge_mod._collect_report_paths

    def _spy(conn):
        observed.append(conn.in_transaction)
        return real(conn)

    with patch.object(purge_mod, "_collect_report_paths", _spy):
        purge_scouting_data(db_path=db_path, force=True)

    assert observed == [True], "enumeration ran outside the write transaction"


def test_production_guard_is_not_skippable_by_the_caller(
    db_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defense in depth: the library guard runs regardless of the call site.

    The CLI runs its own guard first (so a refusal precedes the prompt), but
    that must not be the ONLY protection -- this pins that the library refuses
    on its own even when a caller has already "handled" the guard.
    """
    _seed(db_path, repo_root)
    monkeypatch.setenv("APP_ENV", "production")

    # No kwarg exists to switch the internal guard off.
    with pytest.raises(SystemExit):
        purge_scouting_data(db_path=db_path)

    assert _nonempty_tables(db_path, PURGE_TABLES) == PURGE_TABLES


def test_purge_reports_row_counts(db_path: Path, repo_root: Path) -> None:
    """The result carries per-table counts for the operator summary line."""
    _seed(db_path, repo_root)

    result = purge_scouting_data(db_path=db_path, force=True)

    assert result.rows_deleted["games"] == 1
    assert result.rows_deleted["teams"] == 2
    assert result.total_rows == sum(result.rows_deleted.values())
    assert set(result.rows_deleted) <= PURGE_TABLES
