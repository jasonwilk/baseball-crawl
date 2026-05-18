"""Tests for E-229-07 coach call sheet renderer.

Covers AC-9 (a)-(i):
  (a) alphabetical-by-name sort produces deterministic row order
  (b) NO batting_order conditional code path (grep AC)
  (c) NO flagged-first partition logic (grep AC)
  (d) legend content from module constant
  (e) zero-coverage state per AC-8
  (f) no-outliers state per AC-8a
  (g) cell contents (zone letter vs center-dot)
  (h) header coverage cue
  (i) NOTE column renders rationale + None=blank
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from src.reports.positioning import COVERED_POSITIONS
from src.reports.positioning_call_sheet import (
    _DEFAULT_CELL,
    _display_name,
    _sort_alphabetical,
    render_call_sheet_context,
)
from tests.conftest import load_real_schema


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "test.db"
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    load_real_schema(c)
    c.execute(
        "INSERT INTO teams (id, name, public_id, season_year, membership_type) "
        "VALUES (1, 'Opp Bears', 'opp-bears', 2026, 'tracked')"
    )
    c.execute(
        "INSERT INTO teams (id, name, membership_type) "
        "VALUES (99, 'LSB Varsity', 'member')"
    )
    c.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES ('2026-spring-hs', '2026', 'spring-hs', 2026)"
    )
    c.commit()
    yield c
    c.close()


def _seed_player(conn, player_id, *, first="First", last="Last"):
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, first_name, last_name) "
        "VALUES (?, ?, ?)",
        (player_id, first, last),
    )


def _seed_roster(conn, player_id, jersey,
                 team_id=1, season_id="2026-spring-hs"):
    if jersey is not None:
        conn.execute(
            "INSERT OR IGNORE INTO team_rosters (team_id, player_id, "
            "season_id, jersey_number) VALUES (?, ?, ?, ?)",
            (team_id, player_id, season_id, jersey),
        )


def _seed_aggregate(
    conn, position, *,
    bip_count=60, is_low_confidence=0,
    team_id=1, season_id="2026-spring-hs",
    perspective_team_id=1,
):
    conn.execute(
        """
        INSERT INTO team_position_aggregate (
            team_id, season_id, perspective_team_id, position,
            star_x, star_y, bip_count, is_low_confidence
        ) VALUES (?, ?, ?, ?, 160.0, 200.0, ?, ?)
        """,
        (team_id, season_id, perspective_team_id, position,
         bip_count, is_low_confidence),
    )


def _seed_batter_row(
    conn, *, player_id, position,
    zone_id=None, is_thin=0, bip_count=20,
    direction_deviation=0, depth_deviation=0,
    team_id=1, season_id="2026-spring-hs", perspective_team_id=1,
):
    conn.execute(
        """
        INSERT INTO batter_positioning (
            player_id, team_id, season_id, perspective_team_id, position,
            direction_deviation, depth_deviation, zone_id,
            is_thin, bip_count, hr_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (player_id, team_id, season_id, perspective_team_id, position,
         direction_deviation, depth_deviation, zone_id, is_thin, bip_count),
    )


def _seed_full_opponent(conn):
    """Seed 3 batters across the 6 covered positions.

    p1 (Ramirez, #7) -- flagged at LF (zone A)
    p2 (Davis, #11) -- flagged at LF (zone B) and RF (zone H)
    p3 (Aaron, #3) -- all default
    """
    for position in COVERED_POSITIONS:
        _seed_aggregate(conn, position)
    _seed_player(conn, "p1", first="Hank", last="Ramirez")
    _seed_roster(conn, "p1", "7")
    _seed_batter_row(conn, player_id="p1", position="LF",
                     zone_id="A", direction_deviation=-1, depth_deviation=-1)
    for position in ("CF", "RF", "3B", "SS", "2B"):
        _seed_batter_row(conn, player_id="p1", position=position)

    _seed_player(conn, "p2", first="Marcus", last="Davis")
    _seed_roster(conn, "p2", "11")
    _seed_batter_row(conn, player_id="p2", position="LF",
                     zone_id="B", direction_deviation=-1)
    _seed_batter_row(conn, player_id="p2", position="RF",
                     zone_id="H", direction_deviation=1, depth_deviation=1)
    for position in ("CF", "3B", "SS", "2B"):
        _seed_batter_row(conn, player_id="p2", position=position)

    _seed_player(conn, "p3", first="Tony", last="Aaron")
    _seed_roster(conn, "p3", "3")
    for position in COVERED_POSITIONS:
        _seed_batter_row(conn, player_id="p3", position=position)
    conn.commit()


# ---------------------------------------------------------------------------
# AC-9 (a): alphabetical sort
# ---------------------------------------------------------------------------


class TestAlphabeticalSort:
    def test_rows_sorted_alphabetically_by_last_name(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        names = [r["display_name"] for r in ctx["rows"]]
        # Aaron < Davis < Ramirez (alphabetical).
        assert names == ["AARON, Tony", "DAVIS, Marcus", "RAMIREZ, Hank"]

    def test_same_last_name_uses_first_name_tiebreaker(self):
        rows = [
            {"last_name": "Smith", "first_name": "Bob", "jersey_number": "9"},
            {"last_name": "Smith", "first_name": "Aaron", "jersey_number": "3"},
        ]
        sorted_rows = _sort_alphabetical(rows)
        assert [r["first_name"] for r in sorted_rows] == ["Aaron", "Bob"]

    def test_no_flagged_first_grouping(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        names = [r["display_name"] for r in ctx["rows"]]
        # The "all-default" batter (Aaron) sits FIRST in alphabetical
        # order despite being unflagged. If the code accidentally
        # partitioned by is_flagged, Aaron would land after the
        # flagged batters (Davis, Ramirez).
        assert names[0].startswith("AARON")
        # Per AC-4: alphabetical ordering is strict; default batters
        # are NOT pushed to the end.


# ---------------------------------------------------------------------------
# AC-9 (b) + (c): grep ACs
# ---------------------------------------------------------------------------


class TestGrepACs:
    """AC-9 (b): no `batting_order`-conditional code path.
    AC-9 (c): no flagged-first partition logic.
    AC-9 (i): NOTE column rendered in template.
    """

    def _module_path(self):
        return (
            Path(__file__).parent.parent
            / "src" / "reports" / "positioning_call_sheet.py"
        )

    def _template_path(self):
        return (
            Path(__file__).parent.parent
            / "src" / "api" / "templates" / "reports"
            / "positioning_call_sheet.html"
        )

    def test_no_batting_order_code_reference(self):
        """AC-9 (b): the module must NOT contain a `batting_order`
        conditional. References inside comments pointing to IDEA-077
        are permitted.
        """
        text = self._module_path().read_text()
        # Strip out comments + docstrings so we're checking actual code.
        # Simple heuristic: drop lines starting with `#` (after stripping)
        # and triple-quoted blocks.
        code_lines: list[str] = []
        in_triple = False
        triple_delim = None
        for line in text.split("\n"):
            stripped = line.strip()
            # Toggle triple-quoted blocks. Handle both """ and '''.
            for delim in ('"""', "'''"):
                if not in_triple and stripped.startswith(delim):
                    if stripped.count(delim) >= 2:
                        # Single-line docstring.
                        break
                    in_triple = True
                    triple_delim = delim
                    break
                if in_triple and triple_delim and triple_delim in stripped:
                    in_triple = False
                    triple_delim = None
                    break
            else:
                if not in_triple and not stripped.startswith("#"):
                    code_lines.append(line)
        code_text = "\n".join(code_lines)
        # No `batting_order` reference in the executable code section.
        assert "batting_order" not in code_text, (
            "AC-9 (b) violation: positioning_call_sheet.py contains "
            "a batting_order code reference"
        )

    def test_no_flagged_first_partition_logic(self):
        """AC-9 (c): no partition-by-flag logic. The sort key MUST NOT
        include `is_flagged` as a primary or secondary sort term."""
        text = self._module_path().read_text()
        # Search the code for partition-style patterns.
        # `is_flagged` may appear as a row-level attribute (e.g.,
        # `row["is_flagged"]` for general flag tracking) but MUST NOT
        # appear inside a sort key expression or partition list.
        # Look for the specific anti-patterns.
        # Disallowed patterns:
        #   `key=lambda r: (... r.is_flagged ...)` or `r["is_flagged"]`
        #   inside a sort key tuple
        #   `if r.is_flagged ...` partition splits before sort
        disallowed_patterns = [
            r"key=lambda[^\n]*is_flagged",
            r"sorted\([^)]*is_flagged",
            # The classic "split into two lists then concat" pattern:
            r"\[\s*r\s+for\s+r\s+in[^\]]*if\s+(?:not\s+)?r\[?\s*['\"]?is_flagged",
        ]
        for pat in disallowed_patterns:
            assert not re.search(pat, text), (
                f"AC-9 (c) violation: positioning_call_sheet.py "
                f"contains flagged-first partition pattern: {pat}"
            )

    def test_note_column_rendered_in_template(self):
        """AC-9 (i): the NOTE column header is rendered in the template."""
        text = self._template_path().read_text()
        assert "NOTE" in text, (
            "AC-9 (i) violation: NOTE column header missing from "
            "positioning_call_sheet.html"
        )
        assert "col-note" in text, (
            "AC-9 (i) violation: NOTE column class missing from "
            "positioning_call_sheet.html"
        )


# ---------------------------------------------------------------------------
# AC-9 (d): legend content
# ---------------------------------------------------------------------------


class TestLegendContent:
    def test_legend_uses_locked_compass_long_constant(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # Locked COMPASS_LEGEND_LONG (artifact §F).
        assert ctx["compass_legend"].startswith("A in-left ·")
        assert "deep-right" in ctx["compass_legend"]


# ---------------------------------------------------------------------------
# AC-9 (e): zero-coverage state
# ---------------------------------------------------------------------------


class TestZeroCoverageState:
    def test_no_aggregate_rows_yields_zero_coverage(self, conn):
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["state"] == "zero_coverage"
        assert ctx["rows"] == []

    def test_all_rows_below_threshold_yields_zero_coverage(self, conn):
        # 10 BIPs per position aggregate -> all below 15 -> zero coverage.
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=10, is_low_confidence=1)
        conn.commit()
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["state"] == "zero_coverage"

    def test_zero_coverage_message_present(self, conn):
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert "Not enough spray data" in ctx["zero_coverage_message"]


# ---------------------------------------------------------------------------
# AC-9 (f): no-outliers state per AC-8a
# ---------------------------------------------------------------------------


class TestNoOutliersState:
    def test_no_outliers_state_when_no_zone_id_rows(self, conn):
        # Full tier but every batter all-default.
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=60)
        _seed_player(conn, "p1", first="Tony", last="Aaron")
        _seed_roster(conn, "p1", "3")
        for position in COVERED_POSITIONS:
            _seed_batter_row(conn, player_id="p1", position=position)
        conn.commit()
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        assert ctx["state"] == "no_outliers"
        assert ctx["no_outliers_banner"]
        assert "No outlier batters" in ctx["no_outliers_banner"]

    def test_no_outliers_still_renders_rows_with_all_default_cells(self, conn):
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=60)
        _seed_player(conn, "p1", first="Tony", last="Aaron")
        _seed_roster(conn, "p1", "3")
        for position in COVERED_POSITIONS:
            _seed_batter_row(conn, player_id="p1", position=position)
        conn.commit()
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # AC-8a: matrix still renders, all rows are `·`.
        assert len(ctx["rows"]) == 1
        row = ctx["rows"][0]
        for position in COVERED_POSITIONS:
            assert row[f"cell_{position}"] == _DEFAULT_CELL


# ---------------------------------------------------------------------------
# AC-9 (g): cell contents
# ---------------------------------------------------------------------------


class TestCellContents:
    def test_outlier_zone_renders_letter(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        ramirez = next(r for r in ctx["rows"]
                       if r["display_name"].startswith("RAMIREZ"))
        # p1 (Ramirez) is flagged at LF zone A.
        assert ramirez["cell_LF"] == "A"
        # All other positions default.
        for position in ("CF", "RF", "3B", "SS", "2B"):
            assert ramirez[f"cell_{position}"] == _DEFAULT_CELL

    def test_default_cell_uses_center_dot(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        aaron = next(r for r in ctx["rows"]
                     if r["display_name"].startswith("AARON"))
        # p3 (Aaron) all default.
        for position in COVERED_POSITIONS:
            assert aaron[f"cell_{position}"] == "·"

    def test_thin_batter_renders_as_default(self, conn):
        """is_thin=1 batters are treated as team-default even with
        non-NULL zone_id (per AC-2 + epic TN-5)."""
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, bip_count=60)
        _seed_player(conn, "p1", first="Tim", last="Patel")
        _seed_roster(conn, "p1", "9")
        # Thin batter with zone_id at LF -- should still render `·`.
        _seed_batter_row(conn, player_id="p1", position="LF",
                         zone_id="B", direction_deviation=-1,
                         is_thin=1, bip_count=5)
        for position in ("CF", "RF", "3B", "SS", "2B"):
            _seed_batter_row(conn, player_id="p1", position=position)
        conn.commit()
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        patel = next(r for r in ctx["rows"]
                     if r["display_name"].startswith("PATEL"))
        assert patel["cell_LF"] == "·"  # thin -> default

    def test_cross_position_outliers_render_both_letters(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        davis = next(r for r in ctx["rows"]
                     if r["display_name"].startswith("DAVIS"))
        # p2 (Davis) is flagged at LF zone B AND RF zone H.
        assert davis["cell_LF"] == "B"
        assert davis["cell_RF"] == "H"
        # Other positions are default.
        for position in ("CF", "3B", "SS", "2B"):
            assert davis[f"cell_{position}"] == "·"


# ---------------------------------------------------------------------------
# AC-9 (h): header coverage cue
# ---------------------------------------------------------------------------


class TestHeader:
    def test_header_includes_opponent_name(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
            through_date="Apr 12", game_count=8,
        )
        assert ctx["header"]["opponent_name"] == "Opp Bears"

    def test_header_includes_coverage_cue_from_locked_format(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
            through_date="Apr 12", game_count=8,
        )
        assert ctx["header"]["coverage_cue"] == "Through Apr 12 (8 games)"

    def test_header_renders_in_zero_coverage_state(self, conn):
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
            opponent_name="Opp Bears",
            through_date="Apr 12", game_count=2,
        )
        assert ctx["header"]["opponent_name"] == "Opp Bears"
        assert "Apr 12" in ctx["header"]["coverage_cue"]


# ---------------------------------------------------------------------------
# AC-9 (i): NOTE column rationale
# ---------------------------------------------------------------------------


class TestRationaleNoteColumn:
    def test_rationale_threaded_into_row(self, conn):
        _seed_full_opponent(conn)
        rationales = {"p1": "Pulls grounders to left on early counts."}
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
            rationales=rationales,
        )
        ramirez = next(r for r in ctx["rows"]
                       if r["display_name"].startswith("RAMIREZ"))
        assert ramirez["rationale"] == (
            "Pulls grounders to left on early counts."
        )

    def test_rationale_none_when_not_provided(self, conn):
        _seed_full_opponent(conn)
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        for row in ctx["rows"]:
            assert row["rationale"] is None

    def test_rationale_dict_passthrough(self, conn):
        _seed_full_opponent(conn)
        rationales = {"p1": "rationale A", "p2": "rationale B"}
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
            rationales=rationales,
        )
        # Context surfaces the rationales dict for the template.
        assert ctx["rationales"] == rationales


# ---------------------------------------------------------------------------
# Display name + helper
# ---------------------------------------------------------------------------


class TestDisplayNameHelper:
    def test_last_first_format(self):
        row = {"last_name": "Ramirez", "first_name": "Hank",
               "jersey_number": "7"}
        assert _display_name(row) == "RAMIREZ, Hank"

    def test_uppercase_last_name(self):
        row = {"last_name": "smith", "first_name": "Bob",
               "jersey_number": "1"}
        assert _display_name(row) == "SMITH, Bob"

    def test_jersey_only_when_names_missing(self):
        row = {"last_name": None, "first_name": None,
               "jersey_number": "9"}
        assert _display_name(row) == "#9"

    def test_unresolved_fallback(self):
        row = {"last_name": "", "first_name": "", "jersey_number": None}
        assert _display_name(row) == "(unresolved)"


# ---------------------------------------------------------------------------
# Perspective scoping (TN-7 invariant)
# ---------------------------------------------------------------------------


class TestPerspectiveScoping:
    def test_matrix_scopes_to_chosen_perspective(self, conn):
        # Seed two perspectives; the chosen perspective's matrix
        # excludes the other perspective's batters.
        conn.execute(
            "INSERT INTO teams (id, name, membership_type) "
            "VALUES (100, 'Rival Scout', 'member')"
        )
        for position in COVERED_POSITIONS:
            _seed_aggregate(conn, position, perspective_team_id=1)
            _seed_aggregate(conn, position, perspective_team_id=100)
        # Perspective 1: 1 batter.
        _seed_player(conn, "p-mine", first="Hank", last="Ramirez")
        _seed_roster(conn, "p-mine", "7")
        for position in COVERED_POSITIONS:
            _seed_batter_row(conn, player_id="p-mine", position=position,
                             perspective_team_id=1)
        # Perspective 100: 1 different batter.
        _seed_player(conn, "p-other", first="Other", last="Wright")
        _seed_roster(conn, "p-other", "4")
        for position in COVERED_POSITIONS:
            _seed_batter_row(conn, player_id="p-other", position=position,
                             perspective_team_id=100)
        conn.commit()
        ctx = render_call_sheet_context(
            conn, "opp-bears", "2026-spring-hs",
        )
        # The picked perspective is 1 (standalone-preferred). Matrix
        # contains only Ramirez, not Wright.
        names = [r["display_name"] for r in ctx["rows"]]
        assert any("RAMIREZ" in n for n in names)
        assert not any("WRIGHT" in n for n in names)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_unknown_public_id_raises(self, conn):
        with pytest.raises(ValueError):
            render_call_sheet_context(
                conn, "nonexistent-team", "2026-spring-hs",
            )
