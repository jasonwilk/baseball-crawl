"""Degraded-opponent acceptance & negative-path E2E (E-236-08, the epic's
unifying-invariant acceptance test).

Drives the REAL ``generate_report()`` end-to-end against a transport-only respx
mock (the E-234 harness pattern), using a sibling fixture set
``tests/fixtures/e2e_degraded/`` — the golden oracle in ``tests/fixtures/e2e/``
is NOT touched (AC-1). The scenario is a deliberately-DEGRADED but still-
RENDERABLE opponent: a MIX of M=3 completed games where one is fully charted
(→ N>0, so a full report with a footer trust-block renders) and two are sub-case
A scored-but-empty (→ 0 < N < M); ALL plays-fetches fail (HTTP 500); ALL spray
returns a null chart.

The single test asserts BOTH integrity surfaces in ONE place so they cannot
drift (TN-9):
1. the ``report_generation_runs`` row carries honest per-stage statuses + counts;
2. the rendered coach footer shows honest coverage severity + the K==0 / spray-
   unavailable branches, and does NOT false-alarm the degraded-confidence line on
   the clean, anchored identity;
3. (negative path) the charted game's present stats still render correctly.

The assertions are written to FAIL loudly if any surface lies: a per-stage status
regression, a false spray/plays partial, a coach degraded-line false-fire, or a
K!=0 leak all break a specific assert.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from tests.conftest import load_real_schema

_DEGRADED_DIR = Path(__file__).resolve().parent / "fixtures" / "e2e_degraded"

# Identifiers (mirror the degraded manifest.json).
PUBLIC_ID = "ExampleTm001"
GC_UUID = "00000000-0000-4000-8000-00000000003b"
BASE = "https://api.team-manager.gc.com"

# Completed game ids: game 1 charted (-> N), games 2 & 3 scored-but-empty.
CHARTED_GAME = "00000000-0000-4000-8000-000000000002"
EMPTY_GAMES = (
    "00000000-0000-4000-8000-000000000004",
    "00000000-0000-4000-8000-000000000006",
)
M_GAMES = 3  # total completed games on the schedule


def _load(name: str) -> object:
    return json.loads((_DEGRADED_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_report_e2e.py)
# ---------------------------------------------------------------------------
@pytest.fixture()
def e2e_db(tmp_path):
    """Disk-backed DB with the production schema; returns a fresh-conn factory."""
    db_path = str(tmp_path / "e2e_degraded.db")
    conn = sqlite3.connect(db_path)
    load_real_schema(conn)
    conn.commit()
    conn.close()

    def _fresh_conn():
        c = sqlite3.connect(db_path)
        c.execute("PRAGMA foreign_keys=ON;")
        return c

    return _fresh_conn


@pytest.fixture()
def fake_credentials(monkeypatch):
    """Inject fake web credentials so GameChangerClient constructs (no .env)."""
    monkeypatch.setenv("GAMECHANGER_BASE_URL", "https://api.team-manager.gc.com")
    monkeypatch.setenv("GAMECHANGER_REFRESH_TOKEN_WEB", "fake-refresh")
    monkeypatch.setenv("GAMECHANGER_CLIENT_ID_WEB", "fake-client-id")
    monkeypatch.setenv("GAMECHANGER_CLIENT_KEY_WEB", "fake-client-key")
    monkeypatch.setenv("GAMECHANGER_DEVICE_ID_WEB", "fake-device-id")
    monkeypatch.delenv("PROXY_ENABLED", raising=False)


def _register_degraded_routes(router: respx.Router) -> None:
    """Register one respx route per pipeline call for the DEGRADED scenario.

    Boxscores are served exact-URL (charted for game 1, the shared sub-case A
    empty payload for games 2 & 3). Plays are 500 for ALL games (regex, no
    fixture) and spray is a null-chart 200 for ALL games (regex) -- those two
    are the degradations and are intentionally not recorded successes.
    """
    router.get(f"{BASE}/public/teams/{PUBLIC_ID}").mock(
        return_value=httpx.Response(200, json=_load("public_team_profile.json"))
    )
    router.get(f"{BASE}/public/teams/{PUBLIC_ID}/games").mock(
        return_value=httpx.Response(200, json=_load("public_team_games.json"))
    )
    router.get(f"{BASE}/teams/public/{PUBLIC_ID}/players").mock(
        return_value=httpx.Response(200, json=_load("roster_players.json"))
    )
    router.post(url__startswith=f"{BASE}/search").mock(
        return_value=httpx.Response(200, json=_load("search_response.json"))
    )

    # Boxscores: charted game 1 -> full data (N); empty games 2 & 3 -> sub-case A.
    charted = _load("boxscore_charted.json")
    empty = _load("boxscore_empty.json")
    router.get(
        f"{BASE}/game-stream-processing/{CHARTED_GAME}/boxscore"
    ).mock(return_value=httpx.Response(200, json=charted))
    for gid in EMPTY_GAMES:
        router.get(
            f"{BASE}/game-stream-processing/{gid}/boxscore"
        ).mock(return_value=httpx.Response(200, json=empty))

    # DEGRADATION 1: ALL plays -> HTTP 500 (the authed client retries 5xx then
    # raises; the plays stage swallows it into a fetch-failure -> plays_status
    # "failed", K==0). Regex matches every /plays path.
    router.get(url__regex=r".*/game-stream-processing/[^/]+/plays$").mock(
        return_value=httpx.Response(500, json={"error": "degraded-plays"})
    )

    # DEGRADATION 2: ALL spray -> null chart (a fetch SUCCESS, not an error ->
    # spray_status "completed", spray_games_with_data 0). Regex matches every
    # /player-stats path.
    null_spray = _load("spray_null.json")
    router.get(url__regex=r".*/schedule/events/[^/]+/player-stats$").mock(
        return_value=httpx.Response(200, json=null_spray)
    )


def _row_by_jersey(rows: list[dict], jersey: str) -> dict:
    matches = [r for r in rows if str(r.get("jersey_number")) == jersey]
    assert len(matches) == 1, (
        f"expected exactly one row with jersey #{jersey}, got {len(matches)}"
    )
    return matches[0]


def _read_run_record(conn_factory, slug: str) -> dict:
    conn = conn_factory()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT rgr.* FROM report_generation_runs rgr "
            "JOIN reports r ON r.id = rgr.report_id WHERE r.slug = ?",
            (slug,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "no report_generation_runs row was written"
    return dict(row)


# ---------------------------------------------------------------------------
# The degraded-opponent acceptance test
# ---------------------------------------------------------------------------
def test_degraded_opponent_both_surfaces_tell_the_truth(
    e2e_db, fake_credentials, tmp_path
):
    """Run generate_report() against the degraded opponent and assert BOTH the
    operator run record AND the coach footer are honest -- with no false alarm on
    the clean parts (AC-3/4/5/6)."""
    captured: dict = {}
    from src.reports.renderer import render_report as _real_render

    def _capturing_render(data):
        captured["data"] = data
        html = _real_render(data)
        captured["html"] = html
        return html

    with respx.mock(assert_all_called=False) as router:
        _register_degraded_routes(router)
        with (
            patch(
                "src.gamechanger.token_manager.TokenManager.get_access_token",
                return_value="fake-token-degraded",
            ),
            patch("src.http.session.time.sleep", return_value=None),
            patch("src.reports.generator.get_connection", side_effect=e2e_db),
            patch("src.api.db.get_connection", side_effect=e2e_db),
            patch("src.reports.generator.render_report", side_effect=_capturing_render),
            patch("src.reports.generator._REPO_ROOT", tmp_path),
            patch("src.reports.generator._REPORTS_DIR", tmp_path / "data" / "reports"),
        ):
            from src.reports.generator import generate_report

            result = generate_report(PUBLIC_ID)

    # ---- The pipeline reached a successful terminal state (N>0 -> a real
    #      report rendered, NOT the no_games page) ------------------------
    assert result.success is True, f"generation failed: {result.error_message}"
    assert result.outcome == "ready"
    assert "data" in captured, "render_report was never called -- pipeline aborted"
    assert "html" in captured, "no rendered HTML captured"
    data = captured["data"]
    html = captured["html"]

    # ======================================================================
    # SURFACE 1 -- the operator run record (report_generation_runs) is honest
    # ======================================================================
    run = _read_run_record(e2e_db, result.slug)

    # Per-stage statuses: crawl/load completed (all boxscores valid, sub-case A
    # empty loads errors=0), plays FAILED (all 500), spray COMPLETED (null != error).
    assert run["crawl_status"] == "completed", run["crawl_status"]
    assert run["load_status"] == "completed", run["load_status"]
    assert run["plays_status"] == "failed", (
        f"plays all-500 must be 'failed', got {run['plays_status']!r}"
    )
    assert run["spray_status"] == "completed", (
        "null spray chart is NOT an error -- spray_status must stay 'completed', "
        f"got {run['spray_status']!r} (false-alarm regression)"
    )

    # Counts: M>0, 0 < N < M, K==0, spray_games_with_data==0, and the new count
    # columns reflect the degradation honestly.
    m, n, k = run["completed_games"], run["completed_games_with_data"], run["plays_games_covered"]
    assert m == M_GAMES, f"M (completed_games) expected {M_GAMES}, got {m}"
    assert 0 < n < m, f"expected 0 < N < M, got N={n} M={m}"
    assert k == 0, f"K (plays_games_covered) must be 0 (all plays failed), got {k}"
    assert run["spray_games_with_data"] == 0, run["spray_games_with_data"]
    assert run["boxscores_fetched"] == M_GAMES, run["boxscores_fetched"]
    assert run["load_errors"] == 0, (
        f"sub-case A empty loads contribute 0 errors, got {run['load_errors']}"
    )
    assert run["plays_errors"] and run["plays_errors"] > 0, (
        "all-failed plays must record a non-zero plays_errors tally, got "
        f"{run['plays_errors']!r}"
    )

    # overall completed, and the DERIVED operator-degraded flag is TRUE (computed
    # the same way the admin route does: completed overall + a stage partial/failed).
    assert run["overall_status"] == "completed", run["overall_status"]
    operator_degraded = run["overall_status"] == "completed" and any(
        run[col] in ("partial", "failed")
        for col in (
            "crawl_status", "load_status", "gc_uuid_status", "spray_status",
            "plays_status", "reconciliation_status", "enrichment_status",
        )
    )
    assert operator_degraded is True, (
        "derived operator-degraded must be TRUE (overall completed + plays failed)"
    )

    # ======================================================================
    # SURFACE 2 -- the coach footer (rendered HTML) is honest, no false alarm
    # ======================================================================
    # Coverage severity reflects N-of-M. N=1, M=3 -> 33% -> 'loud' band.
    assert "trust-loud" in html, "coverage severity should be 'loud' at N/M=1/3"
    assert f"{n} of {m} games" in html, (
        f"footer must show honest N-of-M coverage ('{n} of {m} games')"
    )
    # K==0 -> the existing E-235 'No pitch-detail data' branch (regression guard).
    assert "No pitch-detail data" in html, (
        "K==0 must render 'No pitch-detail data' (renderer.py + template branch)"
    )
    # Spray unavailable (no spray rows loaded from null charts).
    assert "spray unavailable" in html, "footer must mark spray unavailable"
    # NO false alarm: the coach degraded-confidence line must NOT fire on the
    # clean, anchored identity (identity_match_method is NOT 'name_only').
    assert data.get("degraded_confidence") is False, (
        "degraded_confidence must be False on a clean anchored identity "
        "(season_fallback was dropped in E-236-06; only name-only degrades)"
    )
    # Target the RENDERED degraded div (and the line text), NOT the bare
    # 'trust-degraded' CSS rule that is always present in the <style> block.
    assert '<div class="trust-degraded">' not in html, (
        "the coach degraded-confidence line must NOT false-fire on clean identity"
    )
    assert "Data accuracy may be limited" not in html, (
        "the degraded-confidence copy must NOT appear on a clean anchored identity"
    )

    # ======================================================================
    # NEGATIVE PATH (AC-5) -- the charted game's present stats render correctly;
    # the degradation does NOT corrupt the data that IS present.
    # ======================================================================
    # Charted game 1 only -> single-game season aggregates.
    # Pitcher #4 (workhorse, G1): IP 4.667 = 14 outs, H2 R1 ER0 BB1 SO7.
    p4 = _row_by_jersey(data["pitching"], "4")
    assert p4["ip_outs"] == 14, f"charted pitcher #4 ip_outs expected 14, got {p4['ip_outs']}"
    assert p4["h"] == 2 and p4["er"] == 0 and p4["bb"] == 1 and p4["so"] == 7
    # Batter #7 (G1): AB2 H1 BB2 2B1.
    b7 = _row_by_jersey(data["batting"], "7")
    assert b7["ab"] == 2 and b7["h"] == 1 and b7["bb"] == 2
    assert b7["doubles"] == 1
