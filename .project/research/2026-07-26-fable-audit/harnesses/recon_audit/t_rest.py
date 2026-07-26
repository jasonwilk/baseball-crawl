"""Remaining probes: narrowing-only, exempt-vs-floor deadlock, roster grain."""
from __future__ import annotations

import logging
import harness
from src.db.reconcile_at_load import (
    classify_absences, AbsenceClass, retire_absent_games,
    retire_departed_roster_players, roster_departure_guard,
    MAX_ROSTER_DEPARTURES, MAX_GAME_RETIREMENTS, FLOOR_RATIO,
)

logging.disable(logging.CRITICAL)

print("=== extra_guard is narrowing-only (permissive guard cannot widen) ===")
r = classify_absences(["a", "b"], [], crawl_authoritative=False,
                      extra_guard=lambda _a: True)
print("  authoritative=False + permissive guard ->", set(r.values()))
r = classify_absences(["a", "b"], ["a"], crawl_authoritative=True,
                      extra_guard=lambda _a: False)
print("  authoritative=True  + refusing guard   ->", r)
calls = []
r = classify_absences(["a"], ["a"], crawl_authoritative=True,
                      extra_guard=lambda a: calls.append(a) or True)
print("  no absences -> guard invoked?", bool(calls), "| result", r)

print()
print("=== EXEMPT games are excluded from the CAP but NOT from the FLOOR ===")
print("    (prior grows with permanently-refused twins; comparable does not)")


def floor_probe(n_keep, n_protected_absent):
    conn = harness.fresh_db()
    harness.seed_base(conn)
    keeps = [f"k{i}" for i in range(n_keep)]
    prot = [f"p{i}" for i in range(n_protected_absent)]
    for g in keeps + prot:
        harness.add_game(conn, g, perspectives=(1,))
    for g in prot:  # foreign junction row -> permanently refused, never leaves prior
        conn.execute("INSERT INTO game_perspectives (game_id, perspective_team_id) "
                     "VALUES (?,2)", (g,))
    gone = "gone"
    harness.add_game(conn, gone, perspectives=(1,))
    prior = n_keep + n_protected_absent + 1
    res = retire_absent_games(
        conn, team_id=1, season_id="2026", fresh_game_ids=set(keeps),
        fetch_ok=True, not_final_game_ids=set(), boxscores_complete=True,
    )
    reason = next(iter(res.refusals.values()), "")
    which = ("floor/not-authoritative" if "not authoritative" in reason
             else "cap" if "MAX_GAME_RETIREMENTS" in reason
             else "protection" if "another team" in reason else "-")
    return prior, len(res.retired_game_ids), which


for prot in (0, 2, 4, 6, 8, 10):
    prior, retired, which = floor_probe(10, prot)
    print(f"    10 present + {prot:2d} protected-absent + 1 genuine removal "
          f"(prior={prior:2d}): genuine retired={retired}  refusal_cause={which}")

print()
print("=== ROSTER grain ===")


def roster(prior_ids, fresh_ids, previously=None, exempt=()):
    conn = harness.fresh_db()
    harness.seed_base(conn)
    for pid in prior_ids:
        harness.add_player(conn, pid)
        conn.execute("INSERT INTO team_rosters (team_id, player_id, season_id) "
                     "VALUES (1,?, '2026')", (pid,))
    res = retire_departed_roster_players(
        conn, team_id=1, season_id="2026", fresh_player_ids=fresh_ids,
        previously_rostered_ids=prior_ids if previously is None else previously,
        exempt_player_ids=exempt,
    )
    left = {r[0] for r in conn.execute("SELECT player_id FROM team_rosters")}
    return res, left


roster_ids = [f"r{i}" for i in range(13)]
for n_gone in (0, 1, 2, 3, 5):
    res, left = roster(roster_ids, set(roster_ids[n_gone:]))
    print(f"  {n_gone} departures of 13: retired={len(res.retired_player_ids)} "
          f"refused={res.refused} reason={(res.refusal_reason or '')[:60]}")

res, left = roster(roster_ids, set())
print(f"  EMPTY fresh crawl: retired={len(res.retired_player_ids)} refused={res.refused}")

res, left = roster(roster_ids, set(roster_ids[3:]), previously=[])
print(f"  3 gone but previously_rostered_ids=EMPTY (churn reading): "
      f"retired={len(res.retired_player_ids)} refused={res.refused}"
      f"   <-- cap DISABLED, deletes above MAX_ROSTER_DEPARTURES")

res, left = roster(roster_ids, set(roster_ids[3:]), exempt=roster_ids[:2])
print(f"  3 gone, 2 of them exempt: retired={sorted(res.retired_player_ids)} "
      f"refused={res.refused}")

print()
print("=== roster_departure_guard direct ===")
for n in range(0, 5):
    print(f"  {n} absent -> {roster_departure_guard(frozenset(map(str, range(n))))}")
