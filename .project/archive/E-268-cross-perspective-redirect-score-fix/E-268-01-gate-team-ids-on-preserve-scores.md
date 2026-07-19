# E-268-01: Gate Team-ID Assignments on preserve_scores (Atomic Orientation Tuple) + Regression Test

## Epic
[E-268: Cross-Perspective Redirect Score-Misattribution Fix](epic.md)

## Status
`DONE`

## Description
After this story is complete, `_upsert_game` writes the game orientation tuple `{home_team_id, away_team_id, home_score, away_score}` ATOMICALLY: on a cross-perspective redirect (`preserve_scores=True`) all four fields keep-existing, and on a first-insert / same-perspective reload all four take the incoming values. This closes CC-2 — the torn write where the two team-ids were overwritten unconditionally while the scores were frozen, silently re-crediting runs to the wrong team on both reports.

## Context
Per epic TN-1, the fix locus is `_upsert_game` (`src/gamechanger/loaders/game_loader.py:1373-1378`). Today the scores use a `CASE WHEN ? THEN COALESCE(games.*, excluded.*)` gated on `preserve_scores`, but `home_team_id`/`away_team_id` are overwritten unconditionally from `excluded.*` — so on a redirect that flips orientation, the preserved `home_score` is attributed to the now-swapped away team. Extending the same keep-existing gate to both team-ids makes the four-field orientation tuple move together. DE confirmed this SOUND (epic Background) — the exact analogue of E-261's `game_stream_id` keep-existing treatment at `:1391`.

## Acceptance Criteria
- [ ] **AC-1**: Given a cross-perspective redirect (`preserve_scores=True`), when `_upsert_game` runs, then `home_team_id`, `away_team_id`, `home_score`, and `away_score` are ALL kept-existing (the canonical row's orientation and scores survive) — the two team-ids are gated on `preserve_scores` exactly as the scores are, per Technical Notes TN-1.
- [ ] **AC-2**: Given a first-insert (no conflict) OR a same-perspective reload (`preserve_scores=False`), when `_upsert_game` runs, then all four fields take the incoming values — the existing correction path is unchanged (no regression).
- [ ] **AC-3 (HARD regression test, per TN-2)**: A test seeded from the validators' repro — canonical A-home 5-3, then B loads the same game with `home_away=None` — asserts the row keeps A as home with 5-3 (not B), AND asserts none of `_query_record` (W-L), `_query_runs_avg` (runs for/against), or `_query_recent_games` (recent form) is mis-credited FOR BOTH teams' reports (team A AND team B — the epic states both are corrupted). The test MUST fail pre-fix and pass post-fix.
- [ ] **AC-4 (correction-path test — GAP-5, over-gating regression guard)**: A `preserve_scores=False` case (first-insert AND a same-perspective reload) asserts all four orientation fields `{home_team_id, away_team_id, home_score, away_score}` TAKE the INCOMING values — proving the fix did not over-gate (always keep-existing), which would pass AC-3 while silently breaking the same-perspective correction path (AC-2).
- [ ] **AC-5**: The change is gated against the E-257 reconciliation-scoreboard (`bb report reconcile-scoreboard`) per TN-3 — no gated stat's abs-Δ increases, neither ratcheted axis counter increases, `self_games` stays 0 (verified at CLOSURE by the operator, not self-checked from the worktree — dev DB absent there).

## Technical Approach
Extend the score-gating CASE at `game_loader.py:1373-1378` to the two team-id assignments so the orientation tuple writes atomically. The exact SQL/CASE shaping is the implementer's decision; the requirement is atomicity of the four-field tuple under `preserve_scores`. Seed the regression test from the in-memory `ScoutingLoader` repro described in TN-2.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/game_loader.py` (`_upsert_game`, the orientation-tuple gating)
- Test file under `tests/` (the HARD regression test)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Regression test written and passing (fails pre-fix, passes post-fix)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
- [ ] E-257 reconciliation-scoreboard ratchet not regressed — verified at CLOSURE by the operator against live data (not self-checked from the worktree — dev DB absent there), per TN-3

## Notes
Closes CC-2 (two-channel CONFIRMED/high). Master record: `.project/research/2026-07-19-rerun-accumulate-only-audit.md`. SEPARATE from E-267 (distinct COALESCE-asymmetry mechanism).
