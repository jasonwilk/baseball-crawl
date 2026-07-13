# E-261-04: Operator repair pass — `bb data merge-duplicate-games`

## Epic
[E-261: Cross-Perspective Game-Dedup Fidelity](./epic.md)

## Status
`DONE`

## Description
After this story, the operator can repair databases already damaged by the two dedup defects without regenerating every affected report: `bb data merge-duplicate-games` detects historical cross-perspective duplicate `games` pairs and merges them via the canonical helper, and restores `game_stream_id` values poisoned by the pre-fix redirect clobber. Dry-run by default, `--execute` to apply, following the `bb data fix-self-games` precedent.

## Context
Prevention (01/03a/03b) stops new damage and self-heals a team on report regeneration, but pairs for teams nobody regenerates persist, and poisoned `game_stream_id` values have NO regeneration path at all (the clobbered value is simply wrong data the redirect will now preserve). Known damage as of 2026-07-12: 6 poisoned rows in the dev DB (from the diagnosis runs), at least one erroring pair in production (the degraded Pat Hagge Patriots Reserve report). Scope and detection constraints are in epic TN-5.

## Acceptance Criteria
- [ ] **AC-1**: Given a DB containing a cross-perspective duplicate pair (TN-2 Defect B shape), when `bb data merge-duplicate-games` runs (no flags), then it prints the merge plan (pair ids, dates, teams, scorelines, per-child-table row counts, AND the per-pair play counts) and writes NOTHING (dry-run default). A pair is included in the merge plan ONLY when ALL corroboration conditions hold: disjoint cross-perspective (PRIMARY) + score-tolerance + near/matching play counts (Codex P1-2 — the play-count safeguard is a REQUIRED gate on inclusion, since the merge deletes a `games` row; a pair failing it is REFUSED, not planned).
- [ ] **AC-2**: Given the same DB, when run with `--execute`, then the pair is merged via `merge_duplicate_game()`, the CLI owns and commits the transaction, and a re-run reports zero remaining pairs (idempotent).
- [ ] **AC-3**: Given a group the detection cannot disambiguate (possible doubleheader, or a merge-helper refusal), when the command runs, then the group is REFUSED with one WARN per group naming the candidate rows, left unmerged in both modes, and refusals do NOT cause a non-zero exit by themselves (mirror `bb data dedup-players` fork handling).
- [ ] **AC-4**: Given tracked-perspective rows whose `game_stream_id` was clobbered (differs from `game_id` AND equals another row's `game_id` or a merged pair's source event id per TN-5), when run with `--execute`, then those rows are restored to self-keyed (`game_stream_id = game_id`). Restore is HARDENED per finding DE-4: it fires only when ALL of a game's perspectives are tracked (any game carrying a member perspective is skipped); the "poisoned value equals another row's `game_id` / redirect source" is a HARD corroboration condition (never restore on a bare value-differs check); member-perspective rows are never modified (asserted by test); and the restore is idempotent (a re-run over already-restored rows is a no-op, asserted by test).
- [ ] **AC-5**: Failure model is CONTINUE-PER-ITEM (Codex P1-1, matching `dedup-players`/`fix-self-games`): each pair is processed under a per-item `try/except`; on failure the command calls `conn.rollback()` to discard the failed item's partial writes (shared-connection partial-commit footgun rule), logs the failure, and CONTINUES to the next item; after the loop it exits non-zero if ANY item failed. It does NOT abort the whole run on the first failure, and it never leaves a failed item's partial writes to be committed by a later item's commit.
- [ ] **AC-6**: Tests cover detection (including a pair REFUSED for failing the near/matching play-count corroboration, Codex P1-2), dry-run inertness, execute+idempotency, refusal, stream-id restore scoping, the continue-per-item failure exit path (error-path testing rule), AND that the CLI imports and reuses E-261-03a's offline predicate from `src/db/game_merge.py` rather than re-inlining it (the import/reuse verification moved here from 03a per Codex P2-3).

## Technical Approach
Per TN-5. Detection: same `(season_id, game_date, unordered pair)` grouping the post-load validation uses, using the offline corroboration variant of the E-261-03a predicate (disjoint cross-perspective as the PRIMARY gate, with score-tolerance + near play counts as corroboration only) — the schedule-count signal is unavailable offline, so bias toward REFUSE on ambiguity. Apply the hard cardinality gate (finding DE-4): merge only a group of EXACTLY 2 rows with disjoint single perspectives; REFUSE any group of ≥3 rows (a doubleheader that was also cross-perspective loaded is 4 rows). Reuse the OFFLINE predicate factored into `src/db/game_merge.py` by E-261-03a (do NOT re-inline the search/filter logic) — see epic finding-J resolution. CLI in `src/cli/data.py` alongside `fix-self-games`; route DB access through `resolve_db_path()`/`get_connection()`.

## Dependencies
- **Blocked by**: E-261-02 (merge helper), E-261-03b (self-healing path + healed-state contract; transitively includes E-261-03a, which factors the shared offline predicate into `game_merge.py`)
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py` (modify — new subcommand)
- `src/db/game_merge.py` (modify — CLI-side detection/plan functions; reuse the offline predicate E-261-03a factored here, do not re-inline)
- `tests/test_cli_data_merge_duplicate_games.py` (create)

## Agent Hint
data-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
The keep-vs-drop decision on this story is RESOLVED: KEEP (epic Resolved Decisions) — the in-pipeline path (E-261-03b) self-heals regenerated teams, but the poisoned-`game_stream_id` restore has NO regeneration self-heal path and teams nobody regenerates still need the pair-merge. Operator closure steps (reconcile-scoreboard before/after, live regeneration check) live in the epic Success Criteria, not here.
