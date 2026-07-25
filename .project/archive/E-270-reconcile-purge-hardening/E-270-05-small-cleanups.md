# E-270-05: Small cleanups — no-op deletion + ordering-fragility comments

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`DONE`
<!-- DONE 2026-07-24. PM AC verdict 4/4, code-reviewer APPROVED. Two PM scope
     rulings: (1) AC-2(ii) is satisfied by STRENGTHENING the pre-existing E-267
     ordering comment rather than adding a redundant second one -- the AC
     specifies a state, not a diff; (2) the pre-existing E-267 `_roster_entry`
     docstring correction is KEPT (the new guard-comment points AT that
     docstring, so a corrected claim would otherwise reference a false one).
     Both of this story's new consequence-claims shipped INVERTED and were
     caught by code-reviewer -- see epic History. -->
<!-- was: IN_PROGRESS -->

## Description
After this story is complete, the verified no-op `not_final_ids &= fresh_ids` line in the scouting loader's game reconcile will be gone (or replaced by a comment pinning the subset invariant), the two ordering-fragility couplings in `_load_team_core` will carry explicit structural comments, and the sole test structurally able to catch a mis-ordered roster reconcile will carry a do-not-delete guard-comment. These are correctness-preserving clarity cleanups the E-267 audit identified.

## Context
The audit's item 5 batched several small cleanups. Two of them — the CLI error-handling wrap (5c) and the CLAUDE.md doc correction (5d) — are carried elsewhere (E-270-02 folds 5c since it restructures the same CLI command; E-270-06 carries 5d because CLAUDE.md is a context-layer path routing to claude-architect). This story carries the remaining two: 5(a) the no-op deletion and 5(b) the structural comments. See epic Technical Notes TN-8.

## Acceptance Criteria
- [ ] **AC-1**: The `not_final_ids &= fresh_ids` line in `_reconcile_absent_games` (`src/gamechanger/loaders/scouting_loader.py`) — a verified no-op (`not_final_ids` is already a subset of `fresh_ids` by construction) — is deleted, OR replaced by a single comment stating the subset invariant if the intent is worth pinning. Behavior is unchanged; existing scouting-loader tests still pass. Per TN-8(a).
- [ ] **AC-2**: `_load_team_core` (`src/gamechanger/loaders/scouting_loader.py`) carries structural comments pinning the two ordering couplings per TN-8(b): (i) the `pre_load_roster_ids` snapshot is a bare local taken early and consumed ~84 lines later; (ii) the game reconcile must follow `_load_boxscores` so the redirect map is populated. The comments make the couplings explicit for a future editor; no behavior changes.
- [ ] **AC-3**: The sole test structurally able to catch the roster reconcile being mis-ordered below the dedup sweep (`test_reconcile_runs_before_dedup...` in `tests/test_roster_grain_reconcile.py`) carries a guard-comment warning against deletion in future cleanup, explaining that the file's unique-name convention makes every other test blind to that ordering. Per TN-8(b).
- [ ] **AC-4**: No behavior change anywhere in this story — it is deletion of a proven no-op plus comments. The full existing test suite for the touched files still passes.

## Technical Approach
Purely a no-op deletion plus comments — no logic changes. For AC-1, confirm the subset invariant holds by reading the loop that builds `not_final_ids` and `fresh_ids` before deleting (every not-final id is added to `fresh_ids` in the same pass). For AC-2/AC-3, add comments only. Follow TN-8. Do NOT let this story drift into refactoring the reconcile ordering — the point is to DOCUMENT the fragility, not change it.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/gamechanger/loaders/scouting_loader.py` (modify — delete the no-op line; add two ordering comments)
- `tests/test_roster_grain_reconcile.py` (modify — add the do-not-delete guard-comment)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (no new tests required; existing tests must still pass)
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Does NOT touch `src/cli/db.py` (item 5c is folded into E-270-02) or `src/db/reconcile_at_load.py` (that is E-270-01) — file-disjoint from every other story. Item 5(d) CLAUDE.md correction is E-270-06.
