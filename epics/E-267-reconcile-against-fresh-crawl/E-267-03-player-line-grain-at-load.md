# E-267-03: Player-Line Grain at Load — Retire Removed Per-Player Stat Rows (H1)

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`TODO`

## Description
After this story is complete, a re-scout of a game whose fresh boxscore OMITS a player who was present in a prior run retires that player's stale `player_game_batting`/`player_game_pitching` row for that game — as part of the normal load, forward-only. This closes H1 (removed-player stat line inflating the query-time season aggregates).

## Context
The per-player stat writers (`_upsert_batting` ~1423-1447, `_upsert_pitching` ~1484-1504 in `game_loader.py`) iterate ONLY the incoming payload and do no set-difference delete. A player deleted from a boxscore between runs (e.g. a scorekeeper fixes a mis-credited line) keeps their row, and since `get_season_batting`/`get_season_pitching` SUM these rows at query time, that opponent's season totals stay permanently inflated. Uses the E-267-01 primitive scoped to the per-game per-perspective stat rows.

## Acceptance Criteria
- [ ] **AC-1**: A prior player line for `(game_id, perspective_team_id)` is retired ONLY when the fresh boxscore for that EXACT `(game_id, perspective_team_id)` is a POPULATED 200 — HTTP 200 whose per-player `stats` arrays are non-empty (players listed WITH stats), per TN-11 — AND the specific prior player is absent from it. When so, that player's stale `player_game_*` leaf row(s) are hard-deleted and no longer counted in `get_season_batting`/`get_season_pitching`. A bare "fetched OK" 200 is NOT sufficient.
- [ ] **AC-2**: Given ANY non-populated boxscore shape — a scored-but-EMPTY envelope (lineup/pitching categories present but per-player `stats: []`, the MODAL opponent-scouting case), an incomplete/not-yet-republished boxscore, a 404 (no game-stream record), or a 401 (auth expiry) — when the load runs, then NO prior line is retired (bias-to-refuse) and one WARN is emitted. Per TN-11, only a POPULATED 200 can trigger a retire.
- [ ] **AC-3**: The set-difference AND the DELETE are both scoped by `perspective_team_id` (per TN-10 risk 1) so a two-perspective game never cross-retires the OTHER perspective's rows (different `player_id`s per perspective).
- [ ] **AC-4**: The reconcile runs on RAW `(game_id, perspective_team_id)` boxscore ids BEFORE the `dedup_team_players` sweep (`scouting_loader.py:197-211`) — per TN-10 risk 2, running after dedup (which merges `player_id`s) would false-flag "absent" and wrong-retire.
- [ ] **AC-5**: The DELETE removes ONLY the `player_game_*` leaf row, NEVER the `players` parent (per TN-10 risk 6 — other games/perspectives/roster reference it).
- [ ] **AC-6**: Regression test per TN-7: reproduces the inflated season aggregate (fails pre-fix — SUM includes the dropped player) and asserts the corrected aggregate post-fix; plus bias-to-refuse cases proving NO retire on (a) a scored-but-EMPTY envelope (categories present, per-player `stats: []`), (b) a 404, and (c) a 401 — none may retire a prior line; plus (d) a two-perspective case proving the other perspective's rows survive, (e) an assertion the `players` row survives, and (f) **[GAP-3 ordering safety]** a case proving a player who survives ONLY because the reconcile ran on RAW ids BEFORE `dedup_team_players` (AC-4) is NOT retired — the test fails if the reconcile is positioned after dedup (a mis-order deletes a live line).

## Technical Approach
Wire the E-267-01 `classify_absences` health-gate into the per-player stat-load path, scoped to `(game_id, perspective_team_id)`, positioned BEFORE the dedup sweep (risk 2). Hard-delete leaf rows only (risk 6), perspective-scoped DELETE (risk 1). The scored-but-empty-boxscore-never-retires guard (TN-2) is the load-bearing correctness rule here.

## Dependencies
- **Blocked by**: E-267-02
- **Blocks**: E-267-04 (shared load-path module)

## Files to Create or Modify
- The per-player stat-load path (`src/gamechanger/loaders/game_loader.py` and/or the E-267-01 module)
- Test file under `tests/`

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] E-257 reconciliation-scoreboard ratchet not regressed — verified at CLOSURE by the operator (not self-checked from the worktree — dev DB absent there), per TN-5

## Notes
Closes H1 (two-channel CONFIRMED/high). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
