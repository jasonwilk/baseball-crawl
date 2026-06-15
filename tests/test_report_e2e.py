"""End-to-end report generation against a transport-only mock (E-234-05).

This is the ONLY guard that exercises the real GameChanger payload-parsing path
end to end: it mocks nothing in the pipeline except the HTTP transport. Every
URL the report pipeline touches is served a recorded, fully-anonymized payload
from ``tests/fixtures/e2e/`` (per that dir's ``manifest.json``), and the REAL
``generate_report()`` drives crawl -> load -> query -> render. Existing report
tests stub the crawler/loader and therefore cannot catch GC payload-shape drift;
this one can.

Seams (everything below the HTTP transport is real):
* ``respx`` intercepts httpx at the transport layer -- both the generator's
  ``create_session()`` public-profile fetch AND every ``GameChangerClient``
  call (boxscore / roster / search / plays / spray) flow through it.
* Fake credentials are injected via env so ``GameChangerClient`` constructs;
  ``TokenManager.get_access_token`` is shimmed to a static token so no auth
  refresh network call is made (the manifest has no token endpoint -- auth is
  intentionally out of band). This is an auth shim, NOT a data-path stub.
* The rate-limit ``time.sleep`` is no-op'd to keep the test fast.

Oracle: the asserted stat values are HAND-COMPUTED from the recorded payloads
and committed in ``tests/fixtures/e2e/README.md`` (api-scout). This test does
NOT invent them. If the generator's output diverges from the committed oracle,
that is a real finding to surface -- not something to paper over by editing the
expected value (AC-1).

No real network, no credentials (AC-3). Reads ONLY ``tests/fixtures/e2e/``,
never ``data/raw/`` (AC-1).
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

_E2E_DIR = Path(__file__).resolve().parent / "fixtures" / "e2e"

# Identifiers (mirror tests/fixtures/e2e/README.md + manifest.json).
PUBLIC_ID = "ExampleTm001"
GC_UUID = "00000000-0000-4000-8000-00000000003b"
TEAM_NAME = "Example Team Varsity"


def _load(name: str) -> object:
    return json.loads((_E2E_DIR / name).read_text(encoding="utf-8"))


def _manifest() -> dict:
    return _load("manifest.json")  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def e2e_db(tmp_path):
    """Disk-backed DB with the production schema; returns a fresh-conn factory."""
    db_path = str(tmp_path / "e2e.db")
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
    # Ensure no proxy path is taken (keeps httpx plain so respx can intercept).
    monkeypatch.delenv("PROXY_ENABLED", raising=False)


def _register_routes(router: respx.Router):
    """Register one respx route per manifest entry; return the POST /search route.

    The /search route is matched on method+URL only (NOT on body/query) so it
    always captures the request -- the request *contract* (body + query) is then
    asserted explicitly against the manifest by the test. This is deliberate:
    ``_resolve_gc_uuid`` swallows exceptions (spray is non-fatal), so a
    body/query regression that produced a respx *no-match* would be silently
    absorbed and would NOT fail the test. Capturing-then-asserting bites
    regardless of that swallow.
    """
    search_route = None
    for req in _manifest()["requests"]:
        method = req["method"].upper()
        url = req["url"]
        payload = _load(req["file"])
        resp = httpx.Response(200, json=payload)
        if method == "GET":
            router.get(url).mock(return_value=resp)
        elif method == "POST":
            search_route = router.post(url__startswith=url).mock(return_value=resp)
        else:  # pragma: no cover - manifest only has GET/POST
            raise AssertionError(f"Unexpected method in manifest: {method}")
    assert search_route is not None, "manifest is missing the POST /search contract"
    return search_route


def _search_contract_from_manifest() -> dict:
    """Return the documented POST /search contract (body + query) from manifest."""
    for req in _manifest()["requests"]:
        if req["method"].upper() == "POST" and req["url"].rstrip("/").endswith(
            "/search"
        ):
            return {
                "body": req.get("request_body"),
                "query": dict(
                    pair.split("=", 1)
                    for pair in req.get("query", "").split("&")
                    if pair
                ),
            }
    raise AssertionError("manifest is missing the POST /search entry")


def _row_by_jersey(rows: list[dict], jersey: str) -> dict:
    matches = [r for r in rows if str(r.get("jersey_number")) == jersey]
    assert len(matches) == 1, (
        f"expected exactly one row with jersey #{jersey}, got {len(matches)}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# The E2E test
# ---------------------------------------------------------------------------
def test_generate_report_e2e_matches_committed_oracle(
    e2e_db, fake_credentials, tmp_path
):
    """Drive generate_report() end-to-end via a transport-only mock and assert
    the committed hand-computed oracle (W-L, batting #7, pitching #4, FPS%)."""
    captured: dict = {}

    # Capture the data dict handed to the renderer (the query-layer oracle
    # surface) AND exercise the real template so a render crash is caught too.
    from src.reports.renderer import render_report as _real_render

    def _capturing_render(data):
        captured["data"] = data
        return _real_render(data)

    with respx.mock(assert_all_called=False) as router:
        search_route = _register_routes(router)
        with (
            patch(
                "src.gamechanger.token_manager.TokenManager.get_access_token",
                return_value="fake-token-e2e",
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

            # Capture transport activity BEFORE the respx context exits
            # (router.calls is cleared on exit).
            captured["call_count"] = router.calls.call_count
            captured["hosts"] = {c.request.url.host for c in router.calls}

            # Capture the actual POST /search request to pin its contract.
            captured["search_call_count"] = search_route.call_count
            if search_route.call_count:
                search_req = search_route.calls[0].request
                captured["search_method"] = search_req.method
                captured["search_path"] = search_req.url.path
                captured["search_body"] = json.loads(search_req.content)
                captured["search_query"] = dict(search_req.url.params)

    # ---- Pipeline reached a successful terminal state --------------------
    assert result.success is True, f"generation failed: {result.error_message}"
    assert result.outcome == "ready"  # E-236-05: success return sets outcome
    assert "data" in captured, "render_report was never called -- pipeline aborted"
    data = captured["data"]

    # ---- Oracle: team W-L = 1-1 -----------------------------------------
    record = data["team"]["record"]
    assert record is not None, "no W-L record computed"
    assert (record["wins"], record["losses"]) == (1, 1), (
        f"W-L oracle 1-1, got {record['wins']}-{record['losses']}"
    )

    # ---- Oracle: batting season line, jersey #7 (exact counting stats) ---
    # README: AB4 R2 H2 RBI1 BB2 SO0 2B1 HBP1 SB1 -> AVG .500, OBP .714.
    b7 = _row_by_jersey(data["batting"], "7")
    assert b7["ab"] == 4
    assert b7["h"] == 2
    assert b7["doubles"] == 1
    assert b7["hr"] == 0
    assert b7["rbi"] == 1
    assert b7["bb"] == 2
    assert b7["so"] == 0
    assert b7["hbp"] == 1
    assert b7["sb"] == 1
    # Derived rate stats from the committed counting line.
    avg = b7["h"] / b7["ab"]
    obp = (b7["h"] + b7["bb"] + b7["hbp"]) / (b7["ab"] + b7["bb"] + b7["hbp"])
    assert round(avg, 3) == 0.500
    assert round(obp, 3) == 0.714

    # ---- Oracle: pitching season line, jersey #4 (exact) ----------------
    # README: 18 outs, H8 R6 ER5 BB3 SO7 -> ERA 7.50, WHIP 1.83, K/9 10.50.
    p4 = _row_by_jersey(data["pitching"], "4")
    assert p4["ip_outs"] == 18
    assert p4["h"] == 8
    assert p4["er"] == 5
    assert p4["bb"] == 3
    assert p4["so"] == 7
    # Generator formats: ERA/WHIP to 2dp, K/9 to 1dp ("10.5" == oracle 10.50).
    assert p4["era"] == "7.50"
    assert p4["whip"] == "1.83"
    assert p4["k9"] == "10.5"

    # ---- Oracle: a plays-derived stat (FPS%) ----------------------------
    # Prefer the attribution-independent team-level value (README: 25/52 =
    # 48.1%) as the primary plays-derived assertion (least sensitive to
    # pitcher attribution), then cross-check #4's multi-game season aggregate.
    team_fps = data["team_fps_pct"]
    assert team_fps is not None, "no plays-derived team FPS% surfaced"
    assert round(team_fps, 3) == round(25 / 52, 3), (
        f"team FPS% oracle 48.1% (25/52), got {team_fps:.4f}. If the pipeline "
        "is correct, the committed oracle/attribution method diverged -- "
        "surface this as a finding, do NOT silently retune."
    )
    # #4 season FPS% = 14/30 = 46.7% (exercises multi-game aggregation).
    assert p4.get("fps_pct") is not None, "no FPS% for pitcher #4"
    assert round(p4["fps_pct"], 3) == round(14 / 30, 3), (
        f"pitcher #4 FPS% oracle 46.7% (14/30), got {p4['fps_pct']:.4f}. "
        "Divergence here is a finding (real bug or attribution mismatch)."
    )

    # ---- No real network: every served request hit the api host ----------
    assert captured["call_count"] > 0, "no HTTP calls were intercepted"
    assert captured["hosts"] == {"api.team-manager.gc.com"}, (
        f"unexpected host(s) contacted: {captured['hosts']}"
    )

    # ---- POST /search request-contract guard ----------------------------
    # The gc_uuid-resolution search MUST be exercised, and its request must
    # match the manifest's documented contract EXACTLY (method + path + JSON
    # body + query params). A regression in search_teams_by_name()'s request
    # construction (wrong body, query, or path) fails here -- which is the
    # whole point of a payload-drift guard. ``_resolve_gc_uuid`` swallows
    # search errors, so this explicit capture-and-assert (not respx matching)
    # is what makes the guard bite.
    contract = _search_contract_from_manifest()
    assert captured["search_call_count"] >= 1, (
        "POST /search (gc_uuid resolution) was never exercised -- a path that "
        "skips the search call would silently lose spray data."
    )
    assert captured["search_method"] == "POST"
    assert captured["search_path"] == "/search", (
        f"search path drifted: {captured['search_path']!r} != '/search'"
    )
    assert captured["search_body"] == contract["body"], (
        f"POST /search body drifted from manifest contract: "
        f"{captured['search_body']!r} != {contract['body']!r}"
    )
    # Manifest documents start_at_page=0 & search_source=search; the request
    # must carry exactly those (string-valued query params).
    for key, expected in contract["query"].items():
        assert captured["search_query"].get(key) == expected, (
            f"POST /search query param {key!r} drifted: "
            f"{captured['search_query'].get(key)!r} != {expected!r}"
        )

    # ---- Load-layer cross-check (independent of the captured render data) -
    # Confirms the real loader persisted season aggregates AND that the
    # (trimmed) spray fixtures are still valid enough to load >=1 row without
    # crashing the non-fatal spray stage. Spray values are NOT oracle-guarded.
    conn = e2e_db()
    try:
        p4_outs = conn.execute(
            "SELECT psp.ip_outs FROM player_season_pitching psp "
            "JOIN team_rosters tr ON tr.player_id = psp.player_id "
            "AND tr.team_id = psp.team_id AND tr.season_id = psp.season_id "
            "WHERE tr.jersey_number = '4'"
        ).fetchone()
        spray_rows = conn.execute("SELECT COUNT(*) FROM spray_charts").fetchone()[0]
    finally:
        conn.close()
    assert p4_outs is not None and p4_outs[0] == 18, (
        "loader did not persist pitcher #4's season ip_outs=18"
    )
    assert spray_rows > 0, (
        "trimmed spray fixtures should still load >=1 spray row (valid/no-crash)"
    )
