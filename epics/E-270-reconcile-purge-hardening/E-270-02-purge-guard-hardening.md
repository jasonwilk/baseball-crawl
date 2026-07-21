# E-270-02: Purge guard hardening — typo-proof guard, informed+typed confirm, flag split, auto-backup

## Epic
[E-270: Harden Reconcile-at-Load and Purge](../E-270-reconcile-purge-hardening/epic.md)

## Status
`TODO`

## Description
After this story is complete, `bb db purge-scouting` will refuse on a typo-class `APP_ENV=prod` (and every other out-of-set value), show the resolved DB path and per-table row counts before the confirmation prompt, require typed confirmation on production, honor a split `--force` (prod-refusal override) / `--yes` (prompt skip), and auto-back-up the database fail-closed before any DELETE. The most destructive command in the system stops failing open on a typo and stops destroying data with no recovery point.

## Context
The E-267 audit found four verified purge-guard weaknesses: (a) `APP_ENV=prod` normalizes to non-production so the guard passes and the purge proceeds, and `validate_app_env()` has zero call sites in `src/cli/`; (b) the guard keys on `APP_ENV` while destruction keys on `resolve_db_path()`, and the confirm prompt never shows the resolved path or row counts (the path is only logged AFTER confirm); (c) `--force` disarms BOTH the prod refusal AND the prompt; (d) no pre-purge backup, though `scripts/backup_db.py` / `backup_database` exists. This story also folds in audit item 5(c) — wrapping the `purge_scouting_data()` CLI call with formatted error handling (currently a raw traceback) — because it edits the same command. See epic Technical Notes TN-5 for the full sequence and layering.

## Acceptance Criteria
- [ ] **AC-1**: Given `APP_ENV=prod` (or any value normalizing outside the recognized set), when `bb db purge-scouting` runs, then it aborts loudly with a non-zero exit and no rows are deleted — `check_purge_production_guard` calls `validate_app_env()` at the top (before `is_production()`), and the CLI converts the resulting `RuntimeError` to a clean `typer.Exit(1)`. Per TN-5(a).
- [ ] **AC-2**: Given a real (non-`--yes`) invocation, when the confirmation is presented, then the prompt text shows the resolved DB path (`resolve_db_path`) and a per-table row-count table over `PURGE_DELETE_ORDER`, produced by a read-only `preview_purge(db_path) -> PurgePreview` in `src/db/purge_scouting.py`. Counts are advisory display ("as of prompt") and no control-flow keys off them. Per TN-5(b).
- [ ] **AC-3**: Given `is_production()`, when the operator is prompted, then a TYPED confirmation is required (type the resolved DB filename or the literal `'purge'`); a mismatch aborts and `purge_scouting_data` is NOT called. Per TN-5(b).
- [ ] **AC-4**: `--force` and `--yes` are separate flags per TN-5(c): `--force` overrides the production refusal ONLY (flows to the library `force`); `--yes` skips the interactive prompt ONLY (never reaches the library). `--force` without `--yes` still prompts; `--yes` without `--force` still refuses on production. A scripted production purge requires both.
- [ ] **AC-5**: Given a real (post-confirmation) purge, when it runs, then `backup_database(db_path=db_path)` is invoked FIRST and, if it raises for any reason, the purge is ABORTED with a non-zero exit and a clear message before any DELETE (the library's `BEGIN IMMEDIATE` is never reached). Sequence and rationale per TN-5(d) (backup after confirm, fail-closed). NOTE for the test author (data-engineer): `backup_database`'s DESTINATION is hardwired to `<repo_root>/data/backups/` via `parents[2]`, independent of `db_path` — so the AC-5 test MUST monkeypatch `backup_database` (both to assert call-ordering / that a raise aborts before the purge AND to prevent a CliRunner test writing a real snapshot into the repo's `data/backups/`).
- [ ] **AC-6**: Given `purge_scouting_data()` itself raises during the purge, when invoked via the CLI, then the CLI surfaces a formatted error message and a non-zero exit (no raw traceback) — audit item 5(c). Per TN-8(c) / TN-5.
- [ ] **AC-7**: The existing purge behavior is otherwise unchanged: `KEEP_TABLES` / `PURGE_DELETE_ORDER` partition, single-transaction FK-safe deletes, `_assert_foreign_keys_on`, post-commit HTML unlink, and identity/auth preservation all still hold; existing `tests/test_purge_scouting.py` and `tests/test_cli_db.py` tests still pass (updated where the CLI signature/flow changed).
- [ ] **AC-8**: The `validate_app_env` typo guard is NOT overridable by the production-refusal escape hatch. Given `APP_ENV=prod` (an out-of-recognized-set typo), when `bb db purge-scouting --force --yes` runs, then it STILL aborts with a non-zero exit and deletes nothing — `--force` overrides only the production REFUSAL, never the typo guard (a typo means the environment posture is ambiguous, so it must fail closed regardless of override flags). This is the epic's own fail-open lesson (`.claude/rules/python-style.md` "missing safety signal defaults to REFUSE") applied to its own spec. A dedicated test pins it.

## Technical Approach
Library changes in `src/db/purge_scouting.py`: add the `validate_app_env()` call at the top of `check_purge_production_guard`, and add the read-only `preview_purge` + `PurgePreview` dataclass. CLI changes in `src/cli/db.py`: split the flags, render the preview + resolved path before the prompt, add the production typed-confirmation branch, invoke `backup_database` fail-closed after confirmation and before `purge_scouting_data`, and wrap the whole flow in formatted error handling. Follow the sequence and layering in epic Technical Notes TN-5 exactly (guard → preview → typed-confirm/`--yes` → backup → purge; backup at the CLI layer; counts display-only). Error-path tests are required (`.claude/rules/testing.md` Error-Path Testing): backup-raises → purge not called + non-zero exit; typed-confirm mismatch on prod → abort, purge not called; the `--force`/`--yes` matrix. Library bits (guard, `preview_purge`) test in `tests/test_purge_scouting.py`; CLI bits in `tests/test_cli_db.py` (CliRunner). Accepted residual (a direct library caller bypasses backup) is documented in TN-5(d) — do not add a library-level backup.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/purge_scouting.py` (modify — `validate_app_env` call in the guard; `preview_purge` + `PurgePreview`)
- `src/cli/db.py` (modify — flag split, preview/path display, typed-confirm, fail-closed backup, formatted error handling)
- `tests/test_purge_scouting.py` (modify — guard raises on `prod`; `preview_purge` counts)
- `tests/test_cli_db.py` (modify — flag matrix, typed-confirm mismatch, backup-fail-closed, formatted error)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests

## Notes
No migration. `validate_app_env()` (`src/api/helpers.py`) raises `RuntimeError`; `backup_database(db_path=None) -> Path` (`src/db/backup.py`) uses the SQLite online backup API and raises fail-closed on an absent/locked DB. This story folds audit item 5(c); E-270-05 carries only items 5(a)/5(b) to keep `src/cli/db.py` edited by one story.
