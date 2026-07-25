# E-270-04: Player-line per-game reconcile companion tests

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`DONE`
<!-- DONE 2026-07-24. PM AC verdict 4/4, code-reviewer APPROVED. The story's
     real deliverable is EVIDENCE, not coverage: mutation 1 (bypass the global
     `if not boxscores` short-circuit) leaves the existing :468 test PASSING,
     which converts the audit's annotation-as-coverage claim from an assertion
     into a demonstration. Strengthened past its ACs during review — see epic
     History (the ENTERED-vs-COMPLETED correction). -->
<!-- was: IN_PROGRESS -->

## Description
After this story is complete, the player-line reconcile will have a test that exercises the REAL per-game skip path — a previously-loaded game whose key is absent from an otherwise-populated fresh boxscore dict — plus a paired variant proving the reconcile still runs on the game that IS present. This replaces a mis-annotated coverage claim: the existing `test_missing_boxscore_404_retires_nothing` passes a whole-empty boxscores dict and so only exercises the global `if not boxscores` early-return, never the per-game path.

## Context
The audit found `test_missing_boxscore_404_retires_nothing` (`tests/test_player_line_reconcile.py:468`) claims per-game-404 safety but passes `_crawl(team, {})` — a whole-dict-empty fixture that trips the `if not boxscores` short-circuit in `_load_team_core`, so the reconcile never runs. No test in the file drives the per-game shape (one previously-loaded game's key absent from an otherwise-populated dict). This becomes a landmine if [[IDEA-158]] is ever implemented. See epic Technical Notes TN-7 for the exact fixture shapes.

## Acceptance Criteria
- [ ] **AC-1**: A new test drives the REAL per-game skip path per TN-7: first load TWO games (A and B); re-scout returns a NON-EMPTY boxscores dict containing only game B's key (game A's key absent). Game A's prior player lines SURVIVE (no fresh evidence for A → bias to refuse), and game B's lines survive.
- [ ] **AC-2**: A paired stronger variant proves the reconcile actually RAN on the present game: same shape, but game B's re-scout drops one player while staying populated → that player's line IS retired, game A untouched. Game B's block is sized at 3+ players so the 3→2 drop clears the 0.5 floor unambiguously. Per TN-7.
- [ ] **AC-3**: The tests are placed in `tests/test_player_line_reconcile.py` (immediately after the existing :468 test) with descriptive names distinguishing the absent-game (retires nothing) case from the covered-game-drop (retires the dropped player) case.
- [ ] **AC-4**: The existing `test_missing_boxscore_404_retires_nothing` is left in place (it is not wrong, only insufficient); the companion ADDS the missing per-game coverage rather than replacing it. All existing tests in the file still pass.

## Technical Approach
Reuse the file's existing fixture helpers (`_crawl`, `_boxscore`, `_team_block`, `_insert_team`, `ScoutingLoader`, `_batting_players`). The absent-game case is `_crawl(team, {GAME_B: _boxscore(...)})` after a two-game first load — a non-empty dict with GAME_A's key missing. The covered-game-drop variant re-scouts GAME_B with one fewer player in the block. Follow the fixture shapes in TN-7. This is a test-only story; verify the boxscore fixture shapes against the authoritative payload structure, not the implementation (`.claude/rules/testing.md` Test-Validates-Spec). Note the `.claude/rules/testing.md` guidance on annotation-as-coverage — this story is the mechanical alternative (drive the real path) to the comment the audit flagged.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `tests/test_player_line_reconcile.py` (modify — two companion tests after :468)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Test-only story, independent of the game-grain cap (this is the player-line grain). Guards against the [[IDEA-158]] landmine without implementing IDEA-158 (an explicit epic Non-Goal).
