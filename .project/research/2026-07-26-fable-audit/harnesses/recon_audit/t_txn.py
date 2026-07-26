import logging, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0,"/workspaces/baseball-crawl"); sys.path.insert(0,"/workspaces/baseball-crawl/tests")
from migrations.apply_migrations import run_migrations
from src.gamechanger.loaders.scouting_loader import ScoutingLoader
from src.db import reconcile_at_load
import test_game_grain_reconcile as G
logging.disable(logging.CRITICAL)
seen=[]
_o = reconcile_at_load._prior_loaded_game_ids
reconcile_at_load._prior_loaded_game_ids = lambda c,t,s: (seen.append(c.in_transaction), _o(c,t,s))[1]
tmp = Path(tempfile.mkdtemp())/"t.db"; run_migrations(db_path=tmp)
db = sqlite3.connect(str(tmp)); db.execute("PRAGMA foreign_keys=ON;")
team = G._insert_team(db)
gs=[G._game(f"g-{i}", start_ts=f"2026-04-1{i}T18:00:00Z", opponent=f"O{i}") for i in range(3)]
ScoutingLoader(db).load_team(G._crawl(team, gs))
ScoutingLoader(db).load_team(G._crawl(team, gs[:2]))
print("  conn.in_transaction at each reconcile entry:", seen)
