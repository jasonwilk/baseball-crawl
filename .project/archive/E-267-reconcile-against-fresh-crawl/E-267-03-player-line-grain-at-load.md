# E-267-03: Player-Line Grain at Load — Retire Removed Per-Player Stat Rows (H1)

## Epic
[E-267: Reconcile-at-Load Against the Fresh Crawl](epic.md)

## Status
`DONE`

## Description
After this story is complete, a re-scout of a game whose fresh boxscore OMITS a player who was present in a prior run retires that player's stale `player_game_batting`/`player_game_pitching` row for that game — as part of the normal load, forward-only. This closes H1 (removed-player stat line inflating the query-time season aggregates).

## Context
The per-player stat writers (`_upsert_batting` ~1423-1447, `_upsert_pitching` ~1484-1504 in `game_loader.py`) iterate ONLY the incoming payload and do no set-difference delete. A player deleted from a boxscore between runs (e.g. a scorekeeper fixes a mis-credited line) keeps their row, and since `get_season_batting`/`get_season_pitching` SUM these rows at query time, that opponent's season totals stay permanently inflated. Uses the E-267-01 primitive scoped to the per-game per-perspective stat rows.

## Acceptance Criteria
- [ ] **AC-1**: A prior player line for `(game_id, perspective_team_id)` is retired ONLY when the fresh boxscore for that EXACT `(game_id, perspective_team_id)` is a POPULATED 200 — HTTP 200 whose per-player `stats` arrays are non-empty (players listed WITH stats), per TN-11 — AND the specific prior player is absent from it. When so, that player's stale `player_game_*` leaf row(s) are hard-deleted and no longer counted in `get_season_batting`/`get_season_pitching`. A bare "fetched OK" 200 is NOT sufficient.
  - **AC-1a (populated is PER-BLOCK, not per-payload — added 2026-07-19, code-reviewer MUST FIX):** A boxscore payload carries TWO team blocks (own + opponent), and `_load_team_stats` writes BOTH under the same `perspective_team_id`. The populated test MUST be evaluated PER BLOCK and must gate only the prior lines belonging to that block. A single payload-level boolean OR'd across both blocks is INSUFFICIENT: a HALF-populated payload (own block has stats, opponent block `stats: []`) then reads as full authority, and the populated own block's ids inflate `comparable` past the floor, hard-deleting the empty block's live prior lines. Worked case: own populates comparable to 5 against 8 prior, `5 >= 4` passes the gate, and 3 stale opponent lines are wrongly deleted. A half-populated payload is a NON-POPULATED shape for the empty block and MUST retire nothing from it.
  - **AC-1b (uncovered rows are LEFT ALONE — ruled 2026-07-19):** Per-block scoping means a prior row whose `team_id` matches NEITHER block in the fresh payload is covered by no block and is therefore left untouched. This is the CORRECT posture, not a gap to close: no fresh evidence covers such a row, so retiring it would be a delete on absence-of-evidence — the exact false-delete class this epic exists to prevent. The accepted consequence is a bounded H1 residual (a stale line that no re-scout will retire). Its blast radius, VERIFIED by a code-reviewer sweep of all 12 modules reading `player_game_*` (2026-07-19):
    - **No stat aggregate can be affected.** All four value-bearing readers scope by BOTH `perspective_team_id` and `team_id`, so an uncovered row can never inflate a stat: `get_season_batting` (`src/api/db.py:501,503`), `get_season_pitching` (`:569,571`), `get_pitching_workload` (`:178-179`), `get_pitching_history`/`build_pitcher_profiles` (`:308-309`).
    - **BUT presence, count, and date CAN be affected.** `_completed_games_with_data()` (`src/reports/generator.py:597-616`) is the SOLE `player_game_*` reader with no `team_id` predicate — its two EXISTS subqueries (`:606-607`, `:610-611`) scope only by `(game_id, perspective_team_id)`. An uncovered row keeps its live `perspective_team_id` (only `team_id` went stale), so it satisfies that check and keeps its game counted. Consequences: a game stays in the coverage count N; `MAX(g.game_date)` can hold the coach-facing "Through {date}" at a game with no live player data; and — the worst of the three — `N > 0` is preserved, **suppressing the E-235 Phase 4b HIGH-1 silent-empty-report gate that exists precisely to catch this class**. Reachability needs BOTH the uncovered condition AND the game having no other live rows for that perspective: narrow, but not construct-only. Tracked as IDEA-156; it is PRE-EXISTING code this story does not touch, NOT an E-267 regression.
  - **Do NOT "fix" this by widening the retire to uncovered rows.** This instruction is more important now that the residual is known to reach a coach-facing surface, because that is exactly the discovery that provokes closing it the dangerous way. Widening the retire means deleting on absence-of-evidence and reintroduces the false-delete hazard. The correct fix is the `_completed_games_with_data` predicate gap (IDEA-156), not the retire scope.
  <!-- AC-1b JUSTIFICATION AMENDED 2026-07-19. The original text claimed the residual was
       "coach-invisible by construction" because coach-facing reads are team_id-scoped. That premise
       was FALSIFIED by a code-reviewer file:line sweep: it holds for all four stat aggregates but NOT
       for _completed_games_with_data. The RULING is unchanged (leaving uncovered rows alone is
       correct bias-to-refuse); only the justification changed. Recorded because a future reader
       inheriting the wrong reason would mis-scope any follow-on fix. -->

- [ ] **AC-2**: Given ANY non-populated boxscore shape, NO prior line is retired (bias-to-refuse). Per TN-11, only a POPULATED 200 can trigger a retire. The shapes split into two classes, which have DIFFERENT audit obligations:
  - **Gated refusals — a WARN IS required.** A scored-but-EMPTY envelope (lineup/pitching categories present but per-player `stats: []` — the MODAL opponent-scouting case), a HALF-populated envelope with respect to its empty block (per AC-1a), or an incomplete/not-yet-republished boxscore. Here the reconcile RUNS, evaluates a candidate set, and decides to refuse — that decision is the auditable event, so it emits a WARN naming the reason. Per-grain granularity: one WARN per affected `player_game_*` table, since batting and pitching are gated independently and can refuse for different reasons (populated-gate vs ratio floor); a merged single line would discard the reason distinction TN-4 depends on.
  - **Structural non-arrivals — NO WARN is required at this grain.** A 404 (no game-stream record → the crawler skips the game) or a 401 (auth expiry → the whole crawl aborts). No payload is loaded, so the reconcile never runs; there is no candidate set, no decision, and nothing deleted to audit. The fetch path owns the logging for these. Requiring a refusal record for code that never executed would be noise, not auditability.

  <!-- AC-2 WORDING CORRECTED 2026-07-19 (PM ruling; independently flagged in PM's own AC verdict and by
       code-reviewer as SHOULD FIX 4). The original wording listed the 404 and 401 shapes alongside the
       empty-envelope shape and asserted a WARN "is emitted" for all of them. That is a factual claim
       about behavior that is FALSE: no code runs at this grain on those paths, so no player-line WARN
       exists or should. This is a correction of a wrong AC, NOT a retrofit to match shipped code —
       the distinction that matters is that the original conflated a REFUSAL DECISION (auditable) with
       a NON-ARRIVAL (nothing to audit). The safety property — no prior line retired — holds absolutely
       on all shapes and is unchanged. Contrast with the per-table WARN count, which was left alone
       because the AC was merely SILENT about multi-grain calls rather than wrong about them. -->

- [ ] **AC-3**: The set-difference AND the DELETE are both scoped by `perspective_team_id` (per TN-10 risk 1) so a two-perspective game never cross-retires the OTHER perspective's rows (different `player_id`s per perspective).
- [ ] **AC-4**: The reconcile runs on RAW `(game_id, perspective_team_id)` boxscore ids BEFORE the `dedup_team_players` sweep (`scouting_loader.py:197-211`) — per TN-10 risk 2, running after dedup (which merges `player_id`s) would false-flag "absent" and wrong-retire.
- [ ] **AC-5**: The DELETE removes ONLY the `player_game_*` leaf row, NEVER the `players` parent (per TN-10 risk 6 — other games/perspectives/roster reference it).
- [ ] **AC-6**: Regression test per TN-7: reproduces the inflated season aggregate (fails pre-fix — SUM includes the dropped player) and asserts the corrected aggregate post-fix; plus bias-to-refuse cases proving NO retire on (a) a scored-but-EMPTY envelope (categories present, per-player `stats: []`), (b) a 404, and (c) a 401 — none may retire a prior line; plus (d) a two-perspective case proving the other perspective's rows survive, (e) an assertion the `players` row survives, and (f) **[GAP-3 ordering safety]** a case proving a player who survives ONLY because the reconcile ran on RAW ids BEFORE `dedup_team_players` (AC-4) is NOT retired — the test fails if the reconcile is positioned after dedup (a mis-order deletes a live line); plus (g) **[HALF-POPULATED payload — added 2026-07-19 per AC-1a]** a payload whose OWN block carries stats while the OPPONENT block is `stats: []` (and the mirror case), asserting the empty block's prior lines ALL survive and a WARN is emitted for that block. This test MUST fail against a payload-level populated flag — every pre-existing test uses the BOTH-blocks-empty shape, so the suite passed with the global flag and only an asymmetric fixture discriminates. Size the fixture so the populated block alone would clear the floor ratio (as AC-6(f) does), otherwise the health gate refuses anyway and the test proves nothing.

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
