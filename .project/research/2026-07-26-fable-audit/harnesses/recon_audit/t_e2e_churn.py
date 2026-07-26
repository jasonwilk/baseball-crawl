"""End-to-end via the REAL producer: ScoutingLoader.load_team, no reconcile mock.

Question: the player-line docstring claims the health gate's numerator
(``prior & fresh``) cannot be inflated by a brand-new player id, and that "an id
churn should REFUSE rather than delete". Drive a total player_id churn through
the real loader and see which happens.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/workspaces/baseball-crawl")
sys.path.insert(0, "/workspaces/baseball-crawl/tests")

from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
import test_player_line_reconcile as H

logging.basicConfig(level=logging.WARNING, format="    LOG %(levelname)s %(message)s")
logging.getLogger().setLevel(logging.WARNING)


def run(old_n: int, new_n: int) -> None:
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    run_migrations(db_path=tmp)
    db = sqlite3.connect(str(tmp))
    db.execute("PRAGMA foreign_keys=ON;")
    team = H._insert_team(db)

    old = [f"old-{i}" for i in range(old_n)]
    new = [f"new-{i}" for i in range(new_n)]

    ScoutingLoader(db).load_team(
        H._crawl(team, {H._GAME: H._boxscore(H._SLUG_A, H._team_block(old))})
    )
    before = H._batting_players(db)
    assert before == set(old), before

    print(f"  run1: {len(before)} lines under OLD ids")
    print(f"  run2: fresh payload carries {new_n} BRAND-NEW ids, zero overlap")
    logs = []
    handler = logging.Handler()
    handler.emit = lambda r: logs.append(r.getMessage()) if r.levelno >= 30 else None
    logging.getLogger().addHandler(handler)
    ScoutingLoader(db).load_team(
        H._crawl(team, {H._GAME: H._boxscore(H._SLUG_A, H._team_block(new))})
    )
    logging.getLogger().removeHandler(handler)

    after = H._batting_players(db)
    survived = after & set(old)
    print(f"    -> old lines surviving: {len(survived)} of {old_n}")
    print(f"    -> new lines present:   {len(after & set(new))} of {new_n}")
    retire_logs = [m for m in logs if "Player-line retire" in m]
    for m in retire_logs:
        print(f"    -> WARN: {m}")
    if not retire_logs:
        print("    -> (no player-line retire WARN emitted)")
    db.close()


print("=== TOTAL churn, fresh block SAME size as the stale set (9 vs 9) ===")
run(9, 9)
print()
print("=== TOTAL churn, fresh block ONE SMALLER than the stale set (9 vs 8) ===")
run(9, 8)
