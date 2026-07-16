"""Golden stat-table regression guard for the report query surface (E-234-01).

This is the primary "did we regress the numbers" guard for the reports flow,
the protected core that Epics B-E all refactor code beneath. It seeds a fixture
DB from ``tests/fixtures/seed.sql`` (read-only -- never mutated here), runs the
full report *data-layer* query surface, and deep-equals the result against the
committed golden ``tests/fixtures/golden/report_stats.json``. Any future change
that alters a report stat value, a computed formula (ERA / WHIP / K-9 / OBP
proxy), or a derived workload/profile value fails this test.

Scope and honest limitations
----------------------------
* **Data-layer only.** The golden guards the OUTPUT of the ``_query_*`` family
  in :mod:`src.reports.generator` plus the pitching families in
  :mod:`src.api.db` (``get_pitching_workload``, ``get_pitching_history``,
  ``build_pitcher_profiles``). It does NOT guard ``renderer.py`` /
  ``scouting_report.html`` -- HTML rendering is covered by
  ``test_report_renderer.py`` / ``test_report_rendering.py`` and story 05's
  end-to-end. Do not over-trust this golden as a full reports guard.
* **Spray / plays are shape-only.** ``seed.sql`` has no ``spray_charts`` /
  ``plays`` / ``play_events`` rows, so ``_query_spray_charts`` and the
  plays-stats queries return EMPTY here. They get a shape / no-crash guard,
  NOT value-regression coverage. Story 05's e2e is the value guard for those
  surfaces (see :func:`test_spray_and_plays_surfaces_are_empty_shape_only`).
* **Determinism.** ``get_pitching_workload`` is passed a FIXED
  ``reference_date`` anchored to the fixture's last game date
  (:data:`WORKLOAD_REFERENCE_DATE`). With the default ``None`` it would use
  *today*, making ``last_outing_days_ago`` / ``pitches_7d`` / ``span_days_7d``
  drift daily and the committed golden rot overnight.

The test NEVER writes the golden (AC-3). Regeneration is the explicit, separate
``scripts/regen_report_golden.py`` path, so a regenerated golden always surfaces
in ``git diff`` and is gated by code review.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.api.db import (
    build_pitcher_profiles,
    get_pitching_history,
    get_pitching_workload,
)
from src.reports import generator as gen
from tests.conftest import load_real_schema

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_SEED_PATH = _FIXTURES_DIR / "seed.sql"
GOLDEN_PATH = _FIXTURES_DIR / "golden" / "report_stats.json"

# The fixture's TEAM_VARSITY plays its primary season here.
TEAM_GC_UUID = "TEAM_VARSITY"
PRIMARY_SEASON_ID = "2026"
# Anchored to the fixture's last game (GAME_007, 2026-04-21) so workload-derived
# integer stats are deterministic. NEVER use the default today (TN-1).
WORKLOAD_REFERENCE_DATE = "2026-04-21"

# Keys stripped before comparison (AC-2 exclusions + AC-4 provenance). Applied
# recursively so the guard stays robust if the surface later grows any of these
# nondeterministic / narrative fields.
_NORMALIZE_DROP_KEYS = frozenset(
    {
        "_meta",  # AC-4 provenance block (observable hand-review record)
        "slug",
        "generated_at",
        "expires_at",
        "created_at",
        "created_at_ms",
        "last_synced",
        "narrative",
        "llm_analysis",
        "enriched_prediction",
        # E-264-01: raw per-team-season ERA basis carried on every pitcher row
        # by get_season_pitching. Provenance for E-264-03's "(assumed)" display
        # decision; not yet rendered, so it stays out of the golden surface
        # comparison (dropping it keeps this story report-invisible per its spec).
        "innings_per_game",
    }
)


# ---------------------------------------------------------------------------
# Collector + normalizer (single source of truth -- imported by the regen script)
# ---------------------------------------------------------------------------
def seed_connection() -> sqlite3.Connection:
    """Return an in-memory connection with the real schema + seed.sql applied.

    ``seed.sql`` is loaded read-only; this never writes back to the fixture.
    """
    conn = sqlite3.connect(":memory:")
    load_real_schema(conn)
    conn.executescript(_SEED_PATH.read_text(encoding="utf-8"))
    conn.row_factory = sqlite3.Row
    return conn


def resolve_team_id(conn: sqlite3.Connection, gc_uuid: str) -> int:
    """Resolve a seed team's INTEGER PK from its symbolic ``gc_uuid``."""
    row = conn.execute(
        "SELECT id FROM teams WHERE gc_uuid = ?", (gc_uuid,)
    ).fetchone()
    if row is None:
        raise AssertionError(f"Seed fixture has no team with gc_uuid={gc_uuid!r}")
    return row[0]


def collect_report_stats(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    reference_date: str,
) -> dict:
    """Run the full report data-layer query surface and assemble one dict.

    Covers every ``_query_*`` in :mod:`src.reports.generator` plus the
    :mod:`src.api.db` pitching families the report consumes. Spray / plays
    queries return empty for this fixture (shape / no-crash only).
    """
    runs_scored_avg, runs_allowed_avg = gen._query_runs_avg(
        conn, team_id, season_id
    )
    freshness_date, game_count = gen._query_freshness(conn, team_id, season_id)
    history = get_pitching_history(team_id, season_id, db=conn)

    return {
        "team_info": gen._query_team_info(conn, team_id),
        "record": gen._query_record(conn, team_id, season_id),
        "batting": gen._query_batting(conn, team_id, season_id),
        "pitching": gen._query_pitching(conn, team_id, season_id),
        "recent_games": gen._query_recent_games(conn, team_id, season_id),
        "runs_avg": {
            "scored": runs_scored_avg,
            "allowed": runs_allowed_avg,
        },
        "freshness": {"date": freshness_date, "count": game_count},
        "roster": gen._query_roster(conn, team_id, season_id),
        # Shape/no-crash only -- seed has no spray_charts rows.
        "spray_charts": gen._query_spray_charts(conn, team_id, season_id),
        # Shape/no-crash only -- seed has no plays rows. game_ids=None exercises
        # the season-scoped SQL path (vs. the empty-list early return).
        "plays_pitching": gen._query_plays_pitching_stats(
            conn, team_id, season_id, game_ids=None
        ),
        "plays_batting": gen._query_plays_batting_stats(
            conn, team_id, season_id, game_ids=None
        ),
        "plays_team": gen._query_plays_team_stats(
            conn, team_id, season_id, game_ids=None
        ),
        "pitching_workload": get_pitching_workload(
            team_id, season_id, reference_date, db=conn
        ),
        "pitching_history": history,
        "pitcher_profiles": build_pitcher_profiles(history),
    }


def canonicalize(obj):
    """Round-trip through JSON so tuples become lists and types match the file.

    The collected dict may contain tuples (e.g. ``_query_runs_avg``) while the
    committed golden is loaded from JSON (lists). Canonicalizing both sides
    makes the deep-equality compare type-stable.
    """
    return json.loads(json.dumps(obj, sort_keys=True))


def normalize(obj):
    """Recursively drop excluded keys (timestamps / slug / provenance / LLM)."""
    if isinstance(obj, dict):
        return {
            k: normalize(v)
            for k, v in obj.items()
            if k not in _NORMALIZE_DROP_KEYS
        }
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return obj


def build_golden_payload(
    conn: sqlite3.Connection,
    team_id: int,
    season_id: str,
    reference_date: str,
    *,
    meta: dict,
) -> dict:
    """Assemble the committed golden payload: ``_meta`` + canonical stats.

    Used by :mod:`scripts.regen_report_golden`. The test imports the same
    collector / normalizer so there is one source of truth for the surface.
    """
    stats = canonicalize(
        collect_report_stats(conn, team_id, season_id, reference_date)
    )
    return {"_meta": meta, **stats}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.fixture()
def seeded_conn():
    conn = seed_connection()
    try:
        yield conn
    finally:
        conn.close()


def test_report_golden_matches_committed(seeded_conn):
    """The live query surface deep-equals the committed golden (AC-1, AC-2, AC-4)."""
    team_id = resolve_team_id(seeded_conn, TEAM_GC_UUID)
    collected = collect_report_stats(
        seeded_conn, team_id, PRIMARY_SEASON_ID, WORKLOAD_REFERENCE_DATE
    )

    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    assert normalize(canonicalize(collected)) == normalize(expected), (
        "Report stat surface diverged from the committed golden. If this change "
        "is intentional, regenerate with `python scripts/regen_report_golden.py` "
        "and hand-review the diff against seed.sql header math."
    )


def test_golden_carries_provenance_meta():
    """The committed golden records an observable hand-review (AC-4)."""
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    meta = expected.get("_meta")
    assert isinstance(meta, dict), "golden must carry a top-level _meta block"
    for field in ("reviewed_by", "reviewed_date", "basis"):
        assert meta.get(field), f"_meta.{field} must be populated"


def test_spray_and_plays_surfaces_are_empty_shape_only(seeded_conn):
    """Spray / plays surfaces are shape/no-crash only -- seed has no such rows (AC-6).

    These queries must run without crashing and return empty, but their values
    are NOT regression-guarded here; story 05's e2e is their value guard.
    """
    team_id = resolve_team_id(seeded_conn, TEAM_GC_UUID)

    assert gen._query_spray_charts(seeded_conn, team_id, PRIMARY_SEASON_ID) == {}
    assert (
        gen._query_plays_pitching_stats(
            seeded_conn, team_id, PRIMARY_SEASON_ID, game_ids=None
        )
        == {}
    )
    assert (
        gen._query_plays_batting_stats(
            seeded_conn, team_id, PRIMARY_SEASON_ID, game_ids=None
        )
        == {}
    )
    plays_team = gen._query_plays_team_stats(
        seeded_conn, team_id, PRIMARY_SEASON_ID, game_ids=None
    )
    assert plays_team["has_plays_data"] is False
    assert plays_team["plays_game_count"] == 0


def test_workload_reference_date_is_deterministic(seeded_conn):
    """A fixed reference_date keeps workload integer stats stable (TN-1 determinism).

    Guards against a future refactor that drops the fixed anchor and lets the
    default (today) drive the golden, which would rot daily.
    """
    team_id = resolve_team_id(seeded_conn, TEAM_GC_UUID)
    workload = get_pitching_workload(
        team_id, PRIMARY_SEASON_ID, WORKLOAD_REFERENCE_DATE, db=seeded_conn
    )
    # GAME_007 (2026-04-21) is the anchor: the ace pitched that day.
    ace = workload["PLAYER_VARSITY_01"]
    assert ace["last_outing_date"] == "2026-04-21"
    assert ace["last_outing_days_ago"] == 0
