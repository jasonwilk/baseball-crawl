# E-259-04: Delete the parity and plays-validation apparatus

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`TODO`

## Description
After this story is complete, the aggregate-parity and plays-validation apparatus — which existed only to check the now-dropped stored tables — is deleted: `src/reports/aggregate_parity.py`, the `bb report verify-aggregates` command, `scripts/validate_plays_stats.py`, and all their tests.

## Context
With the tables dropped (story 03) and no writer or reader remaining, `verify-aggregates` compares nothing — post-cutover the aggregate IS the query, so "stored vs. recomputed" has no left-hand side (Technical Notes §6). `scripts/validate_plays_stats.py` (~800 lines) + `tests/test_validate_plays_stats.py` (~1,021 lines) are a reader the audit missed, already a silent no-op because their `fps`/`qab` columns are in the all-NULL set post-E-239 (Technical Notes §7). This is a plain deletion, not a substitution — the surviving live fidelity gate is `bb report reconcile-scoreboard`, which was already an independent, unconditional check and is untouched here.

## Acceptance Criteria
- [ ] **AC-1**: Given `src/reports/aggregate_parity.py`, when this story is complete, then it and its tests (`tests/test_aggregate_parity.py` or equivalent) are deleted, and nothing imports from it.
- [ ] **AC-2**: Given the `bb report verify-aggregates` command, when this story is complete, then it is removed from the CLI and `bb report --help` no longer lists it.
- [ ] **AC-3**: Given `scripts/validate_plays_stats.py` and `tests/test_validate_plays_stats.py`, when this story is complete, then both are deleted, and nothing imports from them.
- [ ] **AC-4**: Given the full suite, when this story is complete, then it is green — no orphaned import of any deleted module, no test referencing `verify-aggregates` or `aggregate_parity`.

## Technical Approach
Straight deletion. Grep the tree for any importer of `aggregate_parity` or invoker of `verify-aggregates` before deleting, so no orphan import survives (the `bb report` CLI wiring, any admin route, any doc-referenced invocation — docs go to story 06, not here). The context-layer references (rules/agents/CLAUDE.md/skills that mention `verify-aggregates`) are story 05's eviction sweep, NOT this story — this story deletes code and tests only.

## Dependencies
- **Blocked by**: E-259-03 (the tables these read must be gone first)
- **Blocks**: E-259-06 (runbook doc updates reference the removed command)

## Files to Create or Modify
- `src/reports/aggregate_parity.py` (delete)
- `tests/test_aggregate_parity.py` (delete)
- `scripts/validate_plays_stats.py` (delete)
- `tests/test_validate_plays_stats.py` (delete)
- `src/cli/report.py` (remove the `verify-aggregates` command wiring)

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
