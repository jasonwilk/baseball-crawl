"""Player-line grain: health-gate population under the real (post-upsert) ordering."""
from __future__ import annotations

import logging
import harness
from src.db.reconcile_at_load import (
    retire_absent_player_lines, PlayerLineBlock,
)

logging.disable(logging.CRITICAL)


def scenario(old_ids, fresh_ids, populated=True, upsert_fresh=True,
             team_id=2, persp=1):
    """old_ids = lines already in the DB before this run.
    fresh_ids = player ids in the fresh payload block.
    upsert_fresh=True reproduces the REAL ordering (_load_team_stats writes the
    fresh rows before the reconcile reads 'prior'); False is the ordering the
    docstring's health-gate argument assumes."""
    conn = harness.fresh_db()
    harness.seed_base(conn)
    harness.add_game(conn, "gA", perspectives=(persp,))
    for pid in old_ids:
        harness.add_batting(conn, "gA", pid, team_id=team_id, perspective_team_id=persp)
    if upsert_fresh:
        for pid in fresh_ids:
            if pid not in old_ids:
                harness.add_batting(conn, "gA", pid, team_id=team_id,
                                    perspective_team_id=persp)
    block = PlayerLineBlock(
        team_id=team_id,
        batting_player_ids=frozenset(fresh_ids),
        pitching_player_ids=frozenset(),
        populated=populated,
    )
    res = retire_absent_player_lines(
        conn, game_id="gA", perspective_team_id=persp, blocks=[block]
    )
    surviving = {r[0] for r in conn.execute(
        "SELECT player_id FROM player_game_batting WHERE game_id='gA'")}
    return res, surviving


print("=== TOTAL player_id churn: 9 old lines, 9 BRAND-NEW ids in the payload ===")
old = [f"old{i}" for i in range(9)]
new = [f"new{i}" for i in range(9)]

res, surv = scenario(old, new, upsert_fresh=True)
print("  REAL ordering  (reconcile reads prior AFTER the fresh upsert):")
print(f"    retired={sorted(sum(res.retired.values(), []))}")
print(f"    refusals={list(res.refusals.values())}")
print(f"    old lines surviving = {len(surv & set(old))} of 9")

res, surv = scenario(old, new, upsert_fresh=False)
print("  ordering the docstring's gate argument assumes (prior read BEFORE upsert):")
print(f"    retired={sorted(sum(res.retired.values(), []))}")
print(f"    refused={bool(res.refusals)} -> {list(res.refusals.values())[:1]}")
print(f"    old lines surviving = {len(surv & set(old))} of 9")

print()
print("=== boundary sweep, REAL ordering: a = stale, f = fresh block size ===")
print("  (b = 0 matching, so the docstring's intended gate 'b >= a' would refuse ALL)")
for a in (2, 4, 6, 9):
    for f in (a - 1, a, a + 1):
        if f < 1:
            continue
        old_ = [f"old{i}" for i in range(a)]
        new_ = [f"new{i}" for i in range(f)]
        res, surv = scenario(old_, new_, upsert_fresh=True)
        n_ret = len(sum(res.retired.values(), []))
        print(f"    stale={a} fresh={f}: retired={n_ret} refused={bool(res.refusals)}")

print()
print("=== modal scored-but-empty block (stats: []) -> populated=False ===")
res, surv = scenario(old, [], populated=False, upsert_fresh=True)
print(f"    retired={sum(res.retired.values(), [])} refusals={len(res.refusals)}")
print(f"    reason: {list(res.refusals.values())[0][:120] if res.refusals else None}")
print(f"    old lines surviving = {len(surv & set(old))} of 9")

print()
print("=== half-populated payload: own block populated, opponent block empty ===")
conn = harness.fresh_db()
harness.seed_base(conn)
harness.add_game(conn, "gA", perspectives=(1,))
for pid in ["o1", "o2", "o3", "o4", "o5"]:          # own block, fresh
    harness.add_batting(conn, "gA", pid, team_id=1, perspective_team_id=1)
for pid in ["x1", "x2", "x3"]:                       # opponent block, STALE
    harness.add_batting(conn, "gA", pid, team_id=2, perspective_team_id=1)
blocks = [
    PlayerLineBlock(team_id=1, batting_player_ids=frozenset({"o1","o2","o3","o4","o5"}),
                    pitching_player_ids=frozenset(), populated=True),
    PlayerLineBlock(team_id=2, batting_player_ids=frozenset(),
                    pitching_player_ids=frozenset(), populated=False),
]
res = retire_absent_player_lines(conn, game_id="gA", perspective_team_id=1, blocks=blocks)
surv = {r[0] for r in conn.execute("SELECT player_id FROM player_game_batting")}
print(f"    retired={res.retired} refusals={list(res.refusals)}")
print(f"    stale opponent lines surviving: {sorted(surv & {'x1','x2','x3'})}")

print()
print("=== uncovered team_id residual ===")
conn = harness.fresh_db()
harness.seed_base(conn)
harness.add_game(conn, "gA", perspectives=(1,))
for pid in ["o1", "o2"]:
    harness.add_batting(conn, "gA", pid, team_id=1, perspective_team_id=1)
harness.add_batting(conn, "gA", "z1", team_id=3, perspective_team_id=1)
blocks = [PlayerLineBlock(team_id=1, batting_player_ids=frozenset({"o1","o2"}),
                         pitching_player_ids=frozenset(), populated=True)]
res = retire_absent_player_lines(conn, game_id="gA", perspective_team_id=1, blocks=blocks)
print(f"    uncovered_team_ids={res.uncovered_team_ids} retired={res.retired}")
