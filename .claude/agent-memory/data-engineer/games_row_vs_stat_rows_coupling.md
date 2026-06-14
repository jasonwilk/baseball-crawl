---
name: games-row-vs-stat-rows-coupling
description: A completed games row can exist with ZERO player stat rows — the loader couples them loosely. Counting completed games ≠ counting games-with-data.
metadata:
  type: project
---

# Completed `games` row does NOT imply player stat rows (loose coupling)

Discovered E-235 (2026-06-14, Codex HIGH finding I traced against the real code).

**Fact:** In the reports/scouting pipeline, a completed `games` row (scores non-null)
can exist with ZERO `player_game_batting` / `player_game_pitching` rows.

**Why:** `GameLoader._upsert_game_and_stats` (`src/gamechanger/loaders/game_loader.py`)
writes the games row WITH scores UNCONDITIONALLY first (scores come from the
game-summary entry, not the boxscore body), then loads per-player stats
CONDITIONALLY (`if own_data:` / `if opp_data:`). A score-only boxscore (opponent
unresolved → `opp_data=None`; or GC returned a final score with empty lineups)
yields a scored games row with no stat rows. `LoadResult.loaded` even does
`+= 1  # count the game itself`, so `load_result.loaded ≥ 1` with zero player rows.

**Common in OPPONENT scouting specifically:** opponents often have a final score
on the public scoreboard but no opposing-coach GC scorebook → many scored-but-empty
games rows.

**Schedule stubs are NOT this leak:** `ScheduleLoader` writes `status='scheduled'`
with NULL scores, so any query filtering `home_score IS NOT NULL AND away_score IS
NOT NULL` correctly excludes them. `ScoutingLoader` only writes games-table rows via
`GameLoader` from real boxscores.

**Why:** prevents the recurring mistake of treating "completed games count" as
"games we have data for." `_query_freshness()` in `src/reports/generator.py` does a
bare `COUNT(*) FROM games WHERE ... score IS NOT NULL` — NO join/EXISTS on stat
tables — so it counts SCORED games, not DATA-BEARING games.

**How to apply:** Any "how many games do we actually have data for" count (trust
signals, freshness N-of-M, no-data gates, aggregate-parity denominators) MUST
`EXISTS`-filter on a perspective-scoped stat row, e.g.:
`... AND EXISTS (SELECT 1 FROM player_game_batting b WHERE b.game_id = g.game_id AND b.perspective_team_id = ?)`
(and/or the pitching equivalent). Counting bare completed games over-counts.
Relevant to E-235 N (`completed_games_with_data`) and to Epic C aggregate work.
See [[fixture_seed_not_rollup_consistent]] for the related test-fixture caveat.
