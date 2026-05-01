"""Tests for E-228-01: generator-side matchup plumbing.

Covers AC-2, AC-3, AC-4, AC-7, AC-9, AC-10, and the corresponding test ACs
(AC-T2, AC-T3, AC-T7).  Verifies:

- ``generate_report()`` accepts ``our_team_id`` as a keyword-only param.
- ``our_team_id`` is persisted on the ``reports`` row when non-None.
- Backward compatibility: with ``our_team_id=None`` the data passed to
  ``render_report`` is structurally equivalent to today's (no matchup keys
  appear in the dict, the canonical key set is preserved).
- Feature flag: ``FEATURE_MATCHUP_ANALYSIS=0`` causes ``our_team_id`` to be
  silently dropped (treated as None).
- ``is_matchup_enabled()`` recognises the documented truthy values.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from migrations.apply_migrations import run_migrations
from src.gamechanger.crawlers.scouting import ScoutingCrawlResult
from src.gamechanger.pipelines import PlaysStageResult
from src.reports import matchup as matchup_module
from src.reports.generator import generate_report


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_report_generator.py patterns)
# ---------------------------------------------------------------------------


def _clean_plays_stage_result() -> PlaysStageResult:
    return PlaysStageResult(
        attempted=0, loaded=0, skipped=0, errored=0,
        reconcile_errors=0, auth_expired=False, deferred_game_ids=[],
    )


@pytest.fixture()
def db_path(tmp_path):
    """Create a real-schema DB on disk via the migration runner."""
    p = tmp_path / "test.db"
    run_migrations(db_path=p)
    return p


@pytest.fixture()
def fresh_conn(db_path):
    def _open():
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys=ON;")
        return c

    return _open


def _seed_baseline(conn: sqlite3.Connection) -> tuple[int, str]:
    """Insert the minimum rows ``generate_report`` needs to render.

    Returns ``(team_id, season_id)``.
    """
    # Subject team (the team being scouted)
    cursor = conn.execute(
        "INSERT INTO teams (name, public_id, season_year, membership_type) "
        "VALUES ('Subject', 'abc123', 2026, 'tracked')"
    )
    team_id = cursor.lastrowid

    season_id = "2026-spring-hs"
    conn.execute(
        "INSERT INTO seasons (season_id, name, season_type, year) "
        "VALUES (?, ?, 'spring', 2026)",
        (season_id, season_id),
    )

    conn.execute(
        "INSERT INTO scouting_runs "
        "(team_id, season_id, run_type, started_at, status) "
        "VALUES (?, ?, 'full', '2026-03-28T00:00:00Z', 'completed')",
        (team_id, season_id),
    )
    conn.commit()
    return team_id, season_id


def _seed_member_team(conn: sqlite3.Connection, name: str = "LSB Varsity") -> int:
    """Insert a member team (eligible to be passed as ``our_team_id``)."""
    cursor = conn.execute(
        "INSERT INTO teams (name, membership_type, is_active) "
        "VALUES (?, 'member', 1)",
        (name,),
    )
    conn.commit()
    return cursor.lastrowid


def _patch_generator_dependencies(
    tmp_path,
    db_path,
):
    """Return a list of patch context managers that stub external deps.

    Includes scouting crawler/loader, plays stage, spray crawl/load, the
    GameChanger client, and the report storage paths.  Returns a list ready
    to be entered via ``with contextlib.ExitStack``.
    """
    from src.gamechanger.loaders import LoadResult

    db_path_str = str(db_path)

    def _fresh_conn():
        c = sqlite3.connect(db_path_str)
        c.execute("PRAGMA foreign_keys=ON;")
        return c

    mock_client = MagicMock()
    mock_crawler = MagicMock()
    mock_crawler.scout_team.return_value = ScoutingCrawlResult(
        team_id=1, season_id="2026-spring-hs", games_crawled=1,
        games=[], boxscores={"g1": {}}, errors=0,
    )
    mock_loader = MagicMock()
    mock_loader.load_team.return_value = LoadResult(loaded=1)

    return [
        patch("src.reports.generator.get_connection", side_effect=_fresh_conn),
        patch("src.reports.generator.GameChangerClient", return_value=mock_client),
        patch("src.reports.generator.ScoutingCrawler", return_value=mock_crawler),
        patch("src.reports.generator.ScoutingLoader", return_value=mock_loader),
        patch("src.reports.generator.ensure_team_row", return_value=1),
        patch("src.reports.generator._crawl_and_load_spray"),
        patch(
            "src.reports.generator.run_plays_stage",
            return_value=_clean_plays_stage_result(),
        ),
        patch("src.reports.generator._REPO_ROOT", tmp_path),
        patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
    ]


# ---------------------------------------------------------------------------
# AC-10 / AC-T7-prerequisite: is_matchup_enabled() recognises truthy values
# ---------------------------------------------------------------------------


class TestIsMatchupEnabled:
    """Recognised truthy values: '1', 'true', 'yes' (case-insensitive)."""

    @pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", "Yes", "tRuE"])
    def test_truthy_values(self, value, monkeypatch):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", value)
        assert matchup_module.is_matchup_enabled() is True

    @pytest.mark.parametrize(
        "value", ["0", "false", "no", "", "off", "False", "anything-else"],
    )
    def test_falsy_values(self, value, monkeypatch):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", value)
        assert matchup_module.is_matchup_enabled() is False

    def test_unset_is_falsy(self, monkeypatch):
        monkeypatch.delenv("FEATURE_MATCHUP_ANALYSIS", raising=False)
        assert matchup_module.is_matchup_enabled() is False


# ---------------------------------------------------------------------------
# AC-2 / AC-T2: signature accepts our_team_id and persists it
# ---------------------------------------------------------------------------


class TestPersistence:
    """``our_team_id`` round-trips through the report row."""

    def test_our_team_id_persisted_when_non_none(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")

        # Seed subject team + member team (the our_team_id target)
        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch(
                    "src.reports.generator.render_report",
                    return_value="<html>ok</html>",
                ),
            )
            result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True

        with fresh_conn() as conn:
            row = conn.execute(
                "SELECT our_team_id FROM reports WHERE slug = ?",
                (result.slug,),
            ).fetchone()
        assert row is not None
        assert row[0] == our_team_id

    def test_our_team_id_null_when_none(
        self, db_path, tmp_path, fresh_conn,
    ):
        with fresh_conn() as conn:
            _seed_baseline(conn)

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch(
                    "src.reports.generator.render_report",
                    return_value="<html>ok</html>",
                ),
            )
            result = generate_report("abc123", our_team_id=None)

        assert result.success is True

        with fresh_conn() as conn:
            row = conn.execute(
                "SELECT our_team_id FROM reports WHERE slug = ?",
                (result.slug,),
            ).fetchone()
        assert row is not None
        assert row[0] is None


# ---------------------------------------------------------------------------
# AC-9 / AC-T7: feature flag disables our_team_id even if passed
# ---------------------------------------------------------------------------


class TestFeatureFlagSuppression:
    """When FEATURE_MATCHUP_ANALYSIS is off, our_team_id is dropped to None."""

    def test_flag_off_drops_our_team_id(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        # Explicitly disabled
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "0")

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch(
                    "src.reports.generator.render_report",
                    return_value="<html>ok</html>",
                ),
            )
            # Caller passes our_team_id=42 but the flag is OFF
            result = generate_report("abc123", our_team_id=our_team_id)

        # Generation should still succeed -- no exception, no error
        assert result.success is True

        # Persisted column must be NULL despite the caller passing a value
        with fresh_conn() as conn:
            row = conn.execute(
                "SELECT our_team_id FROM reports WHERE slug = ?",
                (result.slug,),
            ).fetchone()
        assert row[0] is None, (
            "FEATURE_MATCHUP_ANALYSIS=0 must override caller-supplied "
            "our_team_id (treated as None)."
        )

    def test_flag_unset_drops_our_team_id(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        monkeypatch.delenv("FEATURE_MATCHUP_ANALYSIS", raising=False)

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch(
                    "src.reports.generator.render_report",
                    return_value="<html>ok</html>",
                ),
            )
            result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True

        with fresh_conn() as conn:
            row = conn.execute(
                "SELECT our_team_id FROM reports WHERE slug = ?",
                (result.slug,),
            ).fetchone()
        assert row[0] is None


# ---------------------------------------------------------------------------
# AC-4 / AC-T3: backward-compat regression -- matchup-off path is unchanged
# ---------------------------------------------------------------------------


# Canonical set of keys ``render_report`` receives from the matchup-off path.
# This is the v1 shape.  E-228-14 added ``matchup_data`` to the dict for ALL
# paths (set to None on the matchup-off path); the renderer interprets None
# as "hide the Game Plan section entirely" -- which is the byte-identical
# fallback for the matchup-off path (AC-7).
_EXPECTED_RENDER_DATA_KEYS = frozenset({
    "team",
    "generated_at",
    "expires_at",
    "freshness_date",
    "game_count",
    "recent_form",
    "pitching",
    "batting",
    "spray_charts",
    "roster",
    "runs_scored_avg",
    "runs_allowed_avg",
    "team_fps_pct",
    "team_pitches_per_pa",
    "has_plays_data",
    "plays_game_count",
    "pitching_workload",
    "generation_date",
    "starter_prediction",
    "enriched_prediction",
    "show_predicted_starter",
    "matchup_data",
})


# Substrings that, if present in the data dict's keys, indicate matchup
# content has leaked into the matchup-off path.  E-228-14 introduced the
# single key ``matchup_data`` (carrying None on the matchup-off path -- the
# renderer hides the section entirely on None).  All other matchup-related
# substrings still indicate a layout regression.
_MATCHUP_KEY_SUBSTRINGS = ("our_team", "game_plan", "lsb_")


class TestBackwardCompatRegression:
    """The matchup-off path passes the SAME data shape to render_report as today.

    Strategy: capture the data dict given to ``render_report`` when calling
    ``generate_report(public_id, our_team_id=None)`` and assert that:

    1. The dict's keys exactly match the v1 canonical set, and
    2. No matchup-related substrings appear in any key.

    This is the "lighter regression check" promised by E-228-01 AC-4 -- the
    heavier byte-identical baseline-fixture machinery is deferred to E-231.
    """

    def test_matchup_off_render_data_shape_is_canonical(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        # Ensure the matchup feature is OFF for this test (default behavior)
        monkeypatch.delenv("FEATURE_MATCHUP_ANALYSIS", raising=False)

        with fresh_conn() as conn:
            _seed_baseline(conn)

        captured: dict = {}

        def _capture_render(data):
            # Deep-ish copy so substitution does not mutate the caller's data.
            captured["data"] = dict(data)
            return "<html>captured</html>"

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch(
                    "src.reports.generator.render_report",
                    side_effect=_capture_render,
                ),
            )
            result = generate_report("abc123", our_team_id=None)

        assert result.success is True
        assert "data" in captured, "render_report was not invoked"

        # Substitute non-deterministic fields with placeholders before
        # asserting on the dict structure.  Per AC-4: deterministic
        # substitution of generated_at, expires_at, slug.  ``slug`` is not in
        # the data dict (it is a generated-row attribute), but
        # ``generation_date`` is derived from ``generated_at`` so we
        # substitute it as well.
        data = dict(captured["data"])
        if "generated_at" in data:
            data["generated_at"] = "<SUBSTITUTED>"
        if "expires_at" in data:
            data["expires_at"] = "<SUBSTITUTED>"
        if "generation_date" in data:
            data["generation_date"] = "<SUBSTITUTED>"

        actual_keys = frozenset(data.keys())

        # AC-T3(a): exact key set match -- catches additions and removals.
        # Format the diff explicitly so a layout regression points at the
        # specific keys that changed.
        added = actual_keys - _EXPECTED_RENDER_DATA_KEYS
        removed = _EXPECTED_RENDER_DATA_KEYS - actual_keys
        assert actual_keys == _EXPECTED_RENDER_DATA_KEYS, (
            "Layout regression detected in matchup-off render data:\n"
            f"  added keys: {sorted(added) or '<none>'}\n"
            f"  removed keys: {sorted(removed) or '<none>'}\n"
            "If this is a deliberate layout change, update "
            "_EXPECTED_RENDER_DATA_KEYS in tests/test_generator_matchup.py."
        )

        # AC-T3(b): no matchup-related substrings should appear in any key.
        for key in actual_keys:
            for token in _MATCHUP_KEY_SUBSTRINGS:
                assert token not in key.lower(), (
                    f"Unexpected matchup-related key {key!r} in matchup-off "
                    f"render data (matched substring {token!r}). "
                    "E-228-01 must not add matchup data to the renderer; "
                    "that ships in E-228-12/14."
                )

        # AC-7 (E-228-14): the matchup-off path passes matchup_data=None to
        # the renderer, which hides the Game Plan section entirely.
        assert data.get("matchup_data") is None, (
            "E-228-14 AC-7: matchup-off path must pass matchup_data=None "
            "to the renderer; got %r" % (data.get("matchup_data"),)
        )

    def test_matchup_off_rendered_html_structural_markers(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        """Render the actual HTML on the matchup-off path and assert
        structural markers are stable.

        This is the second half of AC-4 (E-228-01) and addresses the
        Codex Phase 4b MUST FIX 3 finding that the data-shape assertion
        alone does NOT catch template restructures (HTML/class changes
        that bypass the data dict).  This test FAILS LOUDLY when:

        - Any canonical section header (Predicted Starter, Pitching,
          Batting, Batter Tendencies, Roster) goes missing or is
          renamed.
        - Any Game Plan / matchup marker leaks into the matchup-off
          render output (``game-plan-`` CSS class or "Game Plan" header).
        - The number of top-level ``<h2 class="section-header">`` tags
          deviates from the expected count.

        The heavier byte-identical baseline-fixture machinery is still
        deferred to E-231; this lighter test is the regression backstop
        for matchup-off layout stability.
        """
        monkeypatch.delenv("FEATURE_MATCHUP_ANALYSIS", raising=False)

        with fresh_conn() as conn:
            _seed_baseline(conn)

        captured_html: dict[str, str] = {}

        # Wrap render_report so we get the real rendered HTML.  We
        # cannot let the wrapped function write to disk directly because
        # the generator passes a temp path, but render_report itself
        # just returns the HTML string -- the generator handles disk IO.
        from src.reports.generator import render_report as _real_render

        def _capture_real_render(data):
            html = _real_render(data)
            captured_html["html"] = html
            return html

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch(
                    "src.reports.generator.render_report",
                    side_effect=_capture_real_render,
                ),
            )
            result = generate_report("abc123", our_team_id=None)

        assert result.success is True
        html = captured_html.get("html", "")
        assert html, "render_report did not produce HTML"

        # AC-T3(c): unconditional canonical structural markers MUST be
        # present.  ``Pitching`` and ``Batting`` <h2 section-header>
        # blocks render in scouting_report.html regardless of whether
        # there is data (the table body becomes empty/no-data, but the
        # header still emits).  These tokens are the structural anchors
        # of the off-path baseline -- a template restructure that
        # renames the class, header text, or removes either header MUST
        # fail this test.
        for marker in (
            'class="section-header">Pitching</h2>',
            'class="section-header batting-section">Batting</h2>',
        ):
            assert marker in html, (
                f"Canonical section marker missing from matchup-off "
                f"render output: {marker!r}.  This indicates a layout "
                f"regression in scouting_report.html or its renderer."
            )

        # AC-T3(d): NO matchup-related markers may appear on the
        # matchup-off path.  These are the load-bearing structural
        # tokens introduced by E-228 -- their presence indicates a leak
        # of matchup template content into the matchup-off path.
        for forbidden in (
            "Game Plan</h2>",
            "game-plan-section",
            "game-plan-subsection",
            "game-plan-intro",
        ):
            assert forbidden not in html, (
                f"Matchup-only marker {forbidden!r} leaked into the "
                f"matchup-off rendered HTML.  E-228 must hide the "
                f"Game Plan section entirely when matchup_data is None."
            )

        # AC-T3(e): top-level section headers count must match the
        # matchup-off baseline for the bare-seed fixture.  Only sections
        # that render unconditionally (Pitching, Batting) appear with
        # this minimal seed.  Conditional sections (Roster, Predicted
        # Starter, Batter Tendencies, etc.) require richer data and are
        # exercised by other targeted tests.  If a future template
        # change adds a new UNCONDITIONAL ``<h2 class="section-header">``,
        # update both the count and the marker list above together so
        # the regression is intentional.
        import re
        section_headers = re.findall(
            r'<h2[^>]*class="[^"]*section-header[^"]*"[^>]*>([^<]*)</h2>',
            html,
        )
        expected_unconditional_headers = ["Pitching", "Batting"]
        assert section_headers == expected_unconditional_headers, (
            f"Top-level section headers in matchup-off rendered HTML "
            f"differ from baseline.\n"
            f"  expected: {expected_unconditional_headers}\n"
            f"  actual:   {section_headers}\n"
            f"Update both this list and the marker assertions above "
            f"when a deliberate template change adds or removes a section."
        )


# ---------------------------------------------------------------------------
# E-228-14 AC-T1, AC-T2, AC-T3, AC-T4, AC-T5, AC-T6, AC-T7:
# end-to-end matchup orchestration tests
# ---------------------------------------------------------------------------


def _build_minimal_matchup_inputs(*, opponent_team_id: int = 1, our_team_id: int = 2):
    """Build a non-empty MatchupInputs the engine can produce a non-suppress
    analysis from (so the orchestration block actually exercises enrich)."""
    import datetime

    from src.reports.matchup import MatchupInputs

    return MatchupInputs(
        opponent_team={"id": opponent_team_id, "name": "Opponent", "public_id": "abc123"},
        opponent_top_hitters=[
            {
                "player_id": "p1", "name": "Smith", "jersey_number": "14",
                "pa": 35, "ab": 30, "h": 12, "bb": 4, "so": 5, "hbp": 1,
                "doubles": 3, "triples": 0, "hr": 2, "shf": 0,
                "obp": 0.485, "slg": 0.633, "ops": 1.118,
                "fps_seen": 30, "fps_swing_count": 12,
                "chase_rate": 0.20, "swing_rate_by_count": {},
            },
        ],
        opponent_pitching=[],
        opponent_losses=[
            {
                "game_id": "g1", "game_date": "2026-03-15",
                "opposing_score": 5, "opponent_score": 8, "margin": -3,
                "starter_name": "Doe", "starter_ip_outs": 9, "starter_er": 5,
                "starter_decision": "L", "bullpen_er": 2,
            },
        ],
        # Real keys produced by ``get_sb_tendency`` in src/api/db.py.
        opponent_sb_profile={
            "sb_attempts": 8, "sb_successes": 6, "sb_success_rate": 0.75,
            "catcher_cs_against_attempts": 5,
            "catcher_cs_against_count": 2,
            "catcher_cs_against_rate": 0.40,
        },
        # Real keys produced by ``get_first_inning_pattern`` in src/api/db.py.
        opponent_first_inning_pattern={
            "games_played": 8,
            "games_with_first_inning_runs_scored": 4,
            "games_with_first_inning_runs_allowed": 3,
            "first_inning_scored_rate": 0.5,
            "first_inning_allowed_rate": 0.375,
        },
        opponent_roster_spray=[],
        lsb_team={"id": our_team_id, "name": "LSB Varsity"},
        lsb_pitching=[],
        reference_date=datetime.date(2026, 3, 28),
        season_id="2026-spring-hs",
    )


def _build_enriched_matchup_for_inputs(inputs):
    """Build a fake EnrichedMatchup the LLM would have returned for these inputs."""
    from src.reports.llm_matchup import EnrichedMatchup, HitterCue
    from src.reports.matchup import compute_matchup

    analysis = compute_matchup(inputs)
    cues = [
        HitterCue(player_id=h.player_id,
                  cue=f"Pitch {h.name} carefully ({h.pa} PA, .{int(h.slg * 1000):03d} SLG).")
        for h in analysis.threat_list
    ]
    return analysis, EnrichedMatchup(
        analysis=analysis,
        game_plan_intro="Plan the at-bats early and limit damage in the gap.",
        hitter_cues=cues,
        sb_profile_prose="They run aggressively (8 attempts, 75% success).",
        first_inning_prose="Strong first innings -- score in 50% of games.",
        loss_recipe_prose="Most losses come when the starter gets shelled.",
        model_used="anthropic/claude-haiku-4-5-20251001",
    )


class TestEndToEndMatchupOrchestration:
    """E-228-14 AC-T1: full Game Plan section end-to-end through generate_report.

    The strategy: drive the orchestration with realistic mocked inputs by
    patching ``build_matchup_inputs`` (returns a fixture ``MatchupInputs``)
    and ``enrich_matchup`` (returns a fixture ``EnrichedMatchup``).  The
    test asserts the rendered HTML contains the Game Plan section header,
    each sub-section, the LLM-authored prose verbatim, and the deterministic
    pull-tendency citation format.
    """

    def test_full_game_plan_section_renders_with_all_subsections(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")  # is_llm_available -> True

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        inputs = _build_minimal_matchup_inputs(our_team_id=our_team_id)
        analysis, enriched = _build_enriched_matchup_for_inputs(inputs)

        from contextlib import ExitStack

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch("src.reports.matchup.build_matchup_inputs",
                      return_value=inputs),
            )
            stack.enter_context(
                patch("src.reports.llm_matchup.enrich_matchup",
                      return_value=enriched),
            )
            result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True
        # Read the rendered HTML from disk.
        html_path = tmp_path / "data" / f"reports/{result.slug}.html"
        html = html_path.read_text(encoding="utf-8")

        # AC-T1: Game Plan header present.
        assert "Game Plan" in html
        # All 6 sub-section headers present.
        assert "Top Hitters" in html
        assert "Eligible Opposing Pitchers" in html
        assert "Stolen-Base Profile" in html
        assert "First-Inning Tendency" in html
        assert "Loss Recipe" in html
        assert "Eligible LSB Pitchers" in html
        # Section opener (LLM-authored game_plan_intro) preserved.
        assert "Plan the at-bats early" in html
        # Per-hitter cue (LLM-authored, with parenthetical) preserved verbatim.
        assert "Pitch Smith carefully" in html
        assert "(35 PA, .633 SLG)" in html
        # SB / first-inning / loss-recipe LLM prose preserved.
        assert "They run aggressively" in html
        assert "Strong first innings" in html
        assert "Most losses come when the starter gets shelled" in html


class TestLLMUnavailableFallback:
    """E-228-14 AC-T2: report renders with deterministic content when
    OPENROUTER_API_KEY is unset; no exception surfaces."""

    def test_report_renders_without_llm_when_api_key_missing(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        inputs = _build_minimal_matchup_inputs(our_team_id=our_team_id)

        from contextlib import ExitStack

        captured: dict = {}

        def _capture_render(data):
            captured["data"] = dict(data)
            return "<html>captured</html>"

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch("src.reports.matchup.build_matchup_inputs",
                      return_value=inputs),
            )
            # If enrich_matchup is called, the test fails (key missing).
            stack.enter_context(
                patch("src.reports.llm_matchup.enrich_matchup",
                      side_effect=AssertionError("LLM should not be called")),
            )
            stack.enter_context(
                patch("src.reports.generator.render_report",
                      side_effect=_capture_render),
            )
            result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True
        from src.reports.matchup import MatchupAnalysis
        # Renderer received a bare MatchupAnalysis, NOT an EnrichedMatchup.
        md = captured["data"].get("matchup_data")
        assert isinstance(md, MatchupAnalysis), (
            f"Expected bare MatchupAnalysis on LLM-unavailable path, got {type(md).__name__}"
        )


class TestLLMErrorSwallowed:
    """E-228-14 AC-T3: report renders with deterministic content when LLM raises."""

    def test_llm_exception_logged_and_falls_back(
        self, db_path, tmp_path, fresh_conn, monkeypatch, caplog,
    ):
        import logging

        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        inputs = _build_minimal_matchup_inputs(our_team_id=our_team_id)

        from contextlib import ExitStack

        captured: dict = {}

        def _capture_render(data):
            captured["data"] = dict(data)
            return "<html>captured</html>"

        with caplog.at_level(logging.WARNING, logger="src.reports.generator"):
            with ExitStack() as stack:
                for cm in _patch_generator_dependencies(tmp_path, db_path):
                    stack.enter_context(cm)
                stack.enter_context(
                    patch("src.reports.matchup.build_matchup_inputs",
                          return_value=inputs),
                )
                stack.enter_context(
                    patch("src.reports.llm_matchup.enrich_matchup",
                          side_effect=RuntimeError("LLM blew up")),
                )
                stack.enter_context(
                    patch("src.reports.generator.render_report",
                          side_effect=_capture_render),
                )
                result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True
        from src.reports.matchup import MatchupAnalysis
        md = captured["data"].get("matchup_data")
        assert isinstance(md, MatchupAnalysis)
        # AC-T3: WARNING is logged when LLM fails.
        assert any(
            "Matchup LLM enrichment failed" in rec.message
            for rec in caplog.records
        ), "Expected WARNING log when LLM raises"


class TestEngineSuppressHidesSection:
    """E-228-14 AC-T7 + AC-T4: when engine returns confidence='suppress',
    matchup_data passed to renderer is None (section hidden)."""

    def test_in_engine_suppress_hides_section(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        import datetime

        from src.reports.matchup import MatchupInputs

        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        # AC-T7 in-engine suppress trigger: BOTH top_hitters AND losses empty.
        suppress_inputs = MatchupInputs(
            opponent_team={"id": 1, "name": "Opponent", "public_id": "abc123"},
            opponent_top_hitters=[],
            opponent_pitching=[],
            opponent_losses=[],
            opponent_sb_profile={"sb_attempts": 0, "games_played": 0},
            opponent_first_inning_pattern={"games_played": 0},
            opponent_roster_spray=[],
            lsb_team={"id": our_team_id, "name": "LSB Varsity"},
            lsb_pitching=[],
            reference_date=datetime.date(2026, 3, 28),
            season_id="2026-spring-hs",
        )

        from contextlib import ExitStack

        captured: dict = {}

        def _capture_render(data):
            captured["data"] = dict(data)
            return "<html>captured</html>"

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            stack.enter_context(
                patch("src.reports.matchup.build_matchup_inputs",
                      return_value=suppress_inputs),
            )
            # If enrich_matchup is called when confidence==suppress, that's a bug.
            stack.enter_context(
                patch("src.reports.llm_matchup.enrich_matchup",
                      side_effect=AssertionError("enrich_matchup must not be called on suppress")),
            )
            stack.enter_context(
                patch("src.reports.generator.render_report",
                      side_effect=_capture_render),
            )
            result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True
        # AC-5/AC-T7: matchup_data is None (renderer hides Game Plan).
        assert captured["data"].get("matchup_data") is None, (
            "AC-T7: in-engine suppress must hide Game Plan via matchup_data=None"
        )


class TestSequencingAfterReconciliation:
    """E-228-14 AC-T6: matchup pipeline runs AFTER plays/reconciliation."""

    def test_matchup_runs_after_plays_stage(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        with fresh_conn() as conn:
            _seed_baseline(conn)
            our_team_id = _seed_member_team(conn)

        inputs = _build_minimal_matchup_inputs(our_team_id=our_team_id)
        _, enriched = _build_enriched_matchup_for_inputs(inputs)

        # Track call order via a shared list.
        call_order: list[str] = []

        def _plays_side_effect(*args, **kwargs):
            call_order.append("run_plays_stage")
            return _clean_plays_stage_result()

        def _build_inputs_side_effect(*args, **kwargs):
            call_order.append("build_matchup_inputs")
            return inputs

        from contextlib import ExitStack

        with ExitStack() as stack:
            patches = _patch_generator_dependencies(tmp_path, db_path)
            # Replace the run_plays_stage patch with our order-tracking version.
            patches = [
                p for p in patches
                if "run_plays_stage" not in str(p)
            ]
            for cm in patches:
                stack.enter_context(cm)
            stack.enter_context(
                patch("src.reports.generator.run_plays_stage",
                      side_effect=_plays_side_effect),
            )
            stack.enter_context(
                patch("src.reports.matchup.build_matchup_inputs",
                      side_effect=_build_inputs_side_effect),
            )
            stack.enter_context(
                patch("src.reports.llm_matchup.enrich_matchup",
                      return_value=enriched),
            )
            result = generate_report("abc123", our_team_id=our_team_id)

        assert result.success is True
        # AC-T6: plays stage (reconciliation) runs BEFORE matchup pipeline.
        assert "run_plays_stage" in call_order
        assert "build_matchup_inputs" in call_order
        plays_idx = call_order.index("run_plays_stage")
        matchup_idx = call_order.index("build_matchup_inputs")
        assert plays_idx < matchup_idx, (
            f"AC-T6: matchup must run AFTER plays/reconciliation; "
            f"got order {call_order!r}"
        )


class TestOurTeamIdNoneSkipsMatchup:
    """E-228-14 AC-T5: our_team_id=None hides section AND backward-compat is preserved."""

    def test_our_team_id_none_does_not_invoke_matchup(
        self, db_path, tmp_path, fresh_conn, monkeypatch,
    ):
        monkeypatch.setenv("FEATURE_MATCHUP_ANALYSIS", "1")  # flag ON, but our_team_id=None
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        with fresh_conn() as conn:
            _seed_baseline(conn)

        from contextlib import ExitStack

        captured: dict = {}

        def _capture_render(data):
            captured["data"] = dict(data)
            return "<html>captured</html>"

        with ExitStack() as stack:
            for cm in _patch_generator_dependencies(tmp_path, db_path):
                stack.enter_context(cm)
            # If matchup is invoked, the test fails.
            stack.enter_context(
                patch("src.reports.matchup.build_matchup_inputs",
                      side_effect=AssertionError("build_matchup_inputs must not be called when our_team_id is None")),
            )
            stack.enter_context(
                patch("src.reports.generator.render_report",
                      side_effect=_capture_render),
            )
            result = generate_report("abc123", our_team_id=None)

        assert result.success is True
        # AC-T5: matchup_data is None when our_team_id is None.
        assert captured["data"].get("matchup_data") is None
