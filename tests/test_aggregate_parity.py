"""Tests for the aggregate-parity guard (E-234-02).

Loads migrations/001_initial_schema.sql + tests/fixtures/parity_consistent.sql
into a fresh in-memory SQLite database and exercises
``src.reports.aggregate_parity.verify_aggregates`` directly (no ScoutingLoader,
no network).

The fixture is rollup-consistent by construction: each stored player_season_*
row is the exact perspective-filtered SUM of the fixture's player_game_* rows,
hand-authored independently of the recompute code.  Therefore an EMPTY mismatch
list proves the recompute query is correct -- not merely that two copies of the
same SUM agree.

Run with:
    pytest tests/test_aggregate_parity.py -v
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.reports.aggregate_parity import verify_aggregates  # noqa: E402
from tests.conftest import load_real_schema  # noqa: E402

# Golden, hand-verified output of the recompute SUM projection on the
# rollup-consistent fixture, scoped to the in-scope (TEAM_T, 2026).  Each tuple
# follows the projection's column order (the parity-subset RECOMPUTE_KEYS):
#   batting:  player_id, games_tracked, ab, h, doubles, triples, hr, rbi, r,
#             bb, so, sb, tb, hbp, shf, cs
#   pitching: player_id, games_tracked, ip_outs, h, r, er, bb, so, wp, hbp,
#             pitches, total_strikes, bf, gs   (gs NULL for the NULL-order pitcher)
# These equal the fixture's stored boxscore_only season rows by construction
# (the fixture is the independent oracle), so they PIN the projection's
# byte-identical output for the E-246-04 hoist (AC-2).
_GOLDEN_BATTING: dict[str, tuple] = {
    "PB_01": ("PB_01", 3, 11, 4, 1, 1, 1, 3, 3, 3, 3, 2, 10, 1, 1, 1),
    "PB_02": ("PB_02", 3, 11, 4, 1, 0, 0, 2, 2, 1, 4, 1, 5, 1, 0, 0),
}
_GOLDEN_PITCHING: dict[str, tuple] = {
    "PP_01": ("PP_01", 2, 24, 6, 3, 2, 2, 10, 1, 1, 113, 75, 31, 1),
    "PP_02": ("PP_02", 2, 36, 11, 5, 5, 4, 9, 2, 1, 170, 108, 49, 2),
    "PP_03": ("PP_03", 1, 12, 4, 2, 2, 1, 3, 0, 0, 50, 32, 15, None),
}


@pytest.fixture()
def parity_db() -> sqlite3.Connection:
    """In-memory DB with schema + the rollup-consistent parity fixture."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.executescript((_FIXTURES_DIR / "parity_consistent.sql").read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


class TestCleanGreenPath:
    """AC-5(a)/(b): clean fixture -> empty mismatches, non-vacuous comparison."""

    def test_clean_fixture_has_no_mismatches(self, parity_db: sqlite3.Connection) -> None:
        """The rollup-consistent fixture yields an empty mismatch list."""
        result = verify_aggregates(parity_db)
        assert result.mismatches == [], (
            "Expected no mismatches on the rollup-consistent fixture; got: "
            f"{result.mismatches}"
        )

    def test_clean_fixture_compares_cells(self, parity_db: sqlite3.Connection) -> None:
        """cells_compared > 0 guards against a vacuous green (row-scope/join
        matching zero rows)."""
        result = verify_aggregates(parity_db)
        # 2 batters x 16 batting cols + 3 pitchers x 14 pitching cols = 74.
        assert result.cells_compared > 0
        assert result.cells_compared == 74

    def test_recompute_is_read_only(self, parity_db: sqlite3.Connection) -> None:
        """AC-6: the recompute must not mutate either player_season_* table.

        Snapshots full rows (``SELECT *``) of BOTH season tables before and
        after, so the read-only guarantee is robust against a future edit that
        adds a write path to any column of either table.
        """

        def snapshot() -> tuple[list, list]:
            batting = parity_db.execute(
                "SELECT * FROM player_season_batting ORDER BY id"
            ).fetchall()
            pitching = parity_db.execute(
                "SELECT * FROM player_season_pitching ORDER BY id"
            ).fetchall()
            return batting, pitching

        before = snapshot()
        verify_aggregates(parity_db)
        after = snapshot()
        assert before == after


class TestFilterExclusion:
    """MUST-FIX: the out-of-scope rows make all three recompute filters
    (team_id, season_id, perspective_team_id) load-bearing.  These rows would
    leak into the (T, 2026, persp=T) recompute if the corresponding
    filter were dropped -- breaking the green-path empty / cells_compared==74
    assertions above.  This test locks their presence so a future fixture edit
    cannot silently remove the exclusion proof."""

    def test_out_of_scope_rows_present(self, parity_db: sqlite3.Connection) -> None:
        """The fixture carries cross-perspective, cross-season, and cross-team
        rows in BOTH stat tables (the two recompute queries hold separate filter
        copies), while no stored season row exists outside T / 2026."""
        t_id = parity_db.execute(
            "SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'"
        ).fetchone()[0]
        opp_id = parity_db.execute(
            "SELECT id FROM teams WHERE gc_uuid = 'TEAM_OPP'"
        ).fetchone()[0]

        for table in ("player_game_batting", "player_game_pitching"):
            # cross-perspective: team=T, persp != T
            assert parity_db.execute(
                f"SELECT COUNT(*) FROM {table} "
                "WHERE team_id = ? AND perspective_team_id != ?",
                (t_id, t_id),
            ).fetchone()[0] >= 1, f"{table}: missing cross-perspective row"
            # cross-season: a 2025 game row
            assert parity_db.execute(
                f"SELECT COUNT(*) FROM {table} pg JOIN games g ON pg.game_id = g.game_id "
                "WHERE g.season_id = '2025'"
            ).fetchone()[0] >= 1, f"{table}: missing cross-season row"
            # cross-team: team != T
            assert parity_db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE team_id = ?",
                (opp_id,),
            ).fetchone()[0] >= 1, f"{table}: missing cross-team row"

        # Stored BOXSCORE_ONLY aggregates remain scoped to T / 2026
        # only.  (Member-loaded 'full' rows for T / 2025 exist by
        # design -- see TestMissingScopeDetection -- and are intentionally out
        # of the boxscore_only validated scope.)
        for table in ("player_season_batting", "player_season_pitching"):
            assert parity_db.execute(
                f"SELECT COUNT(*) FROM {table} "
                "WHERE stat_completeness = 'boxscore_only' "
                "AND (team_id != ? OR season_id != '2026')",
                (t_id,),
            ).fetchone()[0] == 0, f"{table}: boxscore_only row leaked out of scope"


class TestMissingScopeDetection:
    """Phase 4b P1: a scope present in the recompute source but missing its
    stored boxscore_only aggregate must be flagged (true detection), while a
    member-loaded full/supplemented scope must NOT be flagged (no false
    positive)."""

    def test_missing_stored_aggregate_scope_is_flagged(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """Deleting the stored boxscore_only pitching rows for the in-scope
        scope (the Codex repro) is now caught: the recompute-source scope has
        game rows but no stored aggregate, so every recomputed pitcher surfaces
        as a (stored=None) mismatch.

        Without the missing-scope derivation this returns 0 mismatches (false
        green) -- so this test fails on the old code and passes on the fix.
        """
        parity_db.execute(
            "DELETE FROM player_season_pitching "
            "WHERE stat_completeness = 'boxscore_only' "
            "AND season_id = '2026'"
        )
        parity_db.commit()

        result = verify_aggregates(parity_db)

        flagged = {
            (m.player_id, m.column): m
            for m in result.mismatches
            if m.season_id == "2026"
        }
        # The deleted pitchers are detected as missing (stored=None).
        assert ("PP_01", "ip_outs") in flagged
        assert flagged[("PP_01", "ip_outs")].stored is None
        assert flagged[("PP_01", "ip_outs")].recomputed == 24
        assert ("PP_02", "ip_outs") in flagged
        assert ("PP_03", "ip_outs") in flagged
        # No mismatch leaks from the member-loaded or cross-team out-of-scope
        # rows.
        assert all(
            m.season_id != "2025" for m in result.mismatches
        ), "member-loaded scope must not be flagged"
        assert all(
            m.player_id != "POPP_01" for m in result.mismatches
        ), "cross-team out-of-scope player must not be flagged"

    def test_member_loaded_scope_not_flagged(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """The member-loaded scope (T, 2025) -- game rows present,
        only 'full' stored rows, zero boxscore_only -- is excluded from the
        gate, so the clean fixture stays green despite its stored values not
        equalling the game-row sums."""
        t_id = parity_db.execute(
            "SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'"
        ).fetchone()[0]

        # Precondition: the scope is genuinely member-loaded.
        for table in ("player_season_batting", "player_season_pitching"):
            completeness = {
                r[0]
                for r in parity_db.execute(
                    f"SELECT DISTINCT stat_completeness FROM {table} "
                    "WHERE team_id = ? AND season_id = '2025'",
                    (t_id,),
                ).fetchall()
            }
            assert completeness == {"full"}, (
                f"{table}: expected only 'full' rows for the member scope; "
                f"got {completeness}"
            )

        result = verify_aggregates(parity_db)
        assert all(
            m.season_id != "2025" for m in result.mismatches
        )
        assert result.mismatches == []

    def test_asymmetric_member_scope_not_flagged(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """ASYMMETRIC member edge: a scope with perspective=team game rows in a
        stat table but ZERO stored rows of any completeness in THAT table, whose
        only member provenance (``full``) lives in the OTHER stat table, must
        still be excluded.

        Models a member team+season where season-stats wrote batting but not
        pitching (the member loader writes per table) while boxscores produced
        ``player_game_pitching`` rows.  A single-table "zero stored here"
        discriminator would FLAG the pitching scope using the boxscore SUM as
        the oracle -- a false positive.  The cross-table provenance
        discriminator excludes it.
        """
        # Delete the pitching member row, leaving only the batting 'full' row
        # for (T, 2025) -> asymmetric member provenance.
        parity_db.execute(
            "DELETE FROM player_season_pitching "
            "WHERE season_id = '2025'"
        )
        parity_db.commit()

        t_id = parity_db.execute(
            "SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'"
        ).fetchone()[0]
        # Precondition: pitching game rows (perspective=team) exist for the
        # scope, with zero stored pitching rows of any completeness.
        assert parity_db.execute(
            "SELECT COUNT(*) FROM player_game_pitching pg "
            "JOIN games g ON pg.game_id = g.game_id "
            "WHERE pg.team_id = ? AND pg.perspective_team_id = ? "
            "AND g.season_id = '2025'",
            (t_id, t_id),
        ).fetchone()[0] >= 1
        assert parity_db.execute(
            "SELECT COUNT(*) FROM player_season_pitching "
            "WHERE team_id = ? AND season_id = '2025'",
            (t_id,),
        ).fetchone()[0] == 0
        # Member provenance survives in the OTHER (batting) table.
        assert parity_db.execute(
            "SELECT COUNT(*) FROM player_season_batting "
            "WHERE team_id = ? AND season_id = '2025' "
            "AND stat_completeness = 'full'",
            (t_id,),
        ).fetchone()[0] >= 1

        result = verify_aggregates(parity_db)
        assert all(
            m.season_id != "2025" for m in result.mismatches
        ), "asymmetric member scope must not be flagged"
        # In-scope green path is undisturbed.
        assert result.mismatches == []


class TestMixedProvenanceScope:
    """E-237-03 Phase 4b P1: a MIXED-provenance scope -- one player preserved as
    ``full`` alongside recomputed ``boxscore_only`` players in the SAME
    (team_id, season_id) table+scope -- must not surface the preserved ``full``
    player as a synthetic ``stored=None`` mismatch.

    The canonical recompute (``src.db.season_aggregates.canonical_recompute``)
    preserves member ``full``/``supplemented`` rows and only INSERTs
    boxscore_only rows for the remaining players, so a member scope can now hold
    BOTH a ``full`` row and ``boxscore_only`` rows.  ``verify_aggregates`` must
    apply the same per-player provenance exclusion as the recompute's NOT EXISTS
    guard.
    """

    def test_full_player_in_mixed_scope_not_flagged(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """Inject a ``full`` batter (ab=99) WITH per-game rows into the in-scope
        (T, 2026) scope that already holds boxscore_only batters.

        Codex's repro: without the per-player provenance exclusion the preserved
        ``full`` player -- who has player_game_batting rows but no stored
        boxscore_only row -- surfaces as bogus (stored=None) mismatches across
        the diffed batting columns.  With the fix, that player is excluded and
        the in-scope green path stays empty.
        """
        t_id = parity_db.execute(
            "SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'"
        ).fetchone()[0]

        parity_db.execute(
            "INSERT INTO players (player_id, first_name, last_name) "
            "VALUES ('MEMBER_BAT', 'Member', 'Batter')"
        )
        # Authoritative member 'full' batting row (from the season-stats API),
        # with distinctive values the per-game recompute would NOT reproduce.
        parity_db.execute(
            "INSERT INTO player_season_batting "
            "(player_id, team_id, season_id, stat_completeness, gp, games_tracked, ab, h) "
            "VALUES ('MEMBER_BAT', ?, '2026', 'full', 30, 30, 99, 40)",
            (t_id,),
        )
        # The SAME player also has an in-scope per-game boxscore row (perspective
        # = team) -- this is what would make the recompute include them.
        parity_db.execute(
            "INSERT INTO player_game_batting "
            "(game_id, player_id, team_id, perspective_team_id, ab, h) "
            "VALUES ('PG_1', 'MEMBER_BAT', ?, ?, 3, 1)",
            (t_id, t_id),
        )
        parity_db.commit()

        result = verify_aggregates(parity_db)

        # The preserved full player produces NO mismatch ...
        assert all(
            m.player_id != "MEMBER_BAT" for m in result.mismatches
        ), f"full player in mixed scope flagged: {result.mismatches}"
        # ... and the in-scope green path is otherwise undisturbed.
        assert result.mismatches == [], (
            f"mixed-provenance scope broke the green path: {result.mismatches}"
        )


class TestInjectedDivergence:
    """AC-5(c): an injected stored/recompute divergence is reported exactly."""

    def test_mutated_gs_is_reported_as_single_mismatch(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """Mutating PP_01 stored gs 1 -> 5 yields exactly one mismatch.

        PP_01 has two appearances but one start, so the recompute gs is 1.
        Forcing the stored value to 5 must surface as a single
        (PP_01, gs, stored=5, recomputed=1) finding -- and nothing else.
        """
        parity_db.execute(
            "UPDATE player_season_pitching SET gs = 5 WHERE player_id = 'PP_01'"
        )
        parity_db.commit()

        result = verify_aggregates(parity_db)

        assert len(result.mismatches) == 1
        m = result.mismatches[0]
        assert m.player_id == "PP_01"
        assert m.column == "gs"
        assert m.stored == 5
        assert m.recomputed == 1
        assert result.cells_compared == 74


class TestSharedProjectionGolden:
    """AC-2 (E-246-04 HARD GATE): the SUM-projection bodies were hoisted into a
    single shared source (``src.db.season_aggregates``) consumed by BOTH
    ``canonical_recompute`` and this parity check.  These characterization tests
    PIN the projection's output against representative season data so the
    consolidation is provably byte-identical -- and stay green forever as a
    drift guard on the integrity seam.

    They reference only names stable across the refactor
    (``_BATTING_RECOMPUTE_SQL`` / ``_PITCHING_RECOMPUTE_SQL`` /
    ``canonical_recompute``), never the new builder symbols, so they execute in
    BOTH checkouts.

    Worktree caveat: pytest loads the editable-installed (main-checkout) source,
    so in the epic worktree these run against the PRE-change projection and
    confirm the golden values are correct; the authoritative post-change proof
    is the closure full-suite run in merged main, where the hoisted projection
    is loaded.  ``test_projection_source_paths`` records which source loaded.
    """

    @staticmethod
    def _team_t_id(conn: sqlite3.Connection) -> int:
        return conn.execute(
            "SELECT id FROM teams WHERE gc_uuid = 'TEAM_T'"
        ).fetchone()[0]

    def test_batting_projection_output_is_pinned(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """The batting recompute SQL yields the pinned golden rows exactly."""
        from src.reports import aggregate_parity

        t_id = self._team_t_id(parity_db)
        rows = parity_db.execute(
            aggregate_parity._BATTING_RECOMPUTE_SQL, (t_id, "2026", t_id)
        ).fetchall()
        got = {row[0]: tuple(row) for row in rows}
        assert got == _GOLDEN_BATTING

    def test_pitching_projection_output_is_pinned(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """The pitching recompute SQL yields the pinned golden rows exactly,
        including the NULL-``gs`` branch (PP_03)."""
        from src.reports import aggregate_parity

        t_id = self._team_t_id(parity_db)
        rows = parity_db.execute(
            aggregate_parity._PITCHING_RECOMPUTE_SQL, (t_id, "2026", t_id)
        ).fetchall()
        got = {row[0]: tuple(row) for row in rows}
        assert got == _GOLDEN_PITCHING

    def test_canonical_and_parity_projections_agree(
        self, parity_db: sqlite3.Connection
    ) -> None:
        """The single-source integrity property (AC-3): the canonical recompute
        and the parity check produce IDENTICAL parity-subset values.

        Runs ``canonical_recompute`` (which DELETE+INSERTs boxscore_only rows
        from the same game rows), reads back the parity-subset columns, and
        asserts they equal both the parity recompute output and the pinned
        golden -- so the two consumers of the shared projection cannot diverge.
        """
        from src.db.season_aggregates import canonical_recompute
        from src.reports import aggregate_parity

        t_id = self._team_t_id(parity_db)

        # Read-only parity recompute output for both tables.
        parity_bat = {
            row[0]: tuple(row)
            for row in parity_db.execute(
                aggregate_parity._BATTING_RECOMPUTE_SQL, (t_id, "2026", t_id)
            ).fetchall()
        }
        parity_pit = {
            row[0]: tuple(row)
            for row in parity_db.execute(
                aggregate_parity._PITCHING_RECOMPUTE_SQL, (t_id, "2026", t_id)
            ).fetchall()
        }

        # Canonical recompute rewrites the boxscore_only rows; read the same
        # parity-subset columns back out.
        canonical_recompute(parity_db, t_id, "2026")

        bat_cols = ", ".join(aggregate_parity._BATTING_RECOMPUTE_KEYS)
        canon_bat = {
            row[0]: tuple(row)
            for row in parity_db.execute(
                f"SELECT {bat_cols} FROM player_season_batting "
                "WHERE team_id = ? AND season_id = '2026' "
                "AND stat_completeness = 'boxscore_only'",
                (t_id,),
            ).fetchall()
        }
        pit_cols = ", ".join(aggregate_parity._PITCHING_RECOMPUTE_KEYS)
        canon_pit = {
            row[0]: tuple(row)
            for row in parity_db.execute(
                f"SELECT {pit_cols} FROM player_season_pitching "
                "WHERE team_id = ? AND season_id = '2026' "
                "AND stat_completeness = 'boxscore_only'",
                (t_id,),
            ).fetchall()
        }

        assert canon_bat == parity_bat == _GOLDEN_BATTING
        assert canon_pit == parity_pit == _GOLDEN_PITCHING

    def test_projection_source_paths(self) -> None:
        """Record which source pytest actually loaded (worktree caveat).

        Asserts only that the projection modules resolved to real files; the
        path string surfaces in ``-s`` / failure output so the reader can see
        whether the worktree or the merged-main source was exercised.
        """
        import src.db.season_aggregates as sa
        import src.reports.aggregate_parity as ap

        print(f"\naggregate_parity loaded from: {ap.__file__}")
        print(f"season_aggregates loaded from: {sa.__file__}")
        assert ap.__file__.endswith("aggregate_parity.py")
        assert sa.__file__.endswith("season_aggregates.py")


class TestDiffColumnsSingleSource:
    """E-246-04 remediation (Codex Phase 4b): the diffed-column sets
    (``_BATTING_COLUMNS`` / ``_PITCHING_COLUMNS``) must DERIVE their stat columns
    from the shared ``*_RECOMPUTE_KEYS`` single source, so a parity-checked
    column added to the shared projection flows automatically into the
    comparison -- no second edit site.  These tests pin BOTH the single-source
    derivation (AC-3 structural enforcement) AND byte-identical behavior on
    existing data (the prior literal tuples reproduced exactly -> cells_compared
    stays 74).
    """

    # The PRE-remediation literal tuples -- the byte-preservation anchor.  The
    # derived tuples MUST equal these exactly (same pairs, same order).
    _EXPECTED_BATTING = (
        ("gp", "games_tracked"),
        ("games_tracked", "games_tracked"),
        ("ab", "ab"),
        ("h", "h"),
        ("doubles", "doubles"),
        ("triples", "triples"),
        ("hr", "hr"),
        ("rbi", "rbi"),
        ("r", "r"),
        ("bb", "bb"),
        ("so", "so"),
        ("sb", "sb"),
        ("tb", "tb"),
        ("hbp", "hbp"),
        ("shf", "shf"),
        ("cs", "cs"),
    )
    _EXPECTED_PITCHING = (
        ("gp_pitcher", "games_tracked"),
        ("games_tracked", "games_tracked"),
        ("ip_outs", "ip_outs"),
        ("h", "h"),
        ("r", "r"),
        ("er", "er"),
        ("bb", "bb"),
        ("so", "so"),
        ("wp", "wp"),
        ("hbp", "hbp"),
        ("pitches", "pitches"),
        ("total_strikes", "total_strikes"),
        ("bf", "bf"),
        ("gs", "gs"),
    )

    def test_diff_columns_reproduce_prior_tuples_exactly(self) -> None:
        """HARD GATE: the derived diff_columns are byte-identical to the prior
        hand-maintained tuples -- same pairs, same order -> cells_compared 74."""
        from src.reports import aggregate_parity

        assert aggregate_parity._BATTING_COLUMNS == self._EXPECTED_BATTING
        assert aggregate_parity._PITCHING_COLUMNS == self._EXPECTED_PITCHING
        # 16 batting + 14 pitching diffed columns -> 2*16 + 3*14 = 74 cells on
        # the fixture (the TestCleanGreenPath cells_compared==74 anchor).
        assert len(aggregate_parity._BATTING_COLUMNS) == 16
        assert len(aggregate_parity._PITCHING_COLUMNS) == 14

    def test_diff_columns_track_shared_keys(self) -> None:
        """AC-3 structural enforcement: the recompute_key sequence each
        diff_columns references equals the shared ``*_RECOMPUTE_KEYS`` (minus
        ``player_id``).  A column added to the shared projection therefore cannot
        be silently skipped by the comparison."""
        from src.db.season_aggregates import (
            BATTING_RECOMPUTE_KEYS,
            PITCHING_RECOMPUTE_KEYS,
        )
        from src.reports import aggregate_parity

        # The leading entry is the non-derivable games-count stored alias
        # (gp / gp_pitcher -> games_tracked); the REMAINDER's recompute keys are
        # exactly the shared keys after player_id, in order.
        batting_stat_keys = tuple(
            rk for _, rk in aggregate_parity._BATTING_COLUMNS[1:]
        )
        pitching_stat_keys = tuple(
            rk for _, rk in aggregate_parity._PITCHING_COLUMNS[1:]
        )
        assert batting_stat_keys == BATTING_RECOMPUTE_KEYS[1:]
        assert pitching_stat_keys == PITCHING_RECOMPUTE_KEYS[1:]

    def test_canonical_only_extras_remain_undiffed(self) -> None:
        """The canonical-only superset extras (pitching w/l/sv, batting
        pa/singles/xbh) and pitching ``hr`` are NOT in the shared keys, so the
        derivation must leave them out of the comparison."""
        from src.reports import aggregate_parity

        batting_cols = {sc for sc, _ in aggregate_parity._BATTING_COLUMNS}
        batting_keys = {rk for _, rk in aggregate_parity._BATTING_COLUMNS}
        pitching_cols = {sc for sc, _ in aggregate_parity._PITCHING_COLUMNS}
        pitching_keys = {rk for _, rk in aggregate_parity._PITCHING_COLUMNS}

        for extra in ("pa", "singles", "xbh"):
            assert extra not in batting_cols and extra not in batting_keys
        for extra in ("w", "l", "sv", "hr"):
            assert extra not in pitching_cols and extra not in pitching_keys
