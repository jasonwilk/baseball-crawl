"""Pure-engine tests for the matchup analysis engine (E-228-12).

Tests in this file build ``MatchupInputs`` fixtures by hand and exercise
:func:`src.reports.matchup.compute_matchup` directly.  No DB connection,
no HTTP, no file I/O.  See ``tests/test_matchup_inputs.py`` for the
input builder + DB integration tests.

Coverage map (AC-T2):
    (a) golden-path → "high" confidence with all sub-sections populated.
    (b) opponent has 0 games → "suppress".
    (c) opponent has 3 games → "moderate"/"low" with data_notes entries.
    (d) all 4 cue-kind classifications via parameterized fixtures.
    (e) low-PA softening → data_notes entry.
    (f) 3-bucket loss-recipe classification + uncategorized.
    (g) pull-tendency note threshold edge cases.
    (h) eligible LSB pitchers list is None when our_team_id is None.

Plus AC-T1: engine purity scan over compute_matchup's call graph.
"""

from __future__ import annotations

import ast
import datetime
import inspect
import re
from pathlib import Path

import pytest

from src.reports import matchup
from src.reports.matchup import (
    DataNote,
    EligiblePitcher,
    LossRecipe,
    MatchupAnalysis,
    MatchupInputs,
    PlayerSprayProfile,
    PullTendencyNote,
    ThreatHitter,
    compute_matchup,
)


# ---------------------------------------------------------------------------
# AC-T1: engine purity
# ---------------------------------------------------------------------------


def _engine_call_graph() -> set[str]:
    """Walk compute_matchup's transitive callees inside src.reports.matchup.

    Returns the set of fully-qualified function names that compose the
    engine -- the input builder and DB-touching helpers are NOT in this
    set.
    """
    src_path = Path(matchup.__file__)
    tree = ast.parse(src_path.read_text())

    # Map function name -> ast.FunctionDef for all top-level functions.
    funcs: dict[str, ast.FunctionDef] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            funcs[node.name] = node

    # Walk callees starting from compute_matchup.
    visited: set[str] = set()
    queue = ["compute_matchup"]
    while queue:
        name = queue.pop()
        if name in visited or name not in funcs:
            continue
        visited.add(name)
        for child in ast.walk(funcs[name]):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    callee = child.func.id
                    if callee in funcs:
                        queue.append(callee)
    return visited


def _strip_docstrings(src: str) -> str:
    """Return ``src`` with the leading docstring of every function removed.

    The purity scan must not flag legitimate prose mentions like "do not
    import sqlite3" inside docstrings.  We parse the source, walk all
    function definitions, drop the docstring node from each, and unparse
    back to text.
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] if len(body) > 1 else [ast.Pass()]
    return ast.unparse(tree)


def test_engine_purity_no_sqlite_or_httpx_or_file_io() -> None:
    """AC-T1: scan compute_matchup's call graph for forbidden imports / I/O."""
    forbidden_patterns = [
        re.compile(r"\bimport\s+sqlite3\b"),
        re.compile(r"\bfrom\s+sqlite3\b"),
        re.compile(r"\bimport\s+httpx\b"),
        re.compile(r"\bfrom\s+httpx\b"),
        re.compile(r"\bopen\s*\("),
    ]
    call_graph = _engine_call_graph()
    assert "compute_matchup" in call_graph
    for fname in call_graph:
        fn = getattr(matchup, fname)
        source = _strip_docstrings(inspect.getsource(fn))
        for pat in forbidden_patterns:
            assert not pat.search(source), (
                f"Engine purity violation in {fname}: "
                f"matched forbidden pattern {pat.pattern!r}"
            )


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_hitter(
    *,
    player_id: str = "p1",
    name: str = "Alpha Hitter",
    pa: int = 60,
    ab: int = 50,
    h: int = 18,
    hr: int = 4,
    bb: int = 8,
    so: int = 12,
    hbp: int = 2,
    sb: int = 1,
    obp: float = 0.380,
    slg: float = 0.500,
    ops: float | None = None,
    fps_seen: int = 30,
    fps_swing_count: int = 12,
    chase_rate: float = 0.10,
    swing_rate_by_count: dict[str, float] | None = None,
) -> dict:
    return {
        "player_id": player_id,
        "name": name,
        "jersey_number": "12",
        "pa": pa,
        "ab": ab,
        "h": h,
        "hr": hr,
        "bb": bb,
        "so": so,
        "hbp": hbp,
        "sb": sb,
        "obp": obp,
        "slg": slg,
        "ops": ops if ops is not None else (obp + slg),
        "fps_seen": fps_seen,
        "fps_swing_count": fps_swing_count,
        "chase_rate": chase_rate,
        "swing_rate_by_count": swing_rate_by_count or {},
    }


def _make_loss(
    *,
    game_id: str = "g1",
    game_date: str = "2026-04-10",
    opposing_score: int = 7,
    opponent_score: int = 2,
    starter_outs: int = 6,
    starter_er: int = 5,
    starter_decision: str | None = "L",
    bullpen_er: int = 0,
    starter_name: str = "Starter Name",
) -> dict:
    margin = opponent_score - opposing_score
    return {
        "game_id": game_id,
        "game_date": game_date,
        "opposing_score": opposing_score,
        "opponent_score": opponent_score,
        "margin": margin,
        "starter_name": starter_name,
        "starter_ip_outs": starter_outs,
        "starter_er": starter_er,
        "starter_decision": starter_decision,
        "bullpen_er": bullpen_er,
    }


def _make_pitching_entry(
    *,
    player_id: str = "pp1",
    name: str = "Opp Pitcher",
    last_outing_date: str = "2026-04-08",
    last_outing_days_ago: int = 2,
    last_outing_pitches: int = 65,
    pitches_7d: int = 65,
) -> dict:
    return {
        "player_id": player_id,
        "name": name,
        "jersey_number": "1",
        "last_outing_date": last_outing_date,
        "last_outing_days_ago": last_outing_days_ago,
        "last_outing_pitches": last_outing_pitches,
        "pitches_7d": pitches_7d,
        "appearances_7d": 1,
    }


def _make_inputs(
    *,
    top_hitters: list[dict] | None = None,
    pitching: list[dict] | None = None,
    losses: list[dict] | None = None,
    sb_profile: dict | None = None,
    first_inning: dict | None = None,
    roster_spray: list[PlayerSprayProfile] | None = None,
    lsb_team: dict | None = None,
    lsb_pitching: list[dict] | None = None,
    reference_date: datetime.date | None = None,
) -> MatchupInputs:
    return MatchupInputs(
        opponent_team={"id": 100, "name": "Rival HS", "public_id": "rival"},
        opponent_top_hitters=top_hitters or [],
        opponent_pitching=pitching or [],
        opponent_losses=losses or [],
        opponent_sb_profile=sb_profile or {
            "sb_attempts": 8,
            "sb_successes": 6,
            "sb_success_rate": 0.75,
            "catcher_cs_against_attempts": 10,
            "catcher_cs_against_count": 3,
            "catcher_cs_against_rate": 0.30,
        },
        opponent_first_inning_pattern=first_inning or {
            "games_played": 12,
            "games_with_first_inning_runs_scored": 5,
            "games_with_first_inning_runs_allowed": 4,
            "first_inning_scored_rate": 0.4167,
            "first_inning_allowed_rate": 0.3333,
        },
        opponent_roster_spray=roster_spray or [],
        lsb_team=lsb_team,
        lsb_pitching=lsb_pitching,
        reference_date=reference_date or datetime.date(2026, 4, 10),
        season_id="2026-spring-hs",
    )


# ---------------------------------------------------------------------------
# AC-T2 (a): golden-path -> "high" confidence
# ---------------------------------------------------------------------------


def test_golden_path_high_confidence_full_dataclass() -> None:
    top = [
        _make_hitter(
            player_id="h1", name="Alpha", pa=60,
            obp=0.400, slg=0.520, fps_seen=30, fps_swing_count=20,
        ),
        _make_hitter(
            player_id="h2", name="Bravo", pa=55,
            obp=0.380, slg=0.490, fps_seen=25, fps_swing_count=10, bb=10,
        ),
        _make_hitter(
            player_id="h3", name="Charlie", pa=42,
            obp=0.360, slg=0.470, fps_seen=22, fps_swing_count=12,
        ),
    ]
    pitching = [
        _make_pitching_entry(player_id=f"p{i}", name=f"Opp{i}")
        for i in range(4)
    ]
    losses = [
        _make_loss(game_id=f"l{i}", starter_outs=6, starter_er=5,
                   starter_decision="L")
        for i in range(4)
    ]
    spray = [
        PlayerSprayProfile(
            player_id="r1", name="Roster One", jersey_number="7",
            pull_pct=0.62, bip_count=22,
        ),
        PlayerSprayProfile(
            player_id="r2", name="Roster Two", jersey_number="9",
            pull_pct=0.40, bip_count=15,  # below pull threshold
        ),
    ]
    lsb_pitching = [_make_pitching_entry(player_id="lsb1", name="Our Ace")]

    inputs = _make_inputs(
        top_hitters=top,
        pitching=pitching,
        losses=losses,
        roster_spray=spray,
        lsb_team={"id": 1, "name": "LSB Varsity"},
        lsb_pitching=lsb_pitching,
    )
    out = compute_matchup(inputs)

    assert out.confidence == "high"
    assert len(out.threat_list) == 3
    # Each top hitter is a ThreatHitter with a cue_kind in the v1 set.
    valid_cues = {"attack_early", "pitch_around", "expand_zone", "default"}
    for t in out.threat_list:
        assert isinstance(t, ThreatHitter)
        assert t.cue_kind in valid_cues
    # Pull-tendency notes only emitted for r1 (above thresholds).
    assert len(out.pull_tendency_notes) == 1
    assert out.pull_tendency_notes[0].player_id == "r1"
    # Eligible pitcher lists populated.
    assert len(out.eligible_opposing_pitchers) == 4
    assert out.eligible_lsb_pitchers is not None
    assert len(out.eligible_lsb_pitchers) == 1
    # Loss recipe captures the shelled bucket.
    assert out.loss_recipe_buckets.starter_shelled_early.count == 4
    # SB and first-inning summaries pass through.
    assert out.sb_profile_summary["sb_attempts"] == 8
    assert out.first_inning_summary["games_played"] == 12


# ---------------------------------------------------------------------------
# AC-T2 (b): suppress when no hitters AND no losses
# ---------------------------------------------------------------------------


def test_suppress_when_no_hitters_and_no_losses() -> None:
    inputs = _make_inputs(
        top_hitters=[],
        losses=[],
        first_inning={
            "games_played": 0,
            "games_with_first_inning_runs_scored": 0,
            "games_with_first_inning_runs_allowed": 0,
            "first_inning_scored_rate": 0.0,
            "first_inning_allowed_rate": 0.0,
        },
        sb_profile={
            "sb_attempts": 0, "sb_successes": 0, "sb_success_rate": 0.0,
            "catcher_cs_against_attempts": 0, "catcher_cs_against_count": 0,
            "catcher_cs_against_rate": 0.0,
        },
    )
    out = compute_matchup(inputs)
    assert out.confidence == "suppress"
    assert out.threat_list == []
    assert out.pull_tendency_notes == []
    assert out.eligible_opposing_pitchers == []
    # Even on suppress, the engine emits the empty data_notes list (the
    # renderer hides the section regardless).
    assert out.data_notes == []


# ---------------------------------------------------------------------------
# AC-T2 (c): few games -> moderate/low + thinness notes
# ---------------------------------------------------------------------------


def test_thin_data_three_games_yields_moderate_or_low_with_notes() -> None:
    top = [_make_hitter(player_id="h1", pa=12, obp=0.300, slg=0.350)]
    inputs = _make_inputs(
        top_hitters=top,
        pitching=[_make_pitching_entry()],
        losses=[
            _make_loss(starter_outs=6, starter_er=5, starter_decision="L"),
        ],
        first_inning={
            "games_played": 3,
            "games_with_first_inning_runs_scored": 1,
            "games_with_first_inning_runs_allowed": 1,
            "first_inning_scored_rate": 0.3333,
            "first_inning_allowed_rate": 0.3333,
        },
        sb_profile={
            "sb_attempts": 1, "sb_successes": 1, "sb_success_rate": 1.0,
            "catcher_cs_against_attempts": 1, "catcher_cs_against_count": 0,
            "catcher_cs_against_rate": 0.0,
        },
    )
    out = compute_matchup(inputs)
    assert out.confidence in {"moderate", "low"}
    note_subsections = {n.subsection for n in out.data_notes}
    # AC-16 notes for sb_profile, first_inning, loss_recipe, opposing_pitchers.
    assert "first_inning" in note_subsections
    assert "loss_recipe" in note_subsections
    assert "sb_profile" in note_subsections
    assert "opposing_pitchers" in note_subsections


# ---------------------------------------------------------------------------
# AC-T2 (d): cue-kind classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape, expected_cue",
    [
        # attack_early: high FPS swing rate (>= 0.55).
        (
            {"pa": 60, "bb": 5, "so": 10, "fps_seen": 40, "fps_swing_count": 25,
             "obp": 0.330, "slg": 0.380},
            "attack_early",
        ),
        # pitch_around: high BB% AND high SLG.
        (
            {"pa": 60, "bb": 9, "so": 10, "fps_seen": 30, "fps_swing_count": 5,
             "obp": 0.420, "slg": 0.500},
            "pitch_around",
        ),
        # expand_zone: high K%.
        (
            {"pa": 60, "bb": 4, "so": 18, "fps_seen": 30, "fps_swing_count": 8,
             "obp": 0.300, "slg": 0.350},
            "expand_zone",
        ),
        # default: nothing salient.
        (
            {"pa": 60, "bb": 5, "so": 8, "fps_seen": 30, "fps_swing_count": 8,
             "obp": 0.330, "slg": 0.380},
            "default",
        ),
    ],
)
def test_cue_kind_classification_parameterized(shape, expected_cue):  # type: ignore[no-untyped-def]
    top = [_make_hitter(player_id="h1", **shape)]
    inputs = _make_inputs(
        top_hitters=top,
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=[_make_loss() for _ in range(3)],
    )
    out = compute_matchup(inputs)
    assert len(out.threat_list) == 1
    assert out.threat_list[0].cue_kind == expected_cue


# ---------------------------------------------------------------------------
# AC-T2 (e): low-PA softening
# ---------------------------------------------------------------------------


def test_low_pa_softening_emits_data_note() -> None:
    top = [
        _make_hitter(player_id="h1", name="Low PA", pa=15,
                     obp=0.380, slg=0.500),
    ]
    inputs = _make_inputs(
        top_hitters=top,
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=[_make_loss() for _ in range(3)],
    )
    out = compute_matchup(inputs)
    hitter_notes = [n for n in out.data_notes if n.subsection == "top_hitters"]
    assert len(hitter_notes) == 1
    assert "Low PA" in hitter_notes[0].message
    assert "15" in hitter_notes[0].message


# ---------------------------------------------------------------------------
# AC-T2 (f): 3-bucket loss-recipe classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "loss_kwargs, expected_bucket",
    [
        (
            # starter_shelled_early: ip_outs<12, er>=4, took L.
            {"starter_outs": 6, "starter_er": 5, "starter_decision": "L",
             "bullpen_er": 0, "opposing_score": 8, "opponent_score": 2},
            "starter_shelled_early",
        ),
        (
            # bullpen_couldnt_hold: starter ip_outs>=12, bullpen er>=3, lost.
            {"starter_outs": 15, "starter_er": 1, "starter_decision": None,
             "bullpen_er": 4, "opposing_score": 6, "opponent_score": 5},
            "bullpen_couldnt_hold",
        ),
        (
            # close_game_lost_late: |margin|<=2 and not other buckets.
            {"starter_outs": 18, "starter_er": 2, "starter_decision": "L",
             "bullpen_er": 0, "opposing_score": 4, "opponent_score": 3},
            "close_game_lost_late",
        ),
        (
            # uncategorized: starter went 18 outs, bullpen 1 ER, big loss.
            {"starter_outs": 18, "starter_er": 1, "starter_decision": None,
             "bullpen_er": 1, "opposing_score": 8, "opponent_score": 1},
            "uncategorized",
        ),
    ],
)
def test_loss_recipe_classification(loss_kwargs, expected_bucket):  # type: ignore[no-untyped-def]
    inputs = _make_inputs(
        top_hitters=[_make_hitter(pa=40)],
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=[_make_loss(**loss_kwargs)],
    )
    out = compute_matchup(inputs)
    recipe = out.loss_recipe_buckets
    if expected_bucket == "starter_shelled_early":
        assert recipe.starter_shelled_early.count == 1
        assert recipe.bullpen_couldnt_hold.count == 0
        assert recipe.close_game_lost_late.count == 0
        assert recipe.uncategorized_count == 0
    elif expected_bucket == "bullpen_couldnt_hold":
        assert recipe.bullpen_couldnt_hold.count == 1
        assert recipe.starter_shelled_early.count == 0
        assert recipe.close_game_lost_late.count == 0
        assert recipe.uncategorized_count == 0
    elif expected_bucket == "close_game_lost_late":
        assert recipe.close_game_lost_late.count == 1
        assert recipe.starter_shelled_early.count == 0
        assert recipe.bullpen_couldnt_hold.count == 0
        assert recipe.uncategorized_count == 0
    else:
        assert recipe.uncategorized_count == 1
        assert recipe.starter_shelled_early.count == 0
        assert recipe.bullpen_couldnt_hold.count == 0
        assert recipe.close_game_lost_late.count == 0


def test_loss_recipe_grounding_tuples_capped() -> None:
    """Bucket grounding lists should not grow unbounded."""
    losses = [
        _make_loss(game_id=f"g{i}", starter_outs=6, starter_er=5,
                   starter_decision="L")
        for i in range(10)
    ]
    inputs = _make_inputs(
        top_hitters=[_make_hitter(pa=40)],
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=losses,
    )
    out = compute_matchup(inputs)
    assert out.loss_recipe_buckets.starter_shelled_early.count == 10
    assert len(out.loss_recipe_buckets.starter_shelled_early.grounding) <= 5


# ---------------------------------------------------------------------------
# AC-T2 (g): pull-tendency edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pull_pct, bip_count, should_emit",
    [
        (0.54, 20, False),  # just below threshold
        (0.55, 20, True),   # exactly at threshold
        (0.60, 9, False),   # below bip count
        (0.60, 10, True),   # exactly at bip count
        (0.70, 25, True),
    ],
)
def test_pull_tendency_threshold_edges(pull_pct, bip_count, should_emit):  # type: ignore[no-untyped-def]
    spray = [
        PlayerSprayProfile(
            player_id="r1", name="Roster One", jersey_number="3",
            pull_pct=pull_pct, bip_count=bip_count,
        ),
    ]
    inputs = _make_inputs(
        top_hitters=[_make_hitter(pa=40)],
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=[_make_loss() for _ in range(3)],
        roster_spray=spray,
    )
    out = compute_matchup(inputs)
    if should_emit:
        assert len(out.pull_tendency_notes) == 1
        note = out.pull_tendency_notes[0]
        assert isinstance(note, PullTendencyNote)
        assert note.player_id == "r1"
    else:
        assert out.pull_tendency_notes == []


# ---------------------------------------------------------------------------
# AC-T2 (h): eligible LSB pitchers list None when our_team_id None
# ---------------------------------------------------------------------------


def test_lsb_pitchers_none_when_our_team_id_unset() -> None:
    inputs = _make_inputs(
        top_hitters=[_make_hitter(pa=40)],
        pitching=[_make_pitching_entry()],
        losses=[_make_loss()],
        lsb_team=None,
        lsb_pitching=None,
    )
    out = compute_matchup(inputs)
    assert out.eligible_lsb_pitchers is None
    # No "lsb_pitchers" subsection note should be emitted.
    lsb_notes = [n for n in out.data_notes if n.subsection == "lsb_pitchers"]
    assert lsb_notes == []


def test_lsb_pitchers_thin_pool_emits_note_when_set() -> None:
    inputs = _make_inputs(
        top_hitters=[_make_hitter(pa=40)],
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=[_make_loss() for _ in range(3)],
        lsb_team={"id": 1, "name": "LSB Varsity"},
        lsb_pitching=[_make_pitching_entry(player_id="lsb1")],
    )
    out = compute_matchup(inputs)
    assert out.eligible_lsb_pitchers is not None
    assert len(out.eligible_lsb_pitchers) == 1
    lsb_notes = [n for n in out.data_notes if n.subsection == "lsb_pitchers"]
    assert len(lsb_notes) == 1


# ---------------------------------------------------------------------------
# AC-13: confidence boundary + AC-4 ranking determinism
# ---------------------------------------------------------------------------


def test_top_hitter_filter_and_tiebreaker() -> None:
    """Hitters below min_pa are excluded; ties broken by PA (more sample)."""
    hitters = [
        # Below min_pa -- excluded entirely.
        _make_hitter(player_id="low", pa=5, obp=0.500, slg=0.600),
        # Two same-OPS hitters: higher PA should win.
        _make_hitter(player_id="tie_a", pa=40, obp=0.400, slg=0.450),
        _make_hitter(player_id="tie_b", pa=60, obp=0.400, slg=0.450),
        # A clear winner.
        _make_hitter(player_id="best", pa=55, obp=0.420, slg=0.520),
    ]
    inputs = _make_inputs(
        top_hitters=hitters,
        pitching=[_make_pitching_entry() for _ in range(3)],
        losses=[_make_loss() for _ in range(3)],
    )
    out = compute_matchup(inputs)
    pids = [t.player_id for t in out.threat_list]
    assert "low" not in pids
    # tie_b (higher PA) should appear before tie_a in ranking.
    assert pids.index("tie_b") < pids.index("tie_a")
    # best (highest OPS) should be first.
    assert pids[0] == "best"


def test_dataclass_default_factory_safety() -> None:
    """LossRecipe / MatchupAnalysis defaults yield distinct lists per call."""
    a = MatchupAnalysis(confidence="suppress")
    b = MatchupAnalysis(confidence="suppress")
    a.threat_list.append(ThreatHitter(
        player_id="x", name="x", jersey_number=None, pa=0,
        obp=0.0, slg=0.0, ops=0.0, bb_pct=0.0, k_pct=0.0,
        fps_swing_rate=0.0, chase_rate=0.0, swing_rate_by_count={},
        cue_kind="default", supporting_stats=[],
    ))
    assert b.threat_list == []
    assert isinstance(a.loss_recipe_buckets, LossRecipe)
    assert a.loss_recipe_buckets is not b.loss_recipe_buckets


def test_data_note_carries_subsection() -> None:
    note = DataNote(message="msg", subsection="sb_profile")
    assert note.subsection == "sb_profile"


def test_eligible_pitcher_dataclass_shape() -> None:
    p = EligiblePitcher(
        player_id="p1", name="X", jersey_number="9",
        last_outing_date="2026-04-01", days_rest=3,
        last_outing_pitches=70, workload_7d=70,
    )
    assert p.player_id == "p1"
    assert p.days_rest == 3
