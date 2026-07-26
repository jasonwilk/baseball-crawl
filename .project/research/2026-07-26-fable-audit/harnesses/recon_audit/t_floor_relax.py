"""Does this run's own newly-loaded games relax the floor beyond the documented bound?"""
import logging, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/workspaces/baseball-crawl"); sys.path.insert(0, "/workspaces/baseball-crawl/tests")
from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
import test_game_grain_reconcile as G
logging.disable(logging.CRITICAL)

def fresh():
    tmp = Path(tempfile.mkdtemp()) / "t.db"; run_migrations(db_path=tmp)
    db = sqlite3.connect(str(tmp)); db.execute("PRAGMA foreign_keys=ON;"); return db

for n_new in (0, 5):
    db = fresh(); team = G._insert_team(db)
    old = [G._game(f"g-old-{i}", start_ts=f"2026-04-{10+i:02d}T18:00:00Z",
                   opponent=f"Old Opp {i}") for i in range(3)]
    ScoutingLoader(db).load_team(G._crawl(team, old))
    assert len(G._game_ids(db)) == 3
    new = [G._game(f"g-new-{i}", start_ts=f"2026-05-{10+i:02d}T18:00:00Z",
                   opponent=f"New Opp {i}") for i in range(n_new)]
    # run 2: 2 of the 3 old games vanish (a=2, k=1)
    ScoutingLoader(db).load_team(G._crawl(team, [old[0], *new]))
    left = G._game_ids(db)
    gone = {"g-old-1", "g-old-2"} - left
    print(f"  stale=2, surviving_old=1, brand_new_this_run={n_new}: "
          f"old games RETIRED = {len(gone)}  (documented model predicts 0: 1 >= 0.5*3 is False)")
