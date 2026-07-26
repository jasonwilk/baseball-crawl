"""Is the game grain's `comparable` denominator also polluted by this run's own load?

The comment at the ``comparable`` assignment rejects two candidate numerators
because "newly-completed games are not in prior". Test that claim: the reconcile
runs AFTER _load_boxscores, which inserts the new games AND their
game_perspectives rows.
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
from src.db import reconcile_at_load
import test_game_grain_reconcile as G

logging.disable(logging.CRITICAL)

captured = []
_orig = reconcile_at_load._prior_loaded_game_ids


def spy(conn, team_id, season_id):
    out = _orig(conn, team_id, season_id)
    captured.append(sorted(out))
    return out


reconcile_at_load._prior_loaded_game_ids = spy


def fresh_db():
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    run_migrations(db_path=tmp)
    db = sqlite3.connect(str(tmp))
    db.execute("PRAGMA foreign_keys=ON;")
    return db


db = fresh_db()
team = G._insert_team(db)

old = [G._game(f"g-old-{i}", start_ts=f"2026-04-{10+i:02d}T18:00:00Z",
               opponent=f"Old Opp {i}") for i in range(4)]
ScoutingLoader(db).load_team(G._crawl(team, old))
print("after run 1, games in DB:", sorted(G._game_ids(db)))

# Run 2: one OLD game vanishes; three BRAND-NEW completed games appear.
new = [G._game(f"g-new-{i}", start_ts=f"2026-05-{10+i:02d}T18:00:00Z",
               opponent=f"New Opp {i}") for i in range(3)]
captured.clear()
ScoutingLoader(db).load_team(G._crawl(team, [*old[:3], *new]))

prior_seen = captured[0]
print()
print("prior_ids the reconcile actually read:")
print("   ", prior_seen)
brand_new_in_prior = [g for g in prior_seen if g.startswith("g-new")]
print(f"    -> brand-new-this-run ids present in 'prior': {brand_new_in_prior}")
print(f"    -> claim 'newly-completed games are not in prior' holds? "
      f"{not brand_new_in_prior}")
print()
print("games after run 2:", sorted(G._game_ids(db)))
