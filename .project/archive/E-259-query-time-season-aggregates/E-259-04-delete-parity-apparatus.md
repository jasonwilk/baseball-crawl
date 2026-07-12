# E-259-04: Delete the parity and plays-validation apparatus

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`DONE`

## Description
After this story is complete, the aggregate-parity and plays-validation apparatus — which existed only to check the now-dropped stored tables — is deleted at SOURCE: `src/reports/aggregate_parity.py`, the `bb report verify-aggregates` command, and `scripts/validate_plays_stats.py`. Their TEST files are already gone — `tests/test_aggregate_parity.py` was deleted in E-259-02 (its surviving projection/KEYS coverage ported to `tests/test_season_projection.py`) and `tests/test_validate_plays_stats.py` in E-259-03 (both die with the dropped tables) — so this story is source + CLI only, not test deletion.

**Clean-deletion note (verified during story-03 AC-verify):** `aggregate_parity.py` only *imports and aliases* `batting_recompute_select`/`pitching_recompute_select` and the `*_RECOMPUTE_KEYS` tuples — those live in `src/db/season_aggregates.py`, which SURVIVES (they are the live projection consumed by `get_season_batting`/`get_season_pitching` and by `tests/test_season_projection.py`). So deleting `aggregate_parity.py` orphans nothing and requires NO re-home. Do NOT delete or gut `season_aggregates.py`.

## Context
With the tables dropped (story 03) and no writer or reader remaining, `verify-aggregates` compares nothing — post-cutover the aggregate IS the query, so "stored vs. recomputed" has no left-hand side (Technical Notes §6). `scripts/validate_plays_stats.py` (~800 lines) + `tests/test_validate_plays_stats.py` (~1,021 lines) are a reader the audit missed, already a silent no-op because their `fps`/`qab` columns are in the all-NULL set post-E-239 (Technical Notes §7). This is a plain deletion, not a substitution — the surviving live fidelity gate is `bb report reconcile-scoreboard`, which was already an independent, unconditional check and is untouched here.

## Acceptance Criteria
- [ ] **AC-1**: Given `src/reports/aggregate_parity.py`, when this story is complete, then it is deleted and nothing imports from it. (Its test `tests/test_aggregate_parity.py` was already deleted in E-259-02 — do NOT re-claim it here; `src/db/season_aggregates.py` SURVIVES, per the clean-deletion note above.)
- [ ] **AC-2**: Given the `bb report verify-aggregates` command, when this story is complete, then it is removed from the CLI (the import + command wiring in `src/cli/report.py` AND the help-text mention in `src/cli/__init__.py`) and `bb report --help` no longer lists it.
- [ ] **AC-3**: Given `scripts/validate_plays_stats.py`, when this story is complete, then it is deleted and nothing imports from it. (Its test `tests/test_validate_plays_stats.py` was already deleted in E-259-03 — do NOT re-claim it here.)
- [ ] **AC-4**: Given the full suite, when this story is complete, then it is green — no orphaned import of any deleted module, and no EXECUTED test path references `verify-aggregates` or `aggregate_parity`. (The `tests/` tree carries no live `aggregate_parity`/`verify_aggregates` references: `test_season_projection.py:3` is an accurate historical-provenance docstring — "Ported from `tests/test_aggregate_parity.py` (deleted in E-259-02)" — which is reconcile-not-strike, LEAVE it; a `test_recon_scoreboard.py` comment that formerly said "mirrors verify_aggregates" was already swept by DE's cosmetic pass.)
- [ ] **AC-5** (dangling-prose sweep in a surviving module): Given `src/reports/recon_scoreboard.py`, which carries design-rationale prose citing the deleted `aggregate_parity.py` (docstring/comments at ~L9 "Following the `aggregate_parity.py` precedent…", ~L209 "no SQL shared with aggregate_parity", ~L354 "mirroring `verify_aggregates`"), when this story is complete, then each such reference is reworded so it no longer points at a now-deleted file — **preserve the design rationale, state it directly rather than by citing the ghost file; do NOT simply delete the rationale**. This is prose-only (no behavior change) and the module survives; it is the deleter cleaning up references to what it deleted (doc-sweep discipline, `.claude/rules/doc-sweep.md`). These three are the COMPLETE live-`src/` dangling set (CR full-file sweep) — no other surviving `src/` prose references the deleted module.

## Technical Approach
Straight deletion. Grep the tree for any importer of `aggregate_parity` or invoker of `verify-aggregates` before deleting, so no orphan import survives (the `bb report` CLI wiring, any admin route, any doc-referenced invocation — docs go to story 06, not here). The context-layer references (rules/agents/CLAUDE.md/skills that mention `verify-aggregates`) are story 05's eviction sweep, NOT this story — this story deletes code and tests only.

## Dependencies
- **Blocked by**: E-259-03 (the tables these read must be gone first)
- **Blocks**: E-259-06 (runbook doc updates reference the removed command)

## Files to Create or Modify
- `src/reports/aggregate_parity.py` (delete — clean; only aliases from `season_aggregates.py`)
- `scripts/validate_plays_stats.py` (delete)
- `src/cli/report.py` (remove the `verify-aggregates` import + command wiring — L21, L170-171, L188)
- `src/cli/__init__.py` (remove `verify-aggregates` from the `bb report` help-text line, ~L12)
- Do NOT touch `src/db/season_aggregates.py` (survives — live home of the recompute-select + KEYS)
- No test-file deletions (test_aggregate_parity.py gone in E-259-02, test_validate_plays_stats.py gone in E-259-03)
- `src/reports/recon_scoreboard.py` (reword 3 dangling design-rationale prose refs to the deleted `aggregate_parity.py` — ~L9, L209, L354, AC-5)

## Agent Hint
data-engineer

## Handoff Context
- **Produces for E-259-05**: the removed command/module names for the context-layer eviction sweep.
- **Produces for E-259-06**: the removed `verify-aggregates` command that runbooks must stop referencing.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests updated (dead tests removed) and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
This is a net-shrinkage deletion (Technical Notes §6). Do NOT add a replacement integrity check — none exists post-cutover, and `reconcile-scoreboard` already covers the surviving fidelity question.
