# E-262-01: CLI Behavioral Audit Fixes

## Epic
[E-262: Post-Program Housekeeping](epic.md)

## Status
`DONE`

## Description
After this story is complete, three CLI correctness defects from the platform-audit residual table are fixed: `bb data dedup-players` no longer silently executes when both `--dry-run` and `--execute` are passed, `bb data reload-annotated-pitches` no longer reports success when games failed, and `bb status` resolves the database path through the canonical resolver instead of a hardcoded path.

## Context
These are three of the platform-audit residuals ratified into this housekeeping epic (sweep §1, `.project/research/2026-07-12-program-endgame-sweep.md`):
- **#1 (MED):** `bb data dedup-players --dry-run --execute` silently executes. The `dry_run` flag is declared at `src/cli/data.py:65` but never read; `:104` derives `is_dry_run = not execute`, so passing both flags silently runs the destructive path. Contradictory flags should be a loud error, not a silent execute.
- **#2 (MED):** `bb data reload-annotated-pitches` exits 0 even when `games_with_errors > 0` (an unconditional `SystemExit(0)`). A maintenance pass that reports success while games failed hides real ingestion failures from the operator.
- **#3 (LOW):** `bb status` hardcodes `data/app.db` (`src/cli/status.py:21`, `_DB_PATH = _DATA_ROOT / "app.db"`), bypassing the canonical `resolve_db_path()` seam. Every other DB-path consumer routes through `resolve_db_path()`; `bb status` should too, or it reports on the wrong DB under a `DATABASE_PATH` override.

## Acceptance Criteria
- [ ] **AC-1**: Given `bb data dedup-players` is invoked with both `--dry-run` and `--execute`, when the command runs, then it exits non-zero with a clear mutual-exclusion error and performs no merges (the destructive path does not run).
- [ ] **AC-2**: Given `bb data reload-annotated-pitches` completes with one or more games that errored, when the command finishes, then it exits non-zero (a clean all-success run still exits 0).
- [ ] **AC-3**: Given a `DATABASE_PATH` override is set, when `bb status` reports the database location/existence, then it reflects the resolved path from `resolve_db_path()` rather than a hardcoded `data/app.db`.
- [ ] **AC-4**: Tests cover each of the three behaviors (mutual-exclusion error, non-zero exit on errored games, path resolution under override).

## Technical Approach
Fixes are localized to `src/cli/data.py` (dedup flag handling and the reload exit-code path) and `src/cli/status.py` (route the DB-path read through the canonical resolver). The canonical DB-path seam is `resolve_db_path()` in `src/db/paths.py` (see CLAUDE.md Architecture). The implementer decides the exact flag-validation and exit-code shapes.

**Impl note (SE review):** `src/cli/status.py:21` `_DB_PATH` is a MODULE-LEVEL (import-time) constant, used at `:58/:60/:61`. The fix must resolve the path inside the function body, not at import — otherwise a test's monkeypatched `DATABASE_PATH` won't take effect. Also `:61` renders `_DB_PATH.relative_to(_PROJECT_ROOT)` for display; a resolved override OUTSIDE the repo root makes `.relative_to()` raise `ValueError` — guard that. Precedent for the AC-2 exit-code shape already exists in the same file: `fix-self-games` at `data.py:798` uses `SystemExit(0 if remaining == 0 else 1)`.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/cli/data.py`
- `src/cli/status.py`
- `tests/test_cli_data.py` (#1 dedup mutual-exclusion, #2 reload exit code)
- `tests/test_cli_status.py` (#3 db-path resolution)
- (Test Scope Discovery: the enumerated test files are the verifiable floor; the implementer greps `tests/` for any additional importer of the changed modules per `.claude/rules/testing.md` — false-negatives are the risk.)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
Source: endgame sweep §1 residuals #1, #2, #3. These are behavioral (not cosmetic) — hence separated from the cosmetic hygiene sweep (story 02).
