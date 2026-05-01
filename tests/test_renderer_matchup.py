"""Tests for E-228-14: Game Plan section rendering.

Covers:

- AC-3 / AC-T8: rendered HTML structure for the 6 sub-sections.
- AC-4: pull-tendency citations are renderer-formatted from raw fields.
- AC-5: confidence='suppress' produces no Game Plan section trace in HTML.
- AC-6: bare MatchupAnalysis (LLM unavailable) renders deterministic content
  with LLM-prose fields hidden entirely (degrade-by-hiding).
- AC-T9: data_notes render at the bottom of the correct sub-section, render
  even on LLM-fallback, and sub-sections with zero notes emit no Note line.

Strategy: build a minimal data dict, hand it to ``render_report`` directly,
and assert against the resulting HTML string.
"""

from __future__ import annotations

import datetime

import pytest

from src.reports.llm_matchup import EnrichedMatchup, HitterCue
from src.reports.matchup import (
    DataNote,
    EligiblePitcher,
    LossRecipe,
    LossRecipeBucket,
    MatchupAnalysis,
    PullTendencyNote,
    ThreatHitter,
)
from src.reports.renderer import render_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_threat(player_id: str, name: str, pa: int = 35, slg: float = 0.500) -> ThreatHitter:
    return ThreatHitter(
        player_id=player_id, name=name, jersey_number="14",
        pa=pa, obp=0.400, slg=slg, ops=0.900,
        bb_pct=0.10, k_pct=0.20, fps_swing_rate=0.50, chase_rate=0.20,
        swing_rate_by_count={}, cue_kind="pitch_around",
        supporting_stats=[f"{pa} PA", "10% BB", "20% K", f".{int(slg * 1000):03d} SLG"],
    )


def _make_pitcher(name: str, jersey: str = "21") -> EligiblePitcher:
    return EligiblePitcher(
        player_id=f"pitcher-{name}", name=name, jersey_number=jersey,
        last_outing_date="2026-03-22", days_rest=6,
        last_outing_pitches=78, workload_7d=78,
    )


def _make_minimal_analysis(
    *, confidence: str = "moderate",
    threats: list[ThreatHitter] | None = None,
    pull_notes: list[PullTendencyNote] | None = None,
    opp_pitchers: list[EligiblePitcher] | None = None,
    lsb_pitchers: list[EligiblePitcher] | None = None,
    data_notes: list[DataNote] | None = None,
    loss_recipe: LossRecipe | None = None,
) -> MatchupAnalysis:
    return MatchupAnalysis(
        confidence=confidence,
        threat_list=threats or [_make_threat("p1", "Smith")],
        pull_tendency_notes=pull_notes or [],
        # Real keys produced by ``get_sb_tendency`` in src/api/db.py.
        sb_profile_summary={
            "sb_attempts": 8,
            "sb_successes": 6,
            "sb_success_rate": 0.75,
            "catcher_cs_against_attempts": 5,
            "catcher_cs_against_count": 2,
            "catcher_cs_against_rate": 0.40,
        },
        # Real keys produced by ``get_first_inning_pattern`` in src/api/db.py.
        first_inning_summary={
            "games_played": 8,
            "games_with_first_inning_runs_scored": 4,
            "games_with_first_inning_runs_allowed": 3,
            "first_inning_scored_rate": 0.5,
            "first_inning_allowed_rate": 0.375,
        },
        loss_recipe_buckets=loss_recipe or LossRecipe(
            starter_shelled_early=LossRecipeBucket(count=2),
            bullpen_couldnt_hold=LossRecipeBucket(count=1),
            close_game_lost_late=LossRecipeBucket(count=1),
            total_losses=4,
        ),
        eligible_opposing_pitchers=opp_pitchers or [_make_pitcher("Doe")],
        eligible_lsb_pitchers=lsb_pitchers if lsb_pitchers is not None else [_make_pitcher("Jones", "31")],
        data_notes=data_notes or [],
    )


def _baseline_render_data(matchup_data) -> dict:
    """Minimum dict accepted by ``render_report`` -- we only care about the matchup section."""
    return {
        "team": {"name": "Test Team", "season_year": 2026, "record": None},
        "generated_at": "2026-03-28T00:00:00",
        "expires_at": "2026-04-11T00:00:00",
        "freshness_date": None,
        "game_count": 0,
        "recent_form": [],
        "pitching": [],
        "batting": [],
        "spray_charts": {},
        "roster": [],
        "runs_scored_avg": None,
        "runs_allowed_avg": None,
        "team_fps_pct": None,
        "team_pitches_per_pa": None,
        "has_plays_data": False,
        "plays_game_count": 0,
        "pitching_workload": {},
        "generation_date": "2026-03-28",
        "starter_prediction": None,
        "enriched_prediction": None,
        "show_predicted_starter": False,
        "matchup_data": matchup_data,
    }


# ---------------------------------------------------------------------------
# AC-T8: HTML structure for all 6 sub-sections (with full LLM enrichment)
# ---------------------------------------------------------------------------


class TestStructureWithFullEnrichment:

    def test_all_six_subsections_render(self):
        analysis = _make_minimal_analysis(
            pull_notes=[PullTendencyNote(
                player_id="p2", name="Brown", jersey_number="7",
                pull_pct=0.62, bip_count=24,
            )],
        )
        enriched = EnrichedMatchup(
            analysis=analysis,
            game_plan_intro="Approach this lineup with discipline.",
            hitter_cues=[HitterCue(player_id="p1",
                                   cue="Pitch Smith carefully (.500 SLG, 35 PA).")],
            sb_profile_prose="They run a lot (8 attempts).",
            first_inning_prose="They score early (50% of games).",
            loss_recipe_prose="Most losses are starter blowups.",
            model_used="test",
        )
        html = render_report(_baseline_render_data(enriched))

        # Section header
        assert "Game Plan" in html
        # game_plan_intro rendered immediately after header
        assert "Approach this lineup with discipline" in html
        # All 6 sub-section headers
        assert "Top Hitters" in html
        assert "Eligible Opposing Pitchers" in html
        assert "Stolen-Base Profile" in html
        assert "First-Inning Tendency" in html
        assert "Loss Recipe" in html
        assert "Eligible LSB Pitchers" in html
        # AC-3 sub-section 1: cue rendered verbatim
        assert "Pitch Smith carefully (.500 SLG, 35 PA)" in html
        # AC-4: pull-tendency note formatted from raw fields by renderer
        assert "Watch the pull from Brown #7" in html
        assert "(62% pull on 24 BIP)" in html
        # PA badge present
        assert "35 PA" in html
        # SB / first-inning / loss-recipe LLM prose preserved
        assert "They run a lot" in html
        assert "They score early" in html
        assert "Most losses are starter blowups" in html

        # Deterministic SB bullet rendered from real engine keys.
        # Fixture: 6 of 8 attempts (75% success); 2 of 5 caught (40% caught).
        assert "Stole 6 of 8 attempts" in html
        assert "75% success" in html
        assert "Threw out 2 of 5 opposing attempts" in html
        assert "40% caught" in html
        # Deterministic first-inning bullet rendered from real engine keys.
        # Fixture: 4 of 8 scored (50%); 3 of 8 allowed (38%).
        assert "Scored in 1st: 4 of 8" in html
        assert "Allowed in 1st: 3 of 8" in html


# ---------------------------------------------------------------------------
# AC-5: confidence='suppress' produces no Game Plan trace in HTML
# ---------------------------------------------------------------------------


class TestSuppressHidesSection:
    """AC-5: when section is suppressed, no Game Plan content (excluding CSS).

    The string 'Game Plan' appears once in the template's <style> block as
    a CSS comment ('/* ---- Matchup strategy section ---- */' was renamed to
    avoid this collision, but we still gate on the rendered section header
    rather than substring counts).
    """

    def test_suppress_analysis_renders_no_section_header(self):
        analysis = _make_minimal_analysis(confidence="suppress", threats=[],
                                          opp_pitchers=[], lsb_pitchers=[])
        html = render_report(_baseline_render_data(analysis))
        # AC-5: rendered section header absent; section class absent.
        assert '<h2 class="section-header">Game Plan</h2>' not in html
        assert 'class="game-plan-section"' not in html

    def test_matchup_data_none_renders_no_section_header(self):
        html = render_report(_baseline_render_data(None))
        assert '<h2 class="section-header">Game Plan</h2>' not in html
        assert 'class="game-plan-section"' not in html

    def test_suppress_no_matchup_css_in_rendered_html(self):
        """AC-5 strict: when matchup is suppressed, NO trace of the section -
        including CSS rule selectors in the <style> block.

        Compares two renders: one with matchup=None (suppressed) and one with
        full matchup data. The CSS selector substring '.game-plan-' must be
        absent in the suppressed render and present in the rendered render.
        """
        # Suppressed render -- matchup_data is None, so no CSS block emitted.
        html_suppressed = render_report(_baseline_render_data(None))
        assert ".game-plan-" not in html_suppressed

        # Rendered case -- matchup is present, CSS block is emitted.
        analysis = _make_minimal_analysis()
        html_rendered = render_report(_baseline_render_data(analysis))
        assert ".game-plan-" in html_rendered


# ---------------------------------------------------------------------------
# AC-6: bare MatchupAnalysis hides LLM-prose entirely (degrade-by-hiding)
# ---------------------------------------------------------------------------


class TestLLMUnavailableFallbackRendering:

    def test_bare_analysis_omits_game_plan_intro(self):
        analysis = _make_minimal_analysis()
        html = render_report(_baseline_render_data(analysis))
        # Section header still renders (deterministic content present)
        assert '<h2 class="section-header">Game Plan</h2>' in html
        # No game_plan_intro div in fallback (CSS class declaration in <style>
        # uses '.game-plan-intro {' -- the rendered div would use 'class="..."').
        assert 'class="game-plan-intro"' not in html

    def test_bare_analysis_renders_supporting_stats_for_top_hitters(self):
        analysis = _make_minimal_analysis(threats=[
            _make_threat("p1", "Smith", pa=35, slg=0.500),
        ])
        html = render_report(_baseline_render_data(analysis))
        # AC-6 sub-section 1 fallback: name + jersey + PA badge + raw stats
        assert "Smith" in html
        # PA badge present (rendered in the depth-badge span on the hitter name).
        assert "35 PA" in html
        # AC-6 fallback path: the supporting_stats div renders with values
        # joined by ' &middot; '. Probe a marker that is unique to this path
        # and would not appear from the PA badge alone -- ".500 SLG" is only
        # present when supporting_stats is rendered in this fixture.
        assert 'class="game-plan-hitter-stats"' in html
        assert ".500 SLG" in html
        assert "10% BB" in html  # one of the supporting stats
        assert "20% K" in html

    def test_bare_analysis_omits_sb_and_first_inning_and_loss_prose(self):
        analysis = _make_minimal_analysis()
        html = render_report(_baseline_render_data(analysis))
        # Deterministic summaries render
        assert "Stolen-Base Profile" in html
        assert "First-Inning Tendency" in html
        assert "Loss Recipe" in html
        # No LLM prose div instance (CSS class declaration is in <style> block).
        assert 'class="game-plan-prose"' not in html
        # Deterministic SB + first-inning bullets render from real engine
        # keys (regression guard against template/engine field-name drift).
        assert "Stole 6 of 8 attempts" in html
        assert "Scored in 1st: 4 of 8" in html

    def test_bare_analysis_renders_pull_tendency_notes(self):
        """AC-6: pull-tendency notes are deterministic; render unchanged on fallback."""
        analysis = _make_minimal_analysis(pull_notes=[PullTendencyNote(
            player_id="p2", name="Brown", jersey_number="7",
            pull_pct=0.62, bip_count=24,
        )])
        html = render_report(_baseline_render_data(analysis))
        assert "Watch the pull from Brown #7" in html
        assert "(62% pull on 24 BIP)" in html


# ---------------------------------------------------------------------------
# AC-4: pull-tendency citation format
# ---------------------------------------------------------------------------


class TestPullTendencyCitationFormat:

    def test_citation_uses_whole_percent(self):
        # 0.55 -> 55%, 0.625 -> 62% (banker's rounding 62.5 -> 62)
        analysis = _make_minimal_analysis(pull_notes=[PullTendencyNote(
            player_id="p2", name="Brown", jersey_number=None,
            pull_pct=0.55, bip_count=15,
        )])
        html = render_report(_baseline_render_data(analysis))
        assert "(55% pull on 15 BIP)" in html

    def test_no_jersey_omits_pound_sign(self):
        analysis = _make_minimal_analysis(pull_notes=[PullTendencyNote(
            player_id="p2", name="Brown", jersey_number=None,
            pull_pct=0.60, bip_count=20,
        )])
        html = render_report(_baseline_render_data(analysis))
        # Jersey absent -> no #N
        assert "Watch the pull from Brown (60% pull on 20 BIP)" in html


# ---------------------------------------------------------------------------
# AC-T9: data_notes render in correct sub-section
# ---------------------------------------------------------------------------


class TestDataNotesPlacement:

    def test_data_notes_appear_only_in_target_subsection(self):
        analysis = _make_minimal_analysis(data_notes=[
            DataNote(message="Early read only: Smith has 12 PA on the season.",
                     subsection="top_hitters"),
            DataNote(message="Small SB sample: 3 attempt(s) on the season.",
                     subsection="sb_profile"),
            DataNote(message="Small loss sample: 2 loss(es) on the season.",
                     subsection="loss_recipe"),
        ])
        html = render_report(_baseline_render_data(analysis))

        # All three notes render
        assert "Note: Early read only: Smith has 12 PA on the season." in html
        assert "Note: Small SB sample: 3 attempt(s) on the season." in html
        assert "Note: Small loss sample: 2 loss(es) on the season." in html

        # Each note appears exactly once
        assert html.count("Early read only: Smith has 12 PA") == 1
        assert html.count("Small SB sample") == 1
        assert html.count("Small loss sample") == 1

    def test_data_notes_render_on_llm_fallback(self):
        """AC-T9(b): data_notes render even when only bare MatchupAnalysis is available."""
        analysis = _make_minimal_analysis(data_notes=[
            DataNote(message="Thin first-inning sample: 2 game(s).",
                     subsection="first_inning"),
        ])
        # Bare MatchupAnalysis (no enrichment).
        html = render_report(_baseline_render_data(analysis))
        assert "Note: Thin first-inning sample: 2 game(s)." in html

    def test_subsection_with_no_notes_emits_no_note_line(self):
        """AC-T9(a): a sub-section with zero data_notes renders no note line."""
        analysis = _make_minimal_analysis(data_notes=[])
        html = render_report(_baseline_render_data(analysis))
        # No "Note: " prefix anywhere
        assert "Note: " not in html

    def test_multiple_notes_for_same_subsection_render_in_order(self):
        analysis = _make_minimal_analysis(data_notes=[
            DataNote(message="First note.", subsection="top_hitters"),
            DataNote(message="Second note.", subsection="top_hitters"),
        ])
        html = render_report(_baseline_render_data(analysis))
        assert "Note: First note." in html
        assert "Note: Second note." in html
        # First note appears before second in input order
        assert html.find("First note.") < html.find("Second note.")

    def test_unknown_subsection_dropped_silently(self):
        """Defensive: unknown subsection is logged + dropped, not rendered."""
        analysis = _make_minimal_analysis(data_notes=[
            DataNote(message="Should not appear.", subsection="bogus_section"),
        ])
        html = render_report(_baseline_render_data(analysis))
        assert "Should not appear" not in html


# ---------------------------------------------------------------------------
# AC-2: section ordering -- Game Plan BEFORE Predicted Starter
# ---------------------------------------------------------------------------


class TestSectionOrdering:

    def test_game_plan_renders_before_predicted_starter_when_both_present(self):
        analysis = _make_minimal_analysis()
        data = _baseline_render_data(analysis)
        # Show Predicted Starter so both sections are present
        data["show_predicted_starter"] = True
        data["starter_prediction"] = None  # "no data" path -- still renders the header
        html = render_report(data)

        # Compare positions of the rendered section headers (not CSS comments).
        gp_idx = html.find('<h2 class="section-header">Game Plan</h2>')
        ps_idx = html.find('<h2 class="section-header">Predicted Starter</h2>')
        assert gp_idx > 0, "Game Plan section header should be present"
        assert ps_idx > 0, "Predicted Starter section header should be present"
        assert gp_idx < ps_idx, (
            "AC-2: Game Plan must render BEFORE Predicted Starter"
        )

    def test_predicted_starter_keeps_position_when_matchup_hidden(self):
        """AC-2: when matchup doesn't render, Predicted Starter stays in current position."""
        data = _baseline_render_data(None)
        data["show_predicted_starter"] = True
        data["starter_prediction"] = None
        html = render_report(data)
        # Game Plan section header absent
        assert '<h2 class="section-header">Game Plan</h2>' not in html
        # Predicted Starter still present
        assert '<h2 class="section-header">Predicted Starter</h2>' in html


# ---------------------------------------------------------------------------
# AC-3: LSB pitchers sub-section gating
# ---------------------------------------------------------------------------


class TestLSBPitchersGating:

    def test_lsb_pitchers_section_renders_when_list_present(self):
        analysis = _make_minimal_analysis(lsb_pitchers=[_make_pitcher("Jones", "31")])
        html = render_report(_baseline_render_data(analysis))
        assert "Eligible LSB Pitchers" in html

    def test_lsb_pitchers_section_hidden_when_list_is_none(self):
        """When our_team_id was None at engine time, eligible_lsb_pitchers is None."""
        analysis = _make_minimal_analysis()
        analysis.eligible_lsb_pitchers = None
        html = render_report(_baseline_render_data(analysis))
        assert "Eligible LSB Pitchers" not in html

    def test_lsb_pitchers_section_renders_with_empty_list_message(self):
        analysis = _make_minimal_analysis(lsb_pitchers=[])
        html = render_report(_baseline_render_data(analysis))
        assert "Eligible LSB Pitchers" in html
        assert "No eligible LSB pitchers" in html
