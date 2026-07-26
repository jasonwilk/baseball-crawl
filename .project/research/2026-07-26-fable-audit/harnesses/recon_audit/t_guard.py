"""Per-table reachability of the IDEA-159 foreign-child guard."""
from __future__ import annotations

import logging
import harness
from src.db.game_merge import _PERSPECTIVE_CHILD_TABLES
from src.db.reconcile_at_load import (
    retire_absent_games, _foreign_perspective_child_rows_exist,
    _game_is_cross_perspective_protected, _other_perspectives,
)

logging.disable(logging.CRITICAL)

INSERTS = {
    "player_game_batting": lambda c, g, p: (
        harness.add_player(c, "px"),
        c.execute("INSERT INTO player_game_batting (game_id, player_id, team_id, "
                  "perspective_team_id) VALUES (?, 'px', 2, ?)", (g, p))),
    "player_game_pitching": lambda c, g, p: (
        harness.add_player(c, "px"),
        c.execute("INSERT INTO player_game_pitching (game_id, player_id, team_id, "
                  "perspective_team_id) VALUES (?, 'px', 2, ?)", (g, p))),
    "plays": lambda c, g, p: (
        harness.add_player(c, "px"),
        c.execute(
            "INSERT INTO plays (game_id, play_order, inning, half, season_id, "
            "batting_team_id, batter_id, perspective_team_id) "
            "VALUES (?, 1, 1, 'top', '2026', 2, 'px', ?)", (g, p))),
    "spray_charts": lambda c, g, p: c.execute(
        "INSERT INTO spray_charts (game_id, team_id, perspective_team_id, "
        "chart_type, event_gc_id) VALUES (?, 2, ?, 'offensive', 'e1')", (g, p)),
    "reconciliation_discrepancies": lambda c, g, p: (
        harness.add_player(c, "px"),
        c.execute(
            "INSERT INTO reconciliation_discrepancies (game_id, run_id, team_id, "
            "player_id, perspective_team_id, signal_name, category, status) "
            "VALUES (?, 'r1', 2, 'px', ?, 'x', 'y', 'MATCH')", (g, p))),
}

print("child tables the guard reads:", _PERSPECTIVE_CHILD_TABLES)
print()
for table in _PERSPECTIVE_CHILD_TABLES:
    for label, persp in (("FOREIGN(2)", 2), ("OWN(1)", 1)):
        conn = harness.fresh_db()
        harness.seed_base(conn)
        # single prior game, junction row for team 1 only
        harness.add_game(conn, "gA", perspectives=(1,))
        harness.add_game(conn, "gB", perspectives=(1,))  # keeps floor ratio happy
        INSERTS[table](conn, "gA", persp)
        pred = _foreign_perspective_child_rows_exist(conn, "gA", 1)
        prot = _game_is_cross_perspective_protected(conn, "gA", 1)
        others = _other_perspectives(conn, "gA", 1)
        res = retire_absent_games(
            conn, team_id=1, season_id="2026", fresh_game_ids={"gB"},
            fetch_ok=True, not_final_game_ids=set(), boxscores_complete=True,
        )
        survived = conn.execute(
            "SELECT COUNT(*) FROM games WHERE game_id='gA'").fetchone()[0]
        child_rows = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE game_id='gA'").fetchone()[0]
        print(f"{table:30s} {label:10s} foreign_pred={pred!s:5s} protected={prot!s:5s} "
              f"others={others} -> retired={res.retired_game_ids} "
              f"games_row_survives={survived} child_rows_left={child_rows}")
    print()

print("=== NULL perspective_team_id on a child row (three-valued-logic claim) ===")
conn = harness.fresh_db()
harness.seed_base(conn)
harness.add_game(conn, "gA", perspectives=(1,))
try:
    harness.add_player(conn, "px")
    conn.execute("INSERT INTO plays (game_id, play_order, inning, half, season_id, "
                 "batting_team_id, batter_id, perspective_team_id) "
                 "VALUES ('gA', 1, 1, 'top', '2026', 2, 'px', NULL)")
    print("  NULL insert ACCEPTED -> pred =",
          _foreign_perspective_child_rows_exist(conn, "gA", 1))
except Exception as e:
    print("  NULL insert REJECTED by schema:", type(e).__name__, e)
