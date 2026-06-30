# E-246-03: Consolidate DB-path resolution cascade to one canonical source

## Epic
[E-246: Dead-Code Removal & Low-Risk Consolidation](epic.md)

## Status
`DONE`

## Description
After this story is complete, the override→`DATABASE_PATH`→default DB-path resolution cascade — currently hand-written in 5 modules and already non-identical — will resolve through a single canonical function. As an intended side effect, `cli/data.py` commands will newly honor the `DATABASE_PATH` env var, closing an operator-visible inconsistency.

## Context
The sweep's M1 finding: the DB-path resolution cascade is hand-written 5× (`src/db/backup.py:22-41`, `src/db/reset.py:23-41`, `src/cli/data.py:38-44`, `src/cli/report.py:31`, `src/api/db.py`) and the copies have already diverged. Critically, `cli/data.py`'s private copy is dead (no caller wires it in), so `bb data` commands ignore `DATABASE_PATH` while `bb report` honors it — an operator-visible inconsistency where the same env var changes behavior in one command group but not another.

This is the one intended behavior change in the epic (flagged in epic Open Questions): after consolidation, `bb data` commands honor `DATABASE_PATH`.

## Acceptance Criteria
- [ ] **AC-1**: Given five modules each resolve the DB path independently, when the story completes, then a single canonical resolution function is the source of truth and the other modules delegate to it (no module re-implements the override→`DATABASE_PATH`→default cascade inline).
- [ ] **AC-2**: Given the dead private resolver in `cli/data.py`, when the story completes, then it is removed and the `bb data` command option defaults are wired through the canonical function.
- [ ] **AC-3**: Given `DATABASE_PATH` is set in the environment and no explicit path override is passed, when a `bb data` command resolves its DB path, then it uses the `DATABASE_PATH` value (verified by an automated test). This is the intended behavior change.
- [ ] **AC-4**: Given the canonical function, when an explicit path override is passed, then the override wins over `DATABASE_PATH`, which wins over the default — preserving the existing precedence for the modules that already honored it.
- [ ] **AC-5**: Given the consolidation, when the DB/CLI test modules run (`tests/test_backup.py`, `tests/test_db_reset_guards.py`, `tests/test_cli_report.py`, and the new `tests/test_cli_data.py` from AC-3), then they pass. (The full-suite-green check across `tests/` is the epic-level closure gate, not a per-story AC — it is only authoritative in the merged main checkout, not the worktree.)

## Technical Approach
Report locations (re-verify before acting): `src/db/backup.py:22-41`, `src/db/reset.py:23-41`, `src/cli/data.py:38-44`, `src/cli/report.py:31`, `src/api/db.py`. The sweep suggests making `reset.py::get_db_path` the canonical source and having the others import it (illustrative — the implementing agent owns where the canonical function lives, subject to the `src/` import-boundary rules in CLAUDE.md). Confirm the precedence order matches the modules that currently honor `DATABASE_PATH` (e.g. `report.py`) so no module regresses.

## Dependencies
- **Blocked by**: None
- **Blocks**: E-246-06 (both touch `src/cli/data.py`)

## Files to Create or Modify
- `src/db/backup.py`
- `src/db/reset.py`
- `src/cli/data.py`
- `src/cli/report.py`
- `src/api/db.py`
- `tests/test_cli_data.py` (create — automated test for AC-3's `DATABASE_PATH`-honoring behavior; `tests/test_cli_data.py` does not exist today, so this is a new module, or extend an existing CLI test module such as `tests/test_cli.py`)

## Agent Hint
software-engineer

## Handoff Context
- **Produces for E-246-06**: This story finalizes the shape of `src/cli/data.py`'s top-of-file DB-path option wiring. E-246-06 (CLI/safety dedup) edits the same file and must run after this story to avoid a conflicting edit on the shared file.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing (including the new `DATABASE_PATH`-honoring test)
- [ ] No regressions in existing tests
- [ ] Code follows project style (see CLAUDE.md)

## Notes
This story carries an operator-awareness flag (see epic Open Questions): `bb data` commands newly honor `DATABASE_PATH`.
