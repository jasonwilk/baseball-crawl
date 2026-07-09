# E-259-06: Update runbooks and admin docs

## Epic
[E-259: Query-Time Season Aggregates](epic.md)

## Status
`TODO`

## Description
After this story is complete, the operator-facing docs in `docs/admin/` no longer prescribe `bb report verify-aggregates` or describe the stored season-aggregate tables as live, and any maintenance recipe that chained through `verify-aggregates` is corrected to reflect the query-time reality.

## Context
`bb report verify-aggregates` was the operator parity diagnostic and an aggregate-integrity cutover gate; it is removed in story 04. Runbooks that reference it (maintenance chains, the aggregate-integrity check, any `backfill → recompute → verify-aggregates` recipe) are now stale. This is the docs-writer half of the eviction — story 05 handles the context layer (`.claude/**` + CLAUDE.md), this story handles `docs/admin/`.

## Acceptance Criteria
- [ ] **AC-1**: Given `docs/admin/` runbooks, when this story is complete, then no runbook prescribes `bb report verify-aggregates` as a step, and any recipe that chained through it is corrected or removed.
- [ ] **AC-2**: Given any `docs/admin/` prose describing the stored `player_season_*` tables or `canonical_recompute` as live operator-relevant surfaces, when this story is complete, then it is corrected to the query-time-derivation reality.
- [ ] **AC-3**: Given the touched docs, when this story is complete, then each carries the staleness convention (Last updated: date, Source: E-259) per `.claude/rules/documentation.md`.
- [ ] **AC-4**: Given the doc-sweep discipline, when this story is verified, then it was applied (token grep for `verify-aggregates`/`canonical_recompute`/`player_season` PLUS synonym expansion PLUS a semantic read of the touched sections), not a keyword grep alone.
- [ ] **AC-5**: Given `.claude/agent-memory/docs-writer/MEMORY.md:24` (docs-writer's own memory), which carries a **positional** pointer "...operator docs live in operations.md ... (after verify-aggregates)", when this story is complete, then that positional reference is corrected — it does not claim the command exists, but it goes stale once this story rewrites `operations.md`. docs-writer edits its own memory per the ownership carve-out.

## Technical Approach
docs-writer owns `docs/admin/` and its own `.claude/agent-memory/docs-writer/` memory. Grep the tree for `verify-aggregates`, `aggregate`, `canonical_recompute`, `player_season` and read each surrounding section. Note the surviving fidelity diagnostic is `bb report reconcile-scoreboard` — where a runbook step genuinely needs an integrity/fidelity check, point to that; where the old step was pure aggregate-parity (now meaningless), remove it rather than substitute.

## Dependencies
- **Blocked by**: E-259-04 (the command must be gone before docs stop prescribing it)
- **Blocks**: None

## Files to Create or Modify
- `docs/admin/operations.md`, `docs/admin/production-deployment.md`, and any other `docs/admin/` runbook referencing the retired command/tables (grep to enumerate)
- `.claude/agent-memory/docs-writer/MEMORY.md` (line ~24 positional pointer — docs-writer own-memory, AC-5)

## Agent Hint
docs-writer

## Handoff Context
None.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Doc-sweep discipline applied (AC-4); staleness headers updated (AC-3)
- [ ] Docs follow the documentation rules (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Do not substitute `reconcile-scoreboard` for `verify-aggregates` blindly — they answer different questions (plays-vs-boxscore fidelity vs. stored-vs-recomputed parity). Only point to `reconcile-scoreboard` where a fidelity check is genuinely wanted; elsewhere the step is simply removed.
