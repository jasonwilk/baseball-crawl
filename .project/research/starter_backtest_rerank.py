"""THROWAWAY re-ranker spike (consultation mode, read-only).

Does the coach's tired-arm "available-but-discounted" penalty, applied ONLY as
a re-rank WITHIN the engine's ranked candidate set (rotation-sequence stays the
primary signal), improve accuracy?

Strength 0 (soft) MUST reproduce the engine's ranking exactly (verified).
Read-only; .project/research/ only.

Run: python3 .project/research/starter_backtest_rerank.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.db import get_pitching_history, build_pitcher_profiles  # noqa: E402
from src.reports.starter_prediction import compute_starter_prediction  # noqa: E402

TEAMS = [
    (147, "2026", "LSB Freshman"), (160, "2026", "LSB Varsity"),
    (185, "2026", "Gretna 216 Reserve"), (126, "2026", "GI Home Federal 18U"),
    (202, "2026", "Griffs 216 Juniors"), (91, "2026", "PrimeTime Reserve"),
    (227, "2024", "Cornhusker JV"), (215, "2026", "Cornhusker LSW 2026"),
    (279, "2026", "Jr Bluejays 15U"), (189, "2026", "Papio Post 32 Reserves"),
    (290, "2026", "Gretna 216 Seniors"), (3, "2026", "Epp Foundation Juniors"),
    (128, "2026", "Lincoln Hotel 18U"), (100, "2026", "Lincoln East Reserve 15U"),
    (336, "2026", "Neb Prospect 15U"), (114, "2026", "Five Star Bath"),
    (186, "2026", "Braxter Construction"),
]
DB = str(ROOT / "data" / "app.db")
LEAGUE = "nsaa_varsity"

# Soft penalty strengths to sweep, plus a hard "demote discounted below available".
STRENGTHS = [0.0, 0.10, 0.25, 0.50]


def ordered_games(history):
    order, seen, starter = [], set(), {}
    for r in history:
        gid = r["game_id"]
        if gid not in seen:
            seen.add(gid)
            order.append((gid, r["game_date"]))
        if r.get("appearance_order") == 1:
            starter[gid] = r["player_id"]
    return order, starter


def rest_state(profile, ref_date):
    """Return (days_rest, last_pitches, preferred_days, discounted_bool).

    Coach preferred-rest model (ON TOP of the legal minimum the engine already
    enforced): <=30 pitches -> 2 days, 31-60 -> 4, 61+ -> 5.
    DISCOUNTED = legal but days_rest < preferred. last-day pitches summed
    (doubleheader), matching the engine's exclusion aggregation.
    """
    apps = profile["appearances"]
    last_date = apps[-1]["game_date"]
    last_day = [a for a in apps if a["game_date"] == last_date]
    pcounts = [a.get("pitches") for a in last_day]
    last_pitches = None if any(p is None for p in pcounts) else sum(pcounts)
    days_rest = (ref_date - date.fromisoformat(last_date)).days
    if last_pitches is None:
        return days_rest, None, None, False  # unknown -> treat as available
    if last_pitches <= 30:
        pref = 2
    elif last_pitches <= 60:
        pref = 4
    else:
        pref = 5
    return days_rest, last_pitches, pref, (days_rest < pref)


def rerank_soft(cands, profiles, ref_date, strength):
    """Subtract `strength` from a DISCOUNTED candidate's likelihood, re-sort.

    Stable: ties (incl. strength=0) preserve the engine's original order, so
    strength=0 reproduces the engine ranking exactly.
    """
    scored = []
    for rank, c in enumerate(cands):
        _, _, _, disc = rest_state(profiles[c["player_id"]], ref_date)
        adj = c["likelihood"] - (strength if disc else 0.0)
        scored.append((adj, rank, c["player_id"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s[2] for s in scored]


def rerank_hard(cands, profiles, ref_date):
    """Demote every DISCOUNTED candidate below every FULLY-AVAILABLE one.

    Engine order preserved within each group.
    """
    avail, discd = [], []
    for c in cands:
        _, _, _, disc = rest_state(profiles[c["player_id"]], ref_date)
        (discd if disc else avail).append(c["player_id"])
    return avail + discd


def run():
    conn = sqlite3.connect(DB)
    variants = [f"soft{s}" for s in STRENGTHS] + ["hard"]
    # aggregate counters per variant
    agg = {v: {"t1": 0, "t2": 0} for v in variants}
    engine = {"t1": 0, "t2": 0}
    N = 0

    # KEY SUBSET: games where engine #1 is a DISCOUNTED (tired) arm
    subset = {"n": 0, "engine_t1": 0}
    sub_variant = {v: {"t1": 0, "wins": 0, "breaks": 0} for v in variants}

    sanity_mismatch = 0

    for team_id, season_id, _label in TEAMS:
        history = get_pitching_history(team_id, season_id, db=conn)
        order, actual_starter = ordered_games(history)
        for i, (gid, gdate) in enumerate(order):
            if i < 4:
                continue
            actual = actual_starter.get(gid)
            if actual is None:
                continue
            asof = [r for r in history if r["game_date"] < gdate]
            if not asof:
                continue
            ref_date = date.fromisoformat(gdate)
            profiles = build_pitcher_profiles(asof)
            pred = compute_starter_prediction(
                profiles, asof, reference_date=ref_date,
                workload=None, league=LEAGUE,
            )
            cands = pred.top_candidates
            if not cands:
                # engine produced no ranked candidates; counts as miss for all
                N += 1
                continue
            N += 1
            eng_order = [c["player_id"] for c in cands]
            engine["t1"] += int(eng_order[0] == actual)
            engine["t2"] += int(actual in eng_order[:2])

            # engine #1 discounted?
            _, _, _, eng1_disc = rest_state(profiles[eng_order[0]], ref_date)
            in_subset = eng1_disc
            if in_subset:
                subset["n"] += 1
                subset["engine_t1"] += int(eng_order[0] == actual)

            for v in variants:
                if v == "hard":
                    ro = rerank_hard(cands, profiles, ref_date)
                else:
                    s = float(v[4:])
                    ro = rerank_soft(cands, profiles, ref_date, s)
                agg[v]["t1"] += int(ro[0] == actual)
                agg[v]["t2"] += int(actual in ro[:2])

                # sanity: soft0 must equal engine order
                if v == "soft0.0" and ro != eng_order:
                    sanity_mismatch += 1

                if in_subset:
                    sub_variant[v]["t1"] += int(ro[0] == actual)
                    moved = ro[0] != eng_order[0]
                    if moved:
                        # tired #1 demoted; did the new #1 fix or break?
                        if eng_order[0] == actual:
                            sub_variant[v]["breaks"] += 1  # engine was right, we broke it
                        elif ro[0] == actual:
                            sub_variant[v]["wins"] += 1     # we fixed a miss

    conn.close()

    def pct(a, b):
        return f"{100*a/b:4.1f}%" if b else "  n/a"

    print(f"\nSANITY: soft0.0 order != engine order on {sanity_mismatch} games "
          f"(must be 0).")
    print(f"\nN scored games = {N}")
    print("\n=== A. AGGREGATE (pooled 357) ===")
    print(f"{'variant':>10} {'top1':>7} {'top2':>7}")
    print(f"{'ENGINE':>10} {pct(engine['t1'],N):>7} {pct(engine['t2'],N):>7}")
    for v in variants:
        print(f"{v:>10} {pct(agg[v]['t1'],N):>7} {pct(agg[v]['t2'],N):>7}")

    print("\n=== B. KEY SUBSET: engine #1 is a DISCOUNTED (tired) arm ===")
    sn = subset["n"]
    print(f"subset size = {sn} of {N} games ({pct(sn,N)}) "
          f"-- bounds max possible aggregate gain")
    print(f"engine top-1 on subset = {pct(subset['engine_t1'],sn)} "
          f"({subset['engine_t1']}/{sn})")
    print(f"{'variant':>10} {'sub_t1':>7} {'wins':>5} {'breaks':>6} {'net':>5}")
    for v in variants:
        sv = sub_variant[v]
        net = sv["wins"] - sv["breaks"]
        print(f"{v:>10} {pct(sv['t1'],sn):>7} {sv['wins']:>5} {sv['breaks']:>6} "
              f"{net:>+5}")


if __name__ == "__main__":
    run()
