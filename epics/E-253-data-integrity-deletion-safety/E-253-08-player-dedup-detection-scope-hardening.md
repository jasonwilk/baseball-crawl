# E-253-08: Player-Dedup Detection & Recompute-Scope Hardening

## Epic
[E-253: Data-Integrity & Deletion Safety](epic.md)

## Status
`TODO`

## Description
After this story is complete, the player-dedup detection will catch accented-name duplicates (Unicode fold consistent with the planner), will not create spurious dedup edges from `LIKE` metacharacters in first names, and the load-path dedup will not delete canonical `boxscore_only` season rows in scopes the end-of-load recompute never rebuilds.

## Context
Three LOW findings, all in `src/db/player_dedup.py`, grouped because they share one file and one concern (dedup correctness):
- **ASCII-only NOCASE** (`:201`/`:205`): detection uses `COLLATE NOCASE`, which is ASCII-only, so accented-name duplicates are missed — diverging from the planner's Unicode fold.
- **Unescaped LIKE wildcards** (`:207`/`:211`): first names are interpolated into a `LIKE (first_name || '%')` without escaping, so a first name containing `%` or `_` creates spurious prefix edges — welding legitimate collapses into refused forks.
- **boxscore_only unrebuilt-scope deletion** (`:850`, latent, multi-season only): load-path dedup deletes canonical `boxscore_only` season rows in scopes the end-of-load recompute never rebuilds. Latent today (live DB has one season; cross-season is a permanent Non-Goal) but a real data-loss path.

## Acceptance Criteria
- [ ] **AC-1**: Given two roster entries for the same human whose names differ only by diacritics (e.g., `José` / `Jose`) on the same `(team_id, season_id)`, when detection runs, then they are detected as a duplicate pair — the fold matches the planner's Unicode fold, not ASCII-only NOCASE. Proven by a test.
- [ ] **AC-2**: Given a first name containing a `LIKE` metacharacter (`%` or `_`), when detection runs, then no spurious prefix edge is created — the wildcard is treated literally. Proven by a test that would produce a false edge without escaping.
- [ ] **AC-3**: Given a load-path dedup on a scope the end-of-load recompute does NOT rebuild, when dedup executes, then it does not delete canonical `boxscore_only` season rows that would be left unrebuilt (no silent data loss). Proven by a test exercising the unrebuilt-scope path.
- [ ] **AC-4**: The fork-refusal and connected-component invariants from E-249 are preserved — this story hardens detection edges and deletion scope only, and does not change the "refuse, don't guess" fork behavior or the per-`(team_id, season_id)` component partition (`.claude/rules/data-model.md`).

## Technical Approach
The implementing agent owns the fold mechanism (align with the planner's existing Unicode fold), the `LIKE` escaping, and the deletion-scope guard. Verify each fix against a failing-then-passing test. Do not alter the E-249 component/fork semantics.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/player_dedup.py` (detection self-join ~201-211; the boxscore_only deletion path ~850)
- `tests/` — accented-name detection test, LIKE-metacharacter test, unrebuilt-scope deletion-guard test

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Cross-reference: `.claude/rules/data-model.md` ("Player Dedup: Components, Fork Refusal, Transaction Ownership"; "Season-Aggregate Parity" — the `boxscore_only` provenance ownership). This story does NOT re-introduce cross-season identity (Non-Goal); the boxscore_only guard is a latent-defect fix only.

Scoping note (internal review iter-1, O2): this story intentionally bundles two detection-edge fixes (AC-1/AC-2, ~lines 201-211) with the deletion-scope data-loss guard (AC-3, ~line 850) as ONE cohesive single-file (`player_dedup.py`) dedup-correctness pass. The concerns are distinct regions but share a file and owner; keeping them together avoids serial-ordering overhead for two small diffs. If the implementer finds the combined diff unwieldy, the deletion-scope guard (AC-3) is the clean split point.
