"""Tests for the plays-vs-boxscore reconciliation scoreboard (E-257-01).

Loads the real migrated schema + tests/fixtures/recon_scoreboard_seed.sql into a
fresh in-memory SQLite database and exercises
``src.reports.recon_scoreboard.compute_scoreboard`` directly, plus the
``bb report reconcile-scoreboard`` CLI wrapper via Typer's CliRunner.

The teeth fixture seeds a populated, KNOWN state (agreeing units -> 100%
fidelity, plus deliberately non-zero axis counters) so the assertions below are
non-vacuous.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.cli.report import app as report_app  # noqa: E402
from src.reports.recon_scoreboard import (  # noqa: E402
    AB_EXCLUSION_OUTCOMES,
    BATTING_RESIDUAL_STATS,
    BATTING_STATS,
    BB_OUTCOMES,
    EXIT_BASELINE_ABSENT,
    EXIT_BASELINE_MALFORMED,
    EXIT_REGRESSION,
    GATED_BATTING_STATS,
    GATED_PITCHING_STATS,
    BaselineError,
    HBP_OUTCOMES,
    HIT_OUTCOMES,
    PITCHING_STATS,
    SO_OUTCOMES,
    ScoreboardResult,
    compute_scoreboard,
    evaluate_gate,
    is_dropped_pitch_event,
    load_baseline,
    to_json_dict,
    write_baseline,
)
from tests.conftest import load_real_schema  # noqa: E402

_BASELINE_FIXTURE = _FIXTURES_DIR / "recon_scoreboard_baseline.json"


def _seed_conn() -> sqlite3.Connection:
    """In-memory DB with the real schema + the teeth fixture."""
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.executescript(
        (_FIXTURES_DIR / "recon_scoreboard_seed.sql").read_text(encoding="utf-8")
    )
    conn.commit()
    return conn


def _seed_file_db(tmp_path: Path, *, drop_self_game: bool = False) -> Path:
    """Write the schema + teeth fixture to a temp SQLite file and return its path.

    ``drop_self_game=True`` deletes the seed's self-game (G_SELF) so the run's
    ``self_games`` counter is 0 -- needed for gate-PASS scenarios, since the gate
    treats ``self_games > 0`` as a hard failure regardless of the baseline.
    """
    db_path = tmp_path / "scoreboard.db"
    conn = sqlite3.connect(str(db_path))
    load_real_schema(conn)
    conn.executescript(
        (_FIXTURES_DIR / "recon_scoreboard_seed.sql").read_text(encoding="utf-8")
    )
    if drop_self_game:
        conn.execute("DELETE FROM games WHERE game_id = 'G_SELF'")
    conn.commit()
    conn.close()
    return db_path


def _use_baseline_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the CLI's baseline resolver at the committed synthetic fixture."""
    monkeypatch.setattr(
        "src.cli.report.default_baseline_path", lambda: _BASELINE_FIXTURE
    )


@pytest.fixture()
def scoreboard_db() -> sqlite3.Connection:
    conn = _seed_conn()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# AC-1: result dataclass shape (per-stat rows + three named axis counters)
# ---------------------------------------------------------------------------


class TestResultShape:
    def test_returns_scoreboard_result(self, scoreboard_db: sqlite3.Connection) -> None:
        result = compute_scoreboard(scoreboard_db)
        assert isinstance(result, ScoreboardResult)

    def test_pitching_and_batting_stat_rows(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        result = compute_scoreboard(scoreboard_db)
        assert tuple(s.stat for s in result.pitching) == PITCHING_STATS
        assert tuple(s.stat for s in result.batting) == BATTING_STATS
        # Each carries exact% and abs-Δ.
        for s in (*result.pitching, *result.batting):
            assert isinstance(s.exact_pct, float)
            assert isinstance(s.abs_delta, int)

    def test_three_axis_counters_are_distinct_named_fields(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        result = compute_scoreboard(scoreboard_db)
        assert isinstance(result.dropped_pitch_events, int)
        assert isinstance(result.no_plays_units, int)
        assert isinstance(result.self_games, int)


# ---------------------------------------------------------------------------
# AC-2: read-only (no mutation)
# ---------------------------------------------------------------------------


class TestReadOnly:
    def test_compute_writes_nothing(self, scoreboard_db: sqlite3.Connection) -> None:
        before = scoreboard_db.total_changes
        compute_scoreboard(scoreboard_db)
        assert scoreboard_db.total_changes == before, (
            "compute_scoreboard must be read-only; "
            "it modified rows on the connection."
        )


# ---------------------------------------------------------------------------
# AC-6: teeth fixture -- agreeing units 100%, seeded non-zero axis values
# ---------------------------------------------------------------------------


class TestTeethFixture:
    def test_agreeing_units_are_100_percent(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        result = compute_scoreboard(scoreboard_db)
        # Every fidelity unit in the fixture agrees exactly -> 100% / abs-Δ 0.
        for s in (*result.pitching, *result.batting):
            assert s.fidelity_units == 1, f"{s.stat}: expected 1 fidelity unit"
            assert s.exact_pct == 100.0, f"{s.stat}: expected 100% exact"
            assert s.abs_delta == 0, f"{s.stat}: expected abs-Δ 0"

    def test_seeded_axis_counters(self, scoreboard_db: sqlite3.Connection) -> None:
        result = compute_scoreboard(scoreboard_db)
        assert result.self_games == 1
        assert result.dropped_pitch_events == 2
        assert result.no_plays_units == 3

    def test_perspective_only_miss_breakdown(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        result = compute_scoreboard(scoreboard_db)
        # PB_persp is the single perspective-only miss (plays only under OPP).
        assert result.perspective_only_misses == 1


# ---------------------------------------------------------------------------
# AC-7: stat-definition drift guard -- constant pins + behavioral mapping
# ---------------------------------------------------------------------------


class TestStatDefinitionConstants:
    def test_outcome_sets_pinned_to_literals(self) -> None:
        assert HIT_OUTCOMES == frozenset(
            {"Single", "Double", "Triple", "Home Run"}
        )
        assert SO_OUTCOMES == frozenset({"Strikeout", "Dropped 3rd Strike"})
        assert BB_OUTCOMES == frozenset({"Walk", "Intentional Walk"})
        assert HBP_OUTCOMES == frozenset({"Hit By Pitch"})

    def test_ab_exclusion_set_pinned_to_literal(self) -> None:
        assert AB_EXCLUSION_OUTCOMES == frozenset(
            {
                "Walk",
                "Intentional Walk",
                "Hit By Pitch",
                "Sacrifice Fly",
                "Sacrifice Bunt",
                "Catcher's Interference",
            }
        )

    def test_residual_stats_are_batting_ab_and_h_only(self) -> None:
        assert BATTING_RESIDUAL_STATS == frozenset({"AB", "H"})

    def test_constants_match_reconciliation_engine(self) -> None:
        """Drift guard: the scoreboard constants are now canonical (TN-7); the
        reconciliation engine holds a private parallel copy for its own
        derivation.  Both derive the same plays->stat mapping, so they MUST
        agree -- this asserts the engine's copy has not drifted from ours."""
        from src.reconciliation import engine

        assert HIT_OUTCOMES == engine._HIT_OUTCOMES
        assert SO_OUTCOMES == engine._SO_OUTCOMES
        assert BB_OUTCOMES == engine._BB_OUTCOMES
        assert HBP_OUTCOMES == engine._HBP_OUTCOMES
        assert AB_EXCLUSION_OUTCOMES == engine._AB_EXCLUSIONS


class TestOutcomeToStatMappingBehavioral:
    """AC-7b: exercise each outcome-to-stat mapping behaviourally -- a row of
    each outcome type must land in the correct stat."""

    def test_each_outcome_maps_to_expected_stat(self) -> None:
        conn = _seed_conn()
        try:
            conn.execute(
                "INSERT INTO players (player_id, first_name, last_name) VALUES "
                "('MAP_BAT', 'Map', 'Bat'), ('MAP_PIT', 'Map', 'Pit')"
            )
            team_id = conn.execute(
                "SELECT id FROM teams WHERE gc_uuid='TEAM_T'"
            ).fetchone()[0]
            # One PA of EVERY outcome member across all buckets (AC-7b: a row of
            # each outcome type must land in the correct stat), not one per bucket:
            #   H  = Single + Double + Triple + Home Run                 -> 4
            #   SO = Strikeout + Dropped 3rd Strike                      -> 2
            #   BB = Walk + Intentional Walk                             -> 2
            #   HBP = Hit By Pitch                                       -> 1
            #   AB-exclusion members (PA but not AB): Walk, Intentional Walk,
            #     Hit By Pitch, Sacrifice Fly, Sacrifice Bunt, Catcher's
            #     Interference                                           -> 6
            #   PA (row count) = 12  ->  AB = 12 - 6 = 6
            outcomes = [
                "Single", "Double", "Triple", "Home Run",   # -> H
                "Strikeout", "Dropped 3rd Strike",          # -> SO
                "Walk", "Intentional Walk",                 # -> BB (+ AB excl)
                "Hit By Pitch",                             # -> HBP (+ AB excl)
                "Sacrifice Fly", "Sacrifice Bunt",          # -> AB excl only
                "Catcher's Interference",                   # -> AB excl only
            ]
            for i, outcome in enumerate(outcomes, start=100):
                conn.execute(
                    "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
                    "batting_team_id, perspective_team_id, batter_id, pitcher_id, outcome) "
                    "VALUES ('G1', ?, 9, 'bottom', '2026', ?, ?, 'MAP_BAT', 'MAP_PIT', ?)",
                    (i, team_id, team_id, outcome),
                )
            # Boxscore lines set to the EXACT expected plays derivation, so a
            # mis-bucketed outcome (e.g. Triple counted as SO, or Catcher's
            # Interference counted as an AB) surfaces as a non-zero abs-Δ on the
            # affected stats.
            conn.execute(
                "INSERT INTO player_game_batting (game_id, player_id, team_id, "
                "perspective_team_id, ab, h, bb, so, hbp) "
                "VALUES ('G1', 'MAP_BAT', ?, ?, 6, 4, 2, 2, 1)",
                (team_id, team_id),
            )
            conn.execute(
                "INSERT INTO player_game_pitching (game_id, player_id, team_id, "
                "perspective_team_id, bf, so, bb, h, hbp) "
                "VALUES ('G1', 'MAP_PIT', ?, ?, 12, 2, 2, 4, 1)",
                (team_id, team_id),
            )
            conn.commit()

            result = compute_scoreboard(conn)
            bat = {s.stat: s for s in result.batting}
            pit = {s.stat: s for s in result.pitching}
            # MAP_BAT / MAP_PIT are second fidelity units; they agree exactly, so
            # every stat stays at abs-Δ 0 -- i.e. each outcome member landed in the
            # right bucket.
            for stat in BATTING_STATS:
                assert bat[stat].abs_delta == 0, (
                    f"batting {stat}: outcome mapping mis-bucketed (abs-Δ != 0)"
                )
            for stat in PITCHING_STATS:
                assert pit[stat].abs_delta == 0, (
                    f"pitching {stat}: outcome mapping mis-bucketed (abs-Δ != 0)"
                )
            # And both new units were actually scored against the full 12-PA set
            # (non-vacuous -- the mapping was exercised, not skipped).
            assert bat["H"].fidelity_units == 2
            assert pit["BF"].fidelity_units == 2
            assert pit["BF"].exact_units == 2
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# AC-9: dropped-pitch detection predicate (exact, not naive LIKE)
# ---------------------------------------------------------------------------


class TestDroppedPitchPredicate:
    @pytest.mark.parametrize(
        "raw_template",
        [
            "Strike 1 looking (Curveball)",
            "Ball 1 (Fastball)",
            "In play (Fastball)",
            "Strike 2 swinging (101 MPH Curveball)",
        ],
    )
    def test_matches_stranded_annotated_pitch(self, raw_template: str) -> None:
        assert is_dropped_pitch_event(raw_template) is True

    @pytest.mark.parametrize(
        "raw_template",
        [
            "Wild pitch (passed ball)",          # trailing paren, NOT a pitch base
            "(Play Edit) Lineup changed",        # leading paren
            "Strike 1 looking",                  # bare pitch (classifies as pitch
                                                 # but is not an 'other' strand here)
            "",
            None,
        ],
    )
    def test_rejects_non_pitch_or_bare_parentheticals(
        self, raw_template: str | None
    ) -> None:
        # The near-miss "Wild pitch (passed ball)" is the key case: a naive
        # LIKE '%(%)%' would count it; the exact predicate does not.
        if raw_template == "Strike 1 looking":
            # A bare pitch DOES classify as a pitch; the counter only ever sees
            # this predicate applied to event_type='other' rows, and a bare pitch
            # would already be stored as 'pitch'.  Documented, not asserted-false.
            assert is_dropped_pitch_event(raw_template) is True
        else:
            assert is_dropped_pitch_event(raw_template) is False

    def test_counter_excludes_near_miss(self, scoreboard_db: sqlite3.Connection) -> None:
        """The fixture seeds 2 stranded pitches + 1 'Wild pitch (passed ball)'
        near-miss 'other' row; the counter is 2, not 3."""
        result = compute_scoreboard(scoreboard_db)
        assert result.dropped_pitch_events == 2


# ---------------------------------------------------------------------------
# AC-4: stable JSON keys (axis counters + per-stat block shape)
# ---------------------------------------------------------------------------


class TestJsonStability:
    def test_axis_counter_keys_exactly_three(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        payload = to_json_dict(compute_scoreboard(scoreboard_db))
        assert set(payload["axis_counters"].keys()) == {
            "dropped_pitch_events",
            "no_plays_units",
            "self_games",
        }

    def test_per_stat_block_shape_is_locked(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        payload = to_json_dict(compute_scoreboard(scoreboard_db))
        assert set(payload["pitching"].keys()) == set(PITCHING_STATS)
        assert set(payload["batting"].keys()) == set(BATTING_STATS)
        expected_cell_keys = {
            "exact_pct",
            "abs_delta",
            "fidelity_units",
            "exact_units",
            "is_residual",
        }
        for block in (payload["pitching"], payload["batting"]):
            for cell in block.values():
                assert set(cell.keys()) == expected_cell_keys

    def test_perspective_only_not_in_json(
        self, scoreboard_db: sqlite3.Connection
    ) -> None:
        payload = to_json_dict(compute_scoreboard(scoreboard_db))
        assert "perspective_only_misses" not in payload
        assert "perspective_only_misses" not in payload["axis_counters"]

    def test_json_is_serializable(self, scoreboard_db: sqlite3.Connection) -> None:
        payload = to_json_dict(compute_scoreboard(scoreboard_db))
        # Round-trips through json cleanly (no non-serializable values).
        assert json.loads(json.dumps(payload)) == payload


# ---------------------------------------------------------------------------
# CLI: AC-3 (human table), AC-4b (clean JSON stdout), AC-5 (DB-missing guard)
# ---------------------------------------------------------------------------


class TestCli:
    def test_human_table_shows_rows_and_axis_counters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Gate-pass scenario (self-game removed, matching baseline) so the view
        # renders and exits 0.
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        _use_baseline_fixture(monkeypatch)
        # Widen the render so long cells are not truncated at the 80-col default.
        monkeypatch.setenv("COLUMNS", "220")
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard"])
        assert result.exit_code == 0, result.output
        out = result.output
        # Per-stat fidelity is rendered.
        assert "Exact%" in out
        assert "Scoreboard" in out
        # The three axis counters appear.
        assert "dropped_pitch_events" in out
        assert "no_plays_units" in out
        assert "self_games" in out
        # AC-3 binding clause: the residual label attaches to the batting AB/H
        # rows ONLY -- never to a pitching row or to batting BB/SO -- and is never
        # suppressed.  Pin it at the RENDER surface (COLUMNS=220 keeps each row's
        # note on one line, so one "residual" occurrence == one labeled row).
        table_lines = out.splitlines()
        residual_lines = [line for line in table_lines if "residual" in line]
        assert len(residual_lines) == 2, (
            f"expected exactly 2 residual-labeled rows (batting AB, H); "
            f"got {len(residual_lines)}: {residual_lines}"
        )
        # Never on a pitching row.
        assert all("batting" in line for line in residual_lines)
        assert not any("pitching" in line for line in residual_lines)
        # Exactly the AB and H rows (" H " matches the H stat cell but not HBP).
        assert any(" AB " in line for line in residual_lines)
        assert any(" H " in line for line in residual_lines)
        # Perspective-only split shown as a display-only sub-line.
        assert "perspective-only" in out

    def test_json_mode_stdout_is_clean_parseable_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        _use_baseline_fixture(monkeypatch)
        # Click 8.2+ separates stdout/stderr by default (no mix_stderr kwarg);
        # result.stdout is stdout only.
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard", "--json"])
        assert result.exit_code == 0, result.stdout
        # stdout is ONLY the JSON object -- no interleaved table text.
        payload = json.loads(result.stdout)
        assert set(payload["axis_counters"].keys()) == {
            "dropped_pitch_events",
            "no_plays_units",
            "self_games",
        }
        assert payload["axis_counters"]["self_games"] == 0

    def test_json_mode_suppresses_table(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        _use_baseline_fixture(monkeypatch)
        # Click 8.2+ separates stdout/stderr by default (no mix_stderr kwarg);
        # result.stdout is stdout only.
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard", "--json"])
        assert "Exact%" not in result.stdout
        assert "Scoreboard" not in result.stdout

    def test_db_missing_errors_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "nope.db"
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: missing
        )
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard"])
        assert result.exit_code == 1
        assert "Database not found" in result.output


# ===========================================================================
# E-257-02: committed baseline + one-way ratchet regression gate
# ===========================================================================


def _cell(abs_delta: int = 0, *, is_residual: bool = False) -> dict[str, object]:
    return {
        "exact_pct": 100.0,
        "abs_delta": abs_delta,
        "fidelity_units": 10,
        "exact_units": 10,
        "is_residual": is_residual,
    }


def _block(stats: tuple[str, ...], abs_map: dict[str, int]) -> dict[str, dict]:
    return {s: _cell(abs_map.get(s, 0)) for s in stats}


def _values(
    *,
    bat: dict[str, int] | None = None,
    pit: dict[str, int] | None = None,
    axis: dict[str, int] | None = None,
) -> dict[str, object]:
    """Build a `to_json_dict`-shaped value block for direct gate tests.

    All abs-Δ default to 0 and all axis counters to 0; ``bat``/``pit`` override
    per-stat abs-Δ and ``axis`` overrides axis counters.
    """
    axis_full = {"dropped_pitch_events": 0, "no_plays_units": 0, "self_games": 0}
    axis_full.update(axis or {})
    return {
        "pitching": _block(PITCHING_STATS, pit or {}),
        "batting": _block(BATTING_STATS, bat or {}),
        "axis_counters": axis_full,
    }


class TestEvaluateGate:
    """AC-2/AC-3/AC-4/AC-6: the one-way ratchet + self_games hard-zero."""

    def test_identical_passes(self) -> None:
        assert evaluate_gate(_values(), _values()).passed

    def test_improvement_passes(self) -> None:
        # Baseline carries a floor; a fresh run that SHRINKS abs-Δ and DROPS a
        # ratcheted counter is an improvement -- never trips the gate (AC-2).
        baseline = _values(bat={"H": 5}, axis={"no_plays_units": 10})
        current = _values(bat={"H": 2}, axis={"no_plays_units": 4})
        assert evaluate_gate(current, baseline).passed

    def test_hold_steady_passes(self) -> None:
        baseline = _values(bat={"AB": 34, "H": 13}, axis={"no_plays_units": 3})
        assert evaluate_gate(baseline, baseline).passed

    @pytest.mark.parametrize("stat", GATED_BATTING_STATS)
    def test_gated_batting_stat_regression_fails(self, stat: str) -> None:
        result = evaluate_gate(_values(bat={stat: 1}), _values())
        assert not result.passed
        assert any(v.name == f"batting.{stat}" for v in result.violations)

    @pytest.mark.parametrize("stat", GATED_PITCHING_STATS)
    def test_gated_pitching_stat_regression_fails(self, stat: str) -> None:
        result = evaluate_gate(_values(pit={stat: 1}), _values())
        assert not result.passed
        assert any(v.name == f"pitching.{stat}" for v in result.violations)

    def test_bf_not_gated(self) -> None:
        # Pitching BF is context-only -- a BF abs-Δ increase must NOT fire (AC-4).
        assert evaluate_gate(_values(pit={"BF": 9}), _values()).passed

    def test_hbp_not_gated(self) -> None:
        # HBP is shown but not equal-gated on either side (AC-4).
        current = _values(bat={"HBP": 9}, pit={"HBP": 9})
        assert evaluate_gate(current, _values()).passed

    def test_dropped_pitch_events_regression_fails(self) -> None:
        result = evaluate_gate(
            _values(axis={"dropped_pitch_events": 5}),
            _values(axis={"dropped_pitch_events": 2}),
        )
        assert not result.passed
        assert any(v.name == "axis.dropped_pitch_events" for v in result.violations)

    def test_no_plays_units_regression_fails(self) -> None:
        result = evaluate_gate(
            _values(axis={"no_plays_units": 7}),
            _values(axis={"no_plays_units": 3}),
        )
        assert not result.passed
        assert any(v.name == "axis.no_plays_units" for v in result.violations)

    def test_self_games_hard_zero_fails_regardless_of_baseline(self) -> None:
        # self_games > 0 fails even when the baseline (wrongly) recorded a
        # non-zero floor -- it is a hard zero, not ratcheted (AC-3/AC-4).
        result = evaluate_gate(
            _values(axis={"self_games": 2}),
            _values(axis={"self_games": 5}),
        )
        assert not result.passed
        violation = next(v for v in result.violations if v.name == "self_games")
        assert violation.kind == "self_games"
        assert violation.current == 2

    def test_metadata_header_ignored(self) -> None:
        # AC-1: the gate compares only the value block; a metadata header on the
        # baseline is ignored (a live --json run has no SHA/date).
        baseline = _values()
        baseline["metadata"] = {"git_sha": "abc123", "snapshot_date": "2026-07-08"}
        assert evaluate_gate(_values(), baseline).passed

    def test_abandoned_pa_residual_exempt_at_floor(self) -> None:
        # AC-6: the abandoned-PA residual on batting AB/H is EXEMPT via the
        # floor -- holding at the baseline abs-Δ passes; rising above it fails.
        baseline = _values(bat={"AB": 34, "H": 13})
        assert evaluate_gate(_values(bat={"AB": 34, "H": 13}), baseline).passed
        regressed = evaluate_gate(_values(bat={"AB": 35, "H": 13}), baseline)
        assert not regressed.passed
        assert any(v.name == "batting.AB" for v in regressed.violations)


class TestBaselineIO:
    """AC-1/AC-5: baseline load + --update-baseline write."""

    def test_load_absent_returns_none(self, tmp_path: Path) -> None:
        assert load_baseline(tmp_path / "nope.json") is None

    def test_load_present_returns_value_block(self) -> None:
        baseline = load_baseline(_BASELINE_FIXTURE)
        assert baseline is not None
        assert set(baseline["axis_counters"].keys()) == {
            "dropped_pitch_events",
            "no_plays_units",
            "self_games",
        }
        # Metadata header present but ignored by the gate.
        assert "metadata" in baseline

    def test_load_truncated_json_raises_baseline_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "truncated.json"
        bad.write_text('{"pitching": {"H": {"abs_delta": 0', encoding="utf-8")
        with pytest.raises(BaselineError):
            load_baseline(bad)

    def test_load_missing_gated_stat_raises_baseline_error(
        self, tmp_path: Path
    ) -> None:
        # Valid JSON, but a gated stat block is absent -> would KeyError in the
        # gate; load_baseline turns it into an actionable BaselineError instead.
        partial = json.loads(_BASELINE_FIXTURE.read_text(encoding="utf-8"))
        del partial["pitching"]["H"]
        bad = tmp_path / "partial.json"
        bad.write_text(json.dumps(partial), encoding="utf-8")
        with pytest.raises(BaselineError):
            load_baseline(bad)

    def test_write_baseline_roundtrip(self, tmp_path: Path) -> None:
        conn = _seed_conn()
        try:
            result = compute_scoreboard(conn)
        finally:
            conn.close()
        target = tmp_path / "baselines" / "reconciliation-scoreboard.json"
        metadata = {
            "git_sha": "deadbeef",
            "db_game_count": 2,
            "snapshot_date": "2026-07-08",
        }
        write_baseline(target, result, metadata)
        # Parent dir auto-created; file written.
        assert target.exists()
        written = json.loads(target.read_text(encoding="utf-8"))
        assert written["metadata"] == metadata
        # Value block equals the fresh --json shape (metadata aside).
        expected = to_json_dict(result)
        assert written["pitching"] == expected["pitching"]
        assert written["batting"] == expected["batting"]
        assert written["axis_counters"] == expected["axis_counters"]

    def test_written_baseline_is_gate_compatible(self, tmp_path: Path) -> None:
        # A freshly-written baseline, re-loaded, passes the gate against the same
        # run (the round-trip is self-consistent).
        conn = _seed_conn()
        try:
            conn.execute("DELETE FROM games WHERE game_id = 'G_SELF'")
            conn.commit()
            result = compute_scoreboard(conn)
        finally:
            conn.close()
        target = tmp_path / "b.json"
        write_baseline(target, result, {"git_sha": "x"})
        baseline = load_baseline(target)
        assert baseline is not None
        assert evaluate_gate(to_json_dict(result), baseline).passed


class TestGateCli:
    """AC-2/AC-3/AC-5/AC-8 end-to-end through the CLI."""

    def test_baseline_absent_bootstrap_exit3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        # No baseline file at the resolved path.
        monkeypatch.setattr(
            "src.cli.report.default_baseline_path",
            lambda: tmp_path / "absent-baseline.json",
        )
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard"])
        # AC-8: distinct non-zero code (3), actionable message, NOT a crash.
        assert result.exit_code == EXIT_BASELINE_ABSENT
        assert result.exception is None or isinstance(result.exception, SystemExit)
        combined = result.output + (result.stderr or "")
        assert "No committed baseline yet" in combined
        assert "--update-baseline" in combined

    def test_self_game_fails_gate_exit1_json_stdout_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Raw seed (self_games == 1) + a self_games==0 baseline -> hard-zero fail.
        # Also proves AC-4b holds UNDER failure: stdout stays clean JSON with
        # self_games surfaced, and the violation goes to stderr with a non-zero
        # exit.
        db_path = _seed_file_db(tmp_path)
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        _use_baseline_fixture(monkeypatch)
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard", "--json"])
        assert result.exit_code == EXIT_REGRESSION
        payload = json.loads(result.stdout)
        assert payload["axis_counters"]["self_games"] == 1
        combined = result.output + (result.stderr or "")
        assert "self_games" in combined

    def test_gate_passes_exit0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        _use_baseline_fixture(monkeypatch)
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard"])
        assert result.exit_code == 0, result.output
        assert "gate passed" in result.output.lower()

    def test_gated_regression_exit1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Corrupt PB_agree's boxscore H so plays (H=2) disagree (box H=3) ->
        # batting.H abs-Δ 1 > baseline floor 0 -> gated regression.
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE player_game_batting SET h = 3 WHERE player_id = 'PB_agree'"
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        _use_baseline_fixture(monkeypatch)
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard"])
        assert result.exit_code == EXIT_REGRESSION
        combined = result.output + (result.stderr or "")
        assert "batting.H" in combined

    def test_update_baseline_writes_file_and_then_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # AC-5 end-to-end: --update-baseline writes the JSON (with metadata),
        # then a subsequent gate run against that written baseline passes.
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        baseline_path = tmp_path / "baselines" / "reconciliation-scoreboard.json"
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        monkeypatch.setattr(
            "src.cli.report.default_baseline_path", lambda: baseline_path
        )
        runner = CliRunner()
        write_result = runner.invoke(
            report_app, ["reconcile-scoreboard", "--update-baseline"]
        )
        assert write_result.exit_code == 0, write_result.output
        assert baseline_path.exists()
        written = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert set(written["metadata"].keys()) == {
            "git_sha",
            "db_game_count",
            "snapshot_date",
        }
        # The just-written baseline is now the floor -> a plain run passes.
        gate_result = runner.invoke(report_app, ["reconcile-scoreboard"])
        assert gate_result.exit_code == 0, gate_result.output

    @pytest.mark.parametrize(
        "contents",
        [
            '{"pitching": {"H": {"abs_delta": 0',            # truncated JSON
            '{"pitching": {}, "batting": {}, "axis_counters": {}}',  # missing keys
        ],
        ids=["truncated", "missing-gated-stat"],
    )
    def test_malformed_baseline_exit4_no_traceback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        contents: str,
    ) -> None:
        db_path = _seed_file_db(tmp_path, drop_self_game=True)
        baseline_path = tmp_path / "corrupt-baseline.json"
        baseline_path.write_text(contents, encoding="utf-8")
        monkeypatch.setattr(
            "src.cli.report.resolve_db_path", lambda *a, **k: db_path
        )
        monkeypatch.setattr(
            "src.cli.report.default_baseline_path", lambda: baseline_path
        )
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard"])
        # Distinct code from absent (3), actionable message, NOT a raw traceback.
        assert result.exit_code == EXIT_BASELINE_MALFORMED
        assert result.exception is None or isinstance(result.exception, SystemExit)
        combined = result.output + (result.stderr or "")
        assert "malformed or incomplete" in combined
        assert "--update-baseline" in combined


class TestHelpDocumentsBootstrapAndRefresh:
    """AC-7: the command --help documents BOTH the first-use bootstrap and the
    ongoing refresh procedure -- pinned so a future edit can't silently drop it."""

    def test_help_contains_bootstrap_and_refresh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Widen so multi-word phrases aren't wrapped apart at the 80-col default.
        monkeypatch.setenv("COLUMNS", "200")
        runner = CliRunner()
        result = runner.invoke(report_app, ["reconcile-scoreboard", "--help"])
        assert result.exit_code == 0
        out = result.output.lower()
        # FIRST-USE bootstrap section.
        assert "first use" in out
        # ONGOING refresh section.
        assert "ongoing" in out
        # The refresh mechanism and the commit step.
        assert "--update-baseline" in result.output
        assert "commit" in out
