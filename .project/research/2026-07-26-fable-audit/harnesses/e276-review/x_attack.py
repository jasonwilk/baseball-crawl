"""E-276 adversarial review — executed checks against CURRENT code.

Read-only w.r.t. the repo: builds throwaway DBs in a temp dir from migrations/.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, "/workspaces/baseball-crawl")

from migrations.apply_migrations import run_migrations
from src.db.reconcile_at_load import (
    AbsenceClass,
    classify_absences,
    crawl_is_authoritative,
)
from src.gamechanger.loaders.scouting_loader import ScoutingLoader

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

SLUG = "team-a-slug"
OPP_UUID = "cccccccc-0000-0000-0000-000000000003"


def fresh_db(tmp: Path, tag: str) -> sqlite3.Connection:
    db_path = tmp / f"{tag}.db"
    run_migrations(db_path=db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def insert_team(db) -> int:
    cur = db.execute(
        "INSERT INTO teams (name, membership_type, gc_uuid, public_id, is_active, season_year)"
        " VALUES ('Team A', 'tracked', 'aaaaaaaa-0000-0000-0000-000000000001', ?, 0, 2026)",
        (SLUG,),
    )
    db.commit()
    return cur.lastrowid


def roster(*pids):
    return [
        {"id": p, "first_name": f"F{p.replace('-', '')}",
         "last_name": f"L{p.replace('-', '')}", "number": str(10 + i)}
        for i, p in enumerate(pids)
    ]


def game_entry(gid, date_iso):
    return {
        "id": gid, "game_status": "completed", "home_away": "home",
        "start_ts": f"{date_iso}T18:00:00Z", "timezone": "America/Chicago",
        "score": {"team": 5, "opponent_team": 3},
        "opponent_team": {"name": "Opp Town"},
    }


def boxscore(batters):
    listed = [
        {"id": p, "first_name": f"F{p.replace('-', '')}",
         "last_name": f"L{p.replace('-', '')}", "number": "9"}
        for p in batters
    ]
    return {
        SLUG: {
            "players": listed,
            "groups": [
                {"category": "lineup",
                 "stats": [{"player_id": p,
                            "stats": {"AB": 3, "R": 1, "H": 2, "RBI": 1, "BB": 0, "SO": 0}}
                           for p in batters],
                 "extra": []},
                {"category": "pitching", "stats": [], "extra": []},
            ],
        },
        OPP_UUID: {"players": [], "groups": []},
    }


def crawl(team_id, roster_payload, games, boxscores):
    return SimpleNamespace(
        team_id=team_id, roster=roster_payload, games=games,
        boxscores=boxscores, schedule_fetch_ok=True,
    )


def batting_rows(db, game_id):
    return sorted(r[0] for r in db.execute(
        "SELECT player_id FROM player_game_batting WHERE game_id = ?", (game_id,)))


def roster_ids(db, team):
    return sorted(r[0] for r in db.execute(
        "SELECT player_id FROM team_rosters WHERE team_id = ? AND season_id = '2026'",
        (team,)))


A = [f"a-{i}" for i in range(1, 10)]   # 9 original batters
B = [f"b-{i}" for i in range(1, 10)]   # 9 brand-new (full churn)
C = [f"c-{i}" for i in range(1, 4)]    # 3 brand-new (partial-looking)
ROSTER = ["p-1", "p-2", "p-3"]


def x1_full_churn_today(tmp):
    """Epic's central defect: 9-vs-9 churn hard-deletes all 9 under TODAY's code."""
    db = fresh_db(tmp, "x1")
    team = insert_team(db)
    g = [game_entry("game-0001", "2026-04-10")]
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g, {"game-0001": boxscore(A)}))
    before = batting_rows(db, "game-0001")
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g, {"game-0001": boxscore(B)}))
    after = batting_rows(db, "game-0001")
    print(f"X1 run1 rows={len(before)}  run2(churn B) rows={len(after)}")
    print(f"X1 originals surviving after churn: {sorted(set(A) & set(after))}")
    assert len(before) == 9
    # Defect expectation: A deleted, only B remains.
    print("X1 VERDICT:", "DEFECT REPRODUCED (A all deleted)" if not set(A) & set(after)
          else "defect NOT reproduced")


def x2_refusal_still_writes(tmp):
    """AC-14 premise check: does a REFUSED run leave the fresh rows written?

    Today: 9 stored A, fresh = 3 brand-new C. Polluted gate: prior=12, comparable=3,
    3 >= 6 is False -> REFUSE. If 'a refusal writes nothing' were true, the table
    would hold 9 rows after run 2. It holds 12.
    """
    db = fresh_db(tmp, "x2")
    team = insert_team(db)
    g = [game_entry("game-0001", "2026-04-10")]
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g, {"game-0001": boxscore(A)}))
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g, {"game-0001": boxscore(C)}))
    after = batting_rows(db, "game-0001")
    print(f"X2 rows after REFUSED churn run: {len(after)} "
          f"(A surviving: {len(set(A) & set(after))}, C added: {len(set(C) & set(after))})")
    print("X2 VERDICT:", "'a refusal writes nothing' is FALSE — fresh rows persist"
          if len(after) == 12 else f"unexpected: {after}")


def x3_corrected_gate_run3(tmp):
    """AC-14 attack: corrected-gate state evolution under IDENTICAL repeated churn.

    run2: snapshot=A(9), fresh=B  -> comparable 0 -> refuse (empty-comparable check)
    run3: snapshot=A∪B(18), fresh=B -> comparable 9 -> 9 >= 0.5*18 -> PERMIT
          classify: A -> REMOVED (player-line has NO cap) -> 9 originals deleted.
    Uses the REAL primitives; only the snapshot population is fed as the
    corrected design specifies (pre-upsert set).
    """
    run2 = crawl_is_authoritative(fetch_ok=True, fresh_count=0, prior_count=9)
    run3 = crawl_is_authoritative(fetch_ok=True, fresh_count=9, prior_count=18)
    print(f"X3 corrected gate run2 (0 of 9): authoritative={run2}")
    print(f"X3 corrected gate run3 (9 of 18): authoritative={run3}")
    cls = classify_absences(set(A) | set(B), set(B), crawl_authoritative=run3)
    removed = sorted(p for p, c in cls.items() if c is AbsenceClass.REMOVED)
    print(f"X3 run3 REMOVED set: {removed}")
    print("X3 VERDICT:", "NO-RATCHET PROPERTY FALSE — corrected gate deletes the 9 "
          "originals on the 3rd identical churn crawl (absent a dedup merge)"
          if removed == sorted(A) and run3 else "property holds")


def x4_roster_ac1_prefix(tmp):
    """Story 03 AC-1 discriminating fixture, executed under TODAY's code.

    3 stored roster rows, fresh roster carries 1, churn-free. Today the floor
    must REFUSE (1 >= 1.5 false) and the WARN must name floor_ratio.
    """
    db = fresh_db(tmp, "x4")
    team = insert_team(db)
    g = [game_entry("game-0001", "2026-04-10")]
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g,
                                       {"game-0001": boxscore(["p-1"])}))
    print(f"X4 roster after run1: {roster_ids(db, team)}")

    records = []
    h = logging.Handler()
    h.emit = lambda r: records.append(r)
    logging.getLogger("src.db.reconcile_at_load").addHandler(h)
    ScoutingLoader(db).load_team(crawl(team, roster("p-1"), g,
                                       {"game-0001": boxscore(["p-1"])}))
    logging.getLogger("src.db.reconcile_at_load").removeHandler(h)
    after = roster_ids(db, team)
    warn = [r.getMessage() for r in records
            if r.levelno == logging.WARNING and "Roster retire REFUSED" in r.getMessage()]
    print(f"X4 roster after run2: {after}")
    print(f"X4 refusal warns: {len(warn)}; floor named: "
          f"{any('floor_ratio' in w for w in warn)}")
    print("X4 VERDICT:", "today refuses via the floor — fixture discriminates"
          if after == sorted(ROSTER) and any("floor_ratio" in w for w in warn)
          else "UNEXPECTED")


def x5_roster_no_boxscore_short_circuit(tmp):
    """Same fixture but run 2 has NO boxscores: _load_team_core early-returns
    BEFORE the roster reconcile — nothing retires under EITHER regime."""
    db = fresh_db(tmp, "x5")
    team = insert_team(db)
    g = [game_entry("game-0001", "2026-04-10")]
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g,
                                       {"game-0001": boxscore(["p-1"])}))
    ScoutingLoader(db).load_team(crawl(team, roster("p-1"), g, {}))
    after = roster_ids(db, team)
    print(f"X5 roster after boxscore-less run2: {after}")
    print("X5 VERDICT:", "roster reconcile UNREACHABLE without boxscores "
          "(early return) — a fixture without a boxscore tests nothing"
          if after == sorted(ROSTER) else "unexpected")


def x6_game_grain_prefix(tmp):
    """Story 02 AC-1 executed today: stale absences refuse alone; adding
    newly-completed games in the same run flips the gate to retire them."""
    db = fresh_db(tmp, "x6")
    team = insert_team(db)
    g125 = [game_entry("game-0001", "2026-04-10"),
            game_entry("game-0002", "2026-04-11"),
            game_entry("game-0005", "2026-04-12")]
    bs = {gid: boxscore([f"q-{gid[-1]}"]) for gid in ("game-0001", "game-0002", "game-0005")}
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g125, bs))
    games0 = sorted(r[0] for r in db.execute("SELECT game_id FROM games"))
    # control: g1,g2 vanish, no new games -> comparable 1 of 3 -> refuse
    g5 = [game_entry("game-0005", "2026-04-12")]
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g5,
                                       {"game-0005": boxscore(["q-5"])}))
    games1 = sorted(r[0] for r in db.execute("SELECT game_id FROM games"))
    # same absences + 2 newly-completed games -> polluted gate permits -> retires
    g534 = [game_entry("game-0005", "2026-04-12"),
            game_entry("game-0003", "2026-04-13"),
            game_entry("game-0004", "2026-04-14")]
    bs2 = {gid: boxscore([f"q-{gid[-1]}"]) for gid in ("game-0005", "game-0003", "game-0004")}
    ScoutingLoader(db).load_team(crawl(team, roster(*ROSTER), g534, bs2))
    games2 = sorted(r[0] for r in db.execute("SELECT game_id FROM games"))
    print(f"X6 after run1: {games0}")
    print(f"X6 after stale-absence-only run (should refuse): {games1}")
    print(f"X6 after absences + 2 newly-completed (should retire g1,g2): {games2}")
    ok = ("game-0001" in games1 and "game-0001" not in games2
          and "game-0002" not in games2)
    print("X6 VERDICT:", "game-grain defect reproduced as the epic states"
          if ok else "UNEXPECTED")


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        x1_full_churn_today(tmp)
        print()
        x2_refusal_still_writes(tmp)
        print()
        x3_corrected_gate_run3(tmp)
        print()
        x4_roster_ac1_prefix(tmp)
        print()
        x5_roster_no_boxscore_short_circuit(tmp)
        print()
        x6_game_grain_prefix(tmp)


if __name__ == "__main__":
    main()
