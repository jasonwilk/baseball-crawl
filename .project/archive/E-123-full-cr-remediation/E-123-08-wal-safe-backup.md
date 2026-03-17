# E-123-08: WAL-Safe Database Backup

## Epic
[E-123: Full Code Review Remediation](epic.md)

## Status
`DONE`

## Description
After this story is complete, `backup_database()` will use the SQLite `Connection.backup()` API instead of `shutil.copy2()`, producing consistent backups even when the database is actively being written to in WAL mode.

## Context
CR4-H6 confirmed that `src/db/backup.py:68` uses `shutil.copy2()` which copies only the main `.db` file, not the WAL/SHM sidecar files. If the database is being written to during backup, the copy may be inconsistent. The SQLite `Connection.backup()` API is the standard solution for WAL-mode databases. See `/.project/research/full-code-review/cr4-verified.md` (H-6) for evidence.

## Acceptance Criteria
- [ ] **AC-1**: `backup_database()` uses `sqlite3.Connection.backup()` (or equivalent safe API) instead of `shutil.copy2()`
- [ ] **AC-2**: The backup file is a complete, consistent SQLite database (not dependent on WAL/SHM files)
- [ ] **AC-3**: Backup file naming and rotation behavior is preserved (same filename pattern, same retention logic)
- [ ] **AC-4**: A test verifies that backup produces a valid SQLite database that can be opened and queried
- [ ] **AC-5**: All existing tests pass

## Technical Approach
Read `src/db/backup.py` to understand the current backup flow (path resolution, naming, rotation). Replace the `shutil.copy2()` call with `sqlite3.connect()` to open the source, then `source.backup(dest)` to copy to a new file. The backup API handles WAL checkpointing internally. Preserve all surrounding logic (timestamp naming, retention, logging). See TN-8 in the epic for details.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `src/db/backup.py`
- `tests/test_backup.py` (create if needed, or add to existing test file)

## Agent Hint
software-engineer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Tests written and passing
- [ ] Code follows project style (see CLAUDE.md)
- [ ] No regressions in existing tests
