# E-270-01: Game-grain retire hardening — absolute cap + stripped-perspective guard

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`DONE`
<!-- DONE 2026-07-24. PM AC verdict 8/8 (AC-4 failed round 1 — the retire loop
     re-enumerated the two protection branches instead of consuming the shared
     predicate — remediated and re-verified). code-reviewer APPROVED 8/8; the
     round-1 MUST FIX and both SHOULD FIXes are terminal. The `exempt` narrowing
     (SHOULD FIX 1) was accepted by PM and TN-1/TN-2 were amended to match.
     A post-DONE addendum (test-and-comment only: a second `else`-arm test plus
     three corrected claims in a docstring and two source comments) was
     PM-re-verified against all 8 ACs — the refusal-gate code is byte-identical
     to the version verified at DONE, so DONE stands unamended. See epic
     History 2026-07-24 "E-270-01 addendum". -->
<!-- was: IN_PROGRESS -->

## Description
After this story is complete, the game-grain retire (`retire_absent_games` in `src/db/reconcile_at_load.py`) will refuse a retire pass when more than `MAX_GAME_RETIREMENTS` retire-eligible games are absent from the fresh schedule (an absolute cap on top of the `FLOOR_RATIO` gate), and it will refuse to hard-delete a game that still holds another perspective's child stat rows even after that perspective's `game_perspectives` row has been stripped. Both protections share ONE predicate so the cap's exempt set can never drift from the loop's refusal set.

## Context
This story merges audit items 1 ([[IDEA-160]] `MAX_GAME_RETIREMENTS`) and 2 ([[IDEA-159]] stripped-perspective un-protection). They are merged because they interlock: the cap must be evaluated over `absent − exempt`, where `exempt` is exactly the set of games the loop would refuse on cross-perspective grounds — and item 2 WIDENS that refusal set. Shipping them separately would create an ordering hazard where the cap's exempt set knows only the old refusal branch while the loop refuses on both, re-opening the deadlock the cap exists to prevent. See epic Technical Notes TN-1 (population correctness / deadlock trap), TN-2 (shared predicate), TN-3 (composition + constant), TN-4 (refusal distinguishability).

## Acceptance Criteria
- [ ] **AC-1**: A new module constant `MAX_GAME_RETIREMENTS = 2` exists in `src/db/reconcile_at_load.py` next to `MAX_ROSTER_DEPARTURES` (operator decision 2026-07-21; rationale in epic Technical Notes TN-3).
- [ ] **AC-2**: Given a fresh crawl that PASSES `FLOOR_RATIO` (fresh comparable ≥ 0.5 × prior) but leaves more than `MAX_GAME_RETIREMENTS` retire-eligible games absent, when `retire_absent_games` runs, then the whole pass is REFUSED (zero games retired) — the cap fires where the floor would not. Test fixture MUST be sized so the floor passes and only the cap refuses (a fixture that also fails the floor proves nothing about the cap).
- [ ] **AC-3**: The cap is evaluated over retire-eligible removals (`absent − exempt`), NOT raw `len(absent)`, per TN-1. Given a team carrying **at least `MAX_GAME_RETIREMENTS` cross-perspective-protected absent games PLUS at least one genuine single-perspective removal** — so raw `len(absent)` = cap+1 (a buggy raw-count impl refuses the whole pass) while `len(absent − exempt)` = 1 (the correct impl retires it) — when the pass runs, then the genuine removal STILL retires (no permanent-refusal deadlock). This discrimination floor (≥ cap protected + ≥ 1 genuine) is mandatory: a fixture with FEWER than cap protected games passes even against the buggy raw-count code and proves nothing. This regression test is mandatory.
- [ ] **AC-4**: A single shared predicate `_game_is_cross_perspective_protected(conn, game_id, team_id)` (ORing `_other_perspectives` non-empty and the new `_foreign_perspective_child_rows_exist`) is consumed by BOTH the `exempt` precompute and the retire-loop refusal branch, per TN-2. A test pins that a game refused via the foreign-child-data branch is ALSO excluded from the cap count (exempt == refusal).
- [ ] **AC-5**: The foreign-child guard queries the `_PERSPECTIVE_CHILD_TABLES` constant (guard-surface == delete-surface, per TN-2), NOT a hand-enumerated table list — so it covers all FIVE child tables including `reconciliation_discrepancies`. Given a game reduced to a single `game_perspectives` row for this team (so `_other_perspectives` returns empty) but still holding a child stat row under a different `perspective_team_id` in ANY of the five tables — including the `reconciliation_discrepancies`-only case — when `retire_absent_games` classifies it REMOVED, then it is REFUSED (not hard-deleted) and all rows survive. `_other_perspectives()` is NOT widened (TN-2). A test asserts the `reconciliation_discrepancies`-only foreign footprint is refused (proving the guard is not a 4-table hand-list).
- [ ] **AC-6**: The cap guard composes with the existing `boxscores_complete` guard via `and` (both must narrow), per TN-3. Tests pin the compose direction: `boxscores_complete=False` refuses even when `len(absent − exempt) <= cap`; and `len(absent − exempt) > cap` refuses even when `boxscores_complete=True`.
- [ ] **AC-7**: The refusal-reason WARN distinguishes the cap-tripped cause (naming the cap constant and the retire-eligible absent count) from the boxscores-incomplete and floor causes, per TN-4. A test asserts the cap constant appears in the cap-case WARN and does not in the floor/boxscores cases.
- [ ] **AC-8**: `MAX_ROSTER_DEPARTURES`, the universal `FLOOR_RATIO` gate, and the `classify_absences` extra_guard cannot-widen invariant are unchanged; existing `test_game_grain_reconcile.py` and `test_roster_grain_reconcile.py` tests still pass.

## Technical Approach
Work is contained to `src/db/reconcile_at_load.py` and the existing `tests/test_game_grain_reconcile.py`. Add the constant and the two helpers (`_foreign_perspective_child_rows_exist`, `_game_is_cross_perspective_protected`), precompute `exempt` once over the absent set before `classify_absences` inside `retire_absent_games` (see TN-1 for the binding constraints and why the population is scoped to `absent` rather than all of `prior_ids`), close over it in the composed guard, gate the retire loop's refusal on the shared predicate, and extend the refusal-reason strings. Follow the shape and constraints in epic Technical Notes TN-1 through TN-4 — the population correctness (why raw `len(absent)` deadlocks), the shared-predicate design, the `and` composition, and the WARN distinguishability are all specified there. Reuse the DRY child-table list already imported (`_PERSPECTIVE_CHILD_TABLES`) for the foreign-child existence check rather than re-listing tables. The `.claude/rules/python-style.md` "missing safety signal defaults to REFUSE" rule applies — no new health/evidence input may default to a permissive value.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/reconcile_at_load.py` (modify — constant, two helpers, exempt precompute, composed cap guard, second refusal branch, refusal strings)
- `tests/test_game_grain_reconcile.py` (modify — cap-fires-where-floor-wouldn't, no-deadlock boundary regression, exempt==refusal, stripped-perspective refusal, compose-direction, WARN distinguishability)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Promotes [[IDEA-160]] (bundle-ready cap) and [[IDEA-159]] direction (b) (record-once-cross-perspective via foreign-child rows). IDEA-159 direction (a) is an explicit epic Non-Goal. Do NOT introduce a soft-retire marker or migration (epic Non-Goals; E-267 TN-4).

Reachability note for AC-5 (data-engineer verified): `_prior_loaded_game_ids` scopes `prior` by `game_perspectives.perspective_team_id = team_id`, so a stripped game still carries THIS team's `game_perspectives` row (only the OTHER perspective's junction row was stripped) — it appears in `prior`, and `_other_perspectives` correctly returns EMPTY for it (no foreign junction row survives). An empty `_other_perspectives` here is NOT the guard failing — it is precisely why the foreign-CHILD-row branch is the load-bearing one for this AC. The two-branch OR in the shared predicate is coherent and the scenario is reachable.
