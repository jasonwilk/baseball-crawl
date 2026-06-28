"""THROWAWAY backtest spike (consultation mode, read-only).

Faithful as-of replay of the REAL probable-starter engine
(`compute_starter_prediction`) vs naive baselines across 17 loaded opponent
seasons. See the spawn brief. Does NOT modify any src/ code or DB rows.

Run: python3 .project/research/starter_backtest.py
"""
from __future__ import annotations

import datetime
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.db import get_pitching_history, build_pitcher_profiles  # noqa: E402
from src.reports.starter_prediction import (  # noqa: E402
    compute_starter_prediction,
    detect_league_level,
    get_rules_for_league,
    get_nsaa_rules,
    _is_excluded,
)

TEAMS = [
    (147, "2026", "Standing Bear Freshman"),
    (160, "2026", "Standing Bear Varsity"),
    (185, "2026", "Gretna Post 216 Reserve"),
    (126, "2026", "Grand Island Home Federal Bank 18U"),
    (202, "2026", "Griffs Post 216 Juniors"),
    (91, "2026", "PrimeTime Westview Reserve"),
    (227, "2024", "Cornhusker LSW JV 2024"),
    (215, "2026", "Cornhusker LSW 2026"),
    (279, "2026", "Jr Bluejays 15U"),
    (189, "2026", "Gene's Auto Papio Post 32 Reserves"),
    (290, "2026", "Gretna Post 216 Seniors"),
    (3, "2026", "Epp Foundation Repair Juniors"),
    (128, "2026", "Lincoln Hotel Group 18U"),
    (100, "2026", "Lincoln East Reserve 15U"),
    (336, "2026", "Nebraska Prospect 29s 15U"),
    (114, "2026", "Five Star Bath Solutions"),
    (186, "2026", "Braxter Construction"),
]

DB = str(ROOT / "data" / "app.db")
FORCED_LEAGUE = "nsaa_varsity"  # PRIMARY run: level-agnostic, per brief


def ordered_games(history):
    """Distinct (game_id, game_date) in chronological order, plus actual starter."""
    seen = {}
    order = []
    starter = {}
    for r in history:
        gid = r["game_id"]
        if gid not in seen:
            seen[gid] = r["game_date"]
            order.append((gid, r["game_date"]))
        if r.get("appearance_order") == 1:
            starter[gid] = r["player_id"]
    return order, starter


def baseline_b1(asof_history):
    """Most-frequent prior starter; ties -> most recent start date."""
    counts = {}
    last_start = {}
    for r in asof_history:
        if r.get("appearance_order") == 1:
            pid = r["player_id"]
            counts[pid] = counts.get(pid, 0) + 1
            d = r["game_date"]
            if pid not in last_start or d > last_start[pid]:
                last_start[pid] = d
    if not counts:
        return None
    return max(counts, key=lambda p: (counts[p], last_start[p]))


def starters_last_start(profiles):
    """player_id -> last start date string, for pitchers with >=1 start."""
    out = {}
    for pid, p in profiles.items():
        if p["total_starts"] > 0:
            out[pid] = p["starts"][-1]["game_date"]
    return out


def baseline_b2(profiles, ref_date, rules):
    """Most-rested rest-ELIGIBLE starter (longest gap since last START)."""
    ls = starters_last_start(profiles)
    if not ls:
        return None
    eligible = {}
    for pid in ls:
        excl, _ = _is_excluded(profiles[pid], ref_date, rules)
        if not excl:
            eligible[pid] = ls[pid]
    pool = eligible or ls  # fall back to all starters if none eligible
    def gap(pid):
        d = datetime.date.fromisoformat(pool[pid])
        return (ref_date - d).days
    # longest gap; tie -> most career starts
    return max(pool, key=lambda p: (gap(p), profiles[p]["total_starts"]))


def baseline_b3(profiles, ref_date):
    """Pure longest-gap-since-last-start among all starters (no rest gate)."""
    ls = starters_last_start(profiles)
    if not ls:
        return None
    def gap(pid):
        d = datetime.date.fromisoformat(ls[pid])
        return (ref_date - d).days
    return max(ls, key=lambda p: (gap(p), profiles[p]["total_starts"]))


def run():
    conn = sqlite3.connect(DB)

    pooled = {k: 0 for k in (
        "n", "e1", "e2", "b1", "b2", "b3", "named", "named_correct",
        "novel", "excl_total", "excl_started",
    )}
    conf_dist = {}
    per_team = []
    # split accumulators
    split = {"ace": {k: 0 for k in ("n", "e1", "e2", "b1", "b2")},
             "committee": {k: 0 for k in ("n", "e1", "e2", "b1", "b2")},
             "mid": {k: 0 for k in ("n", "e1", "e2", "b1", "b2")}}

    for team_id, season_id, label in TEAMS:
        history = get_pitching_history(team_id, season_id, db=conn)
        order, actual_starter = ordered_games(history)

        # full-season GS share (rotation concentration)
        gs_counts = {}
        for gid, pid in actual_starter.items():
            gs_counts[pid] = gs_counts.get(pid, 0) + 1
        total_games = len(order)
        top_gs = max(gs_counts.values()) if gs_counts else 0
        share = top_gs / total_games if total_games else 0
        if share >= 0.50:
            cls = "ace"
        elif share < 0.40:
            cls = "committee"
        else:
            cls = "mid"

        detected = detect_league_level(team_name=label)
        detected_supported = get_rules_for_league(
            detected, datetime.date(2026, 6, 1)) is not None

        t = {k: 0 for k in (
            "n", "e1", "e2", "b1", "b2", "b3", "named", "named_correct",
            "novel", "excl_total", "excl_started")}

        for i, (gid, gdate) in enumerate(order):
            if i < 4:  # 5th game onward
                continue
            actual = actual_starter.get(gid)
            if actual is None:
                continue
            ref_date = datetime.date.fromisoformat(gdate)
            asof = [r for r in history if r["game_date"] < gdate]
            if not asof:
                continue
            profiles = build_pitcher_profiles(asof)
            rules = get_nsaa_rules(ref_date)  # nsaa_varsity gate

            # novel starter (no prior start) -> uncoverable by any method
            prior_starters = {p for p, pr in profiles.items()
                              if pr["total_starts"] > 0}
            is_novel = actual not in prior_starters

            pred = compute_starter_prediction(
                profiles, asof, reference_date=ref_date,
                workload=None, league=FORCED_LEAGUE,
            )
            cands = [c["player_id"] for c in pred.top_candidates]
            e_top1 = cands[0] if cands else None
            e_top2 = cands[:2]
            named = pred.predicted_starter["player_id"] if pred.predicted_starter else None
            conf_dist[pred.confidence] = conf_dist.get(pred.confidence, 0) + 1

            b1 = baseline_b1(asof)
            b2 = baseline_b2(profiles, ref_date, rules)
            b3 = baseline_b3(profiles, ref_date)

            t["n"] += 1
            t["e1"] += int(e_top1 == actual)
            t["e2"] += int(actual in e_top2)
            t["b1"] += int(b1 == actual)
            t["b2"] += int(b2 == actual)
            t["b3"] += int(b3 == actual)
            t["novel"] += int(is_novel)
            if named is not None:
                t["named"] += 1
                t["named_correct"] += int(named == actual)

            # unavailability recall: engine-excluded pitchers
            for pid, p in profiles.items():
                excl, _ = _is_excluded(p, ref_date, rules)
                if excl:
                    t["excl_total"] += 1
                    t["excl_started"] += int(pid == actual)

        per_team.append((team_id, label, total_games, share, cls,
                         detected, detected_supported, t))
        for k in t:
            pooled[k] += t[k]
        sk = cls
        for k in ("n", "e1", "e2", "b1", "b2"):
            split[sk][k] += t[k]

    conn.close()

    # ---- OUTPUT ----
    def pct(a, b):
        return f"{100*a/b:4.1f}%" if b else "  n/a"

    print("\n=== PER-TEAM (engine forced league=nsaa_varsity) ===")
    hdr = (f"{'team':>4} {'G':>3} {'topGS%':>6} {'class':>9} {'N':>3} "
           f"{'eTop1':>6} {'eTop2':>6} {'B1':>6} {'B2':>6} {'B3':>6} "
           f"{'named%':>6} {'detLeague':>16} {'sup':>3}  name")
    print(hdr)
    for tid, label, g, share, cls, det, sup, t in per_team:
        n = t["n"]
        print(f"{tid:>4} {g:>3} {share*100:5.0f}% {cls:>9} {n:>3} "
              f"{pct(t['e1'],n):>6} {pct(t['e2'],n):>6} {pct(t['b1'],n):>6} "
              f"{pct(t['b2'],n):>6} {pct(t['b3'],n):>6} "
              f"{pct(t['named'],n):>6} {det:>16} {'Y' if sup else 'N':>3}  {label}")

    P = pooled
    print("\n=== POOLED ===")
    print(f"scored games N = {P['n']}")
    print(f"novel-starter (uncoverable) games = {P['novel']}  ({pct(P['novel'],P['n'])})")
    print(f"  -> predictability ceiling ~= {pct(P['n']-P['novel'],P['n'])}")
    print(f"engine top-1 : {pct(P['e1'],P['n'])}   ({P['e1']}/{P['n']})")
    print(f"engine top-2 : {pct(P['e2'],P['n'])}   ({P['e2']}/{P['n']})")
    print(f"B1 freq      : {pct(P['b1'],P['n'])}   ({P['b1']}/{P['n']})")
    print(f"B2 rested-elig: {pct(P['b2'],P['n'])}  ({P['b2']}/{P['n']})")
    print(f"B3 rested-pure: {pct(P['b3'],P['n'])}  ({P['b3']}/{P['n']})")
    print(f"engine NAMES a starter: {pct(P['named'],P['n'])} of games; "
          f"when named, correct {pct(P['named_correct'],P['named'])}")
    print(f"\nconfidence tier distribution: {conf_dist}")

    print("\n=== POOLED SPLIT (full-season top-GS share) ===")
    for sk in ("ace", "mid", "committee"):
        s = split[sk]
        n = s["n"]
        print(f"{sk:>9}: N={n:>3}  eTop1={pct(s['e1'],n)}  eTop2={pct(s['e2'],n)}  "
              f"B1={pct(s['b1'],n)}  B2={pct(s['b2'],n)}")

    print("\n=== UNAVAILABILITY RECALL (nsaa_varsity gate) ===")
    et, es = P["excl_total"], P["excl_started"]
    print(f"engine-excluded (game,pitcher) pairs = {et}")
    print(f"  of those, pitcher DID start anyway = {es}")
    print(f"  exclusion correctness (did NOT start) = {pct(et-es, et)}")


if __name__ == "__main__":
    run()
