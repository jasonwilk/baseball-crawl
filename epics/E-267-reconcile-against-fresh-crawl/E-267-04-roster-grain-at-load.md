# E-267-04: Roster Grain at Load — Retire Departed Roster Players (H2)

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`TODO`

## Description
After this story is complete, a re-scout whose fresh roster OMITS a player present in a prior run retires that player's `team_rosters` row for the team+season — as part of the normal load, forward-only. This closes H2 (departed players rendering on the coach-facing report roster grid indefinitely).

## Context
Roster upserts (`_upsert_roster_player` `scouting_loader.py:406-430`; `_upsert_roster_jersey` `game_loader.py:1526-1565`) update present players but never retire absent ones; `_validate_roster_count` only warns. The report roster grid `_query_roster` (`generator.py:626-641`) reads `team_rosters` directly, so an ex-player renders forever. Uses the E-267-01 primitive scoped to the roster grain.

## Acceptance Criteria
- [ ] **AC-1**: Given a team re-scouted whose fresh roster omits a player present in a prior run, and the absence is corroborated as REMOVED (the existing empty-guard `scouting_loader.py:343-345` passed AND the STRICTER roster-grain drop guard held, per Technical Notes TN-2 + TN-12), when the load runs, then that player's `team_rosters` row for the `(team_id, season_id)` is hard-deleted and no longer renders in `_query_roster`.
- [ ] **AC-2 (roster drop cap — LOCKED, DE-decided)**: The roster grain uses an ABSOLUTE cap `MAX_ROSTER_DEPARTURES = 2` (NOT the flat FLOOR_RATIO, too loose for a 12-15 roster — a 9-of-14 mid-edit passes 0.5), per Technical Notes TN-12. Given `absent = {DB roster player_ids for (team_id, season_id)} − {fresh player_id set}`: when `len(absent) > 2` (≥3), then NO roster row is retired (bias-to-refuse) and ONE WARN is logged carrying `team_id`, `season_id`, `roster_db_count`, `fresh_crawl_count`, `absent_count`, and the absent `player_id` list; when `len(absent) <= 2`, the retire proceeds. Only DELETEs are capped — the ADD path (new fresh-crawl players) is NEVER gated. An empty/incomplete payload (empty-guard) is likewise never retired.
- [ ] **AC-3**: The DELETE removes ONLY the `team_rosters` row, NEVER the `players` parent (per TN-10 risk 6 — the player may still have stat rows or appear on other teams; roster departure is not player deletion).
- [ ] **AC-4**: The set-difference and DELETE are scoped to the roster natural key `(team_id, season_id)` — `team_rosters` has NO `perspective_team_id` (PK `(team_id, player_id, season_id)`, per TN-10 risk 1, DE-confirmed). Delete the team-season's roster rows whose `player_id` is absent from the fresh crawl set; no other team's roster can be touched (one team-season = one roster source).
- [ ] **AC-5**: Departed-player semantics are explicit (per TN-10 risk 1 caveat): a player absent from the fresh roster crawl but present in stat tables via the `game_loader._upsert_roster` boxscore backfill (e.g. cut mid-season) IS retired from the roster display while KEEPING their `player_game_*` rows (stat tables FK to `players`, not `team_rosters` — no FK break). The roster grid reflects the current roster; season stats retain the departed player's games.
- [ ] **AC-6 (leaderboard-survives-departure guard test — baseball-coach SHOULD-HAVE, TN-13)**: The repo ALREADY resolves season-leaderboard names via the `players` table and left-joins `team_rosters` only for jersey (`src/api/db.py:457` and `:521`), so no fix is needed — this AC LOCKS that behavior with a regression assertion. Add a test that retires a departed player from `team_rosters` and asserts they STILL appear in the season batting/pitching leaderboards with their name and production intact (only the roster-grid disappearance is intended). The test guards against a future change that would regress the leaderboard join to gate on `team_rosters` membership.
- [ ] **AC-7**: Regression test per TN-7: reproduces the stale roster row (fails pre-fix — ex-player renders in `_query_roster`) and asserts the single-departure retire post-fix; plus bias-to-refuse cases for (a) an empty/incomplete roster payload and (b) a ≥3-player single-run drop (a 9-of-14 mid-edit roster must NOT retire the 5 missing, and must emit the AC-2 WARN); an assertion the `players` row survives; an assertion a backfilled-then-cut player's `player_game_*` rows survive the roster retire (AC-5 semantics); **[GAP-4 cross-team scoping]** a two-team-season case — retire team A's roster and assert team B's `(team_id, season_id)` roster is UNTOUCHED (guards the `WHERE team_id=? AND season_id=?` on the NOT-IN delete); and coverage of the AC-6 leaderboard-survives-departure guard.

## Technical Approach
Wire the E-267-01 `classify_absences` health-gate into the roster-load path, scoped to `(team_id, season_id)`, reusing the existing empty-guard (`scouting_loader.py:343-345`) plus the LOCKED `MAX_ROSTER_DEPARTURES = 2` absolute drop cap (TN-12) as the corroboration — NOT the flat FLOOR_RATIO. Unify with the jersey-upsert path if that simplifies the set-difference. Hard-delete the `team_rosters` leaf only (risk 6). Lock the already-correct `players`-resolved leaderboard join with a regression assertion (AC-6) — no production change expected there.

## Dependencies
- **Blocked by**: E-267-03
- **Blocks**: E-267-05

## Files to Create or Modify
- The roster-load path (`src/gamechanger/loaders/scouting_loader.py`, `src/gamechanger/loaders/game_loader.py`, and/or the E-267-01 module)
- Test file under `tests/` (incl. the AC-6 leaderboard-survives-departure regression assertion — the leaderboard join is already `players`-resolved at `src/api/db.py:457`/`:521`, so no production code change is expected there)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] E-257 reconciliation-scoreboard ratchet not regressed — verified at CLOSURE by the operator (not self-checked from the worktree — dev DB absent there), per TN-5

## Notes
Closes H2 (two-channel CONFIRMED/high). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`.
