"""Game-grain reachability probes."""
from __future__ import annotations

import logging
import harness
from src.db.reconcile_at_load import (
    retire_absent_games, MAX_GAME_RETIREMENTS, FLOOR_RATIO,
)

logging.disable(logging.CRITICAL)  # keep output clean; we assert on results


def build(n_games=10, absent=0, protected_absent=0, protect_via="perspectives"):
    """n_games prior-loaded for team 1. `absent` genuinely-removed eligible games,
    `protected_absent` absent games that carry a foreign footprint."""
    conn = harness.fresh_db()
    harness.seed_base(conn)
    ids = [f"g{i:02d}" for i in range(n_games)]
    for gid in ids:
        harness.add_game(conn, gid, perspectives=(1,))
    absent_ids = ids[:absent]
    prot_ids = ids[absent:absent + protected_absent]
    for gid in prot_ids:
        if protect_via == "perspectives":
            conn.execute(
                "INSERT INTO game_perspectives (game_id, perspective_team_id) VALUES (?,2)",
                (gid,),
            )
        else:  # child rows only, junction stripped
            harness.add_batting(conn, gid, f"p-{gid}", team_id=2, perspective_team_id=2)
    fresh = set(ids) - set(absent_ids) - set(prot_ids)
    return conn, ids, fresh, absent_ids, prot_ids


def run(**kw):
    conn, ids, fresh, absent_ids, prot_ids = build(**kw)
    res = retire_absent_games(
        conn, team_id=1, season_id="2026", fresh_game_ids=fresh,
        fetch_ok=True, not_final_game_ids=set(), boxscores_complete=True,
    )
    return conn, res, absent_ids, prot_ids


print("=== MAX_GAME_RETIREMENTS cap boundary (10 prior, all eligible) ===")
for a in (0, 1, 2, 3, 4):
    conn, res, ab, pr = run(n_games=10, absent=a)
    print(f"  eligible_absent={a}: retired={len(res.retired_game_ids)} "
          f"refused={len(res.refusals)}")
    if res.refusals:
        print("    reason:", next(iter(res.refusals.values()))[:110])

print()
print("=== exempt (protected) games do NOT count toward the cap ===")
for pv in ("perspectives", "children"):
    for a, p in ((1, 5), (2, 5), (3, 0), (3, 5)):
        conn, res, ab, pr = run(n_games=12, absent=a, protected_absent=p, protect_via=pv)
        print(f"  via={pv:12s} eligible={a} protected={p}: "
              f"retired={len(res.retired_game_ids)} refused={len(res.refusals)}")

print()
print("=== FLOOR_RATIO gate: > half of prior absent ===")
conn, res, ab, pr = run(n_games=10, absent=6)
print(f"  6 of 10 absent: retired={len(res.retired_game_ids)} refused={len(res.refusals)}")
print("  reason:", next(iter(res.refusals.values()))[:160])

print()
print("=== fetch_ok=False ===")
conn, ids, fresh, ab, pr = build(n_games=10, absent=1)
res = retire_absent_games(conn, team_id=1, season_id="2026", fresh_game_ids=fresh,
                          fetch_ok=False, not_final_game_ids=set(), boxscores_complete=True)
print(f"  retired={len(res.retired_game_ids)} refused={len(res.refusals)}")
print("  reason:", next(iter(res.refusals.values()))[:160])

print()
print("=== boxscores_complete=False ===")
conn, ids, fresh, ab, pr = build(n_games=10, absent=1)
res = retire_absent_games(conn, team_id=1, season_id="2026", fresh_game_ids=fresh,
                          fetch_ok=True, not_final_game_ids=set(), boxscores_complete=False)
print(f"  retired={len(res.retired_game_ids)} refused={len(res.refusals)}")
print("  reason:", next(iter(res.refusals.values()))[:200])

print()
print("=== empty fresh payload (total fetch collapse, fetch_ok=True) ===")
conn, ids, fresh, ab, pr = build(n_games=10, absent=0)
res = retire_absent_games(conn, team_id=1, season_id="2026", fresh_game_ids=set(),
                          fetch_ok=True, not_final_game_ids=set(), boxscores_complete=True)
print(f"  retired={len(res.retired_game_ids)} refused={len(res.refusals)}")

print()
print("=== not-final present game ===")
conn, ids, fresh, ab, pr = build(n_games=10, absent=0)
res = retire_absent_games(conn, team_id=1, season_id="2026", fresh_game_ids=set(ids),
                          fetch_ok=True, not_final_game_ids={"g03"}, boxscores_complete=True)
print(f"  retired={len(res.retired_game_ids)} refused={list(res.refusals)}")
